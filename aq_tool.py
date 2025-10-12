import cv2
import numpy as np
import networkx as nx
import math

# ----------------------------
# Utility functions
# ----------------------------

def preprocess_image(img_path, px_per_meter=50):
    """
    Load image, convert to grayscale, binarize, and extract skeleton.
    Returns the skeleton image and binary mask.
    """
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Failed to read image: {img_path}")

    # Threshold and invert (so paths = 1)
    _, binary = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)
    binary = binary.astype(np.uint8)

    # Morphological thinning (skeletonization)
    skeleton = cv2.ximgproc.thinning(binary)

    return skeleton, binary


def skeleton_to_graph(skeleton):
    """
    Convert a skeletonized image into a graph structure.
    Each pixel in the skeleton is a node; edges connect neighboring pixels.
    """
    G = nx.Graph()
    h, w = skeleton.shape
    skel_points = np.argwhere(skeleton > 0)

    for y, x in skel_points:
        G.add_node((x, y), x=x, y=y)
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1)]:
            nx_, ny_ = x+dx, y+dy
            if 0 <= nx_ < w and 0 <= ny_ < h and skeleton[ny_, nx_] > 0:
                G.add_edge((x,y), (nx_,ny_), weight=math.hypot(dx, dy))
    return G


def extract_routes(G, max_routes=5):
    """
    Extract simple routes by finding longest paths from endpoints.
    """
    endpoints = [n for n in G.nodes if G.degree[n] == 1]
    routes = []
    weights = []
    visited = set()

    for start in endpoints:
        for end in endpoints:
            if start == end:
                continue
            try:
                path = nx.shortest_path(G, start, end, weight="weight")
                w = sum(G[u][v]["weight"] for u, v in zip(path[:-1], path[1:]))
                if tuple(path) not in visited:
                    routes.append(path)
                    weights.append(w)
                    visited.add(tuple(path))
            except Exception:
                pass

    # Sort by route length
    sorted_idx = np.argsort(weights)[::-1]
    routes = [routes[i] for i in sorted_idx[:max_routes]]
    weights = [weights[i] for i in sorted_idx[:max_routes]]
    return routes, weights


# ----------------------------
# Turn detection (new logic)
# ----------------------------

def detect_turns(route, G, angle_thresh_deg=30, min_turn_len_px=3):
    """
    Detect turns based on local direction change along the route.
    Returns number of turns detected.
    """
    if len(route) < 3:
        return 0

    coords = np.array([[G.nodes[n]['x'], G.nodes[n]['y']] for n in route])
    turns = 0

    for i in range(1, len(coords)-1):
        v1 = coords[i] - coords[i-1]
        v2 = coords[i+1] - coords[i]
        len1 = np.linalg.norm(v1)
        len2 = np.linalg.norm(v2)
        if len1 < min_turn_len_px or len2 < min_turn_len_px:
            continue

        cos_angle = np.dot(v1, v2) / (len1 * len2)
        cos_angle = np.clip(cos_angle, -1, 1)
        angle = math.degrees(math.acos(cos_angle))

        if angle > angle_thresh_deg:
            turns += 1

    return turns


# ----------------------------
# Access Quotient computation
# ----------------------------

def compute_access_quotient(G, routes, weights, min_branch_len=10, angle_thresh_deg=30, min_turn_len_px=3):
    """
    Compute AQ metrics for all routes.
    """
    results = {
        "AQ_S": 0,
        "AQ_F": 0,
        "routes": []
    }

    total_weight = sum(weights) if weights else 1e-9
    aq_sum = 0
    for ridx, route in enumerate(routes):
        turns = detect_turns(route, G, angle_thresh_deg, min_turn_len_px)
        length = weights[ridx]
        if length < min_branch_len:
            continue
        P_MF = length / total_weight
        E_M = 1 / (1 + turns)  # efficiency metric inversely proportional to turns
        aq_sum += P_MF * E_M

        results["routes"].append({
            "route_id": ridx,
            "P_MF": P_MF,
            "E_M": E_M,
            "turns": turns,
            "length": length
        })

    # Aggregate AQ metrics
    results["AQ_S"] = aq_sum
    results["AQ_F"] = aq_sum / len(routes) if len(routes) > 0 else 0

    return results


# ----------------------------
# Main pipeline
# ----------------------------

def run_aq_pipeline(img_path, px_per_meter=50, return_skeleton=False):
    """
    Full AQ pipeline: preprocessing → skeleton → graph → compute metrics.
    """
    skel, binary = preprocess_image(img_path, px_per_meter)
    G = skeleton_to_graph(skel)
    metrics = {
        "num_nodes": len(G.nodes),
        "num_edges": len(G.edges),
    }

    if return_skeleton:
        return metrics, G, skel
    else:
        return metrics, G, None
