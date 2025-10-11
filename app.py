# app.py
import streamlit as st

st.set_page_config(
    page_title="AccessQuotient Floorplan Tool",
    page_icon="🏛️",
    layout="wide"
)

st.title("🏛️ Floorplan Accessibility (AccessQuotient) Tool")

st.markdown("""
Welcome to the **AccessQuotient (AQ) Tool** – an application for analyzing **walkability and accessibility**
from architectural **floorplans**.

Use the sidebar (👈) to navigate between:
1. **📤 Upload & Analyze** — upload your floorplan and compute the graph/skeleton.
2. **📈 Results & Visualization** — explore routes, turns, and AQ metrics.
3. **ℹ️ About & Help** — learn about the method, parameters, and output interpretation.
""")

st.image(
    "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/Floorplan_example.svg/1200px-Floorplan_example.svg.png",
    caption="Example floorplan illustration",
    use_container_width=True
)

st.info("➡️ Start by selecting **📤 Upload & Analyze** from the sidebar.")
