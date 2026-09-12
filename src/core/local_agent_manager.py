# local_agent_manager.py - GESTOR DE AGENTE LOCAL (OLLAMA) PARA AP0L0

import os
import re
import json
import sys
import time
import requests
from urllib.parse import urlparse
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path

# ===== CONFIGURACIÓN DE AP0L0 =====
try:
    from src.core.config import get_base_dir, get_config, CONFIG_DIR
except ImportError:
    # Fallback
    BASE_DIR = Path(__file__).resolve().parent.parent
    CONFIG_DIR = BASE_DIR / "config"
    
    def get_base_dir():
        return BASE_DIR
    
    def get_config():
        try:
            with open(CONFIG_DIR / "api_keys.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

# ===== OPENAI COMPATIBILITY =====
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
    print("[LocalAgent] ⚠️ openai no instalado. pip install openai")

# ===== LOGGER SIMPLE =====
def _log(msg, level="INFO"):
    print(f"[LocalAgent] {level}: {msg}")


class JarvisLocalAgentManager:
    """
    Gestor para el agente local basado en Ollama.
    Proporciona una interfaz unificada para usar modelos locales (Ornith, Dolphin, etc.).
    """
    
    def __init__(self, model_name: Optional[str] = None, base_url: Optional[str] = None):
        config = get_config()
        self.base_url = base_url or config.get("ollama_url", "http://localhost:11434/v1")
        self.model = model_name or config.get("ollama_model", "dolphin3")
        self._client = None
        self._is_ready = None
        self._status_code = None
        
        _log(f"Inicializado con modelo '{self.model}' en {self.base_url}")
    
    @property
    def client(self):
        """Inicializa el cliente OpenAI de forma perezosa."""
        if self._client is None and OpenAI is not None:
            try:
                self._client = OpenAI(
                    base_url=self.base_url,
                    api_key="ollama-local",
                    timeout=300.0
                )
            except Exception as e:
                _log(f"Error inicializando cliente: {e}", "ERROR")
                self._client = None
        return self._client
    
    def _get_ollama_tags_url(self) -> str:
        """Construye la URL de tags de Ollama."""
        parsed = urlparse(self.base_url)
        return f"{parsed.scheme}://{parsed.netloc}/api/tags"
    
    def check_system(self) -> Tuple[bool, str]:
        """
        Verifica si Ollama está funcionando y el modelo está descargado.
        
        Returns:
            Tuple[bool, str]: (Está_Listo, Código_Error)
                - Códigos: "OK", "OLLAMA_NOT_RUNNING", "MODEL_NOT_PULLED", "INVALID_RESPONSE"
        """
        api_url = self._get_ollama_tags_url()
        
        try:
            response = requests.get(api_url, timeout=3.0)
            if response.status_code != 200:
                return False, "OLLAMA_NOT_RUNNING"
        except requests.exceptions.RequestException:
            return False, "OLLAMA_NOT_RUNNING"
        
        try:
            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            
            # Buscar el modelo exacto o con :latest
            model_found = False
            model_base = self.model.split(":")[0]
            for m in models:
                if m == self.model:
                    model_found = True
                    break
                if m == f"{self.model}:latest":
                    model_found = True
                    break
                if self.model == f"{m}:latest":
                    model_found = True
                    break
                # Buscar por nombre base (ej: "dolphin" en "dolphin3")
                if model_base in m:
                    model_found = True
                    break
            
            if not model_found:
                return False, "MODEL_NOT_PULLED"
        except (ValueError, KeyError) as e:
            _log(f"Error parseando respuesta: {e}", "ERROR")
            return False, "INVALID_RESPONSE"
        
        self._is_ready = True
        self._status_code = "OK"
        return True, "OK"
    
    def display_onboarding(self, status: str) -> None:
        """Muestra una guía de instalación para Ollama."""
        print("\n" + "=" * 75)
        print(" 🤖 INICIALIZACIÓN DEL AGENTE LOCAL ".center(75, "="))
        print("=" * 75)
        
        if status == "OLLAMA_NOT_RUNNING":
            print("\n ❌ Ollama no está ejecutándose o instalado en esta máquina.")
            print("    Es un servicio gratuito que permite ejecutar modelos de IA localmente.")
        elif status == "MODEL_NOT_PULLED":
            print(f"\n ❌ El modelo '{self.model}' no está descargado en tu máquina.")
        else:
            print("\n ❌ Error desconocido con el servicio local.")
        
        print("\n 💡 ¿Por qué usar este agente local?")
        print("    • 100% Privado: Todos los datos quedan en tu máquina.")
        print("    • 100% Gratuito: Sin claves API ni suscripciones.")
        print("    • Autónomo: La IA usa tu GPU o CPU local.")
        
        print(f"\n 📦 Espacio requerido: ~4-8 GB para el modelo '{self.model}'.")
        
        print("\n 🚀 GUÍA DE INSTALACIÓN PASO A PASO:")
        print("    ─────────────────────────────────────────────────────")
        print("    1. Ve a https://ollama.com y descarga Ollama.")
        print("    2. Instala Ollama y ejecútalo en segundo plano.")
        print("    3. Abre un terminal (CMD/PowerShell) y ejecuta:")
        print(f"       > ollama pull {self.model}")
        print("    4. Espera a que se descargue el modelo (puede tardar unos minutos).")
        print("    5. Reinicia AP0L0. ¡Ya está listo!")
        print("    ─────────────────────────────────────────────────────\n")
    
    def clean_thinking(self, text: str, strip_thinking: bool = True) -> str:
        """
        Limpia las etiquetas <think> de la respuesta (Qwen, DeepSeek, etc.).
        """
        if not text:
            return ""
        
        if strip_thinking:
            cleaned = re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL)
            cleaned = cleaned.replace("<think>", "").replace("</think>", "")
            return cleaned.strip()
        return text.strip()
    
    def generate_response(self, messages: List[Dict[str, str]], strip_thinking: bool = True) -> Optional[str]:
        """
        Genera una respuesta usando el agente local.
        
        Args:
            messages: Lista de mensajes en formato [{"role": "user", "content": "..."}]
            strip_thinking: Si debe eliminar las etiquetas <think>
        
        Returns:
            str: Respuesta del modelo o None si falló.
        """
        # Verificar estado del sistema
        is_ok, status = self.check_system()
        if not is_ok:
            self.display_onboarding(status)
            return None
        
        if self.client is None:
            _log("Cliente OpenAI no disponible", "ERROR")
            return None
        
        try:
            # Usar API compatible con OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.6,
                max_tokens=4096,
            )
            raw_text = response.choices[0].message.content
            return self.clean_thinking(raw_text, strip_thinking=strip_thinking)
        
        except Exception as e:
            _log(f"Error generando respuesta: {e}", "ERROR")
            return None
    
    def generate_stream(self, messages: List[Dict[str, str]], strip_thinking: bool = True):
        """
        Genera una respuesta en streaming usando el agente local.
        
        Args:
            messages: Lista de mensajes.
            strip_thinking: Si debe eliminar las etiquetas <think>
        
        Yields:
            str: Fragmentos de la respuesta.
        """
        # Verificar estado del sistema
        is_ok, status = self.check_system()
        if not is_ok:
            self.display_onboarding(status)
            yield None
            return
        
        if self.client is None:
            _log("Cliente OpenAI no disponible", "ERROR")
            yield None
            return
        
        try:
            # Usar API compatible con OpenAI con streaming
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.6,
                max_tokens=4096,
                stream=True
            )
            
            buffer = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    buffer += content
                    # Si el strip_thinking está activado, acumular y limpiar al final
                    if not strip_thinking:
                        yield content
                    else:
                        # Limpiar en tiempo real (más complejo, mejor al final)
                        pass
            
            if strip_thinking and buffer:
                yield self.clean_thinking(buffer, strip_thinking=True)
        
        except Exception as e:
            _log(f"Error generando streaming: {e}", "ERROR")
            yield None
    
    def get_available_models(self) -> List[str]:
        """Retorna la lista de modelos disponibles en Ollama."""
        api_url = self._get_ollama_tags_url()
        try:
            response = requests.get(api_url, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                return [m.get("name", "") for m in data.get("models", [])]
        except Exception as e:
            _log(f"Error obteniendo modelos: {e}", "ERROR")
        return []
    
    def pull_model(self, model_name: Optional[str] = None) -> bool:
        """
        Descarga un modelo de Ollama.
        
        Args:
            model_name: Nombre del modelo a descargar (usa self.model si no se especifica).
        
        Returns:
            bool: True si se descargó correctamente.
        """
        target = model_name or self.model
        api_url = self._get_ollama_tags_url().replace("/api/tags", "/api/pull")
        
        try:
            _log(f"Descargando modelo '{target}'...")
            response = requests.post(
                api_url,
                json={"name": target},
                stream=True,
                timeout=3600  # 1 hora máximo
            )
            if response.status_code == 200:
                _log(f"✅ Modelo '{target}' descargado correctamente.")
                return True
            else:
                _log(f"Error descargando: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            _log(f"Error: {e}", "ERROR")
            return False


# ===== FUNCIÓN PARA AP0L0 =====

def get_local_agent(model: Optional[str] = None) -> JarvisLocalAgentManager:
    """
    Retorna una instancia del agente local.
    
    Args:
        model: Nombre del modelo (opcional).
    
    Returns:
        JarvisLocalAgentManager: Instancia del gestor.
    """
    return JarvisLocalAgentManager(model_name=model)


# Compatibilidad con JarvisLive y acciones antiguas que importan un objeto
# global llamado ``local_agent``. La inicialización es local y perezosa: no
# contacta con Ollama hasta que se invoca check_system/generate_response.
local_agent = get_local_agent()


def local_agent_chat(params: Dict[str, Any], player=None, speak=None) -> str:
    """
    Función de punto de entrada para chat con el agente local.
    
    Parámetros:
        message (str): Mensaje para el agente (obligatorio)
        model (str): Modelo a usar (opcional)
        strip_thinking (bool): Eliminar etiquetas <think> (default: True)
    
    Returns:
        str: Respuesta del agente.
    """
    message = params.get("message", "").strip()
    model = params.get("model", None)
    strip_thinking = params.get("strip_thinking", True)
    
    if not message:
        return "❌ Necesito un mensaje para el agente local, señor."
    
    if player:
        player.write_log(f"[LocalAgent] Procesando: {message[:50]}...")
    
    agent = JarvisLocalAgentManager(model_name=model)
    
    # Verificar estado
    is_ok, status = agent.check_system()
    if not is_ok:
        agent.display_onboarding(status)
        return "⚠️ El agente local no está disponible. Revisa la guía de instalación."
    
    # Construir mensajes
    messages = [
        {"role": "system", "content": "Eres JARVIS, un asistente IA útil y conciso. Responde en español."},
        {"role": "user", "content": message}
    ]
    
    # Generar respuesta
    response = agent.generate_response(messages, strip_thinking=strip_thinking)
    if response:
        if speak:
            speak(response)
        return response
    else:
        return "❌ El agente local no pudo generar una respuesta."
