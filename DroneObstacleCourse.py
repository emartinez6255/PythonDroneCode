# ============================================================
# Quanser QLabs – Plane + QDrone2 + Obstacle Course Setup Script
# Integrated with QLabs Basic Shapes
# ============================================================

# region: imports
import os
import sys
import time
import subprocess
import numpy as np

from qvl.qlabs import QuanserInteractiveLabs
from qvl.free_camera import QLabsFreeCamera
from qvl.real_time import QLabsRealTime
from qvl.qdrone2 import QLabsQDrone2
from qvl.person import QLabsPerson
from qvl.basic_shape import QLabsBasicShape
import pal.resources.rtmodels as rtmodels
# endregion


# ------------------------------------------------------------
# Path to QLabs executable
# ------------------------------------------------------------
QLABS_EXE = r"C:\Program Files\Quanser\Quanser Interactive Labs\Quanser Interactive Labs.exe"


# ------------------------------------------------------------
# Connect to existing QLabs OR launch it if needed
# ------------------------------------------------------------
def connect_or_launch_qlabs():
    qlabs = QuanserInteractiveLabs()

    print("Attempting to connect to existing QLabs.")
    if qlabs.open("localhost"):
        print("Connected to existing QLabs instance")
        return qlabs

    print("No running QLabs detected. Launching QLabs with Plane.")
    subprocess.Popen([
        QLABS_EXE,
        "-loadmodule",
        "Plane"
    ])

    # Allow QLabs to fully initialize
    time.sleep(6)

    print("Re-attempting connection.")
    if not qlabs.open("localhost"):
        print("Unable to connect to QLabs after launch")
        sys.exit()

    print("Connected to newly launched QLabs")
    return qlabs


# ------------------------------------------------------------
# Helper: spawn one colored basic shape
# ------------------------------------------------------------
def spawn_shape(shape_obj, actor_num, location, rotation, scale, configuration, color):
    status = shape_obj.spawn_id_degrees(
        actorNumber=actor_num,
        location=location,
        rotation=rotation,
        scale=scale,
        configuration=configuration,
        waitForConfirmation=True
    )

    if status != 0:
        print(f"Warning: failed to spawn actor {actor_num}, status = {status}")
        return

    shape_obj.actorNumber = actor_num
    shape_obj.set_material_properties(
        color=color,
        roughness=0.4,
        metallic=False,
        waitForConfirmation=True
    )


# ------------------------------------------------------------
# Build obstacle course
# ------------------------------------------------------------
def build_obstacle_course(qlabs):
    print("Building obstacle course...")

    shape = QLabsBasicShape(qlabs)

    # Use high actor numbers so they don't conflict with QDrone actor 0
    actor_id = 100

    # -------------------------
    # Start pad
    # -------------------------
    spawn_shape(
        shape_obj=shape,
        actor_num=actor_id,
        location=[0.0, -10.0, 0.05],
        rotation=[0, 0, 0],
        scale=[3.0, 3.0, 0.1],
        configuration=QLabsBasicShape.SHAPE_CUBE,
        color=[0.0, 0.8, 0.0]
    )
    actor_id += 1

    # -------------------------
    # Slalom section
    # -------------------------
    slalom_positions = [
        [2.0, -8.0, 0.75],
        [4.5, -11.0, 0.75],
        [7.0, -8.0, 0.75],
        [9.5, -11.0, 0.75],
        [12.0, -8.0, 0.75],
        [14.5, -11.0, 0.75],
    ]

    for pos in slalom_positions:
        spawn_shape(
            shape_obj=shape,
            actor_num=actor_id,
            location=pos,
            rotation=[0, 0, 0],
            scale=[0.6, 0.6, 1.5],
            configuration=QLabsBasicShape.SHAPE_CYLINDER,
            color=[1.0, 0.85, 0.0]
        )
        actor_id += 1

    # -------------------------
    # Narrow corridor
    # -------------------------
    corridor_x = [18, 20, 22, 24, 26, 28]
    for x in corridor_x:
        # left wall
        spawn_shape(
            shape_obj=shape,
            actor_num=actor_id,
            location=[x, -7.0, 1.0],
            rotation=[0, 0, 0],
            scale=[0.5, 0.5, 2.0],
            configuration=QLabsBasicShape.SHAPE_CUBE,
            color=[0.1, 0.2, 1.0]
        )
        actor_id += 1

        # right wall
        spawn_shape(
            shape_obj=shape,
            actor_num=actor_id,
            location=[x, -12.0, 1.0],
            rotation=[0, 0, 0],
            scale=[0.5, 0.5, 2.0],
            configuration=QLabsBasicShape.SHAPE_CUBE,
            color=[0.1, 0.2, 1.0]
        )
        actor_id += 1

    # -------------------------
    # Box maze section
    # -------------------------
    maze_blocks = [
        [32.0, -9.5, 1.0],
        [34.0, -11.5, 1.0],
        [36.0, -9.5, 1.0],
        [38.0, -11.5, 1.0],
    ]

    for pos in maze_blocks:
        spawn_shape(
            shape_obj=shape,
            actor_num=actor_id,
            location=pos,
            rotation=[0, 0, 0],
            scale=[1.2, 1.2, 2.0],
            configuration=QLabsBasicShape.SHAPE_CUBE,
            color=[1.0, 0.4, 0.0]
        )
        actor_id += 1

    # -------------------------
    # Final wall with gap
    # -------------------------
    # left segment
    spawn_shape(
        shape_obj=shape,
        actor_num=actor_id,
        location=[43.0, -8.0, 1.2],
        rotation=[0, 0, 0],
        scale=[0.4, 4.0, 2.4],
        configuration=QLabsBasicShape.SHAPE_CUBE,
        color=[0.9, 0.0, 0.0]
    )
    actor_id += 1

    # right segment
    spawn_shape(
        shape_obj=shape,
        actor_num=actor_id,
        location=[43.0, -13.5, 1.2],
        rotation=[0, 0, 0],
        scale=[0.4, 4.0, 2.4],
        configuration=QLabsBasicShape.SHAPE_CUBE,
        color=[0.9, 0.0, 0.0]
    )
    actor_id += 1

    # -------------------------
    # Finish pad
    # -------------------------
    spawn_shape(
        shape_obj=shape,
        actor_num=actor_id,
        location=[48.0, -10.0, 0.05],
        rotation=[0, 0, 0],
        scale=[3.0, 3.0, 0.1],
        configuration=QLabsBasicShape.SHAPE_CUBE,
        color=[0.0, 0.8, 0.0]
    )

    print("Obstacle course created.")


def setup(
    initialPosition=[0, -10, 1.0],
    initialOrientation=[0, 0, 0],
):
    os.system("cls")

    # --------------------------------------------------------
    # Connect or launch QLabs
    # --------------------------------------------------------
    qlabs = connect_or_launch_qlabs()

    # --------------------------------------------------------
    # Clean previous actors and models
    # --------------------------------------------------------
    qlabs.destroy_all_spawned_actors()
    QLabsRealTime().terminate_all_real_time_models()
    time.sleep(0.5)

    # --------------------------------------------------------
    # Spawn QDrone2
    # --------------------------------------------------------
    print("Spawning QDrone2.")
    hQDrone = QLabsQDrone2(qlabs, True)
    hQDrone.actorNumber = 0

    hQDrone.spawn_id_degrees(
        actorNumber=0,
        location=initialPosition,
        rotation=initialOrientation,
        scale=[1, 1, 1],
        configuration=0
    )

    hQDrone.possess(hQDrone.VIEWPOINT_TRAILING)

    x = hQDrone.ping()
    print("Ping response:", x)

    # -------------------------------------------------------
    # Spawn People
    # -------------------------------------------------------
    print("Spawning people.")
    NUMPEOPLE = 5
    hpeople = []

    for i in range(NUMPEOPLE):
        hpeople.append(QLabsPerson(qlabs))

    hpeople[0].spawn(
        location=[-2.269, 1.616, 1],
        rotation=[0, 0, np.pi / 2],
        scale=[1, 1, 1],
        configuration=6
    )

    hpeople[1].spawn(
        location=[-3.4, 14.95, 1],
        rotation=[0, 0, 0],
        scale=[1, 1, 1],
        configuration=7
    )

    hpeople[2].spawn(
        location=[5.08, 0.378, 1],
        rotation=[0, 0, 3 * np.pi / 2],
        scale=[1, 1, 1],
        configuration=8
    )

    hpeople[3].spawn(
        location=[-8.341, 6.133, 1],
        rotation=[0, 0, np.pi],
        scale=[1, 1, 1],
        configuration=9
    )

    hpeople[0].move_to(
        location=[-0.597, -7.389, 1],
        speed=hpeople[0].WALK,
        waitForConfirmation=True
    )

    hpeople[1].move_to(
        location=[9.09, 13.967, 1],
        speed=hpeople[1].WALK,
        waitForConfirmation=True
    )

    hpeople[2].move_to(
        location=[6.351, -5.006, 1],
        speed=hpeople[2].WALK,
        waitForConfirmation=True
    )

    hpeople[3].move_to(
        location=[-12.591, -1.731, 1],
        speed=hpeople[3].WALK,
        waitForConfirmation=True
    )

    # --------------------------------------------------------
    # Build obstacle course
    # --------------------------------------------------------
    build_obstacle_course(qlabs)

    # --------------------------------------------------------
    # Spawn Free Camera
    # --------------------------------------------------------
    print("Spawning free camera.")
    hcamera = QLabsFreeCamera(qlabs)
    hcamera.spawn(
        [15.0, -2.0, 8.0],
        [0.0, 0.45, 2.35]
    )

    print("Plane + QDrone2 + obstacle course scene updated.")

    # --------------------------------------------------------
    # Start RT model and print path
    # --------------------------------------------------------
    rtmodel_path = rtmodels.QDRONE2
    print("RT model path:", rtmodel_path)

    QLabsRealTime().start_real_time_model(
        modelName=rtmodel_path,
        actorNumber=0
    )

    print("RT model started.")


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------
if __name__ == "__main__":
    setup()
