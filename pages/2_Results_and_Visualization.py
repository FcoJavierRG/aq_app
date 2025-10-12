import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import cv2
import aq_tool

st.set_page_config(page_title="Results", layout="wide")
st.title("2. Results and Visualization")

def display_results(results_key, routes_key, title):
    if results_key not in st.session_state or not st.session_state[results_key]['routes']:
        st.info(f"No {title.lower()} have been analyzed yet.")
        return

    results = st.session_state[results_key]
    routes = st.session_state[routes_key]
    G = st.session_state["aq_graph"]
    skel = st.session_state["aq_skel"]
    
    st.header(title)

    # --- Summary Metrics ---
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Summary Metrics")
        st.json({
            "Strict AQ (AQ_S)": f"{results['AQ_S']:.4f}",
            "Flexible AQ (AQ_F)": f"{results['AQ_F']:.4f}",
            "Routes Analyzed": len(routes)
        })

    # --- Per-Route Details ---
    with col2:
        st.subheader("Per-Route Details")
        route_data = []
        for r in results["routes"]:
            route_data.append({
                "Route": r["route_id"] + 1,
                "P_MF (Mistake-Free Prob.)": f"{r['P_MF']:.4f}",
                "E_M (Expected Mistakes)": f"{r['E_M']:.2f}",
                "Junctions": r.get("junctions", 0),
                "Length (px)": f"{r.get('length', 0):.0f}"
            })
        
        df = pd.DataFrame(route_data)
        st.dataframe(df)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Route Data (CSV)", csv, f"{title.lower().replace(' ','_')}_routes.csv", "text/csv")

    # --- Visualization ---
    st.subheader("Route Visualization")
    
    # Use skeleton as the base for plotting routes
    img_rgb = cv2.cvtColor((skel * 255).astype("uint8"), cv2.COLOR_GRAY2RGB)
    
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.imshow(img_rgb)

    colors = plt.cm.get_cmap("tab10", len(routes))
    for idx, route in enumerate(routes):
        # Reconstruct the full pixel path for smooth plotting
        pixel_path = aq_tool._get_full_pixel_path(G, route)
        if not pixel_path: continue
        
        xs, ys = zip(*pixel_path) # Switch from (row, col) to (x, y)
        ax.plot(ys, xs, color=colors(idx), linewidth=2.5, label=f"Route {idx+1}")
        
        # Mark start and end points
        start_node_pos = G.nodes[route[0]]['pos']
        end_node_pos = G.nodes[route[-1]]['pos']
        ax.scatter(start_node_pos[1], start_node_pos[0], c="lime", s=80, marker="o", zorder=5, edgecolors='black', label=f"Start {idx+1}")
        ax.scatter(end_node_pos[1], end_node_pos[0], c="red", s=100, marker="X", zorder=5, edgecolors='black', label=f"End {idx+1}")

    ax.axis("off")
    # Consolidate legend
    handles, labels = ax.get_legend_handles_labels()
    unique_labels = {}
    for handle, label in zip(handles, labels):
        if "Route" in label and label not in unique_labels:
            unique_labels[label] = handle
        elif "Start" in label and "Start" not in unique_labels:
            unique_labels["Start"] = handle
        elif "End" in label and "End" not in unique_labels:
             unique_labels["End"] = handle
    
    ax.legend(unique_labels.values(), unique_labels.keys(), loc="upper right")
    
    st.pyplot(fig)


# --- Main Logic ---
if "aq_graph" not in st.session_state:
    st.warning("No floorplan has been analyzed. Please go to the 'Upload and Analyze' page first.")
    st.stop()

# Display results for both automatic and custom routes if they exist
display_results("auto_results", "auto_routes", "Automatic Routes")
st.markdown("---")
display_results("custom_results", "custom_routes", "Manually Selected Routes")

