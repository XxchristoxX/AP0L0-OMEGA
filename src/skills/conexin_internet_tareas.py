from datetime import datetime
import json
import logging
import os
import psutil
import socket
import subprocess
# Configuración de logging para auditoría y defensa
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - AP0L0 - [SECURITY] - %(levelname)s - %(message)s",
)
def run(params):
    """Módulo AP0L0: Auditoría de Conectividad, Control de Tareas Locales
    y Verificación de Privacidad (Aislamiento Offline).
    """
    action = params.get("action", "audit_connectivity")
    results = {}
    logging.info(
        f"Iniciando ejecución de habilidad 'conexin_internet_tareas' con acción: {action}"
    )
    try:
        if action == "audit_connectivity":
            # Audita conexiones de red activas para detectar exfiltración de datos o C2
            active_connections = []
            for conn in psutil.net_connections(kind="inet"):
                try:
                    proc = psutil.Process(conn.pid) if conn.pid else None
                    proc_name = proc.name() if proc else "Desconocido"
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    proc_name = "Inaccesible"
                active_connections.append(
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
                        "process_name": proc_name,
                    }
                )
            results = {
                "status": "success",
                "audit_type": "network_connections",
                "total_connections": len(active_connections),
                "connections": active_connections,
            }
        elif action == "check_offline_readiness":
            # Verifica si el sistema puede operar de forma aislada (requisito para macros offline seguras)
            # Comprueba la resolución DNS local sin salir a internet pública
            test_host = params.get("test_host", "localhost")
            try:
                ip_resolved = socket.gethostbyname(test_host)
                dns_status = "Operational"
            except socket.gaierror:
                ip_resolved = None
                dns_status = "Failed"
            # Evalúa interfaces de red activas
            interfaces = psutil.net_if_addrs()
            if_status = {
                iface: bool(addrs) for iface, addrs in interfaces.items()
            }
            results = {
                "status": "success",
                "audit_type": "offline_readiness",
                "local_dns_resolution": {
                    "host": test_host,
                    "resolved_ip": ip_resolved,
                    "status": dns_status,
                },
                "network_interfaces": if_status,
                "recommendation": (
                    "Sistema apto para procesamiento de voz y macros offline."
                    if dns_status == "Operational"
                    else "Revisar configuración de red."
                ),
            }
        elif action == "simulate_offline_macro":
            # Simula la ejecución segura de una tarea local dictada (sin llamadas externas)
            macro_name = params.get("macro_name", "status_check")
            allowed_macros = ["status_check", "secure_lock", "memory_flush"]
            if macro_name in allowed_macros:
                if macro_name == "status_check":
                    output = f"CPU Usage: {psutil.cpu_percent()}% | RAM Usage: {psutil.virtual_memory().percent}%"
                elif macro_name == "secure_lock":
                    output = (
                        "Simulación: Cierre preventivo de sockets expuestos."
                    )
                elif macro_name == "memory_flush":
                    output = "Simulación: Limpieza de búferes de memoria local."
                else:
                    output = "Macro desconocida."
                results = {
                    "status": "success",
                    "macro": macro_name,
                    "execution_mode": "offline_secure",
                    "output": output,
                }
            else:
                logging.warning(
                    f"Intento de ejecutar macro no autorizada: {macro_name}"
                )
                results = {
                    "status": "error",
                    "message": "Macro no autorizada o inexistente en el perfil de seguridad.",
                }
        else:
            results = {
                "status": "error",
                "message": f"Acción '{action}' no reconocida por el módulo AP0L0.",
            }
    except Exception as e:
        logging.error(f"Error crítico en módulo 'conexin_internet_tareas': {str(e)}")
        return {
            "status": "failure",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        }
    # Estructura del reporte final requerido por el estándar de seguridad
    report = {
        "module": "conexin_internet_tareas",
        "agent": "AP0L0",
        "timestamp": datetime.now().isoformat(),
        "data": results,
    }
    logging.info("Ejecución finalizada con éxito. Generando reporte JSON.")
    return report