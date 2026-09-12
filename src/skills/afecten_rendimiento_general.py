from datetime import datetime
import json
import logging
import psutil
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
def run(params):
    """Módulo de Diagnóstico Predictivo de Recursos para auditoría y
    defensa de sistemas. Analiza el consumo de CPU y RAM de los procesos
    para detectar cuellos de botella y optimizar el rendimiento.
    """
    cpu_threshold = params.get("cpu_threshold", 80.0)
    ram_threshold = params.get("ram_threshold", 85.0)
    alerts = []
    processes_data = []
    logging.info(
        "Iniciando diagnóstico predictivo de recursos..."
    )
    try:
        system_cpu = psutil.cpu_percent(interval=1)
        system_ram = psutil.virtual_memory().percent
        logging.info(
            f"Uso global - CPU: {system_cpu}%, RAM: {system_ram}%"
        )
        if system_cpu > cpu_threshold:
            alerts.append(
                f"Alerta: Uso crítico de CPU en el sistema ({system_cpu}%)"
            )
        if system_ram > ram_threshold:
            alerts.append(
                f"Alerta: Uso crítico de RAM en el sistema ({system_ram}%)"
            )
        for proc in psutil.process_iter(
            ["pid", "name", "cpu_percent", "memory_percent"]
        ):
            try:
                pinfo = proc.info
                p_cpu = pinfo["cpu_percent"] or 0.0
                p_ram = pinfo["memory_percent"] or 0.0
                process_entry = {
                    "pid": pinfo["pid"],
                    "name": pinfo["name"],
                    "cpu_percent": p_cpu,
                    "memory_percent": round(p_ram, 2),
                }
                processes_data.append(process_entry)
                if p_cpu > cpu_threshold:
                    alerts.append(
                        f"Proceso {pinfo['name']} (PID: {pinfo['pid']}) "
                        f"consumiendo alto porcentaje de CPU: {p_cpu}%"
                    )
                if p_ram > ram_threshold:
                    alerts.append(
                        f"Proceso {pinfo['name']} (PID: {pinfo['pid']}) "
                        f"consumiendo alto porcentaje de RAM: {round(p_ram, 2)}%"
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
            "system_metrics": {
                "total_cpu_usage": system_cpu,
                "total_ram_usage": system_ram,
            },
            "thresholds": {
                "cpu": cpu_threshold,
                "ram": ram_threshold,
            },
            "alerts": alerts,
            "processes_monitored": sorted(
                processes_data,
                key=lambda x: x["cpu_percent"],
                reverse=True,
            )[
                :10
            ],  # Top 10 procesos por CPU
        }
        logging.info(
            "Diagnóstico predictivo completado con éxito."
        )
        return report
    except Exception as e:
        error_msg = (
            f"Error crítico durante el diagnóstico de recursos: {str(e)}"
        )
        logging.error(error_msg)
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "message": error_msg,
        }