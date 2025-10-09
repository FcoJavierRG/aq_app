# aq_app

# Floor Plan Accessibility Analyzer (Access Quotient Tool)

This project implements an **automatic floor plan analysis tool** that computes the **Access Quotient (AQ)** of a building layout from a floor plan image.  
The tool extracts walkable routes, identifies junctions and turns, and quantifies the **navigational complexity and accessibility** of the layout.

It can be used as a **Jupyter Notebook**, a **standalone Python module**, or as a **web application** powered by [Streamlite](https://streamlit.io/).

---

## Features

- Automatically extracts walkable paths from a floor plan (PDF/PNG).
- Detects **branches**, **junctions**, and **turns** using graph analysis.
- Computes **Access Quotient (AQ)** metrics:
  - `AQ_S`: Simplified Accessibility Index  
  - `AQ_F`: Full Accessibility Index
- Displays a **graph overlay** on the floor plan.
- Generates a **summary table** of routes with metrics:
  - `P_MF`: Probability of correct movement  
  - `E_M`: Decision complexity  
  - Route length
- Works directly from images (e.g., floorplan.png).
- Ready for web deployment via **Streamlite**.

---

## System Requirements

- Python 3.9 or newer
- [Anaconda](https://www.anaconda.com/) (recommended)

---
