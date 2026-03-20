import pyrealsense2 as rs
import numpy as np
import time

class Camera:
    def __init__(self):
        print("Camera initializing...")
        self.pipeline = rs.pipeline()
        config = rs.config()

        # RGB + Depth streams
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)

        # Start streaming
        self.pipeline.start(config)
        time.sleep(2)  # Warm-up
        print("Camera started.")

    def get_frame(self):
        frames = self.pipeline.wait_for_frames()
        color_frame = frames.get_color_frame()
        depth_frame = frames.get_depth_frame()

        if not color_frame or not depth_frame:
            return None, None, None, False  # Return 4 values

        # Convert color frame to numpy array
        color_image = np.asanyarray(color_frame.get_data())
        # Convert depth frame to numpy array for display
        depth_image = np.asanyarray(depth_frame.get_data())

        return color_image, depth_image, depth_frame, True  # 4 values

    def stop(self):
        self.pipeline.stop()
        print("Camera stopped.")