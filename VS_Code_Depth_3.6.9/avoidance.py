import numpy as np

print("✅ USING CORRECT avoidance.py")

# ---------- Helper ----------
def analyze_region(x_start, x_end, y_start, y_end, depth_frame):
    distances = []

    for x in range(x_start, x_end):
        for y in range(y_start, y_end):
            d = depth_frame.get_distance(x, y)

            # Ignore invalid + extreme values
            if 0 < d < 10:
                distances.append(d)

    if len(distances) == 0:
        return 0, 0, 0

    distances = np.array(distances)

    median_dist = np.median(distances)
    min_dist = np.min(distances)
    free_ratio = np.sum(distances > 1.0) / float(len(distances))

    return median_dist, min_dist, free_ratio


# ---------- Main ----------
def check_distance(depth_frame, depth_image):

    # Safer conversion for RealSense
    depth_array = np.asanyarray(depth_image)

    if not isinstance(depth_array, np.ndarray):
        print("ERROR: depth_image is not a numpy array")
        return {}, "ERROR", "UNKNOWN"

    # Ensure 2D
    if len(depth_array.shape) > 2:
        depth_array = depth_array[:, :, 0]

    if len(depth_array.shape) != 2:
        print("ERROR: depth_array is not 2D, shape:", depth_array.shape)
        return {}, "ERROR", "UNKNOWN"

    # Dimensions
    height, width = depth_array.shape

    print("DEBUG width:", width, "height:", height)

    # Focus region (middle band)
    y_start = int(height * 0.3)
    y_end   = int(height * 0.7)

    # Zones
    left   = (0, int(width * 0.33))
    center = (int(width * 0.33), int(width * 0.66))
    right  = (int(width * 0.66), width)

    # Analyze zones
    left_data   = analyze_region(left[0], left[1], y_start, y_end, depth_frame)
    center_data = analyze_region(center[0], center[1], y_start, y_end, depth_frame)
    right_data  = analyze_region(right[0], right[1], y_start, y_end, depth_frame)

    left_median, left_min, left_free = left_data
    center_median, center_min, center_free = center_data
    right_median, right_min, right_free = right_data

    # Thresholds
    SAFE_DIST = 1.2
    DANGER_DIST = 0.6

    status = "CLEAR"
    direction = "FORWARD"

    if center_min < DANGER_DIST:
        status = "DANGER"
        direction = "LEFT" if left_median > right_median else "RIGHT"

    elif center_median < SAFE_DIST:
        status = "WARNING"
        direction = "LEFT" if left_free > right_free else "RIGHT"

    else:
        status = "CLEAR"
        direction = "FORWARD"

    results = {
        "left": left_data,
        "center": center_data,
        "right": right_data
    }

    return results, status, direction
