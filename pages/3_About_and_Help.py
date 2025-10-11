# pages/3_About_and_Help.py
import streamlit as st

st.title("About AccessQuotient Tool")

st.markdown("""
### What is AccessQuotient (AQ)?
AccessQuotient quantifies **spatial accessibility** within a building layout.  
It considers:
- **Route simplicity** (fewer turns = higher AQ)
- **Movement efficiency** (shorter, more direct paths)
- **Decision complexity** (number of junctions)

### How to use:
1. Upload one or more floorplans (each = one floor).
2. Let the app process connectivity and generate metrics.
3. View results and route visualizations on the **Results** page.

### Tips:
- Use clean, high-contrast floorplan images.
- Adjust parameters in `aq_tool.py` for precision.
- Works best for architectural layouts with clear corridors or paths.
""")

