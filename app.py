import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, Search
from streamlit_folium import st_folium
import rioxarray
import numpy as np
from pyproj import Transformer

# 1. Page Configuration
st.set_page_config(page_title="PK TCF Schools Map Tool", layout="wide")

# File Paths
EXCEL_FILE = "SSR_Final_Fixed.xlsx"
TIF_FILE = "po tcf.tif" 

# --- Data Loading Functions ---
@st.cache_data
def load_excel_data():
    try:
        df = pd.read_excel(EXCEL_FILE)
        # Cleaning column names
        df.columns = df.columns.str.strip()
        # Status column handle karein
        if 'Status' not in df.columns:
            df['Status'] = "N/A"
        # Search ke liye unique identifier
        df['search_tag'] = df['School'].astype(str) + " (ID: " + df.iloc[:, 0].astype(str) + ")"
        df.dropna(subset=['lat', 'lon'], inplace=True)
        return df
    except Exception as e:
        st.error(f"Excel Error: {e}")
        return None

@st.cache_resource
def load_population_data():
    try:
        # Raster data load karein
        da = rioxarray.open_rasterio(TIF_FILE, chunks={'x': 512, 'y': 512})
        return da
    except Exception as e:
        st.error(f"Population File Error: {e}")
        return None

def calculate_population(da, lat, lon, radius_km):
    try:
        if da is None: return None
        # Coordinates transform karein
        transformer = Transformer.from_crs("epsg:4326", da.rio.crs, always_xy=True)
        center_x, center_y = transformer.transform(lon, lat)
        
        # Radius in meters
        radius_m = radius_km * 1000
        xmin, ymin = center_x - radius_m, center_y - radius_m
        xmax, ymax = center_x + radius_m, center_y + radius_m
        
        # Specific area clip karein (srif 2km ya selected radius ka data)
        slice_da = da.rio.clip_box(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax)
        total_pop = slice_da.where(slice_da > 0).sum().compute()
        return int(total_pop)
    except Exception:
        return None

# --- UI Layout ---
st.title("PK TCF Schools & Population Density Map Tool")

# Sidebar Controls
st.sidebar.title("🛠️ Tools & Controls")
selected_radius = st.sidebar.slider("Select Radius (KM):", 1, 10, 2)

data = load_excel_data()
da_pop = load_population_data()

if data is not None:
    # 1. Base Map Setup
    m = folium.Map(location=[30.3753, 69.3451], zoom_start=6)
    
    # Satellite View
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google', name='Google Satellite', overlay=True
    ).add_to(m)

    # 2. Cluster aur Search Layer
    marker_cluster = MarkerCluster(name="TCF Clusters").add_to(m)
    # Search ke liye alag feature group zaroori hai
    search_layer = folium.FeatureGroup(name="Search Layer", show=False).add_to(m)

    for _, row in data.iterrows():
        # School Status determine karein (PR for Primary, SC for Secondary)
        status_val = str(row['Status']).upper()
        # Rang badlein status ke hisab se
        m_color = 'red' if 'PR' in status_val else 'blue' if 'SC' in status_val else 'green'
        
        popup_html = f"""
        <b>School:</b> {row['School']}<br>
        <b>Status:</b> {status_val}<br>
        <b>Lat:</b> {row['lat']:.4f}<br>
        <b>Lon:</b> {row['lon']:.4f}
        """
        
        marker = folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=7,
            color=m_color,
            fill=True,
            fill_opacity=0.7,
            popup=folium.Popup(popup_html, max_width=300),
            name=row['search_tag'] # Search isi field par kaam karega
        )
        marker.add_to(marker_cluster)
        marker.add_to(search_layer)

    # 3. Search Bar Logic (Fixed)
    Search(
        layer=search_layer,
        geom_type='Point',
        placeholder='Search School or ID...',
        collapsed=False,
        search_label='name'
    ).add_to(m)

    folium.LayerControl().add_to(m)

    # 4. Map Display
    map_output = st_folium(m, width=1100, height=600, key="tcf_main_map")

    # 5. Dynamic Population Logic (Click based)
    clicked_coords = None
    if map_output.get("last_clicked"):
        clicked_coords = map_output["last_clicked"]
    
    if clicked_coords:
        lat, lon = clicked_coords['lat'], clicked_coords['lng']
        
        with st.spinner(f"Calculating population for {selected_radius}km radius..."):
            pop_result = calculate_population(da_pop, lat, lon, selected_radius)
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("📍 Selection Details")
        st.sidebar.info(f"Lat: {lat:.5f}, Lon: {lon:.5f}")
        
        if pop_result is not None:
            st.sidebar.metric(f"Population (within {selected_radius}km)", f"{pop_result:,}")
        else:
            st.sidebar.warning("Is location par population data available nahi hai.")
