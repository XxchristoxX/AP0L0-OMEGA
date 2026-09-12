try:
    import pyautogui
except ImportError:
    pyautogui = None
import time
import pyperclip
import asyncio
try:
    import psutil
except ImportError:
    psutil = None
try:
    import requests
except ImportError:
    requests = None
import json
import os
import re
import subprocess

# SPOTIFY
# ==========================================

def _enfocar_spotify():
    """Pone la ventana de Spotify en primer plano. Devuelve True si se encuentra."""
    import win32gui, win32con
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

async def spotify_abrir():
    """Abre Spotify si no está ya abierto."""
    try:
        # ¿Ya abierto?
        if _enfocar_spotify():
            return "Spotify ya está abierto, Christopher, lo he puesto en primer plano."
        ruta = os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")
        if os.path.exists(ruta):
            subprocess.Popen([ruta])
        else:
            # Versión de Microsoft Store
            subprocess.Popen(["explorer", "spotify:"], shell=False)
        time.sleep(4)
        _enfocar_spotify()
        return "Spotify abierto, Christopher."
    except Exception as e:
        return f"No he podido abrir Spotify: {e}"

async def spotify_reproducir_pausa():
    """Alternar reproducción/pausa mediante la tecla multimedia global."""
    pyautogui.press('playpause')
    return "Reproducción/Pausa, Christopher."

async def spotify_siguiente():
    """Pista siguiente mediante la tecla multimedia global."""
    pyautogui.press('nexttrack')
    return "Pista siguiente, Christopher."

async def spotify_anterior():
    """Pista anterior mediante la tecla multimedia global."""
    pyautogui.press('prevtrack')
    return "Pista anterior, Christopher."

async def spotify_detener():
    """Pausa (Spotify no tiene un stop real)."""
    _enfocar_spotify()
    time.sleep(0.2)
    pyautogui.press('playpause')
    return "Música en pausa, Christopher."

def spotify_lanzar_playlist(uri_playlist: str = "") -> bool:
    """Abre Spotify y reproduce una playlist/pista mediante su URI o URL web.
    Se puede usar desde código síncrono (ejecutar_accion_pc).
    Devuelve True si tiene éxito."""
    try:
        # Convertir URL web open.spotify.com → URI nativa spotify:
        if uri_playlist.startswith("https://open.spotify.com/"):
            m = re.search(r'/(track|playlist|album|artist)/([A-Za-z0-9]+)', uri_playlist)
            if m:
                uri_playlist = f"spotify:{m.group(1)}:{m.group(2)}"

        ya_abierto = False
        try:
            ya_abierto = _enfocar_spotify()
        except Exception:
            pass

        if uri_playlist:
            # El protocolo spotify: es manejado por Windows → abre la aplicación y navega
            subprocess.Popen(["explorer", uri_playlist], shell=False)
            time.sleep(3)
        elif not ya_abierto:
            ruta = os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")
            if os.path.exists(ruta):
                subprocess.Popen([ruta])
            else:
                subprocess.Popen(["explorer", "spotify:"], shell=False)
            time.sleep(4)

        try:
            _enfocar_spotify()
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"[SPOTIFY] Error al lanzar playlist: {e}")
        return False

async def spotify_volumen(direccion, escalones=4):
    """Sube o baja el volumen de Spotify mediante Ctrl+Arriba/Abajo."""
    if not _enfocar_spotify():
        return "Spotify no parece estar abierto, Christopher."
    time.sleep(0.2)
    for _ in range(int(escalones)):
        if direccion in ("subir", "up", "aumentar", "mas"):
            pyautogui.hotkey('ctrl', 'up')
        else:
            pyautogui.hotkey('ctrl', 'down')
        time.sleep(0.05)
    msg = "Volumen subido" if direccion in ("subir", "up", "aumentar", "mas") else "Volumen bajado"
    return f"{msg} en Spotify, Christopher."

async def spotify_buscar(busqueda):
    """Abre la barra de búsqueda de Spotify, escribe la consulta y valida."""
    import pyperclip
    # Spotify debe estar abierto
    if not _enfocar_spotify():
        await spotify_abrir()
        time.sleep(3)
        _enfocar_spotify()
    time.sleep(0.5)

    # Atajo Ctrl+L para ir a la barra de búsqueda (todas las versiones)
    pyautogui.hotkey('ctrl', 'l')
    time.sleep(0.5)
    # Fallback Ctrl+K (nueva interfaz de Spotify)
    pyautogui.hotkey('ctrl', 'k')
    time.sleep(0.4)

    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyperclip.copy(busqueda)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.2)
    pyautogui.press('enter')
    
    # Esperar un poco más para asegurar que los resultados estén cargados
    time.sleep(2.0)
    
    # Pulsar Enter para validar la búsqueda (abre el álbum/artista si es el caso)
    pyautogui.press('enter')
    time.sleep(1.0)
    
    # Pulsar Enter una segunda vez para reproducir el primer elemento
    # Es más fiable que Tab+Enter que puede derivar a otros botones
    pyautogui.press('enter')
    time.sleep(0.5)
    
    # Seguridad adicional: si ya estaba seleccionado pero en pausa
    pyautogui.press('enter')
    
    return f"Hecho Christopher, reproduzco '{busqueda}' en Spotify."