import cv2
import os

# Build an absolute path to: Thermal_Project/custom_dataset/images
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
save_dir = os.path.join(base_dir, "custom_dataset", "images")
os.makedirs(save_dir, exist_ok=True)

print("Saving to:", save_dir)

cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("Failed to open FLIR Lepton")
    exit()

count = 0
cv2.namedWindow("Lepton Capture", cv2.WINDOW_NORMAL)

while True:
    ret, frame = cap.read()
    if not ret:
        print("Frame failed")
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    display = cv2.resize(gray, (640, 480), interpolation=cv2.INTER_CUBIC)

    cv2.imshow("Lepton Capture", display)
    key = cv2.waitKey(1) & 0xFF

    if key == ord("s"):
        filename = os.path.join(save_dir, f"img_{count:04d}.png")
        cv2.imwrite(filename, gray)
        print("Saved to:", filename)
        count += 1

    elif key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()