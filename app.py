import streamlit as st
import pandas as pd
import folium
from folium.plugins import Search
from streamlit_folium import st_folium
import rioxarray
import numpy as np
from pyproj import Transformer
from shapely.geometry import Point

st.set_page_config(page_title="TCF School Analysis Tool", layout="wide")

# --- Data Loading ---
@st.cache_data
def load_excel():
    df = pd.read_excel("SSR_Final_Fixed.xlsx")
    df.columns = df.columns.str.strip()
    # Search ke liye clean name
    df['search_name'] = df['School'].astype(str) + " - " + df['Status'].astype(str)
    return df

@st.cache_resource
def load_raster():
    da = rioxarray.open_rasterio("po tcf.tif", chunks=True)
    return da

def get_pop(da, lat, lon, r_km):
    try:
        # CRS transform
        tr = Transformer.from_crs("epsg:4326", da.rio.crs, always_xy=True)
        cx, cy = tr.transform(lon, lat)
        
        # Buffer area (Radius)
        r_m = r_km * 1000
        # Sirf selected area ko clip karna
        subset = da.rio.clip_box(minx=cx-r_m, miny=cy-r_m, maxx=cx+r_m, maxy=cy+r_m)
        
        # Population values sum (NoData values ko zero kar ke)
        data_vals = subset.values
        total = np.nansum(data_vals[data_vals > 0])
        
        # Scaling adjustment (agar data density mein hai)
        return int(total) if total < 2000000 else int(total / 100)
    except:
        return 0

# --- UI ---
st.title("🇵🇰 TCF Schools & Population Density Tool")
r_km = st.sidebar.slider("Radius (KM):", 1, 10, 2)

df = load_excel()
da = load_raster()

# Map Setup
m = folium.Map(location=[30.3753, 69.3451], zoom_start=6)
folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                 attr='Google', name='Satellite').add_to(m)

# Searchable Layer
fg = folium.FeatureGroup(name="Schools").add_to(m)

for _, row in df.iterrows():
    status = str(row.get('Status', 'N/A')).upper()
    color = 'red' if 'PR' in status else 'blue'
    
    # Popup with Status
    popup_html = f"""
    <div style="font-family: Arial; font-size: 12px;">
        <b style="color: {color};">{row['School']}</b><br>
        <hr style="margin: 5px 0;">
        <b>Status:</b> {status}<br>
        <b>ID:</b> {row.iloc[0]}
    </div>
    """
    
    # Circle Marker
    folium.CircleMarker(
        location=[row['lat'], row['lon']],
        radius=6, color=color, fill=True, fill_opacity=0.8,
        popup=folium.Popup(popup_html, max_width=250),
        name=row['search_name'] # Search label
    ).add_to(fg)

# Search Plugin Fix
Search(layer=fg, geom_type='Point', placeholder='School Name...',
       collapsed=False, search_label='name').add_to(m)

# Display Map
map_out = st_folium(m, width=1200, height=650, key="tcf_final_v5")

# --- Click Result ---
click = map_out.get("last_clicked")
if click:
    lat, lon = click['lat'], click['lng']
    with st.sidebar:
        st.markdown("---")
        st.subheader("📍 Location Stats")
        with st.spinner("Calculating..."):
            val = get_pop(da, lat, lon, r_km)
        st.metric(f"Population ({r_km}km)", f"{val:,}")
        st.write(f"Coords: {lat:.4f}, {lon:.4f}")
