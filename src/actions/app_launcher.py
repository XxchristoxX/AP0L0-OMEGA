# app_launcher.py - VERSIÓN COMPLETA PARA AP0L0

import os
import sys
import subprocess
import shutil
import json
import time
from pathlib import Path

# ===== CONSTANTES DE SISTEMA =====
_OS = sys.platform
IS_WINDOWS = _OS == "win32"
IS_MAC = _OS == "darwin"
IS_LINUX = _OS.startswith("linux")

# ===== CONFIGURACIÓN DE AP0L0 =====
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


def _load_config():
    """Carga la configuración de AP0L0 desde api_keys.json."""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[AppLauncher] Error cargando config: {e}")
    return {}


def _save_config(config):
    """Guarda la configuración en api_keys.json."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[AppLauncher] Error guardando config: {e}")


def _find_exe_windows(exe_names, hints=None):
    """
    Encuentra un ejecutable en Windows usando múltiples métodos.
    
    Args:
        exe_names: Lista de nombres de ejecutables (ej: ['chrome.exe'])
        hints: Lista de rutas sugeridas (con variables de entorno)
    
    Returns:
        str: Ruta completa del ejecutable o None
    """
    if not IS_WINDOWS:
        return None
    
    # 1. Buscar en PATH del sistema
    for name in exe_names:
        found = shutil.which(name)
        if found:
            return found
    
    # 2. Buscar en el registro de Windows (App Paths)
    try:
        import winreg
        for name in exe_names:
            # Buscar en HKLM
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{name}",
                    0,
                    winreg.KEY_READ
                )
                path, _ = winreg.QueryValueEx(key, "")
                winreg.CloseKey(key)
                if os.path.exists(path):
                    return path
            except Exception:
                pass
            
            # Buscar en HKCU
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{name}",
                    0,
                    winreg.KEY_READ
                )
                path, _ = winreg.QueryValueEx(key, "")
                winreg.CloseKey(key)
                if os.path.exists(path):
                    return path
            except Exception:
                pass
    except Exception:
        pass
    
    # 3. Buscar en las rutas sugeridas (hints)
    if hints:
        for hint in hints:
            # Expandir variables de entorno (ej: %PROGRAMFILES%)
            path = os.path.expandvars(hint)
            if os.path.exists(path):
                return path
    
    # 4. Buscar en ubicaciones comunes
    common_paths = [
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        os.environ.get("LOCALAPPDATA", ""),
        os.environ.get("APPDATA", ""),
    ]
    
    for base in common_paths:
        if not base or not os.path.exists(base):
            continue
        for name in exe_names:
            # Buscar recursivamente (solo 2 niveles de profundidad)
            for root, dirs, files in os.walk(base):
                depth = root.replace(base, "").count(os.sep)
                if depth > 2:
                    continue
                if name in files:
                    return os.path.join(root, name)
    
    return None


def _launch_app(label, exe_names, hints=None, env_key=None):
    """
    Lanza una aplicación de forma inteligente.
    
    Args:
        label: Nombre legible de la aplicación
        exe_names: Lista de nombres de ejecutables
        hints: Lista de rutas sugeridas
        env_key: Variable de entorno para ruta personalizada
    
    Returns:
        bool: True si se lanzó con éxito
    """
    # 1. Prioridad: variable de entorno
    if env_key:
        env_val = os.path.expandvars(os.getenv(env_key, ""))
        if env_val and os.path.exists(env_val):
            try:
                if IS_WINDOWS:
                    subprocess.Popen([env_val], creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    subprocess.Popen([env_val])
                return True
            except Exception as e:
                print(f"[AppLauncher] Error con {env_key}: {e}")
    
    # 2. Buscar ejecutable
    exe_path = _find_exe_windows(exe_names, hints)
    if exe_path:
        try:
            if IS_WINDOWS:
                subprocess.Popen([exe_path], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.Popen([exe_path])
            return True
        except Exception as e:
            print(f"[AppLauncher] Error lanzando {exe_path}: {e}")
    
    # 3. Si es Mac, intentar con open -a
    if IS_MAC:
        app_name = label.replace(" ", "")
        try:
            subprocess.Popen(["open", "-a", app_name])
            return True
        except Exception as e:
            print(f"[AppLauncher] Error con open -a: {e}")
    
    # 4. Si es Linux, intentar con xdg-open
    if IS_LINUX:
        try:
            subprocess.Popen(["xdg-open", label])
            return True
        except Exception as e:
            print(f"[AppLauncher] Error con xdg-open: {e}")
    
    # 5. Windows: intentar con start
    if IS_WINDOWS:
        try:
            subprocess.Popen(["start", label], shell=True)
            return True
        except Exception as e:
            print(f"[AppLauncher] Error con start: {e}")
    
    print(f"[AppLauncher] ❌ No se pudo lanzar: {label}")
    return False


def _close_app(process_names):
    """
    Cierra una aplicación por nombre de proceso.
    
    Args:
        process_names: Lista de nombres de procesos (ej: ['chrome.exe'])
    
    Returns:
        bool: True si se cerró al menos un proceso
    """
    if not IS_WINDOWS:
        print("[AppLauncher] Cerrar apps solo soportado en Windows")
        return False
    
    try:
        import psutil
        killed = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc_name = proc.info['name'] or ""
                if proc_name.lower() in [n.lower() for n in process_names]:
                    proc.terminate()
                    killed += 1
                    time.sleep(0.05)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if killed == 0:
            # Intentar con taskkill
            for name in process_names:
                subprocess.run(["taskkill", "/F", "/IM", name], capture_output=True)
        return killed > 0
    except ImportError:
        print("[AppLauncher] psutil no instalado. Instala: pip install psutil")
        # Fallback con taskkill
        for name in process_names:
            subprocess.run(["taskkill", "/F", "/IM", name], capture_output=True)
        return True
    except Exception as e:
        print(f"[AppLauncher] Error cerrando: {e}")
        return False


# ===== CATÁLOGO DE APLICACIONES (COMPLETO) =====

_APPS_CATALOGUE = {
    # ===== NAVEGADORES =====
    "chrome": {
        "label": "Google Chrome",
        "noms": ["chrome.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
        ],
        "env_key": "CHROME_PATH"
    },
    "firefox": {
        "label": "Firefox",
        "noms": ["firefox.exe"],
        "hints": [
            r"%PROGRAMFILES%\Mozilla Firefox\firefox.exe",
            r"%PROGRAMFILES(X86)%\Mozilla Firefox\firefox.exe",
        ],
    },
    "edge": {
        "label": "Microsoft Edge",
        "noms": ["msedge.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe",
            r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe",
        ],
    },
    "brave": {
        "label": "Brave",
        "noms": ["brave.exe"],
        "hints": [
            r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
    },
    "opera": {
        "label": "Opera",
        "noms": ["opera.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Programs\Opera\opera.exe",
            r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe",
            r"%APPDATA%\Opera Software\Opera Stable\opera.exe",
            r"%APPDATA%\Opera Software\Opera GX Stable\opera.exe",
        ],
    },
    "vivaldi": {
        "label": "Vivaldi",
        "noms": ["vivaldi.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Vivaldi\Application\vivaldi.exe",
            r"%PROGRAMFILES%\Vivaldi\Application\vivaldi.exe",
        ],
    },
    
    # ===== JUEGOS / LAUNCHERS =====
    "steam": {
        "label": "Steam",
        "noms": ["steam.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Steam\steam.exe",
            r"%PROGRAMFILES%\Steam\steam.exe",
        ],
    },
    "epic": {
        "label": "Epic Games",
        "noms": ["EpicGamesLauncher.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe",
            r"%PROGRAMFILES%\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe",
        ],
    },
    "gog": {
        "label": "GOG Galaxy",
        "noms": ["GalaxyClient.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\GOG Galaxy\GalaxyClient.exe",
            r"%PROGRAMFILES%\GOG Galaxy\GalaxyClient.exe",
        ],
    },
    "origin": {
        "label": "Origin",
        "noms": ["Origin.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Origin\Origin.exe",
            r"%PROGRAMFILES%\Origin\Origin.exe",
        ],
    },
    "ea": {
        "label": "EA App",
        "noms": ["EADesktop.exe", "EA.exe"],
        "hints": [
            r"%PROGRAMFILES%\Electronic Arts\EA Desktop\EA Desktop.exe",
            r"%PROGRAMFILES(X86)%\Electronic Arts\EA Desktop\EA Desktop.exe",
        ],
    },
    "ubisoft": {
        "label": "Ubisoft Connect",
        "noms": ["UbisoftConnect.exe", "upc.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Ubisoft\Ubisoft Game Launcher\UbisoftConnect.exe",
            r"%PROGRAMFILES%\Ubisoft\Ubisoft Game Launcher\UbisoftConnect.exe",
        ],
    },
    "minecraft": {
        "label": "Minecraft",
        "noms": ["Minecraft.exe", "MinecraftLauncher.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Minecraft Launcher\MinecraftLauncher.exe",
            r"%LOCALAPPDATA%\Packages\Microsoft.4297127D64EC6_8wekyb3d8bbwe\Minecraft.exe",
        ],
    },
    
    # ===== COMUNICACIÓN =====
    "discord": {
        "label": "Discord",
        "noms": ["Discord.exe", "Update.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Discord\Update.exe",
            r"%LOCALAPPDATA%\Discord\app-*\Discord.exe",
            r"%APPDATA%\Discord\Update.exe",
        ],
    },
    "whatsapp": {
        "label": "WhatsApp",
        "noms": ["WhatsApp.exe"],
        "hints": [
            r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe",
            r"%LOCALAPPDATA%\Programs\WhatsApp\WhatsApp.exe",
        ],
    },
    "telegram": {
        "label": "Telegram",
        "noms": ["Telegram.exe"],
        "hints": [
            r"%APPDATA%\Telegram Desktop\Telegram.exe",
            r"%LOCALAPPDATA%\Telegram Desktop\Telegram.exe",
        ],
    },
    "teams": {
        "label": "Microsoft Teams",
        "noms": ["ms-teams.exe", "Teams.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\ms-teams.exe",
            r"%LOCALAPPDATA%\Microsoft\Teams\current\Teams.exe",
            r"%PROGRAMFILES%\Microsoft\Teams\current\Teams.exe",
        ],
    },
    "zoom": {
        "label": "Zoom",
        "noms": ["Zoom.exe"],
        "hints": [
            r"%APPDATA%\Zoom\bin\Zoom.exe",
            r"%PROGRAMFILES%\Zoom\bin\Zoom.exe",
            r"%PROGRAMFILES(X86)%\Zoom\bin\Zoom.exe",
        ],
    },
    "skype": {
        "label": "Skype",
        "noms": ["Skype.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\Skype.exe",
            r"%PROGRAMFILES(X86)%\Microsoft\Skype for Desktop\Skype.exe",
        ],
    },
    "signal": {
        "label": "Signal",
        "noms": ["Signal.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Programs\Signal\Signal.exe",
            r"%APPDATA%\Signal\Signal.exe",
        ],
    },
    
    # ===== OFFICE Y BUREÁUTICA =====
    "word": {
        "label": "Microsoft Word",
        "noms": ["WINWORD.EXE"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\WINWORD.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\WINWORD.EXE",
            r"%PROGRAMFILES%\Microsoft Office\Office16\WINWORD.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\Office16\WINWORD.EXE",
        ],
    },
    "excel": {
        "label": "Microsoft Excel",
        "noms": ["EXCEL.EXE"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\EXCEL.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\EXCEL.EXE",
            r"%PROGRAMFILES%\Microsoft Office\Office16\EXCEL.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\Office16\EXCEL.EXE",
        ],
    },
    "powerpoint": {
        "label": "Microsoft PowerPoint",
        "noms": ["POWERPNT.EXE"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\POWERPNT.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\POWERPNT.EXE",
            r"%PROGRAMFILES%\Microsoft Office\Office16\POWERPNT.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\Office16\POWERPNT.EXE",
        ],
    },
    "outlook": {
        "label": "Outlook",
        "noms": ["OUTLOOK.EXE"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\OUTLOOK.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\OUTLOOK.EXE",
            r"%PROGRAMFILES%\Microsoft Office\Office16\OUTLOOK.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\Office16\OUTLOOK.EXE",
        ],
    },
    "onenote": {
        "label": "OneNote",
        "noms": ["ONENOTE.EXE"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\ONENOTE.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\ONENOTE.EXE",
            r"%PROGRAMFILES%\Microsoft Office\Office16\ONENOTE.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\Office16\ONENOTE.EXE",
        ],
    },
    "notepad": {
        "label": "Bloc de notas",
        "noms": ["notepad.exe"],
        "hints": [
            r"%SystemRoot%\System32\notepad.exe",
            r"%SystemRoot%\SysWOW64\notepad.exe",
        ],
    },
    "calc": {
        "label": "Calculadora",
        "noms": ["calc.exe"],
        "hints": [
            r"%SystemRoot%\System32\calc.exe",
        ],
    },
    
    # ===== DISEÑO Y CREATIVO =====
    "photoshop": {
        "label": "Photoshop",
        "noms": ["Photoshop.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop 2024\Photoshop.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop 2025\Photoshop.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop CC 2023\Photoshop.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop 2023\Photoshop.exe",
        ],
    },
    "premiere": {
        "label": "Premiere Pro",
        "noms": ["Adobe Premiere Pro.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Premiere Pro CC 2023\Adobe Premiere Pro.exe",
        ],
    },
    "after_effects": {
        "label": "After Effects",
        "noms": ["AfterFX.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe After Effects 2024\Support Files\AfterFX.exe",
            r"%PROGRAMFILES%\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe",
            r"%PROGRAMFILES%\Adobe\Adobe After Effects 2023\Support Files\AfterFX.exe",
        ],
    },
    "illustrator": {
        "label": "Illustrator",
        "noms": ["Illustrator.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe Illustrator 2024\Support Files\Contents\Windows\Illustrator.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Illustrator 2025\Support Files\Contents\Windows\Illustrator.exe",
        ],
    },
    "capcut": {
        "label": "CapCut",
        "noms": ["CapCut.exe"],
        "hints": [
            r"%LOCALAPPDATA%\CapCut\Apps\CapCut.exe",
            r"%PROGRAMFILES%\CapCut\CapCut.exe",
        ],
    },
    "obs": {
        "label": "OBS Studio",
        "noms": ["obs64.exe", "obs32.exe"],
        "hints": [
            r"%PROGRAMFILES%\obs-studio\bin\64bit\obs64.exe",
            r"%PROGRAMFILES(X86)%\obs-studio\bin\64bit\obs64.exe",
        ],
    },
    "blender": {
        "label": "Blender",
        "noms": ["blender.exe"],
        "hints": [
            r"%PROGRAMFILES%\Blender Foundation\Blender 4.0\blender.exe",
            r"%PROGRAMFILES%\Blender Foundation\Blender 3.6\blender.exe",
            r"%PROGRAMFILES%\Blender Foundation\Blender\blender.exe",
        ],
    },
    "gimp": {
        "label": "GIMP",
        "noms": ["gimp-2.10.exe", "gimp.exe"],
        "hints": [
            r"%PROGRAMFILES%\GIMP 2\bin\gimp-2.10.exe",
            r"%PROGRAMFILES(X86)%\GIMP 2\bin\gimp-2.10.exe",
        ],
    },
    
    # ===== DESARROLLO =====
    "vscode": {
        "label": "Visual Studio Code",
        "noms": ["Code.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
            r"%PROGRAMFILES%\Microsoft VS Code\Code.exe",
        ],
        "env_key": "VSCODE_PATH"
    },
    "terminal": {
        "label": "Terminal",
        "noms": ["wt.exe", "WindowsTerminal.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe",
        ],
    },
    "cmd": {
        "label": "Símbolo del sistema",
        "noms": ["cmd.exe"],
        "hints": [
            r"%SystemRoot%\System32\cmd.exe",
        ],
    },
    "powershell": {
        "label": "PowerShell",
        "noms": ["powershell.exe"],
        "hints": [
            r"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe",
        ],
    },
    
    # ===== MULTIMEDIA =====
    "vlc": {
        "label": "VLC",
        "noms": ["vlc.exe"],
        "hints": [
            r"%PROGRAMFILES%\VideoLAN\VLC\vlc.exe",
            r"%PROGRAMFILES(X86)%\VideoLAN\VLC\vlc.exe",
        ],
    },
    "spotify": {
        "label": "Spotify",
        "noms": ["Spotify.exe"],
        "hints": [
            r"%APPDATA%\Spotify\Spotify.exe",
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe",
        ],
    },
    "deezer": {
        "label": "Deezer",
        "noms": ["Deezer.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Programs\Deezer\Deezer.exe",
            r"%APPDATA%\Deezer\Deezer.exe",
        ],
    },
    
    # ===== UTILIDADES =====
    "filezilla": {
        "label": "FileZilla",
        "noms": ["filezilla.exe"],
        "hints": [
            r"%PROGRAMFILES%\FileZilla FTP Client\filezilla.exe",
            r"%PROGRAMFILES(X86)%\FileZilla FTP Client\filezilla.exe",
        ],
    },
    "winrar": {
        "label": "WinRAR",
        "noms": ["WinRAR.exe"],
        "hints": [
            r"%PROGRAMFILES%\WinRAR\WinRAR.exe",
            r"%PROGRAMFILES(X86)%\WinRAR\WinRAR.exe",
        ],
    },
    "7zip": {
        "label": "7-Zip",
        "noms": ["7zFM.exe"],
        "hints": [
            r"%PROGRAMFILES%\7-Zip\7zFM.exe",
            r"%PROGRAMFILES(X86)%\7-Zip\7zFM.exe",
        ],
    },
    "explorer": {
        "label": "Explorador de archivos",
        "noms": ["explorer.exe"],
        "hints": [
            r"%SystemRoot%\explorer.exe",
        ],
    },
    "taskmgr": {
        "label": "Administrador de tareas",
        "noms": ["taskmgr.exe"],
        "hints": [
            r"%SystemRoot%\System32\taskmgr.exe",
        ],
    },
    "control": {
        "label": "Panel de control",
        "noms": ["control.exe"],
        "hints": [
            r"%SystemRoot%\System32\control.exe",
        ],
    },
    "snipping": {
        "label": "Recortes",
        "noms": ["SnippingTool.exe"],
        "hints": [
            r"%SystemRoot%\System32\SnippingTool.exe",
        ],
    },
}

# ===== ALIAS EN ESPAÑOL =====
_APPS_CATALOGUE["google chrome"] = _APPS_CATALOGUE["chrome"]
_APPS_CATALOGUE["microsoft edge"] = _APPS_CATALOGUE["edge"]
_APPS_CATALOGUE["microsoft word"] = _APPS_CATALOGUE["word"]
_APPS_CATALOGUE["microsoft excel"] = _APPS_CATALOGUE["excel"]
_APPS_CATALOGUE["microsoft powerpoint"] = _APPS_CATALOGUE["powerpoint"]
_APPS_CATALOGUE["visual studio code"] = _APPS_CATALOGUE["vscode"]
_APPS_CATALOGUE["vs code"] = _APPS_CATALOGUE["vscode"]
_APPS_CATALOGUE["bloc de notas"] = _APPS_CATALOGUE["notepad"]
_APPS_CATALOGUE["calculadora"] = _APPS_CATALOGUE["calc"]
_APPS_CATALOGUE["epic games"] = _APPS_CATALOGUE["epic"]
_APPS_CATALOGUE["premiere pro"] = _APPS_CATALOGUE["premiere"]
_APPS_CATALOGUE["adobe premiere"] = _APPS_CATALOGUE["premiere"]
_APPS_CATALOGUE["adobe photoshop"] = _APPS_CATALOGUE["photoshop"]
_APPS_CATALOGUE["after effects"] = _APPS_CATALOGUE["after_effects"]
_APPS_CATALOGUE["adobe after effects"] = _APPS_CATALOGUE["after_effects"]
_APPS_CATALOGUE["gog galaxy"] = _APPS_CATALOGUE["gog"]
_APPS_CATALOGUE["símbolo del sistema"] = _APPS_CATALOGUE["cmd"]
_APPS_CATALOGUE["simbolo del sistema"] = _APPS_CATALOGUE["cmd"]
_APPS_CATALOGUE["administrador de tareas"] = _APPS_CATALOGUE["taskmgr"]
_APPS_CATALOGUE["panel de control"] = _APPS_CATALOGUE["control"]
_APPS_CATALOGUE["explorador de archivos"] = _APPS_CATALOGUE["explorer"]
_APPS_CATALOGUE["explorador"] = _APPS_CATALOGUE["explorer"]


def cargar_apps_personalizadas():
    """
    Carga aplicaciones personalizadas desde la configuración de AP0L0.
    """
    config = _load_config()
    custom_apps = config.get("custom_apps", [])
    
    # Limpiar apps custom anteriores
    keys_to_remove = [k for k, v in _APPS_CATALOGUE.items() if v.get("is_custom")]
    for k in keys_to_remove:
        del _APPS_CATALOGUE[k]
    
    for app in custom_apps:
        app_id = app.get("id")
        app_label = app.get("label")
        app_path = app.get("exe_path")
        if app_id and app_path:
            exe_name = os.path.basename(app_path.replace("\\", "/"))
            new_app = {
                "label": app_label or app_id,
                "noms": [exe_name],
                "hints": [app_path],
                "is_custom": True
            }
            _APPS_CATALOGUE[app_id] = new_app
            if app_label:
                _APPS_CATALOGUE[app_label.lower()] = new_app
    
    # Guardar configuración actualizada
    config["custom_apps"] = custom_apps
    _save_config(config)


def lanzar_app(nombre, cerrar=False):
    """
    Lanza o cierra una aplicación por nombre.
    
    Args:
        nombre (str): Nombre de la aplicación
        cerrar (bool): True para cerrar, False para abrir
    
    Returns:
        str: Mensaje de resultado
    """
    nombre = nombre.lower().strip()
    
    # Buscar en el catálogo
    app_info = None
    for key, info in _APPS_CATALOGUE.items():
        if key == nombre or key in nombre or nombre in key:
            app_info = info
            break
    
    if not app_info:
        return f"No encontré la aplicación '{nombre}'. ¿Está instalada?"
    
    if cerrar:
        if _close_app(app_info["noms"]):
            return f"✅ He cerrado {app_info['label']}"
        else:
            return f"⚠️ No pude cerrar {app_info['label']}. ¿Está ejecutándose?"
    else:
        if _launch_app(app_info["label"], app_info["noms"], app_info.get("hints"), app_info.get("env_key")):
            return f"✅ Lanzando {app_info['label']}..."
        else:
            return f"❌ No pude lanzar {app_info['label']}. ¿Está instalada?"


def open_app_compat(nombre, *args, **kwargs):
    """Alias de compatibilidad para módulos integrados de versiones anteriores."""
    cerrar = bool(kwargs.get("cerrar", kwargs.get("close", False)))
    return lanzar_app(str(nombre or ""), cerrar=cerrar)


def modo_boulot(apps=None, *args, **kwargs):
    """Abre aplicaciones de trabajo configuradas, con compatibilidad histórica."""
    nombres = apps or _load_config().get("work_mode_apps", [])
    if isinstance(nombres, str):
        nombres = [nombres]
    resultados = [lanzar_app(nombre) for nombre in nombres if str(nombre).strip()]
    return "Modo trabajo ejecutado." if not resultados else "\n".join(resultados)


def listar_apps():
    """Lista todas las aplicaciones disponibles en el catálogo."""
    apps = []
    for key, info in _APPS_CATALOGUE.items():
        if not info.get("is_custom"):
            apps.append(key)
    return sorted(apps)


# ===== FUNCIÓN PRINCIPAL PARA AP0L0 =====

def app_launcher(params, player=None, speak=None):
    """
    Función de punto de entrada para AP0L0.
    
    Parámetros:
        action (str): "open", "close", "list"
        app (str): Nombre de la aplicación (para open/close)
    
    Returns:
        str: Mensaje de resultado
    """
    action = params.get("action", "open").lower()
    app_name = params.get("app", "").strip()
    
    if action == "list":
        apps = listar_apps()
        if player:
            player.write_log("[AppLauncher] Listando aplicaciones")
        return "Aplicaciones disponibles:\n" + "\n".join(f"  • {a}" for a in apps[:30])
    
    if not app_name:
        return "Necesito el nombre de la aplicación, señor."
    
    if player:
        player.write_log(f"[AppLauncher] {action} {app_name}")
    
    result = lanzar_app(app_name, cerrar=(action == "close"))
    
    if speak:
        speak(result)
    
    return result


# ===== CARGA DE APPS PERSONALIZADAS AL INICIO =====
cargar_apps_personalizadas()

# ===== PRUEBA =====
if __name__ == "__main__":
    print("=== Prueba de AppLauncher ===")
    print("Apps disponibles:", listar_apps()[:5])
