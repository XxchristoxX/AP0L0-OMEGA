# src/actions/computer_settings.py
# VERSIÓN COMPLETA Y CORREGIDA – Sin pycaw, solo fallback por teclas.
# Eliminado el aviso automático de administrador.

import json
import re
import sys
import time
import subprocess
import platform
import ctypes
from pathlib import Path

# ============================================================
# VERIFICACIÓN DE DEPENDENCIAS Y PERMISOS (SIN PRINT AUTOMÁTICO)
# ============================================================
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False
    # No imprimimos nada aquí para evitar warnings innecesarios

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

_OS = platform.system()

if _OS == "Windows":
    _WIN_HIDE: dict = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    _WIN_HIDE: dict = {}

def _is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# Solo usamos esta variable internamente, sin imprimir
_ADMIN = _is_admin() if _OS == "Windows" else False

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _get_api_key() -> str:
    path = _get_base_dir() / "config" / "api_keys.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("gemini_api_key", "")
    except Exception:
        return ""

def _get_macos_wifi_interface() -> str:
    try:
        result = subprocess.run(
            ["networksetup", "-listallhardwareports"],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.splitlines()
        for i, line in enumerate(lines):
            if "Wi-Fi" in line or "AirPort" in line:
                for j in range(i, min(i + 4, len(lines))):
                    if lines[j].startswith("Device:"):
                        return lines[j].split(":", 1)[1].strip()
    except Exception:
        pass
    return "en0"

# ============================================================
# 1. VOLUMEN (SOLO FALLBACK POR TECLAS)
# ============================================================

def _volume_fallback(action: str, value: int = None):
    """Método de respaldo usando teclas virtuales."""
    import pyautogui
    if action == "up":
        pyautogui.press("volumeup", presses=5)
    elif action == "down":
        pyautogui.press("volumedown", presses=5)
    elif action == "mute":
        pyautogui.press("volumemute")
    elif action == "set" and value is not None:
        current = 50
        diff = value - current
        if diff > 0:
            pyautogui.press("volumeup", presses=diff // 2)
        elif diff < 0:
            pyautogui.press("volumedown", presses=abs(diff) // 2)

def volume_up():
    _volume_fallback("up")
    return "Volumen subido."

def volume_down():
    _volume_fallback("down")
    return "Volumen bajado."

def volume_mute():
    _volume_fallback("mute")
    return "Volumen silenciado."

def volume_set(value: int):
    _volume_fallback("set", value)
    return f"Volumen establecido al {value}%."

# ============================================================
# 2. BRILLO
# ============================================================
def brightness_up():
    if _OS == "Darwin":
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 144'], capture_output=True)
        return
    if _OS == "Linux":
        if subprocess.run(["which", "brightnessctl"], capture_output=True).returncode == 0:
            subprocess.run(["brightnessctl", "set", "+10%"], capture_output=True)
        else:
            subprocess.run(
                'xrandr --output $(xrandr | grep " connected" | head -1 | cut -d " " -f1)'
                ' --brightness $(python3 -c "import subprocess; '
                'b=float(subprocess.check_output([\"xrandr\",\"--verbose\"]).decode()'
                '.split(\"Brightness:\")[1].split()[0]); print(min(1.0,b+0.1))")',
                shell=True, capture_output=True
            )
        return
    if _OS != "Windows":
        return
    try:
        import wmi
        w = wmi.WMI(namespace="root/wmi")
        methods = w.WmiMonitorBrightnessMethods()[0]
        current = w.WmiMonitorBrightness()[0].CurrentBrightness
        new_val = min(100, current + 10)
        methods.WmiSetBrightness(new_val, 1)
    except Exception as e:
        # Intentamos con teclas Fn sin mostrar error
        try:
            pyautogui.hotkey('fn', 'f7')
        except:
            pass

def brightness_down():
    if _OS == "Darwin":
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 145'], capture_output=True)
        return
    if _OS == "Linux":
        if subprocess.run(["which", "brightnessctl"], capture_output=True).returncode == 0:
            subprocess.run(["brightnessctl", "set", "10%-"], capture_output=True)
        else:
            subprocess.run(
                'xrandr --output $(xrandr | grep " connected" | head -1 | cut -d " " -f1)'
                ' --brightness $(python3 -c "import subprocess; '
                'b=float(subprocess.check_output([\"xrandr\",\"--verbose\"]).decode()'
                '.split(\"Brightness:\")[1].split()[0]); print(max(0.1,b-0.1))")',
                shell=True, capture_output=True
            )
        return
    if _OS != "Windows":
        return
    try:
        import wmi
        w = wmi.WMI(namespace="root/wmi")
        methods = w.WmiMonitorBrightnessMethods()[0]
        current = w.WmiMonitorBrightness()[0].CurrentBrightness
        new_val = max(0, current - 10)
        methods.WmiSetBrightness(new_val, 1)
    except Exception as e:
        try:
            pyautogui.hotkey('fn', 'f6')
        except:
            pass

def set_brightness(value: int):
    value = max(0, min(100, int(value)))
    if _OS != "Windows":
        return
    try:
        import wmi
        w = wmi.WMI(namespace="root/wmi")
        methods = w.WmiMonitorBrightnessMethods()[0]
        methods.WmiSetBrightness(value, 1)
    except Exception as e:
        pass

# ============================================================
# 3. WIFI
# ============================================================
def toggle_wifi():
    if _OS == "Darwin":
        iface = _get_macos_wifi_interface()
        result = subprocess.run(["networksetup", "-getairportpower", iface], capture_output=True, text=True)
        state = "off" if "On" in result.stdout else "on"
        subprocess.run(["networksetup", "-setairportpower", iface, state], capture_output=True)
        return
    if _OS == "Linux":
        try:
            result = subprocess.run(["nmcli", "radio", "wifi"], capture_output=True, text=True)
            state = "off" if "enabled" in result.stdout else "on"
            subprocess.run(["nmcli", "radio", "wifi", state], capture_output=True)
        except Exception:
            pass
        return
    if not _ADMIN:
        # No imprimimos nada
        return
    try:
        script = """
        $adapter = Get-NetAdapter | Where-Object { $_.Name -like "*Wi-Fi*" -or $_.Name -like "*Wireless*" -or $_.Name -like "*WLAN*" }
        if ($adapter) {
            if ($adapter.Status -eq 'Up') {
                Disable-NetAdapter -Name $adapter.Name -Confirm:$false
                Write-Host "WiFi Desactivado"
            } else {
                Enable-NetAdapter -Name $adapter.Name -Confirm:$false
                Write-Host "WiFi Activado"
            }
        } else {
            Write-Host "Adaptador WiFi no encontrado"
        }
        """
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=10, **_WIN_HIDE
        )
    except Exception:
        pass

# ============================================================
# 4. ESCRITORIO Y BLOQUEO
# ============================================================
def show_desktop():
    if _OS == "Windows":
        try:
            ctypes.windll.shell32.Shell_ToggleDesktop()
        except Exception:
            try:
                pyautogui.hotkey("win", "d")
            except:
                pass
    elif _OS == "Darwin":
        try:
            pyautogui.hotkey("fn", "f11")
        except:
            pass
    else:
        try:
            pyautogui.hotkey("super", "d")
        except:
            pass

def lock_screen():
    if _OS == "Windows":
        try:
            ctypes.windll.user32.LockWorkStation()
        except Exception:
            try:
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], capture_output=True)
            except:
                pass
    elif _OS == "Darwin":
        subprocess.run(["pmset", "displaysleepnow"], capture_output=True)
    else:
        for cmd in [["gnome-screensaver-command", "-l"], ["xdg-screensaver", "lock"], ["loginctl", "lock-session"]]:
            try:
                subprocess.run(cmd, capture_output=True)
            except:
                pass

def sleep_display():
    if _OS == "Windows":
        try:
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
        except Exception:
            pass
    elif _OS == "Darwin":
        subprocess.run(["pmset", "displaysleepnow"], capture_output=True)
    else:
        subprocess.run(["xset", "dpms", "force", "off"], capture_output=True)

def restart_computer():
    if not _ADMIN:
        return
    if _OS == "Windows":
        try:
            subprocess.run(["shutdown", "/r", "/t", "10"], capture_output=True, check=True, **_WIN_HIDE)
        except Exception:
            pass
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e", 'tell application "System Events" to restart'], capture_output=True)
    else:
        subprocess.run(["systemctl", "reboot"], capture_output=True)

def shutdown_computer():
    if not _ADMIN:
        return
    if _OS == "Windows":
        try:
            subprocess.run(["shutdown", "/s", "/t", "10"], capture_output=True, check=True, **_WIN_HIDE)
        except Exception:
            pass
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e", 'tell application "System Events" to shut down'], capture_output=True)
    else:
        subprocess.run(["systemctl", "poweroff"], capture_output=True)

# ============================================================
# 5. FUNCIONES DE VENTANAS Y NAVEGACIÓN
# ============================================================

def minimize_window():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "m")
    elif _OS == "Windows":
        try:
            pyautogui.hotkey("win", "down")
        except:
            show_desktop()
    else:
        try:
            pyautogui.hotkey("super", "down")
        except:
            show_desktop()

def close_app():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "q")
    else:
        pyautogui.hotkey("alt", "f4")

def close_window():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "w")
    else:
        pyautogui.hotkey("ctrl", "w")

def full_screen():
    if _OS == "Darwin":
        pyautogui.hotkey("ctrl", "command", "f")
    else:
        pyautogui.press("f11")

def maximize_window():
    if _OS == "Darwin":
        subprocess.run(["osascript", "-e",
            'tell application "System Events" to keystroke "f" using {control down, command down}'],
            capture_output=True)
    elif _OS == "Windows":
        pyautogui.hotkey("win", "up")
    else:
        try:
            subprocess.run(["wmctrl", "-r", ":ACTIVE:", "-b", "add,maximized_vert,maximized_horz"],
                capture_output=True)
        except Exception:
            pyautogui.hotkey("super", "up")

def snap_left():
    if _OS == "Windows":
        pyautogui.hotkey("win", "left")
    elif _OS == "Darwin":
        try:
            subprocess.run(["open", "-a", "Rectangle"], capture_output=True, timeout=1)
        except:
            pass
        pyautogui.hotkey("ctrl", "option", "left")
    else:
        try:
            subprocess.run(["wmctrl", "-r", ":ACTIVE:", "-e", "0,0,0,960,1080"], capture_output=True)
        except:
            pass

def snap_right():
    if _OS == "Windows":
        pyautogui.hotkey("win", "right")
    elif _OS == "Darwin":
        try:
            subprocess.run(["open", "-a", "Rectangle"], capture_output=True, timeout=1)
        except:
            pass
        pyautogui.hotkey("ctrl", "option", "right")
    else:
        try:
            subprocess.run(["wmctrl", "-r", ":ACTIVE:", "-e", "0,960,0,960,1080"], capture_output=True)
        except:
            pass

def switch_window():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "tab")
    else:
        pyautogui.hotkey("alt", "tab")

def open_task_manager():
    if _OS == "Windows":
        pyautogui.hotkey("ctrl", "shift", "esc")
    elif _OS == "Darwin":
        subprocess.Popen(["open", "-a", "Activity Monitor"])
    else:
        for cmd in [["gnome-system-monitor"], ["xfce4-taskmanager"], ["htop"]]:
            if subprocess.run(["which", cmd[0]], capture_output=True).returncode == 0:
                subprocess.Popen(cmd)
                break

def focus_search():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "l")
    else:
        pyautogui.hotkey("ctrl", "l")

def pause_video():
    pyautogui.press("space")

def refresh_page():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "r")
    else:
        pyautogui.press("f5")

def close_tab():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "w")
    else:
        pyautogui.hotkey("ctrl", "w")

def new_tab():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "t")
    else:
        pyautogui.hotkey("ctrl", "t")

def next_tab():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "shift", "bracketright")
    else:
        pyautogui.hotkey("ctrl", "tab")

def prev_tab():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "shift", "bracketleft")
    else:
        pyautogui.hotkey("ctrl", "shift", "tab")

def go_back():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "left")
    else:
        pyautogui.hotkey("alt", "left")

def go_forward():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "right")
    else:
        pyautogui.hotkey("alt", "right")

def zoom_in():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "equal")
    else:
        pyautogui.hotkey("ctrl", "equal")

def zoom_out():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "minus")
    else:
        pyautogui.hotkey("ctrl", "minus")

def zoom_reset():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "0")
    else:
        pyautogui.hotkey("ctrl", "0")

def find_on_page():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "f")
    else:
        pyautogui.hotkey("ctrl", "f")

def reload_page_n(n: int):
    for _ in range(max(1, n)):
        refresh_page()
        time.sleep(0.8)

def scroll_up(amount: int = 500):
    pyautogui.scroll(amount)

def scroll_down(amount: int = 500):
    pyautogui.scroll(-amount)

def scroll_top():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "up")
    else:
        pyautogui.hotkey("ctrl", "home")

def scroll_bottom():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "down")
    else:
        pyautogui.hotkey("ctrl", "end")

def page_up():
    pyautogui.press("pageup")

def page_down():
    pyautogui.press("pagedown")

def copy():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "c")
    else:
        pyautogui.hotkey("ctrl", "c")

def paste():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "v")
    else:
        pyautogui.hotkey("ctrl", "v")

def cut():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "x")
    else:
        pyautogui.hotkey("ctrl", "x")

def undo():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "z")
    else:
        pyautogui.hotkey("ctrl", "z")

def redo():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "shift", "z")
    else:
        pyautogui.hotkey("ctrl", "y")

def select_all():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "a")
    else:
        pyautogui.hotkey("ctrl", "a")

def save_file():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "s")
    else:
        pyautogui.hotkey("ctrl", "s")

def press_enter():
    pyautogui.press("enter")

def press_escape():
    pyautogui.press("escape")

def press_key(key: str):
    pyautogui.press(key)

def type_text(text: str, press_enter_after: bool = False):
    if not text:
        return
    if _PYPERCLIP:
        pyperclip.copy(str(text))
        time.sleep(0.15)
        paste()
    else:
        pyautogui.write(str(text), interval=0.03)
    if press_enter_after:
        time.sleep(0.1)
        pyautogui.press("enter")

def take_screenshot():
    if _OS == "Windows":
        pyautogui.hotkey("win", "shift", "s")
    elif _OS == "Darwin":
        pyautogui.hotkey("command", "shift", "3")
    else:
        for cmd in [["scrot"], ["gnome-screenshot"], ["import", "-window", "root", "screenshot.png"]]:
            if subprocess.run(["which", cmd[0]], capture_output=True).returncode == 0:
                subprocess.Popen(cmd)
                return
        pyautogui.hotkey("ctrl", "print_screen")

def open_system_settings():
    if _OS == "Windows":
        pyautogui.hotkey("win", "i")
    elif _OS == "Darwin":
        subprocess.Popen(["open", "-a", "System Preferences"])
    else:
        for cmd in [["gnome-control-center"], ["xfce4-settings-manager"], ["kcmshell5"]]:
            if subprocess.run(["which", cmd[0]], capture_output=True).returncode == 0:
                subprocess.Popen(cmd)
                return

def open_file_explorer():
    if _OS == "Windows":
        pyautogui.hotkey("win", "e")
    elif _OS == "Darwin":
        subprocess.Popen(["open", str(Path.home())])
    else:
        for cmd in [["nautilus"], ["thunar"], ["dolphin"], ["nemo"]]:
            if subprocess.run(["which", cmd[0]], capture_output=True).returncode == 0:
                subprocess.Popen(cmd)
                return
        subprocess.Popen(["xdg-open", str(Path.home())])

def open_run():
    if _OS == "Windows":
        pyautogui.hotkey("win", "r")

def dark_mode():
    if _OS == "Darwin":
        subprocess.run(["osascript", "-e", 'tell app "System Events" to tell appearance preferences to set dark mode to not dark mode'], capture_output=True)
    elif _OS == "Windows":
        try:
            import winreg
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            current, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, 1 - current)
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, 1 - current)
            winreg.CloseKey(key)
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"], capture_output=True, text=True)
            current = result.stdout.strip()
            new_scheme = "'default'" if "dark" in current else "'prefer-dark'"
            subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", new_scheme], capture_output=True)
        except Exception:
            pass

# ============================================================
# 6. MAPA DE ACCIONES
# ============================================================
ACTION_MAP: dict[str, callable] = {
    "volume_up": volume_up,
    "volume_down": volume_down,
    "mute": volume_mute,
    "toggle_mute": volume_mute,
    "brightness_up": brightness_up,
    "brightness_down": brightness_down,
    "set_brightness": set_brightness,
    "sleep_display": sleep_display,
    "screen_off": sleep_display,
    "restart": restart_computer,
    "restart_computer": restart_computer,
    "shutdown": shutdown_computer,
    "shut_down": shutdown_computer,
    "turn_off": shutdown_computer,
    "show_desktop": show_desktop,
    "minimize": minimize_window,
    "minimize_window": minimize_window,
    "maximize": maximize_window,
    "full_screen": full_screen,
    "fullscreen": full_screen,
    "close_app": close_app,
    "close_window": close_window,
    "snap_left": snap_left,
    "snap_right": snap_right,
    "switch_window": switch_window,
    "task_manager": open_task_manager,
    "open_settings": open_system_settings,
    "file_explorer": open_file_explorer,
    "open_run": open_run,
    "focus_search": focus_search,
    "refresh_page": refresh_page,
    "reload": refresh_page,
    "close_tab": close_tab,
    "new_tab": new_tab,
    "next_tab": next_tab,
    "prev_tab": prev_tab,
    "go_back": go_back,
    "go_forward": go_forward,
    "zoom_in": zoom_in,
    "zoom_out": zoom_out,
    "zoom_reset": zoom_reset,
    "find_on_page": find_on_page,
    "scroll_up": scroll_up,
    "scroll_down": scroll_down,
    "scroll_top": scroll_top,
    "scroll_bottom": scroll_bottom,
    "page_up": page_up,
    "page_down": page_down,
    "copy": copy,
    "paste": paste,
    "cut": cut,
    "undo": undo,
    "redo": redo,
    "select_all": select_all,
    "save": save_file,
    "enter": press_enter,
    "escape": press_escape,
    "screenshot": take_screenshot,
    "lock_screen": lock_screen,
    "lock": lock_screen,
    "lock_computer": lock_screen,
    "toggle_wifi": toggle_wifi,
    "wifi": toggle_wifi,
    "wifi_toggle": toggle_wifi,
    "pause_video": pause_video,
    "play_pause": pause_video,
    "dark_mode": dark_mode,
}

_DANGEROUS_ACTIONS = {"restart", "shutdown", "restart_computer", "shut_down", "turn_off"}

# ============================================================
# 7. DETECCIÓN DE INTENCIÓN (con MultiProvider)
# ============================================================
def _detect_action(description: str) -> dict:
    try:
        from src.core.multi_provider import MultiProvider
    except ImportError:
        return _manual_fallback(description)

    available_actions = sorted(ACTION_MAP.keys())
    available_str = ", ".join(available_actions)

    prompt = f"""You are an intent detector for a computer control assistant.

The user says (in any language): "{description}"

Your task is to map this to ONE of the following actions:
{available_str}

Also, you may need to extract a numeric value for actions like volume_set or set_brightness.

Return ONLY a valid JSON object with this exact format:
{{"action": "action_name", "value": null_or_number}}

Rules:
- Choose the action that best matches the user's request.
- For volume_set: value is an integer 0-100.
- For set_brightness: value is an integer 0-100.
- For volume_up, volume_down, brightness_up, brightness_down, toggle_wifi, etc., value is null.

Return ONLY the JSON object, nothing else. No explanation, no markdown."""

    provider = MultiProvider()
    response_text, used_provider = provider.generate(prompt)

    if response_text is None:
        return _manual_fallback(description)

    try:
        text = re.sub(r"```(?:json)?", "", response_text).strip().rstrip("`").strip()
        result = json.loads(text)
        if "action" in result:
            action_name = result["action"].lower().strip().replace(" ", "_")
            if action_name in ACTION_MAP or action_name in ("volume_set", "set_brightness", "type_text", "press_key", "reload_n", "scroll_up", "scroll_down"):
                result["action"] = action_name
                return result
        return {"action": "unknown", "value": None}
    except Exception as e:
        return _manual_fallback(description)

def _manual_fallback(description: str) -> dict:
    desc_lower = description.lower()
    import re

    if any(w in desc_lower for w in ["subir volumen", "más volumen", "volumen arriba", "increase volume"]):
        return {"action": "volume_up", "value": None}
    if any(w in desc_lower for w in ["bajar volumen", "menos volumen", "volumen abajo", "decrease volume"]):
        return {"action": "volume_down", "value": None}
    if any(w in desc_lower for w in ["silenciar", "mute", "sin sonido"]):
        return {"action": "mute", "value": None}
    if any(w in desc_lower for w in ["pon volumen", "set volume", "volumen en"]):
        match = re.search(r"(\d+)", desc_lower)
        val = int(match.group(1)) if match else 50
        return {"action": "volume_set", "value": val}

    if any(w in desc_lower for w in ["subir brillo", "más brillo", "brillo arriba", "increase brightness"]):
        return {"action": "brightness_up", "value": None}
    if any(w in desc_lower for w in ["bajar brillo", "menos brillo", "brillo abajo", "decrease brightness"]):
        return {"action": "brightness_down", "value": None}
    if any(w in desc_lower for w in ["pon brillo", "set brightness", "brillo en"]):
        match = re.search(r"(\d+)", desc_lower)
        val = int(match.group(1)) if match else 50
        return {"action": "set_brightness", "value": val}

    if any(w in desc_lower for w in ["activar wifi", "desactivar wifi", "wifi", "toggle wifi"]):
        return {"action": "toggle_wifi", "value": None}
    if any(w in desc_lower for w in ["mostrar escritorio", "minimizar todo", "show desktop"]):
        return {"action": "show_desktop", "value": None}
    if any(w in desc_lower for w in ["bloquear pantalla", "bloquear pc", "lock screen"]):
        return {"action": "lock_screen", "value": None}
    if any(w in desc_lower for w in ["apagar pantalla", "suspender pantalla", "sleep display"]):
        return {"action": "sleep_display", "value": None}
    if any(w in desc_lower for w in ["apagar pc", "apagar computador", "shutdown", "turn off"]):
        return {"action": "shutdown", "value": None}
    if any(w in desc_lower for w in ["reiniciar pc", "reiniciar computador", "restart", "reboot"]):
        return {"action": "restart", "value": None}
    if any(w in desc_lower for w in ["minimizar ventana", "minimize window"]):
        return {"action": "minimize_window", "value": None}
    if any(w in desc_lower for w in ["maximizar ventana", "maximize window"]):
        return {"action": "maximize_window", "value": None}
    if any(w in desc_lower for w in ["cerrar aplicación", "close app"]):
        return {"action": "close_app", "value": None}
    if any(w in desc_lower for w in ["cerrar pestaña", "close tab"]):
        return {"action": "close_tab", "value": None}
    if any(w in desc_lower for w in ["nueva pestaña", "new tab"]):
        return {"action": "new_tab", "value": None}
    if any(w in desc_lower for w in ["recargar página", "refresh page"]):
        return {"action": "refresh_page", "value": None}

    return {"action": "unknown", "value": None}

# ============================================================
# 8. PUNTO DE ENTRADA PRINCIPAL
# ============================================================
def computer_settings(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    if not _PYAUTOGUI:
        return "pyautogui no está instalado. Ejecuta: pip install pyautogui"

    params = parameters or {}
    raw_action = params.get("action", "").strip()
    description = params.get("description", "").strip()
    value = params.get("value", None)

    if not raw_action and description:
        detected = _detect_action(description)
        raw_action = detected.get("action", "")
        if value is None:
            value = detected.get("value")

    action = raw_action.lower().strip().replace(" ", "_").replace("-", "_")

    if not action or action == "unknown":
        return "No se pudo determinar la acción. Intenta ser más específico."

    # No imprimimos el mensaje de administrador aquí
    if player:
        player.write_log(f"[Settings] {action}")

    if action in _DANGEROUS_ACTIONS:
        confirmed = str(params.get("confirmed", "")).lower()
        if confirmed not in ("yes", "true", "1", "confirm", "sí", "si"):
            return f"Esto va a {action} el computador. Confirma con 'confirmed=yes' o di 'sí'."

    if action == "volume_set":
        if value is None:
            return "Por favor especifica el valor del volumen (0-100)."
        try:
            volume_set(int(value))
            return f"Volumen ajustado al {value}%."
        except Exception as e:
            return f"Error al ajustar volumen: {e}"

    if action == "set_brightness":
        if value is None:
            return "Por favor especifica el valor del brillo (0-100)."
        try:
            set_brightness(int(value))
            return f"Brillo ajustado al {value}%."
        except Exception as e:
            return f"Error al ajustar brillo: {e}"

    if action in ("type_text", "write_on_screen", "type", "write"):
        text = str(value or params.get("text", "")).strip()
        if not text:
            return "No se proporcionó texto para escribir."
        enter_after = str(params.get("press_enter", "false")).lower() in ("true", "1", "yes")
        type_text(text, press_enter_after=enter_after)
        return f"Escrito: {text[:80]}"

    if action == "press_key":
        key = str(value or params.get("key", "")).strip()
        if not key:
            return "No se especificó tecla."
        press_key(key)
        return f"Tecla presionada: {key}"

    if action in ("reload_n", "refresh_n", "reload_page_n"):
        try:
            reload_page_n(int(value or 1))
            return f"Recargado {value or 1} vez/veces."
        except Exception as e:
            return f"Error al recargar: {e}"

    if action == "scroll_up":
        scroll_up(int(value or 500))
        return "Scroll hacia arriba."

    if action == "scroll_down":
        scroll_down(int(value or 500))
        return "Scroll hacia abajo."

    func = ACTION_MAP.get(action)
    if not func:
        return f"Acción desconocida: '{action}'. Acciones válidas: {', '.join(sorted(ACTION_MAP.keys())[:10])}..."

    try:
        func()
        return f"Hecho: {action}."
    except Exception as e:
        return f"Error en {action}: {e}"