# ============================================================
# Quanser QLabs – Plane + QDrone2 Setup Script
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

    print("Attempting to connect to existing QLabs...")
    if qlabs.open("localhost"):
        print("Connected to existing QLabs instance")
        return qlabs

    print("No running QLabs detected. Launching QLabs with Plane...")
    subprocess.Popen([
        QLABS_EXE,
        "-loadmodule",
        "Plane"
    ])

    # Allow QLabs to fully initialize
    time.sleep(6)

    print("Re-attempting connection...")
    if not qlabs.open("localhost"):
        print("Unable to connect to QLabs after launch")
        sys.exit()

    print("Connected to newly launched QLabs")
    return qlabs


def setup(
    initialPosition=[0, 0, 0],
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
    print("Spawning QDrone2...")
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
    print("Spawning people...")
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
    # Spawn Free Camera
    # --------------------------------------------------------
    print("Spawning free camera...")
    hcamera = QLabsFreeCamera(qlabs)
    hcamera.spawn(
        [1.325, 9.5, 0],
        [0, 0.748, 0.792]
    )

    print("Plane + QDrone2 scene updated.")

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