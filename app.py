import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from folium.plugins import MarkerCluster
import rasterio
from rasterio.plot import reshape_as_image
import numpy as np
from shapely.geometry import Point
from pyproj import Transformer
import json

# 1. Page Layout
st.set_page_config(page_title="TCF Schools & Population Map", layout="wide")

# Files ke naam
EXCEL_FILE = "SSR_Final_Fixed.xlsx"
TIF_FILE = "po tcf.tif" # Jo aapne nayi upload ki hai

# --- Data Loading Function ---
@st.cache_data
def load_excel_data():
    try:
        df = pd.read_excel(EXCEL_FILE)
        df.columns = df.columns.str.strip()
        id_col = [col for col in df.columns if 'ID' in col.upper() or 'CODE' in col.upper()][0]
        df['search_id'] = df[id_col].astype(str)
        return df
    except Exception as e:
        st.error(f"Excel Error: {e}")
        return None

# --- Population Calculation Function (Advanced) ---
def get_population_in_radius(lat, lon, radius_km):
    try:
        with rasterio.open(TIF_FILE) as src:
            # Lat/Lon ko TIF ke coordinates mein convert karna
            transformer = Transformer.from_crs("epsg:4326", src.crs, always_xy=True)
            center_x, center_y = transformer.transform(lon, lat)
            
            # 1 pixel approx 100m hai
            pixel_size_m = src.res[0] 
            radius_m = radius_km * 1000
            pixel_radius = int(radius_m / pixel_size_m)

            # Center pixel index dhoondna
            row, col = src.index(center_x, center_y)

            # Us pixel ke gird window read karna
            window = rasterio.windows.Window(
                col - pixel_radius, 
                row - pixel_radius, 
                pixel_radius * 2, 
                pixel_radius * 2
            )
            
            # Data read karna aur empty cells ko zero karna
            data = src.read(1, window=window, boundless=True, fill_value=0)
            
            # Total population sum karna
            total_pop = np.sum(data)
            return int(total_pop)
    except Exception as e:
        st.sidebar.warning(f"Population calc error: {e}")
        return None

# --- Main App ---
st.title("🇵🇰 TCF Schools & Population Density Map")

data = load_excel_data()

# Initialize session state for population display
if 'clicked_info' not in st.session_state:
    st.session_state.clicked_info = None

# 1. Sidebar Control
st.sidebar.title("Population Radius Tool")
st.sidebar.markdown("Map par kahin bhi click karein aur niche radius select karein:")
selected_radius = st.sidebar.slider("Radius (KM):", min_value=1, max_value=10, value=2)

# Display clicked population status in sidebar
if st.session_state.clicked_info:
    info = st.session_state.clicked_info
    st.sidebar.success(f"📍 Location: {info['lat']:.4f}, {info['lon']:.4f}")
    st.sidebar.metric(label=f"Total Population (within {selected_radius}km)", value=f"{info['pop']:,}")

st.markdown("---")

if data is not None:
    # --- Map Setup ---
    # Mouse Click handler add karne ke liye script
    map_id = "main_map"
    m = folium.Map(location=[30.3753, 69.3451], zoom_start=6, tiles=None, id=map_id)
    
    # Base Layers
    folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Google Satellite').add_to(m)
    folium.TileLayer('OpenStreetMap', name='Street Map').add_to(m)

    # 1. Raster Population Layer (visuals only)
    try:
        with rasterio.open(TIF_FILE) as src:
            img = src.read(1)
            # visual representation (basic normalization)
            img_norm = (img - np.nanmin(img)) / (np.nanmax(img) - np.nanmin(img))
            bounds = [[src.bounds.bottom, src.bounds.left], [src.bounds.top, src.bounds.right]]
            folium.raster_layers.ImageOverlay(
                image=img_norm,
                bounds=bounds,
                opacity=0.4,
                name="Population Density (Visual)",
                colormap=lambda x: (1, 0, 0, x)
            ).add_to(m)
    except:
        st.sidebar.warning("Visual population map load nahi ho saki.")

    # 2. Add School Markers (Clusters)
    marker_cluster = MarkerCluster(name="TCF Schools").add_to(m)
    for index, row in data.iterrows():
        if pd.notnull(row['lat']) and pd.notnull(row['lon']):
            # Behtar popup style (image 13 ke mutabiq)
            popup_html = f"""
            <div style="font-family: Arial; width: 220px; font-size: 13px;">
                <h4 style="margin-bottom:5px; color: green;">{row['School']}</h4>
                <b>ID:</b> {row['search_id']}<br>
                <b>Region:</b> {row.get('Region', 'N/A')}<br>
                <b>Status:</b> {row.get('Status', 'N/A')}<br>
                <b>Utilization:</b> {row.get('Operational Utilization', 'N/A')}<br>
                <hr style="margin: 5px 0;">
                <span style="color: #e91e63;"><b>Girls:</b> {row.get('Girls %', '0')}%</span> | 
                <span style="color: #2196f3;"><b>Boys:</b> {row.get('Boys %', '0')}%</span>
            </div>
            """
            folium.Marker(
                location=[row['lat'], row['lon']],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=row['School'],
                icon=folium.Icon(color='green', icon='info-sign')
            ).add_to(marker_cluster)

    # 3. Handle Mouse Click (THE IMPORTANT PART)
    # Folium click location recapture karne ke liye special hack
    folium.LatLngPopup().add_to(m) # Yeh click karne par lat/lon ka popup dikhayega
    
    # Render map
    output = folium_static(m, width=1350, height=750)

    # Click events recapture logic
    # st.write(output) # debug output check karne ke liye

    # Check if a point was clicked usingstreamlit-folium callback
    if output['last_object_clicked']:
        # if a marker was clicked, the latlngpopup wont trigger properly, this logic needs refinement but works for blank spaces
        pass 
    
    if output['last_clicked']:
        clicked_lat = output['last_clicked']['lat']
        clicked_lon = output['last_clicked']['lng']
        
        # Calculate population for this point
        calculated_pop = get_population_in_radius(clicked_lat, clicked_lon, selected_radius)
        
        # Store in session state to display in sidebar
        if calculated_pop is not None:
            st.session_state.clicked_info = {
                'lat': clicked_lat,
                'lon': clicked_lon,
                'pop': calculated_pop
            }
            # Rerun to update sidebar
            st.experimental_rerun()

    folium.LayerControl().add_to(m)

else:
    st.error("Excel data load nahi ho saka.")
