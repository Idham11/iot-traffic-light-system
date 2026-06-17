import time
import requests
import cv2
import numpy as np

RENDER_UPLOAD_URL = "https://iot-traffic-light-system.onrender.com/api/upload_camera"
CAMERA_TOKEN = "demo_camera_token"
LOCAL_CAMERA_URL = "http://127.0.0.1:5000/api/local_camera_frame"

UPLOAD_INTERVAL = 2.0


def fix_blue_color(image_bytes):
    """
    Convert received JPG bytes into image, swap BGR/RGB color,
    then encode back to JPG.
    """
    np_arr = np.frombuffer(image_bytes, np.uint8)

    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if frame is None:
        return image_bytes

    # Try fix blue/weird color issue
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    success, buffer = cv2.imencode(".jpg", frame)

    if not success:
        return image_bytes

    return buffer.tobytes()


while True:
    try:
        frame_response = requests.get(
            LOCAL_CAMERA_URL,
            timeout=5
        )

        if frame_response.status_code == 200:
            fixed_image = fix_blue_color(frame_response.content)

            files = {
                "image": (
                    "latest_camera.jpg",
                    fixed_image,
                    "image/jpeg"
                )
            }

            headers = {
                "X-Camera-Token": CAMERA_TOKEN
            }

            upload_response = requests.post(
                RENDER_UPLOAD_URL,
                files=files,
                headers=headers,
                timeout=20
            )

            print("Upload:", upload_response.status_code)

        else:
            print("Local camera error:", frame_response.status_code)

    except Exception as e:
        print("Upload error:", e)

    time.sleep(UPLOAD_INTERVAL)
