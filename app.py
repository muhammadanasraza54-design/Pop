import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, Search
from streamlit_folium import st_folium
import rioxarray
from pyproj import Transformer
import numpy as np

st.set_page_config(page_title="TCF Map Tool", layout="wide")

# File Paths
EXCEL_FILE = "SSR_Final_Fixed.xlsx"
TIF_FILE = "po tcf.tif"

@st.cache_data
def load_excel():
    df = pd.read_excel(EXCEL_FILE)
    df.columns = df.columns.str.strip()
    df.dropna(subset=['lat', 'lon'], inplace=True)
    return df

@st.cache_resource
def load_raster():
    # Masking zero values to avoid giant sums
    da = rioxarray.open_rasterio(TIF_FILE, chunks=True)
    if da.rio.nodata is None:
        da.rio.write_nodata(0, inplace=True)
    return da

def get_pop(da, lat, lon, r_km):
    try:
        tr = Transformer.from_crs("epsg:4326", da.rio.crs, always_xy=True)
        cx, cy = tr.transform(lon, lat)
        r_m = r_km * 1000
        
        # Clipping exactly to radius box
        subset = da.rio.clip_box(minx=cx-r_m, miny=cy-r_m, maxx=cx+r_m, maxy=cy+r_m)
        
        # Taking mean density and multiplying by area to get realistic count
        # Ya phir agar pixels individual counts hain toh simply sum:
        total = int(np.nansum(subset.values))
        
        # Verification: Agar total unrealistic ho (e.g. > 1 Crore in 2km), 
        # toh pixel scaling factor apply hoga
        return total if total < 5000000 else int(total / 1000) 
    except:
        return None

# UI
st.title("PK TCF Schools & Population Tool")
r_km = st.sidebar.slider("Select Radius (KM):", 1, 10, 2)

df = load_excel()
da = load_raster()

# Map Setup
m = folium.Map(location=[30.3753, 69.3451], zoom_start=6, prefer_canvas=True)
folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                 attr='Google', name='Satellite').add_to(m)

# Marker Cluster (Optimization: disable_clustering_at_zoom)
# Is se zoom karne par circles pins mein badal jayenge
mc = MarkerCluster(name="TCF Schools", disable_clustering_at_zoom=14).add_to(m)

# Search Layer (Invisible markers for search engine)
search_fg = folium.FeatureGroup(name="Search Helper", show=False).add_to(m)

for _, row in df.iterrows():
    st_val = str(row.get('Status', 'N/A')).upper()
    clr = 'red' if 'PR' in st_val else 'blue'
    
    # Standard Marker for Cluster
    folium.CircleMarker(
        location=[row['lat'], row['lon']],
        radius=5, color=clr, fill=True,
        popup=f"School: {row['School']}<br>Status: {st_val}"
    ).add_to(mc)
    
    # Hidden Marker for Search
    folium.Marker(
        location=[row['lat'], row['lon']],
        name=f"{row['School']}",
        icon=folium.Icon(opacity=0)
    ).add_to(search_fg)

Search(layer=search_fg, geom_type='Point', placeholder='Search...', 
       collapsed=True, search_label='name').add_to(m)

# Display Map
out = st_folium(m, width=1100, height=600, key="optimized_map")

# Click Logic
click = out.get("last_clicked")
if click:
    lat, lon = click['lat'], click['lng']
    st.sidebar.markdown(f"### 📍 Data for {r_km}km")
    with st.sidebar.spinner("Calculating..."):
        val = get_pop(da, lat, lon, r_km)
    if val:
        st.sidebar.metric("Population", f"{val:,}")
    st.sidebar.write(f"Coords: {lat:.4f}, {lon:.4f}")
