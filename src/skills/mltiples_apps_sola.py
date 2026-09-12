from datetime import datetime
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
    """Implementa Macros Contextuales de Aplicaciones para auditar,
    gestionar y asegurar estados de múltiples aplicaciones de forma segura.
    """
    mode = params.get("mode", "audit_state")
    target_apps = params.get(
        "apps",
        ["zoom", "spotify", "slack", "teams", "discord"],
    )
    report = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "actions_taken": [],
        "audited_processes": [],
    }
    try:
        if mode == "audit_state":
            logging.info("Iniciando auditoría de procesos y estados de apps.")
            running_processes = []
            for proc in psutil.process_iter(
                ["pid", "name", "status", "cpu_percent", "memory_percent"]
            ):
                try:
                    pinfo = proc.info
                    pname = pinfo["name"].lower()
                    for app in target_apps:
                        if app in pname:
                            running_processes.append(
                                {
                                    "pid": pinfo["pid"],
                                    "name": pinfo["name"],
                                    "status": pinfo["status"],
                                    "cpu_usage": pinfo["cpu_percent"],
                                    "memory_usage": pinfo["memory_percent"],
                                }
                            )
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue
            report["audited_processes"] = running_processes
            report["actions_taken"].append(
                "Auditoría de aplicaciones completada exitosamente."
            )
        elif mode == "secure_context":
            # Modo defensivo: Verifica integridad básica o cierra apps innecesarias en contextos seguros
            action = params.get("action", "report_only")
            logging.info(
                f"Ejecutando modo de seguridad contextual con acción: {action}"
            )
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    pname = proc.info["name"].lower()
                    for app in target_apps:
                        if (
                            app in pname
                            and action == "terminate_unauthorized"
                        ):
                            # Simulación segura o terminación controlada según parámetros de defensa
                            proc.terminate()
                            report["actions_taken"].append(
                                f"Proceso {pname} (PID: {proc.info['pid']}) terminado por política de seguridad."
                            )
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ) as e:
                    logging.warning(
                        f"No se pudo gestionar el proceso: {str(e)}"
                    )
            if action == "report_only":
                report["actions_taken"].append(
                    "Modo seguro ejecutado sin alteraciones de estado (solo reporte)."
                )
        else:
            report["status"] = "error"
            report["message"] = f"Modo desconocido: {mode}"
            logging.error(report["message"])
    except Exception as e:
        logging.error(f"Error crítico en la habilidad mltiples_apps_sola: {str(e)}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error_message": str(e),
        }
    return report