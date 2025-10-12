import streamlit as st
import tempfile, os, json, pandas as pd, matplotlib.pyplot as plt, cv2, networkx as nx
import aq_tool
from aq_tool import run_aq_pipeline, extract_routes, compute_access_quotient, plot_graph_with_labels

st.set_page_config(layout="wide")

st.title("Upload and Analyze Floorplan")
st.info("Start by uploading a floorplan. After the initial analysis, a new section will appear for manual route selection.")

# --- 1. SIDEBAR PARAMETERS ---
st.sidebar.header("Analysis Parameters")
px_per_meter = st.sidebar.number_input("`px_per_meter` (approx)", value=50.0, min_value=1.0, help="The approximate scale of the floorplan in pixels per meter.")

st.sidebar.subheader("Automatic Route Extraction")
max_routes = st.sidebar.slider("`max_routes`", 1, 20, 5, help="The maximum number of diverse routes to automatically find.")

st.sidebar.subheader("AccessQuotient Calculation")
min_branch_len = st.sidebar.slider("`min_branch_len` (px)", 1, 50, 10, help="Minimum pixel length for a path to be considered a valid branch at a junction.")
angle_thresh_deg = st.sidebar.slider("`angle_thresh_deg`", 5, 90, 45, help="Minimum angle (in degrees) to classify a bend in a corridor as a 'turn'.")
min_turn_len_px = st.sidebar.slider("`min_turn_len_px`", 1, 50, 5, help="The sampling distance used to smooth the path before measuring turn angles. Higher values ignore smaller wiggles.")


# --- 2. FILE UPLOAD AND INITIAL ANALYSIS ---
uploaded = st.file_uploader("Upload floorplan (png, jpg, pdf)", type=["png","jpg","jpeg","pdf"])

if uploaded:
    # Create a temporary file to store the uploaded content
    suffix = os.path.splitext(uploaded.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getvalue())
        fpath = tmp.name

    st.info("Running initial analysis to build the pathway graph...")
    with st.spinner("Processing floorplan... (this may take a moment)"):
        G, skel = run_aq_pipeline(fpath, px_per_meter=px_per_meter, return_skeleton=True)
        
        # --- Automatic route analysis ---
        auto_routes, auto_weights = extract_routes(G, max_routes=max_routes)
        auto_results = compute_access_quotient(
            G, auto_routes, auto_weights,
            min_branch_len=min_branch_len,
            angle_thresh_deg=angle_thresh_deg,
            min_turn_len_px=min_turn_len_px
        )

    # --- Store results in session state ---
    st.session_state["aq_graph"] = G
    st.session_state["aq_skel"] = skel
    st.session_state["input_path"] = fpath
    st.session_state["auto_results"] = auto_results
    st.session_state["auto_routes"] = auto_routes
    if "custom_routes" not in st.session_state:
        st.session_state["custom_routes"] = []

    st.success("Initial analysis complete. You can now select routes manually below.")

    # --- 3. MANUAL ROUTE SELECTION UI ---
    with st.expander("Manual Route Selection", expanded=True):
        st.markdown("Select start and end nodes from the graph to define a custom route. The labeled nodes are shown on the map below.")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("### Route Definition")
            if G.number_of_nodes() > 0:
                node_list = sorted(list(G.nodes()))
                start_node = st.selectbox("Select Start Node", node_list)
                end_node = st.selectbox("Select End Node", node_list, index=min(1, len(node_list)-1))

                if st.button("➕ Add Route"):
                    if start_node == end_node:
                        st.warning("Start and end nodes cannot be the same.")
                    else:
                        try:
                            path = nx.dijkstra_path(G, source=start_node, target=end_node, weight='weight')
                            st.session_state.custom_routes.append(path)
                            st.rerun()
                        except nx.NetworkXNoPath:
                            st.error(f"No path could be found between node {start_node} and {end_node}.")
            else:
                st.warning("No nodes found in graph. Cannot select a route.")

            # --- Display and manage custom routes ---
            st.write("### Current Custom Routes")
            if not st.session_state.custom_routes:
                st.caption("No custom routes added yet.")
            else:
                for i, r in enumerate(st.session_state.custom_routes):
                    st.text(f"Route {i+1}: {' -> '.join(map(str, r))}")
                if st.button("🗑️ Clear All Custom Routes"):
                    st.session_state.custom_routes = []
                    st.rerun()
            
            # --- Analyze custom routes ---
            if st.session_state.custom_routes:
                if st.button("Analyze Custom Routes", type="primary"):
                    with st.spinner("Analyzing..."):
                        custom_weights = [1.0 / len(st.session_state.custom_routes)] * len(st.session_state.custom_routes)
                        custom_results = compute_access_quotient(
                            G, st.session_state.custom_routes, custom_weights,
                            min_branch_len=min_branch_len,
                            angle_thresh_deg=angle_thresh_deg,
                            min_turn_len_px=min_turn_len_px
                        )
                        st.session_state['custom_results'] = custom_results
                    st.success("Analysis of custom routes is complete! Go to the **Results** page to view.")


        with col2:
            st.write("### Node Map")
            fig = plot_graph_with_labels(skel, G, title="Click nodes to select route start/end")
            st.pyplot(fig)
else:
    st.warning("Upload a floorplan to begin analysis.")

