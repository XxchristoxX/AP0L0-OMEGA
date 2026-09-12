from datetime import datetime
import json
import logging
import os
import psutil
# Configuración de logs para depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
def run(params):
    """Habilidad 'mayor_privacidad_gestionar' para auditar y defender
    la privacidad del sistema, verificando procesos en segundo plano
    y asegurando que no existan fugas de datos locales no autorizadas.
    """
    action = params.get("action", "audit_background_processes")
    report = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": {},
    }
    try:
        if action == "audit_background_processes":
            logging.info(
                "Iniciando auditoría de procesos en segundo plano..."
            )
            suspicious_keywords = params.get(
                "keywords", ["keylogger", "spyware", "miner", "capture"]
            )
            flagged_processes = []
            for proc in psutil.iter_processes(
                ["pid", "name", "username", "connections"]
            ):
                try:
                    proc_info = proc.info
                    name = proc_info.get("name", "").lower()
                    # Verificar si algún proceso coincide con palabras clave sospechosas
                    if any(keyword in name for keyword in suspicious_keywords):
                        flagged_processes.append(
                            {
                                "pid": proc_info.get("pid"),
                                "name": proc_info.get("name"),
                                "username": proc_info.get("username"),
                            }
                        )
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue
            report["details"] = {
                "total_processes_checked": len(list(psutil.pids())),
                "flagged_processes": flagged_processes,
                "privacy_status": (
                    "Seguro" if not flagged_processes else "Revisión requerida"
                ),
            }
            logging.info(
                f"Auditoría completada. Procesos marcados: {len(flagged_processes)}"
            )
        elif action == "check_local_listeners":
            logging.info(
                "Verificando servicios y puertos locales activos..."
            )
            connections = []
            for conn in psutil.net_connections(kind="inet"):
                if conn.status == "LISTEN":
                    connections.append(
                        {
                            "local_address": f"{conn.laddr.ip}:{conn.laddr.port}",
                            "pid": conn.pid,
                            "status": conn.status,
                        }
                    )
            report["details"] = {
                "active_listeners": connections,
                "total_listeners": len(connections),
            }
            logging.info(
                f"Puertos en escucha analizados: {len(connections)}"
            )
        else:
            report["status"] = "error"
            report["message"] = f"Acción desconocida: {action}"
            logging.error(f"Acción desconocida solicitada: {action}")
    except Exception as e:
        logging.error(f"Error durante la ejecución de la habilidad: {str(e)}")
        report["status"] = "error"
        report["error_message"] = str(e)
    # Exportar reporte en formato JSON seguro
    report_filename = f"privacy_audit_report_{int(datetime.now().timestamp())}.json"
    try:
        with open(report_filename, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=4)
        report["report_file"] = report_filename
        logging.info(f"Reporte generado exitosamente: {report_filename}")
    except IOError as io_err:
        logging.error(f"No se pudo guardar el archivo de reporte: {io_err}")
    return report