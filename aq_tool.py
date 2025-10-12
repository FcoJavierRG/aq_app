import cv2
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from skimage.morphology import skeletonize
from skimage.filters import threshold_otsu

def run_aq_pipeline(img_path, px_per_meter=50.0, return_skeleton=False):
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Image not readable.")

    _, binary = cv2.threshold(img, threshold_otsu(img), 255, cv2.THRESH_BINARY_INV)
    skel = skeletonize(binary // 255).astype(np.uint8)
    ys, xs = np.nonzero(skel)

    G = nx.Graph()
    for x, y in zip(xs, ys):
        G.add_node((x, y), x=x, y=y)
    for x, y in zip(xs, ys):
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            if (x+dx, y+dy) in G:
                G.add_edge((x, y), (x+dx, y+dy), weight=1)

    metrics = {"num_nodes": len(G.nodes), "num_edges": len(G.edges)}
    return (metrics, G, skel) if return_skeleton else (metrics, G)

def extract_routes(G, max_routes=5):
    nodes = list(G.nodes)
    routes = []
    weights = []
    if len(nodes) < 2:
        return routes, weights
    for i in range(min(max_routes, len(nodes)//2)):
        n1, n2 = nodes[i], nodes[-i-1]
        try:
            path = nx.shortest_path(G, n1, n2)
            routes.append(path)
            weights.append(1.0)
        except nx.NetworkXNoPath:
            continue
    return routes, weights

def compute_access_quotient(G, routes, weights, min_branch_len=10, angle_thresh_deg=30, min_turn_len_px=3):
    results = {"routes": [], "AQ_S": 0, "AQ_F": 0}
    if not routes:
        return results

    aq_sum = 0
    for ridx, route in enumerate(routes):
        turns = 0
        turn_points = []
        for i in range(1, len(route)-1):
            x1, y1 = route[i-1]
            x2, y2 = route[i]
            x3, y3 = route[i+1]
            v1 = np.array([x2 - x1, y2 - y1])
            v2 = np.array([x3 - x2, y3 - y2])
            cosang = np.dot(v1, v2) / (np.linalg.norm(v1)*np.linalg.norm(v2) + 1e-6)
            angle = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
            if angle > angle_thresh_deg:
                turns += 1
                turn_points.append((x2, y2))

        length = len(route)
        P_MF = 1 / (1 + turns)
        E_M = length / (len(G.nodes) + 1e-6)
        aq_sum += P_MF * E_M

        results["routes"].append({
            "route_id": ridx,
            "turns": turns,
            "turn_points": turn_points,
            "P_MF": P_MF,
            "E_M": E_M,
            "length": length,
            "decision_points": [(f"dp_{i}", None, None, None, f"turn(angle={round(angle_thresh_deg)})") for i in range(turns)]
        })

    results["AQ_S"] = aq_sum / len(routes)
    results["AQ_F"] = 1 / (1 + np.mean([r["turns"] for r in results["routes"]]))
    return results

def plot_routes_side_by_side(img_path, skel, G, routes):
    img_bgr = cv2.imread(img_path)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    axes[0].imshow(img_rgb)
    axes[0].set_title("Original Floor Plan")
    axes[0].axis("off")

    axes[1].imshow(skel, cmap="gray")
    colors = ["cyan", "lime", "orange", "magenta", "red", "yellow"]
    for idx, route in enumerate(routes):
        color = colors[idx % len(colors)]
        xs = [G.nodes[n]["x"] for n in route]
        ys = [G.nodes[n]["y"] for n in route]
        axes[1].plot(xs, ys, color=color, linewidth=2, label=f"Route {idx+1}")
        axes[1].scatter(xs[0], ys[0], color="green", s=40)
        axes[1].scatter(xs[-1], ys[-1], color="red", s=40)
    axes[1].legend(fontsize=8)
    axes[1].set_title("Skeleton + Detected Routes")
    axes[1].axis("off")
    plt.tight_layout()
    return fig
