import streamlit as st

st.set_page_config(page_title="Floorplan AQ Tool", layout="wide")

st.title("Floorplan Accessibility (AccessQuotient) Tool")
st.markdown("""
Welcome to the **Floorplan AQ Tool** — a visual analytics platform for evaluating spatial accessibility.
Use the sidebar to navigate between pages:

1. **Upload and Analyze** – upload your floorplan (PNG/JPG/PDF) and run the AccessQuotient pipeline.  
2. **Results and Visualization** – explore AQ metrics and visualize extracted routes.  
3. **About and Help** – learn about how the tool works and its methodology.

---
""")
