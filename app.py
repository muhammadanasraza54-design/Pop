import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import rasterio
import numpy as np
from pyproj import Transformer

# 1. Page Layout
st.set_page_config(page_title="TCF Schools & Population Map", layout="wide")

# Files ke naam (Check karein ke GitHub par bilkul yehi naam hain)
EXCEL_FILE = "SSR_Final_Fixed.xlsx"
TIF_FILE = "po tcf.tif" 

# --- Data Loading Function ---
@st.cache_data
def load_excel_data():
    try:
        df = pd.read_excel(EXCEL_FILE)
        df.columns = df.columns.str.strip()
        # ID column dhoondna
        id_col = [col for col in df.columns if 'ID' in col.upper() or 'CODE' in col.upper()][0]
        df['search_id'] = df[id_col].astype(str)
        return df
    except Exception as e:
        st.error(f"Excel Error: {e}")
        return None

# --- Population Calculation Function ---
def get_population_in_radius(lat, lon, radius_km):
    try:
        with rasterio.open(TIF_FILE) as src:
            # Lat/Lon ko TIF ke coordinates mein convert karna
            transformer = Transformer.from_crs("epsg:4326", src.crs, always_xy=True)
            center_x, center_y = transformer.transform(lon, lat)
            
            # Resolution ke mutabiq radius pixels mein convert karna
            pixel_size_m = src.res[0] 
            radius_m = radius_km * 1000
            pixel_radius = int(radius_m / pixel_size_m)

            # Center pixel index
            row, col = src.index(center_x, center_y)

            # Window read karna
            window = rasterio.windows.Window(
                col - pixel_radius, 
                row - pixel_radius, 
                pixel_radius * 2, 
                pixel_radius * 2
            )
            
            data = src.read(1, window=window, boundless=True, fill_value=0)
            total_pop = np.sum(data[data > 0]) # Negative values ko ignore karein
            return int(total_pop)
    except Exception as e:
        return None

# --- UI Setup ---
st.title("🇵🇰 TCF Schools & Population Density Map")

# Sidebar for controls
st.sidebar.title("Population Tool")
selected_radius = st.sidebar.slider("Select Radius (KM):", 1, 10, 2)
st.sidebar.info("Map par kahin bhi click karein population check karne ke liye.")

data = load_excel_data()

if data is not None:
    # Map create karna
    m = folium.Map(location=[30.3753, 69.3451], zoom_start=6)
    
    # Google Satellite Layer
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Satellite'
    ).add_to(m)

    # Markers add karna
    for _, row in data.iterrows():
        if pd.notnull(row['lat']) and pd.notnull(row['lon']):
            popup_text = f"School: {row['School']}<br>ID: {row['search_id']}"
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=5,
                color='green',
                fill=True,
                popup=popup_text
            ).add_to(m)

    # Render Map and get click data
    # folium_static ki jagah st_folium istemal ho raha hai
    map_data = st_folium(m, width=1100, height=600)

    # Click handle karna
    if map_data and map_data.get("last_clicked"):
        clicked_lat = map_data["last_clicked"]["lat"]
        clicked_lon = map_data["last_clicked"]["lng"]
        
        pop_count = get_population_in_radius(clicked_lat, clicked_lon, selected_radius)
        
        # Clicked location par circle dikhane ke liye aur result sidebar mein
        st.sidebar.markdown("---")
        st.sidebar.success(f"📍 Selected Point: {clicked_lat:.4f}, {clicked_lon:.4f}")
        if pop_count is not None:
            st.sidebar.metric(label=f"Total Population ({selected_radius}km)", value=f"{pop_count:,}")
        else:
            st.sidebar.error("Population data not available for this point.")
else:
    st.error("Excel data file nahi mili.")
