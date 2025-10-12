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
    # Initialize the list for custom route definitions (start, end)
    if "custom_route_definitions" not in st.session_state:
        st.session_state["custom_route_definitions"] = []


    st.success("Initial analysis complete. You can now define a list of custom routes below.")

    # --- 3. MANUAL ROUTE SELECTION UI ---
    with st.expander("Manual Route Selection", expanded=True):
        st.markdown("Use the controls to build a list of custom routes (e.g., Route 1: 5 -> 23, Route 2: 10 -> 45). Then, click the analyze button.")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("### Define a Route")
            if G.number_of_nodes() > 0:
                node_list = sorted(list(G.nodes()))
                start_node = st.selectbox("Select Start Node", node_list)
                end_node = st.selectbox("Select End Node", node_list, index=min(1, len(node_list)-1))

                if st.button("➕ Add Route to List"):
                    if start_node == end_node:
                        st.warning("Start and end nodes cannot be the same.")
                    else:
                        # Add the (start, end) tuple to our definitions list
                        st.session_state.custom_route_definitions.append((start_node, end_node))
                        st.rerun()
            else:
                st.warning("No nodes found in graph. Cannot select a route.")

            # --- Display and manage custom routes list ---
            st.write("### Custom Route List")
            if not st.session_state.custom_route_definitions:
                st.caption("No custom routes defined yet.")
            else:
                for i, (start, end) in enumerate(st.session_state.custom_route_definitions):
                    st.text(f"Route {i+1}: Node {start} -> Node {end}")
                
                if st.button("🗑️ Clear Route List"):
                    st.session_state.custom_route_definitions = []
                    # Also clear previous results if they exist
                    if 'custom_results' in st.session_state:
                        del st.session_state['custom_results']
                    if 'custom_routes' in st.session_state:
                        del st.session_state['custom_routes']
                    st.rerun()
            
            # --- Analyze the entire list of custom routes ---
            if st.session_state.custom_route_definitions:
                if st.button("Analyze Full Custom Route List", type="primary"):
                    custom_routes = []
                    valid_definitions = []
                    with st.spinner("Calculating paths for custom routes..."):
                        for start, end in st.session_state.custom_route_definitions:
                            try:
                                path = nx.dijkstra_path(G, source=start, target=end, weight='weight')
                                custom_routes.append(path)
                                valid_definitions.append((start,end))
                            except nx.NetworkXNoPath:
                                st.error(f"Could not find a path for route: {start} -> {end}. It will be skipped.")
                    
                    if custom_routes:
                        st.session_state['custom_routes'] = custom_routes
                        st.session_state['custom_route_definitions'] = valid_definitions # Update list to only valid ones
                        
                        custom_weights = [1.0 / len(custom_routes)] * len(custom_routes)
                        custom_results = compute_access_quotient(
                            G, custom_routes, custom_weights,
                            min_branch_len=min_branch_len,
                            angle_thresh_deg=angle_thresh_deg,
                            min_turn_len_px=min_turn_len_px
                        )
                        st.session_state['custom_results'] = custom_results
                        st.success("Analysis of custom routes is complete! Go to the **Results** page to view.")
                    else:
                        st.warning("No valid paths were found for the defined routes. Analysis could not be completed.")


        with col2:
            st.write("### Node Map")
            fig = plot_graph_with_labels(skel, G, title="Reference this map to select start/end nodes")
            st.pyplot(fig)
else:
    st.warning("Upload a floorplan to begin analysis.")

