import streamlit as st
import pandas as pd
import requests
from geopy.geocoders import Nominatim
import geopandas as gpd

st.set_page_config(page_title="GIS Batch Processing", layout="wide")

# Initialize geocoders
geocoder_nominatim = Nominatim(user_agent="geo_app", timeout=10)

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

# Streamlit app
st.title("GIS Batch Processing")

# User instructions
st.markdown("### Enter multiple addresses in the text box below, one per line.")
st.markdown("### The results will show geocoded coordinates for each address using the selected GIS services.")

# User input for addresses
address_input = st.text_area("Enter addresses:", placeholder="Enter one address per line...")

# GIS service selection
gis_services = st.multiselect(
    "Select GIS services to use:",
    ["Nominatim", "ArcGIS", "GeoPandas"],
    default=["Nominatim", "ArcGIS", "GeoPandas"]
)

# When the user clicks the "Process" button, geocode the addresses
if st.button("Process"):
    if address_input:
        lines = [line.strip() for line in address_input.split('\n') if line.strip()]
        results = []

        # Process each address
        for line in lines:
            row = {'Address': line}

            # Nominatim
            if "Nominatim" in gis_services:
                lat, lon = geocode_with_nominatim(line)
                row['Nominatim Latitude'] = lat
                row['Nominatim Longitude'] = lon

            # ArcGIS
            if "ArcGIS" in gis_services:
                lat, lon = geocode_with_arcgis_api(line)
                row['ArcGIS Latitude'] = lat
                row['ArcGIS Longitude'] = lon

            # GeoPandas
            if "GeoPandas" in gis_services:
                lat, lon = geocode_with_geopandas(line)
                row['GeoPandas Latitude'] = lat
                row['GeoPandas Longitude'] = lon

            results.append(row)

        # Display results
        if results:
            results_df = pd.DataFrame(results)
            st.markdown("### Geocoding Results")
            st.dataframe(results_df)

            # Provide a copy-paste table
            st.markdown("### Copy-Paste Table")
            st.text_area("Results Table (Copy-Paste)", results_df.to_csv(index=False, sep='\t'), height=300)
    else:
        st.warning("Please enter at least one address.")

# Provide a placeholder for any additional notes
st.markdown("### Notes")
st.markdown("Ensure the addresses are entered in a standardized format for best results.")
