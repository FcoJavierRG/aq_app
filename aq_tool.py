import os
import math
import json
import cv2
import fitz
import numpy as np
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
    """Loads an image from a path, supporting PDF, PNG, and JPG."""
    ext = os.path.splitext(path.lower())[1]
    if ext == ".pdf":
        doc = fitz.open(path)
        page = doc.load_page(0)
        zoom = 300 / 72  # Render at 300 DPI
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if img.ndim == 2:
            return img
        # PyMuPDF outputs RGB, convert to BGR for OpenCV consistency
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    else:
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Cannot read image: {path}")
        return img

def preprocess_floorplan(bgr: np.ndarray, cfg: PreprocessConfig) -> Tuple[np.ndarray, np.ndarray]:
    """Converts a floorplan image to a binary walkable mask."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    if cfg.blur_ksize > 1:
        gray = cv2.medianBlur(gray, cfg.blur_ksize)
    bin_inv = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
        cfg.adaptive_block | 1, cfg.adaptive_C
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (cfg.wall_thickness_close, cfg.wall_thickness_close))
    walls = cv2.morphologyEx(bin_inv, cv2.MORPH_CLOSE, kernel)
    free_space_bool = (walls == 0)
    free_space_bool = remove_small_holes(free_space_bool, area_threshold=cfg.min_room_hole_area_px)
    free_space_bool = remove_small_objects(free_space_bool, min_size=cfg.min_corridor_object_px)
    walkable_mask = free_space_bool.astype(np.uint8)
    return (255 - walls), walkable_mask


# ================================================================
# 3. Skeletonization & Graph conversion
# ================================================================
def mask_to_skeleton(mask: np.ndarray) -> np.ndarray:
    """Computes the skeleton of a binary mask."""
    return skeletonize(mask.astype(bool)).astype(np.uint8)

def _neighbors(y: int, x: int, h: int, w: int) -> List[Tuple[int,int]]:
    """Gets 8-connectivity neighbors for a pixel."""
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
        G.add_node(idx, y=float(y), x=float(x), pos=(y,x))
        point_to_node[(y, x)] = idx

    visited = set()
    for (y, x) in keypoints:
        for ny_start, nx_start in _neighbors(y, x, h, w):
            if (ny_start, nx_start) not in S: continue
            if (y, x, ny_start, nx_start) in visited: continue

            path = [(y, x)]
            py, px = y, x
            cy, cx = ny_start, nx_start

            while True:
                path.append((cy, cx))
                visited.add((py, px, cy, cx))
                visited.add((cy, cx, py, px))

                if (cy, cx) in keypoints:
                    u, v = point_to_node[(y, x)], point_to_node[(cy, cx)]
                    if u != v:
                        G.add_edge(u, v, weight=len(path), path=path)
                    break

                nbrs = [(ny, nx) for ny, nx in _neighbors(cy, cx, h, w) if (ny, nx) in S and (ny, nx) != (py, px)]
                if not nbrs: break
                if len(nbrs) > 1: break # Should not happen on skeleton path
                py, px = cy, cx
                cy, cx = nbrs[0]

    return G

# ================================================================
# 4. AccessQuotient computation - CORRECTED
# ================================================================
def _rdp(points, epsilon):
    """Ramer-Douglas-Peucker algorithm for path simplification."""
    if not points:
        return []
    dmax = 0.0
    index = 0
    for i in range(1, len(points) - 1):
        d = _perpendicular_distance(points[i], points[0], points[-1])
        if d > dmax:
            index = i
            dmax = d
    if dmax > epsilon:
        rec_results1 = _rdp(points[:index + 1], epsilon)
        rec_results2 = _rdp(points[index:], epsilon)
        return rec_results1[:-1] + rec_results2
    else:
        return [points[0], points[-1]]

def _perpendicular_distance(pt, line_start, line_end):
    """Calculates the perpendicular distance from a point to a line segment."""
    x0, y0 = pt
    x1, y1 = line_start
    x2, y2 = line_end
    return abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1) / math.sqrt((y2 - y1)**2 + (x2 - x1)**2)

def _angle_between(p1, p2, p3):
    """Calculate angle at p2 formed by p1-p2-p3."""
    v1 = (p1[0] - p2[0], p1[1] - p2[1])
    v2 = (p3[0] - p2[0], p3[1] - p2[1])
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    det = v1[0] * v2[1] - v1[1] * v2[0]
    angle = math.degrees(math.atan2(det, dot))
    return abs(angle)

def _get_full_pixel_path(G, route):
    """Reconstructs the full, ordered pixel path for a given route of nodes."""
    full_path = []
    if not route or len(route) < 2:
        return []
    
    # Start with the position of the first node
    start_node_pos = G.nodes[route[0]]['pos']
    full_path.append(start_node_pos)

    for i in range(len(route) - 1):
        u, v = route[i], route[i+1]
        edge_data = G.get_edge_data(u, v)
        if 'path' in edge_data:
            segment = edge_data['path']
            # Ensure the segment is in the correct order
            if segment[0] == G.nodes[v]['pos']:
                segment = segment[::-1]
            # Append all points except the first (as it's the last point of the previous segment)
            full_path.extend(segment[1:])
    return full_path

def compute_access_quotient(G, routes, weights,
                            min_branch_len=10,
                            angle_thresh_deg=30.0,
                            min_turn_len_px=5):
    """
    Compute AccessQuotient metrics (Strict and Flexible).
    - CORRECTED: Reliably detects turns in corridors.
    - Filters out tiny branches from junctions.
    """
    if not routes:
        return {"AQ_S": 0, "AQ_F": 0, "routes": []}
    assert len(routes) == len(weights), "routes and weights must align"
    assert abs(sum(weights) - 1.0) < 1e-6, "weights must sum to 1"

    AQ_S, AQ_F = 0.0, 0.0
    route_results = []

    for r_idx, (route, w) in enumerate(zip(routes, weights)):
        P_MF = 1.0
        E_M = 0.0
        junctions_count = 0
        turns_count = 0
        
        # --- 1. Calculate complexity from JUNCTIONS ---
        internal_nodes = route[1:-1]
        for node in internal_nodes:
            if G.degree[node] >= 3:
                valid_branches = sum(
                    1 for nbr in G.neighbors(node) 
                    if G.edges[node, nbr].get("weight", 1.0) >= min_branch_len
                )
                if valid_branches >= 2:
                    N_ij = valid_branches
                    P_MF *= (1.0 / N_ij)
                    E_M += (N_ij + 1) / 2.0 - 1.0
                    junctions_count += 1
        
        # --- 2. Calculate complexity from TURNS (Geometric Analysis) ---
        pixel_path = _get_full_pixel_path(G, route)
        if len(pixel_path) > 2:
            # Simplify the path to find the critical corners
            simplified_path = _rdp(pixel_path, epsilon=min_turn_len_px)
            
            # Calculate angle at each corner of the simplified path
            for i in range(1, len(simplified_path) - 1):
                angle = _angle_between(simplified_path[i-1], simplified_path[i], simplified_path[i+1])
                if angle > angle_thresh_deg:
                    # Treat each significant turn as a binary decision
                    N_ij = 2
                    P_MF *= (1.0 / N_ij)
                    E_M += 0.5  # (2+1)/2 - 1 = 0.5
                    turns_count += 1

        AQ_S += w * P_MF
        AQ_F += w * (1.0 / (1.0 + E_M))
        
        route_len = sum(G.edges[u,v].get("weight",1.0) for u,v in zip(route[:-1], route[1:]))

        route_results.append({
            "route_id": r_idx, "P_MF": P_MF, "E_M": E_M,
            "junctions": junctions_count, "turns": turns_count, "length": route_len
        })

    return {"AQ_S": AQ_S, "AQ_F": AQ_F, "routes": route_results}


# ================================================================
# 5. Route extraction
# ================================================================
def extract_routes(G: nx.Graph, max_routes=5, overlap_thresh=0.7):
    """Extract diverse, long routes using endpoint sampling + Dijkstra."""
    if G.number_of_nodes() < 2: return [], []

    endpoints = [n for n, d in G.degree() if d == 1]
    if len(endpoints) < 2: endpoints = list(G.nodes) # Fallback for circular graphs
    if len(endpoints) < 2: return [], []
    
    routes = []
    # Using a non-fixed seed for random route selection on each run
    rng = np.random.default_rng()
    sampled = rng.choice(endpoints, size=min(len(endpoints), max_routes * 4), replace=False)

    for u in sampled:
        lengths, paths = nx.single_source_dijkstra(G, u, weight="weight")
        if not lengths: continue
        
        # Find a distant node, preferably an endpoint
        distant_nodes = sorted(lengths.keys(), key=lambda k: lengths[k], reverse=True)
        v = distant_nodes[0]
        for node in distant_nodes:
            if node in endpoints and node != u:
                v = node
                break
        
        path = paths[v]

        edgeset = set(map(frozenset, zip(path[:-1], path[1:])))
        if not edgeset: continue
        
        overlap = max([len(edgeset & r_set) / len(edgeset) for _, r_set in routes] if routes else [0.0])
        
        if overlap < overlap_thresh:
            routes.append((path, edgeset))
        if len(routes) >= max_routes: break

    final_routes = [r for r, _ in routes]
    weights = [1.0 / len(final_routes)] * len(final_routes) if final_routes else []
    return final_routes, weights

# ================================================================
# 6. Pipeline runner and helpers
# ================================================================
def run_aq_pipeline(input_path: str, px_per_meter=50.0, return_skeleton=False):
    """Full pipeline from image to graph and metrics."""
    pcfg = PreprocessConfig()
    gcfg = GraphConfig()
    img = load_image_any(input_path)
    _, walk = preprocess_floorplan(img, pcfg)
    skel = mask_to_skeleton(walk)
    G = skeleton_to_graph(skel, gcfg)
    
    if return_skeleton:
        return G, skel
    return G

def find_closest_node(G, x, y):
    """Finds the graph node closest to a given (x, y) coordinate."""
    min_dist = float('inf')
    closest_node = -1
    for n, data in G.nodes(data=True):
        dist = math.hypot(data['x'] - x, data['y'] - y)
        if dist < min_dist:
            min_dist = dist
            closest_node = n
    return closest_node

