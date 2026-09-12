# src/core/reflection_engine.py
"""
Reflection Engine - Procesa respuestas y errores del sistema de forma segura.
Maneja tanto dict como list para evitar errores de tipo.
Ahora con capacidad de reflexión autónoma y sugerencias.
"""

import json
import time
import traceback
from typing import Any, Dict, List, Union, Optional, Callable

class ReflectionEngine:
    """
    Motor de reflexión que procesa respuestas y errores del sistema.
    """

    def __init__(self, log_callback: Optional[Callable] = None):
        self.log_callback = log_callback or print
        self._error_count = 0
        self._last_reflection_time = 0.0
        self._reflection_interval = 300  # 5 minutos
        self._reflection_log = []

    def process_response(self, response: Any) -> Dict[str, Any]:
        """
        Procesa una respuesta del LLM, asegurando que siempre devuelva un diccionario.
        """
        if isinstance(response, list):
            if response and isinstance(response[0], dict):
                return self._normalize_dict(response[0])
            else:
                return self._create_error_response(f"La respuesta fue una lista vacía o inválida: {response}")
        elif isinstance(response, dict):
            return self._normalize_dict(response)
        elif isinstance(response, str):
            try:
                parsed = json.loads(response)
                if isinstance(parsed, dict):
                    return self._normalize_dict(parsed)
                else:
                    return {"text": response, "tool_calls": []}
            except json.JSONDecodeError:
                return {"text": response, "tool_calls": []}
        else:
            return self._create_error_response(f"Tipo de respuesta no soportado: {type(response)}")

    def _normalize_dict(self, data: Dict) -> Dict:
        """Normaliza un diccionario para asegurar que tenga las claves mínimas."""
        normalized = {
            "text": data.get("text", ""),
            "tool_calls": data.get("tool_calls", []),
            "intent": data.get("intent", "chat"),
            "parameters": data.get("parameters", {}),
            "needs_clarification": data.get("needs_clarification", False),
            "memory_update": data.get("memory_update")
        }
        if not normalized["text"] and "content" in data:
            normalized["text"] = data["content"]
        return normalized

    def _create_error_response(self, error_msg: str) -> Dict:
        """Crea una respuesta de error segura."""
        self._error_count += 1
        if self.log_callback:
            self.log_callback(f"[Reflection] Error procesado ({self._error_count}): {error_msg}")
        return {
            "text": f"Lo siento, hubo un error al procesar la respuesta. Error: {error_msg[:100]}",
            "tool_calls": [],
            "intent": "chat",
            "parameters": {},
            "needs_clarification": False,
            "memory_update": None
        }

    def should_reflect(self) -> bool:
        """
        Determina si es momento de ejecutar una reflexión.
        Retorna True si han pasado más de `_reflection_interval` segundos
        desde la última reflexión y hay errores registrados.
        """
        now = time.time()
        if self._error_count == 0:
            return False
        if now - self._last_reflection_time > self._reflection_interval:
            return True
        return False

    def run_reflection(self, log_callback: Optional[Callable] = None) -> str:
        """
        Ejecuta una reflexión: analiza los errores recientes y genera una sugerencia.
        Retorna un mensaje de sugerencia.
        """
        self._last_reflection_time = time.time()
        log = log_callback or self.log_callback

        if self._error_count == 0:
            return ""

        if self._error_count > 10:
            suggestion = (
                "He notado varios errores en el procesamiento de respuestas. "
                "Sugiero revisar la configuración de la API y la conectividad de red."
            )
        elif self._error_count > 5:
            suggestion = (
                "Se han producido algunos errores intermitentes. "
                "Podría ser útil reiniciar el asistente para restablecer las conexiones."
            )
        else:
            suggestion = (
                "Todo parece estar funcionando, pero he detectado algún error menor. "
                "Continuaré monitoreando el sistema."
            )

        self._reflection_log.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "error_count": self._error_count,
            "suggestion": suggestion
        })

        log(f"[Reflection] Sugerencia generada: {suggestion}")
        return suggestion

    def get_stats(self) -> Dict:
        return {
            "total_errors": self._error_count,
            "last_error": self._error_count > 0,
            "last_reflection": self._last_reflection_time,
            "reflection_count": len(self._reflection_log)
        }

    def reset(self):
        self._error_count = 0
        self._last_reflection_time = 0.0
        self._reflection_log = []