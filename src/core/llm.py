# src/core/llm.py
"""
Fachada unificada para todos los proveedores de LLM (Gemini, Groq, Ollama, OpenRouter, etc.).
Permite conmutar entre modo local y nube automáticamente.
"""

import time
from typing import Optional, Dict, Any, List
from src.core.multi_provider import MultiProvider
from src.core.groq_ai import GroqAI


class LLM:
    """
    Fachada unificada para LLM con detección automática de disponibilidad.
    """

    def __init__(self):
        self.multi_provider = MultiProvider()
        self.groq = GroqAI()
        self._local_mode = False  # True si se fuerza local (Ollama)
        self._last_provider = "none"

    def set_local_mode(self, enabled: bool):
        """Fuerza el modo local (usa Ollama)."""
        self._local_mode = enabled

    def is_online(self) -> bool:
        """Verifica si hay conexión a internet."""
        import socket
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False

    def generate(self, prompt: str, system_instruction: str = "", temperature: float = 0.7) -> tuple[Optional[str], str]:
        """
        Genera contenido usando el mejor proveedor disponible.
        Retorna (respuesta, nombre_proveedor).
        """
        # Si modo local forzado o sin internet, usar Ollama
        if self._local_mode or not self.is_online():
            # Intentar Ollama
            try:
                import ollama
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                response = ollama.chat(model="qwen2.5:3b", messages=messages)
                if response and "message" in response:
                    self._last_provider = "ollama/local"
                    return response["message"]["content"], "ollama/local"
            except Exception as e:
                print(f"[LLM] Ollama falló: {e}")

            # Fallback local: si no hay internet y Ollama no funciona, error
            return None, "offline/local_fallback"

        # Modo nube: probar proveedores en orden
        # 1. Gemini (prioridad alta)
        try:
            result, provider = self.multi_provider.generate(prompt, system_instruction, temperature)
            if result:
                self._last_provider = provider
                return result, provider
        except Exception as e:
            print(f"[LLM] Gemini falló: {e}")

        # 2. Groq
        if self.groq.is_available():
            try:
                result = self.groq.generate(prompt, system_instruction, temperature)
                if result and not result.startswith("Error"):
                    self._last_provider = "groq"
                    return result, "groq"
            except Exception as e:
                print(f"[LLM] Groq falló: {e}")

        # 3. Intentar OpenRouter (vía cliente importado)
        try:
            from src.core.openrouter_client import client as or_client
            result = or_client.chat(prompt, system=system_instruction, temperature=temperature)
            if result:
                self._last_provider = "openrouter"
                return result, "openrouter"
        except Exception as e:
            print(f"[LLM] OpenRouter falló: {e}")

        # Si todo falla, intentar Ollama local (último recurso)
        try:
            import ollama
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            response = ollama.chat(model="qwen2.5:3b", messages=messages)
            if response and "message" in response:
                self._last_provider = "ollama/fallback"
                return response["message"]["content"], "ollama/fallback"
        except Exception:
            pass

        return None, "all_providers_failed"

    def get_last_provider(self) -> str:
        return self._last_provider