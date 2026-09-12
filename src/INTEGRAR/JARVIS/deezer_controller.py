try:
    import pyautogui
except ImportError:
    pyautogui = None
import time
import pyperclip
import asyncio
import subprocess
import os

# DEEZER
# ==========================================

def _enfocar_deezer():
    """Pone la ventana de Deezer en primer plano. Devuelve True si se encuentra."""
    import win32gui, win32con
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

async def deezer_abrir():
    """Abre Deezer si no está ya abierto."""
    try:
        if _enfocar_deezer():
            return "Deezer ya está abierto, Christopher, lo he puesto en primer plano."
        
        # El protocolo básico de Windows para Deezer
        subprocess.Popen(["explorer", "deezer:"], shell=False)
        time.sleep(4)
        _enfocar_deezer()
        return "Deezer abierto, Christopher."
    except Exception as e:
        return f"No he podido abrir Deezer: {e}"

async def deezer_reproducir_pausa():
    """Alternar reproducción/pausa mediante la tecla multimedia global."""
    pyautogui.press('playpause')
    return "Reproducción/Pausa, Christopher."

async def deezer_siguiente():
    """Pista siguiente mediante la tecla multimedia global."""
    pyautogui.press('nexttrack')
    return "Pista siguiente en Deezer, Christopher."

async def deezer_anterior():
    """Pista anterior mediante la tecla multimedia global."""
    pyautogui.press('prevtrack')
    return "Pista anterior en Deezer, Christopher."

async def deezer_detener():
    """Pausa."""
    _enfocar_deezer()
    time.sleep(0.2)
    pyautogui.press('playpause')
    return "Música en pausa en Deezer, Christopher."

async def deezer_volumen(direccion, escalones=4):
    """Sube o baja el volumen general del PC ya que Deezer no tiene un atajo de volumen universal simple."""
    time.sleep(0.2)
    for _ in range(int(escalones)):
        if direccion in ("subir", "up", "aumentar", "mas"):
            pyautogui.press('volumeup')
        else:
            pyautogui.press('volumedown')
        time.sleep(0.05)
    msg = "Volumen subido" if direccion in ("subir", "up", "aumentar", "mas") else "Volumen bajado"
    return f"{msg}, Christopher."

async def deezer_buscar(busqueda):
    """Abre la búsqueda de Deezer, escribe la consulta y valida."""
    if not _enfocar_deezer():
        await deezer_abrir()
        time.sleep(3)
        _enfocar_deezer()
    time.sleep(0.5)

    # Ctrl+F es el atajo de búsqueda clásico en muchas aplicaciones
    pyautogui.hotkey('ctrl', 'f')
    time.sleep(0.5)

    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyperclip.copy(busqueda)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.2)
    pyautogui.press('enter')
    
    time.sleep(2.0)
    
    # Validar el primer resultado
    pyautogui.press('enter')
    time.sleep(0.5)
    
    # Intentar pulsar la barra espaciadora para reproducir si está enfocado,
    # si no, las teclas multimedia retoman el control
    pyautogui.press('enter')
    
    return f"Hecho Christopher, busco '{busqueda}' en Deezer."