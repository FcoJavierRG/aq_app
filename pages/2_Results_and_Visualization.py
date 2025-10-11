# pages/2_📈_Results_and_Visualization.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

st.title("📈 Results and Visualization")

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

# Bar chart for AQ metrics per route
st.subheader("AQ Metrics per Route")
aq_df = pd.DataFrame({
    "Route": [r["route_id"]+1 for r in results["routes"]],
    "P_MF": [r["P_MF"] for r in results["routes"]],
    "1/(1+E_M)": [1.0/(1.0+r["E_M"]) for r in results["routes"]]
})
st.bar_chart(aq_df.set_index("Route"))

# ===========================
# Floor-by-Floor Visualization
# ===========================
st.subheader("Floor Skeletons with Routes and Decision Points")

floor_names = [fg["name"] for fg in floor_graphs]
selected_floor_idx = st.selectbox("Select floor", range(len(floor_graphs)), format_func=lambda i: floor_names[i])
fg = floor_graphs[selected_floor_idx]
G = fg["G"]

fig, ax = plt.subplots(figsize=(6,6))
ax.imshow(fg["skel"], cmap="gray")
ax.set_title(f"{fg['name']} Skeleton + Routes")
ax.axis("off")

# Overlay routes for this floor
colors = plt.cm.tab10.colors
for r_idx, route in enumerate(routes):
    # Filter nodes by floor
    floor_nodes = [n for n in route if G.nodes[n]["floor"] == selected_floor_idx + 1]
    if len(floor_nodes) < 2:
        continue
    yx = np.array([(G.nodes[n]["y"], G.nodes[n]["x"]) for n in floor_nodes])
    ax.plot(yx[:,1], yx[:,0], color=colors[r_idx % len(colors)], lw=2, label=f"Route {r_idx+1}")

    # Mark decision points (junctions and turns)
    route_info = results["routes"][r_idx]
    for dp in route_info["decision_points"]:
        dp_id = dp[0]
        if isinstance(dp_id, int) and dp_id in floor_nodes:
            ax.plot(G.nodes[dp_id]["x"], G.nodes[dp_id]["y"], 'ro', markersize=5)
        elif isinstance(dp_id, str) and "turn_" in dp_id:
            idx = int(dp_id.split("_")[1])
            if idx < len(floor_nodes):
                node = floor_nodes[idx]
                ax.plot(G.nodes[node]["x"], G.nodes[node]["y"], 'mo', markersize=5)  # magenta for turn

ax.legend()
st.pyplot(fig)

# ===========================
# Multi-Floor Combined View
# ===========================
if len(floor_graphs) > 1:
    st.subheader("Multi-Floor Connectivity Overview")
    fig2, ax2 = plt.subplots(figsize=(6,6))
    ax2.set_title("Merged Floors with Routes")
    ax2.axis("off")
    for idx, fg in enumerate(floor_graphs):
        skel = fg["skel"]
        alpha = 0.3 + 0.2*idx
        ax2.imshow(skel, cmap="gray", alpha=alpha)

    # Compose total graph safely
    from functools import reduce
    graphs_to_merge = [fg["G"] for fg in floor_graphs if "G" in fg and fg["G"] is not None]
    if graphs_to_merge:
        G_total = reduce(nx.compose, graphs_to_merge)
        # Overlay vertical edges
        for u,v,d in G_total.edges(data=True):
            if d.get("type") == "vertical":
                xu, yu = G_total.nodes[u]["x"], G_total.nodes[u]["y"]
                xv, yv = G_total.nodes[v]["x"], G_total.nodes[v]["y"]
                ax2.plot([xu,xv],[yu,yv], 'c--', lw=2)
    st.pyplot(fig2)
