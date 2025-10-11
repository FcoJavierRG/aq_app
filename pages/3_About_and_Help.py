# pages/3_About_and_Help.py
import streamlit as st

st.title("About & Help")
st.markdown("""
### Floorplan Accessibility Tool

This app evaluates **AccessQuotient (AQ)** — a measure of navigability in a building.

#### How It Works
1. Upload one or more floorplan images.
2. The tool extracts **walkable routes** from each floor.
3. Floors are linked via **vertical connectors** (stairs/elevators).
4. AQ is computed based on route structure and number of turns.

#### Outputs
- **AQ_S**: Structural accessibility score (fewer turns = higher AQ).
- **AQ_F**: Functional accessibility score (accounts for total path length).
- **Routes Table**: Detailed per-path data.
- **Skeletons**: Visual representation of traversable paths.
""")
