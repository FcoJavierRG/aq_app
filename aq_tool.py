"""
AQ Tool (Jupyter version) with AccessQuotient support

Inputs: PDF (single page) or raster image (PNG/JPG)
Outputs:
  - metrics dict
  - networkx graph of routes
  - skeleton mask (numpy array)
"""

import os, math, json, cv2, fitz
import numpy as np"""
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
        G.add_node(idx, y=float(y), x=float(x))
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
# 4. AccessQuotient computation
# ================================================================
def _get_perpendicular_distance(pt, line_start, line_end):
    """Calculate the perpendicular distance of a point from a line segment."""
    x0, y0 = pt
    x1, y1 = line_start
    x2, y2 = line_end
    
    dx, dy = x2 - x1, y2 - y1
    mag_sq = dx*dx + dy*dy
    if mag_sq == 0:
        return math.hypot(x0 - x1, y0 - y1)
    
    u = ((x0 - x1) * dx + (y0 - y1) * dy) / mag_sq
    
    if u < 0:
        ix, iy = x1, y1
    elif u > 1:
        ix, iy = x2, y2
    else:
        ix, iy = x1 + u * dx, y1 + u * dy
        
    return math.hypot(x0 - ix, y0 - iy)

def _rdp(points, epsilon):
    """Simplifies a path using the Ramer-Douglas-Peucker algorithm."""
    if not points or len(points) < 3:
        return points
    
    dmax = 0.0
    index = 0
    end = len(points) - 1

    for i in range(1, end):
        d = _get_perpendicular_distance(points[i], points[0], points[end])
        if d > dmax:
            index = i
            dmax = d

    if dmax > epsilon:
        rec_results1 = _rdp(points[:index+1], epsilon)
        rec_results2 = _rdp(points[index:], epsilon)
        return rec_results1[:-1] + rec_results2
    else:
        return [points[0], points[end]]

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
                            min_turn_len_px=5):
    """
    Compute AccessQuotient metrics (Strict and Flexible).
    - Uses RDP algorithm to simplify paths and robustly detect turns.
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
        decision_points = []
        turns_count = 0
        
        route_len = sum(G.edges[u,v].get("weight",1.0) for u,v in zip(route[:-1], route[1:]))

        # 1. Process JUNCTIONS (nodes with degree >= 3)
        for i in range(1, len(route) - 1):
            node = route[i]
            if G.degree[node] >= 3:
                valid_branches = sum(
                    1 for nbr in G.neighbors(node) 
                    if G.edges[node, nbr].get("weight", 1.0) >= min_branch_len
                )
                if valid_branches >= 2:
                    N_ij = valid_branches
                    P_ij = 1.0 / N_ij
                    E_ij = (N_ij + 1) / 2.0 - 1.0
                    P_MF *= P_ij
                    E_M += E_ij
                    decision_points.append({"node": node, "type": "junction", "N_ij": N_ij})

        # 2. Process TURNS by simplifying paths with RDP algorithm
        for i in range(len(route) - 1):
            u, v = route[i], route[i+1]
            pixel_path = G.edges[u, v].get("path", [])
            
            if len(pixel_path) < 3:
                continue
            
            # RDP works on (x,y) points
            xy_path = [(p[1], p[0]) for p in pixel_path]
            
            # The 'min_turn_len_px' is used as the epsilon for simplification
            simplified_path = _rdp(xy_path, epsilon=min_turn_len_px)

            if len(simplified_path) > 2:
                for j in range(1, len(simplified_path) - 1):
                    # Get three consecutive points from the SIMPLIFIED path
                    x_prev, y_prev = simplified_path[j-1]
                    x_curr, y_curr = simplified_path[j]
                    x_next, y_next = simplified_path[j+1]

                    vec1 = (x_curr - x_prev, y_curr - y_prev)
                    vec2 = (x_next - x_curr, y_next - y_curr)
                    angle = _angle_between(vec1, vec2)

                    if angle >= angle_thresh_deg:
                        P_MF *= 0.5  # Each turn is a binary decision
                        E_M += 0.5   # Expected mistakes for binary choice
                        turns_count += 1
                        decision_points.append({"node_coords": (x_curr, y_curr), "type": f"turn({angle:.1f} deg)", "N_ij": 2})
        
        AQ_S += w * P_MF
        AQ_F += w * (1.0 / (1.0 + E_M))

        route_results.append({
            "route_id": r_idx, "P_MF": P_MF, "E_M": E_M,
            "decision_points": decision_points, "turns": turns_count, "length": route_len
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
    sampled = rng.choice(endpoints, size=min(len(endpoints), max_routes * 2), replace=False)

    for u in sampled:
        lengths, paths = nx.single_source_dijkstra(G, u, weight="weight")
        if not lengths: continue
        v = max(lengths, key=lengths.get)
        path = paths[v]

        edgeset = set(map(frozenset, zip(path[:-1], path[1:])))
        overlap = max([len(edgeset & r_set) / len(edgeset) for _, r_set in routes] if routes else [0.0])
        
        if overlap < overlap_thresh:
            routes.append((path, edgeset))
        if len(routes) >= max_routes: break

    final_routes = [r for r, _ in routes]
    weights = [1.0 / len(final_routes)] * len(final_routes) if final_routes else []
    return final_routes, weights


# ================================================================
# 6. Pipeline runner
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
        G.add_node(idx, y=float(y), x=float(x))
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
# 4. AccessQuotient computation
# ================================================================
def _get_perpendicular_distance(pt, line_start, line_end):
    """Calculate the perpendicular distance of a point from a line segment."""
    x0, y0 = pt
    x1, y1 = line_start
    x2, y2 = line_end
    
    dx, dy = x2 - x1, y2 - y1
    mag_sq = dx*dx + dy*dy
    if mag_sq == 0:
        return math.hypot(x0 - x1, y0 - y1)
    
    u = ((x0 - x1) * dx + (y0 - y1) * dy) / mag_sq
    
    if u < 0:
        ix, iy = x1, y1
    elif u > 1:
        ix, iy = x2, y2
    else:
        ix, iy = x1 + u * dx, y1 + u * dy
        
    return math.hypot(x0 - ix, y0 - iy)

def _rdp(points, epsilon):
    """Simplifies a path using the Ramer-Douglas-Peucker algorithm."""
    if not points or len(points) < 3:
        return points
    
    dmax = 0.0
    index = 0
    end = len(points) - 1

    for i in range(1, end):
        d = _get_perpendicular_distance(points[i], points[0], points[end])
        if d > dmax:
            index = i
            dmax = d

    if dmax > epsilon:
        rec_results1 = _rdp(points[:index+1], epsilon)
        rec_results2 = _rdp(points[index:], epsilon)
        return rec_results1[:-1] + rec_results2
    else:
        return [points[0], points[end]]

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
                            min_turn_len_px=5):
    """
    Compute AccessQuotient metrics (Strict and Flexible).
    - Uses RDP algorithm to simplify paths and robustly detect turns.
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
        decision_points = []
        turns_count = 0
        
        route_len = sum(G.edges[u,v].get("weight",1.0) for u,v in zip(route[:-1], route[1:]))

        # 1. Process JUNCTIONS (nodes with degree >= 3)
        for i in range(1, len(route) - 1):
            node = route[i]
            if G.degree[node] >= 3:
                valid_branches = sum(
                    1 for nbr in G.neighbors(node) 
                    if G.edges[node, nbr].get("weight", 1.0) >= min_branch_len
                )
                if valid_branches >= 2:
                    N_ij = valid_branches
                    P_ij = 1.0 / N_ij
                    E_ij = (N_ij + 1) / 2.0 - 1.0
                    P_MF *= P_ij
                    E_M += E_ij
                    decision_points.append({"node": node, "type": "junction", "N_ij": N_ij})

        # 2. Process TURNS by simplifying paths with RDP algorithm
        for i in range(len(route) - 1):
            u, v = route[i], route[i+1]
            pixel_path = G.edges[u, v].get("path", [])
            
            if len(pixel_path) < 3:
                continue
            
            # RDP works on (x,y) points
            xy_path = [(p[1], p[0]) for p in pixel_path]
            
            # The 'min_turn_len_px' is used as the epsilon for simplification
            simplified_path = _rdp(xy_path, epsilon=min_turn_len_px)

            if len(simplified_path) > 2:
                for j in range(1, len(simplified_path) - 1):
                    # Get three consecutive points from the SIMPLIFIED path
                    x_prev, y_prev = simplified_path[j-1]
                    x_curr, y_curr = simplified_path[j]
                    x_next, y_next = simplified_path[j+1]

                    vec1 = (x_curr - x_prev, y_curr - y_prev)
                    vec2 = (x_next - x_curr, y_next - y_curr)
                    angle = _angle_between(vec1, vec2)

                    if angle >= angle_thresh_deg:
                        P_MF *= 0.5  # Each turn is a binary decision
                        E_M += 0.5   # Expected mistakes for binary choice
                        turns_count += 1
                        decision_points.append({"node_coords": (x_curr, y_curr), "type": f"turn({angle:.1f} deg)", "N_ij": 2})
        
        AQ_S += w * P_MF
        AQ_F += w * (1.0 / (1.0 + E_M))

        route_results.append({
            "route_id": r_idx, "P_MF": P_MF, "E_M": E_M,
            "decision_points": decision_points, "turns": turns_count, "length": route_len
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
    sampled = rng.choice(endpoints, size=min(len(endpoints), max_routes * 2), replace=False)

    for u in sampled:
        lengths, paths = nx.single_source_dijkstra(G, u, weight="weight")
        if not lengths: continue
        v = max(lengths, key=lengths.get)
        path = paths[v]

        edgeset = set(map(frozenset, zip(path[:-1], path[1:])))
        overlap = max([len(edgeset & r_set) / len(edgeset) for _, r_set in routes] if routes else [0.0])
        
        if overlap < overlap_thresh:
            routes.append((path, edgeset))
        if len(routes) >= max_routes: break

    final_routes = [r for r, _ in routes]
    weights = [1.0 / len(final_routes)] * len(final_routes) if final_routes else []
    return final_routes, weights


# ================================================================
# 6. Pipeline runner
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


