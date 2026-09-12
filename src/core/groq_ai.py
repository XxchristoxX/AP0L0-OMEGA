# src/core/groq_ai.py
"""
Proveedor de IA para Groq (API cloud). 
Soporta chat, generación de texto y funciones.
"""

import json
from typing import Optional, Dict, Any, List

try:
    import groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

from src.core.config import get_api_key


class GroqAI:
    """
    Interfaz para Groq Cloud API.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "mixtral-8x7b-32768"):
        self.api_key = api_key or get_api_key("groq_api_key")
        self.model = model
        self.client = None
        if GROQ_AVAILABLE and self.api_key:
            self.client = groq.Groq(api_key=self.api_key)

    def is_available(self) -> bool:
        return self.client is not None

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """
        Envía una conversación a Groq y retorna la respuesta.
        """
        if not self.is_available():
            return "Error: Groq no disponible (clave API faltante o librería no instalada)."

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if response and response.choices:
                return response.choices[0].message.content.strip()
            return ""
        except Exception as e:
            print(f"[Groq] Error: {e}")
            return f"Error en Groq: {str(e)}"

    def generate(self, prompt: str, system: str = "", temperature: float = 0.7) -> str:
        """
        Genera una respuesta a partir de un prompt simple.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, temperature=temperature)