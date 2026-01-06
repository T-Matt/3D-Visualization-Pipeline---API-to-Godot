extends Node
class_name VolumeLoaderDebug

# Copy of your volume loader but with extensive debugging for sentinel values

var metadata: Dictionary
var volume_shape: Vector3i  # Original data shape (pressure, lat, lon)
var texture_shape: Vector3i  # Texture shape for rendering (lon, lat, pressure)
var n_channels: int
var bytes_per_channel: int
var variable_names: Array
var data_ranges: Dictionary  # Store min/max for each variable

var data_dir: String = "res://data/frames/"
var metadata_path: String = "res://data/metadata.json"

func _ready():
	print("DEBUG - VolumeLoaderDebug starting...")
	load_metadata()

func load_metadata():
	print("DEBUG - Loading metadata from: ", metadata_path)
	var file = FileAccess.open(metadata_path, FileAccess.READ)
	if file == null:
		print("ERROR: Could not open metadata file at: ", metadata_path)
		return
	
	var file_content = file.get_as_text()
	print("DEBUG - Metadata file size: ", file_content.length(), " characters")
	
	var json = JSON.new()
	var parse_result = json.parse(file_content)
	if parse_result != OK:
		print("ERROR: Failed to parse JSON metadata - ", json.parse_error)
		return
	
	metadata = json.data
	print("DEBUG - Metadata parsed successfully")
	print("Metadata loaded: ", metadata.keys())
	
	var dims = metadata["dimensions"]
	print("DEBUG - Dimensions: ", dims)
	
	# Original data order: (pressure_level, latitude, longitude)
	volume_shape = Vector3i(dims["pressure_level"], dims["latitude"], dims["longitude"])
	
	# Texture order for rendering: (longitude, latitude, pressure_level)
	# This matches how we set up the mesh
	texture_shape = Vector3i(dims["longitude"], dims["latitude"], dims["pressure_level"])
	
	n_channels = metadata["n_channels"]
	bytes_per_channel = metadata["bytes_per_channel"]
	variable_names = metadata["variables"]
	data_ranges = metadata["ranges"]
	
	print("DEBUG - Volume shape (p,lat,lon): ", volume_shape)
	print("DEBUG - Texture shape (lon,lat,p): ", texture_shape)
	print("DEBUG - Variables: ", variable_names)
	print("DEBUG - Channels: ", n_channels, ", bytes per channel: ", bytes_per_channel)
	print("DEBUG - Data ranges: ", data_ranges)

func load_frame_binary(frame_idx: int) -> PackedByteArray:
	var path = data_dir + "frame_%04d.bin" % frame_idx
	var file = FileAccess.open(path, FileAccess.READ)
	return file.get_buffer(file.get_length())

func parse_channels(binary_data: PackedByteArray) -> Dictionary:
	var result = {}
	var floats = binary_data.to_float32_array()
	var vals_per_channel = bytes_per_channel / 4
	
	for i in range(n_channels):
		var start = i * vals_per_channel
		var end = start + vals_per_channel
		var normalized_data = floats.slice(start, end)
		
		# Get the data range for denormalization
		var var_name = variable_names[i]
		var data_min = data_ranges[var_name]["min"]
		var data_max = data_ranges[var_name]["max"]
		
		var processed_data = PackedFloat32Array()
		processed_data.resize(normalized_data.size())
		
		var sentinel_count = 0
		var land_count = 0
		var ocean_count = 0
		
		for j in range(normalized_data.size()):
			var val = normalized_data[j]
			
			# Check for the MORE DRASTIC sentinel values
			if abs(val - (-999.0)) < 1.0:  # Land sentinel - more tolerance
				# Land sentinel - preserve as very negative value
				processed_data[j] = -999.0
				land_count += 1
				sentinel_count += 1
			elif abs(val - (-500.0)) < 1.0:  # Ocean sentinel - more tolerance
				# Ocean sentinel - preserve as very negative value
				processed_data[j] = -500.0
				ocean_count += 1
				sentinel_count += 1
			else:
				# Normal data - denormalize to physical range
				processed_data[j] = data_min + val * (data_max - data_min)
		
		print("DEBUG - Variable ", var_name, ":")
		print("  Land sentinels (-999): ", land_count)
		print("  Ocean sentinels (-500): ", ocean_count) 
		print("  Total extreme negatives: ", sentinel_count)
		
		result[var_name] = processed_data
	
	return result

# Rest of the functions remain the same...
func create_texture3d(float_array: PackedFloat32Array, var_name: String) -> ImageTexture3D:
	print("DEBUG - Creating 3D texture for variable: ", var_name)
	print("DEBUG - Input array size: ", float_array.size())
	
	# Get actual data range for this variable (for shader uniforms)
	var data_min = data_ranges[var_name]["min"]
	var data_max = data_ranges[var_name]["max"]
	print("DEBUG - Data range: [", data_min, ", ", data_max, "]")
	
	# Data comes in as (pressure, lat, lon) flattened
	# Need to reorder to (lon, lat, pressure) for texture
	
	var p = volume_shape.x  # pressure levels (12)
	var lat = volume_shape.y  # latitude (201)
	var lon = volume_shape.z  # longitude (201)
	
	var expected_size = p * lat * lon
	if float_array.size() != expected_size:
		print("ERROR: Array size mismatch - expected: ", expected_size, ", actual: ", float_array.size())
		return null
	
	print("DEBUG - Reordering data from (p,lat,lon) to (lon,lat,p)...")
	
	# Reorder data from (p, lat, lon) to (lon, lat, p)
	var reordered = PackedFloat32Array()
	reordered.resize(float_array.size())
	
	for iz in range(p):  # pressure (becomes Z in texture)
		for iy in range(lat):  # latitude (stays Y)
			for ix in range(lon):  # longitude (becomes X)
				var src_idx = iz * (lat * lon) + iy * lon + ix
				var dst_idx = ix * (lat * p) + iy * p + iz
				reordered[dst_idx] = float_array[src_idx]
	
	print("DEBUG - Data reordering complete")
	
	# Now create texture with reordered data in (lon, lat, p) format
	var images = []
	var slice_size = texture_shape.y * texture_shape.z  # lat * pressure
	
	print("DEBUG - Creating ", texture_shape.x, " image slices, ", slice_size, " pixels each")
	
	# Sample data quality during conversion INCLUDING SENTINEL VALUES
	var value_samples = []
	var negative_samples = []
	
	for x in range(texture_shape.x):  # For each longitude slice
		var slice_data = PackedByteArray()
		var start = x * slice_size
		
		# Convert floats to bytes for RF format (32-bit float per pixel)
		for i in range(slice_size):
			var val = reordered[start + i]
			
			# Sample some values for debugging
			if value_samples.size() < 10:
				value_samples.append(val)
			
			# Collect negative values specifically
			if val < 0.0 and negative_samples.size() < 20:
				negative_samples.append(val)
			
			# Pack float as 4 bytes (little-endian)
			var bytes = PackedByteArray()
			bytes.resize(4)
			bytes.encode_float(0, val)
			slice_data.append_array(bytes)
		
		# Create image: width=pressure, height=latitude, FORMAT_RF = 32-bit float
		var img = Image.create_from_data(texture_shape.z, texture_shape.y, false, Image.FORMAT_RF, slice_data)
		if img == null:
			print("ERROR: Failed to create image slice ", x)
			return null
		images.append(img)
	
	print("DEBUG - Sample actual values stored in texture: ", value_samples)
	print("DEBUG - Sample NEGATIVE values in texture: ", negative_samples)
	
	var tex3d = ImageTexture3D.new()
	# Create texture: width=pressure, height=latitude, depth=longitude
	print("DEBUG - Creating ImageTexture3D with dimensions: ", texture_shape.z, "x", texture_shape.y, "x", texture_shape.x)
	
	tex3d.create(Image.FORMAT_RF, texture_shape.z, texture_shape.y, texture_shape.x, false, images)
	
	print("DEBUG - 3D texture created successfully for ", var_name)
	return tex3d

func load_frame(frame_idx: int) -> Dictionary:
	print("DEBUG - Loading frame ", frame_idx)
	
	var binary = load_frame_binary(frame_idx)
	if binary.is_empty():
		print("ERROR: No binary data loaded for frame ", frame_idx)
		return {}
	
	var channels = parse_channels(binary)
	if channels.is_empty():
		print("ERROR: No channels parsed from binary data")
		return {}
	
	print("DEBUG - Creating textures for ", channels.size(), " variables...")
	var textures = {}
	for var_name in variable_names:
		if not channels.has(var_name):
			print("ERROR: Missing channel data for variable: ", var_name)
			continue
			
		var tex = create_texture3d(channels[var_name], var_name)
		if tex == null:
			print("ERROR: Failed to create texture for variable: ", var_name)
			continue
			
		textures[var_name] = tex
		print("DEBUG - Successfully created texture for: ", var_name)
	
	print("DEBUG - Frame loading complete. Created ", textures.size(), " textures")
	return textures
