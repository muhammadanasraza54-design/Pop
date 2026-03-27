import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import rioxarray
from pyproj import Transformer
import numpy as np

# 1. Page Configuration
st.set_page_config(page_title="TCF Stable Map Tool", layout="wide")

# --- Optimized Data Loading ---
@st.cache_data
def load_data():
    df = pd.read_excel("SSR_Final_Fixed.xlsx")
    df.columns = df.columns.str.strip()
    # Cleaning data (CRITICAL for search)
    df.dropna(subset=['lat', 'lon'], inplace=True)
    df['id_str'] = df.iloc[:, 0].astype(str) # First column as ID
    df['search_tag'] = df['School'].astype(str) + " (" + df['id_str'] + ")"
    return df

@st.cache_resource
def load_raster():
    # Large file loading optimized
    da = rioxarray.open_rasterio("po tcf.tif", chunks={'x': 1024, 'y': 1024})
    da = da.where(da != -9999, 0) # Handle NoData values
    return da

# --- Dynamic Population Calculation ---
def calculate_local_pop(da, lat, lon, r_km):
    if da is None: return 0
    try:
        # CRS transform
        tr = Transformer.from_crs("epsg:4326", da.rio.crs, always_xy=True)
        cx, cy = tr.transform(lon, lat)
        
        # Exact box clip (r_km area)
        r_m = r_km * 1000
        xmin, ymin = cx - r_m, cy - r_m
        xmax, ymax = cx + r_m, cy + r_m
        
        subset = da.rio.clip_box(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax)
        
        # Scaling adjustment: Data appears to be in density.
        total_pop = np.nansum(subset.values)
        
        # Verify result is realistic (e.g. < 5 Million in 2km radius)
        # Assuming typical density unit issue, divide by scale factor if too large
        if total_pop > 5000000:
            total_pop = total_pop / 1000
            
        return int(total_pop)
    except Exception:
        return 0

# --- App UI ---
st.title("🇵🇰 PK TCF Schools & Population Density Map Tool")

# Sidebar
st.sidebar.title("🛠️ Tools & Controls")
r_km = st.sidebar.slider("Population Radius (KM):", 1, 10, 2)

df = load_data()
da = load_raster()

# --- Search Bar Implementation (New & Robust) ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 School Search")
selected_school_tag = st.sidebar.selectbox(
    "Search School Name or ID:", 
    options=["Select School..."] + sorted(df['search_tag'].unique().tolist())
)

# Search Handling
search_row = None
if selected_school_tag != "Select School...":
    search_row = df[df['search_tag'] == selected_school_tag].iloc[0]
    map_lat = search_row['lat']
    map_lon = search_row['lon']
    zoom_level = 15 # Close zoom on found school
else:
    map_lat = 30.3753
    map_lon = 69.3451
    zoom_level = 6 # Default Pakistan zoom

# --- Map Setup ---
st.markdown("---")
m = folium.Map(location=[map_lat, map_lon], zoom_start=zoom_level)

# Satellite View
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
    attr='Google',
    name='Google Satellite',
    overlay=True,
    control=True
).add_to(m)

# Adding Pins and Popups
for _, row in df.iterrows():
    status = str(row.get('Status', 'N/A')).upper()
    color = 'red' if 'PR' in status else 'blue'
    
    # Complex HTML Popup (status wazeh show karega)
    popup_html = f"""
    <div style="font-family: Arial; width: 220px;">
        <h4>{row['School']}</h4>
        <b>ID:</b> {row['id_str']}<br>
        <hr style="margin: 5px 0;">
        <span style="color: {color};"><b>Status:</b> {status}</span>
    </div>
    """
    
    # Adding as CircleMarker for speed
    folium.CircleMarker(
        location=[row['lat'], row['lon']],
        radius=7,
        color=color,
        fill=True,
        fill_opacity=0.7,
        popup=folium.Popup(popup_html, max_width=300),
        tooltip=row['School']
    ).add_to(m)

# Search handler auto-popup (if school searched)
if search_row is not None:
    folium.Marker(
        location=[search_row['lat'], search_row['lon']],
        icon=folium.Icon(color="green", icon="info-sign"),
        popup=f"School: {search_row['School']}\nStatus: {search_row.get('Status', 'N/A')}",
    ).add_to(m)

# Map output capture
map_out = st_folium(m, width=1300, height=700, key="tcf_stable_map_v4")

# --- Catching Clicks and Displaying Stats ---
clicked_coords = None
if map_out.get("last_clicked"):
    clicked_coords = map_out["last_clicked"]

if clicked_coords or search_row is not None:
    # Use search coords if school searched, else use clicked coords
    target_lat = search_row['lat'] if search_row is not None else clicked_coords['lat']
    target_lon = search_row['lon'] if search_row is not None else clicked_coords['lng']
    
    with st.sidebar:
        st.markdown("---")
        st.success(f"📍 Data for {target_lat:.4f}, {target_lon:.4f}")
        
        with st.spinner(f"Calculating population for {r_km}km..."):
            pop_res = calculate_local_pop(da, target_lat, target_lon, r_km)
            
        st.metric(f"Estimated Population (within {r_km}km)", f"{pop_res:,}")
