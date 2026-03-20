import cv2
from cam_module import Camera
from detection_module import Detector

def main():
    cam = Camera()
    detector = Detector()

    try:
        while True:
            # Get frames from camera
            color_frame, depth_image, depth_frame, ok = cam.get_frame()
            if not ok:
                continue

            # Detect humans
            detections = detector.detect(color_frame, depth_frame)
            output_frame = detector.draw(color_frame, detections)

            # Show RGB
            cv2.imshow("Human Detection", output_frame)

            # Show depth as color map
            depth_colormap = cv2.applyColorMap(
                cv2.convertScaleAbs(depth_image, alpha=0.03), cv2.COLORMAP_JET
            )
            cv2.imshow("Depth", depth_colormap)

            if cv2.waitKey(1) & 0xFF == 27:  # ESC to exit
                break

    finally:
        cam.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main() 