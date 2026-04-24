# SAR Unified Framework

This package merges:
- Thermal night-vision human detection (FLIR Lepton + PureThermal via OpenCV)
- RealSense RGB human detection
- RealSense depth-based avoidance/status
- Maestro pan/tilt tracking driven by the thermal detector

## Runtime behavior
- One RealSense pipeline feeds both RGB and depth logic.
- One thermal camera feed runs the YOLO human detector.
- Thermal detections drive pan/tilt tracking.
- If no thermal target is detected, the gimbal can either hold or scan.
- Avoidance logic runs concurrently and is displayed in the HUD.

## Expected hardware
- FLIR Lepton 3.5 exposed as a UVC device through PureThermal Mini
- Intel RealSense color + depth device
- Pololu Maestro connected on the configured COM port

## Notes
- `thermal_model_path` should point to your `best.pt`.
- `thermal_camera_index` may need to be changed.
- `COM_PORT` in `maestro_config.py` must match your Windows device.
- This framework is display/testing oriented and does not directly command the drone flight stack yet.
- Tracking is intentionally based on the thermal model as requested.
