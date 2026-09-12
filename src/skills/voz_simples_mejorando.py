from datetime import datetime
import json
import logging
import os
import psutil
import socket
import subprocess
# Configuración de logging para depuración
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("voz_simples_mejorando")
def run(params):
    """Audita y protege el sistema analizando procesos activos,
    conexiones de red y generando un reporte JSON de estado de seguridad.
    Esta función simula la validación de macros/procesos en el sistema
    para asegurar que no existan tareas desatendidas o maliciosas ejecutándose.
    """
    target_action = params.get("action", "audit_system")
    report = {
        "status": "success",
        "action": target_action,
        "timestamp": datetime.now().isoformat(),
        "details": {},
    }
    try:
        if target_action == "audit_system":
            logger.info(
                "Iniciando auditoría de procesos y conexiones de red..."
            )
            # Auditoría de procesos activos (prevención de macros no autorizadas)
            active_processes = []
            for proc in psutil.process_iter(
                ["pid", "name", "username", "cpu_percent"]
            ):
                try:
                    active_processes.append(proc.info)
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    pass
            # Auditoría de conexiones de red activas
            connections = []
            for conn in psutil.net_connections(kind="inet"):
                connections.append(
                    {
                        "fd": conn.fd,
                        "family": str(conn.family),
                        "type": str(conn.type),
                        "local_address": (
                            f"{conn.laddr.ip}:{conn.laddr.port}"
                            if conn.laddr
                            else None
                        ),
                        "remote_address": (
                            f"{conn.raddr.ip}:{conn.raddr.port}"
                            if conn.raddr
                            else None
                        ),
                        "status": conn.status,
                        "pid": conn.pid,
                    }
                )
            report["details"] = {
                "total_processes": len(active_processes),
                "active_connections": len(connections),
                "suspicious_processes_detected": [
                    p
                    for p in active_processes
                    if p["name"]
                    and any(
                        mal in p["name"].lower()
                        for mal in ["keylogger", "hook", "macro_bot"]
                    )
                ],
                "network_connections_sample": connections[
                    :10
                ],  # Muestra limitada por seguridad
            }
            logger.info("Auditoría completada exitosamente.")
        elif target_action == "check_integrity":
            logger.info("Verificando integridad del entorno de ejecución...")
            # Validación básica de permisos y archivos críticos en el entorno
            report["details"] = {
                "current_user": os.getlogin()
                if hasattr(os, "getlogin")
                else "unknown",
                "system_load": psutil.getloadavg()
                if hasattr(psutil, "getloadavg")
                else "N/A",
                "disk_usage": psutil.disk_usage("/").percent,
            }
        else:
            report["status"] = "error"
            report["message"] = f"Acción desconocida: {target_action}"
            logger.error(report["message"])
    except Exception as e:
        logger.error(f"Error crítico durante la ejecución: {str(e)}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error_message": str(e),
        }
    return report