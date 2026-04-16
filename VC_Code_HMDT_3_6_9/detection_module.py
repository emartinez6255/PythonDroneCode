import cv2

class Detector:
    def __init__(self):
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect(self, image, depth_frame):
        detections = []

        rects, _ = self.hog.detectMultiScale(
            image,
            winStride=(8, 8),
            padding=(16, 16),
            scale=1.05
        )

        for (x, y, w, h) in rects:
            x1, y1 = x, y
            x2, y2 = x + w, y + h
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
                "{0:.2f} m".format(dist),
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )
        return image