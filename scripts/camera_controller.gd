extends Camera3D
class_name VolumeCamera

var orbit_center: Vector3 = Vector3.ZERO
var orbit_distance: float = 20.0  # Increased from 5.0 for better initial view
var orbit_angles: Vector2 = Vector2(-PI/2, PI/2)  # (azimuth, elevation)
var roll_angle: float = PI # Z-axis rotation

var mouse_sensitivity: float = 0.005
var current_fov: float = 70.0  # Field of view for perspective
var zoom_sensitivity: float = 2.0  # FOV change per scroll
var min_fov: float = 5.0  # Zoom in limit (narrow FOV)
var max_fov: float = 100.0  # Zoom out limit (wide FOV)

var is_rotating_orbit: bool = false  # Left-click: orbit rotation
var is_rotating_roll: bool = false  # Right-click: Z-axis roll

func _ready():
	# Set to perspective projection
	projection = PROJECTION_PERSPECTIVE
	fov = current_fov
	
	# Set clipping planes
	near = 0.1
	far = 1000.0
	
	update_camera_transform()  

func _input(event: InputEvent):
	if event is InputEventMouseButton:
		# Left-click: screen-space camera movement (feels like dragging object)
		if event.button_index == MOUSE_BUTTON_LEFT:
			is_rotating_orbit = event.pressed
			is_rotating_roll = false
		
		# Right-click: roll around Z-axis (turntable)
		elif event.button_index == MOUSE_BUTTON_RIGHT:
			is_rotating_roll = event.pressed
			is_rotating_orbit = false
		
		# Scroll wheel zoom (changes field of view)
		elif event.button_index == MOUSE_BUTTON_WHEEL_UP:
			current_fov = max(min_fov, current_fov - zoom_sensitivity)
			fov = current_fov
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			current_fov = min(max_fov, current_fov + zoom_sensitivity)
			fov = current_fov
	
	elif event is InputEventMouseMotion:
		if is_rotating_orbit:
			# Left-click: move camera based on current viewing plane
			move_camera_in_view_plane(event.relative)
			
		elif is_rotating_roll:
			# Right-click: roll around Z-axis (turntable effect)
			roll_angle -= event.relative.x * mouse_sensitivity
			update_camera_transform()

func move_camera_in_view_plane(mouse_delta: Vector2):
	# Get camera's local coordinate system
	var camera_right = global_transform.basis.x
	var camera_up = global_transform.basis.y
	var camera_forward = -global_transform.basis.z
	
	# Scale movement based on distance and FOV for consistent feel
	var movement_scale = mouse_sensitivity * orbit_distance * 0.5
	
	# Calculate movement in camera's viewing plane
	# Move camera opposite to mouse movement (so object appears to follow mouse)
	var world_movement = camera_right * mouse_delta.x * movement_scale
	world_movement += camera_up * -mouse_delta.y * movement_scale
	
	# Project this movement onto a sphere around the orbit center
	# This keeps the camera at a consistent distance while moving in the view plane
	var current_offset = position - orbit_center
	var new_offset = current_offset + world_movement
	
	# Maintain the original distance from orbit center
	new_offset = new_offset.normalized() * orbit_distance
	
	# Convert back to orbital angles
	orbit_angles.x = atan2(new_offset.z, new_offset.x)
	orbit_angles.y = clamp(acos(new_offset.y / orbit_distance), 0.01, PI - 0.01)
	
	update_camera_transform()

func update_camera_transform():
	# Calculate orbital position (same as before)
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
