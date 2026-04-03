import pyrealsense2 as rs
import numpy as np

class Camera:
    def __init__(self):
        pass
        self.pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        self.pipeline.start(config)

    def get_frame(self):
        frames = self.pipeline.wait_for_frames()
        depth_frame = frames.get_depth_frame()

        if not depth_frame:
            return None, None

        depth_image = np.asanyarray(depth_frame.get_data())
        return depth_frame, depth_image

    def stop(self):
        self.pipeline.stop()