# pages/2_Results_and_Visualization.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.title("Results and Visualization")

if "results" not in st.session_state:
    st.warning("No analysis found. Please upload floorplans first.")
    st.stop()

results = st.session_state["results"]
routes = st.session_state["routes"]
floor_graphs = st.session_state["floor_graphs"]

st.subheader("Summary Metrics")
st.json({"AQ_S": results["AQ_S"], "AQ_F": results["AQ_F"], "num_routes": len(routes)})

rows = []
for r in results["routes"]:
    dp_str = ", ".join(f"{dp[0]}" for dp in r["decision_points"])
    rows.append({
        "Route": r["route_id"] + 1,
        "Turns": r["turns"],
        "Length_px": int(r["length"]),
        "DecisionPoints": dp_str
    })
df = pd.DataFrame(rows)
st.dataframe(df)

# Visualization per floor
st.subheader("Floor-by-Floor Skeletons")
cols = st.columns(len(floor_graphs))
for i, fg in enumerate(floor_graphs):
    with cols[i]:
        fig, ax = plt.subplots(figsize=(4, 4))
        ax.imshow(fg["skel"], cmap="gray")
        ax.set_title(fg["name"])
        ax.axis("off")
        st.pyplot(fig, use_container_width=True)
