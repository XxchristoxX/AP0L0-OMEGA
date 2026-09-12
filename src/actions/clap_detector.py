# src/actions/clap_detector.py
import threading
import numpy as np
import time

try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

class ClapDetector:
    def __init__(self, callback, threshold=0.5, cooldown=2.0, max_claps=2):
        if not HAS_PYAUDIO:
            raise ImportError("pyaudio no está instalado.")
        self.callback = callback
        self.threshold = threshold
        self.cooldown = cooldown
        self.max_claps = max_claps
        self.running = False
        self.thread = None
        self.last_clap_time = 0
        self.clap_count = 0
        self._lock = threading.Lock()
        self._last_trigger = 0

    def start(self):
        if self.running:
            return "Clap detector already running."
        self.running = True
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()
        print("[ClapDetector] Escuchando aplausos...")
        return "Clap detector started."

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        print("[ClapDetector] Detenido.")
        return "Clap detector stopped."

    def _listen(self):
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            input=True,
            frames_per_buffer=1024,
            stream_callback=self._audio_callback,
        )
        stream.start_stream()
        while self.running:
            time.sleep(0.1)
        stream.stop_stream()
        stream.close()
        p.terminate()

    def _audio_callback(self, in_data, frame_count, time_info, status):
        if not self.running:
            return (None, pyaudio.paComplete)
        try:
            audio = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)
            volume = np.linalg.norm(audio) / 32768.0
            if volume > self.threshold:
                now = time.time()
                with self._lock:
                    if now - self._last_trigger < self.cooldown:
                        return (None, pyaudio.paContinue)
                    if now - self.last_clap_time > self.cooldown:
                        self.clap_count = 1
                    else:
                        self.clap_count += 1
                        if self.clap_count >= self.max_claps:
                            self.clap_count = 0
                            self._last_trigger = now
                            if self.callback:
                                self.callback()  # NO detener el detector
                    self.last_clap_time = now
        except Exception:
            pass
        return (None, pyaudio.paContinue)


def toggle_clap_detection(parameters: dict = None, player=None, speak=None) -> str:
    action = "toggle"
    if isinstance(parameters, dict):
        action = parameters.get("action") or "toggle"
    elif isinstance(parameters, str):
        action = parameters
    action = str(action).lower().strip()

    if not hasattr(toggle_clap_detection, "_detector"):
        toggle_clap_detection._detector = None
    detector = toggle_clap_detection._detector

    if action in ("on", "activar", "enable"):
        if detector is not None:
            return "La detección de aplausos ya está activa."
        try:
            def clap_callback():
                if speak:
                    speak("Aplausos detectados. ¿En qué puedo ayudarle?")
                if player:
                    player.write_log("👏 Aplausos detectados.")
                # NO detener el detector, solo ejecutar la acción
            detector = ClapDetector(clap_callback, threshold=0.6, cooldown=3.0)
            detector.start()
            toggle_clap_detection._detector = detector
            return "Detección de aplausos activada."
        except Exception as e:
            return f"Error al activar: {e}"

    elif action in ("off", "desactivar", "disable", "stop"):
        if detector:
            detector.stop()
            toggle_clap_detection._detector = None
            return "Detección de aplausos desactivada."
        else:
            return "La detección de aplausos no está activa."

    elif action in ("toggle", "cambiar"):
        if detector is not None:
            detector.stop()
            toggle_clap_detection._detector = None
            return "Detección de aplausos desactivada."
        else:
            try:
                def clap_callback():
                    if speak:
                        speak("Aplausos detectados. ¿En qué puedo ayudarle?")
                    if player:
                        player.write_log("👏 Aplausos detectados.")
                detector = ClapDetector(clap_callback, threshold=0.6, cooldown=3.0)
                detector.start()
                toggle_clap_detection._detector = detector
                return "Detección de aplausos activada."
            except Exception as e:
                return f"Error al activar: {e}"

    elif action in ("status", "estado"):
        return "La detección de aplausos está activa." if detector else "La detección de aplausos está inactiva."

    else:
        return f"Acción '{action}' no soportada."