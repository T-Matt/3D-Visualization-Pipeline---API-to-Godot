shader_type spatial;
render_mode unshaded, cull_back, blend_mix;

uniform sampler3D wind_speed_texture : filter_linear;
uniform sampler3D u_texture : filter_linear;
uniform sampler3D v_texture : filter_linear;
uniform sampler3D t_texture : filter_linear;

// NEW: nearest versions (same textures, different sampling)
uniform sampler3D wind_speed_texture_nn : filter_nearest;
uniform sampler3D u_texture_nn : filter_nearest;
uniform sampler3D v_texture_nn : filter_nearest;
uniform sampler3D t_texture_nn : filter_nearest;




// Data ranges for each variable (for colormap normalization)
uniform vec2 wind_speed_range = vec2(0.0, 70.0);
uniform vec2 u_range = vec2(-54.0, 60.0);
uniform vec2 v_range = vec2(-54.0, 55.0);
uniform vec2 t_range = vec2(-10.0, 317.0);

uniform int active_variable : hint_range(0, 3) = 0;
uniform float step_size : hint_range(0.001, 0.1) = 0.002;
uniform float density_multiplier : hint_range(0.0, 10.0) = 0.5;


vec3 get_atmospheric_colormap(float normalized) {
    // Ensure input is in [0,1] range
    normalized = clamp(normalized, 0.0, 1.0);
    
    // Define the color palette as RGB values
    if (normalized < 0.02) {
        // aliceblue to lightcyan
        return mix(vec3(0.941, 0.973, 1.0), vec3(0.878, 1.0, 1.0), normalized / 0.02);
    } else if (normalized < 0.04) {
        // lightcyan to paleturquoise
        return mix(vec3(0.878, 1.0, 1.0), vec3(0.686, 0.933, 0.933), (normalized - 0.02) / 0.02);
    } else if (normalized < 0.08) {
        // paleturquoise to skyblue
        return mix(vec3(0.686, 0.933, 0.933), vec3(0.529, 0.808, 0.922), (normalized - 0.04) / 0.04);
    } else if (normalized < 0.12) {
        // skyblue to deepskyblue
        return mix(vec3(0.529, 0.808, 0.922), vec3(0.0, 0.749, 1.0), (normalized - 0.08) / 0.04);
    } else if (normalized < 0.16) {
        // deepskyblue to dodgerblue
        return mix(vec3(0.0, 0.749, 1.0), vec3(0.118, 0.565, 1.0), (normalized - 0.12) / 0.04);
    } else if (normalized < 0.20) {
        // dodgerblue to mediumturquoise
        return mix(vec3(0.118, 0.565, 1.0), vec3(0.282, 0.820, 0.800), (normalized - 0.16) / 0.04);
    } else if (normalized < 0.24) {
        // mediumturquoise to mediumaquamarine
        return mix(vec3(0.282, 0.820, 0.800), vec3(0.400, 0.804, 0.667), (normalized - 0.20) / 0.04);
    } else if (normalized < 0.28) {
        // mediumaquamarine to lightgreen
        return mix(vec3(0.400, 0.804, 0.667), vec3(0.565, 0.933, 0.565), (normalized - 0.24) / 0.04);
    } else if (normalized < 0.32) {
        // lightgreen to limegreen
        return mix(vec3(0.565, 0.933, 0.565), vec3(0.196, 0.804, 0.196), (normalized - 0.28) / 0.04);
    } else if (normalized < 0.36) {
        // limegreen to greenyellow
        return mix(vec3(0.196, 0.804, 0.196), vec3(0.678, 1.0, 0.184), (normalized - 0.32) / 0.04);
    } else if (normalized < 0.40) {
        // greenyellow to yellow
        return mix(vec3(0.678, 1.0, 0.184), vec3(1.0, 1.0, 0.0), (normalized - 0.36) / 0.04);
    } else if (normalized < 0.44) {
        // yellow to gold
        return mix(vec3(1.0, 1.0, 0.0), vec3(1.0, 0.843, 0.0), (normalized - 0.40) / 0.04);
    } else if (normalized < 0.48) {
        // gold to orange
        return mix(vec3(1.0, 0.843, 0.0), vec3(1.0, 0.647, 0.0), (normalized - 0.44) / 0.04);
    } else if (normalized < 0.52) {
        // orange to darkorange
        return mix(vec3(1.0, 0.647, 0.0), vec3(1.0, 0.549, 0.0), (normalized - 0.48) / 0.04);
    } else if (normalized < 0.60) {
        // darkorange to orangered (extended range)
        return mix(vec3(1.0, 0.549, 0.0), vec3(1.0, 0.271, 0.0), (normalized - 0.52) / 0.08);
    } else if (normalized < 0.68) {
        // orangered to red
        return mix(vec3(1.0, 0.271, 0.0), vec3(1.0, 0.0, 0.0), (normalized - 0.60) / 0.08);
    } else if (normalized < 0.76) {
        // red to crimson
        return mix(vec3(1.0, 0.0, 0.0), vec3(0.863, 0.078, 0.235), (normalized - 0.68) / 0.08);
    } else if (normalized < 0.84) {
        // crimson to darkred
        return mix(vec3(0.863, 0.078, 0.235), vec3(0.545, 0.0, 0.0), (normalized - 0.76) / 0.08);
    } else if (normalized < 0.92) {
        // darkred to maroon
        return mix(vec3(0.545, 0.0, 0.0), vec3(0.502, 0.0, 0.0), (normalized - 0.84) / 0.08);
    } else {
        // maroon to black for extreme values
        return mix(vec3(0.502, 0.0, 0.0), vec3(0.0, 0.0, 0.0), (normalized - 0.92) / 0.08);
    }
}

vec2 ray_box_intersection(vec3 ray_origin, vec3 ray_dir, vec3 box_min, vec3 box_max) {
	vec3 inv_dir = 1.0 / (ray_dir + 0.0001);
	vec3 t_min = (box_min - ray_origin) * inv_dir;
	vec3 t_max = (box_max - ray_origin) * inv_dir;
	
	vec3 t1 = min(t_min, t_max);
	vec3 t2 = max(t_min, t_max);
	
	float t_near = max(max(t1.x, t1.y), t1.z);
	float t_far = min(min(t2.x, t2.y), t2.z);
	
	if (t_near > t_far || t_far < 0.0) {
		return vec2(-1.0);
	}
	
	return vec2(max(t_near, 0.0), t_far);
}

float sample_volume_linear(vec3 uvw) {
    vec3 tex_uvw = uvw.zyx; // (lon,lat,p) -> (p,lat,lon)
    if (active_variable == 0) return texture(wind_speed_texture, tex_uvw).r;
    if (active_variable == 1) return texture(u_texture, tex_uvw).r;
    if (active_variable == 2) return texture(v_texture, tex_uvw).r;
    return texture(t_texture, tex_uvw).r;
}

float sample_volume_nearest(vec3 uvw) {
    vec3 tex_uvw = uvw.zyx;
    if (active_variable == 0) return texture(wind_speed_texture_nn, tex_uvw).r;
    if (active_variable == 1) return texture(u_texture_nn, tex_uvw).r;
    if (active_variable == 2) return texture(v_texture_nn, tex_uvw).r;
    return texture(t_texture_nn, tex_uvw).r;
}


// Get the data range for the currently active variable
vec2 get_active_range() {
	if (active_variable == 0) {
		return wind_speed_range;
	} else if (active_variable == 1) {
		return u_range;
	} else if (active_variable == 2) {
		return v_range;
	} else {
		return t_range;
	}
}


// vec4 apply_simple_transfer_function(float value) {

     
// 	// Clean sentinel detection
//     if (value < 0.02) {
//         return vec4(0.0, 0.0, 0.0, 0.0);  // Ocean (transparent)
//     }
//     if (value < 0.08) {
//         return vec4(0.2, 0.2, 0.2, 1.0);  // Land (gray, full opacity)
//     }

//     // Normal data processing (0.10-1.0 range)
//     float normalized = (value - 0.08) / 0.92;
//     normalized = clamp(normalized, 0.0, 1.0);

//     // Enhanced colormap with more variation
//     vec3 color;
//     if (normalized < 0.1) {
//         // Very low: dark blue to blue
//         color = mix(vec3(0.0, 0.0, 0.3), vec3(0.0, 0.0, 0.8), normalized / 0.1);
//     } else if (normalized < 0.25) {
//         // Low: blue to cyan
//         color = mix(vec3(0.0, 0.0, 0.8), vec3(0.0, 0.7, 1.0), (normalized - 0.1) / 0.15);
//     } else if (normalized < 0.4) {
//         // Low-medium: cyan to green
//         color = mix(vec3(0.0, 0.7, 1.0), vec3(0.0, 1.0, 0.3), (normalized - 0.25) / 0.15);
//     } else if (normalized < 0.55) {
//         // Medium: green to yellow-green
//         color = mix(vec3(0.0, 1.0, 0.3), vec3(0.5, 1.0, 0.0), (normalized - 0.4) / 0.15);
//     } else if (normalized < 0.7) {
//         // Medium-high: yellow-green to yellow
//         color = mix(vec3(0.5, 1.0, 0.0), vec3(1.0, 1.0, 0.0), (normalized - 0.55) / 0.15);
//     } else if (normalized < 0.85) {
//         // High: yellow to orange
//         color = mix(vec3(1.0, 1.0, 0.0), vec3(1.0, 0.6, 0.0), (normalized - 0.7) / 0.15);
//     } else {
//         // Very high: orange to red
//         color = mix(vec3(1.0, 0.6, 0.0), vec3(1.0, 0.0, 0.0), (normalized - 0.85) / 0.15);
//     }

//     // Volumetric opacity: gentle at low values, ramps up
//     // These constants are good starting points for "atmospheric" feel.
//     float alpha = pow(normalized, 3) * density_multiplier;
//     alpha = clamp(alpha, 0.0, 1.0);

//     return vec4(color, alpha);
// }

vec4 apply_simple_transfer_function(float value) {
    // Handle sentinels
    if (value < 0.02) {
        return vec4(0.0, 0.0, 0.0, 0.0);  // Ocean (transparent)
    }
    if (value <= 0.05) {
        return vec4(0.2, 0.2, 0.2, 1.0);  // Land (gray, full opacity)
    }

    // Decode from 0.10-1.0 range back to 0.0-1.0
    float decoded = (value - 0.05) / 0.95;
    decoded = clamp(decoded, 0.0, 1.0);
    
    // Apply square root for enhanced sensitivity WITHIN the atmospheric range
    float enhanced = sqrt(decoded);
    
    // Get color from the atmospheric colormap
    vec3 color = get_atmospheric_colormap(decoded);

    // Enhanced atmospheric visibility while keeping land distinct
    float alpha = enhanced * 0.005 * density_multiplier;
    alpha = clamp(alpha, 0.0, 1.0);

    return vec4(color, alpha);
}

uniform bool flip_pressure = false; // toggle in Godot if needed

void fragment() {
    vec3 cam_pos   = (INV_VIEW_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
    vec3 world_pos = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
    vec3 ray_dir   = normalize(world_pos - cam_pos);

    vec3 local_min = vec3(-10.0, -10.0, -0.597015);
    vec3 local_max = vec3( 10.0,  10.0,  0.597015);

    vec3 box_min = (MODEL_MATRIX * vec4(local_min, 1.0)).xyz;
    vec3 box_max = (MODEL_MATRIX * vec4(local_max, 1.0)).xyz;

    vec2 hit = ray_box_intersection(cam_pos, ray_dir, box_min, box_max);
    if (hit.x < 0.0) discard;

    vec4 color_accum = vec4(0.0);
    float dist = hit.x;

    int max_steps = int((hit.y - hit.x) / step_size) + 1;
    int step_count = 0;

    while (dist < hit.y && color_accum.a < 0.99 && step_count < max_steps) {
        vec3 pos_world = cam_pos + ray_dir * dist;
        vec3 pos_local = (inverse(MODEL_MATRIX) * vec4(pos_world, 1.0)).xyz;

        vec3 tex_coord = (pos_local - local_min) / (local_max - local_min);

        if (flip_pressure) {
            tex_coord.z = 1.0 - tex_coord.z;
        }

        // REQUIRED: don’t sample outside [0,1]
        if (any(lessThan(tex_coord, vec3(0.0))) || any(greaterThan(tex_coord, vec3(1.0)))) {
            dist += step_size;
            step_count++;
            continue;
        }

        // Land detection: NEAREST sampler (so the 1-slice mask is hittable)
        // float v_nn = sample_volume_nearest(tex_coord); 
		// if (v_nn >= 0.02 && v_nn < 0.08) {  // Land range
		// 	vec4 land_color = vec4(0.2, 0.2, 0.2, 1.0);
		// 	color_accum.rgb += land_color.rgb * (1.0 - color_accum.a);
		// 	color_accum.a = 1.0;
		// 	break;
		// }

        // Atmosphere: smooth sampling
		float v = sample_volume_linear(tex_coord);
		vec4 sample_color = apply_simple_transfer_function(v);

        color_accum.rgb += sample_color.rgb * sample_color.a * (1.0 - color_accum.a);
        color_accum.a   += sample_color.a * (1.0 - color_accum.a);

        dist += step_size;
        step_count++;
    }

    ALBEDO = color_accum.rgb;
    ALPHA  = color_accum.a;
}
