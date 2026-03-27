import streamlit as st
import pandas as pd
import folium
from folium.plugins import Search
from streamlit_folium import st_folium
import rioxarray
import numpy as np
from pyproj import Transformer

st.set_page_config(page_title="TCF School Tool", layout="wide")

# 1. Loading Data
@st.cache_data
def load_excel():
    df = pd.read_excel("SSR_Final_Fixed.xlsx")
    df.columns = df.columns.str.strip()
    return df

@st.cache_resource
def load_raster():
    da = rioxarray.open_rasterio("po tcf.tif", chunks=True)
    return da.where(da != -9999, 0) # NoData handling

# 2. Population Calculation Logic
def get_pop(da, lat, lon, r_km):
    try:
        tr = Transformer.from_crs("epsg:4326", da.rio.crs, always_xy=True)
        cx, cy = tr.transform(lon, lat)
        r_m = r_km * 1000
        subset = da.rio.clip_box(minx=cx-r_m, miny=cy-r_m, maxx=cx+r_m, maxy=cy+r_m)
        
        raw_sum = np.nansum(subset.values)
        # Scaling: Agar value 10 lakh se zyada hai 2km mein, toh wo density factor hai
        actual_pop = int(raw_sum / 1000) if raw_sum > 1000000 else int(raw_sum)
        return max(0, actual_pop)
    except:
        return 0

# UI
df = load_excel()
da = load_raster()

st.title("PK TCF School Analysis Tool")
r_km = st.sidebar.slider("Radius (KM):", 1, 10, 2)

# 3. Map Building
m = folium.Map(location=[30.3753, 69.3451], zoom_start=6)
folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                 attr='Google', name='Satellite').add_to(m)

# FeatureGroup for Search
fg = folium.FeatureGroup(name="Schools").add_to(m)

for _, row in df.iterrows():
    status = str(row.get('Status', 'N/A')).upper()
    color = 'red' if 'PR' in status else 'blue'
    school_name = str(row['School'])
    
    # Tooltip and Popup HTML
    html_content = f"<b>School:</b> {school_name}<br><b>Status:</b> {status}"
    
    # Markers (Better for Search)
    folium.CircleMarker(
        location=[row['lat'], row['lon']],
        radius=6,
        color=color,
        fill=True,
        fill_opacity=0.9,
        popup=folium.Popup(html_content, max_width=300),
        tooltip=school_name,
        name=school_name # This is for Search plugin
    ).add_to(fg)

# Search Bar - Ab yeh 'name' field ko scan karega
Search(layer=fg, geom_type='Point', placeholder='Search School...',
       collapsed=False, search_label='name').add_to(m)

# Map Output
out = st_folium(m, width=1100, height=600, key="tcf_map_v3")

# Sidebar Stats
click = out.get("last_clicked")
if click:
    lat, lon = click['lat'], click['lng']
    pop = get_pop(da, lat, lon, r_km)
    st.sidebar.success(f"📍 Population: **{pop:,}**")
    st.sidebar.info(f"Coords: {lat:.4f}, {lon:.4f}")
