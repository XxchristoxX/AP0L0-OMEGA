import cv2
import numpy as np
from pathlib import Path

class ObjectDetector:
    def __init__(self):
        self.model = None
        try:
            from ultralytics import YOLO
            self.model = YOLO('yolov8n.pt')  # modelo ligero
            print("[ObjectDetector] YOLO cargado.")
        except ImportError:
            print("[ObjectDetector] ultralytics no instalado. Usando OpenCV DNN (menos preciso).")
            self.model = None

    def detect_objects(self, image_path: str) -> str:
        if not Path(image_path).exists():
            return f"Imagen no encontrada: {image_path}"
        img = cv2.imread(image_path)
        if img is None:
            return "No se pudo leer la imagen"
        if self.model:
            results = self.model(img)
            detected = []
            for r in results:
                for box in r.boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    name = self.model.names[cls]
                    detected.append(f"{name} ({conf:.2f})")
            if not detected:
                return "No se detectaron objetos."
            return f"Objetos detectados: " + ", ".join(detected[:10])
        else:
            # Fallback: usar Haar cascade para rostros (simple)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            if len(faces) > 0:
                return f"Detectados {len(faces)} rostro(s)."
            return "No se detectaron objetos (instala ultralytics para mejor detección)."

    def detect_in_video(self, video_path: str, interval: int = 30) -> str:
        if not Path(video_path).exists():
            return f"Vídeo no encontrado: {video_path}"
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            return "No se pudo leer el vídeo."
        frame_count = 0
        results = []
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if frame_count % int(fps * interval) == 0:
                temp_path = f"temp_frame_{frame_count}.jpg"
                cv2.imwrite(temp_path, frame)
                res = self.detect_objects(temp_path)
                results.append(f"Frame {frame_count//fps:.0f}s: {res}")
                Path(temp_path).unlink(missing_ok=True)
            frame_count += 1
        cap.release()
        return "\n".join(results) if results else "No se procesaron frames."