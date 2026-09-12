# src/ui/camera_handler.py
import threading
import json
import time
try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    _CV2_AVAILABLE = False
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

# ===== IMPORTAR CONSTANTE DE SISTEMA =====
from src.utils.system_utils import IS_WINDOWS
from src.config.settings import API_FILE

class CameraHandler:
    def __init__(self, main_window):
        self.main = main_window
        self._cam_stop = threading.Event()
        self._cam_thread = None
        self._previous_gray = None
        self._last_motion_log = 0.0

    def start_stream(self):
        """Inicia la cámara en un hilo separado."""
        if not _CV2_AVAILABLE:
            print("[Camera] OpenCV no está instalado; cámara desactivada.")
            return
        self._cam_stop.clear()
        self.main._cam_stream_sig.emit(True)
        self._cam_thread = threading.Thread(target=self._cam_loop, daemon=True, name="cam-stream")
        self._cam_thread.start()

    def _cam_loop(self):
        """Bucle de captura de OpenCV en hilo separado."""
        try:
            cam_idx = 0
            try:
                with open(API_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    cam_idx = int(cfg.get("camera_index", 0))
            except Exception:
                pass
            # ===== USAR LA CONSTANTE IMPORTADA =====
            backend = cv2.CAP_DSHOW if IS_WINDOWS else cv2.CAP_ANY
            cap = cv2.VideoCapture(cam_idx, backend)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return
            for _ in range(5):
                cap.read()
            while not self._cam_stop.wait(0.033) and cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    # Detección ligera de movimiento por diferencia entre
                    # frames. No reemplaza visión semántica, pero permite
                    # activar el flujo de análisis cuando hay movimiento.
                    try:
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        gray = cv2.resize(gray, (320, 240))
                        if self._previous_gray is not None:
                            delta = cv2.absdiff(self._previous_gray, gray)
                            changed = cv2.countNonZero(cv2.threshold(delta, 22, 255, cv2.THRESH_BINARY)[1])
                            ratio = changed / float(gray.size)
                            now = time.monotonic()
                            if ratio > 0.045 and now - self._last_motion_log > 1.5:
                                self._last_motion_log = now
                                self.main.write_log("SYS: Movimiento detectado frente a la cámara")
                        self._previous_gray = gray
                    except Exception:
                        pass
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
                    self.main._cam_frame_sig.emit(buf.tobytes())
            cap.release()
        except Exception as e:
            print(f"[Camera] Stream error: {e}")
        finally:
            self.main._cam_stream_sig.emit(False)

    def stop_stream(self):
        """Detiene el bucle de la cámara."""
        self._cam_stop.set()

    def on_stream_toggle(self, start: bool):
        """Cambia entre HUD animado y vista de cámara."""
        if start:
            self.main._hud_cam_stack.setCurrentIndex(1)
        else:
            self.main._hud_cam_stack.setCurrentIndex(0)
            self.main._cam_live_lbl.clear()

    def on_frame(self, data: bytes):
        """Actualiza el QLabel con el fotograma recibido."""
        px = QPixmap()
        px.loadFromData(data)
        if not px.isNull():
            w, h = self.main._cam_live_lbl.width(), self.main._cam_live_lbl.height()
            if w > 1 and h > 1:
                self.main._cam_live_lbl.setPixmap(
                    px.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )
