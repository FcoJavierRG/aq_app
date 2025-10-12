import streamlit as st

st.set_page_config(page_title="Floorplan AQ Tool", layout="wide")

st.title("Floorplan Accessibility (AccessQuotient) Tool")
st.markdown("""
Welcome to the **Floorplan AQ Tool** — a visual analytics platform for evaluating spatial accessibility based on the AccessQuotient metric.

This tool processes a floorplan image to identify walkable paths, extracts key routes, and calculates accessibility scores that reflect navigational complexity for individuals with Blind and Visual Impairments (BVI).

### How to Use the Tool

Use the sidebar on the left to navigate between pages:

1.  ** Upload and Analyze**: Upload your floorplan (PNG, JPG, or PDF) and configure the analysis parameters. This is the first step.
2.  **[Image of a bar chart] Results and Visualization**: After analysis, this page will display the calculated AccessQuotient scores, detailed metrics for each route, and an interactive visualization of the routes overlaid on your floorplan.
3.  ** About**: Learn more about the AccessQuotient methodology, the parameters, and how the tool works.

Ready to start? Select **Upload and Analyze** from the sidebar.
""")
