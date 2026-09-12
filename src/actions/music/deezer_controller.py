# deezer_controller.py - VERSIÓN COMPLETA PARA AP0L0

import os
import time
import subprocess
import sys

try:
    import pyautogui
except ImportError:
    pyautogui = None
    print("[Deezer] pyautogui no instalado. Algunas funciones no funcionarán.")

try:
    import pyperclip
except ImportError:
    pyperclip = None
    print("[Deezer] pyperclip no instalado. El pegado no funcionará.")

# ===== CONSTANTES =====
IS_WINDOWS = sys.platform == "win32"


def _focus_deezer():
    """Pone la ventana de Deezer en primer plano."""
    if not IS_WINDOWS:
        return False
    
    try:
        import win32gui
        import win32con
    except ImportError:
        print("[Deezer] win32gui no instalado. pip install pywin32")
        return False
    
    candidates = []
    
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "Deezer" in title:
                candidates.append(hwnd)
    
    win32gui.EnumWindows(callback, None)
    
    if not candidates:
        return False
    
    hwnd = candidates[0]
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        return True
    except Exception as e:
        print(f"[Deezer] Error al enfocar: {e}")
        return False


def deezer_ouvrir():
    """Abre Deezer si no está abierto."""
    try:
        if _focus_deezer():
            return "Deezer ya está abierto, señor."
        
        # Abrir con el protocolo de Windows
        if IS_WINDOWS:
            subprocess.Popen(["explorer", "deezer:"], shell=False)
        else:
            # En Mac/Linux, intentar abrir de otra forma
            subprocess.Popen(["open", "-a", "Deezer"]) if sys.platform == "darwin" else None
        
        time.sleep(4)
        _focus_deezer()
        return "Deezer abierto, señor."
    except Exception as e:
        return f"No pude abrir Deezer: {e}"


def deezer_play_pause():
    """Alterna play/pause."""
    if pyautogui is None:
        return "pyautogui no instalado"
    pyautogui.press('playpause')
    return "Play/Pause en Deezer."


def deezer_siguiente():
    """Pista siguiente."""
    if pyautogui is None:
        return "pyautogui no instalado"
    pyautogui.press('nexttrack')
    return "Pista siguiente."


def deezer_anterior():
    """Pista anterior."""
    if pyautogui is None:
        return "pyautogui no instalado"
    pyautogui.press('prevtrack')
    return "Pista anterior."


def deezer_stop():
    """Pausa la reproducción."""
    if pyautogui is None:
        return "pyautogui no instalado"
    _focus_deezer()
    time.sleep(0.2)
    pyautogui.press('playpause')
    return "Música en pausa."


def deezer_volumen(direccion, pasos=4):
    """Sube o baja el volumen."""
    if pyautogui is None:
        return "pyautogui no instalado"
    
    time.sleep(0.2)
    for _ in range(int(pasos)):
        if direccion in ("subir", "up", "arriba", "mas", "+"):
            pyautogui.press('volumeup')
        else:
            pyautogui.press('volumedown')
        time.sleep(0.05)
    
    msg = "Volumen subido" if direccion in ("subir", "up", "arriba", "mas", "+") else "Volumen bajado"
    return f"{msg} en Deezer."


def deezer_buscar(termino):
    """Busca en Deezer."""
    if pyautogui is None:
        return "pyautogui no instalado"
    if pyperclip is None:
        return "pyperclip no instalado"
    
    if not _focus_deezer():
        deezer_ouvrir()
        time.sleep(3)
        _focus_deezer()
    
    time.sleep(0.5)
    pyautogui.hotkey('ctrl', 'f')
    time.sleep(0.5)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyperclip.copy(termino)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.2)
    pyautogui.press('enter')
    time.sleep(2.0)
    pyautogui.press('enter')
    
    return f"Buscando '{termino}' en Deezer."


def deezer_abrir_url(url):
    """Abre una URL en Deezer (playlist, álbum, canción)."""
    try:
        subprocess.Popen(["explorer", url], shell=False)
        time.sleep(3)
        _focus_deezer()
        return f"Abriendo en Deezer: {url}"
    except Exception as e:
        return f"Error al abrir URL: {e}"


# ===== FUNCIÓN PRINCIPAL PARA AP0L0 =====

def deezer_control(params, player=None, speak=None):
    """
    Función de punto de entrada para AP0L0.
    
    Parámetros:
        action (str): "open", "play", "pause", "next", "prev", "stop", "volume", "search", "url"
        direction (str): "up" o "down" (para volume)
        steps (int): Número de pasos (para volume)
        query (str): Término de búsqueda (para search)
        url (str): URL de Deezer (para url)
    """
    action = params.get("action", "status").lower()
    
    if action == "open":
        result = deezer_ouvrir()
    elif action == "play":
        result = deezer_play_pause()
    elif action == "pause":
        result = deezer_stop()
    elif action == "next":
        result = deezer_siguiente()
    elif action == "prev":
        result = deezer_anterior()
    elif action == "stop":
        result = deezer_stop()
    elif action == "volume":
        direction = params.get("direction", "up")
        steps = params.get("steps", 4)
        result = deezer_volumen(direction, steps)
    elif action == "search":
        query = params.get("query", "")
        if not query:
            return "Necesito un término de búsqueda."
        result = deezer_buscar(query)
    elif action == "url":
        url = params.get("url", "")
        if not url:
            return "Necesito una URL de Deezer."
        result = deezer_abrir_url(url)
    else:
        return f"Acción '{action}' no soportada. Usa: open, play, pause, next, prev, stop, volume, search, url"
    
    if player:
        player.write_log(f"[Deezer] {action}: {result[:50]}...")
    
    if speak:
        speak(result)
    
    return result