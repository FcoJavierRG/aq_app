# pages/2_Results_and_Visualization.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import cv2
import json
from aq_tool import extract_routes, compute_access_quotient

st.title("Results & Visualization")

if "graph" not in st.session_state:
    st.warning("No processed floorplan found. Please start at the Upload & Analyze page.")
    st.stop()

G = st.session_state["graph"]
skel = st.session_state["skeleton"]
input_path = st.session_state["input_path"]
metrics = st.session_state["metrics"]

# Sidebar parameters
st.sidebar.header("Route Extraction Settings")
max_routes = st.sidebar.slider("max_routes", 1, 10, 5)
min_branch_len = st.sidebar.slider("min_branch_len (px)", 1, 200, 10)
angle_thresh_deg = st.sidebar.slider("angle_thresh_deg", 5, 90, 30)
min_turn_len_px = st.sidebar.slider("min_turn_len_px", 1, 20, 3)

routes, weights = extract_routes(G, max_routes=max_routes)
results = compute_access_quotient(
    G, routes, weights,
    min_branch_len=min_branch_len,
    angle_thresh_deg=angle_thresh_deg,
    min_turn_len_px=min_turn_len_px
)

st.subheader("Summary Metrics")
st.json({"AQ_S": results["AQ_S"], "AQ_F": results["AQ_F"], "num_routes": len(routes)})
st.json(metrics)

rows = [
    {
        "Route": r["route_id"] + 1,
        "P_MF": round(r["P_MF"], 4),
        "E_M": round(r["E_M"], 2),
        "Turns": r["turns"],
        "Length_px": r["length"]
    }
    for r in results["routes"]
]

st.dataframe(pd.DataFrame(rows))

# Plot
fig, ax = plt.subplots(figsize=(6,6))
ax.imshow(skel, cmap="gray")
colors = ["red", "lime", "orange", "magenta", "cyan"]
for idx, route in enumerate(routes):
    xs = [G.nodes[n]["x"] for n in route]
    ys = [G.nodes[n]["y"] for n in route]
    ax.plot(xs, ys, color=colors[idx % len(colors)], linewidth=2, label=f"Route {idx+1}")
ax.legend()
ax.axis("off")
st.pyplot(fig)

st.download_button(
    "Download AQ Results JSON",
    data=json.dumps(results, indent=2),
    file_name="aq_results.json",
    mime="application/json"
)
