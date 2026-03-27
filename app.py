import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# Page layout set karein
st.set_page_config(page_title="TCF Pakistan Map", layout="wide")

# Excel file ka naam (Ensure karein ke folder mein yahi naam ho)
FILE_NAME = "SSR_Final_Fixed.xlsx"

@st.cache_data
def load_data():
    # Excel read karein
    df = pd.read_excel(FILE_NAME)
    return df

try:
    data = load_data()
    st.title("🇵🇰 TCF Schools Mapping Dashboard")
    st.markdown("Yeh map Excel file se data utha kar pins dikha raha hai.")

    # Pakistan ke coordinates par map start karein
    m = folium.Map(location=[30.3753, 69.3451], zoom_start=5, tiles="OpenStreetMap")

    # Data par loop chalayein
    for index, row in data.iterrows():
        # Aapki sheet ke column names: 'lat', 'lon', aur 'School'
        lats = row['lat']
        lons = row['lon']
        name = row['School']

        # Check karein ke location khali to nahi
        if pd.notnull(lats) and pd.notnull(lons):
            folium.Marker(
                location=[lats, lons],
                popup=f"<b>School Name:</b><br>{name}",
                tooltip=name,
                icon=folium.Icon(color='green', icon='school', prefix='fa')
            ).add_to(m)

    # Map ko screen par dikhayein
    st_folium(m, width=1350, height=700)

except Exception as e:
    st.error(f"Error: {e}")
    st.info("Check karein ke Excel file mein headings 'lat', 'lon' aur 'School' bilkul isi tarah likhi hain.")
