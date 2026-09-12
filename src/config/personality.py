# config/personality.py
"""
Configuración de personalidades para AP0L0.
Centraliza nombres, subtítulos, voces y colores.
"""

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
DEFAULT_THEME = "#00d4ff"  # <--- AÑADIDO PARA CORREGIR EL ERROR DE IMPORTACIÓN

# Mapas auxiliares
VOICE_MAP = {k: v["voice"] for k, v in PERSONALITY_INFO.items()}
THEME_MAP = {k: v["color"] for k, v in PERSONALITY_INFO.items()}
NAME_MAP = {k: v["name"] for k, v in PERSONALITY_INFO.items()}
SUBTITLE_MAP = {k: v["subtitle"] for k, v in PERSONALITY_INFO.items()}