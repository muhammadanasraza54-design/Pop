import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from folium.plugins import MarkerCluster

# 1. Page Layout
st.set_page_config(page_title="TCF Schools Map", layout="wide")

FILE_NAME = "SSR_Final_Fixed.xlsx"

@st.cache_data
def load_data():
    try:
        df = pd.read_excel(FILE_NAME)
        # Column names ko clean karna
        df.columns = df.columns.str.lower().str.strip()
        
        # ID column dhoondna
        id_cols = [col for col in df.columns if 'id' in col or 'code' in col]
        id_col = id_cols[0] if id_cols else df.columns[0]
        df['search_id'] = df[id_col].astype(str)
        
        return df
    except Exception as e:
        st.error(f"Excel File Error: {e}")
        return None

try:
    data = load_data()
    
    if data is not None:
        st.title("🇵🇰 TCF Schools Interactive Satellite Map")
        
        # --- Sidebar Search ---
        st.sidebar.title("🔍 Search Options")
        search_mode = st.sidebar.radio("Search by:", ["All Schools", "School Name", "School ID"])
        
        selected_row = None
        if search_mode == "School Name":
            name_search = st.sidebar.selectbox("School Name chunein:", sorted(data['school'].dropna().unique()))
            selected_row = data[data['school'] == name_search].iloc[0]
        elif search_mode == "School ID":
            id_search = st.sidebar.selectbox("School ID chunein:", sorted(data['search_id'].dropna().unique()))
            selected_row = data[data['search_id'] == id_search].iloc[0]

        # --- Map Setup ---
        if selected_row is not None:
            map_center = [selected_row['lat'], selected_row['lon']]
            zoom_lvl = 17
        else:
            map_center = [30.3753, 69.3451]
            zoom_lvl = 6

        # Google Satellite Hybrid Tiles (Zyada behtar chalti hain)
        m = folium.Map(
            location=map_center, 
            zoom_start=zoom_lvl, 
            tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
            attr='Google'
        )
        
        # Cluster setup
        marker_cluster = MarkerCluster(name="TCF Clusters").add_to(m)

        # --- Pins Lagana ---
        for index, row in data.iterrows():
            if pd.notnull(row['lat']) and pd.notnull(row['lon']):
                popup_html = f"<b>School:</b> {row['school']}<br><b>ID:</b> {row['search_id']}"
                
                # Agar search kiya gaya school hai
                if selected_row is not None and str(row['search_id']) == str(selected_row['search_id']):
                    folium.Marker(
                        location=[row['lat'], row['lon']],
                        popup=folium.Popup(popup_html, max_width=300),
                        tooltip=row['school'],
                        icon=folium.Icon(color='red', icon='star')
                    ).add_to(m) # Yeh cluster se bahar dikhayega taake foran nazar aaye
                else:
                    # Baaki sab clusters mein
                    folium.Marker(
                        location=[row['lat'], row['lon']],
                        popup=folium.Popup(popup_html, max_width=300),
                        tooltip=row['school'],
                        icon=folium.Icon(color='green', icon='info-sign')
                    ).add_to(marker_cluster)

        # Map display
        folium_static(m, width=1350, height=750)

except Exception as e:
    st.error(f"App mein masla hai: {e}")
