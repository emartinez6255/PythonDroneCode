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
    def __init__(self, port=COM_PORT, baud_rate=BAUD_RATE, timeout=1.0):
        self.ser = serial.Serial(port, baud_rate, timeout=timeout)
        time.sleep(0.2)
        self.current_pan = PAN_CENTER
        self.current_tilt = TILT_CENTER

    def close(self):
        if hasattr(self, 'ser') and self.ser and self.ser.is_open:
            self.ser.close()

    @staticmethod
    def clamp(value, min_value, max_value):
        return max(min_value, min(max_value, value))

    def set_target_us(self, channel, target_us):
        target_quarter_us = int(round(target_us * 4))
        command = bytearray([
            0x84,
            channel,
            target_quarter_us & 0x7F,
            (target_quarter_us >> 7) & 0x7F
        ])
        self.ser.write(command)

    def set_pan(self, target_us):
        target_us = self.clamp(target_us, PAN_MIN, PAN_MAX)
        self.set_target_us(PAN_CHANNEL, target_us)
        self.current_pan = target_us

    def set_tilt(self, target_us):
        target_us = self.clamp(target_us, TILT_MIN, TILT_MAX)
        self.set_target_us(TILT_CHANNEL, target_us)
        self.current_tilt = target_us

    def set_pan_tilt(self, pan_us, tilt_us):
        self.set_pan(pan_us)
        self.set_tilt(tilt_us)

    def go_home(self):
        self.set_pan_tilt(PAN_HOME, TILT_HOME)

    def go_center(self):
        self.set_pan_tilt(PAN_CENTER, TILT_CENTER)

    def move_smooth(self, target_pan=None, target_tilt=None, step_us=DEFAULT_MOVE_STEP_US, delay_s=DEFAULT_STEP_DELAY):
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
