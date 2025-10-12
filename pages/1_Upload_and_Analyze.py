import streamlit as st
import tempfile
import os
from aq_tool import run_aq_pipeline, extract_routes, compute_access_quotient

st.title("🏢 Upload and Analyze Floor Plans")

num_floors = st.number_input("Number of floors to analyze", min_value=1, max_value=10, value=1)
uploaded_files = [st.file_uploader(f"Upload Floor {i+1} Plan", type=["png", "jpg", "jpeg", "pdf"], key=f"file_{i}")
                  for i in range(num_floors)]

if st.button("Run Multi-Floor Analysis"):
    st.session_state.results = []
    st.session_state.graphs = []
    st.session_state.skeletons = []

    for i, uploaded in enumerate(uploaded_files):
        if uploaded is None:
            st.warning(f"Please upload Floor {i+1} before running.")
            st.stop()

        suffix = os.path.splitext(uploaded.name)[1]
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(uploaded.getvalue())
        tmp.flush()

        try:
            metrics, G, skel = run_aq_pipeline(tmp.name, return_skeleton=True)
            routes, weights = extract_routes(G)
            results = compute_access_quotient(G, routes, weights)

            st.session_state.results.append({
                "floor": i + 1,
                "metrics": metrics,
                "routes": results["routes"],
                "AQ_S": results["AQ_S"],
                "AQ_F": results["AQ_F"]
            })
            st.session_state.graphs.append(G)
            st.session_state.skeletons.append(skel)

            st.success(f"✅ Floor {i+1} processed successfully.")
        except Exception as e:
            st.error(f"Pipeline failed for Floor {i+1}: {e}")

    st.success("✅ All floors processed! Go to the **Results and Visualization** page to view combined results.")
