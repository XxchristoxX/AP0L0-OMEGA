# src/actions/uninstaller_helper.py
"""
Ayudante para desinstalar programas (Windows)
"""

import os
try:
    import winreg
    _WINREG_AVAILABLE = True
except ImportError:
    winreg = None
    _WINREG_AVAILABLE = False
import re
import shutil
import subprocess


def clean_name_for_search(name):
    name = re.sub(r'\(.*?\)|v\d+(\.\d+)*|\d+\.\d+(\.\d+)*', '', name)
    name = re.sub(r'[^a-zA-Z0-9\s-]', '', name)
    return name.strip()


def list_installed_programs():
    if not _WINREG_AVAILABLE:
        return []
    paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall")
    ]
    programs = []
    seen = set()
    for hive, path in paths:
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ)
                    name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                    if name and name not in seen:
                        seen.add(name)
                        uninstall_string = winreg.QueryValueEx(subkey, "UninstallString")[0]
                        publisher = winreg.QueryValueEx(subkey, "Publisher")[0] if "Publisher" in subkey else ""
                        version = winreg.QueryValueEx(subkey, "DisplayVersion")[0] if "DisplayVersion" in subkey else ""
                        install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0] if "InstallLocation" in subkey else ""
                        programs.append({
                            "name": name,
                            "subkey": subkey_name,
                            "publisher": publisher,
                            "version": version,
                            "uninstall_string": uninstall_string,
                            "install_location": install_location,
                            "hive": "HKLM" if hive == winreg.HKEY_LOCAL_MACHINE else "HKCU"
                        })
                    winreg.CloseKey(subkey)
                except Exception:
                    pass
            winreg.CloseKey(key)
        except Exception:
            pass
    return programs


def scan_file_leftovers(app_name, publisher="", install_location=""):
    app_name_clean = clean_name_for_search(app_name).lower()
    app_name_no_space = app_name_clean.replace(" ", "")
    leftovers = []
    seen_paths = set()
    if install_location and os.path.exists(install_location):
        abs_path = os.path.abspath(install_location)
        if len(abs_path) > 4:
            seen_paths.add(abs_path)
            leftovers.append({"type": "folder", "path": abs_path, "desc": "Carpeta de instalación"})
    search_dirs = [
        os.environ.get("ProgramFiles", "C:\\Program Files"),
        os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
        os.environ.get("ProgramData", "C:\\ProgramData"),
        os.path.expanduser("~/AppData/Local"),
        os.path.expanduser("~/AppData/Roaming"),
        os.path.expanduser("~/AppData/LocalLow")
    ]
    for base_dir in search_dirs:
        if not base_dir or not os.path.exists(base_dir):
            continue
        try:
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                if not os.path.isdir(item_path):
                    continue
                item_lower = item.lower()
                item_no_space = item_lower.replace(" ", "")
                match = False
                if app_name_clean and len(app_name_clean) > 3 and app_name_clean in item_lower:
                    match = True
                elif app_name_no_space and len(app_name_no_space) > 3 and app_name_no_space in item_no_space:
                    match = True
                if match:
                    abs_path = os.path.abspath(item_path)
                    if abs_path not in seen_paths and len(abs_path) > 4:
                        seen_paths.add(abs_path)
                        leftovers.append({"type": "folder", "path": abs_path, "desc": f"Carpeta en {os.path.basename(base_dir)}"})
        except Exception:
            pass
    return leftovers


def scan_registry_leftovers(app_name, publisher=""):
    if not _WINREG_AVAILABLE:
        return []
    app_name_clean = clean_name_for_search(app_name).lower()
    app_name_no_space = app_name_clean.replace(" ", "")
    leftovers = []
    hives = [
        (winreg.HKEY_CURRENT_USER, "Software"),
        (winreg.HKEY_LOCAL_MACHINE, "Software"),
        (winreg.HKEY_LOCAL_MACHINE, "Software\\Wow6432Node")
    ]
    for hive, base_path in hives:
        hive_name = "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
        try:
            key = winreg.OpenKey(hive, base_path, 0, winreg.KEY_READ)
            for i in range(winreg.QueryInfoKey(key)[0]):
                subkey_name = winreg.EnumKey(key, i)
                subkey_name_lower = subkey_name.lower()
                full_path = f"{hive_name}\\{base_path}\\{subkey_name}"
                match = False
                if app_name_clean and len(app_name_clean) > 3 and app_name_clean in subkey_name_lower:
                    match = True
                elif app_name_no_space and len(app_name_no_space) > 3 and app_name_no_space in subkey_name_lower.replace(" ", ""):
                    match = True
                if match:
                    leftovers.append({"type": "registry", "hive": hive_name, "path": full_path, "desc": "Clave de registro"})
            winreg.CloseKey(key)
        except Exception:
            pass
    return leftovers


def run_uninstall_process(uninstall_string):
    try:
        p = subprocess.Popen(uninstall_string, shell=True)
        p.wait()
        return True, "Desinstalación completada."
    except Exception as e:
        return False, str(e)


def delete_registry_key_recursive(hive, path):
    if not _WINREG_AVAILABLE:
        return False
    hkey_hive = winreg.HKEY_CURRENT_USER if hive == "HKCU" else winreg.HKEY_LOCAL_MACHINE
    try:
        key = winreg.OpenKey(hkey_hive, path, 0, winreg.KEY_ALL_ACCESS)
        subkeys = []
        for i in range(winreg.QueryInfoKey(key)[0]):
            subkeys.append(winreg.EnumKey(key, i))
        winreg.CloseKey(key)
        for subkey in subkeys:
            delete_registry_key_recursive(hive, f"{path}\\{subkey}")
        parent_path, key_name = path.rsplit("\\", 1)
        parent_key = winreg.OpenKey(hkey_hive, parent_path, 0, winreg.KEY_ALL_ACCESS)
        winreg.DeleteKey(parent_key, key_name)
        winreg.CloseKey(parent_key)
        return True
    except Exception:
        return False


def clean_leftover_item(item):
    if item["type"] == "folder":
        if os.path.exists(item["path"]):
            try:
                shutil.rmtree(item["path"])
                return True, "Carpeta eliminada."
            except Exception as e:
                return False, str(e)
        return True, "Carpeta ya no existe."
    elif item["type"] == "registry":
        hive = item["hive"]
        path = item["path"].split("\\", 1)[1]
        ok = delete_registry_key_recursive(hive, path)
        return ok, "Clave de registro eliminada." if ok else "Error eliminando clave."
    return False, "Tipo no soportado."


# ===== FUNCIÓN EXPORTABLE =====

async def uninstaller(params: dict, player=None, speak=None) -> str:
    action = params.get("action", "list")
    if action == "list":
        programs = list_installed_programs()
        if not programs:
            return ("La lista de programas instalados mediante Registro solo está "
                    "disponible en Windows." if not _WINREG_AVAILABLE else
                    "No se encontraron programas instalados.")
        result = "Programas instalados:\n" + "\n".join(f"  • {p['name']}" for p in programs[:30])
    elif action == "scan_leftovers":
        name = params.get("name", "")
        if not name:
            return "Falta el nombre del programa."
        # Buscar el programa en la lista
        programs = list_installed_programs()
        prog = next((p for p in programs if p["name"].lower() == name.lower()), None)
        if not prog:
            return f"Programa '{name}' no encontrado."
        files = scan_file_leftovers(prog["name"], prog.get("publisher", ""), prog.get("install_location", ""))
        regs = scan_registry_leftovers(prog["name"], prog.get("publisher", ""))
        leftovers = files + regs
        if not leftovers:
            return f"No se encontraron residuos para {name}."
        result = f"Residuos para {name}:\n" + "\n".join(f"  • {l['path']} ({l['desc']})" for l in leftovers)
    else:
        result = "Acción no soportada."
    if speak:
        speak(result)
    if player:
        player.write_log(f"[Uninstaller] {result}")
    return result
