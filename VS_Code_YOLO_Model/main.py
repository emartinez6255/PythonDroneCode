from camera_mod import CameraHandler
import cv2

# --------------------------------------------------------------------
# Placeholder Drone Controller (Laptop Testing)
# --------------------------------------------------------------------
class DroneController:
    def __init__(self):
        print("Drone Controller Initialized (simulation mode)")
    def set_velocity(self, vx, vy, vz, yaw):
        print(f"VX: {vx:.2f}, VY: {vy:.2f}, VZ: {vz:.2f}, YAW: {yaw:.2f}")
    def stop(self):
        self.set_velocity(0, 0, 0, 0)
        print("Drone stopped")
# --------------------------------------------------------------------
# Initialize camera and drone controller
# --------------------------------------------------------------------
camera = CameraHandler()
drone = DroneController()

TARGET_SIZE = 120
DEADZONE = 40

try:
    while True:
        frame, persons = camera.get_frame()
        if frame is None:
            continue
        h, w, _ = frame.shape
        
        # ------------------------------------------------------------
        # Draw Camera Center and Target Zone Crosshairs
        # ------------------------------------------------------------
        cv2.line(frame, (w//2 -20, h//2), (w//2 + 20, h//2), (255, 0, 0), 2)
        cv2.line(frame, (w//2, h//2 - 20), (w//2, h//2 + 20), (255, 0, 0), 2)
        
        if len(persons) > 0:
            # -------------------------------------------------------------
            # Selecte Closes Person (Largest Box)
            # -------------------------------------------------------------
            target = max(persons, key=lambda p: (p["bbox"][2]-p["bbox"][0]) * (p["bbox"][3]-p["bbox"][1]))
            
            cx, cy = target["center"]
            x1, y1, x2, y2 = target["bbox"]
            
            error_x = cx - (w//2)
            error_y = cy - (h//2)
            
            box_width = x2 - x1
            
            vx = 0
            vy = 0
            vz = 0
            yaw = 0
            
            # -------------------------------------------------------------
            # Horizontal Centering (Yaw Control)
            # -------------------------------------------------------------
            if abs(error_x) > DEADZONE:
                yaw = -0.0002 * error_x
            # -------------------------------------------------------------
            # Vertical Centering (VZ Control) (Altitude)
            # -------------------------------------------------------------
            if abs(error_y) > DEADZONE:
                vz = -0.0002 * error_y
            # -------------------------------------------------------------
            # Forward/Backward Control (VX) based on Box Size (Distance)
            # -------------------------------------------------------------
            size_error = TARGET_SIZE - box_width
            vx = 0.003 * size_error
            
            drone.set_velocity(vx, vy, vz, yaw)
            # -------------------------------------------------------------
            # Debug Overlays
            # -------------------------------------------------------------
            
            #Person Center
            cv2.circle(frame, (cx, cy), 6, (0, 255, 255), -1)
            
            # Error Vector
            cv2.line(frame, (w//2, h//2), (cx, cy), (0, 255, 255), 2)
            
            # Error Text
            cv2.putText(frame, f"ErrorX:{error_x} ErrorY:{error_y}", (20,30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            # Distance Info
            cv2.putText(frame, f"BoxWidth:{box_width}", (20,60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Display Window
        cv2.imshow("Drone Camera", frame)
        
        if cv2.waitKey(1) & 0xFF == 27: # ESC key to exit
            break
        
except KeyboardInterrupt:
    print("Interrupted by user")
   
    
finally:
    
    drone.stop()
    camera.close()
    cv2.destroyAllWindows()   