# src/core/proactive_engine.py
import random
import time
import psutil
import threading
from datetime import datetime
from src.core.evolution_engine import EvolutionEngine

class ProactiveEngine:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.evolution = EvolutionEngine(orchestrator.memory, orchestrator.router)
        self.active = True
        self.thread = threading.Thread(target=self._suggestion_loop, daemon=True)
        self.thread.start()

    def _suggestion_loop(self):
        counter = 0
        while self.active:
            if counter % 10 == 0:
                hour = datetime.now().hour
                if 7 <= hour < 9:
                    self.orchestrator.tts.speak("¿Quieres tu briefing matutino?")
                cpu = psutil.cpu_percent(interval=1)
                if cpu > 80:
                    self.orchestrator.tts.speak("El sistema está bajo carga alta. ¿Deseas optimizar?")
            if counter % 60 == 0:
                suggestions = self.evolution.analyze_and_suggest()
                if suggestions:
                    self.orchestrator.tts.speak(f"Sugerencias de mejora: {suggestions}")
            counter += 1
            time.sleep(30)

    def stop(self):
        self.active = False