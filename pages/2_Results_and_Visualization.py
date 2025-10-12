# pages/2_📈_Results_and_Visualization.py
import streamlit as st
import pandas as pd
import numpy as np
import networkx as nx
import plotly.graph_objects as go
from streamlit_plotly_events import plotly_events
from functools import reduce

st.title("📈 Results and Visualization (Interactive Multi-Floor AQ Analyzer)")

# =========================
# Load results from session
# =========================
if "results" not in st.session_state:
    st.warning("No analysis found. Please upload floorplans first.")
    st.stop()

results = st.session_state["results"]
routes = st.session_state["routes"]
floor_graphs = st.session_state["floor_graphs"]

# =========================
# Summary
# =========================
st.subheader("Summary Metrics")
st.json({
    "AQ_S": results["AQ_S"],
    "AQ_F": results["AQ_F"],
    "num_routes": len(routes)
})

# =========================
# Per-route metrics table
# =========================
st.subheader("Per-Route Metrics")
rows = []
for r in results["routes"]:
    dp_str = ", ".join(f"{dp[0]}" for dp in r["decision_points"])
    rows.append({
        "Route": r["route_id"] + 1,
        "Turns": r["turns"],
        "Length_px": int(r["length"]),
        "P_MF": round(r.get("P_MF", 0), 3),
        "E_M": round(r.get("E_M", 0), 3),
        "DecisionPoints": dp_str
    })
df = pd.DataFrame(rows)
st.dataframe(df)

# =========================
# 2D Floor Viewer (for node selection)
# =========================
st.subheader("🖱️ Click on the map to select Start and End nodes")

floor_names = [fg["name"] for fg in floor_graphs]
selected_floor_idx = st.selectbox(
    "Select floor to click on",
    range(len(floor_graphs)),
    format_func=lambda i: floor_names[i]
)

fg = floor_graphs[selected_floor_idx]
G = fg["G"]

# Create 2D floor skeleton image
fig2d = go.Figure()
skel_img = np.flipud(fg["skel"])
fig2d.add_trace(go.Heatmap(z=skel_img, colorscale="gray", showscale=False))

# Plot all nodes
x_nodes = [G.nodes[n]["x"] for n in G.nodes]
y_nodes = [G.nodes[n]["y"] for n in G.nodes]
fig2d.add_trace(go.Scatter(
    x=x_nodes,
    y=[skel_img.shape[0] - y for y in y_nodes],
    mode="markers",
    marker=dict(size=6, color="cyan"),
    name="Nodes"
))

fig2d.update_layout(
    height=500,
    width=500,
    margin=dict(l=0, r=0, t=30, b=0),
    xaxis=dict(visible=False),
    yaxis=dict(visible=False)
)

# Capture click data using streamlit-plotly-events
click_result = plotly_events(fig2d, click_event=True, hover_event=False, select_event=False, key="floor_click")

# Handle clicks to pick nodes
if "clicks" not in st.session_state:
    st.session_state["clicks"] = []

# Merge all graphs to a single one for path search
G_total = reduce(nx.compose, [fg["G"] for fg in floor_graphs])

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

if len(st.session_state["clicks"]) == 1:
    st.info(f"Start node selected: {st.session_state['clicks'][0]}")
elif len(st.session_state["clicks"]) == 2:
    st.success(f"Start: {st.session_state['clicks'][0]}, End: {st.session_state['clicks'][1]}")

# =========================
# Compute and visualize path
# =========================
path_nodes = []
if len(st.session_state["clicks"]) == 2:
    start_node, end_node = st.session_state["clicks"]
    try:
        path_nodes = nx.shortest_path(G_total, source=start_node, target=end_node, weight='weight')
        st.success(f"Found path with {len(path_nodes)} nodes from {start_node} → {end_node}")
    except nx.NetworkXNoPath:
        st.error("No valid path found between selected nodes.")

# =========================
# 3D Visualization
# =========================
st.subheader("🌐 3D Multi-Floor Visualization (Enhanced)")

fig3 = go.Figure()
floor_gap = 15  # increased spacing for clarity

# Distinct color map for each floor
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

# Highlight the selected route (if any)
if path_nodes:
    x_vals, y_vals, z_vals = [], [], []
    for n in path_nodes:
        node = G_total.nodes[n]
        x_vals.append(node["x"])
        y_vals.append(node["y"])
        z_vals.append((node["floor"] - 1) * floor_gap)

    fig3.add_trace(go.Scatter3d(
        x=x_vals,
        y=y_vals,
        z=z_vals,
        mode="lines+markers",
        line=dict(color="lime", width=8),
        marker=dict(size=5, color="yellow"),
        name="Selected Route"
    ))

    # Start and End markers
    fig3.add_trace(go.Scatter3d(
        x=[x_vals[0]], y=[y_vals[0]], z=[z_vals[0]],
        mode="markers+text",
        marker=dict(color="blue", size=12),
        text="Start",
        textposition="top center",
        showlegend=False
    ))
    fig3.add_trace(go.Scatter3d(
        x=[x_vals[-1]], y=[y_vals[-1]], z=[z_vals[-1]],
        mode="markers+text",
        marker=dict(color="red", size=12),
        text="End",
        textposition="top center",
        showlegend=False
    ))

# Add vertical connectors (cyan dashed lines)
for u, v, d in G_total.edges(data=True):
    if d.get("type") == "vertical":
        xu, yu, zu = G_total.nodes[u]["x"], G_total.nodes[u]["y"], (G_total.nodes[u]["floor"] - 1) * floor_gap
        xv, yv, zv = G_total.nodes[v]["x"], G_total.nodes[v]["y"], (G_total.nodes[v]["floor"] - 1) * floor_gap
        fig3.add_trace(go.Scatter3d(
            x=[xu, xv],
            y=[yu, yv],
            z=[zu, zv],
            mode="lines",
            line=dict(color="cyan", width=5, dash="dot"),
            hovertext="Vertical Connection",
            showlegend=False
        ))

fig3.update_layout(
    scene=dict(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        zaxis=dict(
            title="Floor Level",
            tickvals=[i * floor_gap for i in range(len(floor_graphs))],
            ticktext=[f"Floor {i+1}" for i in range(len(floor_graphs))],
            showgrid=True
        ),
        aspectmode="manual",
        aspectratio=dict(x=1, y=1, z=0.6)
    ),
    height=800,
    margin=dict(l=0, r=0, t=30, b=0),
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5)
)

st.plotly_chart(fig3, use_container_width=True)

# =========================
# Side-by-side 2D Overview of All Floors
# =========================
st.subheader("🏢 Floor-by-Floor Overview (Top-down)")

cols = st.columns(len(floor_graphs))
for i, fg in enumerate(floor_graphs):
    with cols[i]:
        st.markdown(f"**{fg['name']}**")
        fig, ax = plt.subplots(figsize=(3, 3))
        ax.imshow(fg["skel"], cmap="gray")
        ax.axis("off")
        st.pyplot(fig, use_container_width=True)
