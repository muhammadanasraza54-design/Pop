import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, Search
from streamlit_folium import st_folium
import rioxarray
from pyproj import Transformer

# 1. Page Config
st.set_page_config(page_title="PK TCF Map Tool", layout="wide")

# File Paths
EXCEL_FILE = "SSR_Final_Fixed.xlsx"
TIF_FILE = "po tcf.tif"

# --- Functions ---
@st.cache_data
def load_excel():
    try:
        df = pd.read_excel(EXCEL_FILE)
        df.columns = df.columns.str.strip()
        df.dropna(subset=['lat', 'lon'], inplace=True)
        if 'Status' not in df.columns: df['Status'] = "N/A"
        return df
    except Exception as e:
        st.error(f"Excel Error: {e}")
        return None

@st.cache_resource
def load_raster():
    try:
        # Load with chunks for better performance
        return rioxarray.open_rasterio(TIF_FILE, chunks={'x': 512, 'y': 512})
    except Exception as e:
        st.error(f"TIF Error: {e}")
        return None

def get_pop(da, lat, lon, r_km):
    try:
        if da is None: return None
        tr = Transformer.from_crs("epsg:4326", da.rio.crs, always_xy=True)
        cx, cy = tr.transform(lon, lat)
        r_m = r_km * 1000
        # Dynamic Clip based on selected radius
        box = da.rio.clip_box(minx=cx-r_m, miny=cy-r_m, maxx=cx+r_m, maxy=cy+r_m)
        total = int(box.where(box > 0).sum().compute())
        return total
    except:
        return None

# --- Application ---
st.title("PK TCF Schools & Population Density Tool")

# Sidebar
st.sidebar.header("Settings")
r_km = st.sidebar.slider("Select Radius (KM):", 1, 10, 2)

df = load_excel()
da = load_raster()

if df is not None:
    # Initial Map
    m = folium.Map(location=[30.3753, 69.3451], zoom_start=6)
    
    # Satellite Layer
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google', name='Google Satellite', overlay=True
    ).add_to(m)

    # Cluster for Visuals
    mc = MarkerCluster(name="TCF Schools").add_to(m)
    # Search Layer for Search Plugin
    search_fg = folium.FeatureGroup(name="Search Helper", show=False).add_to(m)

    for _, row in df.iterrows():
        st_val = str(row['Status']).upper()
        clr = 'red' if 'PR' in st_val else 'blue' if 'SC' in st_val else 'green'
        
        popup_html = f"<b>School:</b> {row['School']}<br><b>Status:</b> {st_val}<br><b>ID:</b> {row.iloc[0]}"
        
        # Add to Cluster
        marker = folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=7, color=clr, fill=True, fill_opacity=0.7,
            popup=folium.Popup(popup_html, max_width=250)
        )
        marker.add_to(mc)
        
        # Add to Search Group (Invisible)
        folium.Marker(
            location=[row['lat'], row['lon']],
            name=f"{row['School']} ({st_val})",
            icon=folium.Icon(opacity=0)
        ).add_to(search_fg)

    # Add Search
    Search(
        layer=search_fg,
        geom_type='Point',
        placeholder='Search School...',
        collapsed=False,
        search_label='name'
    ).add_to(m)

    folium.LayerControl().add_to(m)

    # Render Map - Catch output in a variable
    map_data = st_folium(m, width=1200, height=650, key="tcf_v5")

    # --- Population Display (Important!) ---
    # Click data fetch karein
    click_info = None
    if map_data.get("last_clicked"):
        click_info = map_data["last_clicked"]
    elif map_data.get("last_object_clicked"):
        click_info = map_data["last_object_clicked"]

    if click_info:
        lat, lon = click_info['lat'], click_info['lng']
        
        # Sidebar mein result dikhayein
        st.sidebar.markdown("---")
        st.sidebar.subheader("📍 Selected Location")
        
        with st.sidebar:
            with st.spinner("Calculating..."):
                val = get_pop(da, lat, lon, r_km)
            
            if val is not None:
                st.success(f"Population within **{r_km}km**: **{val:,}**")
                st.info(f"Lat: {lat:.5f}, Lon: {lon:.5f}")
            else:
                st.warning("Is jagah ka population data nahi mila.")
