import pyrealsense2 as rs
import numpy as np
import cv2
import time
from ultralytics import YOLO


class Detector:
    def __init__(self):
        self.model = YOLO("yolov8n.pt")

    def detect(self, image, depth_frame):
        results = self.model(image)
        detections = []

        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])

                # class 0 = person
                if cls == 0:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)

                    depth_values = []
                    for dx in range(-2, 3):
                        for dy in range(-2, 3):
                            px = cx + dx
                            py = cy + dy

                            if px < 0 or py < 0 or px >= image.shape[1] or py >= image.shape[0]:
                                continue

                            d = depth_frame.get_distance(px, py)
                            if d > 0:
                                depth_values.append(d)

                    distance = sum(depth_values) / len(depth_values) if depth_values else 0

                    detections.append({
                        "box": (x1, y1, x2, y2),
                        "center": (cx, cy),
                        "distance": distance
                    })

        return detections

    def draw(self, image, detections):
        for d in detections:
            x1, y1, x2, y2 = d["box"]
            cx, cy = d["center"]
            dist = d["distance"]

            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.circle(image, (cx, cy), 4, (0, 0, 255), -1)

            label = f"{dist:.2f} m" if dist > 0 else "N/A"
            cv2.putText(
                image,
                label,
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

        return image


pipeline = rs.pipeline()
config = rs.config()

config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)

print("Starting camera...")
pipeline.start(config)
time.sleep(2)

# Align depth to color
align = rs.align(rs.stream.color)

detector = Detector()

try:
    while True:
        frames = pipeline.wait_for_frames()

        aligned_frames = align.process(frames)
        color_frame = aligned_frames.get_color_frame()
        depth_frame = aligned_frames.get_depth_frame()

        if not color_frame or not depth_frame:
            continue

        color_image = np.asanyarray(color_frame.get_data())
        depth_image = np.asanyarray(depth_frame.get_data())

        detections = detector.detect(color_image, depth_frame)
        output_image = detector.draw(color_image.copy(), detections)

        depth_colormap = cv2.applyColorMap(
            cv2.convertScaleAbs(depth_image, alpha=0.03),
            cv2.COLORMAP_JET
        )

        cv2.imshow("YOLO Person Detection", output_image)
        cv2.imshow("Depth", depth_colormap)

        if cv2.waitKey(1) & 0xFF == 27:
            break

finally:
    pipeline.stop()
    cv2.destroyAllWindows()
