import random
import cv2
import threading
import time

class VisionManager:
    def __init__(self):
        self.camera_active = False
        self.emotion = "neutral"
        self.use_deepface = False
        try:
            from deepface import DeepFace
            self.use_deepface = True
            self.deepface_model = DeepFace
        except ImportError:
            print("[Visión] DeepFace no disponible, usando simulación.")

    def start_camera(self):
        if not self.camera_active:
            self.camera_active = True
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()

    def _capture_loop(self):
        cap = cv2.VideoCapture(0)
        while self.camera_active:
            ret, frame = cap.read()
            if ret:
                if self.use_deepface:
                    try:
                        analysis = self.deepface_model.analyze(frame, actions=['emotion'], enforce_detection=False)
                        self.emotion = analysis[0]['dominant_emotion']
                    except:
                        pass
                else:
                    if int(time.time()) % 5 == 0:
                        self.emotion = random.choice(["happy", "sad", "neutral", "angry", "surprise"])
            time.sleep(1)
        cap.release()

    def get_emotion(self):
        return self.emotion

    def stop(self):
        self.camera_active = False
