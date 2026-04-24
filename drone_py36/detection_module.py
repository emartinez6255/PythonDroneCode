import cv2
from ultralytics import YOLO
from config import RGB_MODEL_PATH, RGB_MODEL_TYPE


class RGBHumanDetector(object):
    def __init__(self):
        self.model = YOLO(RGB_MODEL_PATH)
        self.model_type = RGB_MODEL_TYPE.lower()
        print("RGB model loaded:", RGB_MODEL_PATH, "| type:", self.model_type)

    def detect(self, image, depth_frame):
        detections = []

        results = self.model(image, imgsz=320, verbose=False)

        for box in results[0].boxes:
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])

            # person class only
            if cls_id != 0:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)

            depth_values = []
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    px = cx + dx
                    py = cy + dy
                    if px < 0 or py < 0:
                        continue
                    try:
                        d = depth_frame.get_distance(px, py)
                        if d > 0:
                            depth_values.append(d)
                    except Exception:
                        continue

            distance = 0.0
            if len(depth_values) > 0:
                distance = float(sum(depth_values)) / len(depth_values)

            area = float(max(0, x2 - x1) * max(0, y2 - y1))

            detections.append({
                "box": (x1, y1, x2, y2),
                "center": (cx, cy),
                "distance": distance,
                "conf": conf,
                "cls": cls_id,
                "area": area
            })

        detections = sorted(
            detections,
            key=lambda d: (d.get("conf", 0.0), d.get("area", 0.0)),
            reverse=True
        )

        return detections

    def draw(self, image, detections):
        for d in detections:
            x1, y1, x2, y2 = d["box"]
            dist = d.get("distance", 0.0)
            conf = d.get("conf", 0.0)

            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)

            label = "P {0:.2f} | {1:.2f} m".format(conf, dist)
            cv2.putText(
                image,
                label,
                (x1, max(20, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
            )
        return image