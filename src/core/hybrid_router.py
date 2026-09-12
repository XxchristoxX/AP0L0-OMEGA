# src/core/hybrid_router.py
import json
from pathlib import Path
from src.core.multi_provider import MultiProvider
from src.core.config import get_selected_text_model

class HybridRouter:
    def __init__(self):
        self.provider = MultiProvider()
        self._personality = "APOLO"

    def route(self, prompt: str, personality: str = "APOLO") -> str:
        self._personality = personality
        sys_prompt = (
            f"Eres {personality}, un asistente avanzado. "
            "Responde de manera útil y concisa. "
            "Siempre responde en el idioma en que se te pregunta."
        )
        response, used = self.provider.generate(prompt, system_instruction=sys_prompt)
        if response is None:
            return "[HybridRouter] Error: Todos los proveedores fallaron."
        return response

    def route_local(self, prompt: str, personality: str = "APOLO") -> str:
        """Responde sin usar proveedores externos."""
        self._personality = personality
        system = f"Eres {personality}, un asistente útil. Responde en español."
        response, _ = self.provider.generate_local(prompt, system_instruction=system)
        return response or "El modo local no está disponible. Inicia Ollama y verifica el modelo configurado."

    def route_with_provider(self, prompt: str, personality: str = "APOLO", mode: str = "auto") -> str:
        """Ruta con modo explícito; conserva route() por compatibilidad."""
        self.provider.config["connection_mode"] = mode
        return self.route(prompt, personality)

    def check_connections(self):
        status = {
            "mode": self.provider.config.get("connection_mode", "auto"),
            "cloud_configured": any(self.provider.config.get(k) for k in (
                "gemini_api_key", "openrouter_api_key", "groq_api_key", "openai_api_key"
            )),
            "local_configured": bool(self.provider.ollama_url and self.provider.ollama_model),
        }
        return bool(status["cloud_configured"] or status["local_configured"])

    def connection_status(self) -> dict:
        """Devuelve detalles sin cambiar el contrato booleano anterior."""
        mode = self.provider.config.get("connection_mode", "auto")
        return {
            "mode": mode,
            "cloud_configured": any(self.provider.config.get(k) for k in (
                "gemini_api_key", "openrouter_api_key", "groq_api_key", "openai_api_key"
            )),
            "local_configured": bool(self.provider.ollama_url and self.provider.ollama_model),
        }
