import cv2
from config import (
    THERMAL_CAMERA_INDEX,
    THERMAL_FRAME_WIDTH,
    THERMAL_FRAME_HEIGHT,
    THERMAL_FPS,
)


class ThermalCamera(object):
    def __init__(self, camera_index=THERMAL_CAMERA_INDEX):
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            raise RuntimeError(
                "Failed to open thermal camera index {0}".format(camera_index)
            )

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, THERMAL_FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, THERMAL_FRAME_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, THERMAL_FPS)

        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

    def get_frame(self):
        ok, frame = self.cap.read()
        if not ok:
            return None, False

        # Return the true raw thermal frame.
        # Do NOT rotate here. main_unified.py applies the single required
        # hanging-mount reference rotation before YOLO, tracking, and display.
        return frame, True

    def stop(self):
        if self.cap is not None:
            self.cap.release()
