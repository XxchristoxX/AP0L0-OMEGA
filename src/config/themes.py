# src/config/themes.py
"""
Mapas de personalidad, colores y voces para AP0L0.
"""

# ===== VOCES =====
# Esta tabla es la fuente única para la relación personalidad → voz.  Debe
# coincidir con PERSONALITY_INFO para evitar que el overlay y el agente
# seleccionen voces diferentes para la misma personalidad.
VOICE_MAP = {
    "jarvis": "Charon",
    "agata": "Puck",
    "tony": "Charon",
    "apolo": "Zephyr",
    "friday": "Puck",
}
DEFAULT_VOICE = VOICE_MAP["apolo"]

# ===== TEMAS =====
THEME_MAP = {
    "jarvis": "#00d4ff",
    "agata": "#ff6b9d",
    "tony": "#ff6b00",
    "apolo": "#00ff88",
    "friday": "#9b59b6",
}
DEFAULT_THEME = "#00d4ff"

# ===== NOMBRES Y SUBTÍTULOS =====
PERSONALITY_NAMES = {
    "jarvis": "JARVIS",
    "agata": "AGATA",
    "tony": "TONY",
    "friday": "FRIDAY",
    "apolo": "APOLO",
}

PERSONALITY_SUBTITLES = {
    "jarvis": "Just A Rather Very Intelligent System",
    "agata": "Advanced Generative Assistant for Technology & Art",
    "tony": "Technology Oriented Network Yield",
    "friday": "Female Replacement Intelligent Digital Assistant Youth",
    "apolo": "Autonomous Platform for Orchestration, Learning and Operations",
}

EDGE_TTS_VOICES = {
    "jarvis": "es-ES-ElviraNeural",
    "agata": "es-ES-ElviraNeural",
    "tony": "es-ES-AlvaroNeural",
    "friday": "es-ES-ElviraNeural",
    "apolo": "es-ES-AlvaroNeural",
}
DEFAULT_EDGE_VOICE = "es-ES-ElviraNeural"
