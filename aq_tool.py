"""
AQ Tool (Multi-floor + Route Drawing + Geometry-based Turn Detection)
"""

import cv2
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from skimage.morphology import skeletonize
from skimage.filters import threshold_otsu
from skimage import io, color, measure
from scipy.spatial import KDTree
import math


# =============================
# Utility: Basic image loading
# =============================
def load_image_as_gray(path):
    img = io.imread(path)
    if img.ndim == 3:
        img = color.rgb2gray(img)
    img = (img * 255).astype(np.uint8)
    return img


# =============================
# Skeletonization + Graph build
# =============================
def run_aq_pipeline(
    fpath,
    px_per_meter=50.0,
    return_skeleton=False
):
    img = load_image_as_gray(fpath)
    thresh = threshold_otsu(img)
    binary = img < thresh  # invert if needed
    skel = skeletonize(binary)

    # Label connected components (walkable areas)
    labels = measure.label(skel)
    coords = np.column_stack(np.nonzero(skel))

    # Build graph
    G = nx.Graph()
    for (y, x) in coords:
        G.add_node((x, y), x=float(x), y=float(y))

    for (y, x) in coords:
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx_, ny_ = x + dx, y + dy
                if (nx_, ny_) in G.nodes:
                    G.add_edge((x, y), (nx_, ny_), weight=np.hypot(dx, dy))

    metrics = {
        "num_nodes": G.number_of_nodes(),
        "num_edges": G.number_of_edges(),
        "px_per_meter": px_per_meter,
    }

    return (metrics, G, skel) if return_skeleton else (metrics, G)


# =============================
# Route Extraction
# =============================
def extract_routes(G, max_routes=5):
    if G.number_of_nodes() == 0:
        return [], []

    nodes = list(G.nodes)
    if len(nodes) < 2:
        return [], []

    # Find longest shortest path (diameter approximation)
    routes = []
    weights = []
    paths = []

    # Approx: use top-degree nodes as candidates
    deg_sorted = sorted(G.degree, key=lambda x: x[1], reverse=True)
    end_nodes = [deg_sorted[i][0] for i in range(min(len(deg_sorted), 10))]

    for i, src in enumerate(end_nodes):
        for dst in end_nodes[i+1:]:
            try:
                path = nx.shortest_path(G, src, dst, weight="weight")
                length = nx.path_weight(G, path, "weight")
                routes.append(path)
                weights.append(length)
                paths.append((src, dst, length))
            except nx.NetworkXNoPath:
                continue

    if len(routes) == 0:
        return [], []

    # Sort by length descending
    idx = np.argsort(weights)[::-1][:max_routes]
    routes = [routes[i] for i in idx]
    weights = [weights[i] for i in idx]
    return routes, weights


# =============================
# Geometry-based Turn Detection
# =============================
def angle_between(p1, p2, p3):
    """Return angle (degrees) formed at p2 by p1–p2–p3."""
    v1 = np.array([p1[0]-p2[0], p1[1]-p2[1]])
    v2 = np.array([p3[0]-p2[0], p3[1]-p2[1]])
    if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
        return 0
    cos_ang = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    cos_ang = np.clip(cos_ang, -1, 1)
    ang = np.degrees(np.arccos(cos_ang))
    return ang


def compute_access_quotient(
    G,
    routes,
    weights,
    min_branch_len=10,
    angle_thresh_deg=30,
    min_turn_len_px=3
):
    if len(routes) == 0:
        return {"AQ_S": 0, "AQ_F": 0, "routes": []}

    routes_data = []
    total_E_M = 0
    total_P_MF = 0

    for ridx, route in enumerate(routes):
        route_points = [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in route]
        turns = 0
        decision_points = []
        turn_points = []

        for i in range(1, len(route_points)-1):
            ang = angle_between(route_points[i-1], route_points[i], route_points[i+1])
            if ang > angle_thresh_deg:
                turns += 1
                decision_points.append((f"turn_{i}", None, None, None, f"turn(angle={int(ang)})"))
                turn_points.append(route_points[i])

        length_px = sum(
            np.hypot(route_points[i+1][0]-route_points[i][0],
                     route_points[i+1][1]-route_points[i][1])
            for i in range(len(route_points)-1)
        )

        # Placeholder probabilities
        P_MF = 1 / (1 + turns)
        E_M = length_px / (1 + turns)

        total_P_MF += P_MF
        total_E_M += E_M

        routes_data.append({
            "route_id": ridx,
            "turns": turns,
            "length": length_px,
            "P_MF": P_MF,
            "E_M": E_M,
            "decision_points": decision_points,
            "turn_points": turn_points,
        })

    AQ_S = np.mean([r["P_MF"] for r in routes_data])
    AQ_F = np.mean([r["E_M"] for r in routes_data])

    return {"AQ_S": AQ_S, "AQ_F": AQ_F, "routes": routes_data}


# =============================
# Multi-floor Linking
# =============================
def link_floors(graphs):
    """Combine floor graphs into one, connecting nearest entry/exit nodes."""
    G_total = nx.Graph()
    offset_y = 0
    connectors = []

    for i, G in enumerate(graphs):
        mapping = {}
        for n in G.nodes:
            x = G.nodes[n]["x"]
            y = G.nodes[n]["y"] + offset_y
            mapping[n] = (x, y, i)  # add floor index
        G_floor = nx.relabel_nodes(G, mapping)
        G_total = nx.compose(G_total, G_floor)

        # record midpoints to connect between floors
        nodes_arr = np.array([(G_floor.nodes[n]["x"], G_floor.nodes[n]["y"]) for n in G_floor.nodes])
        mid_idx = np.random.choice(range(len(nodes_arr)), size=min(5, len(nodes_arr)), replace=False)
        for mi in mid_idx:
            connectors.append((nodes_arr[mi][0], nodes_arr[mi][1], i))
        offset_y += 2000  # spacing between floor layouts

    # connect vertically nearest nodes
    for i in range(len(connectors)-1):
        if connectors[i][2] != connectors[i+1][2]:
            n1 = (connectors[i][0], connectors[i][1], connectors[i][2])
            n2 = (connectors[i+1][0], connectors[i+1][1], connectors[i+1][2])
            if n1 in G_total.nodes and n2 in G_total.nodes:
                G_total.add_edge(n1, n2, weight=100)

    return G_total


# =============================
# Visualization
# =============================
def draw_routes_on_image(G, routes, skel, img_rgb=None):
    fig, ax = plt.subplots(figsize=(6, 6))
    if img_rgb is not None:
        ax.imshow(img_rgb, alpha=0.6)
    else:
        ax.imshow(skel, cmap="gray", alpha=0.8)

    colors = ["cyan", "lime", "orange", "magenta", "red", "yellow", "blue", "purple", "teal", "brown"]
    for idx, route in enumerate(routes):
        color = colors[idx % len(colors)]
        xs = [G.nodes[n]["x"] for n in route]
        ys = [G.nodes[n]["y"] for n in route]
        ax.plot(xs, ys, color=color, linewidth=2, label=f"Route {idx+1}")
        ax.scatter(xs[0], ys[0], color="green", marker="o", s=40)
        ax.scatter(xs[-1], ys[-1], color="red", marker="x", s=40)

    ax.axis("off")
    ax.set_title("Detected Routes Overlay")
    ax.legend(fontsize=7)
    plt.tight_layout()
    return fig
