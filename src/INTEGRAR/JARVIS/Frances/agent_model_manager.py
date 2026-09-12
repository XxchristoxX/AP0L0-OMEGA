import builtins
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_model_config.json")

# Dictionnaire complet des modeles disponibles par agent IA
AVAILABLE_MODELS = {
    "Gemini": [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-3.7-flash",
        "gemini-3.7-pro",
        "gemini-3.7-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.5-pro",
        "gemini-3.1-pro",
        "gemini-3.1-flash",
        "gemini-3.1-flash-lite",
        "gemini-2.0-pro-exp-02-05",
        "gemini-2.0-flash-thinking-exp-01-21",
        "gemini-2.0-flash-exp"
    ],
    "Claude": [
        "claude-3-7-sonnet-20250219",
        "claude-3-7-sonnet-latest",
        "claude-3-7-opus",
        "claude-3-7-haiku",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-20241022",
        "claude-3-5-haiku-latest",
        "claude-3-opus-20240229",
        "claude-3-opus-latest",
        "claude-3-haiku-20240307"
    ],
    "ChatGPT": [
        "gpt-4o",
        "gpt-4o-mini",
        "o1",
        "o1-preview",
        "o1-mini",
        "o3-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.6",
        "o4-mini",
        "o3",
        "o3-pro"
    ],
    "Grok": [
        "grok-3",
        "grok-3-mini",
        "grok-2",
        "grok-2-latest",
        "grok-2-1212",
        "grok-2-vision-1212",
        "grok-2-vision-latest",
        "grok-beta",
        "grok-4.5",
        "grok-4.3",
        "grok-4.20-0309-non-reasoning",
        "grok-4.20-0309-reasoning"
    ],
    "DeepSeek": [
        "deepseek-chat",
        "deepseek-reasoner",
        "deepseek-v3",
        "deepseek-r1"
    ],
    "Mistral": [
        "mistral-large-latest",
        "mistral-small-latest",
        "codestral-latest",
        "ministral-8b-latest",
        "ministral-3b-latest",
        "pixtral-large-latest",
        "pixtral-12b-2409",
        "open-mistral-nemo",
        "open-mixtral-8x22b",
        "open-mixtral-8x7b"
    ],
    "Groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant",
        "deepseek-r1-distill-llama-70b",
        "deepseek-r1-distill-qwen-32b",
        "qwen-2.5-32b",
        "qwen-2.5-coder-32b",
        "gemma2-9b-it",
        "gemma-7b-it",
        "mixtral-8x7b-32768"
    ],
    "Ollama": [
        "deepseek-r1:8b",
        "deepseek-r1:14b",
        "deepseek-r1:1.5b",
        "dolphin3",
        "llama3.3:70b",
        "llama3.1:8b",
        "llama3.2:3b",
        "llama3.2:1b",
        "llama3",
        "qwen2.5:7b",
        "qwen2.5-coder:7b",
        "phi4",
        "phi3.5",
        "mistral-nemo",
        "mistral",
        "gemma"
    ]
}

# Modeles locaux disponibles via Ollama (id_ollama -> info)
LOCAL_OLLAMA_MODELS = {
    "dolphin3": {
        "label": "🐬 Dolphin 3.0 (Uncensored, ~4.5 Go)",
        "size_hint": "~4.5 Go VRAM",
        "keywords": ["dolphin", "hermes", "uncensored", "wizardlm-uncensored"]
    },
    "deepseek-r1:8b": {
        "label": "🧠 DeepSeek R1 8B (Reasoning local, ~5 Go VRAM)",
        "size_hint": "~5 Go VRAM",
        "keywords": ["deepseek-r1", "deepseek-r1:8b", "r1:8b", "deepseek"]
    },
    "llama3.1:8b": {
        "label": "🦙 Llama 3.1 8B (Meta, ~5 Go VRAM)",
        "size_hint": "~5 Go VRAM",
        "keywords": ["llama3.1", "llama3.1:8b", "llama-3.1", "meta-llama-3.1"]
    },
    "llama3.2:3b": {
        "label": "⚡ Llama 3.2 3B (Meta ultra-léger, ~2 Go VRAM)",
        "size_hint": "~2 Go VRAM",
        "keywords": ["llama3.2", "llama3.2:3b", "llama-3.2"]
    },
    "phi3.5": {
        "label": "🔷 Phi-3.5 Mini (Microsoft, ~2.2 Go VRAM)",
        "size_hint": "~2.2 Go VRAM",
        "keywords": ["phi3.5", "phi-3.5", "phi3:mini", "phi3"]
    },
    "qwen2.5-coder:7b": {
        "label": "💻 Qwen 2.5 Coder 7B (Alibaba, ~4.5 Go VRAM)",
        "size_hint": "~4.5 Go VRAM",
        "keywords": ["qwen2.5-coder", "qwen2.5-coder:7b", "qwen-coder"]
    }
}

# Modeles par defaut
DEFAULT_MODELS = {
    "Gemini": "gemini-2.5-flash",
    "Grok": "grok-3",
    "Claude": "claude-3-7-sonnet-latest",
    "DeepSeek": "deepseek-chat",
    "Mistral": "mistral-large-latest",
    "Groq": "llama-3.3-70b-versatile",
    "Ollama": "dolphin3",
    "LocalModel": "dolphin3",
    "ChatGPT": "gpt-4o"
}

def load_chosen_models():
    """Charge les modeles preferes depuis le JSON ou retourne les defauts."""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                loaded_models = config.get("chosen_models", {})
                
                # Fusionner avec les valeurs par defaut pour eviter des cles manquantes
                result = DEFAULT_MODELS.copy()
                for agent, model in loaded_models.items():
                    if agent in AVAILABLE_MODELS:
                        # Si le modèle est dans la liste ou personnalisé
                        result[agent] = model
                return result
    except Exception as e:
        print(f"[AGENT MODELE] Erreur lors du chargement des modeles : {e}")
    return DEFAULT_MODELS.copy()

def save_chosen_models(models_dict):
    """Sauvegarde le dictionnaire de modeles choisis dans le JSON."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"chosen_models": models_dict}, f)
        print(f"[AGENT MODELE] Modeles sauvegardes dans la configuration.")
    except Exception as e:
        print(f"[AGENT MODELE] Erreur lors de la sauvegarde des modeles : {e}")

def get_agent_models_info(current_models):
    """Retourne la structure complete pour construire l'interface web."""
    return {
        "available_models": AVAILABLE_MODELS,
        "current_models": current_models,
        "local_ollama_models": LOCAL_OLLAMA_MODELS
    }

def get_local_ollama_models():
    """Retourne le registre des modeles locaux Ollama disponibles."""
    return LOCAL_OLLAMA_MODELS

def get_preferred_local_model(config_dict: dict) -> str:
    """Retourne le modele local prefere depuis la config (defaut: dolphin3)."""
    return config_dict.get("preferred_local_model", "dolphin3")

def set_agent_models(new_models_dict):
    """Mets a jour et sauvegarde les modeles."""
    # Validation
    valid_models = DEFAULT_MODELS.copy()
    if hasattr(builtins, "CHOSEN_MODELS") and builtins.CHOSEN_MODELS:
        valid_models.update(builtins.CHOSEN_MODELS)
    for agent, model in new_models_dict.items():
        if agent in AVAILABLE_MODELS:
            valid_models[agent] = model
            
    builtins.CHOSEN_MODELS = valid_models
    save_chosen_models(valid_models)
    return valid_models


