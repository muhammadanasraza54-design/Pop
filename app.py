import streamlit as st
import pandas as pd
import folium
from folium.plugins import Search
from streamlit_folium import st_folium
import rioxarray
import numpy as np
from pyproj import Transformer

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
    da = rioxarray.open_rasterio(TIF_FILE, chunks=True)
    # NoData handling taake negative values na aayein
    if da.rio.nodata is not None:
        da = da.where(da != da.rio.nodata, 0)
    else:
        da = da.where(da >= 0, 0)
    return da

def get_pop(da, lat, lon, r_km):
    try:
        tr = Transformer.from_crs("epsg:4326", da.rio.crs, always_xy=True)
        cx, cy = tr.transform(lon, lat)
        r_m = r_km * 1000
        # Exact box clip
        subset = da.rio.clip_box(minx=cx-r_m, miny=cy-r_m, maxx=cx+r_m, maxy=cy+r_m)
        # Nansum taake srif numbers count hon
        total = int(np.nansum(subset.values))
        return abs(total) # Negative value block
    except:
        return 0

# UI
st.title("PK TCF School Analysis Tool")
r_km = st.sidebar.slider("Select Radius (KM):", 1, 10, 2)

df = load_excel()
da = load_raster()

# Map - Simple and Fast
m = folium.Map(location=[30.3753, 69.3451], zoom_start=6, control_scale=True)
folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                 attr='Google', name='Satellite').add_to(m)

# School Markers (No Clusters)
# Individual points fast hoti hain agar CircleMarker use karein
search_group = folium.FeatureGroup(name="Schools").add_to(m)

for _, row in df.iterrows():
    status = str(row.get('Status', 'N/A')).upper()
    color = 'red' if 'PR' in status else 'blue'
    
    label = f"{row['School']} | Status: {status}"
    
    folium.CircleMarker(
        location=[row['lat'], row['lon']],
        radius=5,
        color=color,
        fill=True,
        fill_opacity=0.8,
        tooltip=label, # Mouse le jane par status dikhega
        popup=label,   # Click par status dikhega
        name=label
    ).add_to(search_group)

# Search Bar
Search(layer=search_group, geom_type='Point', placeholder='School Name...',
       collapsed=False, search_label='name').add_to(m)

# Output
out = st_folium(m, width=1100, height=600, key="tcf_final_v1")

# Population logic
click = out.get("last_clicked")
if click:
    lat, lon = click['lat'], click['lng']
    st.sidebar.markdown(f"### 📍 Stats for {r_km}KM")
    with st.sidebar.spinner("Calculating..."):
        pop_count = get_pop(da, lat, lon, r_km)
    
    if pop_count > 0:
        st.sidebar.success(f"Estimated Population: **{pop_count:,}**")
    else:
        st.sidebar.warning("No population data in this area.")
    st.sidebar.write(f"Lat: {lat:.4f}, Lon: {lon:.4f}")
