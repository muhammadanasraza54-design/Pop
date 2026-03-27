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

# File Path (Ensure these exist in your GitHub repo)
EXCEL_FILE = "SSR_Final_Fixed.xlsx"
TIF_FILE = "po tcf.tif" 

# --- Functions ---
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
        # Memory efficient loading
        da = rioxarray.open_rasterio(TIF_FILE, chunks={'x': 512, 'y': 512})
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

# --- Main Logic ---
st.title("🇵🇰 PK TCF Schools & Population Density Map Tool")

# Sidebar
st.sidebar.title("🛠️ Tools & Controls")
selected_radius = st.sidebar.slider("Select Radius (KM):", 1, 10, 2)

data = load_excel_data()
da_pop = load_population_data()

if data is not None:
    # 1. Create Base Map
    m = folium.Map(location=[30.3753, 69.3451], zoom_start=6, tiles=None)
    folium.TileLayer('OpenStreetMap', name='Street Map').add_to(m)
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google', name='Google Satellite', overlay=True, control=True
    ).add_to(m)

    # 2. Add Schools (FeatureGroup for Search)
    school_group = folium.FeatureGroup(name="Schools", show=True).add_to(m)
    marker_cluster = MarkerCluster(name="TCF Clusters").add_to(m)

    for _, row in data.iterrows():
        status = str(row.get('Status', 'N/A')).upper()
        m_color = 'red' if 'PR' in status else 'blue' if 'SC' in status else 'green'
        
        # Search properties must be in 'name' or 'label'
        marker = folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=6, color=m_color, fill=True,
            popup=f"School: {row['School']}<br>ID: {row['search_id']}",
            name=str(row['School']) # This is for Search plugin
        )
        marker.add_to(marker_cluster)
        marker.add_to(school_group)

    # 3. Add Search (Fixed logic to avoid AssertionError)
    Search(
        layer=school_group,
        geom_type='Point',
        placeholder='Search School Name',
        collapsed=False,
        search_label='name',
        weight=2
    ).add_to(m)

    folium.LayerControl().add_to(m)

    # 4. Render Map and Catch Output
    # Use a unique key for st_folium
    map_output = st_folium(m, width=1350, height=700, key="tcf_map_v3")

    # 5. Handle Click / Population
    click_data = None
    if map_output.get("last_clicked"):
        click_data = map_output["last_clicked"]
    elif map_output.get("last_object_clicked"):
        click_data = map_output["last_object_clicked"]

    if click_data:
        lat, lon = click_data['lat'], click_data['lng']
        pop_val = calculate_population(da_pop, lat, lon, selected_radius)
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("📍 Selection Info")
        st.sidebar.write(f"Coordinates: `{lat:.5f}, {lon:.5f}`")
        if pop_val is not None:
            st.sidebar.metric(f"Population ({selected_radius}km)", f"{pop_val:,}")
        else:
            st.sidebar.warning("Population data not found here.")
