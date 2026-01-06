import numpy as np
import xarray as xr
from scipy.interpolate import PchipInterpolator

def pchip_interpolate_era5(input_file, output_file, substeps=12):
    """
    PCHIP interpolation for ERA5 atmospheric variables
    Handles NaN and invalid values by preserving them across timesteps
    """
    
    # Load dataset
    ds = xr.open_dataset(input_file)
    
    # Detect time interval (hours)
    time_delta = (ds.valid_time[1] - ds.valid_time[0]).values / np.timedelta64(1, 'h')
    print(f"Detected {time_delta:.0f}-hour intervals, creating {substeps} substeps")
    
    # Create time grids
    n_original = len(ds.valid_time)
    original_hours = np.arange(n_original) * time_delta
    new_hours = np.arange(0, original_hours[-1] + 1, time_delta/substeps)
    
    # Variables to interpolate
    vars_to_interp = ['t', 'u', 'v', 'w']
    interpolated_data = {}
    
    # Interpolate each variable
    for var in vars_to_interp:
        print(f"Interpolating {var}...")
        data = ds[var].values
        
        # Initialize output array
        new_data = np.empty((len(new_hours),) + data.shape[1:])
        
        # Count valid vs invalid grid points
        total_points = data.shape[1] * data.shape[2] * data.shape[3]
        valid_count = 0
        invalid_count = 0
        
        # Interpolate each grid point
        for i in range(data.shape[1]):  # pressure levels
            for j in range(data.shape[2]):  # latitudes  
                for k in range(data.shape[3]):  # longitudes
                    time_series = data[:, i, j, k]
                    
                    # Check if time series contains valid data for interpolation
                    is_finite = np.isfinite(time_series)
                    valid_points = np.sum(is_finite)
                    
                    if valid_points >= 2:
                        # Enough valid points for interpolation
                        try:
                            interpolator = PchipInterpolator(original_hours, time_series)
                            new_data[:, i, j, k] = interpolator(new_hours)
                            valid_count += 1
                        except ValueError:
                            # Fallback: replicate first valid value or NaN
                            if valid_points > 0:
                                first_valid = time_series[is_finite][0]
                                new_data[:, i, j, k] = first_valid
                            else:
                                new_data[:, i, j, k] = np.nan
                            invalid_count += 1
                    elif valid_points == 1:
                        # Only one valid point - replicate it
                        valid_value = time_series[is_finite][0]
                        new_data[:, i, j, k] = valid_value
                        invalid_count += 1
                    else:
                        # No valid points - preserve original pattern (likely land mask)
                        # Replicate the first timestep's value (NaN, negative, etc.)
                        new_data[:, i, j, k] = time_series[0]
                        invalid_count += 1
        
        print(f"  Valid interpolations: {valid_count}/{total_points} ({100*valid_count/total_points:.1f}%)")
        print(f"  Preserved patterns: {invalid_count}/{total_points} ({100*invalid_count/total_points:.1f}%)")
        
        interpolated_data[var] = new_data
    
    # Compute wind speed: |V| = √(u² + v² + w²)
    print("Computing wind speed...")
    u_new = interpolated_data['u']
    v_new = interpolated_data['v'] 
    w_new = interpolated_data['w']
    
    # Compute wind speed, preserving NaN/invalid patterns
    wind_speed = np.sqrt(u_new**2 + v_new**2 + w_new**2)
    
    # Where any component is invalid, set wind speed to NaN
    invalid_mask = (~np.isfinite(u_new)) | (~np.isfinite(v_new)) | (~np.isfinite(w_new))
    wind_speed[invalid_mask] = np.nan
    
    interpolated_data['wind_speed'] = wind_speed
    
    # Create new time coordinate
    start_time = ds.valid_time.values[0]
    new_times = [start_time + np.timedelta64(int(h*3600), 's') for h in new_hours]
    
    # Build interpolated dataset
    new_ds = xr.Dataset(
        {var: (['valid_time', 'pressure_level', 'latitude', 'longitude'], 
               interpolated_data[var]) 
         for var in vars_to_interp + ['wind_speed']},
        coords={
            'valid_time': new_times,
            'pressure_level': ds.pressure_level,
            'latitude': ds.latitude,
            'longitude': ds.longitude
        }
    )
    
    # Copy attributes and save
    new_ds.attrs = ds.attrs
    new_ds.to_netcdf(output_file)
    
    print(f"Original: {ds.dims['valid_time']} timesteps")
    print(f"Interpolated: {new_ds.dims['valid_time']} timesteps")
    print(f"Expansion factor: {new_ds.dims['valid_time']/ds.dims['valid_time']:.1f}x")
    
    return new_ds

# Example usage
if __name__ == "__main__":
    result = pchip_interpolate_era5(
        input_file="era5_6hour.nc",
        output_file="era5_1hour_pchip.nc", 
        substeps=12  # 6-hour → 1-hour intervals
    )