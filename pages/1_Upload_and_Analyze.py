import streamlit as st
import importlib, tempfile, os, json, pandas as pd, matplotlib.pyplot as plt, cv2
import aq_tool
from aq_tool import run_aq_pipeline, extract_routes, compute_access_quotient

st.title("Upload and Analyze Floorplan")

st.sidebar.header("Parameters")
px_per_meter = st.sidebar.number_input("px_per_meter (approx)", value=50.0, min_value=1.0)
max_routes = st.sidebar.slider("max_routes", 1, 10, 5)
min_branch_len = st.sidebar.slider("min_branch_len (px)", 1, 200, 10)
angle_thresh_deg = st.sidebar.slider("angle_thresh_deg", 5, 90, 30)
min_turn_len_px = st.sidebar.slider("min_turn_len_px", 1, 20, 3)

uploaded = st.file_uploader("Upload floorplan (png, jpg, pdf)", type=["png","jpg","jpeg","pdf"])

if uploaded:
    suffix = os.path.splitext(uploaded.name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded.getvalue())
    tmp.flush()
    fpath = tmp.name

    st.info("Running analysis pipeline...")
    with st.spinner("Processing..."):
        metrics, G, skel = run_aq_pipeline(fpath, px_per_meter=px_per_meter, return_skeleton=True)
        routes, weights = extract_routes(G, max_routes=max_routes)
        results = compute_access_quotient(
            G, routes, weights,
            min_branch_len=min_branch_len,
            angle_thresh_deg=angle_thresh_deg,
            min_turn_len_px=min_turn_len_px
        )

    st.session_state["aq_results"] = results
    st.session_state["aq_graph"] = G
    st.session_state["aq_routes"] = routes
    st.session_state["aq_skel"] = skel
    st.session_state["input_path"] = fpath
    st.success("Analysis complete. Visit **Results and Visualization** to explore outputs.")

    # Show basic metrics inline too
    st.json({"AQ_S": results["AQ_S"], "AQ_F": results["AQ_F"], "num_routes": len(routes)})

    try:
        os.remove(fpath)
    except Exception:
        pass
else:
    st.info("Upload a floorplan to begin.")
