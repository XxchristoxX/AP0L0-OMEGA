# src/actions/aura_mode.py
"""
Modo Aura: IA avanzada con razonamiento profundo y creatividad mejorada.
"""

_aura_enabled = False

def toggle_aura_mode(parameters: dict = None, player=None, speak=None) -> str:
    global _aura_enabled
    action = parameters.get("action", "toggle") if parameters else "toggle"

    if action == "toggle":
        _aura_enabled = not _aura_enabled
    elif action == "on":
        _aura_enabled = True
    elif action == "off":
        _aura_enabled = False
    else:
        return f"Acción '{action}' no soportada. Usa: toggle, on, off."

    status = "activado" if _aura_enabled else "desactivado"
    if speak:
        speak(f"Modo Aura {status}, señor.")
    return f"Modo Aura {status}."

def get_aura_prompt() -> str:
    """Devuelve el prompt adicional para el modo Aura."""
    if not _aura_enabled:
        return ""
    return """
    [AURA MODE ACTIVATED]
    You are now in advanced reasoning mode.
    - Think deeply and creatively
    - Provide innovative solutions
    - Connect seemingly unrelated ideas
    - Be more philosophical and visionary
    - Challenge assumptions
    - Offer multiple perspectives
    """