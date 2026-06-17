import time
import threading

try:
    from picamera2 import Picamera2
    import cv2
    HAS_CAMERA = True
except ImportError:
    print("Picamera2/OpenCV not found. Running camera in MOCK mode.")
    HAS_CAMERA = False


class CameraStream:
    def __init__(self):
        self.frame = None
        self.thread = None
        self.running = False
        self.lock = threading.Lock()

    def start(self):
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        print("Camera snapshot thread started.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _capture_loop(self):
        if HAS_CAMERA:
            try:
                picam2 = Picamera2()

                config = picam2.create_video_configuration(
                    main={"size": (1280, 720), "format": "XRGB8888"}
                )

                picam2.configure(config)

                picam2.set_controls({
                    "AwbEnable": True,
                    "AeEnable": True
                })

                picam2.start()
                time.sleep(3)

                while self.running:
                    frame_array = picam2.capture_array()

                    # XRGB8888 usually gives 4 channels, convert to normal BGR
                    frame_array = cv2.cvtColor(frame_array, cv2.COLOR_BGRA2BGR)

                    # Output 16:9 supaya dashboard tak nampak zoom/crop sangat
                    frame_array = cv2.resize(frame_array, (640, 360))

                    ret, buffer = cv2.imencode(
                        ".jpg",
                        frame_array,
                        [cv2.IMWRITE_JPEG_QUALITY, 65]
                    )

                    if ret:
                        with self.lock:
                            self.frame = buffer.tobytes()

                    time.sleep(2.0)

                picam2.stop()

            except Exception as e:
                print(f"Camera error: {e}")
                self.running = False

        else:
            try:
                with open("static/placeholder_feed.jpg", "rb") as f:
                    self.frame = f.read()
            except FileNotFoundError:
                self.frame = b""

            while self.running:
                time.sleep(2.0)

    def get_frame(self):
        with self.lock:
            return self.frame


camera_stream = CameraStream()


def generate_frames():
    while True:
        frame = camera_stream.get_frame()

        if frame:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )

        time.sleep(2.0)
