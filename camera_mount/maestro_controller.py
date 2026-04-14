# maestro_controller.py

import time
import serial

from maestro_config import (
    COM_PORT,
    BAUD_RATE,
    PAN_CHANNEL,
    TILT_CHANNEL,
    PAN_MIN,
    PAN_MAX,
    TILT_MIN,
    TILT_MAX,
    PAN_CENTER,
    TILT_CENTER,
    PAN_HOME,
    TILT_HOME,
    DEFAULT_STEP_DELAY,
    DEFAULT_MOVE_STEP_US,
)


class MaestroController:
    def __init__(self, port: str = COM_PORT, baud_rate: int = BAUD_RATE, timeout: float = 1.0):
        self.ser = serial.Serial(port, baud_rate, timeout=timeout)
        time.sleep(0.2)

        self.current_pan = PAN_CENTER
        self.current_tilt = TILT_CENTER

    def close(self) -> None:
        if hasattr(self, "ser") and self.ser and self.ser.is_open:
            self.ser.close()

    @staticmethod
    def clamp(value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def set_target_us(self, channel: int, target_us: float) -> None:
        """
        Send target in microseconds.
        Maestro compact protocol expects quarter-microseconds.
        """
        target_quarter_us = int(round(target_us * 4))

        command = bytearray([
            0x84,
            channel,
            target_quarter_us & 0x7F,
            (target_quarter_us >> 7) & 0x7F
        ])
        self.ser.write(command)

    def set_pan(self, target_us: float) -> None:
        target_us = self.clamp(target_us, PAN_MIN, PAN_MAX)
        self.set_target_us(PAN_CHANNEL, target_us)
        self.current_pan = target_us

    def set_tilt(self, target_us: float) -> None:
        target_us = self.clamp(target_us, TILT_MIN, TILT_MAX)
        self.set_target_us(TILT_CHANNEL, target_us)
        self.current_tilt = target_us

    def set_pan_tilt(self, pan_us: float, tilt_us: float) -> None:
        self.set_pan(pan_us)
        self.set_tilt(tilt_us)

    def go_home(self) -> None:
        self.set_pan_tilt(PAN_HOME, TILT_HOME)

    def go_center(self) -> None:
        self.set_pan_tilt(PAN_CENTER, TILT_CENTER)

    def move_smooth(
        self,
        target_pan: float | None = None,
        target_tilt: float | None = None,
        step_us: float = DEFAULT_MOVE_STEP_US,
        delay_s: float = DEFAULT_STEP_DELAY,
    ) -> None:
        """
        Smoothly move pan and/or tilt to target positions.
        """
        if target_pan is None:
            target_pan = self.current_pan
        if target_tilt is None:
            target_tilt = self.current_tilt

        target_pan = self.clamp(target_pan, PAN_MIN, PAN_MAX)
        target_tilt = self.clamp(target_tilt, TILT_MIN, TILT_MAX)

        while True:
            done_pan = abs(self.current_pan - target_pan) <= step_us
            done_tilt = abs(self.current_tilt - target_tilt) <= step_us

            if done_pan and done_tilt:
                break

            if not done_pan:
                if target_pan > self.current_pan:
                    self.current_pan = min(self.current_pan + step_us, target_pan)
                else:
                    self.current_pan = max(self.current_pan - step_us, target_pan)

            if not done_tilt:
                if target_tilt > self.current_tilt:
                    self.current_tilt = min(self.current_tilt + step_us, target_tilt)
                else:
                    self.current_tilt = max(self.current_tilt - step_us, target_tilt)

            self.set_pan_tilt(self.current_pan, self.current_tilt)
            time.sleep(delay_s)

        self.set_pan_tilt(target_pan, target_tilt)

    def scan_pan(
        self,
        left_us: float,
        right_us: float,
        tilt_us: float | None = None,
        step_us: float = 10.0,
        delay_s: float = 0.01,
        cycles: int = 1,
    ) -> None:
        """
        Sweep pan left/right while optionally holding tilt fixed.
        """
        left_us = self.clamp(left_us, PAN_MIN, PAN_MAX)
        right_us = self.clamp(right_us, PAN_MIN, PAN_MAX)

        if tilt_us is None:
            tilt_us = self.current_tilt
        tilt_us = self.clamp(tilt_us, TILT_MIN, TILT_MAX)

        self.set_tilt(tilt_us)

        for _ in range(cycles):
            pos = left_us
            while pos <= right_us:
                self.set_pan(pos)
                self.set_tilt(tilt_us)
                time.sleep(delay_s)
                pos += step_us

            pos = right_us
            while pos >= left_us:
                self.set_pan(pos)
                self.set_tilt(tilt_us)
                time.sleep(delay_s)
                pos -= step_us