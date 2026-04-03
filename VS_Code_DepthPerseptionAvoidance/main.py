import cv2
from camera_mod import Camera
from avoidance import check_distance

def main():
    cam = Camera()

    try:
        while True:
            depth_frame, depth_image = cam.get_frame()

            if depth_frame is None:
                continue

            distance, status = check_distance(depth_frame, depth_image)

            if distance is not None:
                print(f"Distance: {distance:.2f} m | Status: {status}")
            else:
                print("No valid depth data")

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