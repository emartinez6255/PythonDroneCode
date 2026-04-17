import pyrealsense2 as rs
import numpy as np
import time

class Camera:
    def __init__(self):
        self.pipeline = rs.pipeline()
        config = rs.config()

        # Streams
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)

        print("Starting camera...")
        self.pipeline.start(config)

        # Warmup (important for stability in Python 3.6)
        print("Warming up camera...")
        for _ in range(10):
            self.pipeline.wait_for_frames()

        time.sleep(1)

    def get_frame(self):
        frames = self.pipeline.wait_for_frames()

        color_frame = frames.get_color_frame()
        depth_frame = frames.get_depth_frame()

        if not color_frame or not depth_frame:
            return None, None, None, False

        color_image = np.asanyarray(color_frame.get_data())
        depth_image = np.asanyarray(depth_frame.get_data())

        return color_image, depth_image, depth_frame, True

    def stop(self):
        self.pipeline.stop()
