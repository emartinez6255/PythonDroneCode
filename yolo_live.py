import cv2
from ultralytics import YOLO

# Load your trained model
model = YOLO(r"C:\Users\Jerry\Thermal_Project\runs\detect\train3\weights\best.pt")

# Open FLIR camera
cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("Camera failed")
    exit()

cv2.namedWindow("Thermal Detection", cv2.WINDOW_NORMAL)

while True:
    ret, frame = cap.read()
    if not ret:
        print("Frame failed")
        break

    # Convert to grayscale and normalize
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

    # Convert back to 3-channel for YOLO
    gray_3ch = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    # Run detection
    results = model(gray_3ch, imgsz=160, verbose=False)

    # Copy frame for drawing
    annotated = gray_3ch.copy()

    for box in results[0].boxes:
        conf = float(box.conf[0])

        # Filter weak detections
        if conf < 0.5:
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0])

        # Draw VERY thin box
        cv2.rectangle(
            annotated,
            (x1, y1),
            (x2, y2),
            (255, 0, 0),
            1   # thickness
        )

        # SUPER tiny text (confidence only)
        cv2.putText(
            annotated,
            f"{conf:.2f}",
            (x1, max(y1 - 3, 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.25,            # VERY small text
            (255, 0, 0),
            1,
            cv2.LINE_AA
        )

    # Resize for display
    display = cv2.resize(
        annotated,
        (640, 480),
        interpolation=cv2.INTER_NEAREST
    )

    cv2.imshow("Thermal Detection", display)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()