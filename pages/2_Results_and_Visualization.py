# pages/2_📈_Results_and_Visualization.py
import streamlit as st
import pandas as pd
import numpy as np
import networkx as nx
import plotly.graph_objects as go
from functools import reduce

st.title("📈 Results and Visualization (Interactive)")

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
# Floor Selection
# ===========================
floor_names = [fg["name"] for fg in floor_graphs]
selected_floor_idx = st.selectbox("Select floor to visualize", range(len(floor_graphs)), format_func=lambda i: floor_names[i])
fg = floor_graphs[selected_floor_idx]
G = fg["G"]

# ===========================
# Interactive Plotly Skeleton + Routes
# ===========================
st.subheader(f"Floor: {fg['name']} - Skeleton & Routes")
fig = go.Figure()

# Skeleton as heatmap
skel_img = np.flipud(fg["skel"])  # flip for correct orientation
fig.add_trace(go.Heatmap(
    z=skel_img,
    colorscale="gray",
    showscale=False,
    hoverinfo="skip"
))

# Overlay routes
colors = px_colors = ['red','blue','green','orange','purple','brown','pink','cyan','magenta','lime']
for r_idx, route in enumerate(routes):
    floor_nodes = [n for n in route if G.nodes[n]["floor"] == selected_floor_idx+1]
    if len(floor_nodes) < 2:
        continue
    yx = np.array([[G.nodes[n]["y"], G.nodes[n]["x"]] for n in floor_nodes])
    fig.add_trace(go.Scatter(
        x=yx[:,1], y=np.flipud(yx[:,0]),  # flip y
        mode="lines+markers",
        line=dict(color=colors[r_idx % len(colors)], width=2),
        name=f"Route {r_idx+1}"
    ))

    # Decision points and turns
    route_info = results["routes"][r_idx]
    for dp in route_info["decision_points"]:
        dp_id = dp[0]
        if isinstance(dp_id, int) and dp_id in floor_nodes:
            fig.add_trace(go.Scatter(
                x=[G.nodes[dp_id]["x"]],
                y=[np.flipud(np.array([G.nodes[dp_id]["y"]]))[0]],
                mode="markers",
                marker=dict(color='red', size=8),
                name=f"Junction {r_idx+1}",
                showlegend=False
            ))
        elif isinstance(dp_id, str) and "turn_" in dp_id:
            idx = int(dp_id.split("_")[1])
            if idx < len(floor_nodes):
                node = floor_nodes[idx]
                fig.add_trace(go.Scatter(
                    x=[G.nodes[node]["x"]],
                    y=[np.flipud(np.array([G.nodes[node]["y"]]))[0]],
                    mode="markers",
                    marker=dict(color='magenta', size=8),
                    name=f"Turn {r_idx+1}",
                    showlegend=False
                ))

fig.update_layout(
    height=600,
    width=600,
    xaxis=dict(scaleanchor="y", showgrid=False, zeroline=False),
    yaxis=dict(showgrid=False, zeroline=False, autorange='reversed'),
    margin=dict(l=0,r=0,t=30,b=0)
)
st.plotly_chart(fig, use_container_width=True)

# ===========================
# Multi-Floor Overview
# ===========================
if len(floor_graphs) > 1:
    st.subheader("Multi-Floor Connectivity Overview")
    fig2 = go.Figure()
    for idx, fg in enumerate(floor_graphs):
        skel_img = np.flipud(fg["skel"])
        fig2.add_trace(go.Heatmap(
            z=skel_img,
            colorscale='gray',
            showscale=False,
            opacity=0.2 + 0.2*idx,
            hoverinfo="skip"
        ))
    # Compose total graph
    graphs_to_merge = [fg["G"] for fg in floor_graphs if "G" in fg and fg["G"] is not None]
    if graphs_to_merge:
        G_total = reduce(nx.compose, graphs_to_merge)
        for u,v,d in G_total.edges(data=True):
            if d.get("type") == "vertical":
                xu, yu = G_total.nodes[u]["x"], G_total.nodes[u]["y"]
                xv, yv = G_total.nodes[v]["x"], G_total.nodes[v]["y"]
                fig2.add_trace(go.Scatter(
                    x=[xu, xv],
                    y=[np.flipud(np.array([yu, yv]))[0]],
                    mode="lines",
                    line=dict(color='cyan', dash='dash', width=2),
                    name='Vertical Connection'
                ))

    fig2.update_layout(
        height=600,
        width=600,
        xaxis=dict(scaleanchor="y", showgrid=False, zeroline=False),
        yaxis=dict(showgrid=False, zeroline=False, autorange='reversed'),
        margin=dict(l=0,r=0,t=30,b=0)
    )
    st.plotly_chart(fig2, use_container_width=True)
