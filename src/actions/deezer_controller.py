# src/actions/deezer_controller.py
"""
Controlador de Deezer para AP0L0
Versión completa desde JARVIS
Soporte: abrir, buscar, reproducir/pausar, siguiente, anterior, volumen
"""

import time
import subprocess
import asyncio

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pyperclip
except ImportError:
    pyperclip = None


def _focus_deezer() -> bool:
    """Pone la ventana de Deezer en primer plano. Retorna True si se encontró."""
    try:
        import win32gui
        import win32con
    except ImportError:
        return False

    candidatos = []
    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            titulo = win32gui.GetWindowText(hwnd)
            if "Deezer" in titulo:
                candidatos.append(hwnd)
    win32gui.EnumWindows(_cb, None)
    if not candidatos:
        return False
    hwnd = candidatos[0]
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        return True
    except Exception:
        return False


async def deezer_ouvrir() -> str:
    """Abre Deezer si no está abierto y lo enfoca."""
    try:
        if _focus_deezer():
            return "Deezer ya está abierto, lo he puesto en primer plano."

        # Protocolo de Windows para Deezer
        subprocess.Popen(["explorer", "deezer:"], shell=False)
        time.sleep(4)
        _focus_deezer()
        return "Deezer lanzado."
    except Exception as e:
        return f"No pude abrir Deezer: {e}"


async def deezer_lecture_pause() -> str:
    """Alterna reproducción/pausa usando tecla multimedia."""
    if pyautogui:
        pyautogui.press('playpause')
        return "Reproducción/Pausa."
    return "Control multimedia no disponible."


async def deezer_suivant() -> str:
    """Canción siguiente."""
    if pyautogui:
        pyautogui.press('nexttrack')
        return "Canción siguiente."
    return "Control multimedia no disponible."


async def deezer_precedent() -> str:
    """Canción anterior."""
    if pyautogui:
        pyautogui.press('prevtrack')
        return "Canción anterior."
    return "Control multimedia no disponible."


async def deezer_stop() -> str:
    """Detiene la reproducción (pausa)."""
    _focus_deezer()
    time.sleep(0.2)
    if pyautogui:
        pyautogui.press('playpause')
        return "Música pausada."
    return "Control multimedia no disponible."


async def deezer_volume(direction: str, pasos: int = 4) -> str:
    """
    Ajusta el volumen del sistema (Deezer no tiene atajo propio, usamos volumen global).
    direction: "monter" o "baisser"
    """
    for _ in range(int(pasos)):
        if direction in ("monter", "up", "augmenter", "plus"):
            if pyautogui:
                pyautogui.press('volumeup')
        else:
            if pyautogui:
                pyautogui.press('volumedown')
        time.sleep(0.05)
    msg = "Volumen subido" if direction in ("monter", "up", "augmenter", "plus") else "Volumen bajado"
    return f"{msg}."


async def deezer_rechercher(recherche: str) -> str:
    """
    Busca y reproduce una canción/artista en Deezer.
    """
    if not pyautogui or not pyperclip:
        return "pyautogui o pyperclip no instalados."

    if not _focus_deezer():
        await deezer_ouvrir()
        time.sleep(3)
        _focus_deezer()
    time.sleep(0.5)

    # Raccourci de búsqueda Ctrl+F
    pyautogui.hotkey('ctrl', 'f')
    time.sleep(0.5)

    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyperclip.copy(recherche)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.2)
    pyautogui.press('enter')
    time.sleep(2.0)

    # Seleccionar primer resultado y reproducir
    pyautogui.press('enter')
    time.sleep(0.5)
    pyautogui.press('enter')

    return f"Buscando y reproduciendo '{recherche}' en Deezer."


# ===== FUNCIÓN EXPORTABLE PARA AP0L0 =====

async def deezer_control(params: dict, player=None, speak=None) -> str:
    """
    Punto de entrada para el sistema de herramientas.
    Parámetros:
        action: "open", "play", "pause", "next", "prev", "stop", "volume", "search"
        query: (para search)
        direction: "up"/"down" (para volume)
        steps: número de pasos (para volume)
    """
    action = params.get("action", "").lower()
    query = params.get("query", "")
    direction = params.get("direction", "up")
    steps = params.get("steps", 4)

    if action == "open":
        result = await deezer_ouvrir()
    elif action == "play" or action == "pause":
        result = await deezer_lecture_pause()
    elif action == "next":
        result = await deezer_suivant()
    elif action == "prev":
        result = await deezer_precedent()
    elif action == "stop":
        result = await deezer_stop()
    elif action == "volume":
        result = await deezer_volume(direction, steps)
    elif action == "search":
        if not query:
            return "Falta el término de búsqueda."
        result = await deezer_rechercher(query)
    else:
        result = f"Acción '{action}' no soportada."

    if speak:
        speak(result)
    if player:
        player.write_log(f"[Deezer] {result}")
    return result