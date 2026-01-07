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
        # Count different types of values using NEW encoding
        ocean_count = np.sum(np.abs(volume - 0.00) < 0.01)         # Ocean sentinels (0.00)
        land_count = np.sum(np.abs(volume - 0.05) < 0.01)          # Land sentinels (0.05)  
        valid_count = np.sum((volume >= 0.10) & (volume <= 1.0))   # Valid normalized data (0.10-1.0)
        gap_count = np.sum((volume > 0.05) & (volume < 0.10))      # Gap values (0.05-0.10)
        other_count = np.sum(~((np.abs(volume - 0.00) < 0.01) | 
                              (np.abs(volume - 0.05) < 0.01) | 
                              ((volume >= 0.10) & (volume <= 1.0)) |
                              ((volume > 0.05) & (volume < 0.10))))
        
        total_pixels = volume.size
        
        print(f"{var_name}: ocean={ocean_count}, land={land_count}, valid={valid_count}, gap={gap_count}, other={other_count}, total={total_pixels}")
        
        # Check that all pixels are accounted for
        accounted = ocean_count + land_count + valid_count + gap_count + other_count
        if accounted != total_pixels:
            print(f"WARNING: {var_name} has {total_pixels - accounted} unaccounted pixels")
            # Show some examples of "other" values
            other_mask = ~((np.abs(volume - 0.00) < 0.01) | 
                          (np.abs(volume - 0.05) < 0.01) | 
                          ((volume >= 0.10) & (volume <= 1.0)) |
                          ((volume > 0.05) & (volume < 0.10)))
            if np.sum(other_mask) > 0:
                other_values = volume[other_mask]
                unique_others = np.unique(other_values)[:10]  # Show first 10 unique
                print(f"  Example 'other' values: {unique_others}")
        
        # Check data ranges for valid data only
        vmin, vmax = ranges[var_name]['min'], ranges[var_name]['max']
        valid_data = volume[(volume >= 0.10) & (volume <= 1.0)]
        if len(valid_data) > 0:
            # Denormalize to check physical ranges (decode from 0.10-1.0 range)
            normalized_data = (valid_data - 0.10) / 0.90
            denorm_data = vmin + normalized_data * (vmax - vmin)
            print(f"  Physical range of valid data: [{denorm_data.min():.3f}, {denorm_data.max():.3f}]")
            print(f"  Expected range: [{vmin:.3f}, {vmax:.3f}]")

def validate_two_plots(frame_data, pressure_levels, var_name="wind_speed",
                       surface_pressure=1013.0, save_prefix="validate"):
    """
    Plot 1: Surface pressure slice with NEW sentinels highlighted.
    Plot 2: Neighboring pressure slice raw values.
    """

    vol = frame_data[var_name]
    p = np.asarray(pressure_levels)

    # Find surface index by pressure value
    surface_idx = int(np.argmin(np.abs(p - surface_pressure)))
    surface_val = float(p[surface_idx])

    # Choose a "second plot" index
    if surface_idx - 1 >= 0:
        second_idx = surface_idx - 1
    else:
        second_idx = min(surface_idx + 1, vol.shape[0] - 1)

    second_val = float(p[second_idx])

    # ----------------------------
    # Plot 1: surface with NEW sentinels highlighted
    # ----------------------------
    surface = vol[surface_idx, :, :].copy()
    display_surface = surface.copy()

    # NEW encoding checks
    ocean_mask = np.abs(surface - 0.00) < 0.01   # Ocean = 0.00
    land_mask = np.abs(surface - 0.05) < 0.01    # Land = 0.05
    valid_mask = (surface >= 0.10) & (surface <= 1.0)  # Data = 0.10-1.0

    # Remap for visibility
    display_surface[land_mask] = 2.0     # Land shows as 2.0
    display_surface[ocean_mask] = 1.5    # Ocean shows as 1.5

    plt.figure(figsize=(10, 6))
    plt.imshow(display_surface, origin="lower", vmin=0, vmax=2)
    plt.title(f"{var_name} @ surface idx {surface_idx} (p≈{surface_val:g} mb) — NEW sentinels highlighted")
    plt.xlabel("Longitude index")
    plt.ylabel("Latitude index")
    cbar = plt.colorbar()
    cbar.set_label("Value (land=2, ocean=1.5, data=0.1-1.0)")
    plt.tight_layout()
    plt.savefig(f"{save_prefix}_{var_name}_surface_p{surface_val:g}.png", dpi=150, bbox_inches="tight")
    plt.show()

    print(f"[Surface p≈{surface_val:g}] ocean(0.00): {np.sum(ocean_mask)}, land(0.05): {np.sum(land_mask)}, "
          f"valid(0.1-1.0): {np.sum(valid_mask)}")

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
    cbar.set_label("Raw stored values (0=ocean, 0.05=land, 0.1-1.0=data)")
    plt.tight_layout()
    plt.savefig(f"{save_prefix}_{var_name}_p{second_val:g}_raw.png", dpi=150, bbox_inches="tight")
    plt.show()

    p2_ocean = np.sum(np.abs(p2 - 0.00) < 0.01)
    p2_land = np.sum(np.abs(p2 - 0.05) < 0.01)
    print(f"[p≈{second_val:g}] ocean: {p2_ocean}, land: {p2_land}, "
          f"min: {np.nanmin(p2):.6f}, max: {np.nanmax(p2):.6f}")
