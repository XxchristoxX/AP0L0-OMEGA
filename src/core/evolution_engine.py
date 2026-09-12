import datetime
import os
import json
from collections import Counter
from src.memory.memory_manager import MemoryManager   # ← ruta corregida
from src.core.hybrid_router import HybridRouter

class EvolutionEngine:
    def __init__(self, memory: MemoryManager, router: HybridRouter):
        self.memory = memory
        self.router = router
        self.summary_interval = 50

    def analyze_and_suggest(self):
        interactions = self.memory.get_recent(limit=self.summary_interval)
        if not interactions:
            return None
        prompt = f"""Analiza el siguiente historial de interacciones del usuario con el asistente y propón 2 o 3 nuevas habilidades (skills) que el asistente debería tener para mejorar la experiencia. Describe cada habilidad en una frase breve.
Historial:
{chr(10).join(interactions)}
Respuesta:"""
        suggestions = self.router.route(prompt, "A.G.A.T.A")
        return suggestions

    def periodic_summary(self):
        now = datetime.datetime.now()
        summary = f"[{now}] Resumen de actividad: {self.memory.count_today()} interacciones hoy."
        self.memory.add("system", summary)
        return summary