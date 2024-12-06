import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from arcgis.gis import GIS
from arcgis.geocoding import geocode
import geopandas as gpd
import io

st.set_page_config(page_title="Batch Geocoding Tool", layout="wide")

# Initialize geocoders
geocoder_nominatim = Nominatim(user_agent="geo_app", timeout=10)
arcgis_gis = GIS()

# Geocoding functions
def geocode_with_nominatim(address):
    try:
        location = geocoder_nominatim.geocode(address)
        if location:
            return location.latitude, location.longitude
    except Exception as e:
        st.error(f"Nominatim error for {address}: {e}")
    return None, None

def geocode_with_arcgis(address):
    try:
        # Use the ArcGIS geocoding as specified in the gis.py document
        url = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
        params = {
            'f': 'json',
            'singleLine': address,
            'outFields': 'Match_addr,Addr_type'
        }
        response = arcgis_gis._con.get(url, params)
        if response:
            data = response.get('candidates', [])
            if data:
                best_match = data[0]
                return best_match['location']['y'], best_match['location']['x']
    except Exception as e:
        st.error(f"ArcGIS error for {address}: {e}")
    return None, None

def geocode_with_geopandas(address):
    try:
        geocoded = gpd.tools.geocode(
            [address], provider="nominatim", user_agent="geo_app"
        )
        if not geocoded.empty:
            location = geocoded.geometry.iloc[0]
            return location.y, location.x
    except Exception as e:
        st.error(f"GeoPandas error for {address}: {e}")
    return None, None

# Streamlit app
st.title("Batch Geocoding with GIS Tools")

st.write("Paste a table below. Ensure the first column is labeled 'Address'.")

# Text area for user to paste data
user_input = st.text_area(
    "Paste your table here (e.g., from Excel). Ensure 'Address' is the first column.",
    height=200
)

if user_input:
    try:
        # Convert pasted text into a DataFrame
        data = pd.read_csv(io.StringIO(user_input), header=None, names=["Address"])
        
        # Validate the presence of data
        if 'Address' not in data.columns:
            st.error("The pasted data must have an 'Address' column.")
        else:
            # Add new columns for geocoding results
            st.write("Processing addresses, this may take a few minutes...")
            data['Nominatim_Lat'], data['Nominatim_Lon'] = zip(
                *data['Address'].apply(geocode_with_nominatim)
            )
            data['ArcGIS_Lat'], data['ArcGIS_Lon'] = zip(
                *data['Address'].apply(geocode_with_arcgis)
            )
            data['GeoPandas_Lat'], data['GeoPandas_Lon'] = zip(
                *data['Address'].apply(geocode_with_geopandas)
            )

            # Display the results
            st.write("Geocoded Results:")
            st.dataframe(data)

            # Allow users to copy the data or save it
            csv = data.to_csv(index=False)
            st.download_button(
                label="Download Geocoded Results as CSV",
                data=csv,
                file_name="geocoded_results.csv",
                mime="text/csv",
            )
    except Exception as e:
        st.error(f"An error occurred: {e}")
