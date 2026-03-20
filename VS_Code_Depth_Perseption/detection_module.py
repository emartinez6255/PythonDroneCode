import cv2
from ultralytics import YOLO

class Detector:
    def __init__(self):
        self.model = YOLO("yolov8n.pt")  # Path to your YOLO model

    def detect(self, image, depth_frame):
        results = self.model(image)
        detections = []

        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])
                if cls == 0:  # person class
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)

                    # Average depth in 5x5 region
                    depth_values = []
                    for dx in range(-2, 3):
                        for dy in range(-2, 3):
                            try:
                                d = depth_frame.get_distance(cx + dx, cy + dy)
                                if d > 0:
                                    depth_values.append(d)
                            except:
                                continue

                    distance = sum(depth_values)/len(depth_values) if depth_values else 0

                    detections.append({
                        "box": (x1, y1, x2, y2),
                        "center": (cx, cy),
                        "distance": distance
                    })

        return detections

    def draw(self, image, detections):
        for d in detections:
            x1, y1, x2, y2 = d["box"]
            dist = d["distance"]
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                image,
                f"{dist:.2f} m",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )
        return image