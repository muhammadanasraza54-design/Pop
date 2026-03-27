import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, Search
from streamlit_folium import st_folium
import rioxarray
import numpy as np
from pyproj import Transformer

# 1. Page Layout
st.set_page_config(page_title="PK TCF Schools Map Tool", layout="wide")

# Files check
EXCEL_FILE = "SSR_Final_Fixed.xlsx"
TIF_FILE = "po tcf.tif" 

# --- Data Loading ---
@st.cache_data
def load_excel_data():
    try:
        df = pd.read_excel(EXCEL_FILE)
        df.columns = df.columns.str.strip()
        id_col = [col for col in df.columns if 'ID' in col.upper() or 'CODE' in col.upper()][0]
        df['search_id'] = df[id_col].astype(str)
        df.dropna(subset=['lat', 'lon'], inplace=True)
        return df
    except Exception as e:
        st.error(f"Excel Error: {e}")
        return None

@st.cache_resource
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
        transformer = Transformer.from_crs("epsg:4326", da.rio.crs, always_xy=True)
        center_x, center_y = transformer.transform(lon, lat)
        radius_m = radius_km * 1000
        xmin, ymin = center_x - radius_m, center_y - radius_m
        xmax, ymax = center_x + radius_m, center_y + radius_m
        slice_da = da.rio.clip_box(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax)
        total_pop = slice_da.where(slice_da > 0).sum().compute()
        return int(total_pop)
    except Exception:
        return None

# --- UI ---
st.title("🇵🇰 PK TCF Schools & Population Density Map Tool")

# Sidebar
st.sidebar.title("🛠️ Tools & Controls")
selected_radius = st.sidebar.slider("Select Radius (KM):", 1, 10, 2)
st.sidebar.info("Tip: Map par click karein ya school pin par population check karne ke liye.")

data = load_excel_data()
da_pop = load_population_data()

if data is not None and da_pop is not None:
    # Map Initialization
    m = folium.Map(location=[30.3753, 69.3451], zoom_start=6, tiles=None)
    folium.TileLayer('OpenStreetMap', name='Street Map').add_to(m)
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google', name='Google Satellite', overlay=True
    ).add_to(m)

    # Marker Group for Search
    school_group = folium.FeatureGroup(name="Schools Layer")
    marker_cluster = MarkerCluster(name="TCF Schools (Clusters)").add_to(m)

    for index, row in data.iterrows():
        status = str(row.get('Status', 'N/A')).upper()
        marker_color = 'red' if 'PR' in status else 'blue' if 'SC' in status else 'green'
        
        popup_html = f"<b>{row['School']}</b><br>ID: {row['search_id']}<br>Status: {status}"
        
        marker = folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=6, color=marker_color, fill=True,
            popup=folium.Popup(popup_html, max_width=250),
            school_name=row['School'], # Custom property for search
            school_id=row['search_id']
        )
        marker.add_to(marker_cluster)
        marker.add_to(school_group) # Search function ke liye

    # Search Bar Fix
    Search(
        layer=school_group,
        geom_type='Point',
        placeholder='Search School Name or ID',
        collapsed=False,
        search_label='school_name'
    ).add_to(m)

    # --- Click Handling (Map & Marker) ---
    # st_folium ka output lena
    map_output = st_folium(m, width=1350, height=700, key="main_map")

    # Click Logic: Priority Map Click then Marker Click
    target_lat, target_lon = None, None
    
    if map_output.get("last_clicked"):
        target_lat = map_output["last_clicked"]["lat"]
        target_lon = map_output["last_clicked"]["lng"]
    elif map_output.get("last_object_clicked"):
        target_lat = map_output["last_object_clicked"]["lat"]
        target_lon = map_output["last_object_clicked"]["lng"]

    if target_lat and target_lon:
        pop_count = calculate_population(da_pop, target_lat, target_lon, selected_radius)
        
        # UI updates in sidebar
        st.sidebar.markdown("---")
        st.sidebar.success(f"📍 Location: {target_lat:.4f}, {target_lon:.4f}")
        if pop_count is not None:
            st.sidebar.metric("Total Population", f"{pop_count:,}")
            # Map par circle dikhana (next render mein ayega)
            folium.Circle(
                location=[target_lat, target_lon],
                radius=selected_radius * 1000,
                color='purple', fill=True, fill_opacity=0.2
            ).add_to(m)
        else:
            st.sidebar.warning("Is jagah ka data available nahi hai.")

    folium.LayerControl().add_to(m)
