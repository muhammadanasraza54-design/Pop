import streamlit as st
import pandas as pd
import folium
from folium.plugins import Search
from streamlit_folium import st_folium, folium_static
import rioxarray
import numpy as np

# Page Configuration
st.set_page_config(layout="wide")

@st.cache_data
def load_data():
    df = pd.read_excel("SSR_Final_Fixed.xlsx")
    df.columns = df.columns.str.strip()
    return df

@st.cache_resource
def load_tif():
    # TIF file loading with error bypass
    try:
        return rioxarray.open_rasterio("po tcf.tif", chunks=True)
    except:
        return None

df = load_data()
da = load_tif()

st.title("TCF Schools Interactive Map")

# 1. Map Create Karein
m = folium.Map(location=[30.3753, 69.3451], zoom_start=6)

# Satellite View
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
    attr='Google', name='Google Satellite'
).add_to(m)

# 2. Markers Add Karein
fg = folium.FeatureGroup(name="Schools").add_to(m)

for _, row in df.iterrows():
    status = str(row.get('Status', 'N/A'))
    color = 'red' if 'PR' in status.upper() else 'blue'
    
    folium.CircleMarker(
        location=[row['lat'], row['lon']],
        radius=6,
        color=color,
        fill=True,
        popup=f"School: {row['School']}<br>Status: {status}",
        name=str(row['School']) # Search ke liye
    ).add_to(fg)

# 3. Search Plugin
Search(layer=fg, geom_type='Point', placeholder='Search School...', 
       collapsed=False, search_label='name').add_to(m)

# --- MAP DISPLAY FIX ---
# Agar st_folium show nahi ho raha, toh folium_static use karein
try:
    st.subheader("Map View")
    # Method 1: Interactive (New)
    st_folium(m, width=1200, height=600, key="main_map")
except:
    # Method 2: Static (Backup)
    folium_static(m, width=1200, height=600)
