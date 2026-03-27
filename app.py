import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import rioxarray
import numpy as np
from pyproj import Transformer
import json

# 1. Page Layout
st.set_page_config(page_title="TCF Schools & Population Tool", layout="wide")

# Files ke naam (Ensure correct file names on GitHub)
EXCEL_FILE = "SSR_Final_Fixed.xlsx"
TIF_FILE = "po tcf.tif" 

# --- Session State to manage Map Rerenders & Popups ---
if 'last_run_clicked_coords' not in st.session_state:
    st.session_state.last_run_clicked_coords = None
if 'map_output' not in st.session_state:
    st.session_state.map_output = None
if 'selected_row_index' not in st.session_state:
    st.session_state.selected_row_index = None

# --- Data Loading Function (Optimized & Cached) ---
@st.cache_data
def load_excel_data():
    try:
        df = pd.read_excel(EXCEL_FILE)
        df.columns = df.columns.str.strip()
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
        # rioxarray use karke dask-backed array load karein (memory friendly)
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
        
        # Windows slices create karna (xarray style, not rasterio window)
        radius_m = radius_km * 1000
        xmin, ymin = center_x - radius_m, center_y - radius_m
        xmax, ymax = center_x + radius_m, center_y + radius_m
        
        # Data clip karna aur compute karna (sirf us slice ko memory mein layein ga)
        slice_da = da.rio.clip_box(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax)
        total_pop = slice_da.where(slice_da > 0).sum().compute()
        return int(total_pop)
    except Exception as e:
        return None

# --- Main App ---
st.title("🇵🇰 TCF Schools & Population Density Map Tool")

# Sidebar
st.sidebar.title("🛠️ Tools & Controls")
st.sidebar.markdown("### Population Radius")
st.sidebar.markdown("Pin par click kar ke population circle banayein:")
selected_radius = st.sidebar.slider("Select Radius (KM):", 1, 10, 2)

data = load_excel_data()
da_pop = load_population_data()

# 1. Map Create Karein (Base & Layers)
if data is not None and da_pop is not None:
    map_location = [30.3753, 69.3451]
    
    # Agar pin click hui hai to map ko wahan centered dikhane ke liye
    if st.session_state.selected_row_index is not None:
        selected_row = data.iloc[st.session_state.selected_row_index]
        map_location = [selected_row['lat'], selected_row['lon']]
        zoom_level = 15 # Zyada close zoom
    else:
        zoom_level = 6

    m = folium.Map(location=map_location, zoom_start=zoom_level, control_scale=True)
    
    # Base Tiles
    google_sat = folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Satellite',
        overlay=True,
        control=True
    ).add_to(m)
    folium.TileLayer('OpenStreetMap', name='Street Map').add_to(m)

    # Markers Loop
    for index, row in data.iterrows():
        status = str(row.get('Status', 'N/A')).upper()
        
        # PR = Red, SC = Blue, Default = Green
        if 'PR' in status: marker_color = 'red'
        elif 'SC' in status: marker_color = 'blue'
        else: marker_color = 'green'

        # Correct Popup Logic (Pehle wala design)
        popup_html = f"""
        <div style="font-family: Arial; width: 220px; font-size: 13px;">
            <h4 style="margin-bottom:5px; color: {marker_color};">{row['School']}</h4>
            <b>ID:</b> {row['search_id']}<br>
            <b>Region:</b> {row.get('Region', 'N/A')}<br>
            <b style="color: {marker_color};">Status:</b> {row.get('Status', 'N/A')}<br>
            <b>Utilization:</b> {row.get('Operational Utilization', 'N/A')}<br>
            <hr style="margin: 5px 0;">
            <b>Location:</b> <span style="font-size: 11px; color: #555;">{row.get('Location', 'Address not found')}</span><br>
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
        ).add_to(m)
    
    # --- Check for clicked marker details ---
    clicked_marker = st.session_state.map_output.get("last_object_clicked") if st.session_state.map_output else None
    
    # Agar koi pin click hui ho to population calculate karein aur radius circle banayein
    if clicked_marker:
        # Markers array ka index maloom karna st_folium se callback mein
        marker_lat, marker_lon = clicked_marker['lat'], clicked_marker['lng']
        
        # Calculate population (optimized function)
        pop_count = calculate_population(da_pop, marker_lat, marker_lon, selected_radius)
        
        # Map par radius circle add karna (taake click hone par circle dikhe)
        folium.Circle(
            location=[marker_lat, marker_lon],
            radius=selected_radius * 1000,
            color='purple',
            fill=True,
            fill_opacity=0.2,
            tooltip=f"Population: {pop_count:,} ({selected_radius}km radius)"
        ).add_to(m)
        
        # Sidebar status update
        st.sidebar.markdown("---")
        st.sidebar.success(f"📍 Analysis Point: {marker_lat:.4f}, {marker_lon:.4f}")
        if pop_count is not None:
            st.sidebar.metric(label=f"Total Population ({selected_radius}km)", value=f"{pop_count:,}")
        else:
            st.sidebar.error("Population data not available.")

    # Render Map and get output (Correct st_folium usage for callbacks)
    st.session_state.map_output = st_folium(m, width=1100, height=600)
    
    # Optional Layer Control (Upar right side par aye ga)
    folium.LayerControl().add_to(m)

else:
    st.error("Data files (Excel/TIF) load nahi ho sakein.")
