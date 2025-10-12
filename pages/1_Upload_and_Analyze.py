import streamlit as st
from aq_tool import run_aq_pipeline, extract_routes, compute_access_quotient, draw_routes_on_image
import tempfile, os

st.title("📤 Upload and Analyze Floorplans")

uploaded_files = st.file_uploader(
    "Upload one or more floorplans",
    type=["png", "jpg", "jpeg", "pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    st.session_state["floors"] = []
    for i, f in enumerate(uploaded_files, 1):
        st.subheader(f"🏠 Floor {i}")
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(f.name)[1]) as tmp:
            tmp.write(f.read())
            tmp_path = tmp.name

        metrics, G, skel = run_aq_pipeline(tmp_path, return_skeleton=True)
        routes, weights = extract_routes(G, max_routes=5)
        results = compute_access_quotient(G, routes, weights)

        st.session_state["floors"].append({
            "floor": i,
            "file": tmp_path,
            "metrics": metrics,
            "results": results,
            "G": G,
            "routes": routes,
            "skeleton": skel,
        })

        st.json(results)
        st.pyplot(plot_routes_side_by_side(tmp_path, skel, G, routes))

    st.success("✅ Floors processed! View detailed results on the **Results** page.")
else:
    st.info("Upload one or more floorplan images to begin.")
