# app.py
import streamlit as st

st.set_page_config(
    page_title="AccessQuotient Analyzer",
    layout="wide"
)

st.title("AccessQuotient Multi-Floor Analyzer")

st.markdown("""
Welcome to the **AccessQuotient (AQ) Analyzer** — an interactive tool for evaluating 
**spatial accessibility** and **path efficiency** within building floorplans.

### How it works:
1. Upload one or more **floorplan images (JPG, PNG, or PDF)** on the **Upload & Analyze** page.  
2. The app extracts **connectivity skeletons**, **decision points**, and **routes** automatically.  
3. Review metrics and visualizations on the **Results** page.  
4. Learn more about AQ and its interpretation on the **About** page.

Use the sidebar or page tabs below to get started.
""")

st.info("Go to **Upload & Analyze** to begin.")
