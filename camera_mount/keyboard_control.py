import time
import msvcrt

from maestro_controller import MaestroController
from maestro_config import (
    PAN_MIN,
    PAN_MAX,
    TILT_MIN,
    TILT_MAX,
    PAN_HOME,
    TILT_HOME,
)

PAN_STEP = 100.0
TILT_STEP = 100.0
LOOP_DELAY = 0.01


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def main() -> None:
    maestro = MaestroController()

    pan = PAN_HOME
    tilt = TILT_HOME

    try:
        maestro.set_pan_tilt(pan, tilt)
        time.sleep(0.5)

        print("Arrow-key control started.")
        print("Controls:")
        print("  Up Arrow    -> tilt up")
        print("  Down Arrow  -> tilt down")
        print("  Left Arrow  -> pan left")
        print("  Right Arrow -> pan right")
        print("  H           -> go home")
        print("  C           -> go center")
        print("  Q           -> quit")
        print("Click the terminal window first so it captures keys.\n")

        while True:
            if msvcrt.kbhit():
                key = msvcrt.getch()

                # Arrow keys come as two bytes on Windows:
                # first b'\\xe0' or b'\\x00', then actual code
                if key in (b'\x00', b'\xe0'):
                    key2 = msvcrt.getch()

                    # Up
                    if key2 == b'H':
                        tilt -= TILT_STEP

                    # Down
                    elif key2 == b'P':
                        tilt += TILT_STEP

                    # Left
                    elif key2 == b'K':
                        pan -= PAN_STEP

                    # Right
                    elif key2 == b'M':
                        pan += PAN_STEP

                    pan = clamp(pan, PAN_MIN, PAN_MAX)
                    tilt = clamp(tilt, TILT_MIN, TILT_MAX)

                    maestro.set_pan_tilt(pan, tilt)
                    print(f"Pan: {pan:.2f} | Tilt: {tilt:.2f}")

                else:
                    # Regular keys
                    try:
                        ch = key.decode("utf-8").lower()
                    except UnicodeDecodeError:
                        ch = ""

                    if ch == "h":
                        pan = PAN_HOME
                        tilt = TILT_HOME
                        maestro.set_pan_tilt(pan, tilt)
                        print(f"HOME -> Pan: {pan:.2f} | Tilt: {tilt:.2f}")

                    elif ch == "c":
                        pan = 1500.0
                        tilt = 1500.0
                        maestro.set_pan_tilt(pan, tilt)
                        print(f"CENTER -> Pan: {pan:.2f} | Tilt: {tilt:.2f}")

                    elif ch == "q":
                        print("Quitting...")
                        break

            time.sleep(LOOP_DELAY)

    finally:
        maestro.close()


if __name__ == "__main__":
    main()