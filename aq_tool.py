"""
AQ Tool (AccessQuotient)
- Loads and processes architectural floorplans (PDF or image)
- Extracts walkable network (skeleton)
- Builds graph and routes
- Computes AccessQuotient metrics with geometry-based turn detection
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
# 1. CONFIGURATION
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
# 2. IMAGE LOADING & PREPROCESSING
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
# 3. SKELETONIZATION & GRAPH CREATION
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
            if (ny, nx_) not in S:
                continue
            if (y, x, ny, nx_) in visited:
                continue

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
                if not nbrs or len(nbrs) > 1:
                    break
                py, px = cy, cx
                cy, cx = nbrs[0]

    return G


# ================================================================
# 4. ROUTE EXTRACTION + AQ CALCULATION
# ================================================================
def _angle_between_vecs(v1, v2):
    a, b = np.array(v1, dtype=float), np.array(v2, dtype=float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    cosv = np.dot(a, b) / (na * nb)
    cosv = float(np.clip(cosv, -1.0, 1.0))
    return math.degrees(math.acos(cosv))


def _build_route_polyline(route, G):
    poly = []
    for i in range(len(route)-1):
        u, v = route[i], route[i+1]
        data = G.get_edge_data(u, v)
        if data and "path" in data:
            seg = [(float(xc), float(yc)) for (yc, xc) in data["path"]]
        else:
            seg = [(G.nodes[u]["x"], G.nodes[u]["y"]), (G.nodes[v]["x"], G.nodes[v]["y"])]
        if not poly:
            poly.extend(seg)
        else:
            if np.allclose(poly[-1], seg[0]):
                poly.extend(seg[1:])
            else:
                poly.extend(seg)
    return poly


def compute_access_quotient(G, routes, weights, angle_thresh_deg=25.0, min_turn_len_px=2.0):
    AQ_S, AQ_F = 0.0, 0.0
    results = []

    for r_idx, (route, w) in enumerate(zip(routes, weights)):
        P_MF, E_M = 1.0, 0.0
        turns = 0

        poly = _build_route_polyline(route, G)
        if len(poly) >= 3:
            for i in range(1, len(poly)-1):
                v1 = (poly[i][0]-poly[i-1][0], poly[i][1]-poly[i-1][1])
                v2 = (poly[i+1][0]-poly[i][0], poly[i+1][1]-poly[i][1])
                ang = _angle_between_vecs(v1, v2)
                if ang >= angle_thresh_deg:
                    turns += 1
                    N_ij = 2
                    P_ij = 0.5
                    E_ij = 0.5
                    P_MF *= P_ij
                    E_M += E_ij

        AQ_S += w * P_MF
        AQ_F += w * (1.0 / (1.0 + E_M))
        results.append({"route_id": r_idx, "turns": turns, "P_MF": P_MF, "E_M": E_M})

    return {"AQ_S": AQ_S, "AQ_F": AQ_F, "routes": results}


def extract_routes(G, max_routes=5, overlap_thresh=0.7):
    if G.number_of_nodes() == 0:
        return [], []
    endpoints = [n for n, d in G.degree() if d == 1]
    if len(endpoints) < 2:
        return [], []

    routes = []
    rng = np.random.default_rng(42)
    sampled = rng.choice(endpoints, size=min(len(endpoints), max_routes*2), replace=False)
    for u in sampled:
        lengths, paths = nx.single_source_dijkstra(G, u, weight="weight")
        if not lengths:
            continue
        v = max(lengths, key=lengths.get)
        path = paths[v]
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
# 5. VISUALIZATION — SIDE BY SIDE
# ================================================================
def plot_routes_side_by_side(input_path: str, skeleton: np.ndarray, G: nx.Graph, routes: list):
    """Show floorplan and skeleton side by side with colored routes."""
    import matplotlib.cm as cm
    img = load_image_any(input_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    skel_rgb = cv2.cvtColor((skeleton * 255).astype("uint8"), cv2.COLOR_GRAY2RGB)
    colors = cm.get_cmap("tab10", len(routes))

    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    titles = ["Floorplan with Routes", "Skeleton with Routes"]
    bgs = [img_rgb, skel_rgb]

    for ax, bg, title in zip(axes, bgs, titles):
        ax.imshow(bg)
        for idx, route in enumerate(routes):
            xs = [G.nodes[n]["x"] for n in route]
            ys = [G.nodes[n]["y"] for n in route]
            ax.plot(xs, ys, color=colors(idx), linewidth=2, label=f"Route {idx+1}")
            ax.scatter(xs[0], ys[0], c="green", s=40, marker="o")
            ax.scatter(xs[-1], ys[-1], c="red", s=40, marker="x")
        ax.set_title(title)
        ax.axis("off")

    plt.legend()
    plt.tight_layout()
    plt.show()
