import streamlit as st
import pandas as pd
import requests
from pyproj import CRS, Transformer
from datetime import datetime, timedelta

# Function to read the site names from the CSV file
def load_site_names(file_path):
    df = pd.read_csv(file_path, header=None)
    site_names = df[0].tolist()
    return site_names

# Function to fetch and read the .txt file from the URL
def read_txt_from_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Will raise an exception for HTTP errors
        from io import StringIO
        data = StringIO(response.text)
        column_names = ['YYYY', 'DDD', 'X', 'isWithinTolerance', 'X(m)', 'Y(m)', 'Z(m)', 'sigmaX(m)', 'sigmaY(m)', 'sigmaZ(m)']
        df = pd.read_csv(data, delim_whitespace=True, header=None, names=column_names)

        # Convert 'YYYY DDD' to a proper Date format (MM/DD/YYYY)
        df['Date'] = pd.to_datetime(df['YYYY'].astype(str) + df['DDD'].astype(str), format='%Y%j').dt.strftime('%m/%d/%Y')

        # Drop the 'YYYY' and 'DDD' columns after creating 'Date'
        df = df.drop(columns=['YYYY', 'DDD'])

        # Reorder the columns to place 'Date' first
        cols = ['Date', 'X', 'isWithinTolerance', 'X(m)', 'Y(m)', 'Z(m)', 'sigmaX(m)', 'sigmaY(m)', 'sigmaZ(m)']
        df = df[cols]

        return df
    except requests.exceptions.RequestException as e:
        st.error(f"Error loading data: {e}")
        return None

# Function to convert XYZ to Lat, Lon, Height using PyProj
def convert_xyz_to_lat_lon_height(x, y, z):
    # Define the WGS84 CRS (Coordinate Reference System)
    wgs84_crs = CRS.from_epsg(4326)  # EPSG:4326 is WGS84
    
    # Define the 3D Cartesian (ECEF) coordinate system for the transformation
    ecef_crs = CRS.from_epsg(4978)  # EPSG:4978 is the ECEF (Earth-Centered, Earth-Fixed) coordinate system
    
    # Create a transformer for converting from ECEF (XYZ) to Lat/Lon/Height (WGS84)
    transformer = Transformer.from_crs(ecef_crs, wgs84_crs, always_xy=True)
    
    # Convert XYZ to Latitude, Longitude, Height
    lon, lat, height = transformer.transform(x, y, z)
    
    return lat, lon, height

# Function to convert uncertainties (sigma) based on the projection system
def convert_uncertainties(sigma_x, sigma_y, sigma_z):
    # We assume simple conversion, but in practice, this could depend on many factors
    return sigma_x, sigma_y, sigma_z

# Streamlit UI
st.title('OPUS-Net Position Data Viewer')

# Load site names from the provided CSV file
site_names = load_site_names('OPUS_Net_Site_Names.csv')

# Dropdown to select the site
selected_site = st.selectbox('Select a site', site_names)

# Fetch Data button
if st.button('Fetch Data'):
    if selected_site:
        # Construct the URL for the selected site
        url = f'https://geodesy.noaa.gov/corsdata/spec_prod/opus/coord_14/{selected_site}'
        
        # Fetch the data from the URL
        data = read_txt_from_url(url)
        
        # If data is fetched successfully, store it in session state
        if data is not None:
            st.session_state.data = data
            st.session_state.show_date_filter = True
        else:
            st.session_state.show_date_filter = False

# Date Filter (hidden until Fetch Data button is clicked)
if 'show_date_filter' in st.session_state and st.session_state.show_date_filter:
    # Get the available date range
    available_dates = pd.to_datetime(st.session_state.data['Date'])
    min_date = available_dates.min().date()
    max_date = available_dates.max().date()

    # Date input for selecting the starting date
    start_date = st.date_input('Select a starting date', min_value=min_date, max_value=max_date, value=min_date)

    # Dropdown to select the number of rows to display
    rows_to_show = st.selectbox('Select number of rows to display', [10, 50, 100], index=0)

    # Button to load filtered data
    if st.button('Show Data'):
        # Filter data based on the selected date and number of rows
        filtered_data = st.session_state.data[pd.to_datetime(st.session_state.data['Date']) >= pd.to_datetime(start_date)]
        filtered_data = filtered_data.head(rows_to_show)
        
        # Store filtered data in session state
        st.session_state.filtered_data = filtered_data
        
        # Display the filtered data
        st.dataframe(filtered_data)

# Convert button (shown only when filtered data is present)
if 'filtered_data' in st.session_state and st.session_state.filtered_data is not None:
    if st.button('Convert'):
        data = st.session_state.filtered_data  # Retrieve the filtered data from session state

        # Create lists to store converted values
        latitudes = []
        longitudes = []
        heights = []
        sigma_latitudes = []
        sigma_longitudes = []
        sigma_heights = []
        
        # Loop through each row and convert XYZ to lat, lon, height
        for index, row in data.iterrows():
            # Extract X, Y, Z and uncertainties
            x = row['X(m)']
            y = row['Y(m)']
            z = row['Z(m)']
            sigma_x = row['sigmaX(m)']
            sigma_y = row['sigmaY(m)']
            sigma_z = row['sigmaZ(m)']
            
            # Convert XYZ to Lat, Lon, Height
            lat, lon, height = convert_xyz_to_lat_lon_height(x, y, z)
            
            # Convert uncertainties
            sigma_lat, sigma_lon, sigma_height = convert_uncertainties(sigma_x, sigma_y, sigma_z)
            
            # Append results to lists
            latitudes.append(lat)
            longitudes.append(lon)
            heights.append(height)
            sigma_latitudes.append(sigma_lat)
            sigma_longitudes.append(sigma_lon)
            sigma_heights.append(sigma_height)
        
        # Create a new DataFrame with the converted data
        converted_data = pd.DataFrame({
            'Date': data['Date'],
            'Latitude': latitudes,
            'Longitude': longitudes,
            'Height (m)': heights,
            'Sigma Latitude (m)': sigma_latitudes,
            'Sigma Longitude (m)': sigma_longitudes,
            'Sigma Height (m)': sigma_heights
        })
        
        # Display the converted data
        st.dataframe(converted_data)
