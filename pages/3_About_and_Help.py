import streamlit as st

st.title("ℹ️ About and Help")

st.markdown("""
**AccessQuotient (AQ)** measures navigational accessibility and wayfinding complexity in spatial layouts.

#### How it works
1. The uploaded floorplan is preprocessed and skeletonized.
2. A topological graph of navigable routes is built.
3. AQ metrics (AQ_S, AQ_F) are computed using graph traversal.

#### Tips
- Use clear, high-contrast floorplans.
- Adjust thresholds if routes are missing or over-detected.
- Results can be exported as CSV or JSON.

#### References
This tool is based on research by spatial accessibility and network analysis methods using Python and OpenCV.

---
**Author:** You  
**Version:** 1.0  
**License:** MIT
""")
