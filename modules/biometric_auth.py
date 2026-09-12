"""
biometric_auth.py - Autenticación Biométrica para AP0LO
Basado en Avinashb722/jarvis-ai-assistant
Soporta: Reconocimiento facial y huella digital (Android via ADB)
"""

import os
import cv2
import numpy as np
import subprocess
from pathlib import Path

# ============================================================
# RECONOCIMIENTO FACIAL
# ============================================================
class FaceAuthenticator:
    def __init__(self, model_path="models/face_model.xml"):
        self.model_path = model_path
        self.face_cascade = None
        self.recognizer = None
        self._load_models()

    def _load_models(self):
        try:
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            # Para reconocimiento avanzado, se necesita entrenar un modelo
            # Aquí usamos una versión simplificada
            print("[FaceAuth] ✅ Modelo facial cargado")
        except Exception as e:
            print(f"[FaceAuth] ⚠️ Error cargando modelo: {e}")

    def detect_faces(self, image_path):
        """Detecta rostros en una imagen"""
        if not self.face_cascade:
            return []
        
        img = cv2.imread(image_path)
        if img is None:
            return []
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
        return faces

    def capture_face(self, output_path="face_capture.jpg"):
        """Captura un rostro desde la cámara"""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return False, "No se pudo abrir la cámara"
        
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            return False, "No se pudo capturar imagen"
        
        faces = self.detect_faces_from_frame(frame)
        if len(faces) == 0:
            return False, "No se detectó ningún rostro"
        
        cv2.imwrite(output_path, frame)
        return True, f"Rostro capturado en {output_path}"

    def detect_faces_from_frame(self, frame):
        if not self.face_cascade:
            return []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return self.face_cascade.detectMultiScale(gray, 1.1, 4)

# ============================================================
# AUTENTICACIÓN POR HUELLA DIGITAL (Android via ADB)
# ============================================================
class FingerprintAuthenticator:
    def __init__(self, device_id=None):
        self.device_id = device_id
        self._check_adb()

    def _check_adb(self):
        """Verifica que ADB esté disponible"""
        try:
            result = subprocess.run(["adb", "version"], capture_output=True, text=True)
            if result.returncode != 0:
                print("[Fingerprint] ⚠️ ADB no encontrado. Instala Android SDK Platform-Tools")
                return False
            print("[Fingerprint] ✅ ADB disponible")
            return True
        except FileNotFoundError:
            print("[Fingerprint] ⚠️ ADB no encontrado")
            return False

    def get_devices(self):
        """Lista dispositivos Android conectados"""
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')[1:]
            devices = []
            for line in lines:
                if line.strip() and 'device' in line:
                    device_id = line.split()[0]
                    devices.append(device_id)
            return devices
        except Exception as e:
            print(f"[Fingerprint] Error: {e}")
            return []

    def send_command(self, command):
        """Envía un comando ADB al dispositivo"""
        if not self.device_id:
            devices = self.get_devices()
            if not devices:
                return None, "No hay dispositivos Android conectados"
            self.device_id = devices[0]
        
        try:
            cmd = ["adb", "-s", self.device_id] + command.split()
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout, result.stderr
        except Exception as e:
            return None, str(e)

# ============================================================
# EJEMPLO DE USO
# ============================================================
if __name__ == "__main__":
    # Face Authentication
    face_auth = FaceAuthenticator()
    success, msg = face_auth.capture_face()
    print(f"Face capture: {msg}")
    
    # Fingerprint Authentication
    fp_auth = FingerprintAuthenticator()
    devices = fp_auth.get_devices()
    print(f"Dispositivos Android: {devices}")