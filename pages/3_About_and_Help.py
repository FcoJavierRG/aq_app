import streamlit as st

st.set_page_config(page_title="About", layout="wide")

st.title("3. About the AccessQuotient Tool")

st.markdown("""
This tool implements the **AccessQuotient** metric, a framework designed to quantify the navigational complexity of indoor environments, specifically for individuals who are Blind or Visually Impaired (BVI).

It analyzes a 2D floorplan to model potential routes and identifies decision points that can pose challenges.
""")

st.header("Methodology")

st.markdown("""
The process involves several key steps:

1.  **Image Preprocessing**: The uploaded floorplan is converted into a binary (black and white) image. The tool identifies walls and isolates the "walkable" free space.
2.  **Skeletonization**: The walkable space is reduced to a thin, one-pixel-wide skeleton that represents all possible navigation paths. This skeleton forms the basis of a mathematical graph.
3.  **Graph Extraction**: The skeleton is converted into a `networkx` graph, where junctions (intersections) and endpoints of corridors become nodes, and the paths between them become edges.
4.  **Route Identification**: The tool automatically identifies a set of diverse, significant routes within the building, typically between major endpoints.
5.  **AccessQuotient Calculation**: For each route, the tool calculates two key metrics based on the number and complexity of its decision points (junctions and sharp turns):
    * **$P_{MF}$ (Probability of Mistake-Free Navigation)**: The likelihood of traversing the route without making a single wrong turn.
    * **$E_M$ (Expected Mistakes)**: The average number of errors one might make along the route.

These individual route scores are then aggregated into two final building-wide scores:
- **`AQ_S` (Strict AccessQuotient)**: A score based on the probability of perfect, mistake-free navigation.
- **`AQ_F` (Flexible AccessQuotient)**: A score based on the expected number of mistakes, acknowledging that errors can happen.

**For both metrics, a higher score indicates a more accessible, less complex environment.**
""")

st.header("Configurable Parameters")
st.markdown("""
The parameters in the sidebar allow you to fine-tune the analysis:

- **Pixels per Meter**: Helps scale the analysis and is important for future distance-based metrics.
- **Max Routes to Extract**: Controls how many distinct paths are analyzed. More routes provide a more comprehensive, but slower, analysis.
- **Min Branch Length**: A noise-reduction parameter. It prevents tiny, insignificant architectural features from being counted as complex junctions.
- **Turn Angle Threshold**: Defines what constitutes a "significant" turn. A gentle curve in a hallway is ignored, but a sharp 90-degree turn is correctly identified as a decision point.
- **Min Turn Segment Length**: Prevents small, noisy wiggles in the skeleton from being counted as turns.
""")
