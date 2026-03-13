def turn_on_camera(camera_name):
    print(f"⚙️ [Turn On Camera]: { camera_name }")
    return { "camera_name": camera_name, "power": 1 }

def turn_off_camera(camera_name):
    print(f"⚙️ [Turn Off Camera]: { camera_name }")
    return { "camera_name": camera_name, "power": 0 }

def zoom_camera(target_camera, target_zoom_factor):
    print(f"⚙️ [Zoom In/Out]: { target_camera } to { target_zoom_factor }")
    return { "camera_name": target_camera, "zoom_factor": target_zoom_factor }