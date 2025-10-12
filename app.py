# app.py
import streamlit as st

st.set_page_config(
    page_title="AccessQuotient Floorplan Tool",
    layout="wide"
)

st.title("Floorplan Accessibility (AccessQuotient) Tool")

st.markdown("""
Welcome to the **AccessQuotient (AQ) Tool** – an application for analyzing **walkability and accessibility**
from architectural **floorplans**.

Use the sidebar to navigate between:
1. **Upload & Analyze** — upload your floorplan and compute the graph/skeleton.
2. **Results & Visualization** — explore routes, turns, and AQ metrics.
3. **About & Help** — learn about the method, parameters, and output interpretation.
""")

st.info("Start by selecting **Upload & Analyze** from the sidebar.")
