from datetime import datetime
import json
import logging
import os
import psutil
import subprocess
# Configuración de logging para depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
)
logger = logging.getLogger("usuario_entre_diferentes")
def run(params):
    """Módulo de Macros Contextuales y Auditoría de Procesos Activos.
    Permite gestionar flujos de trabajo de manera segura, identificando y
    cerrando
    aplicaciones distractoras permitidas y abriendo herramientas de
    desarrollo,
    generando un reporte JSON con las acciones tomadas para la auditoría del
    sistema.
    """
    mode = params.get("mode", "audit")  # 'audit' o 'execute_macro'
    distractor_apps = params.get(
        "distractors",
        ["notepad.exe", "calc.exe", "mspaint.exe"],
    )
    target_ides = params.get("ides", ["code", "devenv"])
    report_format = params.get("format", "json")
    logger.info(
        f"Iniciando habilidad 'usuario_entre_diferentes' en modo: {mode}"
    )
    action_log = []
    active_processes = []
    try:
        # Auditoría de procesos actuales utilizando psutil
        for proc in psutil.process_iter(["pid", "name", "username"]):
            try:
                pinfo = proc.info
                active_processes.append(pinfo)
                # Si estamos ejecutando la macro, terminamos distractores de forma segura
                if (
                    mode == "execute_macro"
                    and pinfo["name"] in distractor_apps
                ):
                    logger.warning(
                        f"Terminando aplicación distractor autorizada: {pinfo['name']} (PID: {pinfo['pid']})"
                    )
                    proc.terminate()
                    proc.wait(timeout=3)
                    action_log.append(
                        {
                            "action": "terminate",
                            "process": pinfo["name"],
                            "pid": pinfo["pid"],
                            "status": "success",
                        }
                    )
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.TimeoutExpired,
            ) as e:
                logger.debug(f"No se pudo procesar un proceso: {e}")
        # Si el modo es 'execute_macro', lanzamos las herramientas de desarrollo de forma segura
        if mode == "execute_macro":
            for ide in target_ides:
                try:
                    logger.info(
                        f"Lanzando herramienta de desarrollo: {ide}"
                    )
                    # Utilizando subprocess para abrir herramientas de forma controlada
                    subprocess.Popen(
                        [ide],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    action_log.append(
                        {"action": "launch", "tool": ide, "status": "success"}
                    )
                except Exception as e:
                    logger.error(f"Error al lanzar la herramienta {ide}: {e}")
                    action_log.append(
                        {
                            "action": "launch",
                            "tool": ide,
                            "status": "error",
                            "details": str(e),
                        }
                    )
        # Construcción del reporte de auditoría/ejecución
        report = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "mode": mode,
            "actions_taken": action_log,
            "total_active_processes_scanned": len(active_processes),
        }
        logger.info(
            "Habilidad 'usuario_entre_diferentes' ejecutada exitosamente."
        )
        if report_format == "json":
            return report
        else:
            return {
                "status": "success",
                "raw_report": json.dumps(report, indent=4),
            }
    except Exception as e:
        logger.critical(
            f"Error crítico en la habilidad 'usuario_entre_diferentes': {e}"
        )
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "message": str(e),
        }