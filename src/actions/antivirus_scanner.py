# src/actions/antivirus_scanner.py
"""
Escáner Antivirus para AP0L0
Versión completa desde JARVIS
Análisis de: Registro de inicio, Procesos activos, Archivos recientes
"""

import os
try:
    import winreg
    _WINREG_AVAILABLE = True
except ImportError:
    winreg = None
    _WINREG_AVAILABLE = False
try:
    import psutil
except ImportError:
    psutil = None
import json
import asyncio
import time
import shutil
import stat
from pathlib import Path

# ===== CONFIGURACIÓN DE AP0L0 =====
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "src" / "config" / "api_keys.json"


def _load_config():
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_config(config):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def get_exclusions():
    config = _load_config()
    return config.get("av_exclusions", [])


def is_excluded(target, exclusions):
    if not target or not exclusions:
        return False
    t_norm = target.replace("\\", "/").lower()
    for exc in exclusions:
        exc_norm = exc.replace("\\", "/").lower()
        if exc_norm == t_norm or exc_norm in t_norm:
            return True
    return False


EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def check_registry_startup():
    entries = []
    if not _WINREG_AVAILABLE:
        return entries
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        for i in range(256):
            try:
                name, val, typ = winreg.EnumValue(key, i)
                entries.append({"name": name, "path": val, "hive": "HKCU\\Run"})
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[AV] Error leyendo HKCU: {e}")

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        for i in range(256):
            try:
                name, val, typ = winreg.EnumValue(key, i)
                entries.append({"name": name, "path": val, "hive": "HKLM\\Run"})
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[AV] Error leyendo HKLM: {e}")
    return entries


def check_running_processes():
    proc_list = []
    if psutil is None:
        return proc_list
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            info = proc.info
            proc_list.append({
                "pid": info.get('pid') or 0,
                "name": info.get('name') or '',
                "path": info.get('exe') or ''
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return proc_list


def collect_files_to_scan():
    paths = []
    folders = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Downloads"),
        os.environ.get("TEMP"),
        os.environ.get("TMP"),
        os.path.dirname(os.path.abspath(__file__))
    ]
    folders = list(set([os.path.abspath(f) for f in folders if f and os.path.exists(f)]))
    for folder in folders:
        try:
            for root, dirs, files in os.walk(folder):
                for d in ["node_modules", "venv", ".git", "__pycache__", ".gemini", ".claude", "dist"]:
                    if d in dirs:
                        dirs.remove(d)
                rel_path = os.path.relpath(root, folder)
                depth = 0 if rel_path == "." else len(rel_path.split(os.sep))
                if depth > 2:
                    dirs.clear()
                for file in files:
                    filepath = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(filepath)
                        paths.append((filepath, mtime))
                    except OSError:
                        pass
        except Exception as e:
            print(f"[AV] Error en carpeta {folder}: {e}")
    paths.sort(key=lambda x: x[1], reverse=True)
    return [p[0] for p in paths[:200]]


def is_file_suspicious(filepath):
    filename = os.path.basename(filepath).lower()
    try:
        if os.path.isfile(filepath) and os.path.getsize(filepath) < 1024 * 500:
            with open(filepath, 'rb') as f:
                content = f.read(2048)
                if EICAR_SIGNATURE in content:
                    return "Threat.EICAR.TestFile", "Cadena de prueba EICAR detectada"
    except Exception:
        pass

    parts = filename.split('.')
    if len(parts) >= 3:
        dangerous_exts = ["exe", "bat", "cmd", "vbs", "js", "scr", "msi", "lnk", "pif", "com"]
        if parts[-1] in dangerous_exts:
            benign_exts = ["pdf", "jpg", "jpeg", "png", "txt", "doc", "docx", "xls", "xlsx", "zip", "rar", "mp4"]
            if parts[-2] in benign_exts:
                return "Suspicious.DoubleExtension", f"Doble extensión: .{parts[-2]}.{parts[-1]}"

    suspicious_keywords = ["mimikatz", "keylogger", "ransomware", "miner.exe", "backdoor", "trojan", "virus.exe"]
    for kw in suspicious_keywords:
        if kw in filename:
            return "Suspicious.Keywords", f"Nombre sospechoso: {kw}"

    if "temp" in filepath.lower() or "tmp" in filepath.lower():
        if filename.endswith((".exe", ".scr", ".pif", ".vbs", ".bat")):
            return "Suspicious.TempExecutable", "Ejecutable en carpeta temporal"

    return None, None


# ===== FUNCIÓN PRINCIPAL DE ESCANEO =====
async def ejecutar_scan_antivirus(ui_callback, speak_callback):
    """
    Ejecuta el escaneo antivirus.
    ui_callback: función que recibe dicts con estado y logs
    speak_callback: función para hablar (texto)
    """
    threats_detected = []
    exclusions = get_exclusions()

    try:
        await ui_callback({
            "type": "av_start",
            "message": "Iniciando motor antivirus AP0L0..."
        })
        await asyncio.sleep(0.5)

        # ---- 1. Registro ----
        await ui_callback({
            "type": "av_progress",
            "step": "registry",
            "message": "Analizando claves de inicio del registro...",
            "percent": 5,
            "threats_found": len(threats_detected)
        })
        await asyncio.sleep(0.5)

        reg_entries = check_registry_startup()
        for reg in reg_entries:
            path_lower = reg["path"].lower()
            for kw in ["temp", "tmp", "mimikatz", "miner", "keylogger", "exploit"]:
                if kw in path_lower or kw in reg["name"].lower():
                    threat = {
                        "type": "registry",
                        "name": reg["name"],
                        "target": reg["path"],
                        "class": "Suspicious.RegistryStartup",
                        "desc": f"Entrada sospechosa ({reg['hive']})"
                    }
                    if is_excluded(threat["target"], exclusions):
                        continue
                    threats_detected.append(threat)
                    await ui_callback({
                        "type": "av_threat_detected",
                        "threat": threat
                    })

        # ---- 2. Procesos ----
        await ui_callback({
            "type": "av_progress",
            "step": "processes",
            "message": "Analizando procesos activos...",
            "percent": 15,
            "threats_found": len(threats_detected)
        })
        await asyncio.sleep(0.5)

        processes = check_running_processes()
        for i, proc in enumerate(processes):
            name_lower = proc["name"].lower()
            path_lower = proc["path"].lower()

            detected = False
            desc = ""
            if "mimikatz" in name_lower or "miner.exe" in name_lower or "keylogger" in name_lower:
                detected = True
                desc = "Proceso malicioso conocido"
            elif ("temp" in path_lower or "tmp" in path_lower) and name_lower.endswith((".exe", ".bat")):
                detected = True
                desc = "Proceso ejecutándose desde temporal"

            if detected:
                threat = {
                    "type": "process",
                    "name": proc["name"],
                    "target": f"PID {proc['pid']} ({proc['path']})",
                    "class": "Suspicious.ActiveProcess",
                    "desc": desc
                }
                if is_excluded(threat["target"], exclusions) or is_excluded(proc["path"], exclusions):
                    continue
                threats_detected.append(threat)
                await ui_callback({
                    "type": "av_threat_detected",
                    "threat": threat
                })

            if i % 15 == 0:
                await ui_callback({
                    "type": "av_progress",
                    "step": "processes",
                    "message": f"Revisando: {proc['name']} (PID {proc['pid']})",
                    "percent": int(15 + (i / len(processes)) * 15),
                    "threats_found": len(threats_detected)
                })
                await asyncio.sleep(0.02)

        # ---- 3. Archivos ----
        await ui_callback({
            "type": "av_progress",
            "step": "files",
            "message": "Recolectando archivos recientes...",
            "percent": 30,
            "threats_found": len(threats_detected)
        })
        await asyncio.sleep(0.5)

        files_to_scan = collect_files_to_scan()
        total_files = len(files_to_scan)

        for idx, filepath in enumerate(files_to_scan):
            t_class, t_desc = is_file_suspicious(filepath)
            if t_class:
                threat = {
                    "type": "file",
                    "name": os.path.basename(filepath),
                    "target": filepath,
                    "class": t_class,
                    "desc": t_desc
                }
                if is_excluded(threat["target"], exclusions):
                    continue
                threats_detected.append(threat)
                await ui_callback({
                    "type": "av_threat_detected",
                    "threat": threat
                })

            pct = int(30 + ((idx + 1) / total_files) * 69) if total_files > 0 else 99
            await ui_callback({
                "type": "av_progress",
                "step": "files",
                "message": filepath,
                "percent": pct,
                "threats_found": len(threats_detected)
            })
            await asyncio.sleep(0.05)

        # ---- Final ----
        status = "infected" if threats_detected else "clean"
        await ui_callback({
            "type": "av_complete",
            "status": status,
            "percent": 100,
            "threats": threats_detected
        })

        if status == "infected":
            await speak_callback(f"Análisis completado. Atención: se detectaron {len(threats_detected)} amenaza(s). Revise la consola para más detalles.")
        else:
            await speak_callback("Análisis de seguridad completado. Su sistema está limpio. Ninguna amenaza detectada.")

    except asyncio.CancelledError:
        print("[AV] Escaneo cancelado por el usuario.")
        await ui_callback({
            "type": "av_cancel",
            "message": "Escaneo interrumpido."
        })
    except Exception as e:
        print(f"[AV] Error durante el escaneo: {e}")
        await ui_callback({
            "type": "av_complete",
            "status": "error",
            "message": f"Error en el escaneo: {e}"
        })
        await speak_callback("Ocurrió un error durante el análisis antivirus.")


# ===== ALIAS PARA COMPATIBILIDAD CON NOMBRE FRANCÉS =====
executer_scan_antivirus = ejecutar_scan_antivirus


# ===== FUNCIÓN EXPORTABLE PARA AP0L0 =====
async def antivirus_scan(params: dict, player=None, speak=None) -> str:
    if player:
        player.write_log("[Antivirus] Iniciando escaneo de seguridad...")

    async def ui_callback(data):
        if data.get("type") == "av_progress":
            msg = data.get("message", "")
            pct = data.get("percent", 0)
            threats = data.get("threats_found", 0)
            if player:
                player.write_log(f"[AV] {msg} ({pct}%) - Amenazas: {threats}")
        elif data.get("type") == "av_threat_detected":
            threat = data.get("threat", {})
            if player:
                player.write_log(f"[AV] 🛡️ Amenaza: {threat.get('name')} - {threat.get('desc')}")
        elif data.get("type") == "av_complete":
            status = data.get("status")
            threats = data.get("threats", [])
            if player:
                if status == "infected":
                    player.write_log(f"[AV] ⚠️ Sistema infectado. {len(threats)} amenaza(s).")
                else:
                    player.write_log(f"[AV] ✅ Sistema limpio.")
        elif data.get("type") == "av_start":
            if player:
                player.write_log("[AV] Iniciando motor antivirus...")
        elif data.get("type") == "av_cancel":
            if player:
                player.write_log("[AV] Escaneo cancelado.")

    async def speak_callback(text):
        if speak:
            await speak(text)

    await ejecutar_scan_antivirus(ui_callback, speak_callback)
    return "Escaneo antivirus finalizado."
