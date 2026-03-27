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

# --- Page Config ---
st.set_page_config(page_title="TCF Engineering Map", layout="wide")

EXCEL_FILE = "SSR_Final_Fixed.xlsx"
POP_FILE = "pak_total_Pop FN.tif"

# --- Population Logic (Cached for Speed) ---
@st.cache_data
def get_pop_data(lat, lon, rad_km):
    if not os.path.exists(POP_FILE): return 0
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
def load_data():
    try:
        df = pd.read_excel(EXCEL_FILE)
        df.columns = df.columns.str.strip()
        id_cols = [col for col in df.columns if 'ID' in col.upper() or 'CODE' in col.upper()]
        id_col = id_cols[0] if id_cols else df.columns[0]
        df['search_id'] = df[id_col].astype(str)
        return df.dropna(subset=['lat', 'lon'])
    except: return None

# --- Session State ---
if 'center' not in st.session_state: st.session_state.center = [30.3753, 69.3451]
if 'zoom' not in st.session_state: st.session_state.zoom = 6
if 'radius' not in st.session_state: st.session_state.radius = 2.0

# Sidebar
st.sidebar.title("🏗️ TCF Engineering")
df = load_data()
selected_row = None

if df is not None:
    # --- Search Schools ---
    st.sidebar.subheader("🔍 Search Schools")
    search_mode = st.sidebar.radio("Search by:", ["All Schools", "School Name", "School ID"])
    
    if search_mode == "School Name":
        name = st.sidebar.selectbox("School Name:", ["Select..."] + sorted(df['School'].astype(str).unique().tolist()))
        if name != "Select...":
            selected_row = df[df['School'] == name].iloc[0]
            st.session_state.center = [selected_row['lat'], selected_row['lon']]
            st.session_state.zoom = 17
            
    elif search_mode == "School ID":
        sid = st.sidebar.selectbox("School ID:", ["Select..."] + sorted(df['search_id'].unique().tolist()))
        if sid != "Select...":
            selected_row = df[df['search_id'] == sid].iloc[0]
            st.session_state.center = [selected_row['lat'], selected_row['lon']]
            st.session_state.zoom = 17

st.sidebar.markdown("---")

# --- THE FIX: Form for Radius to avoid "Busy" Map ---
with st.sidebar.form("map_settings"):
    st.subheader("📏 Map Settings")
    new_radius = st.number_input("Radius (KM)", 0.1, 20.0, float(st.session_state.radius), 0.5)
    submit_button = st.form_submit_button("Update Map & Population")
    
    if submit_button:
        st.session_state.radius = new_radius

# Calculate Population
pop = get_pop_data(st.session_state.center[0], st.session_state.center[1], st.session_state.radius)
st.sidebar.metric("📊 Total Population", f"{pop:,}")

# --- Map Generation ---
st.title("🇵🇰 TCF Schools & Population Map")

m = folium.Map(location=st.session_state.center, zoom_start=st.session_state.zoom, 
               tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google')

# Radius Circle
folium.Circle(st.session_state.center, radius=st.session_state.radius*1000, color='red', fill=True, fill_opacity=0.1).add_to(m)

# Cluster Optimization (Fast rendering)
marker_cluster = MarkerCluster(disableClusteringAtZoom=16).add_to(m)

for _, row in df.iterrows():
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
        [row['lat'], row['lon']], 
        popup=folium.Popup(p_html, max_width=300),
        tooltip=row['School'],
        icon=folium.Icon(color='red' if is_sel else 'green', icon='star' if is_sel else 'info-sign')
    ).add_to(m if is_sel else marker_cluster)

# Map Output
out = st_folium(
    m,
    center=st.session_state.center,
    zoom=st.session_state.zoom,
    key="tcf_map_v11",
    width=1350,
    height=700,
    returned_objects=["last_object_clicked", "center", "zoom"]
)

# Interaction Logic
if out:
    if out.get("center"):
        st.session_state.center = [out["center"]["lat"], out["center"]["lng"]]
    if out.get("zoom"):
        st.session_state.zoom = out["zoom"]
        
    if out.get("last_object_clicked"):
        click_lat = out["last_object_clicked"]["lat"]
        click_lon = out["last_object_clicked"]["lng"]
        if [click_lat, click_lon] != st.session_state.center:
            st.session_state.center = [click_lat, click_lon]
            st.rerun()
