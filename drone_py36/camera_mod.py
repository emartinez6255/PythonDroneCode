import time
import numpy as np
import pyrealsense2 as rs


class RealSenseCamera(object):
    def __init__(self):
        self.pipeline = rs.pipeline()
        self.profile = None

        # Try lighter / common profiles first.
        # Some devices or USB paths will reject certain combos.
        candidate_profiles = [
            # low-load profiles first
            (rs.stream.color, 320, 240, rs.format.bgr8, 15,
             rs.stream.depth, 320, 240, rs.format.z16, 15),

            (rs.stream.color, 424, 240, rs.format.bgr8, 15,
             rs.stream.depth, 424, 240, rs.format.z16, 15),

            # common safe VGA profiles
            (rs.stream.color, 640, 480, rs.format.bgr8, 15,
             rs.stream.depth, 640, 480, rs.format.z16, 15),

            (rs.stream.color, 640, 480, rs.format.bgr8, 30,
             rs.stream.depth, 640, 480, rs.format.z16, 30),
        ]

        last_error = None

        for prof in candidate_profiles:
            config = rs.config()
            try:
                config.enable_stream(prof[0], prof[1], prof[2], prof[3], prof[4])
                config.enable_stream(prof[5], prof[6], prof[7], prof[8], prof[9])

                print(
                    "Trying RealSense profile: "
                    "color={}x{}@{} | depth={}x{}@{}".format(
                        prof[1], prof[2], prof[4],
                        prof[6], prof[7], prof[9]
                    )
                )

                self.profile = self.pipeline.start(config)

                print(
                    "RealSense started with: "
                    "color={}x{}@{} | depth={}x{}@{}".format(
                        prof[1], prof[2], prof[4],
                        prof[6], prof[7], prof[9]
                    )
                )

                for _ in range(10):
                    self.pipeline.wait_for_frames()
                time.sleep(0.5)
                return

            except Exception as e:
                last_error = e
                try:
                    self.pipeline.stop()
                except Exception:
                    pass

        raise RuntimeError(
            "Could not start RealSense with any fallback profile. Last error: {}".format(last_error)
        )

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
        try:
            self.pipeline.stop()
        except Exception:
            pass