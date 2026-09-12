# src/actions/spotify_controller.py
"""
Controlador de Spotify para AP0L0
Versión completa desde JARVIS
Soporte: abrir, buscar, reproducir/pausar, siguiente, anterior, volumen
"""

import os
import time
import subprocess
import re
from typing import Optional

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import psutil
except ImportError:
    psutil = None


def _focus_spotify() -> bool:
    """Pone la ventana de Spotify en primer plano. Retorna True si se encontró."""
    try:
        import win32gui
        import win32con
    except ImportError:
        return False

    candidatos = []
    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            titulo = win32gui.GetWindowText(hwnd)
            if "Spotify" in titulo:
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


async def spotify_ouvrir() -> str:
    """Abre Spotify si no está abierto y lo enfoca."""
    try:
        if _focus_spotify():
            return "Spotify ya está abierto, lo he puesto en primer plano."

        # Intentar con la ruta del instalador
        ruta = os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")
        if os.path.exists(ruta):
            subprocess.Popen([ruta])
        else:
            # Versión de Microsoft Store
            subprocess.Popen(["explorer", "spotify:"], shell=False)
        time.sleep(4)
        _focus_spotify()
        return "Spotify lanzado."
    except Exception as e:
        return f"No pude abrir Spotify: {e}"


async def spotify_lecture_pause() -> str:
    """Alterna reproducción/pausa usando tecla multimedia."""
    if pyautogui:
        pyautogui.press('playpause')
        return "Reproducción/Pausa."
    return "Control multimedia no disponible (pyautogui no instalado)."


async def spotify_suivant() -> str:
    """Canción siguiente."""
    if pyautogui:
        pyautogui.press('nexttrack')
        return "Canción siguiente."
    return "Control multimedia no disponible."


async def spotify_precedent() -> str:
    """Canción anterior."""
    if pyautogui:
        pyautogui.press('prevtrack')
        return "Canción anterior."
    return "Control multimedia no disponible."


async def spotify_stop() -> str:
    """Detiene la reproducción (pausa)."""
    _focus_spotify()
    time.sleep(0.2)
    if pyautogui:
        pyautogui.press('playpause')
        return "Música pausada."
    return "Control multimedia no disponible."


def spotify_lancer_playlist(playlist_uri: str = "") -> bool:
    """
    Lanza una playlist o pista de Spotify (URI o URL web).
    Retorna True si se logró.
    """
    try:
        # Convertir URL web a URI nativa
        if playlist_uri.startswith("https://open.spotify.com/"):
            m = re.search(r'/(track|playlist|album|artist)/([A-Za-z0-9]+)', playlist_uri)
            if m:
                playlist_uri = f"spotify:{m.group(1)}:{m.group(2)}"

        # Enfocar o abrir Spotify
        ya_abierto = _focus_spotify()
        if playlist_uri:
            subprocess.Popen(["explorer", playlist_uri], shell=False)
            time.sleep(3)
        elif not ya_abierto:
            ruta = os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")
            if os.path.exists(ruta):
                subprocess.Popen([ruta])
            else:
                subprocess.Popen(["explorer", "spotify:"], shell=False)
            time.sleep(4)

        _focus_spotify()
        return True
    except Exception as e:
        print(f"[Spotify] Error lanzando playlist: {e}")
        return False


async def spotify_volume(direction: str, pasos: int = 4) -> str:
    """
    Ajusta el volumen de Spotify (Ctrl+Arriba/Abajo).
    direction: "monter" o "baisser"
    """
    if not _focus_spotify():
        return "Spotify no está abierto."
    time.sleep(0.2)
    for _ in range(int(pasos)):
        if direction in ("monter", "up", "augmenter", "plus"):
            if pyautogui:
                pyautogui.hotkey('ctrl', 'up')
        else:
            if pyautogui:
                pyautogui.hotkey('ctrl', 'down')
        time.sleep(0.05)
    msg = "Volumen subido" if direction in ("monter", "up", "augmenter", "plus") else "Volumen bajado"
    return f"{msg} en Spotify."


async def spotify_rechercher(recherche: str) -> str:
    """
    Busca y reproduce una canción/artista en Spotify.
    """
    if not pyautogui or not pyperclip:
        return "pyautogui o pyperclip no instalados."

    if not _focus_spotify():
        await spotify_ouvrir()
        time.sleep(3)
        _focus_spotify()
    time.sleep(0.5)

    # Raccourci de búsqueda (Ctrl+K o Ctrl+L)
    pyautogui.hotkey('ctrl', 'l')
    time.sleep(0.5)
    pyautogui.hotkey('ctrl', 'k')
    time.sleep(0.4)

    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyperclip.copy(recherche)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.2)
    pyautogui.press('enter')
    time.sleep(2.0)

    # Intentar abrir el primer resultado y reproducir
    pyautogui.press('enter')
    time.sleep(1.0)
    pyautogui.press('enter')
    time.sleep(0.5)
    pyautogui.press('enter')

    return f"Buscando y reproduciendo '{recherche}' en Spotify."


# ===== FUNCIÓN EXPORTABLE PARA AP0L0 =====

async def spotify_control(params: dict, player=None, speak=None) -> str:
    """
    Punto de entrada para el sistema de herramientas.
    Parámetros:
        action: "open", "play", "pause", "next", "prev", "stop", "volume", "search", "playlist"
        query: (para search)
        direction: "up"/"down" (para volume)
        steps: número de pasos (para volume)
        uri: URI de playlist (para playlist)
    """
    action = params.get("action", "").lower()
    query = params.get("query", "")
    direction = params.get("direction", "up")
    steps = params.get("steps", 4)
    uri = params.get("uri", "")

    if action == "open":
        result = await spotify_ouvrir()
    elif action == "play" or action == "pause":
        result = await spotify_lecture_pause()
    elif action == "next":
        result = await spotify_suivant()
    elif action == "prev":
        result = await spotify_precedent()
    elif action == "stop":
        result = await spotify_stop()
    elif action == "volume":
        result = await spotify_volume(direction, steps)
    elif action == "search":
        if not query:
            return "Falta el término de búsqueda."
        result = await spotify_rechercher(query)
    elif action == "playlist":
        if not uri:
            return "Falta la URI de la playlist."
        ok = spotify_lancer_playlist(uri)
        result = "Playlist lanzada." if ok else "No se pudo lanzar la playlist."
    else:
        result = f"Acción '{action}' no soportada."

    if speak:
        speak(result)
    if player:
        player.write_log(f"[Spotify] {result}")
    return result