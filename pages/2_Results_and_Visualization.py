import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import cv2
import aq_tool # Import your tool to use its functions

st.set_page_config(page_title="Results", layout="wide")
st.title("2. Results and Visualization")

# Check if results exist in the session state
if "aq_results" not in st.session_state:
    st.warning("No results found. Please run an analysis on the 'Upload and Analyze' page first.")
    st.stop()

# Retrieve data from session state
results = st.session_state["aq_results"]
routes = st.session_state["aq_routes"]
G = st.session_state["aq_graph"]
skel = st.session_state["aq_skel"]
input_path = st.session_state["input_path"]
filename = st.session_state["filename"]

st.header("Overall Accessibility Scores")
st.markdown(f"Metrics for **{filename}**")

col1, col2 = st.columns(2)
with col1:
    aq_s = results.get('AQ_S', 0)
    st.metric(
        label="Strict AccessQuotient (AQ_S)",
        value=f"{aq_s:.4f}",
        help="Represents the weighted probability of mistake-free navigation. Higher is better."
    )
with col2:
    aq_f = results.get('AQ_F', 0)
    st.metric(
        label="Flexible AccessQuotient (AQ_F)",
        value=f"{aq_f:.4f}",
        help="Reflects navigability based on the expected number of mistakes. Higher is better (fewer mistakes)."
    )

st.header("Per-Route Details")
if routes:
    df = pd.DataFrame([
        {
            "Route": r["route_id"] + 1,
            "P_MF (Mistake-Free Prob.)": r["P_MF"],
            "E_M (Expected Mistakes)": r["E_M"],
            "Junctions": sum(1 for dp in r['decision_points'] if dp['type'] == 'junction'),
            "Length (px)": int(r.get("length", 0))
        }
        for r in results["routes"]
    ])
    st.dataframe(df.style.format({
        "P_MF (Mistake-Free Prob.)": "{:.4f}",
        "E_M (Expected Mistakes)": "{:.2f}"
    }))
    
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download Route Data as CSV", csv, f"routes_{filename}.csv", "text/csv")
else:
    st.warning("No routes could be extracted based on the current parameters.")

# --- Visualization ---
st.header("Route Visualization")
st.markdown("Select an option below to view either the floorplan image or the routes overlaid on the skeleton.")

bg_choice = st.radio(
    "Choose visualization:",
    ("Floorplan Image", "Skeleton with Routes"),
    horizontal=True,
    help="Select the view."
)

fig, ax = plt.subplots(figsize=(10, 10))

# Set view based on user's choice
if bg_choice == "Floorplan Image":
    st.info("Displaying the original floorplan.")
    try:
        img_bgr = aq_tool.load_image_any(input_path)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        ax.imshow(img_rgb)
    except Exception as e:
        st.error(f"Could not load original image for display: {e}")
        ax.set_facecolor('white')
        ax.set_xticks([])
        ax.set_yticks([])

elif bg_choice == "Skeleton with Routes":
    st.info("Displaying routes on the computed skeleton. Green circles mark the start of a route, and red 'X's mark the end.")
    # Set skeleton as background
    if skel is not None:
        ax.imshow(skel, cmap="gray")
    else:
        st.warning("Skeleton data not available.")
        ax.set_facecolor('white')
        ax.set_xticks([])
        ax.set_yticks([])

    # Plot routes ONLY on the skeleton view
    if routes:
        colors = plt.cm.get_cmap("tab10", len(routes))
        for idx, route in enumerate(routes):
            xs = [G.nodes[n]["x"] for n in route]
            ys = [G.nodes[n]["y"] for n in route]
            ax.plot(xs, ys, color=colors(idx), linewidth=2.5, label=f"Route {idx+1}")
            ax.scatter([xs[0]], [ys[0]], color="green", marker="o", s=60, zorder=10)
            ax.scatter([xs[-1]], [ys[-1]], color="red", marker="x", s=60, zorder=10)
        ax.legend()

ax.axis("off")
plt.tight_layout()
st.pyplot(fig)

