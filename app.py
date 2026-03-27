import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, Search
from streamlit_folium import st_folium
import rioxarray
import numpy as np
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
        # Status column check
        if 'Status' not in df.columns: df['Status'] = "N/A"
        return df
    except Exception as e:
        st.error(f"Excel Error: {e}")
        return None

@st.cache_resource
def load_raster():
    try:
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
        box = da.rio.clip_box(minx=cx-r_m, miny=cy-r_m, maxx=cx+r_m, maxy=cy+r_m)
        return int(box.where(box > 0).sum().compute())
    except: return None

# --- Main App ---
st.title("PK TCF Schools & Population Density Tool")

# Sidebar
r_km = st.sidebar.slider("Select Radius (KM):", 1, 10, 2)
df = load_excel()
da = load_raster()

if df is not None:
    # Map setup
    m = folium.Map(location=[30.3753, 69.3451], zoom_start=6)
    folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                     attr='Google', name='Satellite').add_to(m)

    # 1. Marker Cluster
    mc = MarkerCluster(name="TCF Schools").add_to(m)
    
    # 2. Search Layer (Markers without Cluster for Search Plugin)
    search_fg = folium.FeatureGroup(name="Search Layer", show=False).add_to(m)

    for _, row in df.iterrows():
        st_val = str(row['Status']).upper()
        # Rang: PR = Red, SC = Blue
        clr = 'red' if 'PR' in st_val else 'blue' if 'SC' in st_val else 'green'
        
        # Pop-up design
        pop_txt = f"<b>School:</b> {row['School']}<br><b>Status:</b> {st_val}<br><b>ID:</b> {row.iloc[0]}"
        
        # Cluster Marker
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=6, color=clr, fill=True, popup=pop_txt
        ).add_to(mc)

        # Search Marker (Invisible but searchable)
        folium.Marker(
            location=[row['lat'], row['lon']],
            name=f"{row['School']} ({st_val})",
            icon=folium.Icon(color="white", icon_color="white", opacity=0)
        ).add_to(search_fg)

    # Search bar add karein
    Search(
        layer=search_fg,
        geom_type='Point',
        placeholder='School ka naam likhen...',
        collapsed=False,
        search_label='name'
    ).add_to(m)

    # Display Map
    out = st_folium(m, width=1200, height=650, key="fixed_map")

    # Population logic on click
    click = out.get("last_clicked")
    if click:
        lat, lon = click['lat'], click['lng']
        with st.sidebar:
            st.markdown("---")
            st.subheader("📍 Location Info")
            val = get_pop(da, lat, lon, r_km)
            if val is not None:
                st.metric(f"Population ({r_km}km)", f"{val:,}")
                st.write(f"Lat: {lat:.4f}, Lon: {lon:.4f}")
            else:
                st.warning("Data not found.")
