import streamlit as st

st.set_page_config(layout="wide")

st.title("About the AccessQuotient Tool")
st.markdown("---")

st.header("What is This Tool?")
st.markdown("""
The **AccessQuotient (AQ) Tool** is an interactive platform for evaluating the navigational complexity of indoor spaces from a floorplan image. It is designed to help architects, designers, and accessibility researchers quantify how challenging a layout might be, particularly for individuals with blindness or visual impairments (BVI).

By analyzing pathways, junctions, and turns, the tool generates objective scores that reflect the cognitive load required to navigate a space successfully.
""")

st.header("How It Works: From Image to Insight")
st.markdown("""
The tool follows a four-step process to analyze a floorplan:

**Step 1: Image Processing**
First, the uploaded image (PNG, JPG, or PDF) is converted into a high-contrast, black-and-white version. The tool identifies the walls and then inverts this to create a "walkable mask," which represents all the open, navigable spaces.

**Step 2: Skeletonization**
From the walkable mask, the tool extracts a one-pixel-wide "skeleton." This skeleton represents the centerlines of all possible paths through the corridors and open areas, forming the foundational map for all subsequent analysis.

**Step 3: Graph Creation**
The skeleton is converted into a mathematical graph consisting of:
-   **Nodes:** These are the key points on the map, such as intersections (junctions where 3 or more paths meet) and endpoints (dead ends or exits).
-   **Edges:** These are the paths connecting the nodes.

**Step 4: Route Analysis & AQ Calculation**
The tool analyzes routes through this graph to calculate the AccessQuotient. It identifies two types of navigational challenges:
-   **Junctions:** Complex intersections that require a choice between multiple paths.
-   **Turns:** Significant bends in a corridor that require a clear decision to change direction.

Each of these decision points contributes to the overall complexity of a route, which is used to calculate the final AQ scores.
""")

st.header("Understanding the Metrics")
st.markdown("""
The tool calculates two variants of the AccessQuotient metric:

-   **Strict AccessQuotient ($AQ_S$):** This measures the probability of completing a route *perfectly* with zero mistakes. It is a weighted average of the mistake-free probabilities for a set of key routes. A higher score (closer to 1.0) indicates an environment that is easier to navigate without any errors.

-   **Flexible AccessQuotient ($AQ_F$):** This metric is based on the *expected number of mistakes* one might make on a route. It accounts for the fact that people can recover from errors. A higher score (closer to 1.0) indicates an environment where fewer mistakes are likely to occur, even if the navigation isn't perfect.
""")

st.header("Parameter Explanations")
st.markdown("""
You can fine-tune the analysis using the parameters in the sidebar on the **Upload and Analyze** page. Here's what they mean:
""")

st.subheader("Analysis Parameters")
st.markdown("""
-   **`px_per_meter` (approx):** This sets the physical scale of the floorplan. An accurate estimate helps in interpreting the lengths of paths and branches in real-world terms, though it does not directly affect the AQ score itself.
-   **`max_routes`:** This controls how many diverse, long routes the tool will attempt to automatically identify after processing the floorplan. These routes are used for the "Automatic Route Analysis."
""")

st.subheader("AccessQuotient Calculation")
st.markdown("""
-   **`min_branch_len` (px):** At a junction (where three or more paths meet), any path shorter than this value will be ignored. This is useful for filtering out noise from the skeletonization process, such as tiny, irrelevant stubs.
-   **`angle_thresh_deg`:** This is the minimum angle that a bend in a corridor must have to be considered a "turn" (a binary decision point). This prevents gentle curves from being counted as navigational challenges.
-   **`min_turn_len_px`:** This parameter controls the sensitivity of the turn-detection algorithm. It acts as a "sampling distance" to smooth out the path before measuring angles.
    -   A **low value** (e.g., 1-3) makes the detection very sensitive to small wiggles in the path.
    -   A **high value** (e.g., 10+) will only detect large, significant changes in direction, ignoring minor curves.
""")

st.header("Current Limitations")
st.markdown("""
-   **Single-Floor Analysis Only:** The tool can only process one floorplan image at a time. It cannot analyze routes that involve stairs or elevators between different floors.
-   **No Obstacle Recognition:** The analysis assumes all space on the skeleton is "walkable" and does not account for temporary obstacles (e.g., furniture, planters) that are not part of the main walls.
""")

