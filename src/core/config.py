# src/core/config.py
"""
Configuración centralizada para AP0L0 OMEGA.
Soporta OpenRouter (principal) y Gemini REST (fallback).
"""

import os
import sys
import json
import re
import ctypes
import platform as _platform
import subprocess as _subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any

# ──────────────────────────────────────────────────────────────
# EXCEPCIONES
# ──────────────────────────────────────────────────────────────

class ReconnectException(Exception):
    """Excepción lanzada cuando se necesita reconectar el asistente."""
    pass

# ──────────────────────────────────────────────────────────────
# UTILIDADES
# ──────────────────────────────────────────────────────────────

def is_admin():
    if os.name != 'nt':
        return os.geteuid() == 0
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent

BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "src" / "config"
API_CONFIG_PATH = CONFIG_DIR / "api_keys.json"
PROMPT_PATH = BASE_DIR / "src" / "core" / "prompt.txt"

# ──────────────────────────────────────────────────────────────
# CONSTANTES
# ──────────────────────────────────────────────────────────────

# Modelos por defecto (fallback)
LIVE_MODEL = "gemini-2.5-flash-native-audio-latest"
LITE_MODEL = "gemini-3.5-flash-lite"
PLANNER_MODEL = "gemini-3.5-flash-lite"
AUDIO_MODEL = "gemini-2.5-flash-native-audio-latest"

# Lista de fallback para LIVE API (en orden de preferencia)
DEFAULT_LIVE_MODELS_FALLBACK = [
    "gemini-2.5-flash-native-audio-latest",
    "gemini-2.5-flash-native-audio-preview-09-2025",
    "gemini-2.5-flash-native-audio-preview-12-2025",
    "gemini-robotics-er-2-streaming-preview",
    "gemini-3.5-live-translate-preview"
]

# Audio
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

# Voces y temas
VOICE_MAP = {
    "jarvis": "Charon",
    "agata": "Puck",
    "tony": "Charon",
    "apolo": "Zephyr",
    "friday": "Puck",
}
DEFAULT_VOICE = VOICE_MAP["apolo"]

THEME_MAP = {
    "jarvis": "#00d4ff",
    "agata": "#ff6b9d",
    "tony": "#ff6b00",
    "apolo": "#00ff88",
    "friday": "#9b59b6",
}
DEFAULT_THEME = THEME_MAP["apolo"]

# ──────────────────────────────────────────────────────────────
# CARGA DE CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────

def _get_config() -> dict:
    defaults = {
        "assistant_name": "APOLO",
        "assistant_subtitle": "Autonomous Platform for Orchestration, Learning and Operations",
        "user_name": "Christopher",
        "personality": "apolo",
        "voice": VOICE_MAP["apolo"],
        "ui_language": "es",
        "response_mode": "voice_text",
        "focus_mode": False,
        "vad_enabled": False,
        "rag_enabled": False,
        "sync_system_theme": False,
        "wallpaper_path": "",
        "ui_color": THEME_MAP["apolo"],
        "ui_main_bg": "#00060a",
        "ui_log_bg": "#010d14",
        "ui_log_text": "#8ffcff",
        "ui_news_bg": "#010f18",
        "ui_news_text": "#5ab8cc",
        "ui_input_bg": "#000d14",
        "ui_input_text": "#d8f8ff",
        "ui_button_bg": "#00d4ff",
        "ui_button_text": "#000000",
        "ui_title_color": "#00d4ff",
        "ui_status_color": "#00ff88",
        "ui_border_color": "#0d3347",
        "ui_font_size": 10,
        "ui_icon_path": "face.png",
        "shortcut_name": "APOLO AI",
        "shortcut_icon": "",
        "font_size_header": 10,
        "font_size_left": 10,
        "font_size_right": 10,
        "font_size_center": 10,
        "font_size_footer": 10,
        "badge1_text": "AI CORE ACTIVE",
        "badge2_text": "SEC CLEARED",
        "badge3_text": "PROTOCOL XLIX",
        "badge4_text": "READY",
        "badge5_text": "ONLINE",
        "badge1_color": "#00ff88",
        "badge2_color": "#00d4ff",
        "badge3_color": "#5ab8cc",
        "badge4_color": "#ffcc00",
        "badge5_color": "#ff6b00",
        "enable_animations": True,
        "enable_sounds": True,
        "show_timestamps": True,
        "auto_scroll_log": True,
        "morning_brief_enabled": True,
        "camera_index": 0,
        "ollama_model": "qwen2.5:3b",
        "ollama_url": "http://localhost:11434",
        "vosk_model_path": "models/vosk-model-es",
        "connection_mode": "auto",
        "openrouter_api_key": "",
        "groq_api_key": "",
        "gemini_api_key": "",
        "stt_engine": "Vosk (Offline)",
        "llm_engine": "Gemini (Cloud)",
        "tts_engine": "pyttsx3 (Local)",
        "auto_learn_enabled": True,
        "auto_learn_interval": 600,
        "planner_enabled": True,
        "gesture_control_enabled": False,
        "face_auth_enabled": False,
        "face_auth_confidence": 0.6,
        "face_user_id": "default_user",
        "force_local_mode": False,
        # ⭐ NUEVOS CAMPOS
        "preferred_llm": "openrouter",
        "openrouter_model": "google/gemini-2.5-flash",
        "gemini_available": False,
        "use_gemini_live": False,
    }
    try:
        if API_CONFIG_PATH.exists():
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in defaults.items():
                if k not in data:
                    data[k] = v
            return data
        else:
            return defaults
    except Exception as e:
        print(f"[ERROR] No se pudo leer la configuración: {e}")
        return defaults

def _get_api_key() -> str:
    cfg = _get_config()
    return cfg.get("gemini_api_key", "")

def _get_openrouter_key() -> str:
    cfg = _get_config()
    return cfg.get("openrouter_api_key", "")

def _validate_api_key(key: str) -> bool:
    if not key or len(key) < 20:
        return False
    # Aceptar tanto AIza como AQ.
    if not key.startswith(("AIza", "AQ.")):
        return False
    return True

def _is_gemini_live_available() -> bool:
    """Verifica si Gemini Live está disponible."""
    cfg = _get_config()
    key = cfg.get("gemini_api_key", "")
    # Solo AIza es válido para Live, AQ. no funciona
    return key.startswith("AIza") and len(key) > 20

def _load_system_prompt(assistant_name: str = "APOLO", subtitle: str = "") -> str:
    try:
        prompt = PROMPT_PATH.read_text(encoding="utf-8")
        prompt = prompt.replace("{assistant_name}", assistant_name)
        prompt = prompt.replace("{assistant_subtitle}", subtitle)
        return prompt
    except Exception:
        return (
            f"Your name is {assistant_name}. {subtitle} "
            "You are an advanced AI assistant. Be concise, direct, and always use the provided tools. "
            "Never simulate results — always call the appropriate tool."
        )

_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)
def _clean_transcript(text: str) -> str:
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()

# ──────────────────────────────────────────────────────────────
# FUNCIONES DE ACCESO (COMPATIBILIDAD)
# ──────────────────────────────────────────────────────────────

def get_api_key() -> str:
    return _get_api_key()

def get_config() -> dict:
    return _get_config()


def _save_config(data: dict) -> bool:
    """Guarda la configuración de forma atómica y multiplataforma.

    Se conserva el nombre privado porque varios módulos históricos lo
    importan directamente. La escritura temporal evita dejar un JSON corrupto
    si el proceso se interrumpe durante el guardado.
    """
    if not isinstance(data, dict):
        raise TypeError("La configuración debe ser un diccionario")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    temporary = API_CONFIG_PATH.with_suffix(".tmp")
    try:
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, API_CONFIG_PATH)
        return True
    except Exception as exc:
        try:
            temporary.unlink(missing_ok=True)
        except Exception:
            pass
        print(f"[CONFIG] No se pudo guardar la configuración: {exc}")
        return False

def get_live_model_list() -> list[str]:
    cfg = _get_config()
    models = cfg.get("live_models_fallback")
    if models and isinstance(models, list) and len(models) > 0:
        return models
    return DEFAULT_LIVE_MODELS_FALLBACK

def get_selected_live_model() -> str:
    return get_live_model_list()[0]

def get_selected_text_model() -> str:
    cfg = _get_config()
    return cfg.get("selected_text_model", LITE_MODEL)

# ──────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL: GENERACIÓN CON FALLBACK
# ──────────────────────────────────────────────────────────────

def gemini_generate(prompt: str, model: str = LITE_MODEL, system_instruction: str = None) -> str:
    """
    Genera contenido usando el mejor proveedor disponible:
    1. OpenRouter (siempre disponible)
    2. Gemini REST (solo si la clave es válida)
    """
    cfg = _get_config()
    
    # ── 1. INTENTAR OPENROUTER (PRINCIPAL) ──
    openrouter_key = cfg.get("openrouter_api_key", "")
    if openrouter_key and len(openrouter_key) > 20:
        try:
            import requests
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openrouter_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": cfg.get("openrouter_model", "google/gemini-2.5-flash"),
                    "messages": messages,
                    "max_tokens": 4000,
                    "temperature": 0.7
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                print(f"[OpenRouter] Error {response.status_code}: {response.text[:100]}")
        except Exception as e:
            print(f"[OpenRouter] Error: {e}")
    
    # ── 2. FALLBACK A GEMINI REST ──
    gemini_key = cfg.get("gemini_api_key", "")
    if gemini_key and _validate_api_key(gemini_key):
        try:
            import google.genai as genai
            from google.genai import types
            
            client = genai.Client(api_key=gemini_key)
            model_to_use = model or get_selected_text_model()
            
            config = types.GenerateContentConfig(max_output_tokens=4000)
            if system_instruction:
                config.system_instruction = system_instruction
            
            response = client.models.generate_content(
                model=model_to_use,
                contents=prompt,
                config=config
            )
            return response.text.strip() if response and response.text else ""
        except Exception as e:
            print(f"[Gemini REST] Error: {e}")
    
    # ── 3. FALLBACK A OLLAMA (LOCAL) ──
    try:
        import requests
        ollama_url = cfg.get("ollama_url", "http://localhost:11434")
        ollama_model = cfg.get("ollama_model", "qwen2.5:3b")
        
        response = requests.post(
            f"{ollama_url}/api/chat",
            json={
                "model": ollama_model,
                "messages": [
                    {"role": "system", "content": system_instruction or "Eres un asistente útil."},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {"num_predict": 4000}
            },
            timeout=120
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("message", {}).get("content", "")
    except Exception as e:
        print(f"[Ollama] Error: {e}")
    
    return "[Error] No se pudo generar una respuesta. Verifica tu conexión a internet y las claves API."

# ──────────────────────────────────────────────────────────────
# FUNCIONES PARA GEMINI LIVE (CON VALIDACIÓN)
# ──────────────────────────────────────────────────────────────

def is_gemini_live_available() -> bool:
    """Verifica si Gemini Live está disponible."""
    return _is_gemini_live_available()

def get_gemini_live_client():
    """Obtiene el cliente de Gemini Live solo si está disponible."""
    if not is_gemini_live_available():
        return None
    try:
        import google.genai as genai
        return genai.Client(api_key=_get_api_key())
    except Exception:
        return None

# ──────────────────────────────────────────────────────────────
# PERSONALIDADES
# ──────────────────────────────────────────────────────────────

PERSONALITY_INFO = {
    "jarvis": {
        "name": "JARVIS",
        "subtitle": "Just A Rather Very Intelligent System",
        "voice": "Charon",
        "color": "#00d4ff"
    },
    "agata": {
        "name": "AGATA",
        "subtitle": "Advanced Generative Assistant for Technology & Art",
        "voice": "Puck",
        "color": "#ff6b9d"
    },
    "tony": {
        "name": "TONY",
        "subtitle": "Technology Oriented Network Yield",
        "voice": "Charon",
        "color": "#ff6b00"
    },
    "friday": {
        "name": "FRIDAY",
        "subtitle": "Female Replacement Intelligent Digital Assistant Youth",
        "voice": "Puck",
        "color": "#9b59b6"
    },
    "apolo": {
        "name": "APOLO",
        "subtitle": "Autonomous Platform for Orchestration, Learning and Operations",
        "voice": "Zephyr",
        "color": "#00ff88"
    }
}

DEFAULT_PERSONALITY = "apolo"
DEFAULT_THEME = "#00ff88"
DEFAULT_VOICE = "Zephyr"
