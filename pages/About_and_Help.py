# pages/3_About_and_Help.py
import streamlit as st

st.title("About & Help")

st.markdown("""
### What is AccessQuotient (AQ)?
**AccessQuotient** quantifies how easily a person can move through a space, based on the **structure and connectivity** of paths.

### How It Works
1. Detect walkable areas from the floorplan.
2. Convert them into a **skeleton** of navigable routes.
3. Build a **graph network** connecting junctions and corridors.
4. Calculate accessibility scores from **path lengths**, **turn angles**, and **branching complexity**.

### Key Metrics
- **AQ_S** — Sum of accessibility probabilities across all main routes.
- **AQ_F** — Average accessibility (fluency) across routes.
- **P_MF** — Probability of making the correct movement.
- **E_M** — Effort measure (lower = better).

### Tips
- If you see *0 routes or turns*, increase `min_branch_len` or reduce `angle_thresh_deg`.
- For clean vector drawings (PDF), use a higher `px_per_meter` (e.g., 100).
- For scanned images, reduce `px_per_meter` or smooth with larger `blur_ksize`.

### Authors
Developed by *[Your Name]* as part of research on spatial accessibility and indoor navigation.
""")
