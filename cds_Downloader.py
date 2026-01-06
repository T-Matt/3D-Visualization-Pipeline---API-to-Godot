"""
CDSapi Download Pipeline
Simple, straightforward ERA5 data download using cdsapi
"""

import cdsapi
import os
from pathlib import Path
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt

def download_era5_data(request_dict, output_filename, dataset_name='reanalysis-era5-pressure-levels'):
    """
    Download ERA5 data using CDS API
    
    Args:
        request_dict (dict): CDS API request parameters
        output_filename (str): Output file name (will overwrite if exists)
        dataset_name (str): CDS dataset identifier
    
    Returns:
        bool: True if successful, False if failed
    """
    
    try:
        # Set up CDS API client (assumes .cdsapirc in current directory)
        cdsapirc_path = Path('.cdsapirc')
        if cdsapirc_path.exists():
            os.environ['CDSAPI_RC'] = str(cdsapirc_path.absolute())
        
        # Initialize client
        client = cdsapi.Client()
        
        # Download data
        print(f"Downloading ERA5 data to: {output_filename}")
        print(f"Request: {len(request_dict['variable'])} variables, {len(request_dict['day'])} days")
        
        client.retrieve(dataset_name, request_dict, output_filename)
        
        print(f"Download complete: {output_filename}")
        return True , output_filename
        
    except Exception as e:
        print(f"Download failed: {e}")
        return False, None

def download_oras5(Regions, region, output_filename='oras5_ocean.nc'):
    """
    Download ORAS5 ocean reanalysis data for land mask creation.
    
    Args:
        Regions (dict): Dictionary of regional bounds [North, West, South, East]
        region (str): Region key (e.g., 'North America', 'Europe', 'South China Sea')
        output_filename (str): Output file name
    
    Returns:
        tuple: (success: bool, output_file: str or None)
    """
    import zipfile
    
    try:
        # Extract region bounds [North, West, South, East]
        bounds = Regions[region]
        north, west, south, east = bounds[0], bounds[1], bounds[2], bounds[3]
        
        print(f"\nDownloading ORAS5 ocean data for region: {region}")
        print(f"Bounds [N, W, S, E]: {bounds}")
        
        # ORAS5 request - uses monthly data
        oras5_request = {
            'product_type': 'operational',
            'vertical_resolution': 'single_level',
            'variable': 'sea_surface_salinity',
            'year': '2020',
            'month': '01',
            'format': 'netcdf',
        }
        
        # Set up CDS API client
        cdsapirc_path = Path('.cdsapirc')
        if cdsapirc_path.exists():
            os.environ['CDSAPI_RC'] = str(cdsapirc_path.absolute())
        
        client = cdsapi.Client()
        
        # Download to temporary zip file
        temp_zip = output_filename + '.zip'
        print(f"Requesting ORAS5 data (global, will crop to region)...")
        print(f"Output: {output_filename}")
        
        client.retrieve('reanalysis-oras5', oras5_request, temp_zip)
        
        # Extract the NetCDF file from the ZIP archive
        print(f"Extracting NetCDF from ZIP archive...")
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            # List files in the ZIP
            files = zip_ref.namelist()
            print(f"Files in archive: {files}")
            
            # Find the .nc file
            nc_files = [f for f in files if f.endswith('.nc')]
            if not nc_files:
                raise ValueError("No NetCDF file found in ZIP archive")
            
            # Extract the first .nc file
            nc_file = nc_files[0]
            print(f"Extracting: {nc_file}")
            zip_ref.extract(nc_file, path=os.path.dirname(output_filename) or '.')
            
            # Rename to output filename (remove target if exists on Windows)
            extracted_path = os.path.join(os.path.dirname(output_filename) or '.', nc_file)
            if os.path.exists(output_filename):
                os.remove(output_filename)
            os.rename(extracted_path, output_filename)
        
        # Remove the ZIP file
        os.remove(temp_zip)
        
        print(f"✓ ORAS5 download and extraction complete: {output_filename}")
        return True, output_filename
        
    except Exception as e:
        print(f"✗ ORAS5 download failed: {e}")
        print("  Check CDS API credentials and dataset access")
        return False, None

# Making a signature for this function
def add_land_mask_to_era5(file_GLORYS, file_ERA, output_file, 
                          Regions, region, verbose=True):

    ######################################################
    # Creating Land Mask from GLORYS and Adding to ERA5   
    ######################################################

    # Load datasets
    print("Loading datasets...")
    dataGLORYS = xr.open_dataset(file_GLORYS)
    dataERA = xr.open_dataset(file_ERA)

    # Detect if it's ORAS5 or GLORYS based on available variables
    is_oras5 = 'sosaline' in dataGLORYS.data_vars
    
    if is_oras5:
        print("Detected ORAS5 ocean data")
        # ORAS5 is single-level (sea surface), no depth dimension
        surfaceGLORYSindex = None
    else:
        print("Detected GLORYS ocean data")
        # Get top depth level for GLORYS
        surfaceGLORYSindex = dataGLORYS.depth.min().values
        if verbose:
            print(f"\nTop depth level in GLORYS: {surfaceGLORYSindex} meters")

    # For ERA5, highest level = lowest pressure (mb)
    surfaceERAindex = dataERA.pressure_level.max().values 

    if verbose:
        print(f"Top pressure level in ERA5: {surfaceERAindex} mb\n")

    # Degrees [North, West, South, East ]
    desired_lon_min = Regions[region][1]  # -135 West
    desired_lon_max = Regions[region][3]  # -45  East
    desired_lat_min = Regions[region][2]  # 0    South
    desired_lat_max = Regions[region][0]  # 50   North

    if verbose:
        print(f"\nRegion: {region}")
        print(f"Lat range: {desired_lat_min} to {desired_lat_max}")
        print(f"Lon range: {desired_lon_min} to {desired_lon_max}")

    # Get ocean data coordinates (different for ORAS5 vs GLORYS)
    if is_oras5:
        # ORAS5 uses nav_lat and nav_lon (2D arrays)
        ocean_lons = dataGLORYS.nav_lon.values
        ocean_lats = dataGLORYS.nav_lat.values
        glorys_lon_min = ocean_lons.min()
        glorys_lon_max = ocean_lons.max()
    else:
        # GLORYS uses standard longitude/latitude coordinates
        glorys_lon_min = dataGLORYS.longitude.values.min()
        glorys_lon_max = dataGLORYS.longitude.values.max()
    
    print(f"\nOcean data longitude convention check:")
    print(f"  Lon range in file: {glorys_lon_min:.2f} to {glorys_lon_max:.2f}")
    
    # Determine if GLORYS uses -180/180 or 0/360
    if glorys_lon_min >= 0 and glorys_lon_max > 180:
        # GLORYS uses 0-360 convention
        print("  -> Using 0-360 convention")
        lon_min_glorys = (360 + desired_lon_min) % 360  # -135 to 225
        lon_max_glorys = (360 + desired_lon_max) % 360  # -45 to 315
    else:
        # GLORYS uses -180/180 convention (same as ERA5)
        print("  -> Using -180/180 convention")
        lon_min_glorys = desired_lon_min  # -135
        lon_max_glorys = desired_lon_max  # -45

    if verbose:
        print(f"Ocean data lon range for selection: {lon_min_glorys} to {lon_max_glorys}")

    ##############################################################
    # DEBUG: CHECK LATITUDE ORDERING IN BOTH DATASETS
    ##############################################################
    print("\n" + "="*60)
    print("DEBUG: LATITUDE COORDINATE ORDERING CHECK")
    print("="*60)
    
    if is_oras5:
        # ORAS5 has 2D nav_lat, just check min/max
        glorys_lats = dataGLORYS.nav_lat.values
        print(f"\nORAS5 latitude range: {glorys_lats.min():.2f} to {glorys_lats.max():.2f}")
        print("ORAS5 uses 2D lat/lon arrays (nav_lat, nav_lon)")
    else:
        glorys_lats = dataGLORYS.latitude.values
        print(f"\nGLORYS latitude range: {glorys_lats.min():.2f} to {glorys_lats.max():.2f}")
        print(f"GLORYS latitude order: {'ASCENDING' if glorys_lats[0] < glorys_lats[-1] else 'DESCENDING'}")
        print(f"GLORYS first 5 lats: {glorys_lats[:5]}")
        print(f"GLORYS last 5 lats: {glorys_lats[-5:]}")
    
    era5_lats = dataERA.latitude.values
    print(f"\nERA5 latitude range: {era5_lats.min():.2f} to {era5_lats.max():.2f}")
    print(f"ERA5 latitude order: {'ASCENDING' if era5_lats[0] < era5_lats[-1] else 'DESCENDING'}")
    print(f"ERA5 first 5 lats: {era5_lats[:5]}")
    print(f"ERA5 last 5 lats: {era5_lats[-5:]}")
    
    if not is_oras5 and (glorys_lats[0] < glorys_lats[-1]) != (era5_lats[0] < era5_lats[-1]):
        print("\n    WARNING: LATITUDE ORDER MISMATCH DETECTED!   ")
        print("GLORYS and ERA5 have opposite latitude ordering!")
        print("This will cause spatial misalignment when coordinates are reassigned!")
    else:
        print("\n  Latitude ordering is consistent between datasets")
    print("="*60 + "\n")
    ##############################################################
    # END DEBUG
    ##############################################################

    # Extract ERA5 data (uses -180 to 180 convention directly)
    surfaceERA_DATA = (dataERA.t.sel(pressure_level=surfaceERAindex)
                    .isel(valid_time=0))

    #########################################################
    # Extract ocean data based on type
    #########################################################
    print("\n" + "="*60)
    print("DEBUG: OCEAN DATASET EXTRACTION")
    print("="*60)
    
    if is_oras5:
        # ORAS5 has 2D coordinates (nav_lat, nav_lon), need to interpolate to regular grid
        print("Extracting ORAS5 data (global grid with 2D coordinates)...")
        print(f"ORAS5 grid shape: y={dataGLORYS.dims['y']}, x={dataGLORYS.dims['x']}")
        
        # Get salinity data (single time step, no depth dimension)
        salinity_data = dataGLORYS.sosaline.isel(time_counter=0)
        nav_lat = dataGLORYS.nav_lat
        nav_lon = dataGLORYS.nav_lon
        
        # Convert ORAS5 nav_lon from 0-360 to -180/180 if needed to match ERA5
        nav_lon_converted = xr.where(nav_lon > 180, nav_lon - 360, nav_lon)
        
        # Create regular lat/lon grid matching ERA5's resolution
        target_lats = np.arange(desired_lat_min, desired_lat_max + 0.25, 0.25)
        target_lons = np.arange(desired_lon_min, desired_lon_max + 0.25, 0.25)
        
        print(f"Interpolating to regular grid: {len(target_lats)} lats x {len(target_lons)} lons")
        
        # Flatten the ORAS5 data for interpolation
        from scipy.interpolate import griddata
        
        # Get valid (non-NaN) points
        valid_mask = ~np.isnan(salinity_data.values)
        points = np.column_stack([
            nav_lon_converted.values[valid_mask],
            nav_lat.values[valid_mask]
        ])
        values = salinity_data.values[valid_mask]
        
        # Create target grid
        lon_grid, lat_grid = np.meshgrid(target_lons, target_lats)
        
        # Interpolate using nearest neighbor (faster and preserves land/ocean boundaries)
        print("Performing nearest-neighbor interpolation...")
        salinity_regular = griddata(points, values, (lon_grid, lat_grid), method='nearest')
        
        # Create xarray DataArray with regular coordinates
        surfaceGLORYS_DATA = xr.DataArray(
            salinity_regular,
            coords={'latitude': target_lats, 'longitude': target_lons},
            dims=['latitude', 'longitude']
        )
        print(f"ORAS5 data interpolated to regular grid, shape: {surfaceGLORYS_DATA.shape}")
        
    else:
        # GLORYS data selection (original logic)
        print(f"GLORYS longitude range: {dataGLORYS.longitude.values.min():.2f} to {dataGLORYS.longitude.values.max():.2f}")
        print(f"GLORYS latitude range: {dataGLORYS.latitude.values.min():.2f} to {dataGLORYS.latitude.values.max():.2f}")
        print(f"Requested GLORYS lon range: {lon_min_glorys:.2f} to {lon_max_glorys:.2f}")
        print(f"Requested lat range: {desired_lat_min:.2f} to {desired_lat_max:.2f}")
        
        # Handle case where longitude range crosses 0 meridian
        # Select every 3rd point to reduce size
        if lon_min_glorys > lon_max_glorys:  # Crosses prime meridian
            # Need to select in two parts and concatenate
            glorys_part1 = dataGLORYS.so.sel(depth=surfaceGLORYSindex,
                                            longitude=slice(lon_min_glorys, 360, 3),  
                                            latitude=slice(desired_lat_min, desired_lat_max, 3))
            glorys_part2 = dataGLORYS.so.sel(depth=surfaceGLORYSindex,
                                            longitude=slice(0, lon_max_glorys, 3), 
                                            latitude=slice(desired_lat_min, desired_lat_max, 3))
            surfaceGLORYS_DATA = xr.concat([glorys_part1, glorys_part2], dim='longitude').isel(time=0)
        else:  # Normal case
            surfaceGLORYS_DATA = (dataGLORYS.so.sel(depth=surfaceGLORYSindex,
                                longitude=slice(lon_min_glorys, lon_max_glorys, 3), 
                                latitude=slice(desired_lat_min, desired_lat_max, 3))
                                .isel(time=0))
    
    print("="*60 + "\n")
    # DEBUG: Check surfaceGLORYS_DATA after selection
    #########################################################
    print("\n" + "="*60)
    print("DEBUG: surfaceGLORYS_DATA AFTER SELECTION")
    print("="*60)
    print(f"surfaceGLORYS_DATA shape: {surfaceGLORYS_DATA.shape}")
    print(f"surfaceGLORYS_DATA dimensions: {surfaceGLORYS_DATA.dims}")
    if 'longitude' in surfaceGLORYS_DATA.dims:
        print(f"Number of longitude points: {len(surfaceGLORYS_DATA.longitude)}")
    if 'latitude' in surfaceGLORYS_DATA.dims:
        print(f"Number of latitude points: {len(surfaceGLORYS_DATA.latitude)}")
    print("="*60 + "\n")
    #########################################################

    # Mask land areas (assuming land has NaN salinity)
    landMask = surfaceGLORYS_DATA.isnull()
    landData = xr.where(landMask, -10, np.nan).astype(np.float32)  # Land areas set to -10, ocean to NaN

    #########################################################
    # DEBUG: Check landData right after creation
    #########################################################
    print("\n" + "="*60)
    print("DEBUG: landData IMMEDIATELY AFTER CREATION")
    print("="*60)
    print(f"landData shape: {landData.shape}")
    print(f"landData dimensions: {landData.dims}")
    if 'longitude' in landData.dims:
        print(f"landData longitude size: {len(landData.longitude)}")
        if len(landData.longitude) > 0:
            print(f"landData longitude range: {landData.longitude.values.min():.2f} to {landData.longitude.values.max():.2f}")
        else:
            print("   ERROR: landData has ZERO longitude points!")
    else:
        print(f"   ERROR: 'longitude' not in landData dimensions! Dims: {landData.dims}")
    
    if 'latitude' in landData.dims:
        print(f"landData latitude size: {len(landData.latitude)}")
        if len(landData.latitude) > 0:
            print(f"landData latitude range: {landData.latitude.values.min():.2f} to {landData.latitude.values.max():.2f}")
        else:
            print("   ERROR: landData has ZERO latitude points!")
    else:
        print(f"   ERROR: 'latitude' not in landData dimensions! Dims: {landData.dims}")
    print("="*60 + "\n")
    #########################################################
    # END DEBUG
    #########################################################

    #########################################################
    # Adding land mask to ERA5 dataset
    #########################################################

    if verbose:
        # Print shapes of datasets
        print(f"ERA5 file shape: {surfaceERA_DATA.shape}")
        print(f"Landmask shape: {landData.shape}\n")

        # Print the storage type
        print(f"Landmask Data Type: {landData.dtype}")
        print(f"ERA5 Surface Data Type: {surfaceERA_DATA.dtype}\n")

    print("Adding the land mask into ERA5 dataset...")

    # Get the current pressure levels
    print("Getting current pressure levels...")
    current_pressure_levels = dataERA.pressure_level.values

    # Create a new pressure level for the land mask (higher pressure = closer to ground)
    print("Adding sea level pressure...")
    land_pressure_level = current_pressure_levels.max() + 13  # e.g., 1013 mb

    # Expand landData to match ERA5 dimensions (add time and pressure_level dimensions)
    print("Matching dimensions...")
    landData_expanded = landData.expand_dims({
        'pressure_level': [land_pressure_level],
        'valid_time': dataERA.valid_time
    })

    # Ensure coordinates match exactly
    print("Aligning coordinates...")
    
    ##############################################################
    # DEBUG: CHECK LAND MASK LATITUDE COORDINATES BEFORE REASSIGNMENT
    ##############################################################
    print("\n" + "="*60)
    print("DEBUG: LAND MASK COORDINATES BEFORE REASSIGNMENT")
    print("="*60)
    
    print(f"\nLandData latitude range: {landData.latitude.values.min():.2f} to {landData.latitude.values.max():.2f}")
    print(f"LandData latitude order: {'ASCENDING' if landData.latitude.values[0] < landData.latitude.values[-1] else 'DESCENDING'}")
    print(f"LandData first 5 lats: {landData.latitude.values[:5]}")
    print(f"LandData last 5 lats: {landData.latitude.values[-5:]}")
    print(f"LandData shape: {landData.shape}")
    
    print(f"\nERA5 latitude values we're about to assign:")
    print(f"ERA5 first 5 lats: {dataERA.latitude.values[:5]}")
    print(f"ERA5 last 5 lats: {dataERA.latitude.values[-5:]}")
    
    # Check if we need to flip the land data to match ERA5's latitude order
    glorys_ascending = landData.latitude.values[0] < landData.latitude.values[-1]
    era5_ascending = dataERA.latitude.values[0] < dataERA.latitude.values[-1]
    
    if glorys_ascending != era5_ascending:
        print("\n    APPLYING FIX: Flipping land data LATITUDE to match ERA5 latitude order...")
        landData_expanded = landData_expanded.isel(latitude=slice(None, None, -1))
        print("  Land data latitude flipped successfully!")
    
    # Check longitude ordering
    print(f"\nLandData longitude range: {landData.longitude.values.min():.2f} to {landData.longitude.values.max():.2f}")
    print(f"LandData longitude order: {'ASCENDING' if landData.longitude.values[0] < landData.longitude.values[-1] else 'DESCENDING'}")
    print(f"LandData first 5 lons: {landData.longitude.values[:5]}")
    print(f"LandData last 5 lons: {landData.longitude.values[-5:]}")
    
    print(f"\nERA5 longitude range: {dataERA.longitude.values.min():.2f} to {dataERA.longitude.values.max():.2f}")
    print(f"ERA5 longitude order: {'ASCENDING' if dataERA.longitude.values[0] < dataERA.longitude.values[-1] else 'DESCENDING'}")
    print(f"ERA5 first 5 lons: {dataERA.longitude.values[:5]}")
    print(f"ERA5 last 5 lons: {dataERA.longitude.values[-5:]}")
    
    # Check if we need to flip the land data to match ERA5's longitude order
    glorys_lon_ascending = landData.longitude.values[0] < landData.longitude.values[-1]
    era5_lon_ascending = dataERA.longitude.values[0] < dataERA.longitude.values[-1]
    
    if glorys_lon_ascending != era5_lon_ascending:
        print("\n    APPLYING FIX: Flipping land data LONGITUDE to match ERA5 longitude order...")
        landData_expanded = landData_expanded.isel(longitude=slice(None, None, -1))
        print("  Land data longitude flipped successfully!")
    else:
        print("\n  Longitude ordering is consistent between datasets")
    
    print("="*60 + "\n")
    ##############################################################
    # END DEBUG
    ##############################################################
    
    # Instead of assigning coordinates, interpolate to match ERA5's exact grid
    print("Interpolating land mask to match ERA5 grid...")
    landData_expanded = landData_expanded.interp(
        latitude=dataERA.latitude,
        longitude=dataERA.longitude,
        method='nearest'  # Use nearest neighbor for land mask (preserve sharp boundaries)
    )

    if verbose:
        print(f"LandData expanded shape after interpolation: {landData_expanded.shape}")
        print(f"LandData expanded dims: {landData_expanded.dims}")
        print(f"  Land mask successfully interpolated to ERA5 grid")

    # Concatenate along the pressure_level dimension for ALL variables
    print("Concatenating temperature along the pressure_level dimension...")
    t_combined = xr.concat(
        [dataERA['t'], landData_expanded],
        dim='pressure_level'
    )

    print("Concatenating u-wind along the pressure_level dimension...")
    u_combined = xr.concat(
        [dataERA['u'], landData_expanded],
        dim='pressure_level'
    )

    print("Concatenating v-wind along the pressure_level dimension...")
    v_combined = xr.concat(
        [dataERA['v'], landData_expanded],
        dim='pressure_level'
    )

    print("Concatenating vertical_velocity along the pressure_level dimension...")
    vertical_velocity_combined = xr.concat(
        [dataERA['w'], landData_expanded],
        dim='pressure_level'
    )

    # print("Concatenating potential_vorticity along the pressure_level dimension...")
    # potential_vorticity_combined = xr.concat(
    #     [dataERA['pv'], landData_expanded],
    #     dim='pressure_level'
    # )

    # print("Concatenating specific_humidity along the pressure_level dimension...")
    # specific_humidity_combined = xr.concat(
    #     [dataERA['q'], landData_expanded],
    #     dim='pressure_level'
    # )   
    
    # print("Concatenating geopotential along the pressure_level dimension...")
    # geopotential_combined = xr.concat(
    #     [dataERA['z'], landData_expanded],
    #     dim='pressure_level'
    # )   

    # Create a NEW dataset with ALL combined variables
    print("Building new dataset...")
    dataERA_with_land = xr.Dataset(
        {
            't': t_combined,
            'u': u_combined,
            'v': v_combined,
            'w': vertical_velocity_combined,
            #'potential_vorticity': potential_vorticity_combined,
            #'specific_humidity': specific_humidity_combined,
            #'geopotential': geopotential_combined
        },
        coords={
            'valid_time': dataERA.valid_time,
            'latitude': dataERA.latitude,
            'longitude': dataERA.longitude,
            'pressure_level': t_combined.pressure_level
        }
    )

    # Copy over any other variables/attributes from original if needed
    dataERA_with_land.attrs = dataERA.attrs

    # Sort by pressure level to keep them in order
    print("Sorting by pressure level...")
    dataERA_with_land = dataERA_with_land.sortby('pressure_level')

    # Save as NetCDF
    dataERA_with_land.to_netcdf(output_file, engine='h5netcdf')
    print(f"Saved modified dataset to: {output_file}")

    # Verify the new shape
    print(f"Original ERA5 shape: {dataERA.t.shape}")
    print(f"New ERA5 with land shape: {dataERA_with_land.t.shape}")
    print(f"Pressure levels: {dataERA_with_land.pressure_level.values}")

    ########################################################################
    # Visualization of Surface Temperature and Land Mask From New Dataset
    ########################################################################

    # Create a figure with 1 row and 2 columns for comparison
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(24, 7))
    #fig = plt.figure(figsize=(12, 18))  

    # Determine correct origin for ERA5 based on latitude ordering
    era5_origin = 'upper' if surfaceERA_DATA.latitude.values[0] > surfaceERA_DATA.latitude.values[-1] else 'lower'
    
    # Plot 1: ERA5 Surface Temperature using matplotlib plotting
    temp_plot = ax1.imshow(
        surfaceERA_DATA.values,
        cmap='Spectral_r',
        origin=era5_origin,
        interpolation='nearest',
        extent=[surfaceERA_DATA.longitude.min(), surfaceERA_DATA.longitude.max(),
                surfaceERA_DATA.latitude.min(), surfaceERA_DATA.latitude.max()]
    )
    ax1.set_title('ERA5 Surface Temperature')
    ax1.set_xlabel('Longitude')
    ax1.set_ylabel('Latitude')

    # Determine correct origin for GLORYS based on latitude ordering
    glorys_origin = 'upper' if landData.latitude.values[0] > landData.latitude.values[-1] else 'lower'
    
    # Plot 2: Land Mask
    land_plot = ax2.imshow(
        landData.values,
        cmap='Greys_r',
        origin=glorys_origin,
        interpolation='nearest',
        extent=[landData.longitude.min(), landData.longitude.max(),
                landData.latitude.min(), landData.latitude.max()]
    )
    ax2.set_title('Land Mask')
    ax2.set_xlabel('Longitude')
    ax2.set_ylabel('Latitude')
    # Show the plot
    plt.show()

# Example usage with your Hurricane Maria request
if __name__ == "__main__": 

    # EVENT COINFIGURATION
    region = 'North America'  # Choose: 'North America', 'Europe', 'South China Sea'
    year = "2005"
    month = "09"
    day_start = 23; day_end = 29
    name = "Hurricane_Katrina_ALLVARIABLES"

    # Fixed regional coordinate grids
    Regions = {
        'North America': [50, -110, 0, -60],      # [North, West, South, East]
        'Europe': [75, -25, 35, 40],
        'South China Sea': [45, 90, -15, 155],    # 45 to -15 N, 90 to 155 E [50x65 degree box]
    }

    # Generate day list
    days = [f"{day:02d}" for day in range(day_start, day_end + 1)]
    days

    # Your Hurricane Katrina request
    era5_request = {
        'product_type': 'reanalysis',
        'variable': [
            'u_component_of_wind',
            'v_component_of_wind', 
            'vertical_velocity',
            # 'potential_vorticity',
            'temperature',
            # 'specific_humidity',
            # 'geopotential',
        ],
        'area': Regions[region], 
        'pressure_level': [
            '1000', '950', '900', '850', '700', '650', '600', 
            '550', '500', '450', '400', '350', '300', '250', 
            '200', '150', '100', '50'
        ],
        'year': [year],
        'month': [month],
        'day': days,
        'time': [f"{hour:02d}:00" for hour in range(0, 24, 6)], # This is done with a 'list comprehension': '0' is filer, '2' is decimal places, 'd' is type (decimal integer)
        'grid': [0.25, 0.25],
        'format': 'netcdf',
        'expver': '1',
        'levtype': 'pl',
        'stream': 'oper',
        'type': 'an'
    }
    
    # Download the data
    success = download_era5_data(era5_request, f'{name.lower()}_era5.nc')
    
    if success:
        print(f"{name} data downloaded successfully!")
    else:
        print("Download failed - check your request and credentials.")