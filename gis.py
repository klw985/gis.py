import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import geopandas as gpd
import pandas as pd
import requests
import googlemaps  # Add Google Maps library

st.set_page_config(page_title="GIS Map Viewer", layout="wide")

# Initialize geocoders
geocoder_nominatim = Nominatim(user_agent="geo_app", timeout=10)

# Initialize Google Maps geocoder
GOOGLE_API_KEY = "AIzaSyAQRwPup2hRdar19THb07uTMeKVOMHv65I"  # Replace with your API key
gmaps = googlemaps.Client(key=GOOGLE_API_KEY)

# Function to geocode using Nominatim
def geocode_with_nominatim(address):
    try:
        location = geocoder_nominatim.geocode(address)
        if location:
            return location.latitude, location.longitude
    except Exception as e:
        st.error(f"Nominatim error for {address}: {e}")
    return None, None

# Function to geocode using ArcGIS REST API
def geocode_with_arcgis_api(address):
    try:
        url = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
        params = {
            'f': 'json',
            'singleLine': address,
            'outFields': 'Match_addr,Addr_type'
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data['candidates']:
                best_match = data['candidates'][0]
                return best_match['location']['y'], best_match['location']['x']
    except Exception as e:
        st.error(f"ArcGIS REST API error for {address}: {e}")
    return None, None

# Function to geocode using GeoPandas
def geocode_with_geopandas(address):
    try:
        gdf = gpd.tools.geocode(
            [address], 
            provider="nominatim", 
            user_agent="geo_app"
        )
        if not gdf.empty:
            return gdf.geometry.y.iloc[0], gdf.geometry.x.iloc[0]
    except Exception as e:
        st.error(f"GeoPandas error for {address}: {e}")
    return None, None

# Function to geocode using Google Maps API
def geocode_with_google(address):
    try:
        geocode_result = gmaps.geocode(address)
        if geocode_result:
            location = geocode_result[0]["geometry"]["location"]
            return location["lat"], location["lng"]
    except Exception as e:
        st.error(f"Google Maps error for {address}: {e}")
    return None, None

# Streamlit app
st.title("GIS Cross-Validation")

# User input for addresses or coordinates
address_input = st.text_area("Enter one or more addresses or coordinates (e.g., 37.7749, -122.4194), one per line:")

# GIS service selection
gis_services = st.multiselect(
    "Select GIS services to use:",
    ["Nominatim", "ArcGIS", "GeoPandas", "Google Maps"],
    default=["Nominatim", "ArcGIS", "GeoPandas", "Google Maps"]
)

# Initialize session state variables if they do not exist
if 'results' not in st.session_state:
    st.session_state.results = []

# When the user clicks the "Submit" button, geocode the addresses
if st.button("Submit"):
    if address_input:
        lines = [line.strip() for line in address_input.split('\n') if line.strip()]
        results = []

        # Loop through addresses or coordinates, assign an index number for each
        for index, line in enumerate(lines, start=1):
            if ',' in line and all(part.strip().replace('.', '', 1).isdigit() for part in line.split(',')):
                # It's a coordinate, so use directly
                try:
                    lat, lon = map(float, line.split(','))
                    results.append({'Latitude': lat, 'Longitude': lon, 'Source': f'Coordinate-{index}', 'Color': 'green', 'Number': index})
                except ValueError:
                    st.error(f"Invalid coordinate: {line}")
            else:
                # It's an address, geocode using the selected GIS services
                if "Nominatim" in gis_services:
                    lat, lon = geocode_with_nominatim(line)
                    if lat is not None and lon is not None:
                        results.append({'Latitude': lat, 'Longitude': lon, 'Source': f'Nominatim-{index}', 'Color': 'blue', 'Number': index})

                if "ArcGIS" in gis_services:
                    lat, lon = geocode_with_arcgis_api(line)
                    if lat is not None and lon is not None:
                        results.append({'Latitude': lat, 'Longitude': lon, 'Source': f'ArcGIS-{index}', 'Color': 'red', 'Number': index})

                if "GeoPandas" in gis_services:
                    lat, lon = geocode_with_geopandas(line)
                    if lat is not None and lon is not None:
                        results.append({'Latitude': lat, 'Longitude': lon, 'Source': f'GeoPandas-{index}', 'Color': 'purple', 'Number': index})

                if "Google Maps" in gis_services:
                    lat, lon = geocode_with_google(line)
                    if lat is not None and lon is not None:
                        results.append({'Latitude': lat, 'Longitude': lon, 'Source': f'Google-{index}', 'Color': 'orange', 'Number': index})

        # Save results to session state
        st.session_state.results = results
    else:
        st.warning("Please enter at least one address or coordinate.")

# Create Folium map
m = folium.Map(location=[38.5767, -92.1735], zoom_start=5)

# Add all markers to the map from session state, ensuring no NaN values
for result in st.session_state.results:
    if result['Latitude'] is not None and result['Longitude'] is not None:
        folium.Marker(
            location=[result['Latitude'], result['Longitude']],
            popup=f"{result['Source']}: {result['Latitude']}, {result['Longitude']}",
            icon=folium.Icon(color=result['Color'], icon='info-sign')
        ).add_to(m)

# Display map
st_data = st_folium(m, width=725, height=500)

# Display coordinates for the last clicked marker (if any)
if st_data and 'last_clicked' in st_data and st_data['last_clicked'] is not None:
    lat = st_data['last_clicked']['lat']
    lon = st_data['last_clicked']['lng']
    st.write(f"Last clicked coordinates: Latitude {lat}, Longitude {lon}")

# Add a color legend to the Streamlit app
st.markdown("### Color Legend")
st.markdown("""
- **Nominatim**: Blue
- **ArcGIS**: Red
- **GeoPandas**: Purple
- **Google Maps**: Orange
- **Direct Coordinates**: Green
""")
