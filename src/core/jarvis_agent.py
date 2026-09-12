# src/core/jarvis_agent.py
"""
Agente JARVIS para AP0L0
"""

import os
import json
import time
import logging
from pathlib import Path

from src.core.config import _get_config

USER_NAME = _get_config().get("user_name", "Christopher")

try:
    import google.genai as genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    GENAI_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="[JARVIS_AGENT] %(message)s")


class JarvisAgent:
    def __init__(self, api_key=None, model="gemini-2.5-flash", memory_file="jarvis_memoire.json"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or _get_config().get("gemini_api_key", "")
        self.model = model
        self.memory_file = Path(memory_file)
        self.client = genai.Client(api_key=self.api_key) if GENAI_AVAILABLE and self.api_key else None
        self.memory = self._load_memory()

    def _load_memory(self):
        if self.memory_file.exists():
            try:
                return json.loads(self.memory_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_memory(self):
        try:
            self.memory_file.write_text(json.dumps(self.memory, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def remember(self, key, value):
        self.memory[key] = {"valeur": value, "timestamp": time.strftime("%d/%m/%Y %H:%M")}
        self._save_memory()

    def forget(self, key):
        if key in self.memory:
            del self.memory[key]
            self._save_memory()
            return True
        return False

    def memory_context(self):
        if not self.memory:
            return ""
        lines = ["MEMORIA PERSISTENTE:"]
        for key, data in self.memory.items():
            lines.append(f"  - {key}: {data['valeur']} (desde {data['timestamp']})")
        return "\n".join(lines)

    def system_prompt(self):
        base = f"Eres JARVIS, asistente IA personal de {USER_NAME}. Responde en español.\n"
        base += self.memory_context()
        return base

    def build_prompt(self, user_message):
        return [
            {"role": "system", "content": self.system_prompt()},
            {"role": "user", "content": user_message}
        ]

    def generate_response(self, user_message):
        if not self.client:
            return "El cliente Gemini no está disponible."
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=self.build_prompt(user_message)
            )
            return response.text.strip() if response and response.text else "No pude generar respuesta."
        except Exception as e:
            return f"Error: {e}"


# ===== FUNCIÓN EXPORTABLE =====

async def jarvis_agent(params: dict, player=None, speak=None) -> str:
    message = params.get("message", "").strip()
    if not message:
        return "Necesito un mensaje."
    agent = JarvisAgent(model=params.get("model", "gemini-2.5-flash"))
    result = agent.generate_response(message)
    if speak:
        speak(result)
    if player:
        player.write_log(f"[JARVIS_AGENT] {result[:80]}...")
    return result