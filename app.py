import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, Search
from streamlit_folium import st_folium
import rioxarray
import numpy as np
from pyproj import Transformer
from shapely.geometry import Point
import json

# 1. Page Layout
st.set_page_config(page_title="PK TCF Schools Map Tool", layout="wide")

# Files ke naam (Ensure correct file names on GitHub)
EXCEL_FILE = "SSR_Final_Fixed.xlsx"
TIF_FILE = "po tcf.tif" 

# --- Session State Management ---
if 'last_run_clicked_coords' not in st.session_state:
    st.session_state.last_run_clicked_coords = None
if 'map_output' not in st.session_state:
    st.session_state.map_output = None

# --- Data Loading Function (Optimized & Cached) ---
@st.cache_data
def load_excel_data():
    try:
        df = pd.read_excel(EXCEL_FILE)
        df.columns = df.columns.str.strip()
        # ID Column dhundna
        id_col = [col for col in df.columns if 'ID' in col.upper() or 'CODE' in col.upper()][0]
        df['search_id'] = df[id_col].astype(str)
        # Lat/Lon ko clean karein warna crash ho jaye ga
        df.dropna(subset=['lat', 'lon'], inplace=True)
        return df
    except Exception as e:
        st.error(f"Excel Error: {e}")
        return None

# --- Memory-Efficient Population Calculation Function (Xarray + Dask) ---
@st.cache_resource # Resource cache for DataArray
def load_population_data():
    try:
        da = rioxarray.open_rasterio(TIF_FILE, chunks=True)
        return da
    except Exception as e:
        st.error(f"Population File Error: {e}")
        return None

def calculate_population(da, lat, lon, radius_km):
    try:
        if da is None: return None
        # Lat/Lon ko TIF ke coordinates mein convert karna
        transformer = Transformer.from_crs("epsg:4326", da.rio.crs, always_xy=True)
        center_x, center_y = transformer.transform(lon, lat)
        
        # Radius in meters for xarray clipping
        radius_m = radius_km * 1000
        xmin, ymin = center_x - radius_m, center_y - radius_m
        xmax, ymax = center_x + radius_m, center_y + radius_m
        
        # Compute only that slice from the dask array (memory friendly)
        slice_da = da.rio.clip_box(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax)
        total_pop = slice_da.where(slice_da > 0).sum().compute()
        return int(total_pop)
    except Exception as e:
        return None

# --- Main App ---
st.title("🇵🇰 PK TCF Schools & Population Density Map Tool")

# Sidebar
st.sidebar.title("🛠️ Tools & Controls")
st.sidebar.markdown("### Population Radius")
st.sidebar.markdown("Pin par click kar ke population circle banayein:")
selected_radius = st.sidebar.slider("Select Radius (KM):", 1, 10, 2)

data = load_excel_data()
da_pop = load_population_data()

# --- Map Setup ---
if data is not None and da_pop is not None:
    map_location = [30.3753, 69.3451] # Pakistan center
    
    m = folium.Map(location=map_location, zoom_start=6, tiles=None, control_scale=True)
    
    # 1. Base Layer (OpenStreetMap default)
    folium.TileLayer('OpenStreetMap', name='Street Map').add_to(m)
    
    # 2. Add Satellite View (Aapki requirement ke mutabiq)
    google_sat = folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Satellite',
        overlay=True,
        control=True
    ).add_to(m)
    google_sat.layer_name = 'Google Satellite'

    # 3. Add Cluster Pins (Markers Cluster)
    marker_cluster = MarkerCluster(name="TCF Schools (Clusters)").add_to(m)

    # Markers Loop
    for index, row in data.iterrows():
        # Status ke mutabiq Marker ka rang (Pehle wala design)
        status = str(row.get('Status', 'N/A')).upper()
        if 'PR' in status: marker_color = 'red'
        elif 'SC' in status: marker_color = 'blue'
        else: marker_color = 'green'

        # Correct Popup Logic (Address update)
        popup_html = f"""
        <div style="font-family: Arial; width: 220px; font-size: 13px;">
            <h4 style="margin-bottom:5px; color: {marker_color};">{row['School']}</h4>
            <b>ID:</b> {row['search_id']}<br>
            <b>Region:</b> {row.get('Region', 'N/A')}<br>
            <b style="color: {marker_color};">Status:</b> {row.get('Status', 'N/A')}<br>
            <b>Utilization:</b> {row.get('Operational Utilization', 'N/A')}<br>
            <hr style="margin: 5px 0;">
            <b>Address:</b> <span style="font-size: 11px; color: #555;">{row.get('Address', 'Location not available')}</span><br>
            <hr style="margin: 5px 0;">
            <span style="color: #e91e63;"><b>Girls:</b> {row.get('Girls %', '0')}%</span> | 
            <span style="color: #2196f3;"><b>Boys:</b> {row.get('Boys %', '0')}%</span>
        </div>
        """
        
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=6,
            color=marker_color,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.7,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{row['School']} ({row.get('Status', 'N/A')})"
        ).add_to(marker_cluster) # Cluster mein add karein

    # 4. Add Search Feature (Pehle wala features restore)
    # Search tool only works with plain markers, not clusters easily, but this shows in a search result
    school_search = Search(
        layer=marker_cluster,
        geom_type='Point',
        placeholder='Search School Name or ID',
        collapsed=False,
        search_label='School', # Match exact column name in Excel
        weight=1,
        fill_color='green'
    ).add_to(m)

    # 5. Handling Clicking for Population (Callbacks for radius)
    clicked_marker = st.session_state.map_output.get("last_object_clicked") if st.session_state.map_output else None
    
    if clicked_marker:
        marker_lat, marker_lon = clicked_marker['lat'], clicked_marker['lng']
        pop_count = calculate_population(da_pop, marker_lat, marker_lon, selected_radius)
        
        # Violet population circle banayein
        folium.Circle(
            location=[marker_lat, marker_lon],
            radius=selected_radius * 1000,
            color='purple',
            fill=True,
            fill_opacity=0.2,
            tooltip=f"Population: {pop_count:,} ({selected_radius}km radius)"
        ).add_to(m)
        
        # Sidebar Status
        st.sidebar.markdown("---")
        st.sidebar.success(f"📍 Selected Point: {marker_lat:.4f}, {marker_lon:.4f}")
        if pop_count is not None:
            st.sidebar.metric(label=f"Total Population ({selected_radius}km)", value=f"{pop_count:,}")
        else:
            st.sidebar.error("Population data not available.")

    # Render Map (Use width=1350 for full view like original screenshot)
    st.session_state.map_output = st_folium(m, width=1350, height=750)

    # Layer Control (Hamesha add karein Google Satellite enable karne ke liye)
    folium.LayerControl().add_to(m)

else:
    st.error("Data files (Excel/TIF) load nahi ho sakein.")
