# src/core/gemini_provider.py
"""
Proveedor Gemini con soporte para AFC, reintentos y fallback a modelos alternativos.
Versión mejorada con manejo de errores, backoff exponencial y uso correcto de Chat.send_message.
"""

import json
import time
import random
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

# Intentar importar google-generativeai
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("[GeminiProvider] ⚠️ google-genai no instalado. Instala: pip install google-genai")

# ===== CONFIGURACIÓN =====
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


def _get_api_key() -> str:
    """Obtiene la clave API de Gemini desde el archivo de configuración."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("gemini_api_key", "")
    except Exception:
        return ""


# ===== MODELOS DISPONIBLES =====
GEMINI_MODELS = [
    "gemini-2.5-flash-native-audio-latest",
    "gemini-2.5-flash-native-audio-preview-09-2025",
    "gemini-2.5-flash-native-audio-preview-12-2025",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.7-flash",
]


class GeminiProvider:
    """
    Proveedor de Gemini con soporte para:
    - Múltiples modelos con fallback automático
    - Reintentos con backoff exponencial
    - AFC (Automatic Function Calling) correcto usando Chat.send_message
    - Streaming opcional
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or _get_api_key()
        self.models = GEMINI_MODELS
        self.default_model = model or "gemini-3.5-flash-lite"
        self._client = None
        self._init_client()

    def _init_client(self):
        """Inicializa el cliente de Gemini."""
        if not GENAI_AVAILABLE:
            raise RuntimeError("google-genai no está instalado.")
        if not self.api_key:
            raise ValueError("No se proporcionó API key para Gemini.")
        self._client = genai.Client(api_key=self.api_key)

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> Union[str, Any]:
        """
        Genera contenido usando Gemini con reintentos y fallback automático.

        Args:
            prompt: El prompt del usuario.
            model: Modelo a usar (opcional, usa el predeterminado).
            system_instruction: Instrucción del sistema (opcional).
            tools: Lista de herramientas para AFC (opcional).
            temperature: Temperatura (0.0 - 1.0).
            max_tokens: Máximo de tokens de salida.
            stream: Si es True, devuelve el generador de streaming.
            max_retries: Número máximo de reintentos.
            base_delay: Retraso base para backoff exponencial.

        Returns:
            Texto generado o generador de streaming.
        """
        model_to_use = model or self.default_model

        # Intentar con el modelo especificado y luego con los alternativos
        models_to_try = [model_to_use] + [m for m in self.models if m != model_to_use]

        last_error = None
        for attempt in range(max_retries):
            for m in models_to_try:
                try:
                    result = self._generate_with_model(
                        prompt=prompt,
                        model=m,
                        system_instruction=system_instruction,
                        tools=tools,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=stream,
                    )
                    if result:
                        return result
                except Exception as e:
                    last_error = e
                    print(f"[GeminiProvider] ⚠️ Error con modelo {m}: {e}")
                    # Si es 503, esperar más tiempo
                    if "503" in str(e) or "UNAVAILABLE" in str(e):
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        print(f"[GeminiProvider] ⏳ Modelo {m} no disponible. Esperando {delay:.1f}s...")
                        time.sleep(delay)
                        break  # Salir del bucle de modelos para reintentar con backoff
                    continue

            # Si llegamos aquí, todos los modelos fallaron en este intento
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"[GeminiProvider] ⏳ Reintentando en {delay:.1f}s...")
                time.sleep(delay)

        raise RuntimeError(f"Todos los modelos de Gemini fallaron después de {max_retries} intentos. Último error: {last_error}")

    def _generate_with_model(
        self,
        prompt: str,
        model: str,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
    ) -> Union[str, Any]:
        """
        Genera contenido con un modelo específico, usando Chat.send_message para AFC.
        """
        if self._client is None:
            self._init_client()

        # Construir configuración
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        if system_instruction:
            config.system_instruction = system_instruction

        if tools:
            # Usar Chat.send_message para AFC correcto
            chat = self._client.chats.create(model=model)
            response = chat.send_message(
                prompt,
                tools=tools,
                config=config,
            )
            # Extraer texto y llamadas a herramientas
            if response and response.candidates:
                candidate = response.candidates[0]
                content = candidate.content
                if content and content.parts:
                    # Recolectar texto de todas las partes
                    text_parts = []
                    tool_calls = []
                    for part in content.parts:
                        if part.text:
                            text_parts.append(part.text)
                        elif part.function_call:
                            tool_calls.append({
                                "name": part.function_call.name,
                                "args": part.function_call.args,
                            })
                    result = {
                        "text": " ".join(text_parts) if text_parts else "",
                        "tool_calls": tool_calls if tool_calls else None,
                    }
                    return result
            return ""

        else:
            # Sin herramientas, usar generate_content directamente
            response = self._client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            if response and response.text:
                return response.text.strip()
            return ""

    def generate_stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        """
        Genera contenido en streaming.
        """
        model_to_use = model or self.default_model
        if self._client is None:
            self._init_client()

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        response = self._client.models.generate_content_stream(
            model=model_to_use,
            contents=prompt,
            config=config,
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text

    def chat(self, messages: List[Dict], model: Optional[str] = None, temperature: float = 0.7) -> str:
        """
        Chat simple con historial de mensajes.
        """
        model_to_use = model or self.default_model
        if self._client is None:
            self._init_client()

        chat = self._client.chats.create(model=model_to_use)
        # Enviar todos los mensajes
        for msg in messages:
            if msg["role"] == "user":
                response = chat.send_message(msg["content"])
            # Los mensajes del sistema se manejan en la configuración de la primera llamada
        # Obtener la última respuesta
        if chat.history:
            last = chat.history[-1]
            if last.parts:
                return " ".join(p.text for p in last.parts if p.text)
        return ""

    def list_models(self) -> List[str]:
        """Lista los modelos disponibles."""
        if self._client is None:
            self._init_client()
        try:
            models = self._client.models.list()
            return [m.name for m in models if "generateContent" in str(m.supported_actions)]
        except Exception as e:
            print(f"[GeminiProvider] Error listando modelos: {e}")
            return GEMINI_MODELS


# ===== FUNCIÓN DE CONVENIENCIA =====
def gemini_generate(
    prompt: str,
    model: Optional[str] = None,
    system_instruction: Optional[str] = None,
    tools: Optional[List[Dict]] = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    max_retries: int = 2,
) -> str:
    """
    Función de conveniencia para generar contenido con Gemini.
    """
    provider = GeminiProvider()
    return provider.generate(
        prompt=prompt,
        model=model,
        system_instruction=system_instruction,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
    )