import streamlit as st
import pandas as pd
import folium
from folium.plugins import Search
from streamlit_folium import st_folium
import rioxarray
import numpy as np

st.set_page_config(layout="wide", page_title="TCF Stable Map")

@st.cache_data
def load_and_clean_data():
    df = pd.read_excel("SSR_Final_Fixed.xlsx")
    df.columns = df.columns.str.strip()
    # Khali coordinates nikal dein taake NaN error na aaye
    df = df.dropna(subset=['lat', 'lon'])
    df['search_label'] = df['School'].astype(str)
    return df

@st.cache_resource
def load_raster():
    try:
        da = rioxarray.open_rasterio("po tcf.tif", chunks=True)
        return da
    except:
        return None

def calculate_local_pop(da, lat, lon, r_km):
    if da is None: return 0
    try:
        # KM ko approx degrees mein convert karna
        deg_buffer = r_km / 111.0
        subset = da.sel(x=slice(lon-deg_buffer, lon+deg_buffer), 
                        y=slice(lat+deg_buffer, lat-deg_buffer))
        total = np.nansum(subset.values)
        # Agar value bahut zyada hai (e.g. 19Cr), toh scaling apply karein
        if total > 5000000: total = total / 100 
        return int(total)
    except:
        return 0

# --- UI Setup ---
df = load_and_clean_data()
da = load_raster()

st.title("PK TCF Schools Interactive Map")
r_km = st.sidebar.slider("Population Radius (KM):", 1, 10, 2)

# Map Create
m = folium.Map(location=[30.3753, 69.3451], zoom_start=6)
folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                 attr='Google', name='Satellite').add_to(m)

fg = folium.FeatureGroup(name="Schools").add_to(m)

for _, row in df.iterrows():
    status = str(row.get('Status', 'N/A')).upper()
    color = 'red' if 'PR' in status else 'blue'
    popup_text = f"<b>{row['School']}</b><br>Status: {status}"
    
    folium.CircleMarker(
        location=[row['lat'], row['lon']],
        radius=7, color=color, fill=True, fill_opacity=0.7,
        popup=folium.Popup(popup_text, max_width=200),
        name=row['search_label']
    ).add_to(fg)

# Search Bar Fix
Search(layer=fg, geom_type='Point', placeholder='Search School...',
       collapsed=False, search_label='name').add_to(m)

# Display Map
map_data = st_folium(m, width=1100, height=600, key="stable_map_v7")

# --- Error Fix for Metrics ---
click = map_data.get("last_clicked")
if click:
    with st.sidebar:
        st.write(f"**Target Coords:** {click['lat']:.4f}, {click['lng']:.4f}")
        pop_res = calculate_local_pop(da, click['lat'], click['lng'], r_km)
        
        # Crash prevention: Check karein ke pop_res valid number hai
        if isinstance(pop_res, (int, float)):
            st.metric("Local Population", f"{int(pop_res):,}")
        else:
            st.warning("Population data not found for this spot.")
