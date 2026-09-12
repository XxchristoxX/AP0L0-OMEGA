# src/core/orchestrator.py
import os
import time
import threading
import speech_recognition as sr
from src.core.personality_manager import PersonalityManager
from src.core.hybrid_router import HybridRouter
from src.core.skills_registry import SkillsRegistry
# Ruta corregida: memory_manager está en src/memory
from src.memory.memory_manager import MemoryManager
from src.core.proactive_engine import ProactiveEngine
from src.core.workspace_manager import WorkspaceManager
from src.core.self_healer import SelfHealer
# Usamos el TTS unificado de tts.py en lugar de EnhancedTTS (que no existe)
from src.tts.tts import create_tts_player
from dotenv import load_dotenv

# ── Stubs para módulos faltantes (no interrumpen el arranque) ──────────
try:
    from src.vision.vision_manager import VisionManager
except ImportError:
    class VisionManager:
        def __init__(self): pass
        def start(self): pass
        def stop(self): pass

try:
    from src.ui.dashboard import Dashboard
except ImportError:
    class Dashboard:
        def __init__(self, orchestrator=None): pass
        def start(self): pass
        def stop(self): pass
        def set_float_mode(self, mode): pass
        def maximize(self): pass
        def set_theme(self, color): pass

try:
    from src.ui.mobile_server import MobileServer
except ImportError:
    class MobileServer:
        def __init__(self, orchestrator=None): pass
        def start(self): pass
        def stop(self): pass

load_dotenv()


class Orchestrator:
    def __init__(self):
        self.personality_mgr = PersonalityManager()
        self.router = HybridRouter()
        self.skills_registry = SkillsRegistry()
        self.memory = MemoryManager()
        self.proactive = ProactiveEngine(self)
        self.workspace_mgr = WorkspaceManager()
        # TTS: cargamos la configuración y creamos el player
        self.tts_config = self._load_tts_config()
        self.tts = create_tts_player(self.tts_config)
        self.vision = VisionManager()
        self.self_healer = SelfHealer()
        self.dashboard = Dashboard(self)
        self.mobile_server = MobileServer(self)
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.running = True
        self.voice_active = True
        self.listen_thread = None
        self.healer_thread = None
        self.start()

    def _load_tts_config(self):
        # Configuración mínima, ajusta según tu config
        return {
            "tts_engine": "edgetts",
            "tts_voice": "es-MX-DaliaNeural",   # voz en español
        }

    def start(self):
        print("[Orquestador] Arrancando AP0LO v3.0...")
        self.dashboard.start()
        self.mobile_server.start()
        self.self_healer.start_monitoring()
        self.listen_thread = threading.Thread(target=self.voice_loop, daemon=True)
        self.listen_thread.start()
        print("[Orquestador] AP0LO está escuchando. Di 'Hola APOLO' para empezar.")

    def voice_loop(self):
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        while self.running:
            try:
                with self.microphone as source:
                    print("Escuchando...")
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=8)
                text = self.recognizer.recognize_google(audio, language="es-ES").lower()
                print(f"[Voz] Comando detectado: {text}")
                self.process_voice(text)
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                print(f"[Voz] Error de reconocimiento: {e}")

    def process_voice(self, text):
        if "autocuración" in text or "autocuracion" in text:
            self.self_healer.run_full_diagnostic()
            return

        if "flota" in text:
            self.dashboard.set_float_mode(True)
            return
        if "retírate" in text or "retirate" in text:
            self.dashboard.set_float_mode(False)
            return
        if "maximiza dashboard" in text:
            self.dashboard.maximize()
            return
        if "cambia tema a" in text:
            color = text.split("cambia tema a")[-1].strip()
            self.dashboard.set_theme(color)
            return
        if "cambia personalidad a" in text:
            name = text.split("cambia personalidad a")[-1].strip().upper()
            self.personality_mgr.set_personality(name)
            # Ahora usamos speak, no say
            self.tts.speak(f"Personalidad cambiada a {name}")
            return
        if "cambia tu voz" in text:
            # adjust_voice no existe, lo ignoramos o avisamos
            self.tts.speak("Aún no puedo cambiar la voz automáticamente.")
            return

        # COMANDO DE AUTOPROGRAMACIÓN ("mejórate")
        if "mejórate" in text or "automejora" in text:
            self.tts.speak("Iniciando automejora avanzada. Esto tomará unos segundos.")
            from src.skills.auto_programmer_advanced import skill_auto_programmer_advanced
            result = skill_auto_programmer_advanced({
                'task': 'Analiza y mejora AP0LO añadiendo cualquier funcionalidad que lo haga más inteligente, proactivo y capaz que J.A.R.V.I.S.'
            })
            self.tts.speak(result)
            return

        response = self.router.route(text, self.personality_mgr.get_current())
        if response:
            self.tts.speak(response)
        else:
            self.tts.speak("No he podido obtener una respuesta.")

        self.skills_registry.execute_relevant(text)

    def shutdown(self):
        self.running = False
        self.dashboard.stop()
        self.mobile_server.stop()
        self.self_healer.stop()
        self.tts.stop()
        print("[Orquestador] AP0LO detenido.")


if __name__ == "__main__":
    orch = Orchestrator()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        orch.shutdown()