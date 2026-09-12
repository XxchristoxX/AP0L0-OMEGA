import json
import logging
import os
import subprocess
from datetime import datetime
import psutil
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
def run(params):
    """
    Habilidad de auditoría 'operativo_forma_totalmente' para verificar
    procesos en ejecución, uso de recursos y servicios activos en el sistema local
    con el fin de detectar anomalías o procesos no autorizados (Defensa y Monitoreo).
    """
    logging.info("Iniciando auditoría de procesos y recursos del sistema operativo.")
    try:
        active_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                # Filtrar procesos con consumo relevante o simplemente recolectar datos básicos
                active_processes.append({
                    "pid": pinfo.get("pid"),
                    "name": pinfo.get("name"),
                    "username": pinfo.get("username"),
                    "cpu_percent": pinfo.get("cpu_percent", 0.0),
                    "memory_percent": pinfo.get("memory_percent", 0.0)
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        # Obtener uso general de recursos para el reporte de auditoría
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_info = psutil.virtual_memory()._asdict()
        disk_info = psutil.disk_usage('/')._asdict()
        report = {
            "status": "success",
            "audit_time": datetime.now().isoformat(),
            "system_metrics": {
                "cpu_usage_percent": cpu_usage,
                "memory": memory_info,
                "disk": disk_info
            },
            "active_processes_count": len(active_processes),
            "processes_sample": active_processes[:20]  # Muestra de los primeros 20 procesos
        }
        logging.info("Auditoría completada exitosamente.")
        return report
    except Exception as e:
        logging.error(f"Error durante la ejecución de la habilidad: {str(e)}")
        return {
            "status": "error",
            "audit_time": datetime.now().isoformat(),
            "error_message": str(e)
        }