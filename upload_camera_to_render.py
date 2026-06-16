import time
import requests

RENDER_UPLOAD_URL = "https://iot-traffic-light-system.onrender.com/api/upload_camera"
CAMERA_TOKEN = "demo_camera_token"
LOCAL_CAMERA_URL = "http://127.0.0.1:5000/api/local_camera_frame"

while True:
    try:
        frame_response = requests.get(
            LOCAL_CAMERA_URL,
            timeout=5
        )

        if frame_response.status_code == 200:

            files = {
                "image": (
                    "latest_camera.jpg",
                    frame_response.content,
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
                timeout=10
            )

            print(
                "Upload:",
                upload_response.status_code
            )

        else:
            print(
                "Local camera error:",
                frame_response.status_code
            )

    except Exception as e:
        print("Upload error:", e)

    time.sleep(0.5)
