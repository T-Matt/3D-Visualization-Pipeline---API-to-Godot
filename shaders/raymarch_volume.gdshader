shader_type spatial;
render_mode unshaded, cull_back, blend_mix;

uniform sampler3D wind_speed_texture : filter_linear;
uniform sampler3D u_texture : filter_linear;
uniform sampler3D v_texture : filter_linear;
uniform sampler3D t_texture : filter_linear;


// Data ranges for each variable (for colormap normalization)
uniform vec2 wind_speed_range = vec2(0.0, 70.0);
uniform vec2 u_range = vec2(-54.0, 60.0);
uniform vec2 v_range = vec2(-54.0, 55.0);
uniform vec2 t_range = vec2(-10.0, 317.0);

uniform int active_variable : hint_range(0, 3) = 0;
uniform float step_size : hint_range(0.001, 0.1) = 0.002;
uniform float density_multiplier : hint_range(0.0, 10.0) = 0.1;

uniform int debug_mode : hint_range(0, 6) = 6;

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

float sample_volume(vec3 uvw) {
	vec3 tex_uvw = uvw.zyx; // Apply coordinate swizzle
	tex_uvw.x = 1.0 - tex_uvw.x;
	float val;
	if (active_variable == 0) {
		val = texture(wind_speed_texture, tex_uvw).r;
	} else if (active_variable == 1) {
		val = texture(u_texture, tex_uvw).r;
	} else if (active_variable == 2) {
		val = texture(v_texture, tex_uvw).r;
	} else {
		val = texture(t_texture, tex_uvw).r;
	}
	
	return val;
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

vec4 apply_simple_transfer_function(float value) {
    // Sentinel / invalid handling
    // With linear filtering, values near sentinel layers can become negative but not exactly -999/-500.
    // Since valid normalized data should be in [0,1], ANY negative value is not valid data.
    if (value < 0.0) {
        // Land: treat "close to -999" as land (use a wider tolerance for linear filtering)
        if (abs(value + 999.0) < 2.0) {
            return vec4(0.0, 0.0, 0.0, 1.0); // land: opaque black
        }
        // Ocean/invalid (including -500 and any interpolated negative junk)
        return vec4(0.0, 0.0, 0.0, 0.0);
    }

    // Normal data processing
    vec2 range = get_active_range();
    float normalized = (value - range.x) / (range.y - range.x);
    normalized = clamp(normalized, 0.0, 1.0);

    // Colormap
    vec3 color;
    if (normalized < 0.15) {
        color = mix(vec3(0.0, 0.0, 0.5), vec3(0.0, 0.0, 1.0), normalized / 0.15);
    } else if (normalized < 0.35) {
        color = mix(vec3(0.0, 0.0, 1.0), vec3(0.0, 1.0, 1.0), (normalized - 0.15) / 0.2);
    } else if (normalized < 0.55) {
        color = mix(vec3(0.0, 1.0, 1.0), vec3(0.0, 1.0, 0.0), (normalized - 0.35) / 0.2);
    } else if (normalized < 0.70) {
        color = mix(vec3(0.0, 1.0, 0.0), vec3(1.0, 1.0, 0.0), (normalized - 0.55) / 0.15);
    } else if (normalized < 0.85) {
        color = mix(vec3(1.0, 1.0, 0.0), vec3(1.0, 0.5, 0.0), (normalized - 0.70) / 0.15);
    } else {
        color = mix(vec3(1.0, 0.5, 0.0), vec3(1.0, 0.0, 0.0), (normalized - 0.85) / 0.15);
    }

    // Volumetric opacity: gentle at low values, ramps up
    // These constants are good starting points for "atmospheric" feel.
    float alpha = pow(normalized, 3) * density_multiplier;
    alpha = clamp(alpha, 0.0, 1.0);

    return vec4(color, alpha);
}

void fragment() {
    // Mode 6: Full volume rendering (AABB-correct)
    vec3 cam_pos   = (INV_VIEW_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
    vec3 world_pos = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
    vec3 ray_dir   = normalize(world_pos - cam_pos);

    // Local AABB from your debug print:
    vec3 local_min = vec3(-10.0, -10.0, -0.597015);
    vec3 local_max = vec3( 10.0,  10.0,  0.597015);

    // Intersect in WORLD space using the same bounds (converted from local)
    vec3 box_min = (MODEL_MATRIX * vec4(local_min, 1.0)).xyz;
    vec3 box_max = (MODEL_MATRIX * vec4(local_max, 1.0)).xyz;

    vec2 hit = ray_box_intersection(cam_pos, ray_dir, box_min, box_max);
    if (hit.x < 0.0) {
        discard;
    }

    vec4 color_accum = vec4(0.0);
    float dist = hit.x;

    int max_steps = int((hit.y - hit.x) / step_size) + 1;
    int step_count = 0;

    while (dist < hit.y && color_accum.a < 0.99 && step_count < max_steps) {
        vec3 pos_world = cam_pos + ray_dir * dist;
        vec3 pos_local = (inverse(MODEL_MATRIX) * vec4(pos_world, 1.0)).xyz;

        // Correct local -> [0,1] mapping
        vec3 tex_coord = (pos_local - local_min) / (local_max - local_min);

        if (all(greaterThanEqual(tex_coord, vec3(0.0))) &&
            all(lessThanEqual(tex_coord, vec3(1.0)))) {

            float sample_val = sample_volume(tex_coord);

            // DEBUG: show land as RED (so we know when we're hitting -999)
            if (abs(sample_val + 999.0) < 0.5) {
                color_accum = vec4(1.0, 0.0, 0.0, 1.0);
                break;
            }

            vec4 sample_color = apply_simple_transfer_function(sample_val);

            // Front-to-back compositing
            color_accum.rgb += sample_color.rgb * sample_color.a * (1.0 - color_accum.a);
            color_accum.a   += sample_color.a   * (1.0 - color_accum.a);
        }

        dist += step_size;
        step_count++;
    }

    ALBEDO = color_accum.rgb;
    ALPHA  = color_accum.a;
}

