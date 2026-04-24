import os

# -------------------------------------------------
# MODEL SELECTION
# -------------------------------------------------
USE_THERMAL_YOLO = True
USE_RGB_YOLO = True

# Thermal model: YOUR trained thermal model
THERMAL_MODEL_PATH = os.environ.get(
    "THERMAL_MODEL_PATH",
    r".\weights\best.pt")

# RGB model selection
RGB_MODEL_TYPE = os.environ.get("RGB_MODEL_TYPE", "yolov8")
RGB_MODEL_PATH = os.environ.get(
    "RGB_MODEL_PATH",
    r"./weights/yolov8n.pt"
)

# -------------------------------------------------
# CAMERA SETTINGS
# -------------------------------------------------
THERMAL_CAMERA_INDEX = int(os.environ.get("THERMAL_CAMERA_INDEX", "0"))
THERMAL_IMGSZ = int(os.environ.get("THERMAL_IMGSZ", "160"))
THERMAL_CONF = float(os.environ.get("THERMAL_CONF", "0.50"))

SHOW_WINDOWS = True
ENABLE_MAESTRO = True
ENABLE_SCAN_WHEN_LOST = True

DISPLAY_WIDTH = 320
DISPLAY_HEIGHT = 240

# -------------------------------------------------
# TRACKING SETTINGS
# -------------------------------------------------
TRACKING_CLASS_ID = 0
TRACK_DEADBAND_X_PX = 8
TRACK_DEADBAND_Y_PX = 8
PAN_GAIN_US_PER_PX = 1.5
TILT_GAIN_US_PER_PX = 1.5
TRACK_SMOOTHING = 0.35
SEARCH_STEP_US = 10.0
SEARCH_DELAY_S = 0.03
SEARCH_TILT_US = None

# -------------------------------------------------
# DRAW SETTINGS
# -------------------------------------------------
DRAW_CONFIDENCE = True
DRAW_RGB_HOG = True
DRAW_DEPTH = False
DRAW_THERMAL = True

# -------------------------------------------------
# PERFORMANCE SETTINGS
# -------------------------------------------------
THERMAL_DETECT_EVERY_N_FRAMES = 1
RGB_DETECT_EVERY_N_FRAMES = 2
DEPTH_UPDATE_EVERY_N_FRAMES = 20
PRINT_STATUS_EVERY_N_FRAMES = 15

# -------------------------------------------------
# THERMAL CAMERA CAPTURE
# -------------------------------------------------
THERMAL_FRAME_WIDTH = 160
THERMAL_FRAME_HEIGHT = 120
THERMAL_FPS = 9

# -------------------------------------------------
# REALSENSE CAPTURE
# -------------------------------------------------
RS_COLOR_WIDTH = 424
RS_COLOR_HEIGHT = 240
RS_DEPTH_WIDTH = 424
RS_DEPTH_HEIGHT = 240
RS_FPS = 15