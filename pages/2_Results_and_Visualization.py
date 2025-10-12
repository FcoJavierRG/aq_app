# pages/2_Results_and_Visualization.py
import streamlit as st
import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from streamlit_plotly_events import plotly_events

st.title("Results and Visualization (Enhanced)")

if "results" not in st.session_state:
    st.warning("No analysis found. Please upload floorplans first.")
    st.stop()

results = st.session_state["results"]
routes = st.session_state["routes"]
floor_graphs = st.session_state["floor_graphs"]
G_total = st.session_state["G_total"]

# ===========================
# Summary
# ===========================
st.subheader("Summary Metrics")
st.json({"AQ_S": results["AQ_S"], "AQ_F": results["AQ_F"], "num_routes": len(routes)})

rows = []
for r in results["routes"]:
    dp_str = ", ".join(f"{dp[0]}" for dp in r["decision_points"])
    rows.append({
        "Route": r["route_id"] + 1,
        "Turns": r["turns"],
        "Length_px": int(r["length"]),
        "P_MF": round(r["P_MF"],3),
        "E_M": round(r["E_M"],3),
        "DecisionPoints": dp_str
    })
st.dataframe(pd.DataFrame(rows))

# ===========================
# Floor Selection
# ===========================
floor_names = [fg["name"] for fg in floor_graphs]
selected_floor_idx = st.selectbox("Select floor to visualize", range(len(floor_graphs)), format_func=lambda i: floor_names[i])
fg = floor_graphs[selected_floor_idx]

# ===========================
# Click Selection for Custom Routes
# ===========================
st.subheader("Select Start and End Points")

fig2d = go.Figure()
skel_img = np.flipud(fg["skel"])
fig2d.add_trace(go.Heatmap(z=skel_img, colorscale="gray", showscale=False, hoverinfo="skip"))

click_result = plotly_events(fig2d, click_event=True, hover_event=False, select_event=False, key="floor_click")

if "clicks" not in st.session_state:
    st.session_state["clicks"] = []

if click_result:
    point = click_result[0]
    click_x, click_y = point["x"], fg["skel"].shape[0] - point["y"]
    nearest_node = min(
        G_total.nodes,
        key=lambda n: (G_total.nodes[n]["x"] - click_x) ** 2 + (G_total.nodes[n]["y"] - click_y) ** 2
    )
    st.session_state["clicks"].append(nearest_node)
    if len(st.session_state["clicks"]) > 2:
        st.session_state["clicks"] = st.session_state["clicks"][-2:]

if len(st.session_state["clicks"]) == 2:
    start, end = st.session_state["clicks"]
    path_nodes = nx.shortest_path(G_total, start, end, weight="weight")
    st.success(f"Custom route selected! {len(path_nodes)} nodes from start to end.")
else:
    path_nodes = []

# =========================
# 3D Visualization
# =========================
st.subheader("3D Multi-Floor Visualization (Enhanced)")

fig3 = go.Figure()
floor_gap = 15
floor_colors = ["gray", "lightblue", "lightgreen", "lightpink", "lightyellow", "lightcoral"]

for idx, fg in enumerate(floor_graphs):
    z_level = idx * floor_gap
    skel_img = np.flipud(fg["skel"])
    y_size, x_size = skel_img.shape
    y_coords, x_coords = np.mgrid[0:y_size, 0:x_size]

    fig3.add_trace(go.Surface(
        z=np.full_like(skel_img, z_level),
        x=x_coords,
        y=y_coords,
        surfacecolor=skel_img,
        colorscale=[[0, floor_colors[idx % len(floor_colors)]], [1, floor_colors[idx % len(floor_colors)]]],
        showscale=False,
        opacity=0.4,
        name=f"Floor {idx+1}"
    ))

if path_nodes:
    x_vals, y_vals, z_vals = [], [], []
    for n in path_nodes:
        node = G_total.nodes[n]
        x_vals.append(node["x"])
        y_vals.append(node["y"])
        z_vals.append((node["floor"] - 1) * floor_gap)

    fig3.add_trace(go.Scatter3d(
        x=x_vals, y=y_vals, z=z_vals,
        mode="lines+markers",
        line=dict(color="lime", width=8),
        marker=dict(size=5, color="yellow"),
        name="Selected Route"
    ))

fig3.update_layout(
    scene=dict(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        zaxis=dict(title="Floor Level", tickvals=[i*floor_gap for i in range(len(floor_graphs))],
                   ticktext=[f"Floor {i+1}" for i in range(len(floor_graphs))]),
        aspectmode="manual",
        aspectratio=dict(x=1, y=1, z=0.6)
    ),
    height=800,
    margin=dict(l=0, r=0, t=30, b=0),
    showlegend=True
)
st.plotly_chart(fig3, use_container_width=True)

# =========================
# 2D Overview
# =========================
st.subheader("Floor-by-Floor Overview (Top-down)")
cols = st.columns(len(floor_graphs))
for i, fg in enumerate(floor_graphs):
    with cols[i]:
        st.markdown(f"**{fg['name']}**")
        fig, ax = plt.subplots(figsize=(3, 3))
        ax.imshow(fg["skel"], cmap="gray")
        ax.axis("off")
        st.pyplot(fig, use_container_width=True)
