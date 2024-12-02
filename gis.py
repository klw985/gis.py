import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from arcgis.gis import GIS
from arcgis.geocoding import geocode
import geopandas as gpd
import pandas as pd
import requests

# Initialize geocoders
geocoder_nominatim = Nominatim(user_agent="geo_app", timeout=10)
arcgis_gis = GIS()

# Function to geocode using Nominatim
def geocode_with_nominatim(address):
    try:
        location = geocoder_nominatim.geocode(address)
        if location:
            return location.latitude, location.longitude
    except Exception as e:
        st.error(f"Nominatim error for {address}: {e}")
    return None, None

# Function to geocode using ArcGIS
def geocode_with_arcgis(address):
    try:
        result = geocode(address, as_featureset=True)
        if result and len(result.features) > 0:
            geometry = result.features[0].geometry
            return geometry['y'], geometry['x']
    except Exception as e:
        st.error(f"ArcGIS error for {address}: {e}")
    return None, None

# Function to geocode with GeoPandas
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

# Function to geocode using OpenStreetMap API
def geocode_with_osm(address):
    try:
        url = f'https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1'
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if len(data) > 0:
                return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        st.error(f"OpenStreetMap error for {address}: {e}")
    return None, None

# Streamlit app
st.title("GIS Cross-Validation with Streamlit and Folium")

# User input for addresses or coordinates
address_input = st.text_area("Enter one or more addresses or coordinates (e.g., 37.7749, -122.4194), one per line:")

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
            if ',' in line and all(part.strip().replace('.', '', 1).lstrip('-').isdigit() for part in line.split(',')):
                # It's a coordinate, so use directly
                try:
                    lat, lon = map(float, line.split(','))
                    results.append({'Latitude': lat, 'Longitude': lon, 'Source': f'Coordinate-{index}', 'Color': 'green', 'Number': index})
                except ValueError:
                    st.error(f"Invalid coordinate format for line {index}: {line}")
            else:
                # It's an address, geocode using four GIS services
                
                # Geocode with Nominatim
                lat, lon = geocode_with_nominatim(line)
                if lat and lon:
                    results.append({'Latitude': lat, 'Longitude': lon, 'Source': f'Nominatim-{index}', 'Color': 'blue', 'Number': index})

                # Geocode with ArcGIS
                lat, lon = geocode_with_arcgis(line)
                if lat and lon:
                    results.append({'Latitude': lat, 'Longitude': lon, 'Source': f'ArcGIS-{index}', 'Color': 'red', 'Number': index})

                # Geocode with GeoPandas
                lat, lon = geocode_with_geopandas(line)
                if lat and lon:
                    results.append({'Latitude': lat, 'Longitude': lon, 'Source': f'GeoPandas-{index}', 'Color': 'purple', 'Number': index})

                # Geocode with OpenStreetMap
                lat, lon = geocode_with_osm(line)
                if lat and lon:
                    results.append({'Latitude': lat, 'Longitude': lon, 'Source': f'OpenStreetMap-{index}', 'Color': 'orange', 'Number': index})

        # Save results to session state
        st.session_state.results = results
    else:
        st.warning("Please enter at least one address or coordinate.")

# Create filter options
filter_options = st.multiselect(
    "Select GIS sources to display:",
    options=['Nominatim', 'ArcGIS', 'GeoPandas', 'OpenStreetMap', 'Coordinate'],
    default=['Nominatim', 'ArcGIS', 'GeoPandas', 'OpenStreetMap', 'Coordinate']
)

# Create Folium map
m = folium.Map(location=[38.5767, -92.1735], zoom_start=5)

# Add all markers to the map from session state, filtering based on user selection
for result in st.session_state.results:
    if any(source in result['Source'] for source in filter_options):
        if not pd.isna(result['Latitude']) and not pd.isna(result['Longitude']):
            folium.Marker(location=[result['Latitude'], result['Longitude']],
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
