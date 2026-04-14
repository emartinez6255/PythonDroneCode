# maestro_config.py

COM_PORT = "COM3"   # <-- CHANGE THIS to your actual Maestro command port
BAUD_RATE = 9600

PAN_CHANNEL = 1
TILT_CHANNEL = 3

# Safe tested servo range in microseconds
PAN_MIN = 500
PAN_MAX = 2500
TILT_MIN = 500
TILT_MAX = 2500

# True electrical centers
PAN_CENTER = 1500.0
TILT_CENTER = 1500.0

# Your preferred resting / home positions
PAN_HOME = 1447.25

# IMPORTANT:
# You wrote 378.00 earlier, but that is outside the normal 500-2500 range.
# If 378.00 was a typo, replace it below with the correct tilt home.
# If it was intentional, this code will clamp it to TILT_MIN.
TILT_HOME = 500.0   # <-- replace with your real tilt home if different

# Motion tuning
DEFAULT_STEP_DELAY = 0.02
DEFAULT_MOVE_STEP_US = 8.0