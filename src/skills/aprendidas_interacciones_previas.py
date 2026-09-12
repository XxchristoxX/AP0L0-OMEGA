import os
import hashlib
import json
import logging
from datetime import datetime
import psutil
import requests
# Configuración de logging para depuración
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
def run(params):
    """
    Habilidad: aprendidas_interacciones_previas
    Propósito: Auditar y defender sistemas analizando patrones de procesos,
    integridad de archivos de configuración y conexiones de red sospechosas
    para prevenir accesos no autorizados o exfiltración de datos.
    """
    target_dir = params.get("target_dir", "/etc")
    report_format = params.get("format", "json")
    logging.info("Iniciando auditoría de seguridad: 'aprendidas_interacciones_previas'")
    audit_results = {
        "timestamp": datetime.now().isoformat(),
        "system_status": "secure",
        "anomalies_detected": [],
        "integrity_check": [],
        "network_connections": []
    }
    try:
        # 1. Análisis de procesos activos en busca de anomalías (Simulando aprendizaje de comportamiento)
        logging.info("Analizando procesos activos...")
        for proc in psutil.process_iter(['pid', 'name', 'username', 'connections']):
            try:
                pinfo = proc.info
                # Detectar conexiones salientes inusuales o procesos sin nombre claro
                if pinfo['name'] in ['nc', 'ncat', 'netcat', 'hydra']:
                    audit_results["anomalies_detected"].append({
                        "type": "Suspicious Process",
                        "details": f"Proceso potencialmente peligroso detectado: {pinfo['name']} (PID: {pinfo['pid']})"
                    })
                    audit_results["system_status"] = "warning"
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        # 2. Verificación de integridad de archivos críticos (Simulando análisis de bandeja/configuraciones)
        logging.info(f"Verificando integridad en el directorio: {target_dir}")
        if os.path.exists(target_dir):
            for root, dirs, files in os.walk(target_dir):
                for file in files[:10]:  # Limitar para rendimiento seguro
                    filepath = os.path.join(root, file)
                    if os.path.isfile(filepath):
                        try:
                            hasher = hashlib.sha256()
                            with open(filepath, 'rb') as f:
                                buf = f.read(65536)
                                while len(buf) > 0:
                                    hasher.update(buf)
                                    buf = f.read(65536)
                            audit_results["integrity_check"].append({
                                "file": filepath,
                                "sha256": hasher.hexdigest()
                            })
                        except PermissionError:
                            continue
        # 3. Auditoría de conexiones de red activas
        logging.info("Auditando conexiones de red establecidas...")
        connections = psutil.net_connections(kind='inet')
        for conn in connections:
            if conn.status == 'ESTABLISHED':
                audit_results["network_connections"].append({
                    "local_address": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "N/A",
                    "remote_address": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A",
                    "status": conn.status
                })
        logging.info("Auditoría completada exitosamente.")
    except Exception as e:
        logging.error(f"Error durante la ejecución de la habilidad: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }
    # Generación de reporte final
    if report_format == "json":
        return {
            "status": "success",
            "skill": "aprendidas_interacciones_previas",
            "report": audit_results
        }
    else:
        return {
            "status": "success",
            "message": "Auditoría finalizada, formato no JSON no soportado en esta vista.",
            "data": audit_results
        }