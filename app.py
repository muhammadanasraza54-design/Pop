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
st.set_page_config(page_title="TCF Schools & Population Map", layout="wide")

# File Names
EXCEL_FILE = "SSR_Final_Fixed.xlsx"
POP_FILE = "pak_total_Pop FN.tif"

# --- Population Calculation Function ---
def get_pop_data(lat, lon, rad_km):
    deg_lat = rad_km / 111.0
    deg_lon = rad_km / (111.0 * math.cos(math.radians(lat)))
    left, bottom, right, top = (lon - deg_lon, lat - deg_lat, lon + deg_lon, lat + deg_lat)
    
    try:
        if not os.path.exists(POP_FILE):
            return None
        with rasterio.open(POP_FILE) as ds:
            window = from_bounds(left, bottom, right, top, ds.transform)
            data = ds.read(1, window=window)
            total = int(np.nansum(data[data > 0]))
            return total
    except:
        return None

@st.cache_data
def load_excel_data():
    try:
        df = pd.read_excel(EXCEL_FILE)
        df.columns = df.columns.str.strip()
        id_cols = [col for col in df.columns if 'ID' in col.upper() or 'CODE' in col.upper()]
        id_col = id_cols[0] if id_cols else df.columns[0]
        df['search_id'] = df[id_col].astype(str)
        return df
    except Exception as e:
        st.error(f"Excel File Error: {e}")
        return None

# --- Session State Initialization ---
# Is se map ki location save rahegi
if 'map_center' not in st.session_state:
    st.session_state.map_center = [30.3753, 69.3451]
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = 6
if 'last_radius' not in st.session_state:
    st.session_state.last_radius = 2.0

# --- Sidebar Logic ---
st.sidebar.title("🏗️ TCF Engineering")

data = load_excel_data()
selected_row = None

if data is not None:
    st.sidebar.subheader("🔍 Search Schools")
    search_mode = st.sidebar.radio("Search by:", ["All Schools", "School Name", "School ID"])
    
    if search_mode == "School Name":
        name_options = ["Select..."] + sorted(data['School'].dropna().unique().tolist())
        name_search = st.sidebar.selectbox("School Name:", name_options)
        if name_search != "Select...":
            selected_row = data[data['School'] == name_search].iloc[0]
            st.session_state.map_center = [selected_row['lat'], selected_row['lon']]
            st.session_state.map_zoom = 16
            
    elif search_mode == "School ID":
        id_options = ["Select..."] + sorted(data['search_id'].dropna().unique().tolist())
        id_search = st.sidebar.selectbox("School ID:", id_options)
        if id_search != "Select...":
            selected_row = data[data['search_id'] == id_search].iloc[0]
            st.session_state.map_center = [selected_row['lat'], selected_row['lon']]
            st.session_state.map_zoom = 16

st.sidebar.markdown("---")

# Radius Input
st.sidebar.subheader("📏 Population Radius")
radius = st.sidebar.number_input("Enter Radius (KM)", min_value=0.1, max_value=50.0, value=float(st.session_state.last_radius), step=0.5)
st.session_state.last_radius = radius

# Current Population based on Center
total_pop = get_pop_data(st.session_state.map_center[0], st.session_state.map_center[1], radius)

if total_pop is not None:
    st.sidebar.metric("📊 Total Population", f"{total_pop:,}")
    st.sidebar.caption(f"📍 {st.session_state.map_center[0]:.4f}, {st.session_state.map_center[1]:.4f}")

# --- Map Setup ---
st.title("🇵🇰 TCF Schools & Population Map")

m = folium.Map(
    location=st.session_state.map_center, 
    zoom_start=st.session_state.map_zoom, 
    tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
    attr='Google'
)

# Radius Circle at Center
folium.Circle(
    st.session_state.map_center, 
    radius=radius*1000, 
    color='red', 
    fill=True, 
    fill_opacity=0.15,
    tooltip=f"{radius}km Radius"
).add_to(m)

# Marker Cluster
marker_cluster = MarkerCluster(name="TCF Clusters").add_to(m)

if data is not None:
    for index, row in data.iterrows():
        if pd.notnull(row['lat']) and pd.notnull(row['lon']):
            popup_html = f"""
            <div style="font-family: Arial; width: 200px;">
                <h4 style="color: #007BFF; margin-bottom:5px;">{row['School']}</h4>
                <b>ID:</b> {row['search_id']}<br>
                <b>Status:</b> {row.get('Status', 'N/A')}<br>
                <b>Utilization:</b> {row.get('Operational Utilization', 'N/A')}
            </div>
            """
            folium.Marker(
                location=[row['lat'], row['lon']],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=row['School'],
                icon=folium.Icon(color='green', icon='info-sign')
            ).add_to(marker_cluster)

# Render Map (Important: we use center and zoom from session state)
out = st_folium(m, width=1350, height=750, key="main_map")

# Update Session State when user moves the map or clicks
if out is not None:
    if out.get("center"):
        st.session_state.map_center = [out["center"]["lat"], out["center"]["lng"]]
    if out.get("zoom"):
        st.session_state.map_zoom = out["zoom"]
    
    # Agar pin par click ho to population recalculate ho
    if out.get("last_clicked"):
        click_pos = [out["last_clicked"]["lat"], out["last_clicked"]["lng"]]
        if click_pos != st.session_state.map_center:
            st.session_state.map_center = click_pos
            st.rerun()
