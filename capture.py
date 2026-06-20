import cv2
import os
import time
from typing import Tuple

import state

if not os.path.exists("picture"):
    os.makedirs("picture")

def save_capture():

    if state.current_frame is None:
        return

    x, y = state.point[0], state.point[1]

    frame = state.current_frame.copy()

    filename = f"picture/{x}_{y}_{int(time.time())}.jpg"

    cv2.imwrite(filename, frame)

    print("캡쳐:", filename)
