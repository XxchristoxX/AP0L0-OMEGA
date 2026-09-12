from datetime import datetime
import json
import logging
import os
import psutil
import socket
import subprocess
# Configuración de logging para auditoría y depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
def run(params):
    """Módulo de auditoría y defensa para verificar la seguridad e integridad
    del subsistema de comandos por voz local (rdenes_voz_directamente).
    Verifica procesos activos, uso de recursos y puertos en escucha
    asociados a posibles backdoors o servicios de escucha no autorizados.
    """
    logging.info(
        "Iniciando auditoría de seguridad para la habilidad 'rdenes_voz_directamente'."
    )
    # Parámetros configurables con valores seguros por defecto
    target = params.get("target", "127.0.0.1")
    monitored_ports = params.get(
        "ports", [5000, 8080, 8443]
    )  # Puertos típicos de APIs de voz locales
    audit_results = {
        "status": "success",
        "module": "rdenes_voz_directamente",
        "audit_time": datetime.now().isoformat(),
        "target": target,
        "process_check": [],
        "network_listeners": [],
        "system_resources": {},
    }
    try:
        # 1. Auditoría de Procesos: Buscar procesos sospechosos o relacionados con síntesis de voz / IA local
        target_keywords = [
            "whisper",
            "vosk",
            "piper",
            "coqui",
            "llama",
            "ollama",
            "python",
        ]
        for proc in psutil.process_iter(
            ["pid", "name", "cmdline", "username"]
        ):
            try:
                pinfo = proc.info
                name = (pinfo["name"] or "").lower()
                cmdline = " ".join(pinfo["cmdline"] or []).lower()
                # Identificar si hay procesos corriendo motores de voz o modelos locales
                if any(kw in name or kw in cmdline for kw in target_keywords):
                    audit_results["process_check"].append(
                        {
                            "pid": pinfo["pid"],
                            "name": pinfo["name"],
                            "cmdline": (
                                pinfo["cmdline"][:3]
                                if pinfo["cmdline"]
                                else []
                            ),
                            "user": pinfo["username"],
                            "status": "monitored",
                        }
                    )
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue
        logging.info(
            f"Procesos relevantes detectados: {len(audit_results['process_check'])}"
        )
        # 2. Auditoría de Red: Verificar si hay servicios locales escuchando en los puertos especificados
        for port in monitored_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((target, port))
            if result == 0:
                audit_results["network_listeners"].append(
                    {
                        "port": port,
                        "status": "OPEN",
                        "risk": "Medium - Local listener active",
                    }
                )
                logging.warning(
                    f"Puerto de escucha detectado abierto: {port}"
                )
            else:
                audit_results["network_listeners"].append(
                    {"port": port, "status": "CLOSED", "risk": "Low"}
                )
            sock.close()
        # 3. Auditoría de Recursos del Sistema (CPU, Memoria) para asegurar que no hay consumo anómalo
        audit_results["system_resources"] = {
            "cpu_usage_percent": psutil.cpu_percent(interval=1),
            "memory_usage_percent": psutil.virtual_memory().percent,
            "disk_usage_percent": psutil.disk_usage("/").percent,
        }
        logging.info(
            "Auditoría completada exitosamente para 'rdenes_voz_directamente'."
        )
    except Exception as e:
        logging.error(f"Error durante la ejecución de la auditoría: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "audit_time": datetime.now().isoformat(),
        }
    return audit_results