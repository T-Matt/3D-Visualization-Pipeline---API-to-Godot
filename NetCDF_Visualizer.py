import xarray as xr
import numpy as np
import plotly.graph_objects as go
from matplotlib.colors import ListedColormap, to_rgba
from datetime import datetime

# =================================== 
# STREAMLINE FUNCTION (SIMPLE)
# =================================== 

def add_simple_streamlines(fig, arr_lons_flat, arr_lats_flat, arr_pressures_flat, colorscale='Spectral_r'):
    """
    Simple version that just adds basic streamlines with no wind data extraction
    """
    
    print("\n--- Adding Ultra-Simple Streamlines ---")
    
    try:
        # Create simple tangential flow pattern
        center_lon = (arr_lons_flat.min() + arr_lons_flat.max()) / 2
        center_lat = (arr_lats_flat.min() + arr_lats_flat.max()) / 2
        
        dx = arr_lons_flat - center_lon
        dy = arr_lats_flat - center_lat
        dist = np.sqrt(dx**2 + dy**2) + 1e-6
        
        speed = 15.0
        u_flow = -dy / dist * speed * np.exp(-dist/4)
        v_flow = dx / dist * speed * np.exp(-dist/4)
        w_flow = np.zeros_like(u_flow)
        
        # Use every 8th point
        indices = np.arange(0, len(arr_lons_flat), 8)
        
        fig.add_trace(go.Streamtube(
            x=arr_lons_flat[indices],
            y=arr_lats_flat[indices],
            z=arr_pressures_flat[indices],
            u=u_flow[indices],
            v=v_flow[indices],
            w=w_flow[indices],
            
            sizeref=0.2,
            colorscale=colorscale,
            opacity=0.15,
            maxdisplayed=80,
            showscale=False,
            name='Flow Pattern',
            showlegend=True
        ))
        
        print(f"Added Simple streamlines with {len(indices)} seeds")
        return True
        
    except Exception as e:
        print(f"Simple streamlines error: {e}")
        return False

"""
ULTRA-SIMPLE CALL (if the main version still has issues):

    ##############################################  
    # ULTRA-SIMPLE STREAMLINES
    ##############################################
    add_ultra_simple_streamlines(
        fig=fig,
        arr_lons_flat=arr_lons_flat,
        arr_lats_flat=arr_lats_flat,
        arr_pressures_flat=arr_pressures_flat
    )
"""

def create_era5_wind_visualization(netcdf_path, stormName=None,
                            arrcolormap_to_use = None, colormap_to_use=None, save_html=False,
                            output_filename=None, save_animation=False, animation_fps=5, time_k = 1,
                            animation_filename=None, subsample_factor_lon=3, subsample_factor_lat=3,
                            arrSubsample_factor_lon=3, arrSubsample_factor_lat=3, arrow_length=0.4, 
                            arrow_thickness=1.25, arrowhead_size = 0.3, arrOpacity=0.8,
                            volume_opacity = 0.5, landMarkerSize=1.0, vScale=4,
                            filterVectors = False, threshold_percentile = 50, region=None,
                            variable="temperature", time_step=0, pressure_range=(None, None),
                            show_arrows=True, latitude_range=(None, None), longitude_range=(None, None)):
    """
    ERA5 NetCDF Hurricane Visualization
    
    Key features from original system:
    - Uniform arrow sizing (use_unit_vectors concept)
    - Magnitude-based coloring
    - Professional layout with custom colorbar
    - 3D cubic boundaries
    - Temperature volume rendering (optional)
    
    Parameters:
    -----------
    show_arrows : bool, optional (default=True)
        If True, display wind arrow vectors. If False, hide arrows.
    latitude_range : tuple, optional (default=(None, None))
        Tuple of (min_lat, max_lat) to filter latitude range. None means no filtering.
    longitude_range : tuple, optional (default=(None, None))
        Tuple of (min_lon, max_lon) to filter longitude range. None means no filtering.
    """
    ################################################################################
    # Data Loading and Preprocessing
    ################################################################################

    print("\n=== ERA5 HURRICANE VISUALIZATION PIPELINE ===\n")
    
    # Load ERA5 NetCDF data
    print("Loading ERA5 NetCDF data...")
    ds = xr.open_dataset(netcdf_path)
    print(f"Dataset variables: {list(ds.data_vars)}")
    print(f"Dataset dimensions: {dict(ds.dims)}")

    # Apply geographic filtering
    lat_min, lat_max = latitude_range
    lon_min, lon_max = longitude_range
    
    if lat_min is not None or lat_max is not None or lon_min is not None or lon_max is not None:
        print("\n=== Applying geographic filtering ===")
        
        if lat_min is not None:
            ds = ds.where(ds.latitude >= lat_min, drop=True)
            print(f"Filtered latitude >= {lat_min}")
        if lat_max is not None:
            ds = ds.where(ds.latitude <= lat_max, drop=True)
            print(f"Filtered latitude <= {lat_max}")
        if lon_min is not None:
            ds = ds.where(ds.longitude >= lon_min, drop=True)
            print(f"Filtered longitude >= {lon_min}")
        if lon_max is not None:
            ds = ds.where(ds.longitude <= lon_max, drop=True)
            print(f"Filtered longitude <= {lon_max}")
        
        print(f"Filtered dataset dimensions: {dict(ds.dims)}")

    # Check available time steps
    n_timesteps = len(ds.valid_time)
    print(f"Available time steps: {n_timesteps}")


    if time_step >= n_timesteps or time_step < 0:
        raise ValueError(f"time_step={time_step} out of range. Must be 0-{n_timesteps-1}")
    
    # Determine which time steps to process
    if save_animation:
        time_steps_to_process = range(0,n_timesteps,time_k+1)
        print(f"Animation mode: Processing all {n_timesteps} time steps")
    else:
        time_steps_to_process = [time_step]

    # Store frames for animation
    frames = []
    fig = None


    ################################################################################
    # GLOBAL MIN/MAX CALCULATION FOR CONSISTENT ANIMATION SCALES
    ################################################################################
    global_cmin = None
    global_cmax = None
    global_temp_min = None
    global_temp_max = None

    has_temperature = 't' in ds.data_vars
    
    if save_animation and variable == "wind_speed":
        print("\n=== Calculating global wind speed range for consistent animation scale ===")
        
        # Calculate wind speed for all timesteps to find global min/max
        all_wind_speeds = []
        for t_idx in time_steps_to_process:
            u_temp = ds.u.isel(valid_time=t_idx)
            v_temp = ds.v.isel(valid_time=t_idx)
            wind_speed_temp = np.sqrt(u_temp**2 + v_temp**2)
            all_wind_speeds.append(wind_speed_temp.values.flatten())
        
        all_wind_speeds = np.concatenate(all_wind_speeds)
        all_wind_speeds = all_wind_speeds[~np.isnan(all_wind_speeds)]
        
        if filterVectors and show_arrows:
            # Apply threshold filtering globally, then use percentile for color range
            threshold_value = np.nanpercentile(all_wind_speeds, threshold_percentile)
            filtered_speeds = all_wind_speeds[all_wind_speeds >= threshold_value]
            global_cmin = float(np.percentile(filtered_speeds, 5))
            global_cmax = float(np.percentile(filtered_speeds, 95))
            print(f"Global wind speed range (filtered, {threshold_percentile}th percentile): {np.min(filtered_speeds):.1f} - {np.max(filtered_speeds):.1f} m/s")
            print(f"Color range (5th-95th percentile): {global_cmin:.1f} - {global_cmax:.1f} m/s ({global_cmin*3.6:.0f} - {global_cmax*3.6:.0f} km/h)")
        else:
            global_cmin = float(np.min(all_wind_speeds))
            global_cmax = float(np.max(all_wind_speeds))
            print(f"Global wind speed range: {global_cmin:.1f} - {global_cmax:.1f} m/s")
            print(f"Global wind speed range (km/h): {global_cmin*3.6:.0f} - {global_cmax*3.6:.0f} km/h")
        
        print("All frames will use this consistent scale")

    ###########################################################
    # PRE-CALCULATE PRESSURE FILTERING (NEEDED FOR GLOBAL CALCS)
    ###########################################################
    # Get filtered pressure levels ONCE
    available_pressures = ds.pressure_level.values
    pmin, pmax = pressure_range

    if pmin is not None or pmax is not None:
        pressure_mask = np.ones(len(available_pressures), dtype=bool)
        if pmin is not None:
            pressure_mask &= (available_pressures >= pmin)
        if pmax is not None:
            pressure_mask &= (available_pressures <= pmax)
        pressure_indices = np.where(pressure_mask)[0]
        
        if len(pressure_indices) == 0:
            raise ValueError(f"No pressure levels found in range {pressure_range}")
        
        filtered_levels = available_pressures[pressure_mask]
    else:
        filtered_levels = available_pressures
        pressure_indices = np.arange(len(available_pressures))
        print("Using all pressure levels")

    print(f"Filtered pressure levels: {filtered_levels}")

    # Now calculate global temperature range if needed
    if save_animation and variable == "t" and has_temperature:
        print("\n=== Calculating level-by-level temperature anomaly normalization ===")
        
        # Calculate temperature anomalies for all timesteps (level-by-level)
        all_temp_anomalies = []
        for t_idx in time_steps_to_process:
            temp_temp = ds['t'].isel(valid_time=t_idx)
            if pmin is not None or pmax is not None:
                temp_temp = temp_temp.isel(pressure_level=pressure_indices)
            
            # Calculate level-by-level anomaly (removes vertical gradient)
            temp_data = temp_temp.values  # shape: (levels, lat, lon)
            temp_anomaly = np.zeros_like(temp_data)
            
            for lev_idx in range(temp_data.shape[0]):
                level_mean = np.nanmean(temp_data[lev_idx, :, :])
                temp_anomaly[lev_idx, :, :] = temp_data[lev_idx, :, :] - level_mean
            
            all_temp_anomalies.append(temp_anomaly.flatten())
        
        all_temp_anomalies = np.concatenate(all_temp_anomalies)
        all_temp_anomalies = all_temp_anomalies[~np.isnan(all_temp_anomalies)]
        
        # Calculate 95% interval (2.5th to 97.5th percentile)
        global_cmin = float(np.percentile(all_temp_anomalies, 2.5))
        global_cmax = float(np.percentile(all_temp_anomalies, 97.5))
        
        # Store full range for reference
        global_temp_min = float(np.min(all_temp_anomalies))
        global_temp_max = float(np.max(all_temp_anomalies))
        
        print(f"Level-by-level anomaly full range: {global_temp_min:.2f} to {global_temp_max:.2f} K")
        print(f"Level-by-level anomaly 95% interval: {global_cmin:.2f} to {global_cmax:.2f} K")
        print("Using level-specific means to highlight horizontal temperature gradients")

    ###########################################################
    # PRE-CALCULATE ALL COORDINATES (ONCE, BEFORE LOOP)
    ###########################################################
    print("\n=== Pre-calculating coordinate systems ===")

    # NATIVE RESOLUTION - Calculate ONCE
    native_lons = ds.longitude.values
    native_lats = ds.latitude.values
    native_levels = filtered_levels

    print(f"Native resolution - Lons: {len(native_lons)}, Lats: {len(native_lats)}, Levels: {len(native_levels)}")

    native_pressures_mesh, native_lats_mesh, native_lons_mesh = np.meshgrid(
        native_levels, native_lats, native_lons, indexing='ij'
    )
    native_lons_flat = native_lons_mesh.flatten()
    native_lats_flat = native_lats_mesh.flatten()
    native_pressures_flat = native_pressures_mesh.flatten()

    # VOLUME RESOLUTION - Calculate ONCE
    vol_lons = ds.longitude[::subsample_factor_lon].values
    vol_lats = ds.latitude[::subsample_factor_lat].values
    vol_levels = native_levels

    print(f"Volume coordinates - Lons: {len(vol_lons)}, Lats: {len(vol_lats)}, Levels: {len(vol_levels)}")

    vol_pressures_mesh, vol_lats_mesh, vol_lons_mesh = np.meshgrid(
        vol_levels, vol_lats, vol_lons, indexing='ij'
    )
    vol_lons_flat = vol_lons_mesh.flatten()
    vol_lats_flat = vol_lats_mesh.flatten()
    vol_pressures_flat = vol_pressures_mesh.flatten()

    # ARROW RESOLUTION - Calculate ONCE (only if arrows enabled)
    if show_arrows:
        arr_lons = ds.longitude[::arrSubsample_factor_lon].values
        arr_lats = ds.latitude[::arrSubsample_factor_lat].values
        arr_levels = native_levels

        print(f"Arrow coordinates - Lons: {len(arr_lons)}, Lats: {len(arr_lats)}, Levels: {len(arr_levels)}")

        arr_pressures_mesh, arr_lats_mesh, arr_lons_mesh = np.meshgrid(
            arr_levels, arr_lats, arr_lons, indexing='ij'
        )
        arr_lons_flat = arr_lons_mesh.flatten()
        arr_lats_flat = arr_lats_mesh.flatten()
        arr_pressures_flat = arr_pressures_mesh.flatten()
    else:
        print("Arrow visualization disabled (show_arrows=False)")

    # BORDER - Calculate ONCE
    lon_range = [native_lons.min(), native_lons.max()]
    lat_range = [native_lats.min(), native_lats.max()]
    dep_range = [native_levels.min(), native_levels.max()]

    # Define cube edges ONCE
    cube_edges = [
        # Bottom face (high pressure/surface)
        ([lon_range[0], lon_range[1]], [lat_range[0], lat_range[0]], [dep_range[0], dep_range[0]]),
        ([lon_range[1], lon_range[1]], [lat_range[0], lat_range[1]], [dep_range[0], dep_range[0]]),
        ([lon_range[1], lon_range[0]], [lat_range[1], lat_range[1]], [dep_range[0], dep_range[0]]),
        ([lon_range[0], lon_range[0]], [lat_range[1], lat_range[0]], [dep_range[0], dep_range[0]]),
        
        # Top face (low pressure/altitude)
        ([lon_range[0], lon_range[1]], [lat_range[0], lat_range[0]], [dep_range[1], dep_range[1]]),
        ([lon_range[1], lon_range[1]], [lat_range[0], lat_range[1]], [dep_range[1], dep_range[1]]),
        ([lon_range[1], lon_range[0]], [lat_range[1], lat_range[1]], [dep_range[1], dep_range[1]]),
        ([lon_range[0], lon_range[0]], [lat_range[1], lat_range[0]], [dep_range[1], dep_range[1]]),
        
        # Vertical edges
        ([lon_range[0], lon_range[0]], [lat_range[0], lat_range[0]], [dep_range[0], dep_range[1]]),
        ([lon_range[1], lon_range[1]], [lat_range[0], lat_range[0]], [dep_range[0], dep_range[1]]),
        ([lon_range[1], lon_range[1]], [lat_range[1], lat_range[1]], [dep_range[0], dep_range[1]]),
        ([lon_range[0], lon_range[0]], [lat_range[1], lat_range[1]], [dep_range[0], dep_range[1]])
    ]

    print("=== Coordinate systems pre-calculated ===\n")

    # Convert matplotlib colormap to plotly format (from original system)
    if isinstance(colormap_to_use, ListedColormap):
            n_colors = len(colormap_to_use.colors)
            plotly_colorscale = [
            [i/(n_colors-1), f'rgb({int(255*r)},{int(255*g)},{int(255*b)})']
            for i, (r,g,b,a) in enumerate(colormap_to_use.colors)
            ]
            print(f"Converted matplotlib colormap to plotly format with {n_colors} colors")
    else:
        plotly_colorscale = colormap_to_use

    # Convert matplotlib colormap to plotly format for arrows (only if arrows enabled)
    if show_arrows:
        if isinstance(arrcolormap_to_use, ListedColormap):
            n_arrColors = len(arrcolormap_to_use.colors)
            arrColorscale = [
                [i/(n_arrColors-1), f'rgb({int(255*r)},{int(255*g)},{int(255*b)})'] 
                for i, (r,g,b,a) in enumerate(arrcolormap_to_use.colors)
            ]
            print(f"Converted matplotlib colormap to plotly format with {n_arrColors} colors")
        else:
            arrColorscale = arrcolormap_to_use

    # Initialize figure
    fig = go.Figure()

    has_temperature = 't' in ds.data_vars

    ###########################################################
    # Looping through each time step
    ###########################################################
    
    # Process each time step
    for t_idx in time_steps_to_process:
        print(f"\n--- Processing time step {t_idx}/{n_timesteps-1} ---")

        # Extract Data
        selected_time = ds.valid_time.values[t_idx]
        time_str = np.datetime_as_string(selected_time, unit='m')

        # Extract wind components at this time step
        u = ds['u'].isel(valid_time=t_idx)
        v = ds['v'].isel(valid_time=t_idx)

        # Extract pre-computed wind speed at this time step
        wind_speed = ds['wind_speed'].isel(valid_time=t_idx)
        wind_speed = wind_speed.isel(pressure_level=pressure_indices)

        # Use pre-calculated pressure indices
        u = u.isel(pressure_level=pressure_indices)
        v = v.isel(pressure_level=pressure_indices)

        # Calculate wind speed
        wind_speed = np.sqrt(u**2 + v**2)
        print(f"Wind data shape: {wind_speed.shape}")

        # Load temperature if needed
        if has_temperature:
            temperature = ds['t'].isel(valid_time=t_idx)
            if pmin is not None or pmax is not None:
                temperature = temperature.isel(pressure_level=pressure_indices)


        ################################################################################
        # NATIVE RESOLUTION - Land Data (use pre-calculated coordinates)
        ################################################################################

        print("Using pre-calculated NATIVE resolution coordinates...")

        # Get native temperature data if available
        if has_temperature:
            native_temp_flat = temperature.values.flatten()
        else:
            native_temp_flat = None

        print(f"Native data shape: {native_lons_flat.shape}")

        ################################################################################
        # VOLUME RESOLUTION - Use pre-calculated coordinates
        ################################################################################

        print(f"Applying volume subsampling (using pre-calculated coordinates)...")

        # Subsample DATA only (coordinates already calculated)
        u_vol_sub = u[:, ::subsample_factor_lat, ::subsample_factor_lon]
        v_vol_sub = v[:, ::subsample_factor_lat, ::subsample_factor_lon]
        wind_speed_vol_sub = wind_speed[:, ::subsample_factor_lat, ::subsample_factor_lon]

        # Subsample temperature if available
        if has_temperature:
            temp_vol_sub = temperature[:, ::subsample_factor_lat, ::subsample_factor_lon]

        print(f"Volume subsampled shape: {wind_speed_vol_sub.shape}")

        # Select volume data based on variable parameter
        if variable == "wind_speed":
            volume_data_flat = wind_speed_vol_sub.values.flatten()
            volume_name = "Wind Speed Volume"
            print("Using wind speed for volume rendering")
        elif variable == "t":
            # Calculate level-by-level temperature anomaly (removes vertical gradient)
            temp_data = temp_vol_sub.values  # shape: (levels, lat, lon)
            temp_anomaly = np.zeros_like(temp_data)
            
            for lev_idx in range(temp_data.shape[0]):
                level_mean = np.nanmean(temp_data[lev_idx, :, :])
                temp_anomaly[lev_idx, :, :] = temp_data[lev_idx, :, :] - level_mean
            
            volume_data_flat = temp_anomaly.flatten()
            volume_name = "Temperature Anomaly (Level-by-Level)"
            print(f"Using level-by-level temperature anomaly for volume rendering")
            print(f"Anomaly range: {np.nanmin(temp_anomaly):.2f} to {np.nanmax(temp_anomaly):.2f} K")
            
            # For animations, global range is already set from 95% percentile calculation
            # For single frames, calculate it now
            if global_cmin is None or global_cmax is None:
                # Use 95% interval for single frame as well
                temp_anom_flat = temp_anomaly.flatten()
                temp_anom_flat = temp_anom_flat[~np.isnan(temp_anom_flat)]
                global_cmin = float(np.percentile(temp_anom_flat, 2.5))
                global_cmax = float(np.percentile(temp_anom_flat, 97.5))
                print(f"Single frame 95% anomaly interval: {global_cmin:.2f} to {global_cmax:.2f} K")
        elif variable == "specific_humidity":
            if 'specific_humidity' not in ds.data_vars:
                raise ValueError("specific_humidity not found in dataset")
            spec_hum = ds['specific_humidity'].isel(valid_time=t_idx, pressure_level=pressure_indices)
            spec_hum_vol_sub = spec_hum[:, ::subsample_factor_lat, ::subsample_factor_lon]
            volume_data_flat = spec_hum_vol_sub.values.flatten()
            volume_name = "Specific Humidity Volume"
            print("Using specific humidity for volume rendering")
        elif variable == "potential_vorticity":
            if 'potential_vorticity' not in ds.data_vars:
                raise ValueError("potential_vorticity not found in dataset")
            pot_vort = ds['potential_vorticity'].isel(valid_time=t_idx, pressure_level=pressure_indices)
            pot_vort_vol_sub = pot_vort[:, ::subsample_factor_lat, ::subsample_factor_lon]
            volume_data_flat = pot_vort_vol_sub.values.flatten()
            volume_name = "Potential Vorticity Volume"
            print("Using potential vorticity for volume rendering")
        elif variable == "geopotential":
            if 'geopotential' not in ds.data_vars:
                raise ValueError("geopotential not found in dataset")
            geopot = ds['geopotential'].isel(valid_time=t_idx, pressure_level=pressure_indices)
            geopot_vol_sub = geopot[:, ::subsample_factor_lat, ::subsample_factor_lon]
            volume_data_flat = geopot_vol_sub.values.flatten()
            volume_name = "Geopotential Volume"
            print("Using geopotential for volume rendering")
        else:
            raise ValueError(f"Invalid variable '{variable}'. Supported: 'wind_speed', 't', 'specific_humidity', 'potential_vorticity', 'geopotential'")


        ################################################################################
        # ARROW RESOLUTION - Apply arrSubsample_factor_* (Lowest Resolution)
        ################################################################################

        if show_arrows:
            print(f"Applying wind arrow subsampling (using pre-calculated coordinates)...")

            # Subsample DATA only
            u_arr_sub = u[:, ::arrSubsample_factor_lat, ::arrSubsample_factor_lon]
            v_arr_sub = v[:, ::arrSubsample_factor_lat, ::arrSubsample_factor_lon]
            wind_speed_arr_sub = wind_speed[:, ::arrSubsample_factor_lat, ::arrSubsample_factor_lon]

            print(f"Arrow subsampled shape: {wind_speed_arr_sub.shape}")

            # Use pre-calculated coordinates
            lons_sample = arr_lons_flat
            lats_sample = arr_lats_flat
            pressures_sample = arr_pressures_flat

            u_flat = u_arr_sub.values.flatten()
            v_flat = v_arr_sub.values.flatten()
            wind_speed_flat = wind_speed_arr_sub.values.flatten()

            # Calculate unit vectors for arrows
            wind_speed_safe = np.where(wind_speed_flat > 0.1, wind_speed_flat, 0.1)
            u_unit = (u_flat / wind_speed_safe) * arrow_length
            v_unit = (v_flat / wind_speed_safe) * arrow_length
            w_unit = np.zeros_like(u_unit) # No vertical component

            print("Calculated unit vectors for wind arrows")

            # Find min/max wind speed for annotations
            cMin = float(np.nanmin(wind_speed_flat))
            cMax = float(np.nanmax(wind_speed_flat))
            cMin_kmh = round(cMin * 3.6)
            cMax_kmh = round(cMax * 3.6)
            print(f"Wind speed range: {cMin:.1f} - {cMax:.1f} m/s ({cMin_kmh} - {cMax_kmh} km/h)")

            if filterVectors:
                thr = np.nanpercentile(wind_speed_flat, threshold_percentile) # Define threshold
                print(f"Applying vector filtering at {threshold_percentile}th percentile: {thr:.1f} m/s")
                significant_vectors = wind_speed_flat >= thr
                print(f"Vectors meeting threshold: {np.sum(significant_vectors)}/{len(wind_speed_flat)} "
                f"({(np.sum(significant_vectors)/len(wind_speed_flat))*100:.1f}%)")
            else:
                significant_vectors = np.ones_like(wind_speed_flat, dtype=bool)

            # Arrow parameters
            arrowhead_length = arrow_length * arrowhead_size # Arrowhead proportional to arrow length

            # Create arrow endpoints
            arrow_x = []
            arrow_y = []
            arrow_z = []
            colors = []

            added = 0
            skipped = 0

            for i in range(len(lons_sample)):
                if not significant_vectors[i]:
                    skipped += 1
                    continue
                
                # Arrow start and end points
                x_start = lons_sample[i]
                y_start = lats_sample[i]
                z_start = pressures_sample[i]
                
                x_end = x_start + u_unit[i]
                y_end = y_start + v_unit[i]
                z_end = z_start + w_unit[i]
                
                # Add vector shaft
                arrow_x.extend([x_start, x_end, None])
                arrow_y.extend([y_start, y_end, None])
                arrow_z.extend([z_start, z_end, None])
                colors.extend([wind_speed_flat[i], wind_speed_flat[i], wind_speed_flat[i]])
                
                # Calculate arrowhead direction (2D horizontal)
                angle = np.arctan2(v_unit[i], u_unit[i])
                
                # Add arrowheads with changeable degrees on either side
                left_angle = angle + np.pi - np.pi/12 # 180 - pi/12 (15 degrees)
                right_angle = angle + np.pi + np.pi/12 # 180 + pi/12 (15 degrees)
                
                x_left = x_end + arrowhead_length * np.cos(left_angle)
                y_left = y_end + arrowhead_length * np.sin(left_angle)
                x_right = x_end + arrowhead_length * np.cos(right_angle)
                y_right = y_end + arrowhead_length * np.sin(right_angle)
                
                # Add left arrowhead line
                arrow_x.extend([x_end, x_left, None])
                arrow_y.extend([y_end, y_left, None])
                arrow_z.extend([z_end, z_end, None])
                colors.extend([wind_speed_flat[i], wind_speed_flat[i], wind_speed_flat[i]])
                
                # Add right arrowhead line
                arrow_x.extend([x_end, x_right, None])
                arrow_y.extend([y_end, y_right, None])
                arrow_z.extend([z_end, z_end, None])

                # Add colors for right arrowhead with wind speed scaling to km/h
                colors.extend([wind_speed_flat[i], wind_speed_flat[i], wind_speed_flat[i]])
                
                added += 1

            print(f"Arrow statistics: Added {added} vectors, Skipped {skipped} vectors")

            # Calculate ranges in m/s using percentile for better color spread
            if save_animation and global_cmin is not None and global_cmax is not None:
                # USE GLOBAL SCALE FOR ANIMATION
                cmin_use = global_cmin
                cmax_use = global_cmax
                print(f"Using global animation scale: {cmin_use:.1f} - {cmax_use:.1f} m/s")
            elif filterVectors and added > 0:
                # Recalculate min/max from DISPLAYED vectors only (single frame mode)
                colors_array = np.array(colors)
                colors_array = colors_array[~np.isnan(colors_array)] # Remove None separators
                # Use 5th-95th percentile for better color distribution
                cmin_use = float(np.percentile(colors_array, 5)) # m/s
                cmax_use = float(np.percentile(colors_array, 95)) # m/s
                print(f"Original range: {cMin:.1f} - {cMax:.1f} m/s")
                print(f"Using filtered color range (5th-95th percentile): {cmin_use:.1f} - {cmax_use:.1f} m/s")

            else:
                cmin_use = cMin # m/s
                cmax_use = cMax # m/s
                print(f"Using full color range: {cmin_use:.1f} - {cmax_use:.1f} m/s")

            # Convert to km/h for display only
            cmin_use_kmh = round(cmin_use * 3.6)
            cmax_use_kmh = round(cmax_use * 3.6)

        ################################################################################
        # BORDER line addition section
        ################################################################################

        print(f"🔳 Using pre-calculated cubic border...")
        # Border lines will be added to figure later using cube_edges


        ################################################################################
        # ANIMATION SETUP
        ################################################################################
        # For animation, we need to create frame data
        if save_animation:
            # Create a dictionary of all trace data for this frame
            frame_data = []
            
            # Add land data if available
            if has_temperature:
                land_mask = (native_pressures_flat == 1013) & (native_temp_flat == -10)
                if np.sum(land_mask) > 0:
                    frame_data.append(go.Scatter3d(
                    x=native_lons_flat[land_mask],
                    y=native_lats_flat[land_mask],
                    z=native_pressures_flat[land_mask],
                    mode='markers',
                    marker=dict(size=landMarkerSize, color="black", showscale=False),
                    showlegend=False
                    ))
            all_variables = ['wind_speed', 't', 'specific_humidity', 'potential_vorticity', 'geopotential']
            # Add volume rendering
            frame_data.append(go.Volume(
                x=vol_lons_flat,
                y=vol_lats_flat,
                z=vol_pressures_flat,
                value=volume_data_flat,
                opacity=volume_opacity,
                surface_count=10,
                colorscale=plotly_colorscale if (variable in all_variables) else 'RdBu_r',
                cmin=global_cmin if (variable  in all_variables) and global_cmin is not None else None,
                cmax=global_cmax if (variable in all_variables) and global_cmax is not None else None,
                showscale=True,
                colorbar=dict(
                    title="Wind Speed<br>(km/h)",
                    titleside="right",
                    titlefont=dict(size=14),
                    tickmode='array',
                    tickvals=np.linspace(global_cmin, global_cmax, 6) if global_cmin is not None else None,
                    ticktext=[f"{int(v*3.6)}" for v in np.linspace(global_cmin, global_cmax, 6)] if global_cmin is not None else None,
                    tickfont=dict(size=12),
                    lenmode='fraction',
                    len=0.75,
                    thickness=20,
                    x=1.02
                ) if (variable == "wind_speed" and global_cmin is not None) else None,
                name=volume_name
            ))
            
            # Add border
            for i, (x_vals, y_vals, z_vals) in enumerate(cube_edges):
                frame_data.append(go.Scatter3d(
                    x=x_vals, y=y_vals, z=z_vals,
                    mode='lines',
                    line=dict(color='black', width=4),
                    showlegend=False,
                    hoverinfo='skip'
                ))
            
            # Add arrows (only if enabled)
            if show_arrows:
                frame_data.append(go.Scatter3d(
                    x=arrow_x,
                    y=arrow_y,
                    z=arrow_z,
                    mode='lines',
                    opacity=arrOpacity,
                    line=dict(
                        color=colors,
                        colorscale=arrColorscale,
                        cmin=cmin_use,
                        cmax=cmax_use,
                        width=arrow_thickness,
                        showscale=False,
                        colorbar=dict(
                            title="Wind Speed<br>(km/h)",
                            titleside="right",
                            tickmode='array',
                            tickvals=np.linspace(cmin_use, cmax_use, 6),
                            ticktext=[f"{int(v*3.6)}" for v in np.linspace(cmin_use, cmax_use, 6)],
                        )
                    ),
                    showlegend=False
                ))
            
            # Create pressure range string
            if pmin is not None and pmax is not None:
                pressure_str = f" [{pmin}-{pmax} hPa]"
            elif pmin is not None:
                    pressure_str = f" [≥{pmin} hPa]"
            elif pmax is not None:
                pressure_str = f" [≤{pmax} hPa]"
            else:
                pressure_str = ""
            
            # Add frame with layout
            frames.append(go.Frame(
                data=frame_data,
                name=str(t_idx),
                layout=go.Layout(
                title=dict(
                    text=f"3D Hurricane Wind Field - ERA5 [{time_str}]{pressure_str}",
                    x=0.5,
                    y=0.95,
                    xanchor='center',
                    yanchor='top',
                    font=dict(size=24, color='black')
                    )
                )
            ))
            
            print(f"Frame {t_idx} created with {len(frame_data)} traces")

        else:
            ################################################################################
            # Plotly 3D Visualization
            ################################################################################

            ###############################################
            # Land Data - NATIVE RESOLUTION (Highest Detail)
            ###############################################

            print("Processing land data at native resolution...")

            if has_temperature:
                # Filter for 1013 hPa pressure level at NATIVE resolution
                land_mask = (native_pressures_flat == 1013) & (native_temp_flat == -10)
                lons_land = native_lons_flat[land_mask]
                lats_land = native_lats_flat[land_mask]
                pressures_land = native_pressures_flat[land_mask]
                
                fig.add_trace(go.Scatter3d(
                    x=lons_land,
                    y=lats_land,
                    z=pressures_land,
                    mode='markers',
                    marker=dict(size=landMarkerSize, color="white", showscale=False),
                    name="Land",
                    showlegend=False
                    ))
                print(f"Land points at 1013 hPa (native): {len(lons_land)}")
            else:
                print("No temperature data - skipping land mask")

            ###############################################
            # Volume Rendering - VOLUME RESOLUTION
            ###############################################

            all_variables = ['wind_speed', 't', 'specific_humidity', 'potential_vorticity', 'geopotential']

            fig.add_trace(go.Volume(
                x=vol_lons_flat,
                y=vol_lats_flat,
                z=vol_pressures_flat,
                value=volume_data_flat,
                opacity=volume_opacity,
                surface_count=10,
                colorscale=plotly_colorscale if (variable in all_variables) else 'RdBu_r',
                cmin=cmin_use if (variable in all_variables and filterVectors and show_arrows) else None,
                cmax=cmax_use if (variable in all_variables and filterVectors and show_arrows) else None,
                showscale=True if variable in all_variables else False,
                colorbar=dict(
                        title="Wind Speed<br>(km/h)",
                        titleside="right",
                        titlefont=dict(size=14),
                        tickmode='array', # Use explicit tick values
                        tickvals=np.linspace(cmin_use, cmax_use, 6) if show_arrows else None, # 6 evenly spaced ticks in m/s
                        ticktext=[f"{int(v*3.6)}" for v in np.linspace(cmin_use, cmax_use, 6)] if show_arrows else None, # Convert to km/h
                        tickfont=dict(size=12),
                        lenmode='fraction',
                        len=0.75, # Colorbar length
                        thickness=20,
                        x=1.02 # Position from right edge
                    ) if (variable == "wind_speed" and show_arrows) else None,
                name=volume_name
            ))
            print(f"Added {volume_name}")

            ###############################################
            # BORDER
            ###############################################
            for i, (x_vals, y_vals, z_vals) in enumerate(cube_edges):
                fig.add_trace(go.Scatter3d(
                    x=x_vals, y=y_vals, z=z_vals,
                    mode='lines',
                    line=dict(color='black', width=4),
                    showlegend=False,
                    hoverinfo='skip',
                    name='Border' if i == 0 else None
                ))

            ##############################################
            # ARROWS (only if enabled)
            ##############################################
            if show_arrows:
                fig.add_trace(go.Scatter3d(
                    x=arrow_x,
                    y=arrow_y,
                    z=arrow_z,
                    mode='lines',
                    opacity=arrOpacity,
                    line=dict(
                        color=colors, # in m/s
                        colorscale=arrColorscale,
                        cmin=cmin_use, # in m/s
                        cmax=cmax_use, # in m/s
                        width=arrow_thickness,
                        showscale=False
                    ),
                    name='Wind Arrows',
                    showlegend=False
                ))
                
                print(f"Added {len(arr_lons_flat)} uniform wind arrows")

                ##############################################  
                # STREAMLINES (FINAL CORRECTED VERSION)
                ##############################################
                # add_streamlines_final(
                #     fig=fig,
                #     ds=ds,
                #     time_step=time_step,
                #     arr_lons_flat=arr_lons_flat,
                #     arr_lats_flat=arr_lats_flat,
                #     arr_pressures_flat=arr_pressures_flat,
                #     arrSubsample_factor_lon=arrSubsample_factor_lon,
                #     arrSubsample_factor_lat=arrSubsample_factor_lat,
                #     native_levels=native_levels,
                #     variable=variable,
                #     plotly_colorscale=plotly_colorscale
                # )

                ##############################################  
                # ULTRA-SIMPLE STREAMLINES
                ##############################################
                add_simple_streamlines(
                    fig=fig,
                    arr_lons_flat=arr_lons_flat,
                    arr_lats_flat=arr_lats_flat,
                    arr_pressures_flat=arr_pressures_flat,
                    colorscale=plotly_colorscale,
                    # Normalize colors to the global min/max wind speed
                    cmin=cmin_use,
                    cmax=cmax_use
                )
            else:
                print("Skipping arrow and streamline visualization (show_arrows=False)")
            
            ##################################################
            # Labels and Annotations (3D Version)
            ##################################################
            # Define labels for each region


    ################################################################################
    # Animation Saving
    ################################################################################
        
    # Create the figure
    if save_animation:
        print("\n=== Creating Animation ===")

        longitude_grid_points = len(ds.longitude.values)
        latitude_grid_points = len(ds.latitude.values)
        print("Longitude grid points:", longitude_grid_points)
        print("Latitude grid points:", latitude_grid_points)
        
        # Use the first frame's data as initial state
        fig = go.Figure(data=frames[0].data, frames=frames)

        frame_duration = int(1000 / animation_fps) # Convert FPS to milliseconds
        transition_duration = int(frame_duration * 0.5) # Transition is half of frame duration
        
        # Update layout for animation
        fig.update_layout(
            width=1600,
            height=900,
            updatemenus=[
            dict(
                type="buttons",
                direction="left",
                x=0.1,
                y=0.05,
                xanchor="left",
                yanchor="bottom",
                buttons=[
                    dict(label="Play",
                        method="animate",
                        args=[None, {"frame": {"duration": frame_duration, "redraw": True},
                            "fromcurrent": True,
                            "mode": "immediate",
                            "transition": {"duration": transition_duration}}]),
                    dict(label="Pause",
                        method="animate",
                        args=[[None], {"frame": {"duration": 0, "redraw": False},
                            "mode": "immediate",
                            "transition": {"duration": 0}}])
                    ]
                )
            ],
            scene=dict(
                aspectmode='manual',
                aspectratio=dict(
                    x=longitude_grid_points/latitude_grid_points, # longitude grid points / latitude grid points
                    y=1, # latitude baseline
                    z=len(filtered_levels) / latitude_grid_points * vScale # pressure levels / latitude grid points scaled
                ),
                xaxis=dict(
                    title=dict(text="Longitude", font=dict(size=16)),
                    tickfont=dict(size=14),
                    backgroundcolor='skyblue',  # Change this
                    gridcolor='white',            # Grid line color
                    zerolinecolor='black',        # Zero line color
                    autorange='reversed'
                ),
                yaxis=dict(
                    title=dict(text="Latitude", font=dict(size=16)),
                    tickfont=dict(size=14),
                    backgroundcolor='skyblue',  # Change this
                    gridcolor='white',
                    zerolinecolor='black', 
                    autorange='reversed'
                ),
                zaxis=dict(
                    title=dict(text="Pressure Level (hPa)", font=dict(size=16)),
                    tickfont=dict(size=14),
                    backgroundcolor='steelblue', # Change this
                    gridcolor='white',
                    zerolinecolor='black',
                    autorange='reversed'
                )
            )
        )

        def frame_args(duration):
            return {
                    "frame": {"duration": duration},
                    "mode": "immediate",
                    "fromcurrent": True,
                    "transition": {"duration": duration, "easing": "linear"},
                }

        sliders = [
                    {
                        "pad": {"b": 10, "t": 60},
                        "len": 0.9,
                        "x": 0.1,
                        "y": 0,
                        "steps": [
                            {
                                "args": [[f.name], frame_args(0)],
                                "label": str(k),
                                "method": "animate",
                            }
                            for k, f in enumerate(fig.frames)
                        ],
                    }
                ]
            
        fig.update_layout(sliders=sliders)

        ##################################################
        # Labels and Annotations (3D Version)
        ##################################################
        # Define labels for each region
        # South China Sea: [45, 90, -15, 155]

        # Save animation
        if animation_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            animation_filename = f"era5_hurricane_animation_{timestamp}.html"
        elif not animation_filename.endswith('.html'):
            animation_filename = animation_filename + '.html'
        
        print(f"Saving animation to {animation_filename}")
        fig.write_html(animation_filename)
        print(f"Animation saved successfully with {len(frames)} frames!")
    else:
        print("\n=== Creating Single Frame Visualization ===") 

        ##############################################################################
        # Layout Customization
        ##############################################################################

        # Format the datetime for the title
        time_str = np.datetime_as_string(selected_time, unit='m') # Format: YYYY-MM-DD HH:MM

        longitude_grid_points = len(ds.longitude.values)
        latitude_grid_points = len(ds.latitude.values)
        print("Longitude grid points:", longitude_grid_points)
        print("Latitude grid points:", latitude_grid_points)
    

        # Create pressure range string for title
        if pmin is not None and pmax is not None:
            pressure_str = f" [{pmin}-{pmax} hPa]"
        elif pmin is not None:
            pressure_str = f" [≥{pmin} hPa]"
        elif pmax is not None:
            pressure_str = f" [≤{pmax} hPa]"
        else:
            pressure_str = ""

        if stormName is None:    
            stormName = "Unnamed"

        # Build annotations list (only include wind speed annotations if arrows are shown)
        annotations_list = []
        if show_arrows:
            annotations_list.extend([
                dict(
                    x=1.20, y=0.92,
                    xref='paper', yref='paper',
                    text=f"Max: {cmax_use_kmh} km/h",
                    showarrow=False,
                    font=dict(size=12, color='black'),
                    align='left'
                ),
                dict(
                    x=1.20, y=0.08,
                    xref='paper', yref='paper',
                    text=f"Min: {cmin_use_kmh} km/h",
                    showarrow=False,
                    font=dict(size=12, color='black'),
                    align='left'
                )
            ])

        fig.update_layout(
            width=1000,
            height=500,
            title=dict(
                text=rf"Hurricane {stormName} Wind Field | Date: [ {time_str} ] [ {pressure_str} ] | ERA5 Data",
                x=0.5,
                y=0.95,
                xanchor='center',
                yanchor='top',
                font=dict(size=16, color='black')
            ),
            scene=dict(
                bgcolor='black',
                aspectmode='manual',
                aspectratio=dict(
                    x=longitude_grid_points/latitude_grid_points, # longitude grid points / latitude grid points
                    y=1, # latitude baseline
                    z=len(filtered_levels) / latitude_grid_points * vScale # pressure levels / latitude grid points scaled
                ),
                xaxis=dict(
                    title=dict(text="Longitude", font=dict(size=16)),
                    tickfont=dict(size=14),
                    backgroundcolor='skyblue',  # Change this
                    gridcolor='white',            # Grid line color
                    zerolinecolor='black',        # Zero line color
                    autorange='reversed'
                ),
                yaxis=dict(
                    title=dict(text="Latitude", font=dict(size=16)),
                    tickfont=dict(size=14),
                    backgroundcolor='skyblue',  # Change this
                    gridcolor='white',
                    zerolinecolor='black'
                ),
                zaxis=dict(
                    title=dict(text="Pressure Level (hPa)", font=dict(size=16)),
                    tickfont=dict(size=14),
                    backgroundcolor='skyblue', # Change this
                    gridcolor='white',
                    zerolinecolor='black',
                    autorange='reversed'
                )
            ),
            annotations=annotations_list
        )
        
        
        # Save HTML if requested (matching original system)
        if save_html:
            if output_filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"era5_hurricane_visualization_{timestamp}.html"
            elif not output_filename.endswith('.html'):
                output_filename = output_filename + '.html'
        
            print(f"\nSaving visualization to {output_filename}")
            fig.write_html(output_filename)
            print("Visualization saved successfully!")
    
    print("\n=== ERA5 Visualization Complete ===")

