import os
import xarray as xr

# Paths
NC_FILE = "C:\\Users\\Matt\\Downloads\\CDS_To_Visual_Latest\\hurricane_katrina_era5_1hour_pchip.nc"
OUTPUT_DIR = "C:\\Users\\Matt\\Downloads\\NC_to_BINARY_GODOT\\bins"
METADATA_FILE = os.path.join(OUTPUT_DIR, "metadata.json")

# Variables

# Dataset variables: ['t', 'u', 'v', 'wind_speed']
# Dataset dimensions: {'valid_time': 211, 'pressure_level': 12, 'latitude': 201, 'longitude': 201}


VARIABLES = ['wind_speed', 'u', 'v', 't']

# Dimensions
ds = xr.open_dataset(NC_FILE)
pressure_levels = ds["pressure_level"].values
ds.close()

VOLUME_DIMS = (12, 201, 201)
N_TIMESTEPS = 211
DTYPE = 'float32'

# Derived
N_CHANNELS = len(VARIABLES)
BYTES_PER_CHANNEL = VOLUME_DIMS[0] * VOLUME_DIMS[1] * VOLUME_DIMS[2] * 4  # float32 = 4 bytes
BYTES_PER_FRAME = BYTES_PER_CHANNEL * N_CHANNELS