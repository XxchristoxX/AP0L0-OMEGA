# src/core/gesture_manager.py
"""
Gesture Manager DEFINITIVO para AP0L0
Soporte completo de gestos + VELOCIDAD AJUSTABLE + suavizado
"""

import cv2
import numpy as np
import threading
import time
import pyautogui
from typing import Optional, Tuple, List

# ===== IMPORTACIÓN DE MEDIAPIPE CON MANEJO DE ERRORES =====
MEDIAPIPE_AVAILABLE = False
mp_hands = None
mp_drawing = None
mp_drawing_styles = None

try:
    # Intentar importar mediapipe con manejo de versión
    import mediapipe as mp
    # Verificar que tenga los módulos necesarios
    if hasattr(mp, 'solutions'):
        mp_hands = mp.solutions.hands
        mp_drawing = mp.solutions.drawing_utils
        mp_drawing_styles = mp.solutions.drawing_styles
        MEDIAPIPE_AVAILABLE = True
        print("[GestureManager] ✅ MediaPipe importado correctamente.")
    else:
        # Intentar importar desde el paquete interno
        try:
            from mediapipe import solutions
            mp_hands = solutions.hands
            mp_drawing = solutions.drawing_utils
            mp_drawing_styles = solutions.drawing_styles
            MEDIAPIPE_AVAILABLE = True
            print("[GestureManager] ✅ MediaPipe (solutions) importado correctamente.")
        except ImportError:
            MEDIAPIPE_AVAILABLE = False
            print("[GestureManager] ❌ MediaPipe no compatible. Instala: pip install mediapipe==0.10.8")
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    print("[GestureManager] ❌ MediaPipe no encontrado. Instala: pip install mediapipe==0.10.8")

# ===== CONFIGURACIÓN PREDETERMINADA =====
SMOOTH_FACTOR = 0.5
SPEED_MULTIPLIER = 1.8
SCROLL_THRESHOLD = 20
DOUBLE_CLICK_THRESHOLD = 0.4
ACTION_COOLDOWN = 0.25


class GestureManager:
    def __init__(
        self,
        camera_index: int = 0,
        num_hands: int = 1,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.5,
        enable_actions: bool = True,
        show_debug_window: bool = True,
        mirror: bool = True,
        smooth_factor: float = SMOOTH_FACTOR,
        speed_multiplier: float = SPEED_MULTIPLIER,
    ):
        if not MEDIAPIPE_AVAILABLE:
            raise RuntimeError("MediaPipe no está disponible. Instala: pip install mediapipe==0.10.8")

        self.camera_index = camera_index
        self.num_hands = num_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.enable_actions = enable_actions
        self.show_debug_window = show_debug_window
        self.mirror = mirror

        # Estado interno
        self._running = False
        self._thread = None
        self._cap = None
        self._hands = None
        self._lock = threading.Lock()

        # CONTROLES DE VELOCIDAD
        self.smooth_x = 0.0
        self.smooth_y = 0.0
        self.smooth_factor = smooth_factor
        self.speed_multiplier = speed_multiplier
        self._is_smooth_initialized = False

        # ESTADO DE LA MANO
        self.current_gesture = None
        self.prev_gesture = None
        self.hand_landmarks = None
        self.hand_center = (0, 0)
        self.hand_visible = False
        self.hand_w, self.hand_h = 640, 480

        # SCROLL
        self.peace_active = False
        self.peace_prev_y = 0
        self.peace_scroll_accum = 0

        # DOBLE CLIC
        self.last_pinch_time = 0.0
        self.double_click_threshold = DOUBLE_CLICK_THRESHOLD

        # CONTROL DE ACCIONES
        self._action_cooldown = ACTION_COOLDOWN
        self._last_action_time = 0.0
        self._drag_active = False
        self._drag_start_pos = (0, 0)

        # Callbacks
        self.on_gesture = None
        self.on_hand_detected = None
        self.on_hand_lost = None

        self._init_model()

    def _init_model(self):
        if not MEDIAPIPE_AVAILABLE:
            return
        try:
            # Usar un contexto de administración para evitar conflictos
            self._hands = mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=self.num_hands,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
            )
            print("[GestureManager] ✅ Modelo de manos inicializado.")
        except Exception as e:
            print(f"[GestureManager] ❌ Error al inicializar el modelo: {e}")
            self._hands = None

    def start(self) -> bool:
        if self._running:
            return True
        if not MEDIAPIPE_AVAILABLE or self._hands is None:
            print("[GestureManager] ❌ No se puede iniciar: modelo no disponible.")
            return False
        try:
            self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                self._cap = cv2.VideoCapture(0)
            if not self._cap.isOpened():
                print("[GestureManager] ❌ No se pudo abrir la cámara.")
                return False
            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True, name="GestureThread")
            self._thread.start()
            print("[GestureManager] 🖐️ Control por gestos iniciado.")
            return True
        except Exception as e:
            print(f"[GestureManager] ❌ Error al iniciar: {e}")
            return False

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._cap:
            self._cap.release()
        self._cap = None
        self.hand_visible = False
        self.current_gesture = None
        self.peace_active = False
        if self._hands:
            self._hands.close()
        cv2.destroyAllWindows()
        print("[GestureManager] 🖐️ Control por gestos detenido.")

    def _loop(self):
        if not self._cap or not self._hands:
            return

        while self._running:
            ret, frame = self._cap.read()
            if not ret or frame is None:
                continue

            self.hand_h, self.hand_w, _ = frame.shape
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._hands.process(rgb)

            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]
                landmarks = hand_landmarks.landmark

                cx = int(sum(lm.x for lm in landmarks) / len(landmarks) * self.hand_w)
                cy = int(sum(lm.y for lm in landmarks) / len(landmarks) * self.hand_h)
                self.hand_center = (cx, cy)
                self.hand_visible = True
                self.hand_landmarks = [(lm.x, lm.y, lm.z) for lm in landmarks]

                gesture = self._recognize_gesture(landmarks)

                if gesture == "peace":
                    self._handle_peace_scroll(cy)
                else:
                    self.peace_active = False
                    self.peace_scroll_accum = 0

                self.prev_gesture = self.current_gesture
                self.current_gesture = gesture

                if gesture:
                    if gesture == "point":
                        self._move_cursor_smooth(cx, cy)
                    elif gesture != self.prev_gesture:
                        self._execute_gesture_action(gesture, (cx, cy))

                if self.on_hand_detected:
                    self.on_hand_detected(self.hand_landmarks, self.hand_center)
                if self.on_gesture and gesture:
                    self.on_gesture(gesture, self.hand_center)

                if self.show_debug_window:
                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS,
                        mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                        mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2),
                    )

            else:
                if self.hand_visible:
                    self.hand_visible = False
                    self.current_gesture = None
                    self.peace_active = False
                    self.peace_scroll_accum = 0
                    if self.on_hand_lost:
                        self.on_hand_lost()

            if self.show_debug_window:
                if self.current_gesture:
                    cv2.putText(
                        frame,
                        f"Gesto: {self.current_gesture}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 255, 0),
                        2,
                    )
                cv2.imshow("Gesture Control (ESC para salir)", frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    self._running = False

        cv2.destroyAllWindows()

    def _recognize_gesture(self, landmarks) -> Optional[str]:
        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        index_tip = landmarks[8]
        index_mcp = landmarks[5]
        middle_tip = landmarks[12]
        middle_mcp = landmarks[9]
        ring_tip = landmarks[16]
        ring_mcp = landmarks[13]
        pinky_tip = landmarks[20]
        pinky_mcp = landmarks[17]

        def is_extended(tip, pip, mcp):
            return tip.y < pip.y < mcp.y

        def distance(p1, p2):
            return ((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2) ** 0.5

        thumb_ext = distance(thumb_tip, thumb_ip) > 0.05
        index_ext = is_extended(index_tip, landmarks[6], index_mcp)
        middle_ext = is_extended(middle_tip, landmarks[10], middle_mcp)
        ring_ext = is_extended(ring_tip, landmarks[14], ring_mcp)
        pinky_ext = is_extended(pinky_tip, landmarks[18], pinky_mcp)

        if not any([index_ext, middle_ext, ring_ext, pinky_ext]):
            return "fist"
        if thumb_ext and not index_ext and not middle_ext and not ring_ext and not pinky_ext:
            return "thumb_up"
        if index_ext and not middle_ext and not ring_ext and not pinky_ext:
            return "point"
        if index_ext and middle_ext and not ring_ext and not pinky_ext:
            return "peace"
        if index_ext and pinky_ext and not middle_ext and not ring_ext:
            return "rock"
        if distance(thumb_tip, index_tip) < 0.04:
            return "pinch"
        if 0.03 < distance(thumb_tip, index_tip) < 0.08 and middle_ext and ring_ext and pinky_ext:
            return "ok"
        if index_ext and middle_ext and ring_ext and pinky_ext and thumb_ext:
            return "open"

        return None

    def _move_cursor_smooth(self, target_x: int, target_y: int):
        screen_w, screen_h = pyautogui.size()

        if self.mirror:
            norm_x = int((self.hand_w - target_x) / self.hand_w * screen_w)
        else:
            norm_x = int(target_x / self.hand_w * screen_w)
        norm_y = int(target_y / self.hand_h * screen_h)

        center_x = screen_w // 2
        center_y = screen_h // 2
        dx = (norm_x - center_x) * self.speed_multiplier
        dy = (norm_y - center_y) * self.speed_multiplier
        norm_x = int(center_x + dx)
        norm_y = int(center_y + dy)

        norm_x = max(0, min(screen_w - 1, norm_x))
        norm_y = max(0, min(screen_h - 1, norm_y))

        if not self._is_smooth_initialized:
            self.smooth_x = float(norm_x)
            self.smooth_y = float(norm_y)
            self._is_smooth_initialized = True

        self.smooth_x += (norm_x - self.smooth_x) * self.smooth_factor
        self.smooth_y += (norm_y - self.smooth_y) * self.smooth_factor

        pyautogui.moveTo(int(self.smooth_x), int(self.smooth_y), duration=0.01)

    def _handle_peace_scroll(self, current_y: int):
        if not self.peace_active:
            self.peace_active = True
            self.peace_prev_y = current_y
            self.peace_scroll_accum = 0
            return

        delta_y = self.peace_prev_y - current_y
        self.peace_prev_y = current_y
        self.peace_scroll_accum += delta_y

        if abs(self.peace_scroll_accum) >= SCROLL_THRESHOLD:
            scroll_amount = int(self.peace_scroll_accum / SCROLL_THRESHOLD)
            scroll_amount = max(-3, min(3, scroll_amount))
            pyautogui.scroll(scroll_amount)
            self.peace_scroll_accum = 0

    def _execute_gesture_action(self, gesture: str, center: Tuple[int, int]):
        if not self.enable_actions:
            return

        now = time.time()
        if now - self._last_action_time < self._action_cooldown:
            return

        x, y = center
        screen_w, screen_h = pyautogui.size()

        if self.mirror:
            norm_x = max(0, min(screen_w - 1, int((self.hand_w - x) / self.hand_w * screen_w)))
        else:
            norm_x = max(0, min(screen_w - 1, int(x / self.hand_w * screen_w)))
        norm_y = max(0, min(screen_h - 1, int(y / self.hand_h * screen_h)))

        if gesture == "point":
            pass
        elif gesture == "pinch":
            if now - self.last_pinch_time < self.double_click_threshold:
                pyautogui.doubleClick(norm_x, norm_y)
                self.last_pinch_time = 0
            else:
                pyautogui.click(norm_x, norm_y)
                self.last_pinch_time = now
        elif gesture == "fist":
            pyautogui.click(norm_x, norm_y, button='right')
        elif gesture == "open":
            if not self._drag_active:
                pyautogui.mouseDown(norm_x, norm_y)
                self._drag_active = True
            else:
                pyautogui.mouseUp(norm_x, norm_y)
                self._drag_active = False
        elif gesture == "thumb_up":
            pyautogui.press('enter')
        elif gesture == "peace":
            pass
        elif gesture == "rock":
            pyautogui.hotkey('alt', 'tab')
        elif gesture == "ok":
            self._toggle_panel()

        self._last_action_time = now

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

    def set_smooth_factor(self, factor: float):
        self.smooth_factor = max(0.05, min(0.95, factor))
        print(f"[Gesture] Suavizado ajustado a {self.smooth_factor:.2f}")

    def set_speed_multiplier(self, multiplier: float):
        self.speed_multiplier = max(0.5, min(5.0, multiplier))
        print(f"[Gesture] Velocidad ajustada a {self.speed_multiplier:.2f}x")


# =====================================================================
# FUNCIONES DE FÁBRICA
# =====================================================================

_gesture_manager_instance: Optional[GestureManager] = None


def start_gesture_control(
    camera_index: int = 0,
    show_debug: bool = True,
    smooth_factor: float = 0.5,
    speed_multiplier: float = 1.8,
    mirror: bool = True,
    player=None,
    speak=None,
) -> str:
    global _gesture_manager_instance
    if _gesture_manager_instance and _gesture_manager_instance._running:
        return "⚠️ El control por gestos ya está activo."
    
    # Verificar dependencias
    try:
        import mediapipe
        # Verificar versión de protobuf
        import google.protobuf
        print(f"[Gesture] MediaPipe version: {mediapipe.__version__ if hasattr(mediapipe, '__version__') else 'unknown'}")
        print(f"[Gesture] Protobuf version: {google.protobuf.__version__}")
    except ImportError as e:
        return f"❌ Dependencia faltante: {e}. Instala: pip install mediapipe==0.10.8 protobuf==4.25.5"

    try:
        _gesture_manager_instance = GestureManager(
            camera_index=camera_index,
            show_debug_window=show_debug,
            enable_actions=True,
            mirror=mirror,
            smooth_factor=smooth_factor,
            speed_multiplier=speed_multiplier,
        )
        if _gesture_manager_instance.start():
            if speak:
                speak("Control por gestos activado, señor.")
            return f"✅ Gestos iniciados (suavizado={smooth_factor}, velocidad={speed_multiplier}x)"
        else:
            return "❌ No se pudo iniciar el control por gestos."
    except Exception as e:
        return f"❌ Error: {e}"


def stop_gesture_control(player=None, speak=None) -> str:
    global _gesture_manager_instance
    if not _gesture_manager_instance or not _gesture_manager_instance._running:
        return "⚠️ El control por gestos no está activo."
    try:
        _gesture_manager_instance.stop()
        _gesture_manager_instance = None
        if speak:
            speak("Control por gestos desactivado, señor.")
        return "✅ Gestos detenidos."
    except Exception as e:
        return f"❌ Error: {e}"


def gesture_control_tool(parameters: dict, player=None, speak=None) -> str:
    action = parameters.get("action", "start").lower()
    camera_index = parameters.get("camera_index", 0)
    show_debug = parameters.get("show_debug", True)
    smooth_factor = parameters.get("smooth_factor", 0.5)
    speed_multiplier = parameters.get("speed_multiplier", 1.8)
    mirror = parameters.get("mirror", True)

    if action in ("start", "activar", "on"):
        return start_gesture_control(camera_index, show_debug, smooth_factor, speed_multiplier, mirror, player, speak)
    elif action in ("stop", "desactivar", "off"):
        return stop_gesture_control(player, speak)
    elif action == "status":
        if _gesture_manager_instance and _gesture_manager_instance._running:
            return "✅ Gestos activos."
        else:
            return "❌ Gestos inactivos."
    elif action in ("sensitivity", "sensibilidad", "speed", "velocidad"):
        smooth = parameters.get("smooth", None)
        speed = parameters.get("speed", None)
        if _gesture_manager_instance and _gesture_manager_instance._running:
            if smooth is not None:
                _gesture_manager_instance.set_smooth_factor(float(smooth))
            if speed is not None:
                _gesture_manager_instance.set_speed_multiplier(float(speed))
            return "✅ Ajustes aplicados."
        else:
            return "⚠️ El control por gestos no está activo. Inícialo primero."
    else:
        return f"⚠️ Acción '{action}' no soportada. Usa: start, stop, status, sensitivity"