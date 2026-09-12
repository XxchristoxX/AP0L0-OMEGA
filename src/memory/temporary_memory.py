# src/memory/temporary_memory.py
"""
Memoria temporal (en RAM) para sesiones de AP0L0.
Se reinicia al cerrar la aplicación.
"""
from typing import Any, Dict, Optional


class TemporaryMemory:
    """
    Memoria de corto plazo para:
        - Intenciones pendientes (multi‑paso)
        - Últimas acciones (búsquedas, apps abiertas)
        - Historial de conversación (últimas N interacciones)
    """

    def __init__(self, max_history: int = 5):
        self.max_history = max_history
        self.reset()

    def reset(self):
        self.pending_intent: Optional[str] = None
        self.parameters: Dict[str, Any] = {}
        self.current_question: Optional[str] = None

        self.last_user_text: Optional[str] = None
        self.last_ai_response: Optional[str] = None

        # --- Acciones recientes ---
        self.last_search: Optional[Dict] = None
        self.last_opened_app: Optional[str] = None

        # --- Historial de conversación ---
        self.conversation_history: list[dict[str, str]] = []

    # -- Intención --
    def set_pending_intent(self, intent: str):
        self.pending_intent = intent

    def clear_pending_intent(self):
        self.pending_intent = None
        self.parameters = {}
        self.current_question = None

    def has_pending_intent(self) -> bool:
        return self.pending_intent is not None

    def update_parameters(self, new_params: dict):
        if not isinstance(new_params, dict):
            return
        for k, v in new_params.items():
            if v not in (None, ""):
                self.parameters[k] = v

    def get_parameters(self) -> dict:
        return self.parameters.copy()

    def get_parameter(self, key: str):
        return self.parameters.get(key)

    def set_current_question(self, param_name: str):
        self.current_question = param_name

    def get_current_question(self) -> Optional[str]:
        return self.current_question

    def clear_current_question(self):
        self.current_question = None

    # -- Textos --
    def set_last_user_text(self, text: str):
        self.last_user_text = text
        self._add_to_history("user", text)

    def set_last_ai_response(self, text: str):
        self.last_ai_response = text
        self._add_to_history("ai", text)

    def get_last_user_text(self):
        return self.last_user_text

    def get_last_ai_response(self):
        return self.last_ai_response

    # -- Acciones --
    def set_last_search(self, query: str, answer: str):
        self.last_search = {"query": query, "answer": answer}

    def get_last_search(self):
        return self.last_search

    def set_open_app(self, app_name: str):
        self.last_opened_app = app_name

    def get_last_opened_app(self):
        return self.last_opened_app

    # -- Historial --
    def _add_to_history(self, role: str, text: str):
        if role not in ("user", "ai"):
            return
        self.conversation_history.append({"role": role, "text": text})
        if len(self.conversation_history) > self.max_history:
            self.conversation_history.pop(0)

    def get_history_for_prompt(self) -> str:
        """Devuelve el historial formateado para inyectar en el prompt."""
        return "\n".join(
            f"{m['role'].capitalize()}: {m['text']}"
            for m in self.conversation_history
        )

    def get_context_summary(self) -> dict:
        """Resumen de estado para depuración."""
        return {
            "pending_intent": self.pending_intent,
            "parameters": self.parameters,
            "last_search": self.last_search,
            "last_opened_app": self.last_opened_app,
            "last_user_text": self.last_user_text,
            "last_ai_response": self.last_ai_response,
        }