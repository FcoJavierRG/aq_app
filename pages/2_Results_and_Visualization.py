import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import networkx as nx
from aq_tool import load_image_any

st.set_page_config(layout="wide")
st.title("Results and Visualization")

# Check if any analysis has been run
if "aq_graph" not in st.session_state:
    st.warning("No results found. Please run an analysis on the 'Upload and Analyze' page first.")
    st.stop()

# --- Helper function to display results for a given route set ---
def display_results(results_key, routes_key, title):
    if results_key not in st.session_state or not st.session_state[results_key]:
        st.info(f"No {title.lower()} found to display. Please define and analyze routes on the 'Upload and Analyze' page.")
        return

    results = st.session_state[results_key]
    routes = st.session_state[routes_key]
    G = st.session_state["aq_graph"]
    skel = st.session_state["aq_skel"]
    input_path = st.session_state["input_path"]

    st.header(title)
    
    # --- 1. Summary Metrics ---
    st.subheader("Summary Metrics")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("Strict AccessQuotient (AQ_S)", f"{results['AQ_S']:.4f}")
        st.metric("Flexible AccessQuotient (AQ_F)", f"{results['AQ_F']:.4f}")
        st.metric("Number of Routes Analyzed", len(routes))

    with col2:
        df_rows = []
        for r in results["routes"]:
            df_rows.append({
                "Route": r["route_id"] + 1,
                "P_MF (Mistake-Free Prob.)": f"{r['P_MF']:.4f}",
                "E_M (Expected Mistakes)": f"{r['E_M']:.2f}",
                "Turns": r.get("turns", 0),
                "Junctions": len([dp for dp in r.get('decision_points', []) if dp.get('type') == 'junction']),
                "Length (px)": int(r.get("length", 0))
            })
        df = pd.DataFrame(df_rows)
        st.dataframe(df)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Route Details as CSV",
            data=csv,
            file_name=f"{title.lower().replace(' ','_')}_routes.csv",
            mime='text/csv',
        )

    # --- 2. Visualization ---
    st.subheader("Route Visualization")
    
    # Create a figure for the plot
    fig, ax = plt.subplots(figsize=(10, 10))
    img = (skel * 255).astype("uint8")
    ax.imshow(cv2.cvtColor(img, cv2.COLOR_GRAY2RGB))

    # Define a color map
    colors = cm.get_cmap("tab10", max(10, len(routes)))

    for idx, route in enumerate(routes):
        # Get path coordinates
        path_coords = []
        for i in range(len(route) - 1):
            u, v = route[i], route[i+1]
            if G.has_edge(u,v):
                 # Correctly orient and append path segments
                segment = G.edges[u,v].get('path', [])
                if not path_coords or path_coords[-1] == segment[0]:
                    path_coords.extend(segment if not path_coords else segment[1:])
                else:
                    path_coords.extend(list(reversed(segment))[1:])
        
        if path_coords:
            xs, ys = zip(*[(p[1], p[0]) for p in path_coords])
            ax.plot(xs, ys, color=colors(idx), linewidth=2.5, label=f"Route {idx+1}")
            
            # Mark start & end points
            start_node_id = route[0]
            end_node_id = route[-1]
            ax.scatter(xs[0], ys[0], c="lime", s=80, marker="o", zorder=5, edgecolors='black', label=f"Start (Node {start_node_id})")
            ax.scatter(xs[-1], ys[-1], c="red", s=100, marker="X", zorder=5, edgecolors='black', label=f"End (Node {end_node_id})")

    ax.set_title(f"{title} on Floorplan Skeleton")
    ax.axis("off")
    # Consolidate legend to avoid duplicate labels
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys())
    
    st.pyplot(fig)


# --- Main page logic ---
# Use tabs to switch between Automatic and Custom results
tab1, tab2 = st.tabs(["Automatic Route Analysis", "Custom Route Analysis"])

with tab1:
    display_results("auto_results", "auto_routes", "Automatic Routes")

with tab2:
    display_results("custom_results", "custom_routes", "Custom Routes")

