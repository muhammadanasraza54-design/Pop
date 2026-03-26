import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from folium.plugins import MarkerCluster

# 1. Page Layout (Hamesha top par)
st.set_page_config(page_title="TCF Schools Map", layout="wide")

FILE_NAME = "SSR_Final_Fixed.xlsx"

@st.cache_data
def load_data():
    try:
        df = pd.read_excel(FILE_NAME)
        # Column names ko lowercase kar rahe hain taake matching mein masla na ho
        df.columns = df.columns.str.lower().str.strip()
        
        # ID column ko string mein convert kar rahe hain search ke liye
        # Aapki sheet ke mutabiq ID column ka naam 'id' ya 'school id' ho sakta hai
        id_col = [col for col in df.columns if 'id' in col or 'code' in col][0]
        df['search_id'] = df[id_col].astype(str)
        
        return df, id_col
    except Exception as e:
        st.error(f"Excel Error: {e}")
        return None, None

try:
    data, original_id_col = load_data()
    
    if data is not None:
        st.sidebar.title("🔍 Search Schools")
        
        # Search Options
        search_mode = st.sidebar.radio("Search by:", ["All Schools", "School Name", "School ID"])
        
        selected_row = None
        
        if search_mode == "School Name":
            name_search = st.sidebar.selectbox("School Name chunein:", sorted(data['school'].unique()))
            selected_row = data[data['school'] == name_search].iloc[0]
            
        elif search_mode == "School ID":
            id_search = st.sidebar.selectbox("School ID chunein:", sorted(data['search_id'].unique()))
            selected_row = data[data['search_id'] == id_search].iloc[0]

        # Map Setup (Satellite View)
        # Location center set karein (Searched school par ya Pakistan ke center par)
        if selected_row is not None:
            map_center = [selected_row['lat'], selected_row['lon']]
            zoom_lvl = 16
        else:
            map_center = [30.3753, 69.3451]
            zoom_lvl = 5

        # Esri World Imagery (Satellite)
        m = folium.Map(location=map_center, zoom_start=zoom_lvl, tiles="Esri.WorldImagery")
        folium.TileLayer('OpenStreetMap', name='Normal Map').add_to(m)
        folium.LayerControl().add_to(m)

        st.title("🇵🇰 TCF Schools Interactive Satellite Map")

        # Marker Cluster
        marker_cluster = MarkerCluster(name="School Clusters").add_to(m)

        # Pins Lagana
        for index, row in data.iterrows():
            if pd.notnull(row['lat']) and pd.notnull(row['lon']):
                popup_text = f"<b>School:</b> {row['school']}<br><b>ID:</b> {row['search_id']}"
                
                # Agar search kiya gaya hai to us pin ko highlight karein
                if selected_row is not None and row['search_id'] == selected_row['search_id']:
                    folium.Marker(
                        location=[row['lat'], row['lon']],
                        popup=popup_text,
                        tooltip=row['school'],
                        icon=folium.Icon(color='red', icon='star')
                    ).add_to(m) # Yeh cluster se bahar dikhayega highlight ke liye
                else:
                    folium.Marker(
                        location=[row['lat'], row['lon']],
                        popup=popup_text,
                        tooltip=row['school'],
                        icon=folium.Icon(color='green', icon='school', prefix='fa')
                    ).add_to(marker_cluster)

        # Map display
        folium_static(m, width=1300, height=750)

except Exception as e:
    st.error(f"Application Error: {e}")
