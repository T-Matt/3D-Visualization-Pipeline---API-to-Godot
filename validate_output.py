import numpy as np
import xarray as xr
import matplotlib.pyplot as plt

def load_frame(filepath, n_channels, volume_shape):
    data = np.fromfile(filepath, dtype=np.float32)
    total_size = np.prod(volume_shape)
    
    channels = {}
    for i, var in enumerate(['wind_speed', 'u', 'v', 't']):
        start = i * total_size
        end = start + total_size
        channels[var] = data[start:end].reshape(volume_shape)
    
    return channels

def check_frame_integrity(frame_data, ranges):
    print("=== FRAME INTEGRITY CHECK ===")
    
    for var_name, volume in frame_data.items():
        # Count different types of values
        land_count = np.sum(np.abs(volume - (-999.0)) < 1.0)        # Land sentinels
        ocean_count = np.sum(np.abs(volume - (-500.0)) < 1.0)       # Ocean sentinels
        valid_count = np.sum((volume >= 0) & (volume <= 1))         # Valid normalized data
        other_count = np.sum(~((np.abs(volume - (-999.0)) < 1.0) | 
                              (np.abs(volume - (-500.0)) < 1.0) | 
                              ((volume >= 0) & (volume <= 1))))
        
        total_pixels = volume.size
        
        print(f"{var_name}: land={land_count}, ocean={ocean_count}, valid={valid_count}, other={other_count}, total={total_pixels}")
        
        # Check that all pixels are accounted for
        accounted = land_count + ocean_count + valid_count + other_count
        if accounted != total_pixels:
            print(f"WARNING: {var_name} has {total_pixels - accounted} unaccounted pixels")
            # Show some examples of "other" values
            other_mask = ~((np.abs(volume - (-999.0)) < 1.0) | 
                          (np.abs(volume - (-500.0)) < 1.0) | 
                          ((volume >= 0) & (volume <= 1)))
            if np.sum(other_mask) > 0:
                other_values = volume[other_mask]
                unique_others = np.unique(other_values)[:10]  # Show first 10 unique
                print(f"  Example 'other' values: {unique_others}")
        
        # Check data ranges
        vmin, vmax = ranges[var_name]['min'], ranges[var_name]['max']
        valid_data = volume[(volume >= 0) & (volume <= 1)]
        if len(valid_data) > 0:
            # Denormalize to check physical ranges
            denorm_data = vmin + valid_data * (vmax - vmin)
            print(f"  Physical range of valid data: [{denorm_data.min():.3f}, {denorm_data.max():.3f}]")
            print(f"  Expected range: [{vmin:.3f}, {vmax:.3f}]")

def validate_two_plots(frame_data, pressure_levels, var_name="wind_speed",
                       surface_pressure=1013.0, save_prefix="validate"):
    """
    Plot 1: Surface pressure slice (closest to surface_pressure) with sentinels highlighted.
    Plot 2: Neighboring pressure slice (next lower pressure, e.g., 1000 if surface is 1013) raw values.

    frame_data[var_name] has shape (p, lat, lon)
    pressure_levels is array-like length p (e.g., [400, 450, ..., 1013])
    """

    vol = frame_data[var_name]
    p = np.asarray(pressure_levels)

    # Find surface index by pressure value
    surface_idx = int(np.argmin(np.abs(p - surface_pressure)))
    surface_val = float(p[surface_idx])

    # Choose a "second plot" index: one level below surface in your ascending array
    # (surface is last index; second-from-last is usually 1000 mb)
    if surface_idx - 1 >= 0:
        second_idx = surface_idx - 1
    else:
        # Fallback if surface is at index 0 (not your case)
        second_idx = min(surface_idx + 1, vol.shape[0] - 1)

    second_val = float(p[second_idx])

    # ----------------------------
    # Plot 1: surface with sentinels highlighted
    # ----------------------------
    surface = vol[surface_idx, :, :].copy()
    display_surface = surface.copy()

    # Exact checks (best for pure Python validation)
    land_mask = (surface == -999.0)
    ocean_mask = (surface == -500.0)
    nan_mask = np.isnan(surface)

    # Remap for visibility
    display_surface[land_mask] = 2.0
    display_surface[ocean_mask] = 1.5
    # If any NaNs remain, show them too
    display_surface[nan_mask] = 1.25

    plt.figure(figsize=(10, 6))
    plt.imshow(display_surface, origin="lower", vmin=0, vmax=2)
    plt.title(f"{var_name} @ surface idx {surface_idx} (p≈{surface_val:g} mb) — sentinels highlighted")
    plt.xlabel("Longitude index")
    plt.ylabel("Latitude index")
    cbar = plt.colorbar()
    cbar.set_label("Value (land=2, ocean=1.5, NaN=1.25, data=0-1)")
    plt.tight_layout()
    plt.savefig(f"{save_prefix}_{var_name}_surface_p{surface_val:g}.png", dpi=150, bbox_inches="tight")
    plt.show()

    valid_mask = (surface >= 0) & (surface <= 1)
    print(f"[Surface p≈{surface_val:g}] land(-999): {np.sum(land_mask)}, ocean(-500): {np.sum(ocean_mask)}, "
          f"NaN: {np.sum(nan_mask)}, valid(0-1): {np.sum(valid_mask)}")

    # ----------------------------
    # Plot 2: neighboring pressure level raw values
    # ----------------------------
    p2 = vol[second_idx, :, :]

    plt.figure(figsize=(10, 6))
    plt.imshow(p2, origin="lower")
    plt.title(f"{var_name} @ idx {second_idx} (p≈{second_val:g} mb) — raw stored values")
    plt.xlabel("Longitude index")
    plt.ylabel("Latitude index")
    cbar = plt.colorbar()
    cbar.set_label("Raw stored values (mostly 0-1, with -500 where invalid)")
    plt.tight_layout()
    plt.savefig(f"{save_prefix}_{var_name}_p{second_val:g}_raw.png", dpi=150, bbox_inches="tight")
    plt.show()

    p2_land = np.sum(p2 == -999.0)
    p2_ocean = np.sum(p2 == -500.0)
    p2_nan = np.sum(np.isnan(p2))
    print(f"[p≈{second_val:g}] land: {p2_land}, ocean/invalid: {p2_ocean}, NaN: {p2_nan}, "
          f"min: {np.nanmin(p2):.6f}, max: {np.nanmax(p2):.6f}")
