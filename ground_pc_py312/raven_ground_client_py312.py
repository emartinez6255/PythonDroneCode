"""
R.A.V.E.N. Ground Client - Python 3.12 recommended

Run this on your ground PC. For localhost testing, run drone_server_py36.py
in another terminal on the same laptop and leave SERVER_IP = "127.0.0.1".

This client:
- connects to the drone/server
- displays thermal, RGB, and depth feeds
- runs your Python 3.12 YOLOv8 thermal detector locally
- sends thermal detections back to the drone/server
- sends START/STOP/SHUTDOWN commands
"""

import socket
import struct
import pickle
import threading
import queue
import time
import traceback
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
import numpy as np

from thermal_detector import ThermalHumanDetector
from detection_module import RGBHumanDetector


# -------------------------------------------------
# NETWORK SETTINGS
# -------------------------------------------------
SERVER_IP = "127.0.0.1"       # Localhost test. Later replace with Jetson IP.
SERVER_PORT = 5055
MAX_MESSAGE_SIZE = 25 * 1024 * 1024

# GUI display size
THERMAL_GUI_W = 470
THERMAL_GUI_H = 350
RGB_GUI_W = 470
RGB_GUI_H = 350
DEPTH_GUI_W = 930
DEPTH_GUI_H = 170

# Run detectors every N incoming frames.
THERMAL_DETECT_EVERY_N_FRAMES = 1
RGB_DETECT_EVERY_N_FRAMES = 2


# -------------------------------------------------
# SOCKET HELPERS
# -------------------------------------------------
def _recvall(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def send_message(sock, send_lock, obj):
    payload = pickle.dumps(obj, protocol=2)
    header = struct.pack("!I", len(payload))
    with send_lock:
        sock.sendall(header + payload)


def recv_message(sock):
    header = _recvall(sock, 4)
    if header is None:
        return None
    size = struct.unpack("!I", header)[0]
    if size <= 0 or size > MAX_MESSAGE_SIZE:
        raise RuntimeError("Invalid message size: {0}".format(size))
    payload = _recvall(sock, size)
    if payload is None:
        return None
    return pickle.loads(payload)


def decode_jpg(data):
    if data is None:
        return None
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def cv2_to_tk_photo(frame_bgr, width, height, interpolation=cv2.INTER_LINEAR):
    if frame_bgr is None:
        frame_bgr = np.zeros((height, width, 3), dtype=np.uint8)
    if len(frame_bgr.shape) == 2:
        frame_bgr = cv2.cvtColor(frame_bgr, cv2.COLOR_GRAY2BGR)
    resized = cv2.resize(frame_bgr, (width, height), interpolation=interpolation)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    header = "P6 {0} {1} 255\n".format(width, height).encode("ascii")
    data = header + rgb.tobytes()
    return tk.PhotoImage(data=data, format="PPM")


# -------------------------------------------------
# DRAW HELPERS
# -------------------------------------------------
def draw_thermal_overlay(frame, detections, tracking_info):
    if frame is None:
        return None
    out = frame.copy()
    h, w = out.shape[:2]

    # Operator-style mirror, matching your prior GUI/main display behavior.
    out = cv2.flip(out, 1)

    cv2.line(out, (w // 2, 0), (w // 2, h), (255, 255, 0), 1)
    cv2.line(out, (0, h // 2), (w, h // 2), (255, 255, 0), 1)

    if tracking_info is not None:
        verify_box = tracking_info.get("verify_box")
        inner_box = tracking_info.get("inner_box")
        if verify_box is not None:
            vx1, vy1, vx2, vy2 = verify_box
            # boxes were produced on non-flipped detector frame, so flip x coords for display
            vx1, vx2 = w - 1 - vx2, w - 1 - vx1
            cv2.rectangle(out, (vx1, vy1), (vx2, vy2), (255, 0, 0), 1)
            cv2.putText(out, "VERIFY", (vx1 + 3, max(12, vy1 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 0, 0), 1)
        if inner_box is not None:
            ix1, iy1, ix2, iy2 = inner_box
            ix1, ix2 = w - 1 - ix2, w - 1 - ix1
            cv2.rectangle(out, (ix1, iy1), (ix2, iy2), (0, 255, 0), 1)
            cv2.putText(out, "TRACK HOLD", (ix1 + 3, max(12, iy1 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)

    for i, d in enumerate(detections or []):
        box = d.get("box")
        center = d.get("center")
        if box is None or center is None:
            continue
        x1, y1, x2, y2 = box
        # flip for operator view
        x1, x2 = w - 1 - x2, w - 1 - x1
        cx, cy = center
        cx = w - 1 - cx
        color = (0, 0, 255) if i == 0 else (255, 0, 0)
        cv2.rectangle(out, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
        cv2.circle(out, (int(cx), int(cy)), 3, (0, 255, 255), -1)
        cv2.putText(out, "conf:{0:.2f}".format(float(d.get("conf", 0.0))), (int(x1), max(10, int(y1) - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    lines = []
    if tracking_info is not None:
        lines = [
            "mode:{0}".format(tracking_info.get("mode", "UNKNOWN")),
            "err_x:{0}".format(int(tracking_info.get("err_x", 0))),
            "err_y:{0}".format(int(tracking_info.get("err_y", 0))),
            "missed:{0}".format(int(tracking_info.get("missed_frames", 0))),
            "pan:{0:.1f} tilt:{1:.1f}".format(float(tracking_info.get("pan_us", 0.0)), float(tracking_info.get("tilt_us", 0.0))),
            "mirror:{0}".format(int(tracking_info.get("mirrored", False))),
        ]
    y = 20
    for line in lines:
        cv2.putText(out, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        y += 20

    return out


# -------------------------------------------------
# NETWORK WORKER
# -------------------------------------------------
class GroundClientWorker(threading.Thread):
    def __init__(self, gui_queue, command_queue, stop_event):
        threading.Thread.__init__(self)
        self.daemon = True
        self.gui_queue = gui_queue
        self.command_queue = command_queue
        self.stop_event = stop_event
        self.sock = None
        self.send_lock = threading.Lock()
        self.thermal_detector = None
        self.rgb_detector = None
        self.detect_counter = 0
        self.rgb_detect_counter = 0
        self.latest_detections = []
        self.latest_rgb_detections = []

    def gui_publish(self, payload):
        try:
            while self.gui_queue.qsize() > 2:
                self.gui_queue.get_nowait()
        except Exception:
            pass
        self.gui_queue.put(payload)

    def command_sender_loop(self):
        while not self.stop_event.is_set():
            try:
                cmd = self.command_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                send_message(self.sock, self.send_lock, cmd)
            except Exception as exc:
                self.gui_publish({"event": "error", "message": "Command send failed: {0}".format(exc)})
                self.stop_event.set()
                break

    def run(self):
        try:
            self.gui_publish({"event": "status", "message": "Connecting to {0}:{1}...".format(SERVER_IP, SERVER_PORT)})
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((SERVER_IP, SERVER_PORT))

            self.thermal_detector = ThermalHumanDetector()
            self.rgb_detector = RGBHumanDetector()

            tx = threading.Thread(target=self.command_sender_loop)
            tx.daemon = True
            tx.start()

            self.gui_publish({"event": "status", "message": "Connected to drone server."})

            while not self.stop_event.is_set():
                msg = recv_message(self.sock)
                if msg is None:
                    break

                msg_type = msg.get("type")
                if msg_type == "frame":
                    seq = int(msg.get("seq", -1))
                    thermal_frame = decode_jpg(msg.get("thermal_jpg"))
                    rgb_frame = decode_jpg(msg.get("rgb_jpg"))
                    depth_frame = decode_jpg(msg.get("depth_jpg"))

                    # Match the old working local 3.12 path:
                    # thermal_tracking_frame -> ThermalHumanDetector.preprocess/detect.
                    # The server sends the native thermal_tracking_frame without resizing,
                    # so detections stay in the exact coordinates tracker.py uses.
                    detections = self.latest_detections
                    thermal_display_frame = thermal_frame

                    self.detect_counter += 1
                    if thermal_frame is not None:
                        try:
                            if self.detect_counter >= THERMAL_DETECT_EVERY_N_FRAMES:
                                self.detect_counter = 0
                                thermal_display_frame, detections = self.thermal_detector.detect(thermal_frame)
                                self.latest_detections = detections
                                send_message(self.sock, self.send_lock, {
                                    "type": "thermal_detections",
                                    "seq": seq,
                                    "detections": detections,
                                })
                            else:
                                thermal_display_frame = self.thermal_detector.preprocess(thermal_frame)
                        except Exception as det_exc:
                            self.gui_publish({"event": "status", "message": "Thermal detection warning: {0}".format(det_exc)})
                            thermal_display_frame = thermal_frame

                    rgb_detections = self.latest_rgb_detections
                    rgb_view = rgb_frame
                    self.rgb_detect_counter += 1
                    if rgb_frame is not None and self.rgb_detector is not None:
                        try:
                            if self.rgb_detect_counter >= RGB_DETECT_EVERY_N_FRAMES:
                                self.rgb_detect_counter = 0
                                # DepthFrame is not streamed as a RealSense object, so pass None.
                                # Existing RGB detector catches that and reports distance as 0.
                                rgb_detections = self.rgb_detector.detect(rgb_frame, None)
                                self.latest_rgb_detections = rgb_detections
                            rgb_view = self.rgb_detector.draw(rgb_frame.copy(), rgb_detections)
                        except Exception as rgb_exc:
                            self.gui_publish({"event": "status", "message": "RGB detection warning: {0}".format(rgb_exc)})
                            rgb_view = rgb_frame

                    tracking_info = msg.get("tracking_info", {}) or {}
                    thermal_view = draw_thermal_overlay(thermal_display_frame, detections, tracking_info)

                    payload = dict(msg)
                    payload["event"] = "frame"
                    payload["thermal_view"] = thermal_view
                    payload["rgb_view"] = rgb_view
                    payload["depth_view"] = depth_frame
                    payload["client_detection_count"] = len(detections or [])
                    payload["client_rgb_detection_count"] = len(rgb_detections or [])
                    self.gui_publish(payload)

                elif msg_type == "server_status":
                    self.gui_publish({"event": "status", "message": msg.get("message", "Server status")})
                elif msg_type == "server_error":
                    self.gui_publish({"event": "error", "message": msg.get("message", "Server error"), "traceback": msg.get("traceback", "")})

        except Exception as exc:
            self.gui_publish({"event": "error", "message": str(exc), "traceback": traceback.format_exc()})
        finally:
            try:
                if self.sock is not None:
                    self.sock.close()
            except Exception:
                pass
            self.gui_publish({"event": "stopped", "message": "Disconnected from drone server."})


# -------------------------------------------------
# GUI
# -------------------------------------------------
class RavenGroundClient(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.title("R.A.V.E.N. SAR Mission Control - Ground Client")
        self.geometry("1260x820")
        self.minsize(1120, 740)
        self.configure(bg="#0b1020")

        self.gui_queue = queue.Queue()
        self.command_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.connected = False

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
        style.configure("Start.TButton", font=("Segoe UI", 11, "bold"), padding=8)
        style.configure("Stop.TButton", font=("Segoe UI", 11, "bold"), padding=8)

        header = ttk.Frame(self)
        header.pack(fill="x", padx=18, pady=(14, 8))

        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text="R.A.V.E.N. SAR Mission Control", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="Remote Ground Client: PC YOLOv8 + Drone Python 3.6 Framework", style="Sub.TLabel").pack(anchor="w")

        control_box = ttk.Frame(header)
        control_box.pack(side="right")
        self.connect_btn = ttk.Button(control_box, text="Connect", command=self.connect_server, style="Start.TButton")
        self.connect_btn.pack(side="left", padx=(0, 8))
        self.start_btn = ttk.Button(control_box, text="Launch Framework", command=self.start_framework, style="Start.TButton", state="disabled")
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = ttk.Button(control_box, text="Stop Framework", command=self.stop_framework, style="Stop.TButton", state="disabled")
        self.stop_btn.pack(side="left")

        status_bar = ttk.Frame(self, style="Panel.TFrame")
        status_bar.pack(fill="x", padx=18, pady=(0, 10))
        self.connection_label = ttk.Label(status_bar, text="SYSTEM: DISCONNECTED", style="Panel.TLabel", font=("Segoe UI", 11, "bold"))
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
        ttk.Label(thermal_panel, text="THERMAL / NIGHT-VISION TRACKING", style="FeedTitle.TLabel").pack(anchor="w", padx=10, pady=(10, 6))
        self.thermal_canvas = tk.Label(thermal_panel, bg="#000000", anchor="center", width=THERMAL_GUI_W, height=THERMAL_GUI_H)
        self.thermal_canvas.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        rgb_panel = ttk.Frame(feed_row, style="Panel.TFrame")
        rgb_panel.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ttk.Label(rgb_panel, text="REALSENSE RGB FEED", style="FeedTitle.TLabel").pack(anchor="w", padx=10, pady=(10, 6))
        self.rgb_canvas = tk.Label(rgb_panel, bg="#000000", anchor="center", width=RGB_GUI_W, height=RGB_GUI_H)
        self.rgb_canvas.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        bottom_panel = ttk.Frame(feeds, style="Panel.TFrame")
        bottom_panel.pack(fill="x", pady=(12, 0))
        ttk.Label(bottom_panel, text="DEPTH AVOIDANCE VISUALIZATION", style="FeedTitle.TLabel").pack(anchor="w", padx=10, pady=(10, 6))
        self.depth_canvas = tk.Label(bottom_panel, bg="#000000", anchor="center", width=DEPTH_GUI_W, height=DEPTH_GUI_H)
        self.depth_canvas.pack(fill="x", padx=10, pady=(0, 10))

        command_panel = ttk.Frame(main, style="Panel.TFrame", width=330)
        command_panel.pack(side="right", fill="y", padx=(14, 0))
        command_panel.pack_propagate(False)

        ttk.Label(command_panel, text="MISSION COMMANDS", style="FeedTitle.TLabel").pack(anchor="w", padx=12, pady=(12, 8))
        self.command_text = tk.Text(command_panel, height=30, bg="#020617", fg="#d1fae5", insertbackground="#d1fae5", relief="flat", font=("Consolas", 10), wrap="word")
        self.command_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.command_text.insert("end", "R.A.V.E.N. remote client standby.\nClick Connect.\n")
        self.command_text.configure(state="disabled")

        self._show_blank_frames()

    def _show_blank_frames(self):
        blank_thermal = np.zeros((THERMAL_GUI_H, THERMAL_GUI_W, 3), dtype=np.uint8)
        blank_rgb = np.zeros((RGB_GUI_H, RGB_GUI_W, 3), dtype=np.uint8)
        blank_depth = np.zeros((DEPTH_GUI_H, DEPTH_GUI_W, 3), dtype=np.uint8)
        cv2.putText(blank_thermal, "NO THERMAL SIGNAL", (110, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (160, 160, 160), 2)
        cv2.putText(blank_rgb, "NO RGB SIGNAL", (140, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (160, 160, 160), 2)
        cv2.putText(blank_depth, "NO DEPTH SIGNAL", (350, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (160, 160, 160), 2)
        self.thermal_photo = cv2_to_tk_photo(blank_thermal, THERMAL_GUI_W, THERMAL_GUI_H)
        self.rgb_photo = cv2_to_tk_photo(blank_rgb, RGB_GUI_W, RGB_GUI_H)
        self.depth_photo = cv2_to_tk_photo(blank_depth, DEPTH_GUI_W, DEPTH_GUI_H)
        self.thermal_canvas.configure(image=self.thermal_photo)
        self.rgb_canvas.configure(image=self.rgb_photo)
        self.depth_canvas.configure(image=self.depth_photo)

    def _append_command(self, text):
        self.command_text.configure(state="normal")
        self.command_text.insert("end", text)
        self.command_text.see("end")
        self.command_text.configure(state="disabled")

    def connect_server(self):
        if self.worker is not None:
            return
        self.stop_event.clear()
        self.worker = GroundClientWorker(self.gui_queue, self.command_queue, self.stop_event)
        self.worker.start()
        self.connect_btn.configure(state="disabled")
        self.connection_label.configure(text="SYSTEM: CONNECTING")

    def start_framework(self):
        self.command_queue.put({"type": "command", "command": "START"})
        self.connection_label.configure(text="SYSTEM: STARTING")
        self._append_command("Sent START command.\n")

    def stop_framework(self):
        self.command_queue.put({"type": "command", "command": "STOP"})
        self.connection_label.configure(text="SYSTEM: STOPPING")
        self._append_command("Sent STOP command.\n")

    def _format_depth_regions(self, regions):
        if not regions:
            return "Depth regions: --"
        lines = []
        for name in ("left", "center", "right"):
            vals = regions.get(name)
            if vals is None:
                continue
            try:
                med, min_d, free = vals
                lines.append("  {0:<6} median={1:>5.2f}m  min={2:>5.2f}m  free={3:>4.2f}".format(name, med, min_d, free))
            except Exception:
                lines.append("  {0:<6} {1}".format(name, vals))
        return "Depth regions:\n" + "\n".join(lines)

    def _update_command_panel(self, payload):
        tracking = payload.get("tracking_info", {}) or {}
        text = []
        text.append("R.A.V.E.N. REMOTE LIVE STATUS")
        text.append("-" * 30)
        text.append("Client thermal detections : {0}".format(payload.get("client_detection_count", 0)))
        text.append("Client RGB detections     : {0}".format(payload.get("client_rgb_detection_count", 0)))
        text.append("Server thermal lock       : {0}".format(payload.get("thermal_lock", 0)))
        text.append("")
        text.append("Depth/Avoidance")
        text.append("  Status    : {0}".format(payload.get("avoid_status", "UNKNOWN")))
        text.append("  Direction : {0}".format(payload.get("avoid_direction", "UNKNOWN")))
        text.append(self._format_depth_regions(payload.get("depth_regions", {})))
        text.append("")
        text.append("Mount/Tracking")
        text.append("  Mode      : {0}".format(tracking.get("mode", "UNKNOWN")))
        text.append("  Pan       : {0:.1f} us".format(float(payload.get("pan", 0.0))))
        text.append("  Tilt      : {0:.1f} us".format(float(payload.get("tilt", 0.0))))
        text.append("  Mirrored  : {0}".format(int(tracking.get("mirrored", False))))
        text.append("  Err X/Y   : {0}, {1}".format(int(tracking.get("err_x", 0)), int(tracking.get("err_y", 0))))
        text.append("  Velocity  : pan={0:.1f}, tilt={1:.1f}".format(float(tracking.get("servo_pan_vel", 0.0)), float(tracking.get("servo_tilt_vel", 0.0))))
        text.append("  Missed    : {0}".format(tracking.get("missed_frames", 0)))
        text.append("")
        text.append("Server FPS estimate: {0:.1f}".format(float(payload.get("fps", 0.0))))
        self.command_text.configure(state="normal")
        self.command_text.delete("1.0", "end")
        self.command_text.insert("end", "\n".join(text))
        self.command_text.configure(state="disabled")

    def _poll_queue(self):
        try:
            while True:
                payload = self.gui_queue.get_nowait()
                event = payload.get("event")
                if event == "frame":
                    self.connection_label.configure(text="SYSTEM: ONLINE")
                    self.start_btn.configure(state="normal")
                    self.stop_btn.configure(state="normal")
                    self.fps_label.configure(text="FPS: {0:.1f}".format(float(payload.get("fps", 0.0))))

                    thermal_view = payload.get("thermal_view")
                    rgb_view = payload.get("rgb_view")
                    depth_view = payload.get("depth_view")
                    if thermal_view is not None:
                        self.thermal_photo = cv2_to_tk_photo(thermal_view, THERMAL_GUI_W, THERMAL_GUI_H)
                        self.thermal_canvas.configure(image=self.thermal_photo)
                    if rgb_view is not None:
                        self.rgb_photo = cv2_to_tk_photo(rgb_view, RGB_GUI_W, RGB_GUI_H)
                        self.rgb_canvas.configure(image=self.rgb_photo)
                    if depth_view is not None:
                        self.depth_photo = cv2_to_tk_photo(depth_view, DEPTH_GUI_W, DEPTH_GUI_H)
                        self.depth_canvas.configure(image=self.depth_photo)
                    self._update_command_panel(payload)

                elif event == "status":
                    self.connection_label.configure(text="SYSTEM: CONNECTED")
                    self.start_btn.configure(state="normal")
                    self.stop_btn.configure(state="normal")
                    self._append_command(payload.get("message", "Status") + "\n")
                elif event == "error":
                    self.connection_label.configure(text="SYSTEM: ERROR")
                    self.connect_btn.configure(state="normal")
                    self.start_btn.configure(state="disabled")
                    self.stop_btn.configure(state="disabled")
                    self._append_command("\nERROR:\n" + payload.get("message", "Unknown error") + "\n")
                    if payload.get("traceback"):
                        self._append_command(payload.get("traceback") + "\n")
                    messagebox.showerror("R.A.V.E.N. Error", payload.get("message", "Unknown error"))
                elif event == "stopped":
                    self.connection_label.configure(text="SYSTEM: DISCONNECTED")
                    self.connect_btn.configure(state="normal")
                    self.start_btn.configure(state="disabled")
                    self.stop_btn.configure(state="disabled")
                    self.fps_label.configure(text="FPS: --")
                    self._append_command("\n" + payload.get("message", "Disconnected") + "\n")
                    self.worker = None
        except queue.Empty:
            pass
        finally:
            self.after(40, self._poll_queue)

    def on_close(self):
        try:
            if self.worker is not None:
                self.command_queue.put({"type": "command", "command": "STOP"})
                self.command_queue.put({"type": "command", "command": "SHUTDOWN"})
                self.stop_event.set()
                time.sleep(0.2)
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    app = RavenGroundClient()
    app.mainloop()
