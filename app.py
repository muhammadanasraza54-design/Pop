import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from folium.plugins import MarkerCluster

# 1. Page layout set karein (Hamesha sab se upar hona chahiye)
st.set_page_config(page_title="TCF Schools Map", layout="wide")

# Excel file ka naam (Ensure karein ke folder mein yahi naam ho)
FILE_NAME = "SSR_Final_Fixed.xlsx"

@st.cache_data
def load_data():
    # Excel read karein
    try:
        df = pd.read_excel(FILE_NAME)
        
        # Check karein ke column names sahi hain
        # Excel mein agar lowercase/uppercase headings hon to ye unhein standard kar dega
        df.columns = df.columns.str.lower()
        
        # Agar 'School ID' column nahi hai, to example dekar check karein
        # Assuming your ID column is named 'school id' or similar
        potential_id_cols = [col for col in df.columns if 'id' in col or 'code' in col]
        if potential_id_cols:
            df['school_id_str'] = df[potential_id_cols[0]].astype(str) # String mein convert karein for easy search
        else:
            df['school_id_str'] = "" # Khali ID agar nahi milta
            
        return df
    except Exception as e:
        st.error(f"Excel read karne mein masla hua: {e}")
        return None

try:
    data = load_data()
    if data is not None:
        st.title("🇵🇰 TCF Schools Mapping Dashboard")
        st.markdown("Is map mein ab satellite view aur school ID search maujood hai.")

        # Pakistan ke coordinates par map start karein
        # Satellite view (tiles="Esri.WorldImagery") set kiya hai
        m = folium.Map(location=[30.3753, 69.3451], zoom_start=5, tiles="Esri.WorldImagery")
        
        # OpenStreetMap bhi alternate tile layer ke taur par add karein
        folium.TileLayer('OpenStreetMap').add_to(m)
        folium.LayerControl().add_to(m) # User ko layer switch karne ka option dein

        # Marker Cluster banayein (Ye pins ko group kar deta hai taake map fast chale)
        marker_cluster = MarkerCluster().add_to(m)

        # 1. SEARCH BAR - School ID sy (Hamesha map ke upar rakhna hai)
        # Assuming ID column is in lower case 'school id' or derived 'school_id_str'
        school_id_options = data['school_id_str'].dropna().unique().tolist()
        
        st.sidebar.markdown("### Search")
        search_id = st.sidebar.selectbox("School ID select karein:", ["Sab Dikhaein"] + school_id_options)

        if search_id != "Sab Dikhaein":
            # Sirf selected school ka data nikalen
            selected_school_data = data[data['school_id_str'] == search_id]
            if not selected_school_data.empty:
                row = selected_school_data.iloc[0]
                lats = row['lat']
                lons = row['lon']
                name = row['school']

                if pd.notnull(lats) and pd.notnull(lons):
                    # Map ko searched school par center karein aur zoom karein
                    m = folium.Map(location=[lats, lons], zoom_start=15, tiles="Esri.WorldImagery")
                    folium.TileLayer('OpenStreetMap').add_to(m)
                    folium.LayerControl().add_to(m)
                    
                    # Single pin searched school ke liye
                    folium.Marker(
                        location=[lats, lons],
                        popup=f"<b>School ID:</b> {search_id}<br><b>School Name:</b><br>{name}",
                        tooltip=f"{name} ({search_id})",
                        icon=folium.Icon(color='red', icon='school', prefix='fa')
                    ).add_to(m)
            else:
                st.sidebar.warning("Selected School ID ke liye coordinates nahi mile.")

        else:
            # "Sab Dikhaein" ke liye purana cluster loop chalaein
            for index, row in data.iterrows():
                # Column names: 'lat', 'lon', 'school', 'school_id_str'
                lats = row['lat']
                lons = row['lon']
                name = row['school']
                id_str = row['school_id_str']

                # Check karein ke coordinates khali na hon
                if pd.notnull(lats) and pd.notnull(lons):
                    folium.Marker(
                        location=[lats, lons],
                        popup=f"<b>School ID:</b> {id_str}<br><b>School Name:</b><br>{name}",
                        tooltip=name,
                        icon=folium.Icon(color='green', icon='school', prefix='fa')
                    ).add_to(marker_cluster) # Cluster mein add kiya

        # Map ko screen par dikhayein
        folium_static(m, width=1350, height=700)

except Exception as e:
    st.error(f"Error: {e}")
    st.info("Ensure karein ke Excel mein 'lat', 'lon', 'School' aur ID headings maujood hain.")
