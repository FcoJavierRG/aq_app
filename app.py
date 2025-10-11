# app.py
import streamlit as st

st.set_page_config(layout="wide", page_title="Floorplan AQ Tool")

st.title("Floorplan Accessibility (AccessQuotient) Tool")
st.markdown("""
Welcome to the **AccessQuotient (AQ) Tool**.

This app analyzes the **navigability and accessibility** of building floorplans using a skeleton-based graph approach.

### Features
- **Upload** one or more floorplan images (JPG, PNG, PDF)
- **Compute** accessibility metrics (AQ_S, AQ_F)
- **Detect** routes and geometric turns automatically
- **Visualize** the extracted skeleton and paths
- **Support** for **multi-floor buildings**

### Workflow
1. Go to **Upload and Analyze** to run the pipeline.
2. Then open **Results and Visualization** to view results.
3. Use **About and Help** for explanations of each metric.

---
""")
