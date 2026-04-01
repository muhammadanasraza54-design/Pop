import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
import rasterio
from rasterio.windows import from_bounds
import math
import numpy as np
import os

# --- Page Config ---
st.set_page_config(page_title="TCF Engineering Map", layout="wide")

EXCEL_FILE = "SSR_Final_Fixed.xlsx"
POP_FILE = "pak_total_Pop FN.tif"

# --- Population calculation (Optimized & Cached) ---
@st.cache_data
def get_pop_data(lat, lon, rad_km):
    if not os.path.exists(POP_FILE): return 0
    try:
        # Optimization: Sirf valid coordinates par calculate karein
        if pd.isna(lat) or pd.isna(lon): return 0
        
        deg_lat = rad_km / 111.0
        deg_lon = rad_km / (111.0 * math.cos(math.radians(lat)))
        left, bottom, right, top = (lon - deg_lon, lat - deg_lat, lon + deg_lon, lat + deg_lat)
        
        with rasterio.open(POP_FILE) as ds:
            window = from_bounds(left, bottom, right, top, ds.transform)
            data = ds.read(1, window=window, boundless=True, fill_value=0)
            return int(np.nansum(data[data > 0]))
    except: 
        return 0

# --- Data Loading & Cleaning ---
@st.cache_data(show_spinner="Loading Data...")
def load_data():
    try:
        df = pd.read_excel(EXCEL_FILE)
        df.columns = df.columns.str.strip()
        
        # Missing coordinates wali rows delete karna taake map crash na ho
        df = df.dropna(subset=['lat', 'lon'])
        df = df[(df['lat'] != 0) & (df['lon'] != 0)]
        
        id_cols = [col for col in df.columns if 'ID' in col.upper() or 'CODE' in col.upper()]
        id_col = id_cols[0] if id_cols else df.columns[0]
        df['search_id'] = df[id_col].astype(str)
        return df
    except Exception as e:
        st.error(f"Excel File Error: {e}")
        return None

# --- Session State Management ---
if 'center' not in st.session_state: st.session_state.center = [30.3753, 69.3451]
if 'zoom' not in st.session_state: st.session_state.zoom = 6

# --- Sidebar ---
st.sidebar.title("🏗️ TCF Engineering")
df_full = load_data()
selected_row = None

if df_full is not None:
    # Map Filters
    st.sidebar.subheader("🌍 Map Filters")
    if 'Region' in df_full.columns:
        regions = ["All Regions"] + sorted(df_full['Region'].unique().astype(str).tolist())
        selected_region = st.sidebar.selectbox("Select Region:", regions)
        df = df_full[df_full['Region'] == selected_region] if selected_region != "All Regions" else df_full
    else:
        df = df_full

    # Search Schools
    st.sidebar.subheader("🔍 Search Schools")
    search_mode = st.sidebar.radio("Search by:", ["All Schools", "School Name", "School ID"])
    
    if search_mode == "School Name":
        name_list = ["Select..."] + sorted(df['School'].astype(str).unique().tolist())
        name = st.sidebar.selectbox("School Name:", name_list)
        if name != "Select...":
            selected_row = df[df['School'] == name].iloc[0]
            st.session_state.center = [selected_row['lat'], selected_row['lon']]
            st.session_state.zoom = 17
            
    elif search_mode == "School ID":
        id_list = ["Select..."] + sorted(df['search_id'].unique().tolist())
        sid = st.sidebar.selectbox("School ID:", id_list)
        if sid != "Select...":
            selected_row = df[df['search_id'] == sid].iloc[0]
            st.session_state.center = [selected_row['lat'], selected_row['lon']]
            st.session_state.zoom = 17

    st.sidebar.markdown("---")
    radius = st.sidebar.number_input("Radius (KM)", 0.1, 20.0, 2.0, 0.5)
    
    # --- Population Calculation & Distribution ---
total_pop = get_pop_data(st.session_state.center[0], st.session_state.center[1], radius)

if total_pop > 0:
    # Pakistan Census trends ke mutabiq approximate percentages
    primary_ratio = 0.135  # 13.5% (Age 5-9)
    secondary_ratio = 0.115 # 11.5% (Age 10-14)

    primary_kids = int(total_pop * primary_ratio)
    secondary_kids = int(total_pop * secondary_ratio)

    # Sidebar mein display karne ke liye
    st.sidebar.metric("📊 Total Population", f"{total_pop:,}")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("🎒 Primary (5-9)", f"{primary_kids:,}")
    with col2:
        st.metric("🏫 Secondary (10-14)", f"{secondary_kids:,}")

# --- Main Map View ---
st.title("🇵🇰 TCF Schools & Population Map")

m = folium.Map(
    location=st.session_state.center, 
    zoom_start=st.session_state.zoom, 
    tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
    attr='Google',
    control_scale=True,
    prefer_canvas=True
)

# Radius Circle at current center
folium.Circle(
    st.session_state.center, 
    radius=radius*1000, 
    color='red', 
    fill=True, 
    fill_opacity=0.1
).add_to(m)

# Marker Cluster
marker_cluster = MarkerCluster(disableClusteringAtZoom=16).add_to(m)

if df_full is not None:
    for _, row in df.iterrows():
        # --- 1. Excel se naye Fields uthayein ---
        status_raw = row.get('Status', 'N/A')
        # Agar 'M' hai to 'Operational' dikhayein, warna jo likha hai wahi
        status_text = "Operational" if status_raw == 'M' else status_raw
        
        util_val = row.get('Operational Utilization', 0.0)
        loc_detail = row.get('Location', 'N/A')
        dist_name = row.get('District', 'N/A')
        
        # Utilization ke liye color logic (100% se upar Red, warna Green)
        util_box_color = "#DC3545" if util_val > 100 else "#28A745"

        # --- 2. p_html ko update karein (Line 144 onwards) ---
        p_html = f"""
        <div style="font-family: 'Segoe UI', Arial; width: 260px; line-height: 1.5; padding: 5px;">
            <h4 style="color:#007BFF; margin:0 0 8px 0; border-bottom: 2px solid #007BFF; padding-bottom: 3px;">
                {row['School']}
            </h4>
            
            <p style="margin:3px 0;"><b>ID:</b> {row['search_id']}</p>
            <p style="margin:3px 0;"><b>Location:</b> {loc_detail}, {dist_name}</p>
            <p style="margin:3px 0;"><b>Status:</b> 
                <span style="color:#28A745; font-weight:bold;">{status_text}</span>
            </p>

            <div style="background-color:#f8f9fa; padding:10px; border-radius:5px; border-left:6px solid {util_box_color}; margin:10px 0;">
                <span style="font-size:0.85em; color:#666; text-transform: uppercase;">Operational Utilization</span><br>
                <b style="font-size:1.2em; color:{util_box_color};">{util_val}%</b>
            </div>

            <div style="display: flex; justify-content: space-between; margin-top: 5px; background: #eef2f7; padding: 5px; border-radius: 3px;">
                <span style="color:#E83E8C; font-weight:bold;">♀ Girls: {row.get('Girls %', 0)}%</span>
                <span style="color:#007BFF; font-weight:bold;">♂ Boys: {row.get('Boys %', 0)}%</span>
            </div>
        </div>
        """

        # --- Baqi code (is_sel aur Marker) waisa hi rahega ---
        is_sel = (selected_row is not None and 
                  str(row['search_id']) == str(selected_row['search_id']))
        
        folium.Marker(
            [row['lat'], row['lon']], 
            popup=folium.Popup(p_html, max_width=350),
            tooltip=row['School'],
            icon=folium.Icon(color='red' if is_sel else 'green', 
                             icon='star' if is_sel else 'info-sign')
        ).add_to(m if is_sel else marker_cluster)
# --- Map Output with Click Control ---
# Note: yahan humne zoom aur center ko st_folium ke parameters se control kiya hai
out = st_folium(
    m,
    center=st.session_state.center,
    zoom=st.session_state.zoom,
    key="tcf_map_final_optimized",
    width=1350,
    height=700,
    returned_objects=["zoom", "center", "last_clicked"], 
    use_container_width=True
)

# Interaction Logic (FIXED)
if out:
    # 1. Zoom persistence: Sirf tab update karein jab waqai change ho
    if out.get("zoom") is not None and out["zoom"] != st.session_state.zoom:
        st.session_state.zoom = out["zoom"]

    # 2. Click detection: Sirf click hone par center change karein
    # Is logic ko optimize kiya hai taake zoom karne par ye trigger na ho
    curr_clicked = out.get("last_clicked")
    
    if curr_clicked:
        click_lat = curr_clicked["lat"]
        click_lng = curr_clicked["lng"]
        
        # Check karein ke kya ye click purane center se mukhtalif hai?
        # precision check (0.0001) taake floating point error se rerun na ho
        if (abs(click_lat - st.session_state.center[0]) > 0.0001 or 
            abs(click_lng - st.session_state.center[1]) > 0.0001):
            
            st.session_state.center = [click_lat, click_lng]
            # Jab hum school search karte hain to zoom 17 hota hai, 
            # usko barqarar rakhne ke liye hum yahan zoom reset nahi karenge
            st.rerun()

    # 3. Map Panning: Agar user map move kare (click nahi), 
    # to center update karein baghair rerun kiye taake view jump na kare
    if out.get("center") is not None:
        new_center = [out["center"]["lat"], out["center"]["lng"]]
        if new_center != st.session_state.center:
            # Hum sirf state update kar rahe hain, rerun nahi
            st.session_state.center = new_center

