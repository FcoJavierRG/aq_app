"""
AQ Tool (Multi-floor + Enhanced Geometry-based Turn Detection)

Inputs:
  - PDF (single page) or raster image (PNG/JPG)
Outputs:
  - metrics dict
  - networkx graph of routes
  - skeleton mask (numpy array)
"""

import os, math, json, cv2, fitz
import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
from dataclasses import dataclass
from typing import Tuple, Dict, Any, List
from skimage.morphology import skeletonize, remove_small_holes, remove_small_objects


# ================================================================
# 1. Preprocessing configs
# ================================================================
@dataclass
class PreprocessConfig:
    blur_ksize: int = 3
    adaptive_block: int = 51
    adaptive_C: int = 5
    min_room_hole_area_px: int = 500
    min_corridor_object_px: int = 200
    wall_thickness_close: int = 3

@dataclass
class GraphConfig:
    skeleton_prune_len_px: int = 10
    node_merge_radius_px: int = 3


# ================================================================
# 2. Image loading & preprocessing
# ================================================================
def load_image_any(path: str) -> np.ndarray:
    ext = os.path.splitext(path.lower())[1]
    if ext == ".pdf":
        doc = fitz.open(path)
        page = doc.load_page(0)
        zoom = 300 / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if img.ndim == 2:
            return img
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    else:
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Cannot read image: {path}")
        return img

def preprocess_floorplan(bgr: np.ndarray, cfg: PreprocessConfig) -> Tuple[np.ndarray, np.ndarray]:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    if cfg.blur_ksize > 1:
        gray = cv2.medianBlur(gray, cfg.blur_ksize)
    bin_inv = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
        cfg.adaptive_block | 1, cfg.adaptive_C
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (cfg.wall_thickness_close, cfg.wall_thickness_close))
    walls = cv2.morphologyEx(bin_inv, cv2.MORPH_CLOSE, kernel)
    free_space = (walls == 0).astype(np.uint8)
    free_space_bool = free_space.astype(bool)
    free_space_bool = remove_small_holes(free_space_bool, area_threshold=cfg.min_room_hole_area_px)
    free_space_bool = remove_small_objects(free_space_bool, min_size=cfg.min_corridor_object_px)
    walkable_mask = free_space_bool.astype(np.uint8)
    return (255 - walls), walkable_mask


# ================================================================
# 3. Skeletonization & Graph conversion
# ================================================================
def mask_to_skeleton(mask: np.ndarray) -> np.ndarray:
    return skeletonize(mask.astype(bool)).astype(np.uint8)

def _neighbors(y: int, x: int, h: int, w: int) -> List[Tuple[int,int]]:
    res = []
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            if dy==0 and dx==0: continue
            ny,nx = y+dy, x+dx
            if 0<=ny<h and 0<=nx<w: res.append((ny,nx))
    return res

def skeleton_to_graph(skel: np.ndarray, gcfg: GraphConfig) -> nx.Graph:
    """Convert skeleton into a sparse graph."""
    h, w = skel.shape
    ys, xs = np.where(skel > 0)
    S = set(zip(ys, xs))
    degree = {}
    for (y, x) in S:
        deg = sum((ny, nx) in S for ny, nx in _neighbors(y, x, h, w))
        degree[(y, x)] = deg

    junctions = {(y, x) for (y, x), d in degree.items() if d >= 3}
    endpoints = {(y, x) for (y, x), d in degree.items() if d == 1}
    keypoints = junctions | endpoints

    G = nx.Graph()
    point_to_node = {}
    for idx, (y, x) in enumerate(keypoints):
        G.add_node(idx, y=float(y), x=float(x))
        point_to_node[(y, x)] = idx

    visited = set()
    for (y, x) in keypoints:
        for ny, nx_ in _neighbors(y, x, h, w):
            if (ny, nx_) not in S: continue
            if (y, x, ny, nx_) in visited: continue

            path = [(y, x)]
            py, px = y, x
            cy, cx = ny, nx_
            while True:
                path.append((cy, cx))
                visited.add((py, px, cy, cx))
                visited.add((cy, cx, py, px))
                if (cy, cx) in keypoints and (cy, cx) != (y, x):
                    u = point_to_node[(y, x)]
                    v = point_to_node[(cy, cx)]
                    if u != v:
                        G.add_edge(u, v, weight=len(path), path=path)
                    break
                nbrs = [(ny, nx_) for ny, nx_ in _neighbors(cy, cx, h, w)
                        if (ny, nx_) in S and (ny, nx_) != (py, px)]
                if not nbrs: break
                if len(nbrs) > 1: break
                py, px = cy, cx
                cy, cx = nbrs[0]
    return G


# ================================================================
# 4. Multi-floor graph merging helper
# ================================================================
def link_floors(graphs: List[nx.Graph]) -> nx.Graph:
    """Merge multiple floor graphs and add vertical connectors."""
    if not graphs: return nx.Graph()
    if len(graphs) == 1: return graphs[0]
    G_total = nx.compose_all(graphs)
    for i in range(len(graphs)-1):
        G1, G2 = graphs[i], graphs[i+1]
        x1 = np.mean([G1.nodes[n]["x"] for n in G1])
        y1 = np.mean([G1.nodes[n]["y"] for n in G1])
        x2 = np.mean([G2.nodes[n]["x"] for n in G2])
        y2 = np.mean([G2.nodes[n]["y"] for n in G2])
        def nearest(G, x, y):
            return min(G.nodes, key=lambda n: (G.nodes[n]["x"]-x)**2 + (G.nodes[n]["y"]-y)**2)
        n1, n2 = nearest(G1, x1, y1), nearest(G2, x2, y2)
        G_total.add_edge(n1, n2, weight=3.0, type="vertical")
    return G_total


# ================================================================
# 5. Metrics
# ================================================================
def compute_metrics(G: nx.Graph, px_per_meter: float) -> Dict[str,Any]:
    if len(G)==0:
        return {"num_nodes":0,"num_edges":0,"AQ_v1":0.0}
    return {
        "num_nodes": int(G.number_of_nodes()),
        "num_edges": int(G.number_of_edges()),
        "AQ_v1": float(len(G))/max(px_per_meter,1.0)
    }


# ================================================================
# 6. Full pipeline runner
# ================================================================
def run_aq_pipeline(input_path:str, px_per_meter=50.0,
                    outdir="out", min_corridor_px=200,
                    prune_len_px=10, return_skeleton=False):
    os.makedirs(outdir,exist_ok=True)
    pcfg=PreprocessConfig(min_corridor_object_px=min_corridor_px)
    gcfg=GraphConfig(skeleton_prune_len_px=prune_len_px)
    img=load_image_any(input_path)
    _, walk=preprocess_floorplan(img,pcfg)
    skel=mask_to_skeleton(walk)
    G=skeleton_to_graph(skel,gcfg)
    metrics=compute_metrics(G,px_per_meter)
    if return_skeleton: return metrics, G, skel
    return metrics, G


# ================================================================
# 7. Geometry-based AccessQuotient
# ================================================================
def _angle_between_vecs(v1, v2):
    a = np.array(v1, dtype=float)
    b = np.array(v2, dtype=float)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na==0 or nb==0: return 0.0
    cosv = np.dot(a,b)/(na*nb)
    cosv = float(np.clip(cosv, -1.0, 1.0))
    return math.degrees(math.acos(cosv))

def _build_route_polyline(route, G):
    poly=[]
    for i in range(len(route)-1):
        u,v=route[i],route[i+1]
        data=G.get_edge_data(u,v)
        if data is None or data.get("path") is None:
            xu,yu=G.nodes[u]["x"],G.nodes[u]["y"]
            xv,yv=G.nodes[v]["x"],G.nodes[v]["y"]
            segment=[(xu,yu),(xv,yv)]
        else:
            seg=data["path"]
            segment=[(float(xc),float(yc)) for (yc,xc) in seg]
        if not poly: poly.extend(segment)
        else:
            if np.allclose(poly[-1],segment[0]): poly.extend(segment[1:])
            else: poly.extend(segment)
    cleaned=[tuple(poly[0])]
    for p in poly[1:]:
        if not np.allclose(p, cleaned[-1]):
            cleaned.append(tuple(p))
    return cleaned

def compute_access_quotient(G, routes, weights,
                            min_branch_len=10,
                            angle_thresh_deg=30.0,
                            min_turn_len_px=3.0):
    if len(routes)!=len(weights):
        raise AssertionError("routes and weights must align")
    AQ_S, AQ_F = 0.0, 0.0
    route_results=[]
    for r_idx,(route,w) in enumerate(zip(routes,weights)):
        P_MF=1.0; E_M=0.0
        decision_points=[]; turns_count=0; turn_points=[]
        # Junctions
        for i in range(1,len(route)-1):
            node=route[i]
            if G.degree[node]>=3:
                valid_branches=sum(
                    1 for nbr in G.neighbors(node)
                    if G.edges[node,nbr].get("weight",1.0)>=min_branch_len)
                if valid_branches>=2:
                    N_ij=valid_branches; P_ij=1.0/N_ij; E_ij=(N_ij+1)/2.0-1.0
                    P_MF*=P_ij; E_M+=E_ij
                    decision_points.append((node,N_ij,P_ij,E_ij,"junction"))
        # Turns
        poly=_build_route_polyline(route,G)
        if len(poly)>=3:
            vecs=[(poly[i+1][0]-poly[i][0],poly[i+1][1]-poly[i][1])
                  for i in range(len(poly)-1)]
            seg_lengths=[math.hypot(v[0],v[1]) for v in vecs]
            merged_vecs=[]; merged_lengths=[]; i=0
            while i<len(vecs):
                v_total=vecs[i]; L_total=seg_lengths[i]; j=i+1
                while j<len(vecs) and seg_lengths[j]<min_turn_len_px:
                    v_total=(v_total[0]+vecs[j][0], v_total[1]+vecs[j][1])
                    L_total+=seg_lengths[j]; j+=1
                merged_vecs.append(v_total); merged_lengths.append(L_total)
                i=j
            for i in range(1,len(merged_vecs)):
                ang=_angle_between_vecs(merged_vecs[i-1],merged_vecs[i])
                if ang>=angle_thresh_deg:
                    turns_count+=1
                    idx=sum(int(l>=min_turn_len_px) for l in seg_lengths[:i])
                    turn_points.append(poly[idx])
                    N_ij=2; P_ij=0.5; E_ij=0.5
                    P_MF*=P_ij; E_M+=E_ij
                    decision_points.append((f"turn_{idx}",N_ij,P_ij,E_ij,
                                            f"turn(angle={round(ang,1)})"))
        AQ_S+=w*P_MF
        AQ_F+=w*(1.0/(1.0+E_M))
        route_results.append({
            "route_id":r_idx,"P_MF":P_MF,"E_M":E_M,
            "decision_points":decision_points,
            "turns":turns_count,"turn_points":turn_points,
            "length":len(route)
        })
    return {"AQ_S":AQ_S,"AQ_F":AQ_F,"routes":route_results}


# ================================================================
# 8. Route extraction
# ================================================================
def extract_routes(G:nx.Graph,max_routes=5,overlap_thresh=0.7):
    if G.number_of_nodes()==0: return [],[]
    endpoints=[n for n,d in G.degree() if d==1]
    if len(endpoints)<2: return [],[]
    routes=[]; rng=np.random.default_rng(42)
    sampled=rng.choice(endpoints,size=min(len(endpoints),max_routes*2),replace=False)
    for u in sampled:
        lengths,paths=nx.single_source_dijkstra(G,u,weight="weight")
        if not lengths: continue
        v=max(lengths,key=lengths.get); path=paths[v]
        edgeset=set(zip(path[:-1],path[1:]))
        overlap=max(len(edgeset & set(zip(r[:-1],r[1:])))
                    / max(len(edgeset),1) for r in routes) if routes else 0.0
        if overlap<overlap_thresh:
            routes.append(path)
        if len(routes)>=max_routes: break
    weights=[1.0/len(routes)]*len(routes) if routes else []
    return routes,weights

