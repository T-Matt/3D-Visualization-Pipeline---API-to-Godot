import xarray as xr
import json
import config

def compute_global_ranges(nc_file, variables):
    ds = xr.open_dataset(nc_file)
    return {var: {'min': float(ds[var].min().compute()), 
                  'max': float(ds[var].max().compute())} 
            for var in variables}

def extract_coordinate_info(nc_file):
    ds = xr.open_dataset(nc_file)
    return {coord: ds[coord].values for coord in ['latitude', 'longitude', 'pressure_level']}

def create_metadata(ranges, coords, cfg):
    return {
        'variables': cfg.VARIABLES,
        'ranges': ranges,
        'coordinates': {k: v.tolist() for k, v in coords.items()},
        'dimensions': dict(zip(['pressure_level', 'latitude', 'longitude'], cfg.VOLUME_DIMS)),
        'n_timesteps': cfg.N_TIMESTEPS,
        'n_channels': cfg.N_CHANNELS,
        'dtype': cfg.DTYPE,
        'bytes_per_channel': cfg.BYTES_PER_CHANNEL,
        'bytes_per_frame': cfg.BYTES_PER_FRAME,
        'sentinel_values': {
            'land': -999.0,
            'ocean': -500.0,
            'valid_range': [0.0, 1.0]
        }
    }

def save_metadata(metadata, filepath):
    with open(filepath, 'w') as f:
        json.dump(metadata, f, indent=2)