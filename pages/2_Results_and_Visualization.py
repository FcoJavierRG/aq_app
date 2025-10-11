import streamlit as st
import plotly.graph_objects as go
from functools import reduce
import numpy as np
import networkx as nx

st.title("📊 Multi-Floor 3D Route Visualization")

# Check session state
if "results" not in st.session_state:
    st.warning("No analysis found. Please upload floorplans first.")
    st.stop()

results = st.session_state["results"]
routes = st.session_state["routes"]
floor_graphs = st.session_state["floor_graphs"]

# ===========================
# 3D Figure
# ===========================
fig = go.Figure()

# Assign each floor a Z-level
floor_levels = {idx+1: idx*10 for idx in range(len(floor_graphs))}  # floors separated by 10 units

# Plot skeletons per floor as semi-transparent surface
for fg in floor_graphs:
    z = floor_levels[fg["name"].split()[-1]]  # floor number
    skel = fg["skel"]
    h, w = skel.shape
    # Only plot walkable areas
    ys, xs = np.where(skel > 0)
    zs = np.full_like(xs, z)
    fig.add_trace(go.Scatter3d(
        x=xs, y=ys, z=zs,
        mode='markers',
        marker=dict(size=2, color='lightgray', opacity=0.3),
        name=fg["name"]
    ))

# Plot routes spanning floors
colors = ['red','blue','green','orange','purple','brown','pink','cyan','magenta','lime']
for r_idx, route in enumerate(routes):
    xs, ys, zs = [], [], []
    for n in route:
        # Find which floor
        floor = next((idx+1 for idx, fg in enumerate(floor_graphs) if n in fg["G"].nodes), None)
        if floor is None:
            continue
        G = floor_graphs[floor-1]["G"]
        xs.append(G.nodes[n]["x"])
        ys.append(G.nodes[n]["y"])
        zs.append(floor_levels[floor])
    fig.add_trace(go.Scatter3d(
        x=xs, y=ys, z=zs,
        mode='lines+markers',
        line=dict(color=colors[r_idx % len(colors)], width=5),
        marker=dict(size=4),
        name=f"Route {r_idx+1}"
    ))

# Layout
fig.update_layout(
    scene=dict(
        xaxis=dict(title='X', visible=False),
        yaxis=dict(title='Y', visible=False),
        zaxis=dict(title='Floor', visible=True)
    ),
    height=700,
    margin=dict(l=0,r=0,t=30,b=0)
)

st.plotly_chart(fig, use_container_width=True)
