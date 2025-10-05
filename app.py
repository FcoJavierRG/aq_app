# app.py
import streamlit as st
import importlib
import tempfile, os, json
import pandas as pd
import matplotlib.pyplot as plt
import cv2

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

uploaded = st.file_uploader("Upload floorplan (png, jpg, pdf)", type=["png","jpg","jpeg","pdf"])

if uploaded:
    # Save upload to temporary file
    suffix = os.path.splitext(uploaded.name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded.getvalue())
    tmp.flush()
    tmp.close()
    fpath = tmp.name

    st.info("Running pipeline — this may take several seconds for large images.")
    with st.spinner("Processing..."):
        try:
            # Run pipeline (returns metrics, graph, skeleton)
            metrics, G, skel = run_aq_pipeline(fpath, px_per_meter=px_per_meter, return_skeleton=True)
        except Exception as e:
            st.error(f"Pipeline failed: {e}")
            raise

        # Extract routes
        routes, weights = extract_routes(G, max_routes=max_routes)

        # Compute AQ with the improved function that detects turns
        results = compute_access_quotient(G, routes, weights,
                                         min_branch_len=min_branch_len,
                                         angle_thresh_deg=angle_thresh_deg,
                                         min_turn_len_px=min_turn_len_px)

    # --- Display summary metrics ---
    st.subheader("Summary Metrics")
    col1, col2 = st.columns([1,2])
    with col1:
        st.json({"AQ_S": results["AQ_S"], "AQ_F": results["AQ_F"], "num_routes": len(routes)})
    with col2:
        # show raw metrics from pipeline
        st.write("Pipeline-level metrics (skeleton/graph):")
        st.json(metrics)

    # --- Build routes DataFrame ---
    rows = []
    for r in results["routes"]:
        rows.append({
            "Route": r["route_id"]+1,
            "P_MF": round(r["P_MF"], 4),
            "E_M": round(r["E_M"], 2),
            "Turns": r.get("turns", 0),
            "Length_px": int(r.get("length", 0))
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        st.subheader("Routes table")
        st.dataframe(df)

        # CSV download
        csv = df.to_csv(index=False)
        st.download_button("Download routes CSV", csv, "routes.csv", "text/csv")

    else:
        st.warning("No routes found. Try adjusting parameters (reduce min_branch_len or increase max_routes).")

    # --- Plot original image + routes overlay ---
    st.subheader("Visualization")
    # load original for background if raster (if pdf, skip background)
    try:
        if suffix.lower() == ".pdf":
            # use skeleton only when pdf
            img = None
        else:
            img_bgr = cv2.imread(fpath, cv2.IMREAD_COLOR)
            if img_bgr is not None:
                img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            else:
                img = None
    except Exception:
        img = None

    fig, ax = plt.subplots(figsize=(8,8))
    if img is not None:
        ax.imshow(img, alpha=0.8)
    # if skeleton exists, show it as background
    if skel is not None:
        ax.imshow(skel, cmap="gray", alpha=0.6)

    colors = ["cyan","lime","orange","magenta","brown","yellow","red","blue","purple","teal"]
    for idx, route in enumerate(routes):
        xs = [G.nodes[n]["x"] for n in route]
        ys = [G.nodes[n]["y"] for n in route]
        ax.plot(xs, ys, color=colors[idx%len(colors)], linewidth=2, label=f"Route {idx+1}")
        ax.scatter([xs[0]],[ys[0]], marker="o", color="green", s=40)   # start
        ax.scatter([xs[-1]],[ys[-1]], marker="x", color="red", s=40)  # end
    ax.axis("off")
    ax.set_title("Routes overlay (skeleton in background)")

    st.pyplot(fig)

    # Save outputs (optional)
    out_json = json.dumps(results, indent=2)
    st.download_button("Download AQ JSON", out_json, "aq_results.json", "application/json")

    # Clean up temp file
    try:
        os.remove(fpath)
    except Exception:
        pass

else:
    st.info("Upload a floorplan to begin. If you are editing aq_tool.py, re-run this app to pick up changes.")
