# app.py
import streamlit as st
import importlib
import tempfile, os, json
import pandas as pd
import matplotlib.pyplot as plt
import cv2
import random

# reload aq_tool so edits are picked up while developing
import aq_tool
importlib.reload(aq_tool)
from aq_tool import run_aq_pipeline, extract_routes, compute_access_quotient

st.set_page_config(layout="wide", page_title="Floorplan AQ Tool")
st.title("Floorplan Accessibility (AccessQuotient) Tool")

# Sidebar parameters
st.sidebar.header("Parameters")
px_per_meter = st.sidebar.number_input("px_per_meter (approx)", value=50.0, min_value=1.0)
max_routes = st.sidebar.slider("max_routes", min_value=1, max_value=10, value=5)
min_branch_len = st.sidebar.slider("min_branch_len (px)", min_value=1, max_value=200, value=10)
angle_thresh_deg = st.sidebar.slider("angle_thresh_deg", min_value=5, max_value=90, value=30)
min_turn_len_px = st.sidebar.slider("min_turn_len_px", min_value=1, max_value=20, value=3)

uploaded = st.file_uploader("Upload floorplan (png, jpg, pdf)", type=["png", "jpg", "jpeg", "pdf"])

colors = ["cyan", "lime", "orange", "magenta", "brown", "yellow", "red", "blue", "purple", "teal"]

if uploaded:
    suffix = os.path.splitext(uploaded.name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded.getvalue())
    tmp.flush()
    tmp.close()
    fpath = tmp.name

    st.info("Running pipeline — this may take several seconds for large images.")
    with st.spinner("Processing..."):
        try:
            metrics, G, skel = run_aq_pipeline(fpath, px_per_meter=px_per_meter, return_skeleton=True)
        except Exception as e:
            st.error(f"Pipeline failed: {e}")
            raise

        # --- Randomized routes ---
        all_nodes = list(G.nodes())
        routes = []
        weights = []
        for _ in range(max_routes):
            start, end = random.sample(all_nodes, 2)
            # extract_routes should accept optional start/end if possible
            route_list, weight_list = extract_routes(G, max_routes=1)  # fallback if custom start/end not supported
            routes.append(route_list[0])
            weights.append(weight_list[0])

        results = compute_access_quotient(
            G,
            routes,
            weights,
            min_branch_len=min_branch_len,
            angle_thresh_deg=angle_thresh_deg,
            min_turn_len_px=min_turn_len_px
        )

    # --- Summary Metrics ---
    st.subheader("Summary Metrics")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.json({"AQ_S": results["AQ_S"], "AQ_F": results["AQ_F"], "num_routes": len(routes)})
    with col2:
        st.write("Pipeline-level metrics (skeleton/graph):")
        st.json(metrics)

    # --- Build Routes Table ---
    rows = []
    for idx, r in enumerate(results["routes"]):
        decision_points_str = ", ".join(f"{dp[0]}({dp[4]})" for dp in r["decision_points"])
        rows.append({
            "Route": r["route_id"] + 1,
            "P_MF": round(r["P_MF"], 4),
            "E_M": round(r["E_M"], 2),
            "Turns": r.get("turns", 0),
            "Length_px": int(r.get("length", 0)),
            "DecisionPoints": decision_points_str,
            "Color": colors[idx % len(colors)]
        })

    df = pd.DataFrame(rows)

    if not df.empty:
        st.subheader("Routes Table")

        # Color entire row by route
        def highlight_row(row):
            color = row.Color
            return [f'background-color: {color}; color: black' for _ in row.index]

        st.dataframe(df.style.apply(highlight_row, axis=1))

        # CSV download (without color column)
        csv = df.drop(columns=["Color"]).to_csv(index=False)
        st.download_button("Download Routes CSV", csv, "routes.csv", "text/csv")
    else:
        st.warning("No routes found. Adjust parameters.")

    # --- Visualization ---
    st.subheader("Visualization")
    img = None
    if suffix.lower() != ".pdf":
        img_bgr = cv2.imread(fpath, cv2.IMREAD_COLOR)
        if img_bgr is not None:
            img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    fig2, ax2 = plt.subplots(figsize=(6, 6))
    if skel is not None:
        ax2.imshow(skel, cmap="gray", alpha=1.0)

    for idx, r in enumerate(results["routes"]):
        route = routes[idx]
        color = colors[idx % len(colors)]
        xs = [G.nodes[n]["x"] for n in route]
        ys = [G.nodes[n]["y"] for n in route]
        ax2.plot(xs, ys, color=color, linewidth=2, label=f"Route {idx+1}")
        ax2.scatter([xs[0]], [ys[0]], marker="o", color="green", s=40, label="_nolegend_")
        ax2.scatter([xs[-1]], [ys[-1]], marker="x", color="red", s=40, label="_nolegend_")

        # Plot decision points with labels
        for dp in r["decision_points"]:
            dp_name, N_ij, P_ij, E_ij, dp_type = dp
            if "turn" in dp_type:
                tp_idx = int(dp_name.split("_")[1])
                x, y = r["turn_points"][tp_idx] if tp_idx < len(r["turn_points"]) else (xs[tp_idx], ys[tp_idx])
                ax2.scatter([x], [y], marker="o", color=color, s=50, edgecolor="black", label="_nolegend_")
                angle_str = dp_type.split("angle=")[-1].replace(")", "")
                ax2.text(x, y, f"{angle_str}°", color="black", fontsize=7, ha="center", va="bottom")
            elif dp_type == "junction":
                node_idx = route.index(dp_name) if dp_name in route else 0
                x, y = xs[node_idx], ys[node_idx]
                ax2.scatter([x], [y], marker="s", color="black", s=60, label="_nolegend_")
                ax2.text(x, y, f"N={N_ij}", color="white", fontsize=7, ha="center", va="center")

    ax2.axis("off")
    ax2.set_title("Skeleton and Detected Routes")
    ax2.legend(loc="upper right", fontsize=8)

    col1, col2 = st.columns(2)
    with col1:
        if img is not None:
            st.image(img, caption="Original Floor Plan", use_container_width=True)
        else:
            st.info("PDF detected – no raster image to show.")
    with col2:
        st.pyplot(fig2, use_container_width=True)

    # --- Save outputs ---
    out_json = json.dumps(results, indent=2)
    st.download_button("Download AQ JSON", out_json, "aq_results.json", "application/json")

    try:
        os.remove(fpath)
    except Exception:
        pass

else:
    st.info("Upload a floorplan to begin. Adjust parameters or re-run app if editing aq_tool.py.")
