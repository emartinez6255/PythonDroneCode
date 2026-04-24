R.A.V.E.N. SAR Mission Control - Python 3.6.9 transfer

This package keeps the same logic, architecture, and GUI design as the current Python 3.12 version.
Main Python 3.6 compatibility change:
- Removed Python 3.10-only type-union syntax from maestro_controller.py.

Run:
    python raven_mission_control.py

Optional EXE build:
    BUILD_EXE_PY36.bat

Important dependency note:
- The source code is Python 3.6-compatible syntax.
- Some packages may still need Python 3.6-compatible versions/wheels on the QDrone/Jetson environment.
- Current ultralytics releases require Python >=3.8, so the thermal_detector.py / detection_module.py YOLO loading may require a compatible older YOLO backend or a Python 3.8+ environment.
