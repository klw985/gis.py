import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import geopandas as gpd
import requests
from opencage.geocoder import OpenCageGeocode  # Import OpenCage library
import math
import pandas as pd

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

# Use columns to arrange the text area, submit button, and GIS services dropdown side-by-side.
col1, col2 = st.columns([3, 1])
with col1:
    address_input = st.text_area(
        "Enter one or more addresses or coordinates (e.g., 37.7749, -122.4194), one per line:"
    )
    submit_button = st.button("Submit")
with col2:
    gis_services = st.multiselect(
        "Select GIS services to use:",
        ["Nominatim", "ArcGIS", "GeoPandas", "OpenCage"],
        default=["Nominatim", "ArcGIS", "GeoPandas", "OpenCage"]
    )

# Initialize session state for results if not already present
if 'results' not in st.session_state:
    st.session_state.results = []

if submit_button:
    if address_input:
        lines = [line.strip() for line in address_input.split('\n') if line.strip()]
        results = []
        for line in lines:
            # If the input appears to be comma-separated coordinates, use them directly.
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
                # Otherwise, use each selected GIS service for geocoding the address.
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

# Create the base Folium map centered on Missouri (approximate center)
m = folium.Map(location=[38.573936, -92.603760], zoom_start=7, control_scale=True)

# Add default tile layer and satellite view layer
folium.TileLayer('OpenStreetMap', name="Street View").add_to(m)
folium.TileLayer('Esri.WorldImagery', name="Satellite View").add_to(m)

# Load and add Missouri 2010 congressional district boundaries.
try:
    folium.GeoJson("2010_Congressional_Districts.json", name="Congressional Districts").add_to(m)
except Exception as e:
    st.error("Error loading Missouri congressional district boundaries: " + str(e))

# Add layer control so users can toggle layers.
folium.LayerControl().add_to(m)

# Create a MarkerCluster for managing overlapping markers.
marker_cluster = MarkerCluster().add_to(m)

# Group results by nearly identical coordinates (rounding to 5 decimals)
grouped_by_coord = {}
for res in st.session_state.results:
    lat = res['Latitude']
    lon = res['Longitude']
    if lat is None or lon is None or math.isnan(lat) or math.isnan(lon):
        st.error(f"Skipping invalid coordinates for input {res['Input']} from {res['Source']}: ({lat}, {lon})")
        continue
    key = (round(lat, 5), round(lon, 5))
    grouped_by_coord.setdefault(key, []).append(res)

# For each group, create one marker. If multiple results share the same spot, list all details.
for key, group in grouped_by_coord.items():
    avg_lat = sum(item['Latitude'] for item in group) / len(group)
    avg_lon = sum(item['Longitude'] for item in group) / len(group)
    
    tooltip_lines = []
    for item in group:
        tooltip_lines.append(f"Input: {item['Input']}<br>{item['Source']}: ({item['Latitude']:.4f}, {item['Longitude']:.4f})")
    tooltip_text = "<br><br>".join(tooltip_lines)
    
    # If multiple markers overlap, use a distinct color (black), otherwise use the individual package color.
    marker_color = "black" if len(group) > 1 else group[0]['Color']
    
    folium.Marker(
        location=[avg_lat, avg_lon],
        tooltip=tooltip_text,
        popup=folium.Popup(tooltip_text, parse_html=True),
        icon=folium.Icon(color=marker_color, icon='info-sign')
    ).add_to(marker_cluster)

# Render the map in Streamlit.
st_data = st_folium(m, width=725, height=500)

# Build a table of all geocoded points.
if st.session_state.results:
    df = pd.DataFrame(st.session_state.results)
    st.markdown("### Geocoded Results")
    st.dataframe(df)

# Show clicked coordinates in a separate section for easy copy-paste.
if st_data and 'last_clicked' in st_data and st_data['last_clicked'] is not None:
    clicked_coords = st_data['last_clicked']
    st.markdown("### Last Clicked Coordinate")
    st.write(f"Latitude: {clicked_coords['lat']}, Longitude: {clicked_coords['lng']}")
