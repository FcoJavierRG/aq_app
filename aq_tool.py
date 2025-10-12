# aq_tool.py
import cv2
import numpy as np
import networkx as nx
from skimage.morphology import skeletonize
from scipy.spatial import distance

# ============================================================
# HELPER: Load and preprocess image
# ============================================================
def load_floorplan(image_path):
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Could not load image: {image_path}")
    img = cv2.GaussianBlur(img, (3, 3), 0)
    _, bw = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bw = 255 - bw  # invert, corridors = white
    return bw


# ============================================================
# HELPER: Skeletonization
# ============================================================
def extract_skeleton(binary_img):
    """Return thinned skeleton as binary numpy array."""
    skel = skeletonize(binary_img > 0)
    skel = (skel * 255).astype(np.uint8)
    return skel


# ============================================================
# GRAPH: Build graph from skeleton
# ============================================================
def skeleton_to_graph(skel):
    """Convert skeleton pixels to graph nodes and edges."""
    G = nx.Graph()
    coords = np.argwhere(skel > 0)
    for idx, (y, x) in enumerate(coords):
        G.add_node(idx, x=int(x), y=int(y))
    # connect 8-neighbors
    for i, (y, x) in enumerate(coords):
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dy == 0 and dx == 0:
                    continue
                ny, nx_ = y + dy, x + dx
                if (ny, nx_) in [tuple(p) for p in coords]:
                    j = np.where((coords == [ny, nx_]).all(axis=1))[0]
                    if len(j) > 0:
                        G.add_edge(i, int(j[0]), weight=1.0)
    return G


# ============================================================
# GRAPH: Simplify graph (remove degree-2 nodes)
# ============================================================
def simplify_graph(G):
    G_simple = G.copy()
    for n in list(G.nodes):
        if G.degree[n] == 2:
            neighbors = list(G.neighbors(n))
            if len(neighbors) == 2:
                u, v = neighbors
                if not G_simple.has_edge(u, v):
                    w = G_simple[u][n]["weight"] + G_simple[n][v]["weight"]
                    G_simple.add_edge(u, v, weight=w)
                G_simple.remove_node(n)
    return G_simple


# ============================================================
# ROUTE EXTRACTION
# ============================================================
def extract_routes(G, max_routes=5):
    """Find routes between distant nodes in the graph."""
    nodes = list(G.nodes)
    if len(nodes) < 2:
        return [], []
    coords = np.array([[G.nodes[n]["x"], G.nodes[n]["y"]] for n in nodes])
    dist_matrix = distance.cdist(coords, coords, metric="euclidean")
    idx_pairs = np.dstack(np.unravel_index(np.argsort(dist_matrix.ravel()), dist_matrix.shape))[0]
    routes, weights = [], []
    for (i, j) in idx_pairs[::-1]:
        if i == j:
            continue
        try:
            path = nx.shortest_path(G, nodes[i], nodes[j], weight="weight")
            routes.append(path)
            weights.append(dist_matrix[i, j])
            if len(routes) >= max_routes:
                break
        except nx.NetworkXNoPath:
            continue
    return routes, weights


# ============================================================
# AQ METRICS
# ============================================================
def compute_access_quotient(G, routes, weights,
                            min_branch_len=10,
                            angle_thresh_deg=30,
                            min_turn_len_px=3):
    """Compute basic AccessQuotient-like metrics."""
    AQ_S = 0.0
    AQ_F = 0.0
    route_results = []

    for ridx, route in enumerate(routes):
        turns = count_turns(G, route, angle_thresh_deg)
        length = sum(G[u][v]["weight"] for u, v in zip(route[:-1], route[1:]))
        E_M = np.exp(-0.05 * turns) if turns > 0 else 1.0
        P_MF = 1.0 / (1.0 + length / 100.0)
        AQ_S += E_M
        AQ_F += P_MF
        route_results.append({
            "route_id": ridx,
            "turns": turns,
            "length": length,
            "E_M": E_M,
            "P_MF": P_MF,
            "decision_points": [(i, route[i]) for i in range(0, len(route), max(1, len(route)//4))]
        })

    if routes:
        AQ_S /= len(routes)
        AQ_F /= len(routes)

    return {"AQ_S": AQ_S, "AQ_F": AQ_F, "routes": route_results}


# ============================================================
# TURN COUNT HELPER
# ============================================================
def count_turns(G, route, angle_thresh_deg=30):
    """Count how many turns occur along a route."""
    if len(route) < 3:
        return 0
    turns = 0
    for i in range(1, len(route) - 1):
        n1, n2, n3 = route[i-1], route[i], route[i+1]
        x1, y1 = G.nodes[n1]["x"], G.nodes[n1]["y"]
        x2, y2 = G.nodes[n2]["x"], G.nodes[n2]["y"]
        x3, y3 = G.nodes[n3]["x"], G.nodes[n3]["y"]
        v1 = np.array([x2 - x1, y2 - y1])
        v2 = np.array([x3 - x2, y3 - y2])
        dot = np.dot(v1, v2)
        if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
            continue
        angle = np.degrees(np.arccos(np.clip(dot / (np.linalg.norm(v1)*np.linalg.norm(v2)), -1.0, 1.0)))
        if angle > angle_thresh_deg:
            turns += 1
    return turns


# ============================================================
# PIPELINE WRAPPER
# ============================================================
def run_aq_pipeline(image_path, px_per_meter=50, return_skeleton=False):
    """Full AQ pipeline: image -> skeleton -> graph -> metrics."""
    img = load_floorplan(image_path)
    skel = extract_skeleton(img)
    G = skeleton_to_graph(skel)
    G = simplify_graph(G)

    routes, weights = extract_routes(G)
    results = compute_access_quotient(G, routes, weights)

    if return_skeleton:
        return results, G, skel
    return results, G
