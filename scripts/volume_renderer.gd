extends MeshInstance3D
class_name VolumeRenderer

var volume_material: ShaderMaterial
var current_textures: Dictionary
var active_variable: String = "wind_speed"
var data_ranges: Dictionary  # Store data ranges for shader uniforms

func _ready():
	setup_volume_mesh(Vector3(12, 201, 201))
	volume_material = create_volume_material()
	# Verify shader loaded
	if volume_material == null:
		print("ERROR: Failed to create volume material!")
		return
		
	if volume_material.shader == null:
		print("ERROR: Shader failed to load!")
		return
	print("DEBUG - Shader path: ", volume_material.shader.resource_path)
	
	# Apply material
	material_override = volume_material
	
	# Force update
	set_surface_override_material(0, volume_material)
	

func setup_volume_mesh(dimensions: Vector3):
	print("DEBUG - Setting up volume mesh with dimensions: ", dimensions)
	
	var box = BoxMesh.new()
	
	# Rearrange dimensions: (pressure_level, lat, lon) -> (lon, lat, pressure_level)
	# X = longitude (201), Y = latitude (201), Z = pressure (12)
	var vertical_dims = Vector3(dimensions.y, dimensions.z, dimensions.x)
	print("DEBUG - Rearranged dimensions (lon,lat,pressure): ", vertical_dims)
	
	# Scale proportionally - keep the aspect ratio!
	# Make the largest horizontal dimension = 20 units
	var horizontal_scale = 20.0 / max(vertical_dims.x, vertical_dims.y)
	print("DEBUG - Horizontal scale factor: ", horizontal_scale)
	
	# Don't normalize Z - keep it proportional to show it's much thinner
	box.size = vertical_dims * horizontal_scale
	print("DEBUG - Final mesh size: ", box.size)
	
	mesh = box
	
	# Verify mesh was created
	if mesh == null:
		print("ERROR: Failed to create mesh!")
	else:
		print("DEBUG - Mesh created successfully")

func create_volume_material() -> ShaderMaterial:
	print("DEBUG - Creating volume material...")
	# Load shader
	var shader = load("res://shaders/raymarch_volume.gdshader")
	if shader == null:
		print("ERROR: Failed to load shader from res://shaders/raymarch_volume.gdshader")
		print("DEBUG - Check if shader file exists at that path")
		return null
	
	
	var mat = ShaderMaterial.new()
	mat.shader = shader
	
	# Set default parameters
	mat.set_shader_parameter("step_size", 0.001)
	mat.set_shader_parameter("density_multiplier", 0.5)
	mat.set_shader_parameter("active_variable", 0)
	
	print("DEBUG - ShaderMaterial created successfully")
	return mat

func update_frame(textures_dict: Dictionary):
	
	if volume_material == null:
		print("ERROR: Volume material is null!")
		return
	
	if textures_dict == null or textures_dict.is_empty():
		print("ERROR: No textures provided!")
		return
	
	current_textures = textures_dict
	
	print("DEBUG - Received textures: ", textures_dict.keys())
	
	# Check each texture before setting
	var required_textures = ["wind_speed", "u", "v", "t"]
	for tex_name in required_textures:
		if not textures_dict.has(tex_name):
			print("ERROR: Missing required texture: ", tex_name)
			return
		
		var tex = textures_dict[tex_name]
		if tex == null:
			print("ERROR: Texture is null for: ", tex_name)
			return
		
		print("DEBUG - Texture ", tex_name, " - Size: ", tex.get_width(), "x", tex.get_height(), "x", tex.get_depth())
		print("DEBUG - Texture ", tex_name, " - Format: ", tex.get_format())
	
	# Set textures to material
	print("DEBUG - Setting textures to shader parameters...")
	volume_material.set_shader_parameter("wind_speed_texture", textures_dict["wind_speed"])
	volume_material.set_shader_parameter("u_texture", textures_dict["u"])
	volume_material.set_shader_parameter("v_texture", textures_dict["v"])
	volume_material.set_shader_parameter("t_texture", textures_dict["t"])

	# nearest bindings (same textures)
	volume_material.set_shader_parameter("wind_speed_texture_nn", textures_dict["wind_speed"])
	volume_material.set_shader_parameter("u_texture_nn", textures_dict["u"])
	volume_material.set_shader_parameter("v_texture_nn", textures_dict["v"])
	volume_material.set_shader_parameter("t_texture_nn", textures_dict["t"])
	
	print("DEBUG - All textures set to material successfully")
	
func set_data_ranges(ranges: Dictionary):
	"""Set the data ranges for proper colormap normalization in the shader"""
	data_ranges = ranges
	
	if volume_material == null:
		print("ERROR: Volume material is null!")
		return
	
	print("DEBUG - Setting shader range uniforms:")
	
	# Set range uniforms for each variable
	if ranges.has("wind_speed"):
		var r = ranges["wind_speed"]
		var range_vec = Vector2(r["min"], r["max"])
		volume_material.set_shader_parameter("wind_speed_range", range_vec)
		print("  wind_speed_range: ", range_vec)
	
	if ranges.has("u"):
		var r = ranges["u"]
		var range_vec = Vector2(r["min"], r["max"])
		volume_material.set_shader_parameter("u_range", range_vec)
		print("  u_range: ", range_vec)
	
	if ranges.has("v"):
		var r = ranges["v"]
		var range_vec = Vector2(r["min"], r["max"])
		volume_material.set_shader_parameter("v_range", range_vec)
		print("  v_range: ", range_vec)
	
	if ranges.has("t"):
		var r = ranges["t"]
		var range_vec = Vector2(r["min"], r["max"])
		volume_material.set_shader_parameter("t_range", range_vec)
		print("  t_range: ", range_vec)
	
	print("DEBUG - Data ranges set in shader")


func set_active_variable(var_name: String):
	print("DEBUG - Setting active variable to: ", var_name)
	
	if volume_material == null:
		print("ERROR: Volume material is null!")
		return
	
	active_variable = var_name
	var var_idx = ["wind_speed", "u", "v", "t"].find(var_name)
	
	if var_idx == -1:
		print("ERROR: Unknown variable name: ", var_name)
		return
	
	print("DEBUG - Variable index: ", var_idx)
	volume_material.set_shader_parameter("active_variable", var_idx)
	
	# Verify parameter was set
	print("DEBUG - Active variable parameter set to: ", volume_material.get_shader_parameter("active_variable"))
