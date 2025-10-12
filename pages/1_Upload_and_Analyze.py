import streamlit as st
import tempfile, os
import importlib
import networkx as nx
import numpy as np
import aq_tool
importlib.reload(aq_tool)
from aq_tool import run_aq_pipeline, extract_routes, compute_access_quotient

st.title("📤 Upload and Analyze Floorplans")

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

     # ============================================
# Merge graphs and create multi-floor links
# ============================================
if len(floor_graphs) == 1:
    G_total = floor_graphs[0]["G"]
else:
    G_total = nx.compose_all([fg["G"] for fg in floor_graphs])

    # Smarter vertical linking: find nodes roughly above each other
    max_xy_distance = 40  # pixel threshold for vertical alignment
    vertical_links = 0

    for i in range(len(floor_graphs) - 1):
        G1, G2 = floor_graphs[i]["G"], floor_graphs[i + 1]["G"]

        coords1 = np.array([[G1.nodes[n]["x"], G1.nodes[n]["y"]] for n in G1])
        coords2 = np.array([[G2.nodes[n]["x"], G2.nodes[n]["y"]] for n in G2])

        for n1 in G1.nodes:
            x1, y1 = G1.nodes[n1]["x"], G1.nodes[n1]["y"]
            # find nearest node in next floor
            nearest = min(G2.nodes, key=lambda n2: (G2.nodes[n2]["x"] - x1) ** 2 + (G2.nodes[n2]["y"] - y1) ** 2)
            x2, y2 = G2.nodes[nearest]["x"], G2.nodes[nearest]["y"]
            dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
            if dist < max_xy_distance:
                G_total.add_edge(n1, nearest, weight=dist, type="vertical")
                vertical_links += 1

    st.info(f"🔗 Created {vertical_links} vertical inter-floor links.")

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

    st.success("✅ Analysis complete! Go to the 'Results and Visualization' page to explore outputs.")
