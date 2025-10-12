# pages/1_Upload_and_Analyze.py
import streamlit as st
import importlib, tempfile, os
import aq_tool

importlib.reload(aq_tool)
from aq_tool import run_aq_pipeline

st.title("Upload & Analyze Floorplan")

st.sidebar.header("Parameters")
px_per_meter = st.sidebar.number_input("px_per_meter (approx)", value=50.0, min_value=1.0)
min_corridor_px = st.sidebar.slider("min_corridor_px", 50, 1000, 200)
prune_len_px = st.sidebar.slider("prune_len_px", 1, 50, 10)

uploaded = st.file_uploader("Upload floorplan (png, jpg, pdf)", type=["png", "jpg", "jpeg", "pdf"])

if uploaded:
    suffix = os.path.splitext(uploaded.name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded.getvalue())
    tmp.flush()
    tmp.close()
    fpath = tmp.name

    st.info("⏳ Running pipeline...")
    with st.spinner("Processing..."):
        metrics, G, skel = run_aq_pipeline(fpath, px_per_meter=px_per_meter, return_skeleton=True)

    st.session_state["metrics"] = metrics
    st.session_state["graph"] = G
    st.session_state["skeleton"] = skel
    st.session_state["input_path"] = fpath

    st.success("Floorplan processed! Go to **Results & Visualization** → to continue.")
else:
    st.info("Upload a floorplan to begin analysis.")
