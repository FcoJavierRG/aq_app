"""
AQ Tool (Jupyter version) with AccessQuotient support

Inputs: PDF (single page) or raster image (PNG/JPG)
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
from IPython.display import display
import networkx as nx
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
    """
    Convert skeleton into a sparse graph:
    - Nodes: junctions (degree>=3) and endpoints (degree==1)
    - Edges: traced paths between nodes
    """
    h, w = skel.shape
    ys, xs = np.where(skel > 0)
    S = set(zip(ys, xs))

    # Degree of each pixel
    degree = {}
    for (y, x) in S:
        deg = sum((ny, nx) in S for ny, nx in _neighbors(y, x, h, w))
        degree[(y, x)] = deg

    junctions = {(y, x) for (y, x), d in degree.items() if d >= 3}
    endpoints = {(y, x) for (y, x), d in degree.items() if d == 1}
    keypoints = junctions | endpoints

    # Map each keypoint to a node id
    G = nx.Graph()
    point_to_node = {}
    for idx, (y, x) in enumerate(keypoints):
        G.add_node(idx, y=float(y), x=float(x))
        point_to_node[(y, x)] = idx

    visited = set()

    # Traverse skeleton from each keypoint
    for (y, x) in keypoints:
        for ny, nx_ in _neighbors(y, x, h, w):
            if (ny, nx_) not in S:
                continue
            if (y, x, ny, nx_) in visited:
                continue

            path = [(y, x)]
            py, px = y, x
            cy, cx = ny, nx_

            # Follow skeleton until hitting another keypoint or dead end
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

                nbrs = [(ny, nx_) for ny, nx_ in _neighbors(cy, cx, h, w) if (ny, nx_) in S and (ny, nx_) != (py, px)]
                if not nbrs:
                    break
                if len(nbrs) > 1:
                    break
                py, px = cy, cx
                cy, cx = nbrs[0]

    return G


# ================================================================
# 4. Metrics & plotting
# ================================================================
def compute_metrics(G: nx.Graph, px_per_meter: float) -> Dict[str,Any]:
    if len(G)==0: return {"num_nodes":0,"num_edges":0,"AQ_v1":0.0}
    return {
        "num_nodes": int(G.number_of_nodes()),
        "num_edges": int(G.number_of_edges()),
        "AQ_v1": float(len(G))/max(px_per_meter,1.0)
    }

def save_skeleton_png(skel: np.ndarray, outpath: str):
    plt.figure(figsize=(8,8))
    plt.imshow(skel, cmap="gray")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(outpath,dpi=200,bbox_inches="tight",pad_inches=0.0)
    plt.close()

def export_graph_json(G: nx.Graph, outpath: str):
    data={"nodes":[{"id":int(n),"x":float(d["x"]),"y":float(d["y"])} for n,d in G.nodes(data=True)],
          "edges":[{"u":int(u),"v":int(v)} for u,v in G.edges()]}
    with open(outpath,"w") as f: json.dump(data,f,indent=2)

def export_metrics_json(metrics: Dict[str,Any], outpath: str):
    with open(outpath,"w") as f: json.dump(metrics,f,indent=2)

def plot_graph_on_floorplan(input_path:str,G:nx.Graph):
    img=load_image_any(input_path)
    plt.figure(figsize=(10,10))
    plt.imshow(cv2.cvtColor(img,cv2.COLOR_BGR2RGB))
    for u,v in G.edges():
        x0,y0=G.nodes[u]["x"],G.nodes[u]["y"]
        x1,y1=G.nodes[v]["x"],G.nodes[v]["y"]
        plt.plot([x0,x1],[y0,y1],"r-",linewidth=1)
    xs=[d["x"] for _,d in G.nodes(data=True)]
    ys=[d["y"] for _,d in G.nodes(data=True)]
    plt.scatter(xs,ys,c="blue",s=10)
    plt.axis("off")
    plt.show()


# ================================================================
# 5. Pipeline runner
# ================================================================
def run_aq_pipeline(input_path:str, px_per_meter=50.0, outdir="out",
                    min_corridor_px=200, prune_len_px=10, return_skeleton=False):
    os.makedirs(outdir,exist_ok=True)
    pcfg=PreprocessConfig(min_corridor_object_px=min_corridor_px)
    gcfg=GraphConfig(skeleton_prune_len_px=prune_len_px)
    img=load_image_any(input_path)
    _, walk=preprocess_floorplan(img,pcfg)
    skel=mask_to_skeleton(walk)
    G=skeleton_to_graph(skel,gcfg)
    metrics=compute_metrics(G,px_per_meter)
    save_skeleton_png(skel,os.path.join(outdir,"skeleton.png"))
    export_graph_json(G,os.path.join(outdir,"routes.json"))
    export_metrics_json(metrics,os.path.join(outdir,"metrics.json"))
    if return_skeleton: return metrics, G, skel
    return metrics, G


# ================================================================
# 6. AccessQuotient computation
# ================================================================
def _angle_between(a, b):
    # a, b are 2D vectors
    da = math.hypot(a[0], a[1])
    db = math.hypot(b[0], b[1])
    if da == 0 or db == 0:
        return 0.0
    cosv = (a[0]*b[0] + a[1]*b[1]) / (da * db)
    cosv = max(-1.0, min(1.0, cosv))
    return math.degrees(math.acos(cosv))

def compute_access_quotient(G, routes, weights,
                            min_branch_len=10,
                            angle_thresh_deg=30.0,
                            min_turn_len_px=3):
    """
    Compute AccessQuotient but:
      - treat significant turns at degree-2 nodes as decision points (N_ij=2)
      - filter out tiny branches (edge 'weight' < min_branch_len)
    Parameters
    ----------
    G : networkx.Graph
        Graph where edges have 'weight' (length)
    routes : list[list]
        List of routes (each route is a list of node IDs)
    weights : list[float]
        Weights for each route (sum==1)
    min_branch_len : float
        Minimum edge length to count a neighboring branch as valid
    angle_thresh_deg : float
        Minimum change-of-direction angle (in degrees) at a degree-2 node
        to consider it a decision/turn.
    min_turn_len_px : float
        Minimum length in pixels of the incoming/outgoing segments for a turn to be valid.
    Returns
    -------
    dict with AQ_S, AQ_F, routes details (P_MF, E_M, decision_points, turns_count)
    """
    assert len(routes) == len(weights), "routes and weights must align"
    assert abs(sum(weights) - 1.0) < 1e-6, "weights must sum to 1"

    AQ_S, AQ_F = 0.0, 0.0
    route_results = []

    for r_idx, (route, w) in enumerate(zip(routes, weights)):
        P_MF = 1.0
        E_M = 0.0
        decision_points = []
        turns_count = 0

        # iterate internal nodes only (exclude start/end)
        for i in range(1, len(route)-1):
            node = route[i]
            deg = G.degree[node]

            # first handle true junctions deg >= 3
            if deg >= 3:
                # count only branches whose edge weight >= min_branch_len
                valid_branches = 0
                branch_neighbors = []
                for nbr in G.neighbors(node):
                    edge_len = G.edges[node, nbr].get("weight", 1.0)
                    if edge_len >= min_branch_len:
                        valid_branches += 1
                        branch_neighbors.append((nbr, edge_len))

                # if <=1 valid branch then it's not really a branching point
                if valid_branches >= 2:
                    N_ij = valid_branches
                    P_ij = 1.0 / N_ij
                    # original formula: (N+1)/(K+1) - 1 , K=1
                    E_ij = (N_ij + 1) / 2.0 - 1.0

                    P_MF *= P_ij
                    E_M += E_ij
                    decision_points.append((node, N_ij, P_ij, E_ij, "junction"))

            # now consider degree == 2 nodes that might be turns
            elif deg == 2:
                prev_node = route[i-1]
                next_node = route[i+1]

                # coordinates (x,y) stored in node attributes
                x_prev, y_prev = (G.nodes[prev_node]["x"], G.nodes[prev_node]["y"])
                x_curr, y_curr = (G.nodes[node]["x"], G.nodes[node]["y"])
                x_next, y_next = (G.nodes[next_node]["x"], G.nodes[next_node]["y"])

                # compute incoming/outgoing segment lengths
                in_len = G.edges[prev_node, node].get("weight", 1.0) if G.has_edge(prev_node, node) else math.hypot(x_curr-x_prev, y_curr-y_prev)
                out_len = G.edges[node, next_node].get("weight", 1.0) if G.has_edge(node, next_node) else math.hypot(x_next-x_curr, y_next-y_curr)

                # if segments are too short, ignore (likely noise)
                if in_len < min_turn_len_px or out_len < min_turn_len_px:
                    continue

                # compute angle between vectors prev->curr and curr->next
                v1 = (x_curr - x_prev, y_curr - y_prev)
                v2 = (x_next - x_curr, y_next - y_curr)
                ang = _angle_between(v1, v2)

                # if angle exceeds threshold, count as binary decision N_ij=2
                if ang >= angle_thresh_deg:
                    N_ij = 2
                    P_ij = 1.0 / N_ij
                    E_ij = (N_ij + 1) / 2.0 - 1.0  # equals 0.5

                    P_MF *= P_ij
                    E_M += E_ij
                    turns_count += 1
                    decision_points.append((node, N_ij, P_ij, E_ij, f"turn(angle={round(ang,1)})"))

            # else deg == 1 or deg == 0 -> nothing to do

        AQ_S += w * P_MF
        AQ_F += w * (1.0 / (1.0 + E_M))

        route_results.append({
            "route_id": r_idx,
            "P_MF": P_MF,
            "E_M": E_M,
            "decision_points": decision_points,
            "turns": turns_count,
            "length": len(route)
        })

    return {
        "AQ_S": AQ_S,
        "AQ_F": AQ_F,
        "routes": route_results
    }

# ================================================================
# 7. Faster route extraction (no all-pairs)
# ================================================================
def extract_routes(G: nx.Graph, max_routes=5, overlap_thresh=0.7):
    """
    Extract diverse routes using endpoint sampling + Dijkstra 
    (much faster than all-pairs).
    """
    if G.number_of_nodes() == 0:
        return [], []

    # Collect endpoints (degree==1)
    endpoints = [n for n, d in G.degree() if d == 1]
    if len(endpoints) < 2:
        return [], []

    routes = []
    rng = np.random.default_rng(42)  # reproducible randomness
    sampled = rng.choice(endpoints, size=min(len(endpoints), max_routes*2), replace=False)

    for u in sampled:
        # Find farthest node from u
        lengths, paths = nx.single_source_dijkstra(G, u, weight="weight")
        if not lengths:
            continue
        v = max(lengths, key=lengths.get)
        path = paths[v]

        # Check overlap with existing routes
        edgeset = set(zip(path[:-1], path[1:]))
        overlap = max(
            len(edgeset & set(zip(r[:-1], r[1:]))) / max(len(edgeset), 1)
            for r in routes
        ) if routes else 0.0

        if overlap < overlap_thresh:
            routes.append(path)
        if len(routes) >= max_routes:
            break

    weights = [1.0 / len(routes)] * len(routes) if routes else []
    return routes, weights


# ================================================================
# 8. Plot + Table Output (with AQ summary)
# ================================================================
def plot_routes_with_table(input_path: str, G: nx.Graph, routes: list, results: dict, skeleton=None):
    """
    Plot routes on floorplan/skeleton and show table of P_MF, E_M, Length,
    plus a summary row with AQ_S and AQ_F.
    """
    import matplotlib.cm as cm

    if skeleton is None:
        img = load_image_any(input_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    else:
        img = cv2.cvtColor((skeleton * 255).astype("uint8"), cv2.COLOR_GRAY2RGB)

    # --- Plot ---
    plt.figure(figsize=(10, 10))
    plt.imshow(img)

    colors = cm.get_cmap("tab10", len(routes))
    for idx, route in enumerate(routes):
        xs = [G.nodes[n]["x"] for n in route]
        ys = [G.nodes[n]["y"] for n in route]
        plt.plot(xs, ys, color=colors(idx), linewidth=2, label=f"Route {idx+1}")
        plt.scatter(xs[0], ys[0], c="green", s=60, marker="o")  # start
        plt.scatter(xs[-1], ys[-1], c="red", s=60, marker="x")  # end

    plt.legend()
    plt.title("Extracted Routes on Floorplan")
    plt.axis("off")
    plt.show()

    # --- Table of metrics ---
    rows = []
    for r in results["routes"]:
        rows.append({
            "Route": r["route_id"] + 1,
            "P_MF": round(r["P_MF"], 4),
            "E_M": round(r["E_M"], 2),
            "Length": len(routes[r["route_id"]])
        })

    # Add summary row
    rows.append({
        "Route": "SUMMARY",
        "P_MF": f"AQ_S={round(results['AQ_S'],4)}",
        "E_M": f"AQ_F={round(results['AQ_F'],4)}",
        "Length": "-"
    })

    df = pd.DataFrame(rows)
    display(df)



def plot_routes_on_floorplan(input_path: str, G: nx.Graph, routes: list, skeleton=None):
    """
    Plot extracted routes on floorplan or skeleton.
    
    Parameters
    ----------
    input_path : str
        Path to floorplan image (PNG/JPG/PDF).
    G : nx.Graph
        Graph of skeletonized floorplan.
    routes : list of list
        Each route is a list of node IDs.
    skeleton : np.ndarray or None
        If provided, use skeleton as background instead of original image.
    """
    import matplotlib.cm as cm

    if skeleton is None:
        img = load_image_any(input_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    else:
        img = cv2.cvtColor((skeleton * 255).astype("uint8"), cv2.COLOR_GRAY2RGB)

    plt.figure(figsize=(10, 10))
    plt.imshow(img)

    # Different color per route
    colors = cm.get_cmap("tab10", len(routes))

    for idx, route in enumerate(routes):
        xs = [G.nodes[n]["x"] for n in route]
        ys = [G.nodes[n]["y"] for n in route]
        plt.plot(xs, ys, color=colors(idx), linewidth=2, label=f"Route {idx+1}")

        # Mark start & end
        plt.scatter(xs[0], ys[0], c="green", s=60, marker="o")   # start
        plt.scatter(xs[-1], ys[-1], c="red", s=60, marker="x")  # end

    plt.legend()
    plt.title("Extracted Routes on Floorplan")
    plt.axis("off")
    plt.show()

