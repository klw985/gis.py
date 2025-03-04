import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import geopandas as gpd
import requests
from opencage.geocoder import OpenCageGeocode  # Import OpenCage library

st.set_page_config(page_title="GIS Map Viewer", layout="wide")

# Initialize geocoders
geocoder_nominatim = Nominatim(user_agent="geo_app", timeout=10)

OPENCAGE_API_KEY = "c45010c61631462eac954223488bbd4b"  # Replace with your API key from https://opencagedata.com
opencage_geocoder = OpenCageGeocode(OPENCAGE_API_KEY)

def geocode_with_nominatim(address):
    try:
        location = geocoder_nominatim.geocode(address)
        if location:
            return location.latitude, location.longitude
    except Exception as e:
        st.error(f"Nominatim error for {address}: {e}")
    return None, None

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

def geocode_with_opencage(address):
    try:
        results = opencage_geocoder.geocode(address)
        if results and len(results) > 0:
            location = results[0].get('geometry')
            if location:
                return location.get('lat'), location.get('lng')
            else:
                st.error(f"OpenCage returned an unexpected format for {address}.")
        else:
            st.warning(f"No results returned from OpenCage for {address}.")
    except Exception as e:
        st.error(f"OpenCage error for {address}: {e}")
    return None, None

st.title("GIS Cross-Validation")

# User input for addresses or coordinates
address_input = st.text_area("Enter one or more addresses or coordinates (e.g., 37.7749, -122.4194), one per line:")

# Select GIS services (Google Maps removed, OpenCage added)
gis_services = st.multiselect(
    "Select GIS services to use:",
    ["Nominatim", "ArcGIS", "GeoPandas", "OpenCage"],
    default=["Nominatim", "ArcGIS", "GeoPandas", "OpenCage"]
)

# Initialize session state for results if not already present
if 'results' not in st.session_state:
    st.session_state.results = []

if st.button("Submit"):
    if address_input:
        lines = [line.strip() for line in address_input.split('\n') if line.strip()]
        results = []
        for line in lines:
            # If the input looks like comma-separated coordinates, use them directly
            if ',' in line and all(part.strip().replace('.', '', 1).isdigit() for part in line.split(',')):
                try:
                    lat, lon = map(float, line.split(','))
                    results.append({
                        'Input': line,
                        'Latitude': lat,
                        'Longitude': lon,
                        'Source': 'Coordinate',
                        'Color': 'green'
                    })
                except ValueError:
                    st.error(f"Invalid coordinate: {line}")
            else:
                # Use each selected GIS service for an address
                if "Nominatim" in gis_services:
                    lat, lon = geocode_with_nominatim(line)
                    if lat is not None and lon is not None:
                        results.append({
                            'Input': line,
                            'Latitude': lat,
                            'Longitude': lon,
                            'Source': 'Nominatim',
                            'Color': 'blue'
                        })
                if "ArcGIS" in gis_services:
                    lat, lon = geocode_with_arcgis_api(line)
                    if lat is not None and lon is not None:
                        results.append({
                            'Input': line,
                            'Latitude': lat,
                            'Longitude': lon,
                            'Source': 'ArcGIS',
                            'Color': 'red'
                        })
                if "GeoPandas" in gis_services:
                    lat, lon = geocode_with_geopandas(line)
                    if lat is not None and lon is not None:
                        results.append({
                            'Input': line,
                            'Latitude': lat,
                            'Longitude': lon,
                            'Source': 'GeoPandas',
                            'Color': 'purple'
                        })
                if "OpenCage" in gis_services:
                    lat, lon = geocode_with_opencage(line)
                    if lat is not None and lon is not None:
                        results.append({
                            'Input': line,
                            'Latitude': lat,
                            'Longitude': lon,
                            'Source': 'OpenCage',
                            'Color': 'orange'
                        })
        st.session_state.results = results
    else:
        st.warning("Please enter at least one address or coordinate.")

# Create the base Folium map
m = folium.Map(location=[38.5767, -92.1735], zoom_start=5)
marker_cluster = MarkerCluster().add_to(m)

import math
# ... (rest of your code)

# Group results by the input text (address or coordinates)
grouped = {}
for res in st.session_state.results:
    key = res['Input']
    if key not in grouped:
        grouped[key] = []
    grouped[key].append(res)

# For each input group, compute a representative coordinate and build tooltip text
for input_text, group in grouped.items():
    avg_lat = sum(item['Latitude'] for item in group) / len(group)
    avg_lon = sum(item['Longitude'] for item in group) / len(group)
    
    # Check if the computed coordinates are NaN
    if avg_lat is None or avg_lon is None or math.isnan(avg_lat) or math.isnan(avg_lon):
        st.error(f"Skipping marker for {input_text} due to invalid coordinates: ({avg_lat}, {avg_lon})")
        continue
    
    tooltip_lines = [f"Input: {input_text}"]
    for item in group:
        tooltip_lines.append(f"{item['Source']}: ({item['Latitude']:.4f}, {item['Longitude']:.4f})")
    tooltip_text = "<br>".join(tooltip_lines)
    
    # Use the first item's color for the marker icon
    marker_color = group[0]['Color']
    
    folium.Marker(
        location=[avg_lat, avg_lon],
        tooltip=tooltip_text,
        popup=folium.Popup(tooltip_text, parse_html=True),
        icon=folium.Icon(color=marker_color, icon='info-sign')
    ).add_to(marker_cluster)


st_data = st_folium(m, width=725, height=500)

if st_data and 'last_clicked' in st_data and st_data['last_clicked'] is not None:
    lat = st_data['last_clicked']['lat']
    lon = st_data['last_clicked']['lng']
    st.write(f"Last clicked coordinates: Latitude {lat}, Longitude {lon}")

st.markdown("### Color Legend")
st.markdown("""
- **Nominatim**: Blue
- **ArcGIS**: Red
- **GeoPandas**: Purple
- **OpenCage**: Orange
- **Direct Coordinates**: Green
""")
