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

# ===========================
# Multi-Floor 3D Visualization (continuous routes)
# ===========================
st.subheader("Multi-Floor 3D Route Visualization")

# Z levels for floors
floor_levels = {idx + 1: idx * 10 for idx in range(len(floor_graphs))}

# Merge all floor graphs
graphs_to_merge = [fg["G"] for fg in floor_graphs if "G" in fg and fg["G"] is not None]
G_total = reduce(nx.compose, graphs_to_merge)

# Build figure
fig = go.Figure()

# Floor skeletons
for idx, fg in enumerate(floor_graphs):
    z_level = floor_levels[idx + 1]
    ys, xs = np.where(fg["skel"] > 0)
    zs = np.full_like(xs, z_level)
    fig.add_trace(go.Scatter3d(
        x=xs, y=ys, z=zs,
        mode='markers',
        marker=dict(size=2, color='lightgray', opacity=0.25),
        name=fg["name"],
        hoverinfo='skip'
    ))

# Route colors
colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'cyan', 'magenta', 'lime']

# Routes following actual edges
for r_idx, route in enumerate(routes):
    xs, ys, zs = [], [], []
    for i in range(len(route) - 1):
        u, v = route[i], route[i + 1]
        if u not in G_total.nodes or v not in G_total.nodes:
            continue
        floor_u, floor_v = G_total.nodes[u]["floor"], G_total.nodes[v]["floor"]
        xs.extend([G_total.nodes[u]["x"], G_total.nodes[v]["x"], None])
        ys.extend([G_total.nodes[u]["y"], G_total.nodes[v]["y"], None])
        zs.extend([floor_levels[floor_u], floor_levels[floor_v], None])
    fig.add_trace(go.Scatter3d(
        x=xs, y=ys, z=zs,
        mode='lines',
        line=dict(color=colors[r_idx % len(colors)], width=5),
        name=f"Route {r_idx + 1}",
        hoverinfo='text',
        text=[f"Route {r_idx+1}: Floor {G_total.nodes[v]['floor']}" for v in route[:-1]]
    ))

# Decision points and turns
for r_idx, route_info in enumerate(results["routes"]):
    for dp in route_info["decision_points"]:
        dp_id = dp[0]
        if dp_id not in G_total.nodes:
            continue
        floor = G_total.nodes[dp_id]["floor"]
        x, y = G_total.nodes[dp_id]["x"], G_total.nodes[dp_id]["y"]
        z = floor_levels[floor]
        color = 'red' if isinstance(dp_id, int) else 'magenta'
        fig.add_trace(go.Scatter3d(
            x=[x], y=[y], z=[z],
            mode='markers',
            marker=dict(color=color, size=6),
            hovertemplate=f"Node: {dp_id}<br>Floor: {floor}<extra></extra>",
            name=f"DP {dp_id}",
            showlegend=False
        ))

# Vertical connectors
for u, v, d in G_total.edges(data=True):
    if d.get("type") == "vertical":
        xu, yu = G_total.nodes[u]["x"], G_total.nodes[u]["y"]
        xv, yv = G_total.nodes[v]["x"], G_total.nodes[v]["y"]
        floor_u, floor_v = G_total.nodes[u]["floor"], G_total.nodes[v]["floor"]
        fig.add_trace(go.Scatter3d(
            x=[xu, xv],
            y=[yu, yv],
            z=[floor_levels[floor_u], floor_levels[floor_v]],
            mode='lines',
            line=dict(color='cyan', dash='dash', width=4),
            name='Vertical Connection',
            hoverinfo='skip',
            showlegend=False
        ))

# Layout and interactivity
fig.update_layout(
    scene=dict(
        xaxis=dict(title='', visible=False),
        yaxis=dict(title='', visible=False),
        zaxis=dict(title='Floor Level', visible=True),
        aspectmode='data'
    ),
    height=800,
    margin=dict(l=0, r=0, t=30, b=0),
    legend=dict(
        x=0.85, y=0.9,
        bgcolor='rgba(255,255,255,0.6)'
    )
)

st.plotly_chart(fig, use_container_width=True)
