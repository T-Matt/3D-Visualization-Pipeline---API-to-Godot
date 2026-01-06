import numpy as np
import xarray as xr
import os
from tqdm import tqdm

def load_single_timestep(nc_file, variables, time_idx):
    ds = xr.open_dataset(nc_file)
    volumes = {var: ds[var].isel(valid_time=time_idx).values for var in variables}
    pressure_levels = ds["pressure_level"].values
    return volumes, pressure_levels

def create_universal_mask(volumes_dict):
    """Create a consistent land/ocean mask that applies to all variables"""
    
    # Combine masks from all variables to create a universal mask
    land_mask = np.zeros_like(list(volumes_dict.values())[0], dtype=bool)
    ocean_mask = np.zeros_like(list(volumes_dict.values())[0], dtype=bool)
    
    for var_name, volume in volumes_dict.items():
        # Accumulate land areas (negative values) from any variable
        land_mask |= (volume < 0)
        # Accumulate ocean areas (NaN values) from any variable
        ocean_mask |= np.isnan(volume)
    
    print(f"Universal mask statistics:")
    print(f"  Land points: {np.sum(land_mask)}")
    print(f"  Ocean points: {np.sum(ocean_mask)}")
    print(f"  Valid points: {np.sum(~land_mask & ~ocean_mask)}")
    print(f"  Total points: {land_mask.size}")
    
    return land_mask, ocean_mask

def normalize_volumes(volumes_dict, ranges, pressure_levels, surface_pressure=1013.0):
    # Find surface index robustly
    surface_idx = int(np.argmin(np.abs(pressure_levels - surface_pressure)))

    sample_var = next(iter(volumes_dict.values()))
    surface_shape = sample_var[surface_idx, :, :].shape

    surface_land_mask = np.zeros(surface_shape, dtype=bool)
    surface_ocean_mask = np.zeros(surface_shape, dtype=bool)

    for _, volume in volumes_dict.items():
        surf = volume[surface_idx, :, :]
        # If land is encoded as -10 exactly:
        surface_land_mask |= np.isclose(surf, -10.0)
        surface_ocean_mask |= np.isnan(surf)

    print(f"Surface pressure ~{surface_pressure} hPa at index {surface_idx} (value={pressure_levels[surface_idx]})")
    print(f"  Land points at surface: {np.sum(surface_land_mask)}")
    print(f"  Ocean points at surface: {np.sum(surface_ocean_mask)}")

    normalized = {}
    for var, volume in volumes_dict.items():
        vmin, vmax = ranges[var]["min"], ranges[var]["max"]

        if vmax != vmin:
            normalized_vol = (volume - vmin) / (vmax - vmin)
        else:
            normalized_vol = np.zeros_like(volume, dtype=np.float32)

        # Convert NaNs everywhere to invalid/ocean sentinel
        normalized_vol = np.nan_to_num(normalized_vol, nan=-500.0)

        # Apply surface sentinels at the correct surface_idx
        normalized_vol[surface_idx, surface_ocean_mask] = -500.0
        normalized_vol[surface_idx, surface_land_mask] = -999.0

        normalized[var] = normalized_vol.astype(np.float32)

    return normalized


def stack_channels(volumes_dict, variable_order):
    return np.concatenate([volumes_dict[var].flatten() for var in variable_order])

def export_frame(stacked_data, frame_idx, output_dir, dtype='float32'):
    filepath = os.path.join(output_dir, f"frame_{frame_idx:04d}.bin")
    stacked_data.astype(dtype).tofile(filepath)

def process_all_timesteps(nc_file, variables, ranges, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    # Get number of timesteps once from the dataset
    ds = xr.open_dataset(nc_file)
    n_timesteps = ds.dims["valid_time"]
    ds.close()

    for t in tqdm(range(n_timesteps), desc="Processing frames"):
        volumes, pressure_levels = load_single_timestep(nc_file, variables, t)
        normalized = normalize_volumes(volumes, ranges, pressure_levels, surface_pressure=1013.0)
        stacked = stack_channels(normalized, variables)
        export_frame(stacked, t, output_dir)
