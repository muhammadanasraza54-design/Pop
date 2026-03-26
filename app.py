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
        # Column names ki extra spaces khatam karna
        df.columns = df.columns.str.strip()
        
        # ID column ko identify karna (Flexible search)
        id_col = [col for col in df.columns if 'ID' in col.upper() or 'CODE' in col.upper()][0]
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
        st.sidebar.title("🔍 Search Schools")
        search_mode = st.sidebar.radio("Search by:", ["All Schools", "School Name", "School ID"])
        
        selected_row = None
        if search_mode == "School Name":
            name_search = st.sidebar.selectbox("School Name chunein:", sorted(data['School'].dropna().unique()))
            selected_row = data[data['School'] == name_search].iloc[0]
        elif search_mode == "School ID":
            id_search = st.sidebar.selectbox("School ID chunein:", sorted(data['search_id'].dropna().unique()))
            selected_row = data[data['search_id'] == id_search].iloc[0]

        # --- Map Setup ---
        if selected_row is not None:
            map_center = [selected_row['lat'], selected_row['lon']]
            zoom_lvl = 18
        else:
            map_center = [30.3753, 69.3451]
            zoom_lvl = 6

        # Google Satellite Hybrid (Best performance)
        m = folium.Map(
            location=map_center, 
            zoom_start=zoom_lvl, 
            tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
            attr='Google'
        )
        
        marker_cluster = MarkerCluster(name="TCF Clusters").add_to(m)

        # --- Pins Lagana ---
        for index, row in data.iterrows():
            if pd.notnull(row['lat']) and pd.notnull(row['lon']):
                
                # Nayi details: Region aur Location add ki hain
                popup_html = f"""
                <div style="font-family: Arial; width: 220px; font-size: 13px;">
                    <h4 style="margin-bottom:5px; color: #007BFF;">{row['School']}</h4>
                    <b>ID:</b> {row['search_id']}<br>
                    <b>Region:</b> {row.get('Region', 'N/A')}<br>
                    <b>Status:</b> {row.get('Status', 'N/A')}<br>
                    <b>Utilization:</b> {row.get('Operational Utilization', 'N/A')}<br>
                    <hr style="margin: 5px 0;">
                    <b>Location:</b> <span style="font-size: 11px; color: #555;">{row.get('Location', 'Address not found')}</span><br>
                    <hr style="margin: 5px 0;">
                    <span style="color: #e91e63;"><b>Girls:</b> {row.get('Girls %', '0')}%</span> | 
                    <span style="color: #2196f3;"><b>Boys:</b> {row.get('Boys %', '0')}%</span>
                </div>
                """
                
                if selected_row is not None and str(row['search_id']) == str(selected_row['search_id']):
                    folium.Marker(
                        location=[row['lat'], row['lon']],
                        popup=folium.Popup(popup_html, max_width=300),
                        tooltip=f"FOUND: {row['School']}",
                        icon=folium.Icon(color='red', icon='star')
                    ).add_to(m)
                else:
                    folium.Marker(
                        location=[row['lat'], row['lon']],
                        popup=folium.Popup(popup_html, max_width=300),
                        tooltip=row['School'],
                        icon=folium.Icon(color='green', icon='info-sign')
                    ).add_to(marker_cluster)

        folium_static(m, width=1350, height=750)

except Exception as e:
    st.error(f"App Error: {e}")
