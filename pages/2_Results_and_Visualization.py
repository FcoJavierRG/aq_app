import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import cv2

st.title("Results and Visualization")

if "aq_results" not in st.session_state:
    st.warning("No results found. Please run analysis on the **Upload and Analyze** page first.")
    st.stop()

results = st.session_state["aq_results"]
routes = st.session_state["aq_routes"]
G = st.session_state["aq_graph"]
skel = st.session_state["aq_skel"]
input_path = st.session_state["input_path"]

st.subheader("Summary Metrics")
col1, col2 = st.columns(2)
with col1:
    st.json({"AQ_S": results["AQ_S"], "AQ_F": results["AQ_F"], "num_routes": len(routes)})
with col2:
    st.write("Per-route summary:")
    df = pd.DataFrame([
        {"Route": r["route_id"]+1, "P_MF": round(r["P_MF"],4), "E_M": round(r["E_M"],2),
         "Turns": r.get("turns",0), "Length_px": int(r.get("length",0))}
        for r in results["routes"]
    ])
    st.dataframe(df)

csv = df.to_csv(index=False)
st.download_button("Download Routes CSV", csv, "routes.csv", "text/csv")

# Visualization
st.subheader("Route Overlay Visualization")
fig, ax = plt.subplots(figsize=(8,8))
try:
    if input_path.lower().endswith(".pdf"):
        img = None
    else:
        img_bgr = cv2.imread(input_path)
        img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB) if img_bgr is not None else None
except Exception:
    img = None

if img is not None:
    ax.imshow(img, alpha=0.8)
if skel is not None:
    ax.imshow(skel, cmap="gray", alpha=0.6)

colors = ["cyan","lime","orange","magenta","brown","yellow","red","blue","purple","teal"]
for idx, route in enumerate(routes):
    xs = [G.nodes[n]["x"] for n in route]
    ys = [G.nodes[n]["y"] for n in route]
    ax.plot(xs, ys, color=colors[idx%len(colors)], linewidth=2, label=f"Route {idx+1}")
    ax.scatter([xs[0]],[ys[0]], color="green", marker="o", s=40)
    ax.scatter([xs[-1]],[ys[-1]], color="red", marker="x", s=40)

ax.axis("off")
ax.legend()
st.pyplot(fig)
