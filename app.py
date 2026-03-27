import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
import rasterio
from rasterio.windows import from_bounds
import math
import numpy as np
import os

# 1. Page Layout
st.set_page_config(page_title="TCF Engineering Map", layout="wide")

EXCEL_FILE = "SSR_Final_Fixed.xlsx"
POP_FILE = "pak_total_Pop FN.tif"

# --- Population Calculation ---
def get_pop_data(lat, lon, rad_km):
    deg_lat = rad_km / 111.0
    deg_lon = rad_km / (111.0 * math.cos(math.radians(lat)))
    left, bottom, right, top = (lon - deg_lon, lat - deg_lat, lon + deg_lon, lat + deg_lat)
    try:
        if not os.path.exists(POP_FILE): return None
        with rasterio.open(POP_FILE) as ds:
            window = from_bounds(left, bottom, right, top, ds.transform)
            data = ds.read(1, window=window)
            return int(np.nansum(data[data > 0]))
    except: return None

@st.cache_data
def load_excel_data():
    try:
        df = pd.read_excel(EXCEL_FILE)
        df.columns = df.columns.str.strip()
        id_col = [col for col in df.columns if 'ID' in col.upper() or 'CODE' in col.upper()][0]
        df['search_id'] = df[id_col].astype(str)
        return df
    except: return None

# --- Session State (Map Persistence) ---
if 'center' not in st.session_state:
    st.session_state.center = [30.3753, 69.3451]
if 'zoom' not in st.session_state:
    st.session_state.zoom = 6

# --- Sidebar ---
st.sidebar.title("🏗️ TCF Engineering")
data = load_excel_data()
selected_row = None

if data is not None:
    st.sidebar.subheader("🔍 Search Schools")
    search_mode = st.sidebar.radio("Search by:", ["All Schools", "School Name", "School ID"])
    
    if search_mode == "School Name":
        name = st.sidebar.selectbox("School Name:", ["Select..."] + sorted(data['School'].dropna().unique().tolist()))
        if name != "Select...":
            selected_row = data[data['School'] == name].iloc[0]
            st.session_state.center = [selected_row['lat'], selected_row['lon']]
            st.session_state.zoom = 17
            
    elif search_mode == "School ID":
        id_s = st.sidebar.selectbox("School ID:", ["Select..."] + sorted(data['search_id'].dropna().unique().tolist()))
        if id_s != "Select...":
            selected_row = data[data['search_id'] == id_s].iloc[0]
            st.session_state.center = [selected_row['lat'], selected_row['lon']]
            st.session_state.zoom = 17

st.sidebar.markdown("---")
radius = st.sidebar.number_input("Radius (KM)", min_value=0.1, max_value=50.0, value=2.0, step=0.5)

# Calculate Population
total_pop = get_pop_data(st.session_state.center[0], st.session_state.center[1], radius)
if total_pop is not None:
    st.sidebar.metric("📊 Total Population", f"{total_pop:,}")

# --- Map Setup ---
st.title("🇵🇰 TCF Schools & Population Map")

m = folium.Map(
    location=st.session_state.center, 
    zoom_start=st.session_state.zoom, 
    tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
    attr='Google'
)

# Radius Circle
folium.Circle(
    st.session_state.center, radius=radius*1000, 
    color='red', fill=True, fill_opacity=0.15
).add_to(m)

marker_cluster = MarkerCluster(name="TCF Clusters").add_to(m)

if data is not None:
    for _, row in data.iterrows():
        if pd.notnull(row['lat']) and pd.notnull(row['lon']):
            # Full Popup Data Restored
            p_html = f"""
            <div style="font-family: Arial; width: 220px; font-size: 13px;">
                <h4 style="margin-bottom:5px; color: #007BFF;">{row['School']}</h4>
                <b>ID:</b> {row['search_id']}<br>
                <b>Status:</b> {row.get('Status', 'N/A')}<br>
                <b>Utilization:</b> {row.get('Operational Utilization', 'N/A')}<br>
                <hr style="margin: 5px 0;">
                <span style="color: #e91e63;"><b>Girls:</b> {row.get('Girls %', '0')}%</span> | 
                <span style="color: #2196f3;"><b>Boys:</b> {row.get('Boys %', '0')}%</span>
            </div>
            """
            is_sel = selected_row is not None and str(row['search_id']) == str(selected_row['search_id'])
            folium.Marker(
                location=[row['lat'], row['lon']],
                popup=folium.Popup(p_html, max_width=300),
                tooltip=row['School'],
                icon=folium.Icon(color='red' if is_sel else 'green', icon='star' if is_sel else 'info-sign')
            ).add_to(marker_cluster if not is_sel else m)

# st_folium with state management
out = st_folium(m, width=1350, height=750, key="main_map")

# Capture center/zoom changes to prevent restore
if out:
    if out.get("center"):
        st.session_state.center = [out["center"]["lat"], out["center"]["lng"]]
    if out.get("zoom"):
        st.session_state.zoom = out["zoom"]
    if out.get("last_clicked"):
        new_p = [out["last_clicked"]["lat"], out["last_clicked"]["lng"]]
        if new_p != st.session_state.center:
            st.session_state.center = new_p
            st.rerun()
