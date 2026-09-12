# src/actions/clipboard_intelligence.py
# Procesa el contenido del portapapeles: traducir, resumir, explicar, corregir.
# También incluye modo proactivo (monitoreo automático con sugerencias).

import sys
import json
import time
import threading
from pathlib import Path

import pyperclip

# ===== FUNCIONES AUXILIARES =====
def _get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _get_api_key():
    path = _get_base_dir() / "config" / "api_keys.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


# ===== CLASE PRINCIPAL =====
class ClipboardIntelligence:
    def __init__(self):
        print("[ClipboardIntelligence] Inicializado.")

    def _get_clipboard_text(self):
        try:
            return pyperclip.paste().strip()
        except Exception:
            return ""

    def _call_gemini(self, prompt: str) -> str:
        from google import genai
        client = genai.Client(api_key=_get_api_key())
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip()

    def translate(self, target_lang: str = "spanish") -> str:
        text = self._get_clipboard_text()
        if not text:
            return "No hay texto en el portapapeles."
        prompt = f"Traduce el siguiente texto al {target_lang}:\n\n{text}"
        return self._call_gemini(prompt)

    def summarize(self) -> str:
        text = self._get_clipboard_text()
        if not text:
            return "No hay texto en el portapapeles."
        prompt = f"Resume el siguiente texto en 3-5 frases:\n\n{text}"
        return self._call_gemini(prompt)

    def explain(self) -> str:
        text = self._get_clipboard_text()
        if not text:
            return "No hay texto en el portapapeles."
        prompt = f"Explica el siguiente texto de forma clara y sencilla:\n\n{text}"
        return self._call_gemini(prompt)

    def correct(self) -> str:
        text = self._get_clipboard_text()
        if not text:
            return "No hay texto en el portapapeles."
        prompt = f"Corrige los errores gramaticales y de estilo del siguiente texto:\n\n{text}"
        return self._call_gemini(prompt)


# ===== MODO PROACTIVO (FUNCIÓN DE NIVEL SUPERIOR) =====
def start_proactive_mode(parameters: dict = None, player=None, speak=None) -> str:
    """
    Inicia el modo proactivo del portapapeles.
    Monitorea el portapapeles y sugiere acciones automáticamente.
    """
    import threading
    import time
    import pyperclip

    # Variable para controlar si el modo ya está activo (evitar duplicados)
    if not hasattr(start_proactive_mode, "_running"):
        start_proactive_mode._running = False

    if start_proactive_mode._running:
        return "El modo proactivo del portapapeles ya está activo."

    start_proactive_mode._running = True

    def _monitor():
        clipboard_intel = ClipboardIntelligence()
        last_text = ""
        # Intentar importar langdetect opcionalmente
        try:
            from langdetect import detect
            has_langdetect = True
        except ImportError:
            has_langdetect = False

        while start_proactive_mode._running:
            try:
                current = pyperclip.paste()
                if current and current != last_text and len(current) > 20:
                    last_text = current
                    # Detectar idioma si es posible
                    lang = "unknown"
                    if has_langdetect:
                        try:
                            lang = detect(current)
                        except:
                            pass

                    # Determinar acción sugerida según el contenido
                    if "?" in current:
                        action = "explain"
                        action_text = "explicar"
                    elif len(current) > 100:
                        action = "summarize"
                        action_text = "resumir"
                    else:
                        action = "translate"
                        action_text = "traducir"

                    # Mostrar sugerencia en la UI
                    if player:
                        player.write_log(f"📋 Portapapeles: texto copiado ({lang}). ¿Quieres {action_text}?")
                    if speak:
                        speak(f"Portapapeles: texto copiado. ¿Quieres {action_text}? Di 'yes' para {action_text}, 'no' para ignorar.")
                time.sleep(1)
            except Exception as e:
                if player:
                    player.write_log(f"⚠️ Error en modo proactivo: {e}")
                time.sleep(2)

        start_proactive_mode._running = False

    thread = threading.Thread(target=_monitor, daemon=True)
    thread.start()
    return "Modo proactivo del portapapeles iniciado."


def stop_proactive_mode(parameters: dict = None, player=None, speak=None) -> str:
    """
    Detiene el modo proactivo del portapapeles.
    """
    if hasattr(start_proactive_mode, "_running") and start_proactive_mode._running:
        start_proactive_mode._running = False
        if speak:
            speak("Modo proactivo del portapapeles detenido.")
        return "Modo proactivo del portapapeles detenido."
    else:
        return "El modo proactivo del portapapeles no está activo."


def clipboard_proactive(parameters: dict = None, player=None, speak=None) -> str:
    """
    Función de punto de entrada unificada para la herramienta 'clipboard_proactive'.
    Soporta: on, start, off, stop, toggle, status.
    """
    action = "toggle"
    if isinstance(parameters, dict):
        action = parameters.get("action") or "toggle"
    elif isinstance(parameters, str):
        action = parameters

    action = str(action).lower().strip()

    is_running = getattr(start_proactive_mode, "_running", False)

    if action in ("on", "start", "activar", "activado", "enable"):
        if is_running:
            return "El modo proactivo del portapapeles ya está activo."
        return start_proactive_mode(parameters, player, speak)

    elif action in ("off", "stop", "desactivar", "desactivado", "disable"):
        if not is_running:
            return "El modo proactivo del portapapeles no está activo."
        return stop_proactive_mode(parameters, player, speak)

    elif action in ("status", "estado"):
        status_text = "activo" if is_running else "inactivo"
        return f"El modo proactivo del portapapeles está {status_text}."

    elif action in ("toggle", "cambiar"):
        if is_running:
            return stop_proactive_mode(parameters, player, speak)
        else:
            return start_proactive_mode(parameters, player, speak)

    else:
        if is_running:
            return "El modo proactivo del portapapeles ya está activo."
        return start_proactive_mode(parameters, player, speak)