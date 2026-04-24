import time
import math

from maestro_config import (
    PAN_MIN,
    PAN_MAX,
    TILT_MIN,
    TILT_MAX,
    PAN_HOME,
    TILT_HOME,
    PAN_CENTER,
    TILT_CENTER,
)
from config import (
    TRACK_DEADBAND_X_PX,
    TRACK_DEADBAND_Y_PX,
)


def clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))


def opposite_limit(value, min_value, max_value):
    midpoint = (min_value + max_value) / 2.0

    if abs(value - min_value) < 1e-6:
        return max_value
    if abs(value - max_value) < 1e-6:
        return min_value

    return max_value if value <= midpoint else min_value


class ThermalTargetTracker(object):
    def __init__(self, maestro):
        self.maestro = maestro
        self.filtered_pan = float(getattr(maestro, "current_pan", PAN_HOME))
        self.filtered_tilt = float(getattr(maestro, "current_tilt", TILT_HOME))
        # Continuous velocity controller.
        # Velocities are servo microseconds/second instead of one-frame step sizes.
        self.pan_velocity_us = 0.0
        self.tilt_velocity_us = 0.0
        self.last_control_time = time.time()

        # Pan direction correction for the final camera orientation.
        # This does NOT change servo limits or the 360 mirror behavior.
        # It only changes how image-space left/right error drives pan velocity.
        # If pan ever tracks backward again, change this to +1.0.
        self.pan_direction_sign = -1.0

        self.pan_accel_gain = 48.0
        self.tilt_accel_gain = 38.0
        self.velocity_friction = 0.91
        self.inner_box_friction = 0.80
        self.lost_target_friction = 0.58
        self.max_pan_velocity_us = 1050.0
        self.max_tilt_velocity_us = 760.0
        self.edge_max_pan_velocity_us = 620.0
        self.edge_max_tilt_velocity_us = 450.0
        self.pan_velocity_gain = 0.90
        self.tilt_velocity_gain = 0.72
        self.inner_box_w_ratio = 0.22
        self.inner_box_h_ratio = 0.26
        self.verify_box_w_ratio = 0.78
        self.verify_box_h_ratio = 0.82
        self.edge_wrap_zone_ratio = 0.18
        self.locked_target = None
        self.locked_center = None
        self.locked_box = None
        self.locked_conf = 0.0
        self.locked_area = 0.0
        self.prev_locked_center = None
        self.center_velocity = (0.0, 0.0)
        self.missed_frames = 0
        # Prevent instant search when YOLO drops a few frames.
        # At 9 FPS, 22 frames is roughly 2.4 seconds.
        self.lock_hold_after_loss_frames = 22
        self.lock_stale = False
        self.reacquire_radius_px = 155.0
        self.post_wrap_reacquire_radius_px = 190.0
        self.small_target_area_ratio = 0.012
        self.medium_target_area_ratio = 0.040
        self.tiny_target_hold_ratio = 0.006
        self.scan_pan_left = 496.0
        self.scan_pan_right = 2496.0
        self.scan_tilt_top = 496.0
        self.scan_tilt_bottom = 2496.0
        self.scan_tilt_step = 140.0
        self.scan_pan_step = 12.0
        self.scan_delay_s = 0.01
        self.scan_current_pan = self.scan_pan_left
        self.scan_current_tilt = self.scan_tilt_top
        self.scan_move_left_to_right = True
        self.last_scan_time = 0.0
        self.verification_delay_s = 1.15
        self.verify_active = False
        self.verify_start_time = 0.0
        self.verify_candidate = None
        self.mirrored_mode = False
        self.wrap_cooldown_s = 0.45
        self.last_wrap_time = 0.0
        self.post_wrap_reacquire_s = 1.15
        self.post_wrap_reacquire_until = 0.0
        self.wrap_residual_pan = 0.0
        self.wrap_guard_active = False
        self.wrap_landed_side = None
        self.wrap_guard_start_time = 0.0
        self.wrap_guard_min_hold_s = 1.10
        self.wrap_guard_force_release_s = 4.00
        self.wrap_guard_release_margin_us = 320.0
        self.wrap_edge_hold_margin_us = 90.0
        self.wrap_overshoot_confirm_us = 260.0
        self.wrap_blocked_frames = 0

    def go_center(self):
        self.filtered_pan = float(PAN_CENTER)
        self.filtered_tilt = float(TILT_CENTER)
        self.pan_velocity_us = 0.0
        self.tilt_velocity_us = 0.0
        self.maestro.set_pan_tilt(self.filtered_pan, self.filtered_tilt)

    def go_home(self):
        self.filtered_pan = float(PAN_HOME)
        self.filtered_tilt = float(TILT_HOME)
        self.pan_velocity_us = 0.0
        self.tilt_velocity_us = 0.0
        self.maestro.set_pan_tilt(self.filtered_pan, self.filtered_tilt)

    def reset_raster_scan(self):
        self.scan_current_pan = self.scan_pan_left
        self.scan_current_tilt = self.scan_tilt_top
        self.scan_move_left_to_right = True
        self.last_scan_time = 0.0

    def clear_lock(self):
        self.locked_target = None
        self.locked_center = None
        self.locked_box = None
        self.locked_conf = 0.0
        self.locked_area = 0.0
        self.prev_locked_center = None
        self.center_velocity = (0.0, 0.0)
        self.missed_frames = 0
        self.lock_stale = False
        self.pan_velocity_us *= 0.25
        self.tilt_velocity_us *= 0.25
        self.wrap_residual_pan = 0.0

    def clear_verification(self):
        self.verify_active = False
        self.verify_start_time = 0.0
        self.verify_candidate = None

    def is_verifying(self):
        return self.verify_active

    def is_mirrored(self):
        return self.mirrored_mode

    def _rect_from_ratio(self, frame_shape, w_ratio, h_ratio):
        frame_h, frame_w = frame_shape[:2]
        bw = int(round(frame_w * w_ratio))
        bh = int(round(frame_h * h_ratio))
        x1 = int((frame_w - bw) / 2)
        y1 = int((frame_h - bh) / 2)
        x2 = x1 + bw
        y2 = y1 + bh
        return (x1, y1, x2, y2)

    def _inner_box(self, frame_shape):
        return self._rect_from_ratio(frame_shape, self.inner_box_w_ratio, self.inner_box_h_ratio)

    def _verify_box(self, frame_shape):
        return self._rect_from_ratio(frame_shape, self.verify_box_w_ratio, self.verify_box_h_ratio)

    def _point_in_rect(self, point, rect):
        x, y = point
        x1, y1, x2, y2 = rect
        return x1 <= x <= x2 and y1 <= y <= y2

    def _boundary_error(self, point, rect):
        x, y = point
        x1, y1, x2, y2 = rect
        err_x = 0
        err_y = 0
        if x < x1:
            err_x = x - x1
        elif x > x2:
            err_x = x - x2
        if y < y1:
            err_y = y - y1
        elif y > y2:
            err_y = y - y2
        return err_x, err_y

    def _edge_zone(self, point, frame_shape):
        frame_h, frame_w = frame_shape[:2]
        margin = int(round(frame_w * self.edge_wrap_zone_ratio))
        if point[0] <= margin:
            return "left"
        if point[0] >= frame_w - margin:
            return "right"
        return None

    def verification_status(self):
        remaining = 0.0
        if self.verify_active:
            remaining = max(0.0, self.verification_delay_s - (time.time() - self.verify_start_time))
        return {"err_x": 0, "err_y": 0, "pan_us": self.filtered_pan, "tilt_us": self.filtered_tilt, "mode": "VERIFY", "missed_frames": self.missed_frames, "verify_remaining_s": remaining, "mirrored": self.mirrored_mode}

    def _can_wrap_now(self):
        return (time.time() - self.last_wrap_time) >= self.wrap_cooldown_s

    def _is_post_wrap_reacquire_active(self):
        return time.time() <= self.post_wrap_reacquire_until

    def _arm_post_wrap_reacquire(self):
        self.post_wrap_reacquire_until = time.time() + self.post_wrap_reacquire_s

    def _update_wrap_guard_release(self):
        if not self.wrap_guard_active:
            return
        held_s = time.time() - self.wrap_guard_start_time
        if held_s < self.wrap_guard_min_hold_s:
            return
        if self.wrap_landed_side == "min" and self.filtered_pan > (PAN_MIN + self.wrap_guard_release_margin_us):
            self.wrap_guard_active = False
            self.wrap_landed_side = None
            self.wrap_blocked_frames = 0
            return
        if self.wrap_landed_side == "max" and self.filtered_pan < (PAN_MAX - self.wrap_guard_release_margin_us):
            self.wrap_guard_active = False
            self.wrap_landed_side = None
            self.wrap_blocked_frames = 0
            return
        if held_s >= self.wrap_guard_force_release_s:
            self.wrap_guard_active = False
            self.wrap_landed_side = None
            self.wrap_blocked_frames = 0

    def _is_wrap_blocked_by_guard(self, wrapped_to_right, candidate_pan):
        self._update_wrap_guard_release()
        if not self.wrap_guard_active:
            return False
        if self.wrap_landed_side == "min" and wrapped_to_right is False:
            return (PAN_MIN - candidate_pan) < self.wrap_overshoot_confirm_us
        if self.wrap_landed_side == "max" and wrapped_to_right is True:
            return (candidate_pan - PAN_MAX) < self.wrap_overshoot_confirm_us
        return False

    def _rotate_center_180(self, center, frame_shape):
        frame_h, frame_w = frame_shape[:2]
        cx, cy = center
        return (frame_w - 1 - cx, frame_h - 1 - cy)

    def _rotate_box_180(self, box, frame_shape):
        frame_h, frame_w = frame_shape[:2]
        x1, y1, x2, y2 = box
        return (frame_w - 1 - x2, frame_h - 1 - y2, frame_w - 1 - x1, frame_h - 1 - y1)

    def _rotate_lock_for_mirror(self, frame_shape):
        if frame_shape is None:
            return
        if self.locked_center is not None:
            self.locked_center = self._rotate_center_180(self.locked_center, frame_shape)
        if self.prev_locked_center is not None:
            self.prev_locked_center = self._rotate_center_180(self.prev_locked_center, frame_shape)
        if self.locked_box is not None:
            self.locked_box = self._rotate_box_180(self.locked_box, frame_shape)
        if self.locked_target is not None:
            self.locked_target = dict(self.locked_target)
            if "center" in self.locked_target:
                self.locked_target["center"] = self._rotate_center_180(self.locked_target["center"], frame_shape)
            if "box" in self.locked_target:
                self.locked_target["box"] = self._rotate_box_180(self.locked_target["box"], frame_shape)
        vx, vy = self.center_velocity
        self.center_velocity = (-vx, -vy)

    def _do_wrap(self, wrapped_to_right, residual_pan=0.0, frame_shape=None):
        new_pan = PAN_MIN if wrapped_to_right else PAN_MAX
        new_tilt = opposite_limit(self.filtered_tilt, TILT_MIN, TILT_MAX)

        self.filtered_pan = float(clamp(new_pan, PAN_MIN, PAN_MAX))
        self.filtered_tilt = float(clamp(new_tilt, TILT_MIN, TILT_MAX))

        carry = max(180.0, min(abs(self.pan_velocity_us), 360.0))
        self.pan_velocity_us = carry if wrapped_to_right else -carry
        self.tilt_velocity_us *= 0.12

        self.maestro.set_pan_tilt(self.filtered_pan, self.filtered_tilt)

        self.mirrored_mode = not self.mirrored_mode
        self.last_wrap_time = time.time()
        self.last_control_time = self.last_wrap_time
        self.wrap_residual_pan = float(residual_pan) * 0.15

        self.wrap_guard_active = True
        self.wrap_landed_side = "min" if wrapped_to_right else "max"
        self.wrap_guard_start_time = self.last_wrap_time
        self.wrap_blocked_frames = 0

        self._rotate_lock_for_mirror(frame_shape)
        self.clear_verification()
        self._arm_post_wrap_reacquire()

        return {
            "err_x": 0,
            "err_y": 0,
            "pan_us": self.filtered_pan,
            "tilt_us": self.filtered_tilt,
            "mode": "MIRROR_FLIP_HARD_LIMIT",
            "missed_frames": self.missed_frames,
            "servo_pan_vel": self.pan_velocity_us,
            "servo_tilt_vel": self.tilt_velocity_us,
            "mirrored": self.mirrored_mode,
            "wrap_guard": self.wrap_guard_active,
            "wrap_landed_side": self.wrap_landed_side,
        }

    def _map_scan_pose(self, pan_us, tilt_us):
        pan_us = clamp(pan_us, PAN_MIN, PAN_MAX)
        tilt_us = clamp(tilt_us, TILT_MIN, TILT_MAX)
        if not self.mirrored_mode:
            return pan_us, tilt_us
        mirrored_pan = (PAN_MIN + PAN_MAX) - pan_us
        mirrored_tilt = opposite_limit(tilt_us, TILT_MIN, TILT_MAX)
        return clamp(mirrored_pan, PAN_MIN, PAN_MAX), clamp(mirrored_tilt, TILT_MIN, TILT_MAX)

    def _center_distance(self, c1, c2):
        dx = float(c1[0] - c2[0])
        dy = float(c1[1] - c2[1])
        return math.sqrt(dx * dx + dy * dy)

    def _box_area(self, box):
        x1, y1, x2, y2 = box
        return float(max(0, x2 - x1) * max(0, y2 - y1))

    def _box_iou(self, box_a, box_b):
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        inter = float(iw * ih)
        union = max(1.0, self._box_area(box_a) + self._box_area(box_b) - inter)
        return inter / union

    def _choose_acquire_target(self, detections, frame_shape):
        if not detections:
            return None
        verify_box = self._verify_box(frame_shape)
        frame_h, frame_w = frame_shape[:2]
        frame_center = (frame_w // 2, frame_h // 2)
        candidates = []
        for d in detections:
            center = d.get("center", frame_center)
            if not self._point_in_rect(center, verify_box):
                continue
            area = d.get("area", self._box_area(d["box"]))
            conf = d.get("conf", 0.0)
            dist = self._center_distance(center, frame_center)
            score = (-1.00 * area) - (180.0 * conf) + (0.20 * dist)
            candidates.append((score, -area, -conf, dist, d))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        return candidates[0][4]

    def _choose_locked_target(self, detections):
        if not detections or self.locked_center is None or self.locked_box is None:
            return None
        predicted_center = self.locked_center
        if self.prev_locked_center is not None:
            predicted_center = (int(round(self.locked_center[0] + self.center_velocity[0] * self.pan_velocity_gain)), int(round(self.locked_center[1] + self.center_velocity[1] * self.tilt_velocity_gain)))
        candidates = []
        radius = self.post_wrap_reacquire_radius_px if self._is_post_wrap_reacquire_active() else self.reacquire_radius_px
        for d in detections:
            center = d.get("center", None)
            box = d.get("box", None)
            if center is None or box is None:
                continue
            dist = self._center_distance(center, predicted_center)
            if dist > radius:
                continue
            area = d.get("area", self._box_area(box))
            conf = d.get("conf", 0.0)
            iou = self._box_iou(box, self.locked_box)
            area_change = abs(area - self.locked_area) / max(1.0, self.locked_area)
            score = (1.15 * dist) - (420.0 * iou) + (90.0 * area_change) - (0.018 * area) - (12.0 * conf)
            candidates.append((score, dist, -iou, area_change, -area, d))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4]))
        return candidates[0][5]

    def update_lock(self, detections, frame_shape):
        if self.locked_center is not None:
            if detections:
                matched = self._choose_locked_target(detections)
                if matched is not None:
                    new_center = matched["center"]
                    self.prev_locked_center = self.locked_center
                    self.center_velocity = (float(new_center[0] - self.locked_center[0]), float(new_center[1] - self.locked_center[1]))
                    self.locked_target = dict(matched)
                    self.locked_center = new_center
                    self.locked_box = matched["box"]
                    self.locked_conf = matched.get("conf", 0.0)
                    self.locked_area = matched.get("area", self._box_area(matched["box"]))
                    self.missed_frames = 0
                    self.lock_stale = False
                    self.clear_verification()
                    return self.locked_target
            self.missed_frames += 1
            if self.missed_frames <= self.lock_hold_after_loss_frames and self.locked_target is not None:
                self.lock_stale = True
                self.clear_verification()
                return self.locked_target
            self.clear_lock()
            self.clear_verification()
            return None
        if not detections:
            self.clear_verification()
            return None
        candidate = self._choose_acquire_target(detections, frame_shape)
        if candidate is None:
            self.clear_verification()
            return None
        if self._is_post_wrap_reacquire_active():
            matched = dict(candidate)
            self.clear_verification()
            self.post_wrap_reacquire_until = 0.0
        else:
            if not self.verify_active:
                self.verify_active = True
                self.verify_start_time = time.time()
                self.verify_candidate = dict(candidate)
                return None
            prev_center = self.verify_candidate.get("center", candidate["center"])
            prev_area = self.verify_candidate.get("area", self._box_area(self.verify_candidate["box"]))
            new_area = candidate.get("area", self._box_area(candidate["box"]))
            if self._center_distance(prev_center, candidate.get("center", prev_center)) > 65.0 or abs(new_area - prev_area) / max(1.0, prev_area) > 0.65:
                self.verify_start_time = time.time()
            self.verify_candidate = dict(candidate)
            if (time.time() - self.verify_start_time) < self.verification_delay_s:
                return None
            matched = self.verify_candidate
            self.clear_verification()
        self.locked_target = dict(matched)
        self.lock_stale = False
        self.locked_center = matched["center"]
        self.locked_box = matched["box"]
        self.locked_conf = matched.get("conf", 0.0)
        self.locked_area = matched.get("area", self._box_area(matched["box"]))
        self.prev_locked_center = self.locked_center
        self.center_velocity = (0.0, 0.0)
        self.missed_frames = 0
        return self.locked_target

    def _target_size_ratio(self, target, frame_shape):
        frame_h, frame_w = frame_shape[:2]
        return float(target.get("area", self._box_area(target["box"]))) / float(max(1, frame_h * frame_w))

    def _clamp_velocity(self, value, max_value):
        return clamp(value, -max_value, max_value)

    def _control_dt(self):
        now = time.time()
        dt = now - self.last_control_time
        self.last_control_time = now
        return clamp(dt, 0.015, 0.140)

    def _hold_lost_target(self, frame_shape):
        dt = self._control_dt()
        self.pan_velocity_us *= self.lost_target_friction
        self.tilt_velocity_us *= self.lost_target_friction
        if abs(self.pan_velocity_us) < 6.0:
            self.pan_velocity_us = 0.0
        if abs(self.tilt_velocity_us) < 6.0:
            self.tilt_velocity_us = 0.0
        self.filtered_pan = clamp(self.filtered_pan + self.pan_velocity_us * dt, PAN_MIN, PAN_MAX)
        self.filtered_tilt = clamp(self.filtered_tilt + self.tilt_velocity_us * dt, TILT_MIN, TILT_MAX)
        self.maestro.set_pan_tilt(self.filtered_pan, self.filtered_tilt)
        return {
            "err_x": 0,
            "err_y": 0,
            "pan_us": self.filtered_pan,
            "tilt_us": self.filtered_tilt,
            "mode": "LOST_HOLD_REACQUIRE",
            "target_conf": 0.0,
            "target_area": self.locked_area,
            "target_area_ratio": 0.0,
            "missed_frames": self.missed_frames,
            "servo_pan_vel": self.pan_velocity_us,
            "servo_tilt_vel": self.tilt_velocity_us,
            "mirrored": self.mirrored_mode,
            "wrap_guard": self.wrap_guard_active,
            "wrap_landed_side": self.wrap_landed_side,
            "inner_box": self._inner_box(frame_shape),
            "verify_box": self._verify_box(frame_shape),
        }

    def update_tracking(self, target, frame_shape):
        if self.lock_stale:
            return self._hold_lost_target(frame_shape)

        dt = self._control_dt()
        x1, y1, x2, y2 = target["box"]
        cx = int((x1 + x2) / 2)
        cy = int(y1 + 0.38 * (y2 - y1))
        inner_box = self._inner_box(frame_shape)
        verify_box = self._verify_box(frame_shape)
        vx, vy = self.center_velocity
        pred_cx = cx + int(round(vx * self.pan_velocity_gain))
        pred_cy = cy + int(round(vy * self.tilt_velocity_gain))
        err_x, err_y = self._boundary_error((pred_cx, pred_cy), inner_box)
        edge_zone = self._edge_zone((cx, cy), frame_shape)
        area_ratio = self._target_size_ratio(target, frame_shape)

        # FOV / clipping guard. When the box is cut by the camera edge,
        # the measured vertical center is unreliable and can cause tilt twitching.
        frame_h, frame_w = frame_shape[:2]
        clip_margin_x = 3
        clip_margin_y = 3
        clipped_left = x1 <= clip_margin_x
        clipped_right = x2 >= (frame_w - 1 - clip_margin_x)
        clipped_top = y1 <= clip_margin_y
        clipped_bottom = y2 >= (frame_h - 1 - clip_margin_y)
        vertically_clipped = clipped_top or clipped_bottom
        horizontally_clipped = clipped_left or clipped_right

        # Do not chase a clipped top/bottom edge as if it were the person's true center.
        if clipped_bottom and err_y > 0:
            err_y = 0
        elif clipped_top and err_y < 0:
            err_y = 0

        gain_scale = 1.0
        max_pan_vel = self.max_pan_velocity_us
        max_tilt_vel = self.max_tilt_velocity_us
        if area_ratio < self.tiny_target_hold_ratio:
            gain_scale = 0.55
            max_pan_vel *= 0.60
            max_tilt_vel *= 0.55
        elif area_ratio < self.small_target_area_ratio:
            gain_scale = 0.76
            max_pan_vel *= 0.78
            max_tilt_vel *= 0.72
        elif area_ratio < self.medium_target_area_ratio:
            gain_scale = 0.92
            max_pan_vel *= 0.92
            max_tilt_vel *= 0.88
        if edge_zone is not None or self.wrap_guard_active:
            max_pan_vel = min(max_pan_vel, self.edge_max_pan_velocity_us)
            max_tilt_vel = min(max_tilt_vel, self.edge_max_tilt_velocity_us)

        # Extra damping when the target is clipped by the camera FOV.
        # Pan can still track; tilt is made conservative because the vertical
        # center is not trustworthy while clipped.
        if vertically_clipped:
            max_tilt_vel = min(max_tilt_vel, 210.0)
            self.tilt_velocity_us *= 0.42

        if horizontally_clipped:
            max_pan_vel = min(max_pan_vel, 520.0)

        # Continuous velocity movement. Outside the inner box it accelerates;
        # inside the inner box it decays smoothly instead of stopping instantly.
        if err_x == 0:
            self.pan_velocity_us *= self.inner_box_friction
        else:
            effective_err_x = self.pan_direction_sign * err_x
            self.pan_velocity_us = (self.pan_velocity_us * self.velocity_friction) + (effective_err_x * self.pan_accel_gain * gain_scale * dt)
        if err_y == 0:
            self.tilt_velocity_us *= self.inner_box_friction
        else:
            effective_err_y = -err_y if self.mirrored_mode else err_y
            self.tilt_velocity_us = (self.tilt_velocity_us * self.velocity_friction) + (effective_err_y * self.tilt_accel_gain * gain_scale * dt)

        self.pan_velocity_us = self._clamp_velocity(self.pan_velocity_us, max_pan_vel)
        self.tilt_velocity_us = self._clamp_velocity(self.tilt_velocity_us, max_tilt_vel)
        candidate_pan = self.filtered_pan + self.pan_velocity_us * dt
        candidate_tilt = self.filtered_tilt + self.tilt_velocity_us * dt

        self._update_wrap_guard_release()

        # Hard 360 mimic: if the servo command crosses a physical limit,
        # flip immediately. Do not require the target to be inside an edge box.
        # Return immediately so candidate_tilt cannot overwrite the tilt flip.
        if candidate_pan > PAN_MAX:
            if self._can_wrap_now() and not self._is_wrap_blocked_by_guard(True, candidate_pan):
                residual = min(candidate_pan - PAN_MAX, 90.0)
                return self._do_wrap(
                    wrapped_to_right=True,
                    residual_pan=residual,
                    frame_shape=frame_shape
                )
            self.wrap_blocked_frames += 1
            candidate_pan = PAN_MAX - self.wrap_edge_hold_margin_us
            self.pan_velocity_us = 0.0

        elif candidate_pan < PAN_MIN:
            if self._can_wrap_now() and not self._is_wrap_blocked_by_guard(False, candidate_pan):
                residual = max(candidate_pan - PAN_MIN, -90.0)
                return self._do_wrap(
                    wrapped_to_right=False,
                    residual_pan=residual,
                    frame_shape=frame_shape
                )
            self.wrap_blocked_frames += 1
            candidate_pan = PAN_MIN + self.wrap_edge_hold_margin_us
            self.pan_velocity_us = 0.0

        self.filtered_pan = clamp(candidate_pan, PAN_MIN, PAN_MAX)
        self.filtered_tilt = clamp(candidate_tilt, TILT_MIN, TILT_MAX)
        self.maestro.set_pan_tilt(self.filtered_pan, self.filtered_tilt)
        return {
            "err_x": err_x,
            "err_y": err_y,
            "pan_us": self.filtered_pan,
            "tilt_us": self.filtered_tilt,
            "mode": "TRACK_CONTINUOUS_BOUNDARY",
            "target_conf": target.get("conf", 0.0),
            "target_area": target.get("area", 0.0),
            "target_area_ratio": area_ratio,
            "missed_frames": self.missed_frames,
            "vel_x": vx,
            "vel_y": vy,
            "servo_pan_vel": self.pan_velocity_us,
            "servo_tilt_vel": self.tilt_velocity_us,
            "mirrored": self.mirrored_mode,
            "wrap_guard": self.wrap_guard_active,
            "wrap_landed_side": self.wrap_landed_side,
            "wrap_blocked_frames": self.wrap_blocked_frames,
            "inner_box": inner_box,
            "verify_box": verify_box,
            "edge_zone": edge_zone,
            "clip_left": clipped_left,
            "clip_right": clipped_right,
            "clip_top": clipped_top,
            "clip_bottom": clipped_bottom,
            "vertical_clip_guard": vertically_clipped,
            "dt": dt,
        }

    def search_step(self):
        now = time.time()
        if self.verify_active:
            return self.verification_status()
        if (now - self.last_scan_time) < self.scan_delay_s:
            return {"err_x": 0, "err_y": 0, "pan_us": self.filtered_pan, "tilt_us": self.filtered_tilt, "mode": "SEARCH_WAIT", "scan_row_tilt": self.filtered_tilt, "mirrored": self.mirrored_mode}
        self.last_scan_time = now
        servo_pan, servo_tilt = self._map_scan_pose(self.scan_current_pan, self.scan_current_tilt)
        self.filtered_pan = clamp(servo_pan, PAN_MIN, PAN_MAX)
        self.filtered_tilt = clamp(servo_tilt, TILT_MIN, TILT_MAX)
        self.pan_velocity_us = 0.0
        self.tilt_velocity_us = 0.0
        self.maestro.set_pan_tilt(self.filtered_pan, self.filtered_tilt)
        if self.scan_move_left_to_right:
            self.scan_current_pan += self.scan_pan_step
            if self.scan_current_pan > self.scan_pan_right:
                self.scan_current_pan = self.scan_pan_right
                self.scan_current_tilt += self.scan_tilt_step
                self.scan_move_left_to_right = False
        else:
            self.scan_current_pan -= self.scan_pan_step
            if self.scan_current_pan < self.scan_pan_left:
                self.scan_current_pan = self.scan_pan_left
                self.scan_current_tilt += self.scan_tilt_step
                self.scan_move_left_to_right = True
        if self.scan_current_tilt > self.scan_tilt_bottom:
            self.scan_current_tilt = self.scan_tilt_top
            self.scan_move_left_to_right = True
            self.scan_current_pan = self.scan_pan_left
        return {"err_x": 0, "err_y": 0, "pan_us": self.filtered_pan, "tilt_us": self.filtered_tilt, "mode": "SEARCH", "scan_row_tilt": self.filtered_tilt, "mirrored": self.mirrored_mode}
