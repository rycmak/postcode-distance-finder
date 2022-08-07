# app.py, run with 'streamlit run app.py'
import streamlit as st
import pgeocode
import geopy
from geopy.extra.rate_limiter import RateLimiter
import numpy as np
import pandas as pd
import requests
import json
import time
import folium
from streamlit_folium import st_folium

st.title("Find total distance from list of postcodes to destination")

def get_destination_lat_long():
  destination_address = st.text_input("Input destination address and press Enter:",
                                      help="Please include street number, street name, suburb, and city",
                                      placeholder="E.g.: 72 Victoria Street West, Auckland 1010")
  locator = geopy.geocoders.Nominatim(user_agent="postcode-distance-app")
  geocode = RateLimiter(locator.geocode, min_delay_seconds=1)
  location = geocode(destination_address)
  if location:
    lat_long = tuple(location.point[0:2])
  else:
    lat_long = None
  return destination_address, lat_long


def get_postcodes():
  postcodes_csv = st.file_uploader("Upload CSV file containing list of postcodes \
                                  (one column, with one postcode per row):")
  if postcodes_csv is not None:
    postcodes_df = pd.read_csv(postcodes_csv, names=["postcodes"], dtype=object)
    return postcodes_df
  else:
    return None


def get_postcodes_lat_long(df):
  # Find latitude and longitude of each postcode
  column_names = ["City", "Suburb", "Postcode", "Latitude", "Longitude", "Distance (km)"]
  geocoded_data = pd.DataFrame(columns=column_names)
  nomi = pgeocode.Nominatim('nz')
  if df is not None:
    for i, row in df.iterrows():
      postcode_info = nomi.query_postal_code(row["postcodes"])
      geocoded_data = geocoded_data.append({'City' : postcode_info["state_name"], 
                                          'Suburb': postcode_info["place_name"], 
                                          'Postcode': postcode_info["postal_code"], 
                                          'Latitude': postcode_info["latitude"], 
                                          'Longitude': postcode_info["longitude"]}, ignore_index = True)
    return geocoded_data
  else:
    return None

  # consider cases when postcode not recognized


def calc_distance(df, dest_lat_long):
  # Calculate distance from each postcode to destination
  destination_latitude = dest_lat_long[0]
  destination_longitude = dest_lat_long[1]
  if df is not None:
    df = df[df["Latitude"].notna() & df["Longitude"].notna()]
    for i, row in df.iterrows():
      if len(df) > 10 and i % 10 == 0:
        time.sleep(1)  # add time delay to not overwhelm server with requests
      # Call Open Source Routing Machine (OSRM) to calculate driving distance
      response = requests.get(f"""http://router.project-osrm.org/route/v1/driving/{destination_longitude},{destination_latitude};{row["Longitude"]},{row["Latitude"]}?overview=false""")
      results = json.loads(response.content)
      driving_distance = results["routes"][0]["distance"] / 1000  # results are given in metres, so divide by 1000 to get km
      df.at[i, "Distance (km)"] = driving_distance
    return df
  else:
    return None


def draw_map(dest_lat_long, data):
  # Plot marker for destination
  map = folium.Map(location=[dest_lat_long[0], dest_lat_long[1]], 
                    zoom_control=False, scrollWheelZoom=False, dragging=False)
  folium.Marker([45.5236, -122.6750], color='red').add_to(map)
  # Plot marker for each postcode
  for i, row in data.iterrows():
    folium.Marker([row["Latitude"], row["Longitude"]], color='blue').add_to(map)
  st_folium(map, width=800)


def main():
  destination_address, destination_lat_long = get_destination_lat_long()
  if not destination_address:
    return
  
  elif destination_lat_long:
    st.markdown(f"Destination latitude and longitude: {destination_lat_long}")

    postcodes_df = get_postcodes()
    if postcodes_df is not None:
      st.markdown("Postcodes from file:")
      st.write(postcodes_df)

      geocoded_data = get_postcodes_lat_long(postcodes_df)
      
      draw_map(destination_lat_long, geocoded_data)

      with st.spinner("Calculating distances from all postcodes to destination..."):
        distances_df = calc_distance(geocoded_data, destination_lat_long)
      st.markdown("Here are the driving distances:")
      st.write(distances_df)

      st.markdown(f"""<h3>Total distance from all postcodes to 
                  <span style="color:blue">{destination_address}</span> is 
                  {sum(distances_df['Distance (km)']):.2f} km</h3>""", unsafe_allow_html=True)
    else:
      return

  else:
    st.text("Latitude and longitude could not be found for address 😢")
  

if __name__ == "__main__":
    main()