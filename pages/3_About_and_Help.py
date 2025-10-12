import streamlit as st

st.set_page_config(layout="wide")

st.title("About the AccessQuotient Tool")

st.header("Methodology")
st.markdown("""
The **AccessQuotient (AQ)** is a metric designed to quantify the navigational complexity of an indoor space, particularly for individuals with blindness or visual impairments (BVI). It models the challenges of navigating a building by focusing on the number and complexity of decision points a person encounters along a given route.

The tool calculates two variants of the metric:

-   **Strict AccessQuotient ($AQ_S$):** This measures the probability of completing a route *perfectly* with zero mistakes. It is a weighted average of the mistake-free probabilities for a set of key routes. A higher score indicates an environment that is easier to navigate without any errors.

-   **Flexible AccessQuotient ($AQ_F$):** This metric is based on the *expected number of mistakes* one might make on a route. It accounts for the fact that people can recover from errors. A higher score indicates an environment where fewer mistakes are likely to occur, even if the navigation isn't perfect.

The final score for a building is a weighted average of the scores for several important routes within it.
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

