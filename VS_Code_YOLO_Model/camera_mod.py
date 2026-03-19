import cv2
from ultralytics import YOLO
import torch

print("Running THIS camera_mod.py")

class CameraHandler:
    def __init__(self, source=0):
        # Windows DirectShow backend for better performance on Windows
        self.cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        
        if not self.cap.isOpened():
            raise ValueError("Cannot open camera")
        
        print("Camera opened successfully")
        
        # Load the YOLO model
        self.model = YOLO('yolov8n.pt') # nano verion(fast)
        
        # Force CPU for stability ( can be changed to GPU if available and stable )
        self.model.to("cpu")
        print("Using CPU")
            
        # Frame counter for skipping frames
        self.frame_count = 0
        
    def get_frame(self):
        ret, frame = self.cap.read()
        
        if not ret:
            print("Frame grab failed")
            return None, []
        
        self.frame_count += 1
        persons = []
        
        # Run YOLO every 3 frames (prevent overload)
        if self.frame_count % 3 == 0:
            results = self.model(frame, imgsz=224, conf=0.5, verbose=False)
            
            for box in results[0].boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                
                if cls == 0: # Class 0 = person
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    
                    persons.append({
                        "bbox": (x1, y1, x2, y2),
                        "confidence": conf,
                        "center": ((x1 + x2) // 2, (y1 + y2) // 2)
                    })
                    
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    cv2.putText(frame, f"Person {conf:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255, 0), 2)
                    
        return frame, persons
    
    def close(self):
        self.cap.release()
        cv2.destroyAllWindows
        print("Camera and windows closed")
    