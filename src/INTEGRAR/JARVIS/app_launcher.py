import os
import subprocess
try:
    import psutil
except ImportError:
    psutil = None
import time
import asyncio
import shutil

# MODO TRABAJO
# ==========================================

def _trabajo_encontrar_exe(nombres_exe: list, rutas_sugeridas: list = None) -> str:
    """Encuentra un ejecutable en cualquier Windows.
    Orden: registro App Paths → PATH del sistema → rutas conocidas."""
    # 1. Registro de Windows (el más fiable — todas las aplicaciones instaladas están ahí)
    try:
        import winreg
        for exe in nombres_exe:
            for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                try:
                    key = winreg.OpenKey(
                        hive,
                        f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe}"
                    )
                    ruta, _ = winreg.QueryValueEx(key, "")
                    winreg.CloseKey(key)
                    p = os.path.expandvars(ruta.strip('"'))
                    if os.path.exists(p):
                        return p
                except Exception:
                    pass
    except ImportError:
        pass

    # 2. PATH del sistema
    for exe in nombres_exe:
        encontrado = shutil.which(exe)
        if encontrado:
            return encontrado

    # 3. Rutas conocidas comunes
    if rutas_sugeridas:
        for sugerencia in rutas_sugeridas:
            p = os.path.expandvars(sugerencia)
            if os.path.exists(p):
                return p

    return ""


def _trabajo_lanzar(etiqueta: str, nombres_exe: list,
                   rutas_sugeridas: list = None, clave_env: str = None) -> bool:
    """Lanza una aplicación — detección universal, sin ventanas emergentes de error de Windows."""
    # Sobrescritura mediante .env (prioridad absoluta)
    if clave_env:
        valor_env = os.path.expandvars(os.getenv(clave_env, ""))
        if valor_env and os.path.exists(valor_env):
            try:
                subprocess.Popen([valor_env])
                return True
            except Exception:
                pass

    # Detección automática (registro → PATH → sugerencias)
    ruta_exe = _trabajo_encontrar_exe(nombres_exe, rutas_sugeridas)
    if ruta_exe:
        try:
            subprocess.Popen([ruta_exe])
            return True
        except Exception:
            pass

    # No encontrado — se registra silenciosamente, sin ventanas emergentes de Windows
    print(f"[TRABAJO] {etiqueta} no encontrado en este PC (registro, PATH y sugerencias agotados)")
    return False


def _cerrar_app(nombres_proceso: list) -> bool:
    """Termina todos los procesos que coincidan con los nombres dados (insensible a mayúsculas)."""
    if psutil is None:
        return False
    terminados = 0
    nombres_lower = [n.lower() for n in nombres_proceso]
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() in nombres_lower:
                proc.terminate()
                terminados += 1
        except Exception:
            pass
    return terminados > 0


# Catálogo de aplicaciones abribles / cerrables por comando de voz
_CATALOGO_APPS = {
    # ── Navegadores ──────────────────────────────────────────
    "chrome": {
        "label": "Google Chrome", "noms": ["chrome.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
        ],
    },
    "firefox": {
        "label": "Firefox", "noms": ["firefox.exe"],
        "hints": [r"%PROGRAMFILES%\Mozilla Firefox\firefox.exe", r"%PROGRAMFILES(X86)%\Mozilla Firefox\firefox.exe"],
    },
    "edge": {
        "label": "Microsoft Edge", "noms": ["msedge.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe",
            r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe",
        ],
    },
    "opera": {
        "label": "Opera", "noms": ["opera.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Programs\Opera\opera.exe",
            r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe",
            r"%APPDATA%\Opera Software\Opera Stable\opera.exe",
            r"%APPDATA%\Opera Software\Opera GX Stable\opera.exe",
        ],
    },
    "brave": {
        "label": "Brave", "noms": ["brave.exe"],
        "hints": [
            r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
    },
    # ── Juegos / Lanzadores ─────────────────────────────────────
    "steam": {
        "label": "Steam", "noms": ["steam.exe"],
        "hints": [r"%PROGRAMFILES(X86)%\Steam\steam.exe", r"%PROGRAMFILES%\Steam\steam.exe"],
    },
    "epic": {
        "label": "Epic Games", "noms": ["EpicGamesLauncher.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe",
            r"%PROGRAMFILES%\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe",
        ],
    },
    "origin": {
        "label": "Origin", "noms": ["Origin.exe"],
        "hints": [r"%PROGRAMFILES(X86)%\Origin\Origin.exe", r"%PROGRAMFILES%\Origin\Origin.exe"],
    },
    "ea": {
        "label": "EA App", "noms": ["EADesktop.exe", "EA.exe"],
        "hints": [
            r"%PROGRAMFILES%\Electronic Arts\EA Desktop\EA Desktop.exe",
            r"%PROGRAMFILES(X86)%\Electronic Arts\EA Desktop\EA Desktop.exe",
        ],
    },
    "ubisoft": {
        "label": "Ubisoft Connect", "noms": ["UbisoftConnect.exe", "upc.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Ubisoft\Ubisoft Game Launcher\UbisoftConnect.exe",
            r"%PROGRAMFILES%\Ubisoft\Ubisoft Game Launcher\UbisoftConnect.exe",
        ],
    },
    "gog": {
        "label": "GOG Galaxy", "noms": ["GalaxyClient.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\GOG Galaxy\GalaxyClient.exe",
            r"%PROGRAMFILES%\GOG Galaxy\GalaxyClient.exe",
        ],
    },
    "minecraft": {
        "label": "Minecraft", "noms": ["Minecraft.exe", "MinecraftLauncher.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Minecraft Launcher\MinecraftLauncher.exe",
            r"%LOCALAPPDATA%\Packages\Microsoft.4297127D64EC6_8wekyb3d8bbwe\Minecraft.exe",
        ],
    },
    # ── Comunicación ────────────────────────────────────────
    "discord": {
        "label": "Discord", "noms": ["Discord.exe", "Update.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Discord\Update.exe",
            r"%LOCALAPPDATA%\Discord\app-*\Discord.exe",
            r"%APPDATA%\Discord\Update.exe",
        ],
    },
    "teams": {
        "label": "Microsoft Teams", "noms": ["ms-teams.exe", "Teams.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\ms-teams.exe",
            r"%LOCALAPPDATA%\Microsoft\Teams\current\Teams.exe",
            r"%PROGRAMFILES%\Microsoft\Teams\current\Teams.exe",
        ],
    },
    "whatsapp": {
        "label": "WhatsApp", "noms": ["WhatsApp.exe"],
        "hints": [
            r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe",
            r"%LOCALAPPDATA%\Programs\WhatsApp\WhatsApp.exe",
        ],
    },
    "telegram": {
        "label": "Telegram", "noms": ["Telegram.exe"],
        "hints": [
            r"%APPDATA%\Telegram Desktop\Telegram.exe",
            r"%LOCALAPPDATA%\Telegram Desktop\Telegram.exe",
        ],
    },
    "zoom": {
        "label": "Zoom", "noms": ["Zoom.exe"],
        "hints": [
            r"%APPDATA%\Zoom\bin\Zoom.exe",
            r"%PROGRAMFILES%\Zoom\bin\Zoom.exe",
            r"%PROGRAMFILES(X86)%\Zoom\bin\Zoom.exe",
        ],
    },
    "skype": {
        "label": "Skype", "noms": ["Skype.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\Skype.exe",
            r"%PROGRAMFILES(X86)%\Microsoft\Skype for Desktop\Skype.exe",
        ],
    },
    # ── Ofimática / Office ─────────────────────────────────
    "word": {
        "label": "Microsoft Word", "noms": ["WINWORD.EXE", "winword.exe"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\WINWORD.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\WINWORD.EXE",
            r"%PROGRAMFILES%\Microsoft Office\Office16\WINWORD.EXE",
        ],
    },
    "excel": {
        "label": "Microsoft Excel", "noms": ["EXCEL.EXE", "excel.exe"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\EXCEL.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\EXCEL.EXE",
            r"%PROGRAMFILES%\Microsoft Office\Office16\EXCEL.EXE",
        ],
    },
    "powerpoint": {
        "label": "Microsoft PowerPoint", "noms": ["POWERPNT.EXE", "powerpnt.exe"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\POWERPNT.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\POWERPNT.EXE",
        ],
    },
    "outlook": {
        "label": "Outlook", "noms": ["OUTLOOK.EXE", "outlook.exe", "olk.exe"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\OUTLOOK.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\OUTLOOK.EXE",
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\olk.exe",
        ],
    },
    "onenote": {
        "label": "OneNote", "noms": ["ONENOTE.EXE", "onenote.exe"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\ONENOTE.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\ONENOTE.EXE",
        ],
    },
    # ── Creativo / Diseño ─────────────────────────────────────
    "photoshop": {
        "label": "Photoshop", "noms": ["Photoshop.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop 2024\Photoshop.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop 2025\Photoshop.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop CC 2023\Photoshop.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop 2023\Photoshop.exe",
        ],
    },
    "premiere": {
        "label": "Premiere Pro", "noms": ["Adobe Premiere Pro.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Premiere Pro CC 2023\Adobe Premiere Pro.exe",
        ],
    },
    "after effects": {
        "label": "After Effects", "noms": ["AfterFX.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe After Effects 2024\Support Files\AfterFX.exe",
            r"%PROGRAMFILES%\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe",
            r"%PROGRAMFILES%\Adobe\Adobe After Effects 2023\Support Files\AfterFX.exe",
        ],
    },
    "illustrator": {
        "label": "Illustrator", "noms": ["Illustrator.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe Illustrator 2024\Support Files\Contents\Windows\Illustrator.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Illustrator 2025\Support Files\Contents\Windows\Illustrator.exe",
        ],
    },
    "capcut": {
        "label": "CapCut", "noms": ["CapCut.exe"],
        "hints": [
            r"%LOCALAPPDATA%\CapCut\Apps\CapCut.exe",
            r"%PROGRAMFILES%\CapCut\CapCut.exe",
        ],
    },
    "obs": {
        "label": "OBS Studio", "noms": ["obs64.exe", "obs32.exe"],
        "hints": [
            r"%PROGRAMFILES%\obs-studio\bin\64bit\obs64.exe",
            r"%PROGRAMFILES(X86)%\obs-studio\bin\64bit\obs64.exe",
        ],
    },
    "blender": {
        "label": "Blender", "noms": ["blender.exe"],
        "hints": [
            r"%PROGRAMFILES%\Blender Foundation\Blender 4.0\blender.exe",
            r"%PROGRAMFILES%\Blender Foundation\Blender 3.6\blender.exe",
            r"%PROGRAMFILES%\Blender Foundation\Blender\blender.exe",
        ],
    },
    "gimp": {
        "label": "GIMP", "noms": ["gimp-2.10.exe", "gimp.exe"],
        "hints": [
            r"%PROGRAMFILES%\GIMP 2\bin\gimp-2.10.exe",
            r"%PROGRAMFILES(X86)%\GIMP 2\bin\gimp-2.10.exe",
        ],
    },
    # ── Desarrollo ────────────────────────────────────────
    "vscode": {
        "label": "Visual Studio Code", "noms": ["Code.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
            r"%PROGRAMFILES%\Microsoft VS Code\Code.exe",
        ],
    },
    "claude": {
        "label": "Claude", "noms": ["claude.exe", "Claude.exe"],
        "hints": [
            r"%LOCALAPPDATA%\AnthropicClaude\claude.exe",
            r"%PROGRAMFILES%\AnthropicClaude\claude.exe",
            r"%APPDATA%\AnthropicClaude\claude.exe",
        ],
    },
    "terminal": {
        "label": "Terminal", "noms": ["wt.exe", "WindowsTerminal.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe",
        ],
    },
    # ── Multimedia ───────────────────────────────────────────
    "vlc": {
        "label": "VLC", "noms": ["vlc.exe"],
        "hints": [
            r"%PROGRAMFILES%\VideoLAN\VLC\vlc.exe",
            r"%PROGRAMFILES(X86)%\VideoLAN\VLC\vlc.exe",
        ],
    },
    "spotify": {
        "label": "Spotify", "noms": ["Spotify.exe"],
        "hints": [
            r"%APPDATA%\Spotify\Spotify.exe",
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe",
        ],
    },
    # ── Utilidades ──────────────────────────────────────────
    "filezilla": {
        "label": "FileZilla", "noms": ["filezilla.exe"],
        "hints": [
            r"%PROGRAMFILES%\FileZilla FTP Client\filezilla.exe",
            r"%PROGRAMFILES(X86)%\FileZilla FTP Client\filezilla.exe",
        ],
    },
    "winrar": {
        "label": "WinRAR", "noms": ["WinRAR.exe"],
        "hints": [
            r"%PROGRAMFILES%\WinRAR\WinRAR.exe",
            r"%PROGRAMFILES(X86)%\WinRAR\WinRAR.exe",
        ],
    },
    "7zip": {
        "label": "7-Zip", "noms": ["7zFM.exe"],
        "hints": [
            r"%PROGRAMFILES%\7-Zip\7zFM.exe",
            r"%PROGRAMFILES(X86)%\7-Zip\7zFM.exe",
        ],
    },
    "antigravity": {
        "label": "Antigravity", "noms": ["Antigravity.exe", "antigravity.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Antigravity\Antigravity.exe",
            r"%PROGRAMFILES%\Antigravity\Antigravity.exe",
            r"%PROGRAMFILES(X86)%\Antigravity\Antigravity.exe",
            r"%APPDATA%\Antigravity\Antigravity.exe",
            r"%LOCALAPPDATA%\Programs\Antigravity\Antigravity.exe",
        ],
    },
}
# Alias — varias formas de nombrar la misma aplicación
_CATALOGO_APPS["ea app"]          = _CATALOGO_APPS["ea"]
_CATALOGO_APPS["microsoft edge"]  = _CATALOGO_APPS["edge"]
_CATALOGO_APPS["opera gx"]        = _CATALOGO_APPS["opera"]
_CATALOGO_APPS["google chrome"]   = _CATALOGO_APPS["chrome"]
_CATALOGO_APPS["epic games"]      = _CATALOGO_APPS["epic"]
_CATALOGO_APPS["epic game"]       = _CATALOGO_APPS["epic"]
_CATALOGO_APPS["ubisoft connect"] = _CATALOGO_APPS["ubisoft"]
_CATALOGO_APPS["uplay"]          = _CATALOGO_APPS["ubisoft"]
_CATALOGO_APPS["gog galaxy"]     = _CATALOGO_APPS["gog"]
_CATALOGO_APPS["visual studio code"] = _CATALOGO_APPS["vscode"]
_CATALOGO_APPS["vs code"]        = _CATALOGO_APPS["vscode"]
_CATALOGO_APPS["code"]           = _CATALOGO_APPS["vscode"]
_CATALOGO_APPS["premiere pro"]   = _CATALOGO_APPS["premiere"]
_CATALOGO_APPS["adobe premiere"] = _CATALOGO_APPS["premiere"]
_CATALOGO_APPS["adobe photoshop"]= _CATALOGO_APPS["photoshop"]
_CATALOGO_APPS["adobe after effects"] = _CATALOGO_APPS["after effects"]
_CATALOGO_APPS["adobe illustrator"] = _CATALOGO_APPS["illustrator"]
_CATALOGO_APPS["microsoft word"] = _CATALOGO_APPS["word"]
_CATALOGO_APPS["microsoft excel"]= _CATALOGO_APPS["excel"]
_CATALOGO_APPS["microsoft powerpoint"] = _CATALOGO_APPS["powerpoint"]
_CATALOGO_APPS["powerpoint"]     = _CATALOGO_APPS["powerpoint"]
_CATALOGO_APPS["ppt"]            = _CATALOGO_APPS["powerpoint"]
_CATALOGO_APPS["microsoft outlook"] = _CATALOGO_APPS["outlook"]
_CATALOGO_APPS["microsoft teams"]= _CATALOGO_APPS["teams"]
_CATALOGO_APPS["obs studio"]     = _CATALOGO_APPS["obs"]
_CATALOGO_APPS["siete zip"]       = _CATALOGO_APPS["7zip"]
_CATALOGO_APPS["7 zip"]          = _CATALOGO_APPS["7zip"]

def _cargar_apps_personalizadas():
    """Carga las aplicaciones dinámicas desde jarvis_config.json y las añade a _CATALOGO_APPS."""
    import json
    try:
        ruta_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        if not os.path.exists(ruta_config):
            return
        with open(ruta_config, "r", encoding="utf-8") as f:
            config = json.load(f)
            apps_personalizadas = config.get("custom_apps", [])
            
            claves_a_eliminar = [k for k, v in _CATALOGO_APPS.items() if v.get("is_custom")]
            for k in claves_a_eliminar:
                del _CATALOGO_APPS[k]
                
            for app in apps_personalizadas:
                app_id = app.get("id")
                app_etiqueta = app.get("label")
                app_ruta = app.get("exe_path")
                if app_id and app_ruta:
                    nombre_exe = os.path.basename(app_ruta.replace("\\", "/"))
                    nueva_app = {
                        "label": app_etiqueta,
                        "noms": [nombre_exe],
                        "hints": [app_ruta],
                        "is_custom": True
                    }
                    _CATALOGO_APPS[app_id] = nueva_app
                    if app_etiqueta:
                        _CATALOGO_APPS[app_etiqueta.lower()] = nueva_app
    except Exception as e:
        print(f"[TRABAJO] Error al cargar aplicaciones personalizadas: {e}")

_cargar_apps_personalizadas()


async def modo_trabajo():
    """Lanza Spotify, abre Documentos, Descargas, Chrome y Antigravity
    en disposición de cuadrantes en la pantalla."""
    try:
        import win32gui, win32con, win32api
    except ImportError:
        return "Falta pywin32 — instálelo para la disposición de ventanas."

    await hablar("Bien, preparo su espacio de trabajo.")

    # ── 1. Spotify en segundo plano (PRIORIDAD — lanzado primero) ────
    lanzar_spotify_playlist(SPOTIFY_MUSICA_URI)
    time.sleep(0.5)

    # ── 2. Apertura de carpetas ────────────────────────────
    # Documentos (irá arriba a la izquierda)
    ruta_documentos = resolver_ruta("documentos")
    subprocess.Popen(["explorer", ruta_documentos])
    time.sleep(0.3)

    # Descargas (irá arriba a la derecha)
    ruta_descargas = resolver_ruta("descargas")
    subprocess.Popen(["explorer", ruta_descargas])
    time.sleep(0.3)

    # ── 3. Chrome (irá abajo a la izquierda) ──────────────────────
    _trabajo_lanzar(
        "Chrome", ["chrome.exe"],
        rutas_sugeridas=[
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
        ],
        clave_env="CHROME_PATH"
    )
    time.sleep(0.3)

    # ── 4. Antigravity (irá abajo a la derecha) ─────────────────
    _trabajo_lanzar(
        "Antigravity", ["Antigravity.exe", "antigravity.exe"],
        rutas_sugeridas=[
            r"%LOCALAPPDATA%\Antigravity\Antigravity.exe",
            r"%PROGRAMFILES%\Antigravity\Antigravity.exe",
            r"%PROGRAMFILES(X86)%\Antigravity\Antigravity.exe",
            r"%APPDATA%\Antigravity\Antigravity.exe",
            r"%LOCALAPPDATA%\Programs\Antigravity\Antigravity.exe",
        ],
        clave_env="ANTIGRAVITY_PATH"
    )
    time.sleep(0.3)

    await hablar("Aplicaciones lanzadas, ordeno su espacio en unos segundos.")
    time.sleep(7)

    # ── 5. Disposición en 4 cuadrantes ────────────────────────
    ancho_pantalla = win32api.GetSystemMetrics(0)
    alto_pantalla = win32api.GetSystemMetrics(1)
    alto_trabajo   = alto_pantalla - 48
    mitad_ancho = ancho_pantalla // 2
    mitad_alto = alto_trabajo  // 2

    #  ┌──────────────────┬──────────────────┐
    #  │   Documentos     │  Descargas       │
    #  │   (arriba izq)   │  (arriba dcha)   │
    #  ├──────────────────┼──────────────────┤
    #  │   Chrome         │  Antigravity     │
    #  │   (abajo izq)    │  (abajo dcha)    │
    #  └──────────────────┴──────────────────┘
    disposicion = [
        {"titulos": ["Documentos"],                           "pos": (0,  0,  mitad_ancho, mitad_alto)},
        {"titulos": ["Descargas", "Telechargements",
                    "Downloads"],                           "pos": (mitad_ancho, 0,  mitad_ancho, mitad_alto)},
        {"titulos": ["Chrome", "Google Chrome"],             "pos": (0,  mitad_alto, mitad_ancho, mitad_alto)},
        {"titulos": ["Antigravity"],                         "pos": (mitad_ancho, mitad_alto, mitad_ancho, mitad_alto)},
    ]

    def _encontrar_hwnd(titulos):
        encontrado = [None]
        def cb(hwnd, _):
            if encontrado[0]:
                return
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if any(palabra.lower() in t.lower() for palabra in titulos):
                    encontrado[0] = hwnd
        win32gui.EnumWindows(cb, None)
        return encontrado[0]

    ok = 0
    for item in disposicion:
        hwnd = _encontrar_hwnd(item["titulos"])
        if hwnd:
            x, y, w, h = item["pos"]
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOP, x, y, w, h,
                win32con.SWP_SHOWWINDOW
            )
            time.sleep(0.2)
            ok += 1

    if ok == 4:
        return "Su espacio de trabajo está listo, Christopher. Buen día."
    return f"Espacio listo — {ok}/4 ventanas posicionadas. Música iniciada de fondo."