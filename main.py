import config
from extract_metadata import compute_global_ranges, extract_coordinate_info, create_metadata, save_metadata
from process_volumes import process_all_timesteps
from validate_output import load_frame, check_frame_integrity, validate_two_plots

# Extract and save metadata
ranges = compute_global_ranges(config.NC_FILE, config.VARIABLES)
coords = extract_coordinate_info(config.NC_FILE)
metadata = create_metadata(ranges, coords, config)

save_metadata(metadata, config.METADATA_FILE)

# Process all frames
process_all_timesteps(config.NC_FILE, config.VARIABLES, ranges, config.OUTPUT_DIR)

# Validate first frame
frame = load_frame(f"{config.OUTPUT_DIR}/frame_0000.bin", n_channels=4, volume_shape=config.VOLUME_DIMS)
check_frame_integrity(frame, ranges)
validate_two_plots(frame, pressure_levels=config.pressure_levels, var_name="wind_speed", surface_pressure=1013.0, save_prefix="validate")
