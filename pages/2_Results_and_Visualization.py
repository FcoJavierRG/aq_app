import streamlit as st
import pandas as pd
import numpy as np
import networkx as nx
import plotly.graph_objects as go
from functools import reduce

st.title("📈 Results and Visualization (3D Multi-Floor)")

# ===========================
# Check for session data
# ===========================
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
st.json({
    "AQ_S": results["AQ_S"],
    "AQ_F": results["AQ_F"],
    "num_routes": len(routes)
})

# ===========================
# Per-Route Table
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
# 3D Multi-Floor Route Visualization (Enhanced + Route Selection)
# ============================================
st.subheader("Multi-Floor 3D Route Visualization")

floor_gap = 10  # vertical distance between floors
colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'cyan', 'magenta', 'lime']

# Let user choose which routes to show
all_route_labels = [f"Route {i+1}" for i in range(len(routes))]
selected_routes = st.multiselect(
    "Select routes to visualize",
    all_route_labels,
    default=all_route_labels[:5]  # show first 5 by default
)

# Initialize figure
fig3 = go.Figure()

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

# Get total graph
G_total = nx.compose_all([fg["G"] for fg in floor_graphs])

# Plot only selected routes
for r_idx, route in enumerate(routes):
    route_label = f"Route {r_idx+1}"
    if route_label not in selected_routes:
        continue

    x_vals, y_vals, z_vals = [], [], []

    for n in route:
        if n in G_total.nodes:
            node = G_total.nodes[n]
            x_vals.append(node["x"])
            y_vals.append(node["y"])
            z_vals.append((node["floor"] - 1) * floor_gap)

    if len(x_vals) > 1:
        color = colors[r_idx % len(colors)]
        fig3.add_trace(go.Scatter3d(
            x=x_vals,
            y=y_vals,
            z=z_vals,
            mode="lines+markers",
            line=dict(color=color, width=6),
            marker=dict(size=4),
            name=route_label
        ))

        # Add start and end points
        fig3.add_trace(go.Scatter3d(
            x=[x_vals[0]], y=[y_vals[0]], z=[z_vals[0]],
            mode="markers+text",
            marker=dict(color="blue", size=8, symbol="circle"),
            text="Start",
            textposition="top center",
            name=f"{route_label} Start",
            showlegend=False
        ))
        fig3.add_trace(go.Scatter3d(
            x=[x_vals[-1]], y=[y_vals[-1]], z=[z_vals[-1]],
            mode="markers+text",
            marker=dict(color="red", size=8, symbol="circle"),
            text="End",
            textposition="top center",
            name=f"{route_label} End",
            showlegend=False
        ))

# Highlight vertical edges in cyan
for u, v, d in G_total.edges(data=True):
    if d.get("type") == "vertical":
        xu, yu, zu = G_total.nodes[u]["x"], G_total.nodes[u]["y"], (G_total.nodes[u]["floor"] - 1) * floor_gap
        xv, yv, zv = G_total.nodes[v]["x"], G_total.nodes[v]["y"], (G_total.nodes[v]["floor"] - 1) * floor_gap
        fig3.add_trace(go.Scatter3d(
            x=[xu, xv],
            y=[yu, yv],
            z=[zu, zv],
            mode="lines",
            line=dict(color="cyan", width=6, dash="dot"),
            hovertext="Vertical Connection",
            name="Vertical Link",
            showlegend=False
        ))

fig3.update_layout(
    scene=dict(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        zaxis=dict(
            title="Floor",
            tickvals=[i * floor_gap for i in range(len(floor_graphs))],
            ticktext=[f"Floor {i+1}" for i in range(len(floor_graphs))]),
        aspectmode="data"
    ),
    height=800,
    margin=dict(l=0, r=0, t=30, b=0)
)

st.plotly_chart(fig3, use_container_width=True)

