import streamlit as st

st.set_page_config(page_title="Floorplan AQ Tool", layout="wide")

st.title("Floorplan Accessibility (AccessQuotient) Tool")
st.markdown("""
Welcome to the **Floorplan AQ Tool**, an interactive platform for evaluating spatial accessibility. 
This tool allows you to analyze floorplans to understand and quantify navigational complexity.

**Follow this workflow:**

1.  **Upload and Analyze:**
    * Navigate to this page using the sidebar.
    * Upload your floorplan (PNG, JPG, or PDF) and set the analysis parameters.
    * The tool will automatically process the image and build a complete pathway graph.

2.  **Define Custom Routes (Optional):**
    * After the initial analysis, a **Manual Route Selection** panel will appear.
    * Use the generated node map to define a list of specific start and end points for routes you wish to evaluate.

3.  **Results and Visualization:**
    * Go to this page to view a detailed breakdown of both the automatically detected routes and your custom-defined routes.
    * Explore metrics like **AccessQuotient (Strict & Flexible)**, expected mistakes, and the number of turns and junctions.

4.  **About:**
    * Visit this page for detailed explanations of the methodology and the various parameters you can adjust.

---
""")
