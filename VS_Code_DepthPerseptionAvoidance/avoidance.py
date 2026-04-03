import numpy as np

SAFE_DISTANCE = 1.0  # meters

def check_distance(depth_frame, depth_image):
    h, w = depth_image.shape
    cx, cy = w // 2, h // 2

    # 40x40 region around center
    region = depth_image[cy-20:cy+20, cx-20:cx+20]

    # Filter out invalid pixels (0 values)
    valid_pixels = region[region > 0]

    if len(valid_pixels) == 0:
        return None, "NO DATA"

    # Convert to meters
    avg_distance = np.mean(valid_pixels) * depth_frame.get_units()

    if avg_distance < SAFE_DISTANCE:
        return avg_distance, "TOO CLOSE"
    else:
        return avg_distance, "SAFE"