import streamlit as st
import tempfile
import os
import aq_tool # Your main logic file

st.set_page_config(page_title="Upload & Analyze", layout="wide")

st.title("1. Upload and Analyze Floorplan")
st.markdown("Upload your floorplan image and configure the analysis parameters. The tool will process the image to extract a navigational graph and identify key routes.")

# --- Sidebar for Parameters ---
st.sidebar.header("Analysis Parameters")
px_per_meter = st.sidebar.number_input(
    "Pixels per Meter (approx)", 
    value=50.0, min_value=1.0, 
    help="Estimate the scale of the floorplan. How many pixels correspond to one meter?"
)
max_routes = st.sidebar.slider(
    "Max Routes to Extract", 1, 15, 5,
    help="The maximum number of distinct long routes to identify for analysis."
)

st.sidebar.header("Decision Point Parameters")
min_branch_len = st.sidebar.slider(
    "Min Branch Length (px)", 1, 100, 10,
    help="Ignore very short stubs at junctions to reduce noise."
)
angle_thresh_deg = st.sidebar.slider(
    "Turn Angle Threshold (deg)", 5, 90, 30,
    help="A turn in a corridor is only considered a decision point if its angle is greater than this value."
)
min_turn_len_px = st.sidebar.slider(
    "Min Turn Segment Length (px)", 1, 50, 5,
    help="Segments of a turn must be at least this long to be considered a valid decision point."
)

# --- Main Page for Upload and Execution ---
uploaded = st.file_uploader("Upload floorplan (png, jpg, pdf)", type=["png", "jpg", "jpeg", "pdf"])

if uploaded:
    # Use a temporary file to save the upload
    suffix = os.path.splitext(uploaded.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getvalue())
        fpath = tmp.name

    st.info(f"File '{uploaded.name}' uploaded successfully. Running analysis...")
    
    try:
        with st.spinner("Processing floorplan... This may take a moment."):
            # 1. Run the core pipeline to get the graph and skeleton
            G, skel = aq_tool.run_aq_pipeline(fpath, px_per_meter=px_per_meter, return_skeleton=True)
            
            # 2. Extract routes from the graph
            routes, weights = aq_tool.extract_routes(G, max_routes=max_routes)
            
            # 3. Compute AccessQuotient metrics
            results = aq_tool.compute_access_quotient(
                G, routes, weights,
                min_branch_len=min_branch_len,
                angle_thresh_deg=angle_thresh_deg,
                min_turn_len_px=min_turn_len_px
            )

        # Store results in session state to be used by other pages
        st.session_state["aq_results"] = results
        st.session_state["aq_graph"] = G
        st.session_state["aq_routes"] = routes
        st.session_state["aq_skel"] = skel
        st.session_state["input_path"] = fpath
        st.session_state["filename"] = uploaded.name

        st.success("Analysis complete! ✅")
        st.info("Navigate to the **Results and Visualization** page to explore the outputs.")

        # Show a preview of the main metrics
        st.subheader("Analysis Summary")
        st.json({
            "Strict AccessQuotient (AQ_S)": f"{results.get('AQ_S', 0):.4f}",
            "Flexible AccessQuotient (AQ_F)": f"{results.get('AQ_F', 0):.4f}",
            "Number of Routes Analyzed": len(routes)
        })

    except Exception as e:
        st.error(f"An error occurred during analysis: {e}")
        # Clean up the temp file in case of error
        if os.path.exists(fpath):
            os.remove(fpath)
else:
    st.info("Upload a floorplan to begin the analysis.")
