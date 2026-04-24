"""
R.A.V.E.N. Drone Server - Python 3.6 compatible

Run this on the drone/Jetson side, or on your laptop for localhost testing.

This file keeps the existing framework logic on the drone/server side:
- Thermal camera capture
- RealSense RGB/depth capture
- Depth avoidance
- Maestro pan/tilt control
- tracker.py mount/360 mirror logic

The ground PC receives camera frames, runs thermal YOLO detection, and sends
thermal detections back to this server. The server then uses those detections
with the SAME tracker.py logic to move the mount.

Local test:
    python drone_server_py36.py

Ground GUI should connect to:
    127.0.0.1 : 5055
"""

import socket
import struct
import pickle
import threading
import time
import traceback

import cv2
import numpy as np

from config import (
    ENABLE_MAESTRO,
    ENABLE_SCAN_WHEN_LOST,
    DRAW_THERMAL,
    THERMAL_DETECT_EVERY_N_FRAMES,
    DEPTH_UPDATE_EVERY_N_FRAMES,
    PRINT_STATUS_EVERY_N_FRAMES,
)
from cam_module import ThermalCamera
from camera_mod import RealSenseCamera
from avoidance import check_distance


# -------------------------------------------------
# NETWORK SETTINGS
# -------------------------------------------------
HOST = "0.0.0.0"
PORT = 5055
JPEG_QUALITY = 95
MAX_MESSAGE_SIZE = 25 * 1024 * 1024

# Your current tested hardware behavior:
# False = correct thermal feed orientation when mount is hanging.
USE_HANGING_MOUNT_REFERENCE = False

# Server-side display/frame tuning
THERMAL_STREAM_W = None
THERMAL_STREAM_H = None
RGB_STREAM_W = 424
RGB_STREAM_H = 240
DEPTH_STREAM_W = 424
DEPTH_STREAM_H = 120

# If the ground PC is running detection, this can stay 1.
SERVER_SEND_EVERY_N_FRAMES = 1


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
    payload = pickle.dumps(obj, protocol=2)  # protocol 2 is Python 3.6 safe
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


# -------------------------------------------------
# IMAGE HELPERS
# -------------------------------------------------
def encode_jpg(frame, width=None, height=None, quality=JPEG_QUALITY):
    if frame is None:
        return None
    if width is not None and height is not None:
        frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        return None
    return buf.tobytes()


def encode_png(frame, width=None, height=None):
    if frame is None:
        return None
    if width is not None and height is not None:
        frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_NEAREST)
    ok, buf = cv2.imencode(".png", frame)
    if not ok:
        return None
    return buf.tobytes()


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
    if tracker.is_mirrored():
        frame = cv2.rotate(frame, cv2.ROTATE_180)
    return frame


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


# -------------------------------------------------
# DRONE SERVER STATE
# -------------------------------------------------
class SharedState(object):
    def __init__(self):
        self.lock = threading.Lock()
        self.running_requested = False
        self.shutdown_requested = False
        self.latest_thermal_detections = []
        self.latest_detection_seq = -1
        self.last_command = "IDLE"

    def set_running(self, value):
        with self.lock:
            self.running_requested = bool(value)

    def get_running(self):
        with self.lock:
            return self.running_requested

    def request_shutdown(self):
        with self.lock:
            self.shutdown_requested = True
            self.running_requested = False

    def get_shutdown(self):
        with self.lock:
            return self.shutdown_requested

    def update_detections(self, seq, detections):
        with self.lock:
            self.latest_detection_seq = int(seq)
            self.latest_thermal_detections = detections or []

    def get_detections(self):
        with self.lock:
            return list(self.latest_thermal_detections), self.latest_detection_seq


def command_receiver(sock, state):
    try:
        while not state.get_shutdown():
            msg = recv_message(sock)
            if msg is None:
                state.request_shutdown()
                break
            msg_type = msg.get("type")
            if msg_type == "command":
                cmd = msg.get("command", "").upper()
                if cmd == "START":
                    state.set_running(True)
                elif cmd == "STOP":
                    state.set_running(False)
                elif cmd == "SHUTDOWN":
                    state.request_shutdown()
                    break
            elif msg_type == "thermal_detections":
                state.update_detections(msg.get("seq", -1), msg.get("detections", []))
    except Exception:
        state.request_shutdown()


# -------------------------------------------------
# FRAMEWORK LOOP
# -------------------------------------------------
def run_framework_loop(sock, send_lock, state):
    thermal_cam = None
    rs_cam = None
    maestro = None

    try:
        send_message(sock, send_lock, {
            "type": "server_status",
            "running": False,
            "message": "Drone server connected. Send START to launch framework."
        })

        while not state.get_shutdown():
            if not state.get_running():
                time.sleep(0.05)
                continue

            try:
                thermal_cam = ThermalCamera()
                rs_cam = RealSenseCamera()
                maestro = build_maestro()

                from tracker import ThermalTargetTracker
                tracker = ThermalTargetTracker(maestro)

                tracker.go_home()
                time.sleep(1.0)
                tracker.reset_raster_scan()

                send_message(sock, send_lock, {
                    "type": "server_status",
                    "running": True,
                    "message": "Drone framework started."
                })

                thermal_counter = 0
                depth_counter = 0
                loop_count = 0
                seq = 0
                status = "UNKNOWN"
                direction = "UNKNOWN"
                depth_regions = {}
                depth_view = None
                start_time = time.time()
                tracking_info = {}

                while state.get_running() and not state.get_shutdown():
                    loop_count += 1
                    thermal_counter += 1
                    depth_counter += 1

                    thermal_raw, ok_t = thermal_cam.get_frame()
                    color_image, depth_image, depth_frame, ok_rs = rs_cam.get_frame()

                    if not ok_t or not ok_rs:
                        time.sleep(0.01)
                        continue

                    thermal_tracking_frame = get_tracking_frame(thermal_raw, tracker)

                    if depth_counter >= DEPTH_UPDATE_EVERY_N_FRAMES:
                        depth_counter = 0
                        depth_regions, status, direction = check_distance(depth_frame, depth_image)
                        depth_view = draw_depth(depth_image, status, direction)

                    thermal_dets, det_seq = state.get_detections()

                    # Update mount/tracker using detections produced on the ground PC.
                    chosen_target = tracker.update_lock(thermal_dets, thermal_tracking_frame.shape)
                    if chosen_target is not None:
                        tracking_info = tracker.update_tracking(chosen_target, thermal_tracking_frame.shape)
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

                    if loop_count % SERVER_SEND_EVERY_N_FRAMES == 0:
                        # Send the SAME native thermal_tracking_frame that the old local
                        # 3.12 framework gave to ThermalHumanDetector.detect(). Do not
                        # resize or normalize it here. The ground PC runs the old
                        # preprocessing/detection path, then sends detections back in
                        # this same coordinate system for tracker.py.
                        thermal_jpg = encode_png(thermal_tracking_frame, THERMAL_STREAM_W, THERMAL_STREAM_H)
                        rgb_jpg = encode_jpg(color_image, RGB_STREAM_W, RGB_STREAM_H, JPEG_QUALITY)
                        depth_jpg = encode_jpg(depth_view, DEPTH_STREAM_W, DEPTH_STREAM_H, JPEG_QUALITY)

                        elapsed = max(0.001, time.time() - start_time)
                        fps = loop_count / elapsed

                        send_message(sock, send_lock, {
                            "type": "frame",
                            "seq": seq,
                            "running": True,
                            "thermal_jpg": thermal_jpg,
                            "thermal_shape": tuple(thermal_tracking_frame.shape[:2]),
                            "rgb_jpg": rgb_jpg,
                            "depth_jpg": depth_jpg,
                            "thermal_count": len(thermal_dets),
                            "thermal_lock": 1 if chosen_target is not None else 0,
                            "rgb_count": 0,
                            "avoid_status": status,
                            "avoid_direction": direction,
                            "depth_regions": depth_regions,
                            "tracking_info": dict(tracking_info),
                            "pan": float(getattr(maestro, "current_pan", 0.0)),
                            "tilt": float(getattr(maestro, "current_tilt", 0.0)),
                            "fps": fps,
                            "detection_seq_used": det_seq,
                        })
                        seq += 1

                    if loop_count % PRINT_STATUS_EVERY_N_FRAMES == 0:
                        print("thermal_dets={0} avoid={1}/{2} mode={3} pan={4:.1f} tilt={5:.1f} mirrored={6}".format(
                            len(thermal_dets),
                            status,
                            direction,
                            tracking_info.get("mode", "UNKNOWN"),
                            getattr(maestro, "current_pan", 0.0),
                            getattr(maestro, "current_tilt", 0.0),
                            int(tracking_info.get("mirrored", False))
                        ))

                send_message(sock, send_lock, {
                    "type": "server_status",
                    "running": False,
                    "message": "Drone framework stopped."
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
                thermal_cam = None
                rs_cam = None
                maestro = None

    except Exception as exc:
        try:
            send_message(sock, send_lock, {
                "type": "server_error",
                "running": False,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            })
        except Exception:
            pass


def main():
    print("R.A.V.E.N. Drone Server starting on {0}:{1}".format(HOST, PORT))
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)

    try:
        while True:
            print("Waiting for ground PC connection...")
            client, addr = server.accept()
            print("Ground PC connected from {0}".format(addr))

            state = SharedState()
            send_lock = threading.Lock()
            rx_thread = threading.Thread(target=command_receiver, args=(client, state))
            rx_thread.daemon = True
            rx_thread.start()

            run_framework_loop(client, send_lock, state)

            try:
                client.close()
            except Exception:
                pass
            print("Ground PC disconnected.")

    finally:
        try:
            server.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
