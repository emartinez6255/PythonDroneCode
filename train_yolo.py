from ultralytics import YOLO

model = YOLO("yolov8n.pt")

model.train(
    data=r"C:\Users\Jerry\Thermal_Project\custom_dataset_yolo_v2\data.yaml",  # ← updated
    epochs=50,
    imgsz=160,
    batch=8,
    device="cpu"
)