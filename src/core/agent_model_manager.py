# agent_model_manager.py - GESTOR DE MODELOS POR AGENTE PARA AP0L0

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

# ===== CONFIGURACI車N DE AP0L0 =====
try:
    from src.core.config import get_base_dir, CONFIG_DIR
except ImportError:
    BASE_DIR = Path(__file__).resolve().parent.parent
    CONFIG_DIR = BASE_DIR / "config"
    
    def get_base_dir():
        return BASE_DIR

# ===== RUTA DE CONFIGURACI車N =====
CONFIG_PATH = CONFIG_DIR / "api_keys.json"

# ===== MODELOS DISPONIBLES (EN ESPA?OL) =====

AVAILABLE_MODELS: Dict[str, List[str]] = {
    "Gemini": [
        "gemini-3.5-flash",
        "gemini-3.1-pro",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash-exp"
    ],
    "Grok": [
        "grok-beta",
        "grok-2-1212",
        "grok-4.5",
        "grok-4.3",
        "grok-4.20-0309-non-reasoning",
        "grok-4.20-0309-reasoning"
    ],
    "Claude": [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-latest",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307"
    ],
    "Groq": [
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
        "gemma-7b-it"
    ],
    "Ollama": [
        "dolphin3",
        "phi3.5",
        "llama3.1:8b",
        "llama3",
        "mistral",
        "gemma"
    ],
    "ChatGPT": [
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.6",
        "o4-mini",
        "o3",
        "o3-pro"
    ],
    "Mistral": [
        "mistral-large-latest",
        "mistral-small-latest",
        "codestral-latest"
    ]
}

# ===== MODELOS LOCALES OLLAMA (EN ESPA?OL) =====

LOCAL_OLLAMA_MODELS: Dict[str, Dict[str, Any]] = {
    "dolphin3": {
        "label": "?? Dolphin 3.0 (Sin censura, ~4.5 GB)",
        "size_hint": "~4.5 GB VRAM",
        "keywords": ["dolphin", "hermes", "uncensored"]
    },
    "phi3.5": {
        "label": "?? Phi-3.5 Mini (Microsoft, ~2.2 GB VRAM)",
        "size_hint": "~2.2 GB VRAM",
        "keywords": ["phi3.5", "phi-3.5", "phi3:mini"]
    },
    "llama3.1:8b": {
        "label": "?? Llama 3.1 8B (Meta, ~5 GB VRAM)",
        "size_hint": "~5 GB VRAM",
        "keywords": ["llama3.1", "llama3.1:8b", "llama-3.1"]
    }
}

# ===== MODELOS POR DEFECTO =====

DEFAULT_MODELS: Dict[str, str] = {
    "Gemini": "gemini-3.1-flash-lite",
    "Grok": "grok-beta",
    "Claude": "claude-3-5-sonnet-20241022",
    "Mistral": "mistral-large-latest",
    "Groq": "llama-3.3-70b-versatile",
    "Ollama": "dolphin3",
    "LocalModel": "dolphin3",
    "ChatGPT": "gpt-5.6-sol"
}


def _load_config() -> Dict[str, Any]:
    """Carga la configuraci車n desde api_keys.json."""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[AgentModel] Error cargando config: {e}")
    return {}


def _save_config(config: Dict[str, Any]) -> None:
    """Guarda la configuraci車n en api_keys.json."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[AgentModel] Error guardando config: {e}")


def load_chosen_models() -> Dict[str, str]:
    """
    Carga los modelos preferidos desde la configuraci車n.
    
    Returns:
        Dict[str, str]: Diccionario con los modelos elegidos por agente.
    """
    config = _load_config()
    chosen = config.get("chosen_models", {})
    
    # Fusionar con defaults
    result = DEFAULT_MODELS.copy()
    for agent, model in chosen.items():
        if agent in result and model in AVAILABLE_MODELS.get(agent, []):
            result[agent] = model
    
    return result


def save_chosen_models(models_dict: Dict[str, str]) -> None:
    """
    Guarda los modelos preferidos en la configuraci車n.
    
    Args:
        models_dict: Diccionario con los modelos por agente.
    """
    config = _load_config()
    config["chosen_models"] = models_dict
    _save_config(config)
    print(f"[AgentModel] ? Modelos guardados: {models_dict}")


def get_agent_models_info(current_models: Dict[str, str]) -> Dict[str, Any]:
    """
    Retorna la estructura completa para la interfaz web.
    
    Args:
        current_models: Diccionario con los modelos actuales.
    
    Returns:
        Dict con available_models, current_models y local_ollama_models.
    """
    return {
        "available_models": AVAILABLE_MODELS,
        "current_models": current_models,
        "local_ollama_models": LOCAL_OLLAMA_MODELS
    }


def get_local_ollama_models() -> Dict[str, Dict[str, Any]]:
    """Retorna el registro de modelos locales Ollama disponibles."""
    return LOCAL_OLLAMA_MODELS


def set_agent_models(new_models_dict: Dict[str, str]) -> Dict[str, str]:
    """
    Actualiza y guarda los modelos.
    
    Args:
        new_models_dict: Nuevos modelos por agente.
    
    Returns:
        Dict[str, str]: Modelos validados y guardados.
    """
    valid_models = DEFAULT_MODELS.copy()
    for agent, model in new_models_dict.items():
        if agent in AVAILABLE_MODELS and model in AVAILABLE_MODELS[agent]:
            valid_models[agent] = model
    
    save_chosen_models(valid_models)
    return valid_models


def get_preferred_local_model() -> str:
    """Retorna el modelo local preferido desde la configuraci車n."""
    config = _load_config()
    return config.get("preferred_local_model", "dolphin3")


def set_preferred_local_model(model: str) -> None:
    """Guarda el modelo local preferido en la configuraci車n."""
    if model in LOCAL_OLLAMA_MODELS:
        config = _load_config()
        config["preferred_local_model"] = model
        _save_config(config)
        print(f"[AgentModel] ? Modelo local preferido: {model}")


# ===== FUNCI車N PARA AP0L0 =====

def get_model_for_agent(agent: str) -> str:
    """
    Obtiene el modelo configurado para un agente espec赤fico.
    
    Args:
        agent: Nombre del agente (Gemini, Grok, Claude, etc.)
    
    Returns:
        str: Nombre del modelo.
    """
    models = load_chosen_models()
    return models.get(agent, DEFAULT_MODELS.get(agent, "gemini-3.1-flash-lite"))