# src/core/multi_provider.py
"""
Proveedor múltiple de IA que combina Gemini, OpenRouter, Groq, Ollama y OpenAI.
Integra los módulos locales groq_ai.py y llm.py del usuario (ahora desde src/core).
Con reintentos, fallback automático y caché.
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import threading
import logging

# Configurar logging silencioso
logger = logging.getLogger("MultiProvider")
logger.setLevel(logging.WARNING)

# ===== CONFIGURACIÓN =====
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
CACHE_DIR = BASE_DIR / "cache" / "llm"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = 3600

_cache = {}
_cache_lock = threading.Lock()


def _get_config() -> Dict[str, Any]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_cache_key(prompt: str, model: str, system: str = "") -> str:
    content = f"{prompt}|{model}|{system}"
    return hashlib.md5(content.encode()).hexdigest()


def _get_from_cache(key: str) -> Optional[str]:
    with _cache_lock:
        if key in _cache:
            entry = _cache[key]
            if time.time() - entry["timestamp"] < CACHE_TTL:
                return entry["value"]
            else:
                del _cache[key]
    return None


def _save_to_cache(key: str, value: str):
    with _cache_lock:
        _cache[key] = {"value": value, "timestamp": time.time()}


class MultiProvider:
    """
    Proveedor múltiple con fallback automático.
    """

    def __init__(self):
        self.config = _get_config()
        self.gemini_models = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.7-flash"]
        self.openrouter_model = "meta-llama/llama-3-70b-instruct"
        self.groq_model = "mixtral-8x7b-32768"
        self.ollama_model = self.config.get("ollama_model", "qwen2.5:3b")
        self.ollama_url = self.config.get("ollama_url", "http://localhost:11434")
        self.openai_model = "gpt-3.5-turbo"

        # Inicialización perezosa: no creamos clientes hasta que se necesiten
        self._gemini_client = None
        self._openai_client = None
        self._groq_client = None

        # No imprimimos mensajes de inicialización aquí

        self.stats = {
            "gemini": {"success": 0, "fail": 0},
            "openrouter": {"success": 0, "fail": 0},
            "groq": {"success": 0, "fail": 0},
            "ollama": {"success": 0, "fail": 0},
            "openai": {"success": 0, "fail": 0},
            "groq_local": {"success": 0, "fail": 0},
            "llm_local": {"success": 0, "fail": 0},
        }

    def _init_gemini(self):
        if self._gemini_client is None:
            try:
                from google import genai
                if self.config.get("gemini_api_key"):
                    self._gemini_client = genai.Client(api_key=self.config["gemini_api_key"])
                else:
                    self._gemini_client = None
            except ImportError:
                self._gemini_client = None

    def _init_openai(self):
        if self._openai_client is None:
            try:
                import openai
                if self.config.get("openai_api_key"):
                    self._openai_client = openai.OpenAI(api_key=self.config["openai_api_key"])
                else:
                    self._openai_client = None
            except ImportError:
                self._openai_client = None

    def _init_groq(self):
        if self._groq_client is None:
            try:
                import groq
                if self.config.get("groq_api_key"):
                    self._groq_client = groq.Groq(api_key=self.config["groq_api_key"])
                else:
                    self._groq_client = None
            except ImportError:
                self._groq_client = None

    # ===== LLAMADAS A CADA PROVEEDOR =====

    def _call_gemini(self, prompt: str, system: str = "", temperature: float = 0.7) -> Tuple[Optional[str], str]:
        self._init_gemini()
        if self._gemini_client is None:
            return None, "gemini_not_available"
        for model in self.gemini_models:
            try:
                from google.genai import types
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=2000,
                )
                if system:
                    config.system_instruction = system
                response = self._gemini_client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                if response and response.text:
                    text = response.text.strip()
                    if text:
                        self.stats["gemini"]["success"] += 1
                        return text, f"gemini/{model}"
            except Exception as e:
                self.stats["gemini"]["fail"] += 1
                logger.debug(f"Gemini {model} falló: {e}")
                time.sleep(0.5)
                continue
        return None, "gemini_all_failed"

    def _call_openrouter(self, prompt: str, system: str = "", temperature: float = 0.7) -> Tuple[Optional[str], str]:
        try:
            import requests
        except ImportError:
            return None, "openrouter_requests_missing"
        api_key = self.config.get("openrouter_api_key")
        if not api_key:
            return None, "openrouter_no_key"
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.openrouter_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2000,
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if content:
                    self.stats["openrouter"]["success"] += 1
                    return content.strip(), "openrouter"
            else:
                self.stats["openrouter"]["fail"] += 1
                logger.debug(f"OpenRouter error {response.status_code}: {response.text[:200]}")
        except Exception as e:
            self.stats["openrouter"]["fail"] += 1
            logger.debug(f"OpenRouter falló: {e}")
        return None, "openrouter_failed"

    def _call_groq_api(self, prompt: str, system: str = "", temperature: float = 0.7) -> Tuple[Optional[str], str]:
        self._init_groq()
        if self._groq_client is None:
            return None, "groq_not_available"
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = self._groq_client.chat.completions.create(
                model=self.groq_model,
                messages=messages,
                temperature=temperature,
                max_tokens=2000,
            )
            if response and response.choices:
                content = response.choices[0].message.content
                if content:
                    self.stats["groq"]["success"] += 1
                    return content.strip(), "groq_api"
        except Exception as e:
            self.stats["groq"]["fail"] += 1
            logger.debug(f"Groq API falló: {e}")
        return None, "groq_api_failed"

    def _call_groq_local(self, prompt: str, system: str = "", temperature: float = 0.7) -> Tuple[Optional[str], str]:
        try:
            from src.core.groq_ai import get_response as groq_local_response
        except ImportError:
            return None, "groq_local_not_available"
        try:
            response = groq_local_response(prompt)
            if response:
                self.stats["groq_local"]["success"] += 1
                return response, "groq_local"
        except Exception as e:
            self.stats["groq_local"]["fail"] += 1
            logger.debug(f"Groq local falló: {e}")
        return None, "groq_local_failed"

    def _call_llm_local(self, prompt: str, system: str = "", temperature: float = 0.7) -> Tuple[Optional[str], str]:
        try:
            from src.core.llm import get_llm_output as local_llm_response
        except ImportError:
            return None, "llm_local_not_available"
        try:
            result = local_llm_response(prompt)
            if isinstance(result, dict):
                text = result.get("text", "")
                if text:
                    self.stats["llm_local"]["success"] += 1
                    return text, "llm_local"
            elif isinstance(result, str):
                if result:
                    self.stats["llm_local"]["success"] += 1
                    return result, "llm_local"
        except Exception as e:
            self.stats["llm_local"]["fail"] += 1
            logger.debug(f"LLM local falló: {e}")
        return None, "llm_local_failed"

    def _call_ollama(self, prompt: str, system: str = "", temperature: float = 0.7) -> Tuple[Optional[str], str]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            import ollama
            response = ollama.chat(model=self.ollama_model, messages=messages,
                                   options={"temperature": temperature})
            content = response.get("message", {}).get("content", "") if response else ""
            if content:
                self.stats["ollama"]["success"] += 1
                return content.strip(), f"ollama/{self.ollama_model}"
        except ImportError:
            pass
        except Exception as e:
            self.stats["ollama"]["fail"] += 1
            logger.debug(f"Ollama falló: {e}")

        # Cliente HTTP de respaldo: funciona aunque el paquete ollama no esté
        # instalado y permite usar el mismo daemon en Windows, Linux, macOS y
        # Android/Termux cuando Ollama esté disponible por red.
        try:
            import requests
            response = requests.post(
                f"{self.ollama_url.rstrip('/')}/api/chat",
                json={"model": self.ollama_model, "messages": messages,
                      "stream": False, "options": {"temperature": temperature}},
                timeout=120,
            )
            if response.ok:
                content = response.json().get("message", {}).get("content", "")
                if content:
                    self.stats["ollama"]["success"] += 1
                    return content.strip(), f"ollama/{self.ollama_model}"
        except Exception as e:
            self.stats["ollama"]["fail"] += 1
            logger.debug(f"Ollama HTTP falló: {e}")
        return None, "ollama_failed"

    def _call_openai(self, prompt: str, system: str = "", temperature: float = 0.7) -> Tuple[Optional[str], str]:
        self._init_openai()
        if self._openai_client is None:
            return None, "openai_not_available"
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = self._openai_client.chat.completions.create(
                model=self.openai_model,
                messages=messages,
                temperature=temperature,
                max_tokens=2000,
            )
            if response and response.choices:
                content = response.choices[0].message.content
                if content:
                    self.stats["openai"]["success"] += 1
                    return content.strip(), "openai"
        except Exception as e:
            self.stats["openai"]["fail"] += 1
            logger.debug(f"OpenAI falló: {e}")
        return None, "openai_failed"

    # ===== MÉTODO PRINCIPAL =====

    def generate(
        self,
        prompt: str,
        system_instruction: str = "",
        temperature: float = 0.7,
        use_cache: bool = True,
    ) -> Tuple[Optional[str], str]:
        if use_cache:
            cache_key = _get_cache_key(prompt, "multi", system_instruction)
            cached = _get_from_cache(cache_key)
            if cached:
                return cached, "cache"

        mode = str(self.config.get("connection_mode", "auto")).lower()
        cloud = [("gemini", self._call_gemini), ("openrouter", self._call_openrouter),
                 ("groq_api", self._call_groq_api), ("openai", self._call_openai)]
        # Ollama es el único backend garantizado sin Internet. Los módulos
        # históricos groq_local/llm_local pueden envolver APIs remotas, por lo
        # que no se incluyen en el modo local estricto.
        local = [("ollama", self._call_ollama)]
        # auto/cloud prioriza nube y solo cae a local si no hay clave, red o
        # cuota. local nunca realiza llamadas externas.
        providers = local if mode == "local" else (cloud if mode == "cloud" else cloud + local)

        for name, func in providers:
            result, provider_name = func(prompt, system_instruction, temperature)
            if result:
                if use_cache:
                    _save_to_cache(cache_key, result)
                return result, provider_name

        return None, "all_failed"

    def generate_local(self, prompt: str, system_instruction: str = "",
                       temperature: float = 0.7) -> Tuple[Optional[str], str]:
        """Genera exclusivamente con proveedores locales, sin red externa."""
        for _, func in (("ollama", self._call_ollama),):
            result, provider = func(prompt, system_instruction, temperature)
            if result:
                return result, provider
        return None, "local_unavailable"

    def generate_with_retry(
        self,
        prompt: str,
        system_instruction: str = "",
        temperature: float = 0.7,
        max_retries: int = 3,
    ) -> Tuple[Optional[str], str]:
        for attempt in range(max_retries):
            result, provider = self.generate(prompt, system_instruction, temperature)
            if result:
                return result, provider
            if attempt < max_retries - 1:
                delay = 1.5 ** attempt
                logger.debug(f"Reintentando en {delay:.1f}s...")
                time.sleep(delay)
        return None, "all_failed_after_retries"

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        return self.stats

    def reset_stats(self):
        for k in self.stats:
            self.stats[k] = {"success": 0, "fail": 0}


def generate_with_fallback(prompt: str, system: str = "", temperature: float = 0.7) -> str:
    provider = MultiProvider()
    result, provider_name = provider.generate(prompt, system, temperature)
    if result:
        return result
    return "Lo siento, no pude generar una respuesta en este momento."
