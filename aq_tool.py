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
