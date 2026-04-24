class PersistentBoxTracker(object):
    def __init__(self, max_missed=6, smoothing=0.5):
        self.max_missed = max_missed
        self.smoothing = smoothing
        self.last_detection = None
        self.missed = 0

    def _smooth_box(self, old_box, new_box):
        x1 = int(old_box[0] * (1.0 - self.smoothing) + new_box[0] * self.smoothing)
        y1 = int(old_box[1] * (1.0 - self.smoothing) + new_box[1] * self.smoothing)
        x2 = int(old_box[2] * (1.0 - self.smoothing) + new_box[2] * self.smoothing)
        y2 = int(old_box[3] * (1.0 - self.smoothing) + new_box[3] * self.smoothing)
        return (x1, y1, x2, y2)

    def _smooth_center(self, old_center, new_center):
        cx = int(old_center[0] * (1.0 - self.smoothing) + new_center[0] * self.smoothing)
        cy = int(old_center[1] * (1.0 - self.smoothing) + new_center[1] * self.smoothing)
        return (cx, cy)

    def _smooth_value(self, old_val, new_val):
        return old_val * (1.0 - self.smoothing) + new_val * self.smoothing

    def _box_area(self, box):
        x1, y1, x2, y2 = box
        w = max(0, x2 - x1)
        h = max(0, y2 - y1)
        return float(w * h)

    def update(self, detections):
        if detections and len(detections) > 0:
            best = detections[0]

            if self.last_detection is None:
                box = best["box"]
                self.last_detection = {
                    "box": box,
                    "center": best["center"],
                    "distance": best.get("distance", 0.0),
                    "conf": best.get("conf", 0.0),
                    "area": best.get("area", self._box_area(box)),
                }
            else:
                new_box = self._smooth_box(
                    self.last_detection["box"],
                    best["box"]
                )
                new_center = self._smooth_center(
                    self.last_detection["center"],
                    best["center"]
                )
                new_distance = self._smooth_value(
                    self.last_detection.get("distance", 0.0),
                    best.get("distance", 0.0)
                )
                new_conf = self._smooth_value(
                    self.last_detection.get("conf", 0.0),
                    best.get("conf", 0.0)
                )
                new_area = self._smooth_value(
                    self.last_detection.get("area", self._box_area(self.last_detection["box"])),
                    best.get("area", self._box_area(best["box"]))
                )

                self.last_detection["box"] = new_box
                self.last_detection["center"] = new_center
                self.last_detection["distance"] = new_distance
                self.last_detection["conf"] = new_conf
                self.last_detection["area"] = new_area

            self.missed = 0
        else:
            self.missed += 1
            if self.missed > self.max_missed:
                self.last_detection = None

        if self.last_detection is None:
            return []

        return [self.last_detection]