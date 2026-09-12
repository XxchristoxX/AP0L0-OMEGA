from datetime import datetime
import json
import logging
import os
import psutil
import subprocess
# Configuración de logging para depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("automatizar_configuracin_entorno")
def run(params):
    """Habilidad de seguridad defensiva para auditar, verificar y gestionar
    servicios/procesos del entorno de trabajo de manera controlada.
    """
    action = params.get("action", "audit_environment")
    mode = params.get("mode", "development")
    # Definición de perfiles de procesos seguros para auditoría y gestión defensiva
    profiles = {
        "development": {
            "required_processes": ["code", "git"],
            "allowed_ports": [22, 80, 443, 3000, 8000, 8080],
        },
        "meeting": {
            "required_processes": ["zoom", "teams", "slack"],
            "allowed_ports": [443],
        },
        "secure_audit": {
            "required_processes": ["wireshark", "nmap"],
            "allowed_ports": [22, 443],
        },
    }
    report = {
        "status": "success",
        "action": action,
        "mode": mode,
        "timestamp": datetime.now().isoformat(),
        "details": {},
    }
    try:
        if action == "audit_environment":
            logger.info(
                f"Iniciando auditoría de entorno para el modo: {mode}"
            )
            # Obtener lista de procesos activos usando psutil
            active_processes = []
            for proc in psutil.process_iter(["pid", "name", "username"]):
                try:
                    active_processes.append(
                        {
                            "pid": proc.info["pid"],
                            "name": proc.info["name"],
                            "user": proc.info["username"],
                        }
                    )
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue
            # Verificar conexiones de red activas (defensa y monitoreo)
            active_connections = []
            for conn in psutil.net_connections(kind="inet"):
                if conn.status == "ESTABLISHED":
                    active_connections.append(
                        {
                            "local_address": f"{conn.laddr.ip}:{conn.laddr.port}"
                            if conn.laddr
                            else "N/A",
                            "remote_address": f"{conn.raddr.ip}:{conn.raddr.port}"
                            if conn.raddr
                            else "N/A",
                            "pid": conn.pid,
                        }
                    )
            report["details"] = {
                "active_processes_count": len(active_processes),
                "established_connections_count": len(active_connections),
                "connections": active_connections[:10],  # Limitar salida
            }
            logger.info("Auditoría de entorno completada exitosamente.")
        elif action == "verify_integrity":
            logger.info(
                "Verificando integridad de servicios críticos del sistema..."
            )
            # Ejemplo defensivo: comprobar uso de recursos para detectar anomalías
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_info = psutil.virtual_memory()
            report["details"] = {
                "cpu_usage_percent": cpu_usage,
                "memory_total_gb": round(
                    memory_info.total / (1024 ** 3), 2
                ),
                "memory_available_percent": memory_info.percent,
                "anomaly_detected": cpu_usage > 90.0
                or memory_info.percent > 90.0,
            }
            logger.info("Verificación de integridad finalizada.")
        else:
            report["status"] = "error"
            report["message"] = f"Acción desconocida: {action}"
            logger.warning(f"Se intentó ejecutar una acción no válida: {action}")
    except Exception as e:
        logger.error(
            f"Error crítico durante la ejecución de la habilidad: {str(e)}"
        )
        report["status"] = "error"
        report["error_message"] = str(e)
    # Retorno estructurado en formato JSON requerido por la especificación
    return report