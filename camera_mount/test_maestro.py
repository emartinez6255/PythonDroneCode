# test_maestro.py

import time
from maestro_controller import MaestroController
from maestro_config import PAN_HOME, TILT_HOME, PAN_MIN, PAN_MAX, TILT_MIN, TILT_MAX

def clamp(value: float, min_value: float, max_value: float) -> float:
    return(max(min_value,min(max_value, value)))

def raster_scan(
        maestro: MaestroController,
        pan_left: float,
        pan_right: float,
        tilt_top: float,
        tilt_bottom: float,
        tilt_step: float =  120.0,
        pan_step: float = 12.0,
        delay_s: float = 0.01,
        cycles: int = 1,
) -> None:
    pan_left = clamp(pan_left, PAN_MIN, PAN_MAX)
    pan_right = clamp(pan_right, PAN_MIN, PAN_MAX)
    tilt_top = clamp(tilt_top, TILT_MIN, TILT_MAX)
    tilt_bottom = clamp(tilt_bottom, TILT_MIN, TILT_MAX)

    if tilt_top > tilt_bottom:
        tilt_top, tilt_bottom = tilt_bottom, tilt_top

    for _ in range (cycles):
        current_tilt = tilt_top
        move_left_to_right = True

        while current_tilt <= tilt_bottom:
            maestro.set_tilt(current_tilt)
            time.sleep(0.05)
            
            if move_left_to_right:
                pan = pan_left
                while pan <= pan_right:
                    maestro.set_pan_tilt(pan, current_tilt)
                    time.sleep(delay_s)
                    pan+= pan_step
            else:
                pan = pan_right
                while pan >= pan_left:
                    maestro.set_pan_tilt(pan, current_tilt)
                    time.sleep(delay_s)
                    pan -= pan_step

            current_tilt += tilt_step
            move_left_to_right = not move_left_to_right


def main() -> None:
    maestro = MaestroController()

    try:
        print("Going to center...")
        maestro.go_center()
        time.sleep(2)

        print("Going to home...")
        maestro.go_home()
        time.sleep(2)

        print("Small pan test...")
        maestro.move_smooth(target_pan=1200, target_tilt=TILT_HOME)
        time.sleep(1)
        maestro.move_smooth(target_pan=1800, target_tilt=TILT_HOME)
        time.sleep(1)
        maestro.move_smooth(target_pan=PAN_HOME, target_tilt=TILT_HOME)
        time.sleep(1)

        print("Small tilt test...")
        maestro.move_smooth(target_pan=PAN_HOME, target_tilt=1000)
        time.sleep(1)
        maestro.move_smooth(target_pan=PAN_HOME, target_tilt=2000)
        time.sleep(1)
        maestro.move_smooth(target_pan=PAN_HOME, target_tilt=TILT_HOME)
        time.sleep(1)

        print("Running raster scan...")
        raster_scan(
            maestro=maestro,
            pan_left = 496,
            pan_right=2496,
            tilt_top=496,
            tilt_bottom=2496,
            tilt_step=140,
            pan_step=12,
            delay_s=0.01,
            cycles=4
        )

       
        print("Returning home...")
        maestro.move_smooth(target_pan=PAN_HOME, target_tilt=TILT_HOME)
        time.sleep(1)

        print("Done.")

    finally:
        maestro.close()


if __name__ == "__main__":
    main()