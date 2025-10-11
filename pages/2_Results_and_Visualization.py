# pages/2_Results_and_Visualization.py
import streamlit as st
import pandas as pd
from aq_tool import draw_routes_on_image, link_floors

st.title("📈 Results and Visualization")

if "results" not in st.session_state or len(st.session_state.results) == 0:
    st.warning("No analysis found. Please go to the 'Upload and Analyze' page first.")
    st.stop()

# --- Combine metrics into one summary table ---
rows = []
for res in st.session_state.results:
    rows.append({
        "Floor": res["floor"],
        "AQ_S": round(res["AQ_S"], 4),
        "AQ_F": round(res["AQ_F"], 4),
        "Routes": len(res["routes"]),
        "Nodes": res["metrics"]["num_nodes"],
        "Edges": res["metrics"]["num_edges"],
    })

df = pd.DataFrame(rows)
st.subheader("Summary Metrics per Floor")
st.dataframe(df)

# --- Multi-floor combined visualization ---
st.subheader("Combined Multi-Floor Route Visualization")

try:
    G_total = link_floors(st.session_state.graphs)
    # Use the first skeleton just for background — purely visual
    fig = draw_routes_on_image(G_total, [], st.session_state.skeletons[0])
    st.pyplot(fig)
except Exception as e:
    st.error(f"Visualization failed: {e}")
