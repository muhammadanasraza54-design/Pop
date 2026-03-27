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
POP_FILE = "pak_total_Pop FN.tif"  # Sirf yahi file use hogi

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
            # Nan values ko handle karte hue sum nikalna
            total = int(np.nansum(data[data > 0]))
            return total
    except Exception as e:
        return None

@st.cache_data
def load_excel_data():
    try:
        df = pd.read_excel(EXCEL_FILE)
        df.columns = df.columns.str.strip()
        # ID/Code column dhoondna
        id_col = [col for col in df.columns if 'ID' in col.upper() or 'CODE' in col.upper()][0]
        df['search_id'] = df[id_col].astype(str)
        return df
    except Exception as e:
        st.error(f"Excel File Error: {e}")
        return None

# Initialize Session State for Position
if 'pos' not in st.session_state:
    st.session_state.pos = [30.3753, 69.3451] # Default Pakistan Center

# --- Sidebar Logic ---
st.sidebar.title("🏗️ TCF Engineering")

# 1. Search Schools
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
            st.session_state.pos = [selected_row['lat'], selected_row['lon']]
            
    elif search_mode == "School ID":
        id_options = ["Select..."] + sorted(data['search_id'].dropna().unique().tolist())
        id_search = st.sidebar.selectbox("School ID:", id_options)
        if id_search != "Select...":
            selected_row = data[data['search_id'] == id_search].iloc[0]
            st.session_state.pos = [selected_row['lat'], selected_row['lon']]

st.sidebar.markdown("---")

# 2. Radius & Population Settings
st.sidebar.subheader("📏 Population Radius")
radius = st.sidebar.number_input("Enter Radius (KM)", min_value=0.1, max_value=50.0, value=2.0, step=0.5)

# Calculate Population
total_pop = get_pop_data(st.session_state.pos[0], st.session_state.pos[1], radius)

if total_pop is not None:
    st.sidebar.metric("📊 Total Population", f"{total_pop:,}")
    st.sidebar.caption(f"📍 Coordinates: {st.session_state.pos[0]:.4f}, {st.session_state.pos[1]:.4f}")
else:
    st.sidebar.warning("TIF file not found or data error.")

# --- Map Setup ---
st.title("🇵🇰 TCF Schools & Population Map")

zoom_lvl = 16 if selected_row is not None else 6

m = folium.Map(
    location=st.session_state.pos, 
    zoom_start=zoom_lvl, 
    tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
    attr='Google'
)

# Radius Circle
folium.Circle(
    st.session_state.pos, 
    radius=radius*1000, 
    color='red', 
    fill=True, 
    fill_opacity=0.15,
    tooltip=f"{radius}km Population Area"
).add_to(m)

# Marker Cluster
marker_cluster = MarkerCluster(name="TCF Clusters").add_to(m)

if data is not None:
    for index, row in data.iterrows():
        if pd.notnull(row['lat']) and pd.notnull(row['lon']):
            popup_html = f"""
            <div style="font-family: Arial; width: 200px; font-size: 13px;">
                <h4 style="margin-bottom:5px; color: #007BFF;">{row['School']}</h4>
                <b>ID:</b> {row['search_id']}<br>
                <b>Status:</b> {row.get('Status', 'N/A')}<br>
                <hr style="margin: 5px 0;">
                <span style="color: #e91e63;"><b>Utilization:</b> {row.get('Operational Utilization', 'N/A')}</span>
            </div>
            """
            
            is_selected = selected_row is not None and str(row['search_id']) == str(selected_row['search_id'])
            
            folium.Marker(
                location=[row['lat'], row['lon']],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=row['School'],
                icon=folium.Icon(color='red' if is_selected else 'green', icon='star' if is_selected else 'info-sign')
            ).add_to(marker_cluster if not is_selected else m)

# Full Height Map
out = st_folium(m, width=1350, height=750, key=f"map_{st.session_state.pos}_{radius}")

# Handle Map Click
if out.get("last_clicked"):
    new_pos = [out["last_clicked"]["lat"], out["last_clicked"]["lng"]]
    if new_pos != st.session_state.pos:
        st.session_state.pos = new_pos
        st.rerun()
