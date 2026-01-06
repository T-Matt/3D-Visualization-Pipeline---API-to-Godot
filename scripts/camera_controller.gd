extends Camera3D
class_name VolumeCamera

var orbit_center: Vector3 = Vector3.ZERO
var orbit_distance: float = 20.0  # Increased from 5.0 for better initial view
var orbit_angles: Vector2 = Vector2(PI/2, PI/3)  # (azimuth, elevation)
var roll_angle: float = 0.0  # Z-axis rotation

var mouse_sensitivity: float = 0.005
var ortho_size: float = 15.0  # Increased from 10.0 for zoomed-out start
var zoom_sensitivity: float = 0.5
var min_ortho_size: float = 0.5  # Zoom in limit
var max_ortho_size: float = 50.0  # Zoom out limit

var is_rotating_orbit: bool = false  # Left-click: orbit rotation
var is_rotating_roll: bool = false  # Right-click: Z-axis roll

func _ready():
	# Switch to orthographic projection
	projection = PROJECTION_ORTHOGONAL
	size = ortho_size
	
	# Set far plane - near plane doesn't matter in ortho
	far = 1000.0
	
	update_camera_transform()
	print("Camera initialized at: ", position, " looking at: ", orbit_center)
	print("Ortho size: ", ortho_size)
	
	# DEBUG: Check if camera is current and basic setup
	print("DEBUG - Camera current: ", current)
	print("DEBUG - Camera projection: ", projection)
	print("DEBUG - Camera transform: ", transform)
	
	# DEBUG: Check what's in the scene
	var parent = get_parent()
	if parent:
		print("DEBUG - Scene children:")
		for child in parent.get_children():
			print("  ", child.name, " (", child.get_class(), ") visible: ", child.get("visible"))

func _input(event: InputEvent):
	if event is InputEventMouseButton:
		# Left-click: orbit rotation (spherical)
		if event.button_index == MOUSE_BUTTON_LEFT:
			is_rotating_orbit = event.pressed
			is_rotating_roll = false
		
		# Right-click: roll around Z-axis (turntable)
		elif event.button_index == MOUSE_BUTTON_RIGHT:
			is_rotating_roll = event.pressed
			is_rotating_orbit = false
		
		# Scroll wheel zoom (changes orthographic size, not distance)
		elif event.button_index == MOUSE_BUTTON_WHEEL_UP:
			ortho_size = max(min_ortho_size, ortho_size - zoom_sensitivity)
			size = ortho_size
			print("DEBUG - Zoomed in to size: ", ortho_size)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			ortho_size = min(max_ortho_size, ortho_size + zoom_sensitivity)
			size = ortho_size
			print("DEBUG - Zoomed out to size: ", ortho_size)
	
	elif event is InputEventMouseMotion:
		if is_rotating_orbit:
			# Left-click: standard orbit rotation
			orbit_angles.x -= event.relative.x * mouse_sensitivity
			orbit_angles.y = clamp(orbit_angles.y - event.relative.y * mouse_sensitivity, 0.01, PI - 0.01)
			update_camera_transform()
		
		elif is_rotating_roll:
			# Right-click: roll around Z-axis (turntable effect)
			roll_angle -= event.relative.x * mouse_sensitivity
			update_camera_transform()

func update_camera_transform():
	# Calculate orbital position
	var x = orbit_distance * sin(orbit_angles.y) * cos(orbit_angles.x)
	var y = orbit_distance * cos(orbit_angles.y)
	var z = orbit_distance * sin(orbit_angles.y) * sin(orbit_angles.x)
	
	var new_position = orbit_center + Vector3(x, y, z)
	
	# DEBUG: Only print when position actually changes significantly
	if position.distance_to(new_position) > 0.1:
		print("DEBUG - Camera moving from ", position, " to ", new_position)
		print("DEBUG - Distance to center: ", new_position.distance_to(orbit_center))
	
	position = new_position
	
	# Choose up vector that won't cause gimbal lock
	var up_vector = Vector3.UP
	# When looking nearly straight down or up, use forward direction as up
	if abs(orbit_angles.y) < 0.1 or abs(orbit_angles.y - PI) < 0.1:
		up_vector = Vector3.FORWARD
	
	look_at(orbit_center, up_vector)
	
	# Apply Z-axis roll
	rotate_object_local(Vector3(0, 0, 1), roll_angle - rotation.z)
