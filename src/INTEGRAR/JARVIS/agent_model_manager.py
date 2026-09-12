import builtins
import json
import os

RUTA_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_model_config.json")

# Diccionario de modelos disponibles por agente
MODELOS_DISPONIBLES = {
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
    "Mistral": [
        "mistral-large-latest",
        "mistral-small-latest",
        "open-mixtral-8x22b"
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
    ]
}

# Modelos locales disponibles mediante Ollama (id_ollama -> info)
MODELOS_LOCALES_OLLAMA = {
    "dolphin3": {
        "label": "🐬 Dolphin 3.0 (Sin censura, ~4.5 GB)",
        "size_hint": "~4.5 GB VRAM",
        "keywords": ["dolphin", "hermes", "uncensored", "wizardlm-uncensored"]
    },
    "phi3.5": {
        "label": "🔷 Phi-3.5 Mini (Microsoft, ~2.2 GB VRAM)",
        "size_hint": "~2.2 GB VRAM",
        "keywords": ["phi3.5", "phi-3.5", "phi3:mini", "phi3"]
    },
    "llama3.1:8b": {
        "label": "🦙 Llama 3.1 8B (Meta, ~5 GB VRAM)",
        "size_hint": "~5 GB VRAM",
        "keywords": ["llama3.1", "llama3.1:8b", "llama-3.1", "meta-llama-3.1"]
    }
}

# Modelos por defecto
MODELOS_POR_DEFECTO = {
    "Gemini": "gemini-3.1-flash-lite",
    "Grok": "grok-beta",
    "Claude": "claude-3-5-sonnet-20241022",
    "Mistral": "mistral-large-latest",
    "Groq": "llama-3.3-70b-versatile",
    "Ollama": "dolphin3",
    "LocalModel": "dolphin3",
    "ChatGPT": "gpt-5.6-sol"
}

def cargar_modelos_elegidos():
    """Carga los modelos preferidos desde el JSON o devuelve los valores por defecto."""
    try:
        if os.path.exists(RUTA_CONFIG):
            with open(RUTA_CONFIG, "r", encoding="utf-8") as f:
                config = json.load(f)
                modelos_cargados = config.get("chosen_models", {})
                
                # Fusionar con los valores por defecto para evitar claves faltantes
                resultado = MODELOS_POR_DEFECTO.copy()
                for agente, modelo in modelos_cargados.items():
                    if agente in resultado and modelo in MODELOS_DISPONIBLES.get(agente, []):
                        resultado[agente] = modelo
                return resultado
    except Exception as e:
        print(f"[AGENTE MODELO] Error al cargar los modelos: {e}")
    return MODELOS_POR_DEFECTO.copy()

def guardar_modelos_elegidos(diccionario_modelos):
    """Guarda el diccionario de modelos elegidos en el JSON."""
    try:
        with open(RUTA_CONFIG, "w", encoding="utf-8") as f:
            json.dump({"chosen_models": diccionario_modelos}, f)
        print(f"[AGENTE MODELO] Modelos guardados en la configuración.")
    except Exception as e:
        print(f"[AGENTE MODELO] Error al guardar los modelos: {e}")

def obtener_info_modelos_agente(modelos_actuales):
    """Devuelve la estructura completa para construir la interfaz web."""
    return {
        "available_models": MODELOS_DISPONIBLES,
        "current_models": modelos_actuales,
        "local_ollama_models": MODELOS_LOCALES_OLLAMA
    }

def obtener_modelos_locales_ollama():
    """Devuelve el registro de modelos locales de Ollama disponibles."""
    return MODELOS_LOCALES_OLLAMA

def obtener_modelo_local_preferido(diccionario_config: dict) -> str:
    """Devuelve el modelo local preferido desde la configuración (por defecto: dolphin3)."""
    return diccionario_config.get("preferred_local_model", "dolphin3")

def establecer_modelos_agente(nuevos_modelos_dict):
    """Actualiza y guarda los modelos."""
    # Validación
    modelos_validos = MODELOS_POR_DEFECTO.copy()
    for agente, modelo in nuevos_modelos_dict.items():
        if agente in MODELOS_DISPONIBLES and modelo in MODELOS_DISPONIBLES[agente]:
            modelos_validos[agente] = modelo
            
    builtins.CHOSEN_MODELS = modelos_validos
    guardar_modelos_elegidos(modelos_validos)
    return modelos_validos