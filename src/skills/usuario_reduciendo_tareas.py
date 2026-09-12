from datetime import datetime
import hashlib
import json
import logging
import os
import psutil
import subprocess
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
def run(params):
    """Habilidad 'usuario_reduciendo_tareas' orientada a la auditoría
    y defensa de integridad de flujos de trabajo locales.
    Verifica directorios de automatización, audita procesos sospechosos
    y genera un reporte JSON de los ejecutables y scripts monitoreados.
    """
    target_dir = params.get(
        "target_dir", os.path.expanduser("~/Desktop")
    )
    allowed_extensions = params.get(
        "allowed_extensions", [".py", ".sh", ".bat", ".ps1"]
    )
    logging.info(
        f"Iniciando auditoría de flujos de trabajo en: {target_dir}"
    )
    audited_files = []
    suspicious_processes = []
    try:
        # 1. Auditoría de archivos en el directorio objetivo (simulando scripts de automatización)
        if os.path.exists(target_dir):
            for root, dirs, files in os.walk(target_dir):
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in allowed_extensions:
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, "rb") as f:
                                file_hash = hashlib.sha256(
                                    f.read()
                                ).hexdigest()
                            audited_files.append(
                                {
                                    "file_name": file,
                                    "path": file_path,
                                    "sha256": file_hash,
                                    "status": "monitored_secure",
                                }
                            )
                        except Exception as e:
                            logging.error(
                                f"No se pudo leer el archivo {file_path}: {str(e)}"
                            )
        else:
            logging.warning(
                f"El directorio objetivo no existe: {target_dir}"
            )
        # 2. Auditoría de procesos activos en búsqueda de ejecución anómala relacionada con automatización
        for proc in psutil.process_iter(
            ["pid", "name", "cmdline", "username"]
        ):
            try:
                pinfo = proc.info
                name = pinfo.get("name", "").lower()
                # Monitoreo básico de intérpretes que podrían ejecutar tareas automatizadas no verificadas
                if name in [
                    "powershell.exe",
                    "cmd.exe",
                    "bash",
                    "python.exe",
                ]:
                    cmdline = pinfo.get("cmdline")
                    suspicious_processes.append(
                        {
                            "pid": pinfo.get("pid"),
                            "name": name,
                            "cmdline": (
                                " ".join(cmdline)
                                if cmdline
                                else ""
                            ),
                            "user": pinfo.get("username"),
                        }
                    )
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                pass
        report = {
            "status": "success",
            "skill": "usuario_reduciendo_tareas",
            "audit_time": datetime.now().isoformat(),
            "target_directory": target_dir,
            "audited_scripts_count": len(audited_files),
            "audited_scripts": audited_files,
            "active_interpreters_monitored": len(
                suspicious_processes
            ),
            "suspicious_processes": suspicious_processes,
        }
        logging.info(
            "Auditoría de flujos de trabajo completada con éxito."
        )
        return report
    except Exception as e:
        logging.error(
            f"Error crítico ejecutando la habilidad: {str(e)}"
        )
        return {
            "status": "error",
            "skill": "usuario_reduciendo_tareas",
            "audit_time": datetime.now().isoformat(),
            "message": str(e),
        }