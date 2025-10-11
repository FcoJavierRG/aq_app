# pages/2_📈_Results_and_Visualization.py
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
        "P_MF": round(r["P_MF"],3),
        "E_M": round(r["E_M"],3),
        "DecisionPoints": dp_str
    })
df = pd.DataFrame(rows)
st.dataframe(df)

# ===========================
# Multi-Floor 3D Visualization
# ===========================
st.subheader("Multi-Floor 3D Route Visualization")

# Assign each floor a Z-level
floor_levels = {idx+1: idx*10 for idx in range(len(floor_graphs))}  # separation 10 units

fig = go.Figure()

# Skeleton points per floor
for idx, fg in enumerate(floor_graphs):
    z_level = floor_levels[idx+1]
    ys, xs = np.where(fg["skel"] > 0)
    zs = np.full_like(xs, z_level)
    fig.add_trace(go.Scatter3d(
        x=xs, y=ys, z=zs,
        mode='markers',
        marker=dict(size=2, color='lightgray', opacity=0.3),
        name=fg["name"]
    ))

# Routes across floors
colors = ['red','blue','green','orange','purple','brown','pink','cyan','magenta','lime']
for r_idx, route in enumerate(routes):
    xs, ys, zs = [], [], []
    for n in route:
        # Determine floor
        floor = next((i+1 for i, fg in enumerate(floor_graphs) if n in fg["G"].nodes), None)
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

# Junctions and Turns
for r_idx, route in enumerate(routes):
    route_info = results["routes"][r_idx]
    for dp in route_info["decision_points"]:
        dp_id = dp[0]
        # Junction
        if isinstance(dp_id, int):
            floor = next((i+1 for i, fg in enumerate(floor_graphs) if dp_id in fg["G"].nodes), None)
            if floor is None:
                continue
            G = floor_graphs[floor-1]["G"]
            fig.add_trace(go.Scatter3d(
                x=[G.nodes[dp_id]["x"]],
                y=[G.nodes[dp_id]["y"]],
                z=[floor_levels[floor]],
                mode='markers',
                marker=dict(color='red', size=6),
                name=f"Junction {r_idx+1}",
                showlegend=False,
                hovertemplate=f"Junction ID: {dp_id}<br>Floor: {floor}"
            ))
        # Turn
        elif isinstance(dp_id, str) and "turn_" in dp_id:
            idx = int(dp_id.split("_")[1])
            if idx < len(route):
                node = route[idx]
                floor = next((i+1 for i, fg in enumerate(floor_graphs) if node in fg["G"].nodes), None)
                if floor is None:
                    continue
                G = floor_graphs[floor-1]["G"]
                fig.add_trace(go.Scatter3d(
                    x=[G.nodes[node]["x"]],
                    y=[G.nodes[node]["y"]],
                    z=[floor_levels[floor]],
                    mode='markers',
                    marker=dict(color='magenta', size=6),
                    name=f"Turn {r_idx+1}",
                    showlegend=False,
                    hovertemplate=f"Turn Node: {node}<br>Floor: {floor}"
                ))

# Vertical connectors
graphs_to_merge = [fg["G"] for fg in floor_graphs if "G" in fg and fg["G"] is not None]
if graphs_to_merge:
    G_total = reduce(nx.compose, graphs_to_merge)
    for u,v,d in G_total.edges(data=True):
        if d.get("type") == "vertical":
            xu, yu = G_total.nodes[u]["x"], G_total.nodes[u]["y"]
            xv, yv = G_total.nodes[v]["x"], G_total.nodes[v]["y"]
            floor_u = G_total.nodes[u]["floor"]
            floor_v = G_total.nodes[v]["floor"]
            fig.add_trace(go.Scatter3d(
                x=[xu, xv],
                y=[yu, yv],
                z=[floor_levels[floor_u], floor_levels[floor_v]],
                mode='lines',
                line=dict(color='cyan', dash='dash', width=4),
                name='Vertical Connection',
                showlegend=True
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
