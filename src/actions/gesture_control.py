# src/actions/gesture_control.py
"""
Control por gestos con MediaPipe Hands.
Soporta: mover cursor, clic (pinch), arrastrar (fist), scroll (dos dedos),
abrir panel, cerrar, etc.
"""

import cv2
import sys
import threading
import time
import subprocess
import importlib
import os

# ===== INSTALACIÓN AUTOMÁTICA DE MEDIAPIPE =====
def _ensure_mediapipe():
    try:
        import mediapipe as mp
        return mp
    except ImportError:
        print("[GestureControl] MediaPipe no instalado. Intentando instalar...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "mediapipe", "--user", "--quiet"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            import mediapipe as mp
            print("[GestureControl] MediaPipe instalado correctamente.")
            return mp
        except Exception as e:
            print(f"[GestureControl] No se pudo instalar MediaPipe: {e}")
            return None

mp = _ensure_mediapipe()
if mp is not None:
    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles
else:
    mp_hands = mp_drawing = mp_drawing_styles = None

# ===== CLASE PRINCIPAL =====
class GestureController:
    def __init__(self):
        self.running = False
        self.thread = None
        self.cap = None
        self.callback = None
        self._last_gesture = None
        self._cooldown = 0
        self._screen_width, self._screen_height = self._get_screen_size()
        self._hands = None
        self._smooth_x = 0
        self._smooth_y = 0
        self._smooth_factor = 0.5
        self._speed_multiplier = 1.8

    def _get_screen_size(self):
        try:
            import pyautogui
            return pyautogui.size()
        except:
            return 1920, 1080

    def set_callback(self, callback):
        self.callback = callback

    def start(self, camera_index=0):
        if self.running:
            return "Gestures already running."
        if mp is None:
            return "MediaPipe no disponible. No se pudo instalar."

        try:
            self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                return "No se pudo abrir la cámara."

            self._hands = mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.5
            )
            self.running = True
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            return "Gestures started."
        except Exception as e:
            return f"Error starting gestures: {e}"

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        return "Gestures stopped."

    def _loop(self):
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
        self._smooth_x, self._smooth_y = pyautogui.position()

        while self.running and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                continue

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._hands.process(rgb)

            gesture = None
            landmarks = None

            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]
                landmarks = hand_landmarks
                gesture = self._detect_gesture(hand_landmarks)

                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style()
                )

                # Movimiento del cursor
                if gesture == "index_only" or gesture == "point":
                    index = hand_landmarks.landmark[8]
                    screen_x = int(index.x * self._screen_width)
                    screen_y = int(index.y * self._screen_height)
                    self._move_cursor_smooth(screen_x, screen_y)

            if gesture:
                cv2.putText(frame, f"Gesto: {gesture}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                if self.callback and self._cooldown == 0:
                    self.callback(gesture)
                    self._cooldown = 10

            if self._cooldown > 0:
                self._cooldown -= 1

            if gesture and landmarks:
                self._execute_gesture_action(gesture, landmarks, frame)

            cv2.imshow('AP0L0 Gesture Control (ESC para salir)', frame)
            if cv2.waitKey(1) & 0xFF == 27:
                self.stop()
                break

        cv2.destroyAllWindows()

    def _move_cursor_smooth(self, target_x, target_y):
        import pyautogui
        screen_w, screen_h = self._screen_width, self._screen_height

        # Invertir X para efecto espejo
        norm_x = screen_w - target_x
        norm_y = target_y

        # Aplicar multiplicador de velocidad
        center_x = screen_w // 2
        center_y = screen_h // 2
        dx = (norm_x - center_x) * self._speed_multiplier
        dy = (norm_y - center_y) * self._speed_multiplier
        norm_x = int(center_x + dx)
        norm_y = int(center_y + dy)

        norm_x = max(0, min(screen_w - 1, norm_x))
        norm_y = max(0, min(screen_h - 1, norm_y))

        self._smooth_x += (norm_x - self._smooth_x) * self._smooth_factor
        self._smooth_y += (norm_y - self._smooth_y) * self._smooth_factor

        pyautogui.moveTo(int(self._smooth_x), int(self._smooth_y), duration=0.01)

    def _detect_gesture(self, landmarks):
        thumb_tip = landmarks.landmark[4]
        index_tip = landmarks.landmark[8]
        middle_tip = landmarks.landmark[12]
        ring_tip = landmarks.landmark[16]
        pinky_tip = landmarks.landmark[20]
        thumb_mcp = landmarks.landmark[2]
        index_mcp = landmarks.landmark[5]
        middle_mcp = landmarks.landmark[9]

        thumb_extended = thumb_tip.x > thumb_mcp.x
        index_extended = index_tip.y < index_mcp.y
        middle_extended = middle_tip.y < middle_mcp.y
        ring_extended = ring_tip.y < landmarks.landmark[13].y
        pinky_extended = pinky_tip.y < landmarks.landmark[17].y

        thumb_index_dist = ((thumb_tip.x - index_tip.x)**2 + (thumb_tip.y - index_tip.y)**2)**0.5

        if not index_extended and not middle_extended and not ring_extended and not pinky_extended:
            return "fist"
        if index_extended and middle_extended and ring_extended and pinky_extended and thumb_extended:
            return "open"
        if thumb_index_dist < 0.05 and index_extended and not middle_extended:
            return "pinch"
        if thumb_extended and not index_extended and not middle_extended and not ring_extended and not pinky_extended:
            return "thumb_up"
        if index_extended and middle_extended and not ring_extended and not pinky_extended:
            return "two_fingers"
        if index_extended and not middle_extended and not ring_extended and not pinky_extended:
            return "index_only"

        return None

    def _execute_gesture_action(self, gesture, landmarks, frame):
        import pyautogui
        h, w, _ = frame.shape
        index = landmarks.landmark[8]
        screen_x = int(index.x * self._screen_width)
        screen_y = int(index.y * self._screen_height)

        if gesture == "pinch":
            pyautogui.click(screen_x, screen_y)
            time.sleep(0.1)
        elif gesture == "fist":
            pyautogui.mouseDown()
            time.sleep(0.1)
            pyautogui.moveTo(screen_x, screen_y, duration=0.1)
            pyautogui.mouseUp()
        elif gesture == "two_fingers":
            pyautogui.scroll(-3)
        elif gesture == "thumb_up":
            pyautogui.rightClick(screen_x, screen_y)
        elif gesture == "open":
            self._toggle_panel()

    def _toggle_panel(self):
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is None:
                return
            for widget in app.allWidgets():
                if widget.__class__.__name__ == 'JarvisCircularPanel':
                    if widget.isVisible():
                        widget.hide()
                    else:
                        widget.show()
                        widget.raise_()
                    break
        except Exception as e:
            print(f"[Gesture] Error toggling panel: {e}")

    def is_running(self):
        return self.running


# ===== FUNCIÓN EXPORTABLE =====
def gesture_control(parameters: dict, player=None, speak=None) -> str:
    action = parameters.get("action", "toggle").lower()

    if not hasattr(gesture_control, "_controller"):
        gesture_control._controller = None

    controller = gesture_control._controller

    if action in ("start", "activar", "on"):
        if controller and controller.is_running():
            return "El control por gestos ya está activo."
        new_controller = GestureController()
        def on_gesture(gesture):
            if player:
                player.write_log(f"[Gesto] {gesture}")
        new_controller.set_callback(on_gesture)
        result = new_controller.start()
        if "started" in result:
            gesture_control._controller = new_controller
            if player:
                player.write_log("[Gesture] Control por gestos activado.")
            if speak:
                speak("Control por gestos activado.")
            return result
        return f"Error al iniciar gestos: {result}"

    elif action in ("stop", "desactivar", "off"):
        if controller and controller.is_running():
            controller.stop()
            gesture_control._controller = None
            if player:
                player.write_log("[Gesture] Control por gestos desactivado.")
            if speak:
                speak("Control por gestos desactivado.")
            return "Gestos detenidos."
        return "El control por gestos no está activo."

    elif action in ("status", "estado"):
        if controller and controller.is_running():
            return "Control por gestos ACTIVO."
        return "Control por gestos INACTIVO."

    elif action in ("toggle", "cambiar"):
        if controller and controller.is_running():
            return gesture_control({"action": "stop"}, player, speak)
        return gesture_control({"action": "start"}, player, speak)

    else:
        return f"Acción '{action}' no soportada. Usa: start, stop, status, toggle"