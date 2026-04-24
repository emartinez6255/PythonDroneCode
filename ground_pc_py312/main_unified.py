import time
import cv2
import numpy as np

from config import (
    SHOW_WINDOWS,
    ENABLE_MAESTRO,
    ENABLE_SCAN_WHEN_LOST,
    DISPLAY_WIDTH,
    DISPLAY_HEIGHT,
    DRAW_DEPTH,
    DRAW_THERMAL,
    DRAW_RGB_HOG,
    THERMAL_DETECT_EVERY_N_FRAMES,
    RGB_DETECT_EVERY_N_FRAMES,
    DEPTH_UPDATE_EVERY_N_FRAMES,
    PRINT_STATUS_EVERY_N_FRAMES,
)
from cam_module import ThermalCamera
from camera_mod import RealSenseCamera
from detection_module import RGBHumanDetector
from thermal_detector import ThermalHumanDetector
from avoidance import check_distance


# -------------------------------------------------
# HANGING-MOUNT REFERENCE ORIENTATION
# -------------------------------------------------
# IMPORTANT:
# The final reference frame is the mount HANGING under the drone.
# Therefore the thermal frame is ALWAYS rotated 180 degrees here before
# YOLO detection, tracking, and display.
#
# Result:
#   - Bench/upright test mount: raw feed upright -> corrected feed upside down.
#   - Hanging drone mount: raw feed upside down -> corrected feed upright.
#
# Do NOT change Maestro servo limits, servo values, pan direction, or tilt direction.
# This is only a camera-frame correction layer.

# Always use the hanging-mount reference frame.
# Bench/upright testing will look upside down on purpose.
# Real hanging mount will be corrected upright.
USE_HANGING_MOUNT_REFERENCE = False


class DummyMaestro(object):
    def __init__(self):
        self.current_pan = 1500.0
        self.current_tilt = 1500.0

    def set_pan_tilt(self, pan_us, tilt_us):
        self.current_pan = pan_us
        self.current_tilt = tilt_us

    def go_home(self):
        pass

    def go_center(self):
        self.current_pan = 1500.0
        self.current_tilt = 1500.0

    def close(self):
        pass


def build_maestro():
    if ENABLE_MAESTRO:
        from maestro_controller import MaestroController
        return MaestroController()
    return DummyMaestro()


def rotate_box_180(box, frame_w, frame_h):
    x1, y1, x2, y2 = box
    nx1 = frame_w - 1 - x2
    ny1 = frame_h - 1 - y2
    nx2 = frame_w - 1 - x1
    ny2 = frame_h - 1 - y1
    return (nx1, ny1, nx2, ny2)


def rotate_center_180(center, frame_w, frame_h):
    cx, cy = center
    return (frame_w - 1 - cx, frame_h - 1 - cy)


def rotate_detections_180(detections, frame_shape):
    frame_h, frame_w = frame_shape[:2]
    rotated = []
    for d in detections:
        nd = dict(d)
        if "box" in nd:
            nd["box"] = rotate_box_180(nd["box"], frame_w, frame_h)
        if "center" in nd:
            nd["center"] = rotate_center_180(nd["center"], frame_w, frame_h)
        rotated.append(nd)
    return rotated


def flip_box_h(box, frame_w):
    x1, y1, x2, y2 = box
    return (frame_w - 1 - x2, y1, frame_w - 1 - x1, y2)


def flip_center_h(center, frame_w):
    cx, cy = center
    return (frame_w - 1 - cx, cy)


def flip_detections_h(detections, frame_shape):
    frame_h, frame_w = frame_shape[:2]
    flipped = []
    for d in detections:
        nd = dict(d)
        if "box" in nd:
            nd["box"] = flip_box_h(nd["box"], frame_w)
        if "center" in nd:
            nd["center"] = flip_center_h(nd["center"], frame_w)
        flipped.append(nd)
    return flipped




def apply_hanging_mount_reference_orientation(frame):
    if frame is None:
        return None

    # Hanging the mount under the drone flips the camera installation by 180 deg.
    # Apply this BEFORE YOLO and BEFORE drawing, so detection/tracking/display
    # all use the same coordinate system.
    if USE_HANGING_MOUNT_REFERENCE:
        return cv2.rotate(frame, cv2.ROTATE_180)

    return frame


def get_tracking_frame(thermal_raw, tracker):
    if thermal_raw is None:
        return None

    # First force the frame into the hanging-mount reference orientation.
    frame = apply_hanging_mount_reference_orientation(thermal_raw)

    # Then apply the existing 360-mirror camera correction.
    # This keeps detector/tracker/display coordinates consistent after the
    # hard mirror flip without changing servo limits or Maestro commands.
    if tracker.is_mirrored():
        frame = cv2.rotate(frame, cv2.ROTATE_180)

    return frame

def make_bw_display_frame(frame):
    if frame is None:
        return None

    if len(frame.shape) == 2:
        gray = frame.copy()
    elif len(frame.shape) == 3 and frame.shape[2] == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame.copy()

    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def draw_thermal(frame, all_detections, chosen_target, tracking_info=None):
    out = frame.copy()
    h, w = out.shape[:2]

    cv2.line(out, (w // 2, 0), (w // 2, h), (255, 255, 0), 1)
    cv2.line(out, (0, h // 2), (w, h // 2), (255, 255, 0), 1)

    if tracking_info is not None:
        verify_box = tracking_info.get("verify_box", None)
        inner_box = tracking_info.get("inner_box", None)
        if verify_box is not None:
            vx1, vy1, vx2, vy2 = verify_box
            cv2.rectangle(out, (vx1, vy1), (vx2, vy2), (255, 0, 0), 1)
            cv2.putText(out, "VERIFY", (vx1 + 3, max(12, vy1 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 0, 0), 1)
        if inner_box is not None:
            ix1, iy1, ix2, iy2 = inner_box
            cv2.rectangle(out, (ix1, iy1), (ix2, iy2), (0, 255, 0), 1)
            cv2.putText(out, "TRACK HOLD", (ix1 + 3, max(12, iy1 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)

    for d in all_detections:
        x1, y1, x2, y2 = d["box"]

        color = (255, 0, 0)
        if chosen_target is not None and d["box"] == chosen_target["box"]:
            color = (0, 0, 255)

        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        cv2.circle(out, d["center"], 3, (0, 255, 255), -1)

        cv2.putText(
            out,
            "conf:{0:.2f}".format(d.get("conf", 0.0)),
            (x1, max(10, y1 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            color,
            1
        )

    if tracking_info is not None:
        cv2.putText(
            out,
            "mode:{0}".format(tracking_info.get("mode", "UNKNOWN")),
            (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1
        )
        cv2.putText(
            out,
            "err_x:{0}".format(int(tracking_info.get("err_x", 0))),
            (10, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1
        )
        cv2.putText(
            out,
            "err_y:{0}".format(int(tracking_info.get("err_y", 0))),
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1
        )
        cv2.putText(
            out,
            "missed:{0}".format(int(tracking_info.get("missed_frames", 0))),
            (10, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1
        )
        cv2.putText(
            out,
            "size:{0:.4f}".format(float(tracking_info.get("target_area_ratio", 0.0))),
            (10, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1
        )
        cv2.putText(
            out,
            "pan:{0:.1f} tilt:{1:.1f}".format(
                tracking_info.get("pan_us", 0.0),
                tracking_info.get("tilt_us", 0.0)
            ),
            (10, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1
        )
        cv2.putText(
            out,
            "mirror:{0}".format(int(tracking_info.get("mirrored", False))),
            (10, 140),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1
        )
        cv2.putText(
            out,
            "vpan:{0:.1f} vtilt:{1:.1f}".format(
                tracking_info.get("servo_pan_vel", 0.0),
                tracking_info.get("servo_tilt_vel", 0.0)
            ),
            (10, 160),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1
        )
        cv2.putText(
            out,
            "edge:{0} guard:{1}".format(
                tracking_info.get("edge_zone", None),
                int(tracking_info.get("wrap_guard", False))
            ),
            (10, 180),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1
        )

    return out


def draw_depth(depth_image, status, direction):
    depth_norm = cv2.normalize(depth_image, None, 0, 255, cv2.NORM_MINMAX)
    depth_norm = np.uint8(depth_norm)
    depth_colormap = cv2.applyColorMap(depth_norm, cv2.COLORMAP_JET)

    cv2.putText(
        depth_colormap,
        "Status: {0}".format(status),
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1
    )
    cv2.putText(
        depth_colormap,
        "Direction: {0}".format(direction),
        (10, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1
    )

    return depth_colormap


def main():
    thermal_cam = ThermalCamera()
    rs_cam = RealSenseCamera()

    thermal_detector = ThermalHumanDetector()
    rgb_detector = RGBHumanDetector()

    maestro = build_maestro()

    from tracker import ThermalTargetTracker
    tracker = ThermalTargetTracker(maestro)

    thermal_dets = []
    rgb_dets = []
    thermal_prepared = None
    chosen_target = None

    status = "UNKNOWN"
    direction = "UNKNOWN"

    loop_count = 0
    thermal_counter = 0
    rgb_counter = 0
    depth_counter = 0

    last_depth_image = None

    print("Unified SAR framework started.")
    print("Going to home...")
    tracker.go_home()
    time.sleep(1.0)
    tracker.reset_raster_scan()
    print("Pixel lock-on ready.")
    print("ESC or q to quit.")

    try:
        while True:
            loop_count += 1
            thermal_counter += 1
            rgb_counter += 1
            depth_counter += 1

            thermal_raw, ok_t = thermal_cam.get_frame()
            color_image, depth_image, depth_frame, ok_rs = rs_cam.get_frame()

            if not ok_t or not ok_rs:
                continue

            thermal_tracking_frame = get_tracking_frame(thermal_raw, tracker)

            # Detect in the same upright logical frame used by the tracker.
            if thermal_counter >= THERMAL_DETECT_EVERY_N_FRAMES or thermal_prepared is None:
                thermal_counter = 0
                thermal_prepared, thermal_dets = thermal_detector.detect(thermal_tracking_frame)
            else:
                thermal_prepared = thermal_detector.preprocess(thermal_tracking_frame)

            if rgb_counter >= RGB_DETECT_EVERY_N_FRAMES:
                rgb_counter = 0
                rgb_dets = rgb_detector.detect(color_image, depth_frame)

            if depth_counter >= DEPTH_UPDATE_EVERY_N_FRAMES:
                depth_counter = 0
                _, status, direction = check_distance(depth_frame, depth_image)
                last_depth_image = depth_image.copy()

            chosen_target = tracker.update_lock(thermal_dets, thermal_prepared.shape)

            if chosen_target is not None:
                tracking_info = tracker.update_tracking(chosen_target, thermal_prepared.shape)
            else:
                if tracker.is_verifying():
                    tracking_info = tracker.verification_status()
                elif ENABLE_SCAN_WHEN_LOST:
                    tracking_info = tracker.search_step()
                else:
                    tracking_info = {
                        "err_x": 0,
                        "err_y": 0,
                        "pan_us": maestro.current_pan,
                        "tilt_us": maestro.current_tilt,
                        "mode": "HOLD",
                        "missed_frames": 0,
                        "mirrored": tracker.is_mirrored(),
                    }

            if DRAW_RGB_HOG:
                rgb_view = rgb_detector.draw(color_image.copy(), rgb_dets)
            else:
                rgb_view = color_image.copy()

            thermal_view = None
            if DRAW_THERMAL and thermal_tracking_frame is not None:
                draw_frame = make_bw_display_frame(thermal_tracking_frame)
                draw_dets = thermal_dets
                draw_target = chosen_target

                # Keep the displayed feed aligned with the same logical frame
                # that drives detection and tracking, then mirror horizontally
                # for easier operator viewing.
                draw_frame = cv2.flip(draw_frame, 1)
                draw_dets = flip_detections_h(draw_dets, thermal_tracking_frame.shape)
                if draw_target is not None:
                    draw_target = flip_detections_h([draw_target], thermal_tracking_frame.shape)[0]

                thermal_view = draw_thermal(
                    draw_frame,
                    draw_dets,
                    draw_target,
                    tracking_info
                )

            depth_view = None
            if DRAW_DEPTH and last_depth_image is not None:
                depth_view = draw_depth(last_depth_image, status, direction)

            if SHOW_WINDOWS:
                if thermal_view is not None:
                    cv2.imshow(
                        "Thermal Detection + Pixel Lock",
                        cv2.resize(
                            thermal_view,
                            (DISPLAY_WIDTH, DISPLAY_HEIGHT),
                            interpolation=cv2.INTER_NEAREST
                        )
                    )

                cv2.imshow(
                    "RGB Human Detection",
                    cv2.resize(
                        rgb_view,
                        (DISPLAY_WIDTH, DISPLAY_HEIGHT),
                        interpolation=cv2.INTER_NEAREST
                    )
                )

                if depth_view is not None:
                    cv2.imshow(
                        "Depth Avoidance",
                        cv2.resize(
                            depth_view,
                            (DISPLAY_WIDTH, DISPLAY_HEIGHT),
                            interpolation=cv2.INTER_NEAREST
                        )
                    )

            if loop_count % PRINT_STATUS_EVERY_N_FRAMES == 0:
                print(
                    "thermal_all={0} thermal_lock={1} rgb_all={2} "
                    "avoid={3}/{4} mode={5} missed={6} pan={7:.1f} tilt={8:.1f} mirrored={9}".format(
                        len(thermal_dets),
                        1 if chosen_target is not None else 0,
                        len(rgb_dets),
                        status,
                        direction,
                        tracking_info.get("mode", "UNKNOWN"),
                        tracking_info.get("missed_frames", 0),
                        maestro.current_pan,
                        maestro.current_tilt,
                        int(tracking_info.get("mirrored", False))
                    )
                )

            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord("q"):
                break

    finally:
        thermal_cam.stop()
        rs_cam.stop()
        maestro.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()