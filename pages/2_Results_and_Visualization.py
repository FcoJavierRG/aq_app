# pages/2_Results_and_Visualization.py
import streamlit as st
import pandas as pd

st.title("Results and Visualization")

if "floors" not in st.session_state or not st.session_state["floors"]:
    st.warning("No data available. Please analyze floorplans first.")
else:
    rows = []
    for data in st.session_state["floors"]:
        rows.append({
            "Floor": data["floor"],
            "AQ_S": round(data["results"]["AQ_S"], 4),
            "AQ_F": round(data["results"]["AQ_F"], 4),
            "Num Routes": len(data["results"]["routes"]),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df)

    combined_AQ = df["AQ_S"].mean()
    st.success(f"Combined Multi-Floor AQ_S: **{combined_AQ:.3f}**")

    st.markdown("### Individual Route Details")
    for floor_data in st.session_state["floors"]:
        st.markdown(f"#### Floor {floor_data['floor']}")
        for r in floor_data["results"]["routes"]:
            st.write(r)

