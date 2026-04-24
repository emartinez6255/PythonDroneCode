import os
import cv2
from ultralytics import YOLO
from config import THERMAL_MODEL_PATH, THERMAL_IMGSZ, THERMAL_CONF


class ThermalHumanDetector(object):
    def __init__(self):
        self.model = YOLO(THERMAL_MODEL_PATH)
        self.conf = THERMAL_CONF
        self.imgsz = THERMAL_IMGSZ
        print("Thermal model loaded:", os.path.abspath(THERMAL_MODEL_PATH))

    def preprocess(self, frame):
        # Match your working yolo_live.py preprocessing
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        gray_3ch = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        return gray_3ch

    def detect(self, frame):
        prepared = self.preprocess(frame)
        results = self.model(prepared, imgsz=self.imgsz, verbose=False)

        detections = []
        for box in results[0].boxes:
            conf = float(box.conf[0])
            cls_id = int(box.cls[0]) if box.cls is not None else 0

            if conf < self.conf:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            area = float(max(0, x2 - x1) * max(0, y2 - y1))

            detections.append({
                "box": (x1, y1, x2, y2),
                "center": (cx, cy),
                "conf": conf,
                "cls": cls_id,
                "area": area
            })

        detections = sorted(
            detections,
            key=lambda d: (d.get("conf", 0.0), d.get("area", 0.0)),
            reverse=True
        )

        return prepared, detections