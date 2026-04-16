import cv2
import numpy as np
from camera_mod import Camera
from avoidance import check_distance

def main():
    cam = Camera()

    try:
        while True:
            color_image, depth_image, depth_frame, ok = cam.get_frame()

            if not ok:
                continue

            # -------------------------------
            # Avoidance logic
            # -------------------------------
            results, status, direction = check_distance(depth_frame, depth_image)

            # -------------------------------
            # Depth visualization
            # -------------------------------
            depth_norm = cv2.normalize(depth_image, None, 0, 255, cv2.NORM_MINMAX)
            depth_norm = np.uint8(depth_norm)

            depth_colormap = cv2.applyColorMap(depth_norm, cv2.COLORMAP_JET)

            # -------------------------------
            # Overlay text on RGB
            # -------------------------------
            cv2.putText(color_image, "Status: {}".format(status), (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            cv2.putText(color_image, "Direction: {}".format(direction), (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # -------------------------------
            # Show BOTH windows
            # -------------------------------
            cv2.imshow("RGB View", color_image)
            cv2.imshow("Depth View", depth_colormap)

            print(status, direction)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break

    finally:
        cam.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()