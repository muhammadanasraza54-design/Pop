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

# --- Page Configuration ---
st.set_page_config(page_title="TCF Schools & Population Map", layout="wide")

# File Names (Make sure these exist in your GitHub repo)
EXCEL_FILE = "SSR_Final_Fixed.xlsx"
POP_FILE = "pak_total_Pop FN.tif"

# --- 1. Population Calculation Function ---
def get_pop_data(lat, lon, rad_km):
    if not os.path.exists(POP_FILE):
        return None
    try:
        # Distance to Degrees conversion
        deg_lat = rad_km / 111.0
        deg_lon = rad_km / (111.0 * math.cos(math.radians(lat)))
        left, bottom, right, top = (lon - deg_lon, lat - deg_lat, lon + deg_lon, lat + deg_lat)
        
        with rasterio.open(POP_FILE) as ds:
            window = from_bounds(left, bottom, right, top, ds.transform)
            # Boundless=True aur fill_value=0 taake edge par crash na ho
            data = ds.read(1, window=window, boundless=True, fill_value=0)
            total = int(np.nansum(data[data > 0]))
            return total
    except Exception:
        return 0

# --- 2. Data Loading with Fix for NaN/Crash ---
@st.cache_data(show_spinner=False)
def load_excel_data():
    try:
        df = pd.read_excel(EXCEL_FILE)
        df.columns = df.columns.str.strip()
        
        # CRITICAL FIX: Remove rows where coordinates are missing
        df = df.dropna(subset=['lat', 'lon'])
        
        # Identify ID column
        id_cols = [col for col in df.columns if 'ID' in col.upper() or 'CODE' in col.upper()]
        id_col = id_cols[0] if id_cols else df.columns[0]
        df['search_id'] = df[id_col].astype(str)
        
        return df
    except Exception as e:
        st.error(f"Excel Error: {e}")
        return None

# --- 3. Session State for Map Persistence ---
# Is se radius change karne par map restore nahi hoga
if 'map_center' not in st.session_state:
    st.session_state.map_center = [30.3753, 69.3451]
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = 6

# --- 4. Sidebar UI ---
st.sidebar.title("🏗️ TCF Engineering")
data = load_excel_data()
selected_row = None

if data is not None:
    st.sidebar.subheader("🔍 Search Schools")
    search_mode = st.sidebar.radio("Search by:", ["All Schools", "School Name", "School ID"])
    
    if search_mode == "School Name":
        name_options = ["Select..."] + sorted(data['School'].astype(str).unique().tolist())
        name_search = st.sidebar.selectbox("School Name:", name_options)
        if name_search != "Select...":
            selected_row = data[data['School'] == name_search].iloc[0]
            st.session_state.map_center = [selected_row['lat'], selected_row['lon']]
            st.session_state.map_zoom = 17
            
    elif search_mode == "School ID":
        id_options = ["Select..."] + sorted(data['search_id'].unique().tolist())
        id_search = st.sidebar.selectbox("School ID:", id_options)
        if id_search != "Select...":
            selected_row = data[data['search_id'] == id_search].iloc[0]
            st.session_state.map_center = [selected_row['lat'], selected_row['lon']]
            st.session_state.map_zoom = 17

st.sidebar.markdown("---")

# Radius Control
radius = st.sidebar.number_input("Enter Radius (KM)", min_value=0.1, max_value=50.0, value=2.0, step=0.5)

# Calculate Population
pop_res = get_pop_data(st.session_state.map_center[0], st.session_state.map_center[1], radius)
if pop_res is not None:
    st.sidebar.metric("📊 Total Population", f"{pop_res:,}")
    st.sidebar.caption(f"📍 Coords: {st.session_state.map_center[0]:.4f}, {st.session_state.map_center[1]:.4f}")

# --- 5. Map Rendering ---
st.title("🇵🇰 TCF Schools & Population Map")

# Base Map
m = folium.Map(
    location=st.session_state.map_center, 
    zoom_start=st.session_state.map_zoom, 
    tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
    attr='Google'
)

# Population Radius Circle
folium.Circle(
    st.session_state.map_center, 
    radius=radius*1000, 
    color='red', 
    fill=True, 
    fill_opacity=0.1
).add_to(m)

# Marker Cluster for Speed
marker_cluster = MarkerCluster(name="TCF Clusters", disableClusteringAtZoom=16).add_to(m)

if data is not None:
    for _, row in data.iterrows():
        # Popup Design Restored
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
            tooltip=str(row['School']),
            icon=folium.Icon(color='red' if is_sel else 'green', icon='star' if is_sel else 'info-sign')
        ).add_to(m if is_sel else marker_cluster)

# st_folium with bi-directional update
out = st_folium(
    m, 
    width=1350, 
    height=750, 
    key="tcf_map_v9",
    use_container_width=True
)

# Update Session State when map moves (prevents restore/reset)
if out:
    if out.get("center"):
        # Check if center actually changed to avoid infinite loop
        new_lat = round(out["center"]["lat"], 5)
        new_lng = round(out["center"]["lng"], 5)
        if [new_lat, new_lng] != st.session_state.map_center:
            st.session_state.map_center = [new_lat, new_lng]
    
    if out.get("zoom"):
        if out["zoom"] != st.session_state.map_zoom:
            st.session_state.map_zoom = out["zoom"]
            
    # If a pin is clicked, move center there for population calculation
    if out.get("last_clicked"):
        click_p = [out["last_clicked"]["lat"], out["last_clicked"]["lng"]]
        if click_p != st.session_state.map_center:
            st.session_state.map_center = click_p
            st.rerun()
