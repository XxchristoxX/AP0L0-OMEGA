from datetime import datetime
import json
import logging
import psutil
# Configuración básica de logging para depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
def run(params):
    """Monitorea el uso de recursos en tiempo real para identificar procesos
    que consumen altos recursos (CPU/Memoria) y sugiere optimizaciones
    para garantizar una experiencia de usuario fluida y segura.
    """
    cpu_threshold = params.get("cpu_threshold", 80.0)
    memory_threshold = params.get("memory_threshold", 80.0)
    exclude_processes = params.get(
        "exclude", ["System", "systemd", "kernel", "python", "explorer.exe"]
    )
    flagged_processes = []
    system_status = {}
    try:
        logging.info(
            "Iniciando análisis predictivo de recursos del sistema..."
        )
        # Obtener uso general del sistema
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_info = psutil.virtual_memory()
        system_status = {
            "cpu_total_percent": cpu_usage,
            "memory_total_percent": memory_info.percent,
            "memory_available_mb": round(
                memory_info.available / (1024 * 1024), 2
            ),
        }
        logging.info(f"Estado general - CPU: {cpu_usage}%, Memoria: {memory_info.percent}%")
        # Iterar sobre los procesos activos
        for proc in psutil.process_iter(
            ["pid", "name", "cpu_percent", "memory_percent"]
        ):
            try:
                pinfo = proc.info
                pname = pinfo.get("name")
                pcpu = pinfo.get("cpu_percent") or 0.0
                pmem = pinfo.get("memory_percent") or 0.0
                # Filtrar procesos excluidos o del sistema crítico
                if pname in exclude_processes:
                    continue
                # Identificar procesos que exceden los umbrales de rendimiento
                if pcpu > cpu_threshold or pmem > memory_threshold:
                    recommendation = "Suspender temporalmente o priorizar"
                    if pcpu > 90.0:
                        recommendation = (
                            "Alto impacto en CPU. Se sugiere cierre preventivo."
                        )
                    flagged_processes.append(
                        {
                            "pid": pinfo.get("pid"),
                            "name": pname,
                            "cpu_percent": pcpu,
                            "memory_percent": round(pmem, 2),
                            "recommendation": recommendation,
                        }
                    )
                    logging.warning(
                        f"Proceso pesado detectado: {pname} (PID: {pinfo.get('pid')}) - CPU: {pcpu}%, MEM: {round(pmem, 2)}%"
                    )
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue
        report = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "system_metrics": system_status,
            "thresholds": {
                "cpu_limit": cpu_threshold,
                "memory_limit": memory_threshold,
            },
            "heavy_processes_detected": len(flagged_processes),
            "recommendations": flagged_processes,
        }
        logging.info(
            "Análisis completado exitosamente. Generando reporte JSON."
        )
        return report
    except Exception as e:
        error_msg = f"Error crítico durante el monitoreo de recursos: {str(e)}"
        logging.error(error_msg)
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "message": error_msg,
        }