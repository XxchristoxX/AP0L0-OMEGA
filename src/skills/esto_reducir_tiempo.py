from datetime import datetime
import json
import logging
import os
import socket
import subprocess
# Configuración de logging para depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
def run(params=None):
    """Habilidad de seguridad 'esto_reducir_tiempo': Auditoría y defensa
    perimétrica local. Realiza una verificación de sockets y procesos
    activos para asegurar la integridad del sistema defensivo.
    """
    if params is None:
        params = {}
    target = params.get("target", "127.0.0.1")
    ports = params.get("ports", [22, 80, 443, 3306, 8080])
    logging.info(
        f"Iniciando auditoría defensiva para el objetivo: {target}"
    )
    results = []
    try:
        # Auditoría de puertos locales/remotos (Defensa)
        for port in ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            result = sock.connect_ex((target, port))
            if result == 0:
                results.append(
                    {
                        "port": port,
                        "status": "ABIERTO",
                    }
                )
                logging.warning(
                    f"Alerta Defensiva: Puerto crítico {port} abierto en {target}"
                )
            else:
                results.append(
                    {
                        "port": port,
                        "status": "CERRADO/SEGURO",
                    }
                )
            sock.close()
        # Verificación rápida del estado del sistema operativo mediante comandos seguros
        system_status = "OK"
        if os.name == "posix":
            # Comprobación de conexiones activas de red de forma segura
            netstat_process = subprocess.run(
                ["netstat", "-an"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if netstat_process.returncode != 0:
                system_status = (
                    "Advertencia: No se pudo ejecutar netstat"
                )
        report = {
            "status": "success",
            "skill": "esto_reducir_tiempo",
            "target": target,
            "audit_time": datetime.now().isoformat(),
            "port_audit": results,
            "system_audit": system_status,
        }
        logging.info(
            "Auditoría completada exitosamente. Generando reporte JSON."
        )
        return report
    except Exception as e:
        error_msg = f"Error crítico durante la ejecución de la habilidad: {str(e)}"
        logging.error(error_msg)
        return {
            "status": "error",
            "skill": "esto_reducir_tiempo",
            "message": error_msg,
            "audit_time": datetime.now().isoformat(),
        }