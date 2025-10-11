# pages/1_Upload_and_Analyze.py
import streamlit as st
import tempfile, os, json
import pandas as pd
import matplotlib.pyplot as plt
import cv2
import importlib

import aq_tool
importlib.reload(aq_tool)
from aq_tool import (
    run_aq_pipeline,
    extract_routes,
    compute_access_quotient,
    link_floors,
    draw_routes_on_image
)

st.title("Upload and Analyze Floor Plans")

st.markdown("""
Upload one or multiple **floor plan images (JPG, PNG, or PDF)** to extract walkable routes, 
detect turns, and compute the **Access Quotient (AQ)** — a measure of spatial accessibility.
""")

# --- Sidebar parameters ---
st.sidebar.header("Parameters")
px_per_meter = st.sidebar.number_input("px_per_meter (approx)", value=50.0, min_value=1.0)
max_routes = st.sidebar.slider("max_routes", 1, 10, 5)
min_branch_len = st.sidebar.slider("min_branch_len (px)", 1, 200, 10)
angle_thresh_deg = st.sidebar.slider("angle_thresh_deg", 5, 90, 30)
min_turn_len_px = st.sidebar.slider("min_turn_len_px", 1, 20, 3)

uploaded_files = st.file_uploader(
    "Upload one or more floorplans (png, jpg, jpeg, pdf)", 
    type=["png", "jpg", "jpeg", "pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    floor_graphs = []
    results_all = []

    for i, uploaded in enumerate(uploaded_files):
        floor_name = f"Floor {i+1}"
        st.markdown(f"### {floor_name}")

        suffix = os.path.splitext(uploaded.name)[1]
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(uploaded.getvalue())
        tmp.flush()
        tmp.close()
        fpath = tmp.name

        st.info(f"Processing {floor_name}...")
        with st.spinner("Running AQ pipeline..."):
            try:
                metrics, G, skel = run_aq_pipeline(
                    fpath,
                    px_per_meter=px_per_meter,
                    return_skeleton=True
                )
            except Exception as e:
                st.error(f"Pipeline failed for {floor_name}: {e}")
                continue

        # Store per-floor graph
        floor_graphs.append(G)

        # Extract and analyze routes
        routes, weights = extract_routes(G, max_routes=max_routes)
        results = compute_access_quotient(
            G, routes, weights,
            min_branch_len=min_branch_len,
            angle_thresh_deg=angle_thresh_deg,
            min_turn_len_px=min_turn_len_px
        )
        results_all.append(results)

        # ---- Table ----
        st.write(f"**Summary for {floor_name}:**")
        st.json({
            "AQ_S": results["AQ_S"],
            "AQ_F": results["AQ_F"],
            "num_routes": len(routes),
            "num_nodes": metrics["num_nodes"],
            "num_edges": metrics["num_edges"]
        })

        # Build routes dataframe
        rows = []
        for r in results["routes"]:
            dp_text = ", ".join(f"{dp[0]}" for dp in r["decision_points"])
            rows.append({
                "Route": r["route_id"] + 1,
                "P_MF": round(r["P_MF"], 4),
                "E_M": round(r["E_M"], 2),
                "Turns": r.get("turns", 0),
                "Length_px": int(r.get("length", 0)),
                "DecisionPoints": dp_text
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            st.dataframe(df)

        # ---- Visualization ----
        st.write(f"**Visualization — {floor_name}**")
        try:
            img_bgr = cv2.imread(fpath, cv2.IMREAD_COLOR)
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB) if img_bgr is not None else None
        except Exception:
            img_rgb = None

        fig = draw_routes_on_image(G, routes, skel, img_rgb)
        st.pyplot(fig, use_container_width=True)

        # Clean up
        os.remove(fpath)

    # --- Combine multi-floor graphs ---
    if len(floor_graphs) > 1:
        st.markdown("##  Multi-floor Combined Network")
        G_total = link_floors(floor_graphs)
        st.success(f"Combined {len(floor_graphs)} floors into unified 3D navigation graph.")
        st.write(f"Total nodes: {G_total.number_of_nodes()}, Total edges: {G_total.number_of_edges()}")

        # Display overall AQ summary
        total_AQ_S = sum(r["AQ_S"] for r in results_all) / len(results_all)
        total_AQ_F = sum(r["AQ_F"] for r in results_all) / len(results_all)
        st.json({"Overall_AQ_S": total_AQ_S, "Overall_AQ_F": total_AQ_F})

else:
    st.info(" Upload one or more floor plans to begin.")

