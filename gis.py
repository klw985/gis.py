import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import geopandas as gpd
from shapely.geometry import Point
import math
import pandas as pd
import requests
from opencage.geocoder import OpenCageGeocode  # Import OpenCage library

st.set_page_config(page_title="GIS Map Viewer", layout="wide")

# Initialize geocoders
geocoder_nominatim = Nominatim(user_agent="geo_app", timeout=10)
OPENCAGE_API_KEY = "c45010c61631462eac954223488bbd4b"  # Replace with your API key if needed
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
        params = {'f': 'json', 'singleLine': address, 'outFields': 'Match_addr,Addr_type'}
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('candidates'):
                best_match = data['candidates'][0]
                return best_match['location']['y'], best_match['location']['x']
    except Exception as e:
        st.error(f"ArcGIS error for {address}: {e}")
    return None, None

def geocode_with_geopandas(address):
    try:
        gdf = gpd.tools.geocode([address], provider="nominatim", user_agent="geo_app")
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
                st.error(f"OpenCage returned unexpected format for {address}.")
        else:
            st.warning(f"No results from OpenCage for {address}.")
    except Exception as e:
        st.error(f"OpenCage error for {address}: {e}")
    return None, None

st.title("GIS Cross-Validation")

# Load congressional district shapefile from the dedicated folder.
try:
    districts_gdf = gpd.read_file("congressional_districts/gz_2010_29_500_11_500k.shp")
    districts_gdf = districts_gdf.to_crs(epsg=4326)
    # (Optional) Remove or comment out the next line once you have verified the columns:
    # st.write("District columns:", districts_gdf.columns.tolist())
except Exception as e:
    st.error("Error loading district boundaries: " + str(e))
    districts_gdf = None

def get_district_from_point(point, districts_gdf):
    if districts_gdf is None:
        return "No district data"
    for idx, row in districts_gdf.iterrows():
        if row['geometry'].contains(point):
            # For this dataset, the 'CD' field holds the congressional district.
            return row['CD']
    return "Not in any district"

# Arrange input elements in two columns.
col1, col2 = st.columns([3, 1])
with col1:
    address_input = st.text_area("Enter one or more addresses or coordinates (e.g., 37.7749, -122.4194), one per line:")
    submit_button = st.button("Submit")
with col2:
    gis_services = st.multiselect(
        "Select GIS services to use:",
        ["Nominatim", "ArcGIS", "GeoPandas", "OpenCage"],
        default=["Nominatim", "ArcGIS", "GeoPandas", "OpenCage"]
    )

if 'results' not in st.session_state:
    st.session_state.results = []

if submit_button and address_input:
    lines = [line.strip() for line in address_input.splitlines() if line.strip()]
    results = []
    for line in lines:
        # If input looks like coordinates (comma-separated), use them directly.
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
            except Exception:
                st.error(f"Invalid coordinate: {line}")
        else:
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

# Create the base Folium map.
m = folium.Map(location=[38.5767, -92.1735], zoom_start=5)
# Add tile layers.
folium.TileLayer('OpenStreetMap', name='Street View').add_to(m)
folium.TileLayer('Esri.WorldImagery', name='Satellite View').add_to(m)
folium.LayerControl().add_to(m)

marker_cluster = MarkerCluster().add_to(m)

# Group markers by nearly identical coordinates (rounded to 5 decimals).
grouped_by_coord = {}
for res in st.session_state.results:
    lat = res.get('Latitude')
    lon = res.get('Longitude')
    if lat is None or lon is None or math.isnan(lat) or math.isnan(lon):
        continue
    key = (round(lat, 5), round(lon, 5))
    grouped_by_coord.setdefault(key, []).append(res)

for key, group in grouped_by_coord.items():
    avg_lat = sum(item['Latitude'] for item in group) / len(group)
    avg_lon = sum(item['Longitude'] for item in group) / len(group)
    point = Point(avg_lon, avg_lat)
    district = get_district_from_point(point, districts_gdf)
    tooltip_lines = [f"District: {district}"]
    for item in group:
        tooltip_lines.append(f"Input: {item['Input']}<br>{item['Source']}: ({item['Latitude']:.4f}, {item['Longitude']:.4f})")
    tooltip_text = "<br><br>".join(tooltip_lines)
    marker_color = "black" if len(group) > 1 else group[0]['Color']
    folium.Marker(
        location=[avg_lat, avg_lon],
        tooltip=tooltip_text,
        popup=folium.Popup(tooltip_text, parse_html=True),
        icon=folium.Icon(color=marker_color, icon='info-sign')
    ).add_to(marker_cluster)

# (Optional) Comment out the fit_bounds call if it's causing issues.
# all_coords = [(res['Latitude'], res['Longitude']) for res in st.session_state.results
#               if res['Latitude'] is not None and res['Longitude'] is not None
#               and not math.isnan(res['Latitude']) and not math.isnan(res['Longitude'])]
# if all_coords:
#     min_lat = min(lat for lat, lon in all_coords)
#     max_lat = max(lat for lat, lon in all_coords)
#     min_lon = min(lon for lat, lon in all_coords)
#     max_lon = max(lon for lat, lon in all_coords)
#     m.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])

# Render the map using st_folium.
st_data = st_folium(m, width=725, height=500)

# Display last clicked coordinates (formatted as a simple comma-separated string) and the district.
if st_data and 'last_clicked' in st_data and st_data['last_clicked']:
    last_clicked = st_data['last_clicked']
    coords_str = f"{last_clicked['lat']}, {last_clicked['lng']}"
    clicked_point = Point(last_clicked['lng'], last_clicked['lat'])
    clicked_district = get_district_from_point(clicked_point, districts_gdf)
    st.markdown(f"**Last clicked:** {coords_str} (District: {clicked_district})")

# Build a table of all geocoded points with district info.
if st.session_state.results:
    results_table = []
    for res in st.session_state.results:
        lat = res.get('Latitude')
        lon = res.get('Longitude')
        if lat is not None and lon is not None and not math.isnan(lat) and not math.isnan(lon):
            pt = Point(lon, lat)
            district = get_district_from_point(pt, districts_gdf)
        else:
            district = "N/A"
        row = res.copy()
        row['District'] = district
        results_table.append(row)
    df = pd.DataFrame(results_table)
    st.markdown("### Geocoded Results")
    st.dataframe(df)

st.markdown("### Color Legend")
st.markdown("""
- **Nominatim**: Blue  
- **ArcGIS**: Red  
- **GeoPandas**: Purple  
- **OpenCage**: Orange  
- **Direct Coordinates**: Green  
- **Overlapping Markers**: Black
""")
