"""
R.A.V.E.N. SAR Mission Control
Desktop GUI replacement for main_unified.py

What this does:
- Starts/stops the SAR framework from a Windows GUI
- Shows Thermal/Night-Vision tracking feed and RGB RealSense feed side-by-side
- Shows depth avoidance status/direction/region metrics in a command panel
- Does NOT use cv2.imshow windows
- Uses tkinter only, so no extra GUI package is required

Expected project files in same folder:
    config.py
    cam_module.py
    camera_mod.py
    detection_module.py
    thermal_detector.py
    tracker.py
    avoidance.py
    maestro_controller.py
    maestro_config.py

Run:
    python raven_mission_control.py

Optional EXE build:
    pip install pyinstaller
    pyinstaller --onefile --windowed --name "RAVEN SAR Mission Control" raven_mission_control.py
"""

import threading
import time
import queue
import traceback
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
import numpy as np

from config import (
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
# CAMERA ORIENTATION
# -------------------------------------------------
# Your current tested hardware behavior:
#   False = correct feed orientation when mount is hanging.
# Keep this matching your working main_unified.py.
USE_HANGING_MOUNT_REFERENCE = False


# -------------------------------------------------
# GUI DISPLAY TUNING
# -------------------------------------------------
THERMAL_GUI_W = 470
THERMAL_GUI_H = 350
RGB_GUI_W = 470
RGB_GUI_H = 350
DEPTH_GUI_W = 930
DEPTH_GUI_H = 170
DEPTH_SMOOTHING_ALPHA = 0.35
GUI_DEPTH_UPDATE_EVERY_N_FRAMES = 2


# -------------------------------------------------
# TK / CV2 IMAGE HELPERS
# -------------------------------------------------
def cv2_to_tk_photo(frame_bgr, width, height, interpolation=cv2.INTER_LINEAR):
    """Convert a BGR/gray OpenCV image to a Tk PhotoImage without Pillow."""
    if frame_bgr is None:
        frame_bgr = np.zeros((height, width, 3), dtype=np.uint8)

    if len(frame_bgr.shape) == 2:
        frame_bgr = cv2.cvtColor(frame_bgr, cv2.COLOR_GRAY2BGR)

    resized = cv2.resize(frame_bgr, (width, height), interpolation=interpolation)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

    header = f"P6 {width} {height} 255\n".encode("ascii")
    data = header + rgb.tobytes()
    return tk.PhotoImage(data=data, format="PPM")


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
    if USE_HANGING_MOUNT_REFERENCE:
        return cv2.rotate(frame, cv2.ROTATE_180)
    return frame


def get_tracking_frame(thermal_raw, tracker):
    if thermal_raw is None:
        return None

    frame = apply_hanging_mount_reference_orientation(thermal_raw)

    # Existing 360 mirror correction. This keeps detector/tracker/display
    # coordinates consistent after hard mirror flip.
    if tracker.is_mirrored():
        frame = cv2.rotate(frame, cv2.ROTATE_180)

    return frame


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
        cv2.putText(out, "conf:{0:.2f}".format(d.get("conf", 0.0)), (x1, max(10, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    if tracking_info is not None:
        lines = [
            "mode:{0}".format(tracking_info.get("mode", "UNKNOWN")),
            "err_x:{0}".format(int(tracking_info.get("err_x", 0))),
            "err_y:{0}".format(int(tracking_info.get("err_y", 0))),
            "missed:{0}".format(int(tracking_info.get("missed_frames", 0))),
            "size:{0:.4f}".format(float(tracking_info.get("target_area_ratio", 0.0))),
            "pan:{0:.1f} tilt:{1:.1f}".format(tracking_info.get("pan_us", 0.0), tracking_info.get("tilt_us", 0.0)),
            "mirror:{0}".format(int(tracking_info.get("mirrored", False))),
            "vpan:{0:.1f} vtilt:{1:.1f}".format(tracking_info.get("servo_pan_vel", 0.0), tracking_info.get("servo_tilt_vel", 0.0)),
        ]
        y = 20
        for line in lines:
            cv2.putText(out, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
            y += 20

    return out


def draw_depth(depth_image, status, direction):
    if depth_image is None:
        return None

    depth = np.asanyarray(depth_image)
    if len(depth.shape) > 2:
        depth = depth[:, :, 0]

    depth = depth.astype(np.float32)

    max_depth_mm = 4000.0
    depth = np.clip(depth, 0, max_depth_mm)

    depth_norm = (depth / max_depth_mm) * 255.0
    depth_norm = np.uint8(depth_norm)
    depth_norm = cv2.GaussianBlur(depth_norm, (5, 5), 0)

    depth_colormap = cv2.applyColorMap(depth_norm, cv2.COLORMAP_JET)

    cv2.putText(depth_colormap, "Status: {0}".format(status), (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    cv2.putText(depth_colormap, "Direction: {0}".format(direction), (10, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

    return depth_colormap


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


class FrameworkWorker(threading.Thread):
    def __init__(self, output_queue, stop_event):
        super().__init__(daemon=True)
        self.output_queue = output_queue
        self.stop_event = stop_event

    def publish(self, payload):
        # Keep GUI responsive by dropping stale frames if needed.
        try:
            while self.output_queue.qsize() > 2:
                self.output_queue.get_nowait()
        except Exception:
            pass
        self.output_queue.put(payload)

    def run(self):
        thermal_cam = None
        rs_cam = None
        maestro = None

        try:
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
            tracking_info = {}

            status = "UNKNOWN"
            direction = "UNKNOWN"
            depth_regions = {}
            last_depth_image = None
            depth_view = None
            smoothed_depth_view = None

            loop_count = 0
            thermal_counter = 0
            rgb_counter = 0
            depth_counter = 0
            start_time = time.time()

            tracker.go_home()
            time.sleep(1.0)
            tracker.reset_raster_scan()

            self.publish({
                "event": "status",
                "running": True,
                "message": "R.A.V.E.N. framework started."
            })

            while not self.stop_event.is_set():
                loop_count += 1
                thermal_counter += 1
                rgb_counter += 1
                depth_counter += 1

                thermal_raw, ok_t = thermal_cam.get_frame()
                color_image, depth_image, depth_frame, ok_rs = rs_cam.get_frame()

                if not ok_t or not ok_rs:
                    time.sleep(0.01)
                    continue

                thermal_tracking_frame = get_tracking_frame(thermal_raw, tracker)

                if thermal_counter >= THERMAL_DETECT_EVERY_N_FRAMES or thermal_prepared is None:
                    thermal_counter = 0
                    thermal_prepared, thermal_dets = thermal_detector.detect(thermal_tracking_frame)
                else:
                    thermal_prepared = thermal_detector.preprocess(thermal_tracking_frame)

                if rgb_counter >= RGB_DETECT_EVERY_N_FRAMES:
                    rgb_counter = 0
                    rgb_dets = rgb_detector.detect(color_image, depth_frame)

                if depth_counter >= GUI_DEPTH_UPDATE_EVERY_N_FRAMES:
                    depth_counter = 0
                    depth_regions, status, direction = check_distance(depth_frame, depth_image)
                    last_depth_image = depth_image.copy()

                    new_depth_view = draw_depth(last_depth_image, status, direction)

                    if new_depth_view is not None:
                        if smoothed_depth_view is None:
                            smoothed_depth_view = new_depth_view.copy()
                        else:
                            smoothed_depth_view = cv2.addWeighted(
                                new_depth_view,
                                DEPTH_SMOOTHING_ALPHA,
                                smoothed_depth_view,
                                1.0 - DEPTH_SMOOTHING_ALPHA,
                                0
                            )
                        depth_view = smoothed_depth_view.copy()

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

                    # Same operator viewing style as current main_unified.py.
                    draw_frame = cv2.flip(draw_frame, 1)
                    draw_dets = flip_detections_h(draw_dets, thermal_tracking_frame.shape)
                    if draw_target is not None:
                        draw_target = flip_detections_h([draw_target], thermal_tracking_frame.shape)[0]

                    thermal_view = draw_thermal(draw_frame, draw_dets, draw_target, tracking_info)

                elapsed = max(0.001, time.time() - start_time)
                fps = loop_count / elapsed

                if loop_count % PRINT_STATUS_EVERY_N_FRAMES == 0:
                    print(
                        "thermal_all={0} thermal_lock={1} rgb_all={2} avoid={3}/{4} "
                        "mode={5} missed={6} pan={7:.1f} tilt={8:.1f} mirrored={9}".format(
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

                self.publish({
                    "event": "frame",
                    "running": True,
                    "thermal_view": thermal_view,
                    "rgb_view": rgb_view,
                    "depth_view": depth_view,
                    "thermal_count": len(thermal_dets),
                    "thermal_lock": 1 if chosen_target is not None else 0,
                    "rgb_count": len(rgb_dets),
                    "avoid_status": status,
                    "avoid_direction": direction,
                    "depth_regions": depth_regions,
                    "tracking_info": dict(tracking_info),
                    "pan": float(getattr(maestro, "current_pan", 0.0)),
                    "tilt": float(getattr(maestro, "current_tilt", 0.0)),
                    "fps": fps,
                })

        except Exception as exc:
            self.publish({
                "event": "error",
                "running": False,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            })
        finally:
            try:
                if thermal_cam is not None:
                    thermal_cam.stop()
            except Exception:
                pass
            try:
                if rs_cam is not None:
                    rs_cam.stop()
            except Exception:
                pass
            try:
                if maestro is not None:
                    maestro.close()
            except Exception:
                pass
            self.publish({
                "event": "stopped",
                "running": False,
                "message": "R.A.V.E.N. framework stopped."
            })


class RavenMissionControl(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("R.A.V.E.N. SAR Mission Control")
        self.geometry("1260x820")
        self.minsize(1120, 740)
        self.configure(bg="#0b1020")

        self.output_queue = queue.Queue()
        self.stop_event = None
        self.worker = None
        self.running = False

        self.thermal_photo = None
        self.rgb_photo = None
        self.depth_photo = None

        self._build_ui()
        self.after(40, self._poll_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#0b1020")
        style.configure("Panel.TFrame", background="#111827", relief="flat")
        style.configure("TLabel", background="#0b1020", foreground="#e5e7eb")
        style.configure("Panel.TLabel", background="#111827", foreground="#e5e7eb")
        style.configure("Title.TLabel", background="#0b1020", foreground="#e5e7eb", font=("Segoe UI", 20, "bold"))
        style.configure("Sub.TLabel", background="#0b1020", foreground="#93c5fd", font=("Segoe UI", 10))
        style.configure("FeedTitle.TLabel", background="#111827", foreground="#f9fafb", font=("Segoe UI", 12, "bold"))
        style.configure("Status.TLabel", background="#111827", foreground="#d1d5db", font=("Consolas", 10))
        style.configure("Start.TButton", font=("Segoe UI", 11, "bold"), padding=8)
        style.configure("Stop.TButton", font=("Segoe UI", 11, "bold"), padding=8)

        header = ttk.Frame(self)
        header.pack(fill="x", padx=18, pady=(14, 8))

        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text="R.A.V.E.N. SAR Mission Control", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="Real-time Autonomous Vision, Evaluation, and Navigation", style="Sub.TLabel").pack(anchor="w")

        control_box = ttk.Frame(header)
        control_box.pack(side="right")
        self.start_btn = ttk.Button(control_box, text="▶ Launch Framework", command=self.start_framework, style="Start.TButton")
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = ttk.Button(control_box, text="■ Stop Framework", command=self.stop_framework, style="Stop.TButton", state="disabled")
        self.stop_btn.pack(side="left")

        status_bar = ttk.Frame(self, style="Panel.TFrame")
        status_bar.pack(fill="x", padx=18, pady=(0, 10))
        self.connection_label = ttk.Label(status_bar, text="SYSTEM: OFFLINE", style="Panel.TLabel", font=("Segoe UI", 11, "bold"))
        self.connection_label.pack(side="left", padx=12, pady=8)
        self.fps_label = ttk.Label(status_bar, text="FPS: --", style="Panel.TLabel")
        self.fps_label.pack(side="right", padx=12, pady=8)

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        feeds = ttk.Frame(main)
        feeds.pack(side="left", fill="both", expand=True)

        feed_row = ttk.Frame(feeds)
        feed_row.pack(fill="both", expand=True)

        thermal_panel = ttk.Frame(feed_row, style="Panel.TFrame")
        thermal_panel.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ttk.Label(thermal_panel, text="THERMAL / NIGHT-VISION HUMAN TRACKING", style="FeedTitle.TLabel").pack(anchor="w", padx=10, pady=(10, 6))
        self.thermal_canvas = tk.Label(thermal_panel, bg="#000000", anchor="center")
        self.thermal_canvas.pack(anchor="center", expand=True, padx=10, pady=(0, 10))

        rgb_panel = ttk.Frame(feed_row, style="Panel.TFrame")
        rgb_panel.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ttk.Label(rgb_panel, text="REALSENSE RGB HUMAN DETECTION", style="FeedTitle.TLabel").pack(anchor="w", padx=10, pady=(10, 6))
        self.rgb_canvas = tk.Label(rgb_panel, bg="#000000", anchor="center")
        self.rgb_canvas.pack(anchor="center", expand=True, padx=10, pady=(0, 10))

        bottom_panel = ttk.Frame(feeds, style="Panel.TFrame")
        bottom_panel.pack(fill="x", pady=(12, 0))
        ttk.Label(bottom_panel, text="DEPTH AVOIDANCE VISUALIZATION", style="FeedTitle.TLabel").pack(anchor="w", padx=10, pady=(10, 6))
        self.depth_canvas = tk.Label(bottom_panel, bg="#000000", anchor="center")
        self.depth_canvas.pack(anchor="center", padx=10, pady=(0, 10))

        command_panel = ttk.Frame(main, style="Panel.TFrame", width=330)
        command_panel.pack(side="right", fill="y", padx=(14, 0))
        command_panel.pack_propagate(False)

        ttk.Label(command_panel, text="MISSION COMMANDS", style="FeedTitle.TLabel").pack(anchor="w", padx=12, pady=(12, 8))

        self.command_text = tk.Text(
            command_panel,
            height=30,
            bg="#020617",
            fg="#d1fae5",
            insertbackground="#d1fae5",
            relief="flat",
            font=("Consolas", 10),
            wrap="word",
        )
        self.command_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.command_text.insert("end", "R.A.V.E.N. standby.\nPress Launch Framework to begin.\n")
        self.command_text.configure(state="disabled")

        self._show_blank_frames()

    def _show_blank_frames(self):
        blank_thermal = np.zeros((THERMAL_GUI_H, THERMAL_GUI_W, 3), dtype=np.uint8)
        blank_rgb = np.zeros((RGB_GUI_H, RGB_GUI_W, 3), dtype=np.uint8)
        blank_depth = np.zeros((DEPTH_GUI_H, DEPTH_GUI_W, 3), dtype=np.uint8)

        cv2.putText(blank_thermal, "NO THERMAL SIGNAL", (105, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (160, 160, 160), 2)
        cv2.putText(blank_rgb, "NO RGB SIGNAL", (140, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (160, 160, 160), 2)
        cv2.putText(blank_depth, "NO DEPTH SIGNAL", (345, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (160, 160, 160), 2)

        self.thermal_photo = cv2_to_tk_photo(blank_thermal, THERMAL_GUI_W, THERMAL_GUI_H)
        self.rgb_photo = cv2_to_tk_photo(blank_rgb, RGB_GUI_W, RGB_GUI_H)
        self.depth_photo = cv2_to_tk_photo(blank_depth, DEPTH_GUI_W, DEPTH_GUI_H)

        self.thermal_canvas.configure(image=self.thermal_photo)
        self.rgb_canvas.configure(image=self.rgb_photo)
        self.depth_canvas.configure(image=self.depth_photo)

    def start_framework(self):
        if self.running:
            return
        self.stop_event = threading.Event()
        self.worker = FrameworkWorker(self.output_queue, self.stop_event)
        self.worker.start()
        self.running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.connection_label.configure(text="SYSTEM: STARTING...")
        self._append_command("Launching R.A.V.E.N. framework...\n")

    def stop_framework(self):
        if not self.running:
            return
        self._append_command("Stopping framework...\n")
        self.connection_label.configure(text="SYSTEM: STOPPING...")
        if self.stop_event is not None:
            self.stop_event.set()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def _append_command(self, text):
        self.command_text.configure(state="normal")
        self.command_text.insert("end", text)
        self.command_text.see("end")
        self.command_text.configure(state="disabled")

    def _format_depth_regions(self, regions):
        if not regions:
            return "Depth regions: --"
        lines = []
        for name in ("left", "center", "right"):
            vals = regions.get(name, None)
            if vals is None:
                continue
            try:
                med, min_d, free = vals
                lines.append(f"  {name:<6} median={med:>5.2f}m  min={min_d:>5.2f}m  free={free:>4.2f}")
            except Exception:
                lines.append(f"  {name:<6} {vals}")
        return "Depth regions:\n" + "\n".join(lines)

    def _update_command_panel(self, payload):
        tracking = payload.get("tracking_info", {}) or {}
        text = []
        text.append("R.A.V.E.N. LIVE STATUS")
        text.append("-" * 30)
        text.append(f"Thermal detections : {payload.get('thermal_count', 0)}")
        text.append(f"Thermal lock       : {payload.get('thermal_lock', 0)}")
        text.append(f"RGB detections     : {payload.get('rgb_count', 0)}")
        text.append("")
        text.append("Depth/Avoidance")
        text.append(f"  Status    : {payload.get('avoid_status', 'UNKNOWN')}")
        text.append(f"  Direction : {payload.get('avoid_direction', 'UNKNOWN')}")
        text.append(self._format_depth_regions(payload.get("depth_regions", {})))
        text.append("")
        text.append("Mount/Tracking")
        text.append(f"  Mode      : {tracking.get('mode', 'UNKNOWN')}")
        text.append(f"  Pan       : {payload.get('pan', 0.0):.1f} us")
        text.append(f"  Tilt      : {payload.get('tilt', 0.0):.1f} us")
        text.append(f"  Mirrored  : {int(tracking.get('mirrored', False))}")
        text.append(f"  Err X/Y   : {int(tracking.get('err_x', 0))}, {int(tracking.get('err_y', 0))}")
        text.append(f"  Velocity  : pan={tracking.get('servo_pan_vel', 0.0):.1f}, tilt={tracking.get('servo_tilt_vel', 0.0):.1f}")
        text.append(f"  Missed    : {tracking.get('missed_frames', 0)}")
        text.append("")
        text.append(f"FPS estimate: {payload.get('fps', 0.0):.1f}")

        self.command_text.configure(state="normal")
        self.command_text.delete("1.0", "end")
        self.command_text.insert("end", "\n".join(text))
        self.command_text.configure(state="disabled")

    def _poll_queue(self):
        try:
            while True:
                payload = self.output_queue.get_nowait()
                event = payload.get("event")

                if event == "frame":
                    self.connection_label.configure(text="SYSTEM: ONLINE")
                    self.fps_label.configure(text="FPS: {0:.1f}".format(payload.get("fps", 0.0)))

                    thermal_view = payload.get("thermal_view")
                    rgb_view = payload.get("rgb_view")
                    depth_view = payload.get("depth_view")

                    if thermal_view is not None:
                        self.thermal_photo = cv2_to_tk_photo(thermal_view, THERMAL_GUI_W, THERMAL_GUI_H, interpolation=cv2.INTER_LINEAR)
                        self.thermal_canvas.configure(image=self.thermal_photo)
                    if rgb_view is not None:
                        self.rgb_photo = cv2_to_tk_photo(rgb_view, RGB_GUI_W, RGB_GUI_H, interpolation=cv2.INTER_LINEAR)
                        self.rgb_canvas.configure(image=self.rgb_photo)
                    if depth_view is not None:
                        self.depth_photo = cv2_to_tk_photo(depth_view, DEPTH_GUI_W, DEPTH_GUI_H, interpolation=cv2.INTER_LINEAR)
                        self.depth_canvas.configure(image=self.depth_photo)

                    self._update_command_panel(payload)

                elif event == "status":
                    self.connection_label.configure(text="SYSTEM: ONLINE")
                    self._append_command(payload.get("message", "Status update") + "\n")

                elif event == "error":
                    self.running = False
                    self.start_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    self.connection_label.configure(text="SYSTEM: ERROR")
                    self._append_command("\nERROR:\n" + payload.get("message", "Unknown error") + "\n")
                    self._append_command(payload.get("traceback", "") + "\n")
                    messagebox.showerror("R.A.V.E.N. Error", payload.get("message", "Unknown error"))

                elif event == "stopped":
                    self.running = False
                    self.start_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    self.connection_label.configure(text="SYSTEM: OFFLINE")
                    self.fps_label.configure(text="FPS: --")
                    self._append_command("\n" + payload.get("message", "Stopped") + "\n")

        except queue.Empty:
            pass
        finally:
            self.after(40, self._poll_queue)

    def on_close(self):
        if self.running and self.stop_event is not None:
            self.stop_event.set()
            time.sleep(0.2)
        self.destroy()


if __name__ == "__main__":
    app = RavenMissionControl()
    app.mainloop()
