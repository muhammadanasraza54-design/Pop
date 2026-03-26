import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from folium.plugins import MarkerCluster

# 1. Page layout set karein (Ye hamesha sab se upar hona chahiye)
st.set_page_config(page_title="TCF Pakistan Map", layout="wide")

# Excel file ka naam
FILE_NAME = "SSR_Final_Fixed.xlsx"

@st.cache_data
def load_data():
    # Excel read karein
    df = pd.read_excel(FILE_NAME)
    return df

try:
    data = load_data()
    st.title("🇵🇰 TCF Schools Mapping Dashboard")
    st.markdown("Yeh map ab optimized hai aur fast chalega.")

    # 2. Pakistan ke coordinates par map start karein
    m = folium.Map(location=[30.3753, 69.3451], zoom_start=5, tiles="OpenStreetMap")

    # 3. Marker Cluster banayein (Ye pins ko group kar deta hai taake map heavy na ho)
    marker_cluster = MarkerCluster().add_to(m)

    # Data par loop chalayein
    for index, row in data.iterrows():
        # Column names: 'lat', 'lon', aur 'School'
        lats = row['lat']
        lons = row['lon']
        name = row['School']

        # Check karein ke coordinates khali na hon
        if pd.notnull(lats) and pd.notnull(lons):
            folium.Marker(
                location=[lats, lons],
                popup=f"<b>School Name:</b><br>{name}",
                tooltip=name,
                icon=folium.Icon(color='green', icon='school', prefix='fa')
            ).add_to(marker_cluster) # Cluster mein add kiya

    # 4. Map ko screen par dikhayein (folium_static reload nahi hota bar bar)
    folium_static(m, width=1350, height=700)

except Exception as e:
    st.error(f"Error: {e}")
    st.info("Ensure karein ke Excel mein 'lat', 'lon' aur 'School' headings maujood hain.")
