import cv2
from cam_module import Camera
from detection_module import Detector

def main():
    cam = Camera()
    detector = Detector()

    try:
        while True:
            color_frame, depth_image, depth_frame, ok = cam.get_frame()

            if not ok:
                continue

            detections = detector.detect(color_frame, depth_frame)
            output = detector.draw(color_frame, detections)

            # RGB view
            cv2.imshow("Human Detection", output)

            # Depth view (what you wanted)
            depth_colormap = cv2.applyColorMap(
                cv2.convertScaleAbs(depth_image, alpha=0.03),
                cv2.COLORMAP_JET
            )
            cv2.imshow("Depth View", depth_colormap)

            if cv2.waitKey(1) & 0xFF == 27:
                break

    finally:
        cam.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()