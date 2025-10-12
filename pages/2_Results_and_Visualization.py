import streamlit as st
import pandas as pd
import numpy as np
import networkx as nx
import plotly.graph_objects as go
from functools import reduce
import math

st.title("📈 Results and Visualization (Interactive Route Planner)")

if "results" not in st.session_state:
    st.warning("No analysis found. Please upload floorplans first.")
    st.stop()

results = st.session_state["results"]
routes = st.session_state["routes"]
floor_graphs = st.session_state["floor_graphs"]

# ===========================
# Summary Metrics
# ===========================
st.subheader("Overall Summary")
st.json({"AQ_S": results["AQ_S"], "AQ_F": results["AQ_F"], "num_routes": len(routes)})

# ===========================
# Per-Route Metrics Table
# ===========================
st.subheader("Per-Route Metrics")
rows = []
for r in results["routes"]:
    dp_str = ", ".join(f"{dp[0]}" for dp in r["decision_points"])
    rows.append({
        "Route": r["route_id"] + 1,
        "Turns": r["turns"],
        "Length_px": int(r["length"]),
        "P_MF": round(r["P_MF"], 3),
        "E_M": round(r["E_M"], 3),
        "DecisionPoints": dp_str
    })
df = pd.DataFrame(rows)
st.dataframe(df)

# ============================================
# 1️⃣ Unified Graph and 2D Interactive Node Picker
# ============================================
st.subheader("🎯 Select Start & End Points (2D Floor View)")

G_total = nx.compose_all([fg["G"] for fg in floor_graphs])
floor_names = [fg["name"] for fg in floor_graphs]
selected_floor_idx = st.selectbox("Select a floor to pick nodes", range(len(floor_graphs)), format_func=lambda i: floor_names[i])
fg = floor_graphs[selected_floor_idx]

# Plot 2D floor skeleton + all nodes
fig2d = go.Figure()
fig2d.add_trace(go.Heatmap(
    z=np.flipud(fg["skel"]),
    colorscale="gray",
    showscale=False,
    hoverinfo="skip"
))

# Overlay graph nodes
xs, ys = [G_total.nodes[n]["x"] for n in G_total.nodes], [G_total.nodes[n]["y"] for n in G_total.nodes]
fig2d.add_trace(go.Scatter(
    x=xs, y=[fg["skel"].shape[0] - y for y in ys],  # flip Y for correct orientation
    mode="markers",
    marker=dict(size=6, color="blue"),
    text=[f"Node {n}" for n in G_total.nodes],
    hoverinfo="text"
))

fig2d.update_layout(
    title="Click two nodes: Start & End",
    height=500,
    xaxis=dict(showgrid=False),
    yaxis=dict(showgrid=False, scaleanchor="x"),
    margin=dict(l=0, r=0, t=30, b=0)
)

click_data = st.plotly_chart(fig2d, use_container_width=True, on_click="rerun")

# Store clicks
if "clicks" not in st.session_state:
    st.session_state["clicks"] = []

if click_data and click_data.get("points"):
    point = click_data["points"][0]
    click_x, click_y = point["x"], fg["skel"].shape[0] - point["y"]
    nearest_node = min(G_total.nodes, key=lambda n: (G_total.nodes[n]["x"] - click_x) ** 2 + (G_total.nodes[n]["y"] - click_y) ** 2)
    st.session_state["clicks"].append(nearest_node)
    if len(st.session_state["clicks"]) > 2:
        st.session_state["clicks"] = st.session_state["clicks"][-2:]

if len(st.session_state["clicks"]) == 1:
    st.info(f"✅ Start node selected: Node {st.session_state['clicks'][0]}")
elif len(st.session_state["clicks"]) == 2:
    st.success(f"✅ Start: Node {st.session_state['clicks'][0]} | End: Node {st.session_state['clicks'][1]}")

# ============================================
# 2️⃣ Compute route if 2 nodes selected
# ============================================
path_nodes = []
if len(st.session_state["clicks"]) == 2:
    start_node, end_node = st.session_state["clicks"]
    try:
        path_nodes = nx.shortest_path(G_total, source=start_node, target=end_node, weight="weight")
        st.success(f"Found route with {len(path_nodes)} nodes between Node {start_node} and Node {end_node}")
    except nx.NetworkXNoPath:
        st.error("No valid path found between selected nodes.")

# ============================================
# 3️⃣ 3D Visualization
# ============================================
st.subheader("🌐 3D Visualization of Selected Route")

fig3 = go.Figure()
floor_gap = 10

# Add faint floor surfaces
for idx, fg in enumerate(floor_graphs):
    z_level = idx * floor_gap
    skel_img = np.flipud(fg["skel"])
    y_size, x_size = skel_img.shape
    y_coords, x_coords = np.mgrid[0:y_size, 0:x_size]
    fig3.add_trace(go.Surface(
        z=np.full_like(skel_img, z_level),
        x=x_coords, y=y_coords,
        surfacecolor=skel_img,
        colorscale="gray",
        showscale=False,
        opacity=0.2,
        name=f"Floor {idx+1}"
    ))

# Plot route
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

    # Start/end markers
    fig3.add_trace(go.Scatter3d(
        x=[x_vals[0]], y=[y_vals[0]], z=[z_vals[0]],
        mode="markers+text",
        marker=dict(color="blue", size=10),
        text="Start",
        textposition="top center",
        showlegend=False
    ))
    fig3.add_trace(go.Scatter3d(
        x=[x_vals[-1]], y=[y_vals[-1]], z=[z_vals[-1]],
        mode="markers+text",
        marker=dict(color="red", size=10),
        text="End",
        textposition="top center",
        showlegend=False
    ))

# Draw vertical connectors
for u, v, d in G_total.edges(data=True):
    if d.get("type") == "vertical":
        xu, yu, zu = G_total.nodes[u]["x"], G_total.nodes[u]["y"], (G_total.nodes[u]["floor"] - 1) * floor_gap
        xv, yv, zv = G_total.nodes[v]["x"], G_total.nodes[v]["y"], (G_total.nodes[v]["floor"] - 1) * floor_gap
        fig3.add_trace(go.Scatter3d(
            x=[xu, xv], y=[yu, yv], z=[zu, zv],
            mode="lines",
            line=dict(color="cyan", width=4, dash="dot"),
            hovertext="Vertical Connection",
            showlegend=False
        ))

fig3.update_layout(
    scene=dict(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        zaxis=dict(
            title="Floor",
            tickvals=[i * floor_gap for i in range(len(floor_graphs))],
            ticktext=[f"Floor {i+1}" for i in range(len(floor_graphs))]
        ),
        aspectmode="data"
    ),
    height=800,
    margin=dict(l=0, r=0, t=30, b=0)
)

st.plotly_chart(fig3, use_container_width=True)
