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

# --- Fast Population Calculation ---
def get_pop_data(lat, lon, rad_km):
    if not os.path.exists(POP_FILE): return None
    try:
        deg_lat = rad_km / 111.0
        deg_lon = rad_km / (111.0 * math.cos(math.radians(lat)))
        left, bottom, right, top = (lon - deg_lon, lat - deg_lat, lon + deg_lon, lat + deg_lat)
        
        with rasterio.open(POP_FILE) as ds:
            window = from_bounds(left, bottom, right, top, ds.transform)
            data = ds.read(1, window=window, boundless=True, fill_value=0)
            return int(np.nansum(data[data > 0]))
    except: return 0

@st.cache_data(show_spinner=False)
def load_excel_data():
    try:
        df = pd.read_excel(EXCEL_FILE)
        df.columns = df.columns.str.strip()
        id_col = [col for col in df.columns if 'ID' in col.upper() or 'CODE' in col.upper()][0]
        df['search_id'] = df[id_col].astype(str)
        # Sirf zaroori columns rakhein taake memory bache
        return df[['School', 'lat', 'lon', 'search_id', 'Status', 'Operational Utilization', 'Girls %', 'Boys %']]
    except: return None

# --- Session State ---
if 'center' not in st.session_state: st.session_state.center = [30.3753, 69.3451]
if 'zoom' not in st.session_state: st.session_state.zoom = 6

# --- Sidebar ---
st.sidebar.title("🏗️ TCF Engineering")
data = load_excel_data()
selected_row = None

# Search Logic
if data is not None:
    search_mode = st.sidebar.radio("Search by:", ["All Schools", "School Name", "School ID"])
    if search_mode == "School Name":
        name = st.sidebar.selectbox("School Name:", ["Select..."] + sorted(data['School'].astype(str).unique().tolist()))
        if name != "Select...":
            selected_row = data[data['School'] == name].iloc[0]
            st.session_state.center = [selected_row['lat'], selected_row['lon']]
            st.session_state.zoom = 17
    elif search_mode == "School ID":
        id_s = st.sidebar.selectbox("School ID:", ["Select..."] + sorted(data['search_id'].unique().tolist()))
        if id_s != "Select...":
            selected_row = data[data['search_id'] == id_s].iloc[0]
            st.session_state.center = [selected_row['lat'], selected_row['lon']]
            st.session_state.zoom = 17

st.sidebar.markdown("---")
radius = st.sidebar.slider("Radius (KM)", 0.5, 20.0, 2.0, 0.5)

# Calculate Population (Sirf Sidebar mein update hoga)
pop = get_pop_data(st.session_state.center[0], st.session_state.center[1], radius)
if pop is not None:
    st.sidebar.metric("📊 Total Population", f"{pop:,}")

# --- Map Setup ---
m = folium.Map(location=st.session_state.center, zoom_start=st.session_state.zoom, 
               tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google')

folium.Circle(st.session_state.center, radius=radius*1000, color='red', fill=True, fill_opacity=0.1).add_to(m)

marker_cluster = MarkerCluster(name="TCF Clusters", disableClusteringAtZoom=16).add_to(m)

if data is not None:
    for _, row in data.iterrows():
        p_html = f"""
        <div style="font-family: Arial; width: 200px; font-size: 12px;">
            <b style="color: #007BFF;">{row['School']}</b><br>
            ID: {row['search_id']}<br>
            Status: {row['Status']}<br>
            Util: {row['Operational Utilization']}<br>
            G: {row['Girls %']}% | B: {row['Boys %']}%
        </div>"""
        is_sel = selected_row is not None and str(row['search_id']) == str(selected_row['search_id'])
        folium.Marker(
            location=[row['lat'], row['lon']],
            popup=folium.Popup(p_html, max_width=250),
            icon=folium.Icon(color='red' if is_sel else 'green', icon='info-sign' if not is_sel else 'star')
        ).add_to(marker_cluster if not is_sel else m)

# Display Map
out = st_folium(m, width=1200, height=700, key="map_v8", use_container_width=True)

# Update State without Rerun unless necessary
if out:
    if out.get("center") and out["center"] != {"lat": st.session_state.center[0], "lng": st.session_state.center[1]}:
        st.session_state.center = [out["center"]["lat"], out["center"]["lng"]]
    if out.get("zoom") and out["zoom"] != st.session_state.zoom:
        st.session_state.zoom = out["zoom"]
    if out.get("last_clicked"):
        new_p = [out["last_clicked"]["lat"], out["last_clicked"]["lng"]]
        if new_p != st.session_state.center:
            st.session_state.center = new_p
            st.rerun()
