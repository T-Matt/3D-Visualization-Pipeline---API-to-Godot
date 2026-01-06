extends Node3D

@onready var loader = $VolumeLoader
@onready var renderer = $VolumeRenderer
@onready var frame_slider = $UI/FrameSlider
@onready var var_selector = $UI/VariableSelector
@onready var play_button = $UI/PlayButton

var current_frame: int = 0
var is_playing: bool = false
var playback_speed: float = 24.0  # frames per second

func _ready():
	print("DEBUG - Main controller starting...")
	
	# Check if nodes exist
	print("DEBUG - Loader found: ", loader != null)
	print("DEBUG - Renderer found: ", renderer != null)
	print("DEBUG - UI elements found - Slider: ", frame_slider != null, 
		  ", Selector: ", var_selector != null, ", Button: ", play_button != null)
	
	# Wait a frame to ensure loader is ready
	await get_tree().process_frame
	
	# Check if loader has loaded metadata
	if loader == null:
		print("ERROR - VolumeLoader not found!")
		return
	
	if not loader.metadata.has("n_timesteps"):
		print("ERROR - Loader metadata not ready!")
		print("DEBUG - Loader metadata: ", loader.metadata)
		return
	
	print("DEBUG - Loader metadata loaded: ", loader.metadata.keys())
	print("DEBUG - Number of timesteps: ", loader.metadata["n_timesteps"])
	print("DEBUG - Variable names: ", loader.variable_names)
	
	# Setup UI
	if frame_slider:
		frame_slider.max_value = loader.metadata["n_timesteps"] - 1
		frame_slider.value = 0
		frame_slider.value_changed.connect(_on_frame_changed)
		print("DEBUG - Frame slider setup: range 0 to ", frame_slider.max_value)
	
	if var_selector:
		var_selector.clear()
		for var_name in loader.variable_names:
			var_selector.add_item(var_name)
		var_selector.item_selected.connect(_on_variable_changed)
		print("DEBUG - Variable selector setup with ", var_selector.get_item_count(), " items")
	
	if play_button:
		play_button.pressed.connect(_on_play_pressed)
		print("DEBUG - Play button connected")
	
	# Set data ranges in renderer
	if renderer and loader.data_ranges:
		print("DEBUG - Setting data ranges from metadata:")
		print("  wind_speed: ", loader.data_ranges["wind_speed"])
		print("  u: ", loader.data_ranges["u"])
		print("  v: ", loader.data_ranges["v"])
		print("  t: ", loader.data_ranges["t"])
		renderer.set_data_ranges(loader.data_ranges)
		print("DEBUG - Data ranges set in renderer")
	
	# Load initial frame
	print("DEBUG - Loading initial frame...")
	load_and_display_frame(0)
	print("DEBUG - Main controller initialization complete")

func _process(delta):
	if is_playing:
		current_frame += playback_speed * delta
		if current_frame >= loader.metadata["n_timesteps"]:
			current_frame = 0
		
		var frame_idx = int(current_frame)
		frame_slider.value = frame_idx
		load_and_display_frame(frame_idx)

func load_and_display_frame(frame_idx: int):
	print("DEBUG - Loading frame ", frame_idx)
	
	if loader == null:
		print("ERROR - Loader is null!")
		return
		
	var textures = loader.load_frame(frame_idx)
	
	if textures == null or textures.is_empty():
		print("ERROR - No textures loaded for frame ", frame_idx)
		return
	
	print("DEBUG - Loaded textures: ", textures.keys())
	for var_name in textures.keys():
		var tex = textures[var_name]
		if tex:
			print("DEBUG - Texture ", var_name, " size: ", tex.get_width(), "x", tex.get_height(), "x", tex.get_depth())
		else:
			print("ERROR - Texture ", var_name, " is null!")
	
	if renderer == null:
		print("ERROR - Renderer is null!")
		return
		
	print("DEBUG - Updating renderer with textures...")
	renderer.update_frame(textures)

func _on_frame_changed(value: float):
	if not is_playing:
		print("DEBUG - Frame slider changed to: ", value)
		load_and_display_frame(int(value))

func _on_variable_changed(index: int):
	var var_name = loader.variable_names[index]
	print("DEBUG - Variable changed to: ", var_name, " (index ", index, ")")
	renderer.set_active_variable(var_name)

func _on_play_pressed():
	is_playing = !is_playing
	play_button.text = "Pause" if is_playing else "Play"
	print("DEBUG - Playback ", "started" if is_playing else "stopped")
