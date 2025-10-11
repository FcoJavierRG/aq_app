# pages/1_Upload_and_Analyze.py
import streamlit as st
import tempfile, os
import importlib
import networkx as nx
import numpy as np
import aq_tool
importlib.reload(aq_tool)
from aq_tool import run_aq_pipeline, extract_routes, compute_access_quotient

st.title("Upload and Analyze Floorplans")

st.markdown("""
Upload one or more **floorplans** (PNG, JPG, or PDF).  
Each uploaded image will be treated as a separate floor (Floor 1, Floor 2, etc.).
""")

px_per_meter = st.sidebar.number_input("px_per_meter (approx)", value=50.0, min_value=1.0)
max_routes = st.sidebar.slider("max_routes", min_value=1, max_value=10, value=5)
min_branch_len = st.sidebar.slider("min_branch_len (px)", min_value=1, max_value=200, value=10)
angle_thresh_deg = st.sidebar.slider("angle_thresh_deg", min_value=5, max_value=90, value=30)
min_turn_len_px = st.sidebar.slider("min_turn_len_px", min_value=1, max_value=20, value=3)

uploaded_files = st.file_uploader(
    "Upload one or more floorplans", 
    type=["png", "jpg", "jpeg", "pdf"], 
    accept_multiple_files=True
)

if uploaded_files:
    st.info("Running accessibility analysis...")
    floor_graphs = []
    for idx, uploaded in enumerate(uploaded_files):
        suffix = os.path.splitext(uploaded.name)[1]
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(uploaded.getvalue())
        tmp.close()

        floor_name = f"Floor {idx+1}"
        st.write(f"Processing {floor_name}...")

        try:
            metrics, G, skel = run_aq_pipeline(tmp.name, px_per_meter=px_per_meter, return_skeleton=True)
            for n in G.nodes:
                G.nodes[n]["floor"] = idx + 1
            floor_graphs.append({"name": floor_name, "G": G, "skel": skel, "path": tmp.name})
        except Exception as e:
            st.error(f"Failed on {uploaded.name}: {e}")
            continue

    # Merge graphs (link floors automatically)
    if len(floor_graphs) == 1:
        G_total = floor_graphs[0]["G"]
    else:
        G_total = nx.compose_all([fg["G"] for fg in floor_graphs])
        for i in range(len(floor_graphs)-1):
            G1, G2 = floor_graphs[i]["G"], floor_graphs[i+1]["G"]
            x1, y1 = np.mean([G1.nodes[n]["x"] for n in G1]), np.mean([G1.nodes[n]["y"] for n in G1])
            x2, y2 = np.mean([G2.nodes[n]["x"] for n in G2]), np.mean([G2.nodes[n]["y"] for n in G2])

            def find_nearest(G, x, y):
                return min(G.nodes, key=lambda n: (G.nodes[n]["x"]-x)**2 + (G.nodes[n]["y"]-y)**2)
            n1, n2 = find_nearest(G1, x1, y1), find_nearest(G2, x2, y2)
            G_total.add_edge(n1, n2, weight=3.0, type="vertical")

    routes, weights = extract_routes(G_total, max_routes=max_routes)
    results = compute_access_quotient(
        G_total, routes, weights,
        min_branch_len=min_branch_len,
        angle_thresh_deg=angle_thresh_deg,
        min_turn_len_px=min_turn_len_px
    )

    st.session_state["results"] = results
    st.session_state["routes"] = routes
    st.session_state["floor_graphs"] = floor_graphs

    st.success("Analysis complete! Go to the 'Results and Visualization' page to explore outputs.")
