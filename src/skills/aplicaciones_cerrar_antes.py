from datetime import datetime
import json
import logging
import os
import psutil
# Configuración de logging para depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
def run(params):
    """Habilidad de autodiagnóstico predictivo para auditoría de recursos del sistema.
    Analiza CPU, RAM y temperatura (si está disponible) para detectar
    consumos anómalos, sugiriendo procesos candidatos a ser cerrados
    para mitigar posibles ataques de denegación de servicio local (DoS)
    o fallos de rendimiento.
    """
    logging.info(
        "Iniciando habilidad de autodiagnóstico 'aplicaciones_cerrar_antes'."
    )
    # Parámetros configurables con valores por defecto seguros
    cpu_threshold = params.get("cpu_threshold", 80.0)  # Porcentaje
    ram_threshold = params.get("ram_threshold", 80.0)  # Porcentaje
    temp_threshold = params.get(
        "temp_threshold", 75.0
    )  # Grados Celsius aproximados
    report = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "system_metrics": {},
        "anomalies_detected": False,
        "suggested_actions": [],
        "processes_analyzed": 0,
    }
    try:
        # 1. Monitoreo de recursos globales
        cpu_usage = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        ram_usage = ram.percent
        report["system_metrics"] = {
            "cpu_percent": cpu_usage,
            "ram_percent": ram_usage,
            "ram_total_gb": round(ram.total / (1024**3), 2),
            "ram_available_gb": round(ram.available / (1024**3), 2),
        }
        # Intento de obtener temperatura del sistema (dependiente del SO/hardware)
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                current_temps = {}
                for name, entries in temps.items():
                    for entry in entries:
                        current_temps[
                            f"{name}_{entry.label or 'core'}"
                        ] = entry.current
                report["system_metrics"]["temperatures"] = current_temps
                # Verificar si alguna temperatura supera el umbral
                for k, v in current_temps.items():
                    if v > temp_threshold:
                        report["anomalies_detected"] = True
                        report["suggested_actions"].append(
                            f"Alerta térmica: {k} está a {v}°C (Umbral: {temp_threshold}°C)."
                        )
        except Exception as temp_err:
            logging.warning(
                f"No se pudieron leer los sensores de temperatura: {str(temp_err)}"
            )
            report["system_metrics"]["temperatures"] = (
                "No disponible / No soportado"
            )
        # Verificar umbrales globales de CPU y RAM
        if cpu_usage > cpu_threshold:
            report["anomalies_detected"] = True
            report["suggested_actions"].append(
                f"Uso de CPU elevado: {cpu_usage}% (Umbral: {cpu_threshold}%)."
            )
        if ram_usage > ram_threshold:
            report["anomalies_detected"] = True
            report["suggested_actions"].append(
                f"Uso de RAM elevado: {ram_usage}% (Umbral: {ram_threshold}%)."
            )
        # 2. Análisis detallado de procesos para auditoría predictiva
        heavy_processes = []
        for proc in psutil.process_iter(
            ["pid", "name", "cpu_percent", "memory_percent"]
        ):
            try:
                pinfo = proc.info
                report["processes_analyzed"] += 1
                # Filtrar procesos que consumen recursos significativos (>5% CPU o RAM)
                p_cpu = pinfo["cpu_percent"] or 0.0
                p_mem = pinfo["memory_percent"] or 0.0
                if p_cpu > 5.0 or p_mem > 5.0:
                    heavy_processes.append(
                        {
                            "pid": pinfo["pid"],
                            "name": pinfo["name"],
                            "cpu_percent": p_cpu,
                            "memory_percent": round(p_mem, 2),
                        }
                    )
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue
        # Ordenar procesos por mayor consumo de CPU y RAM combinados
        heavy_processes = sorted(
            heavy_processes,
            key=lambda x: (x["cpu_percent"] + x["memory_percent"]),
            reverse=True,
        )
        report["top_consuming_processes"] = heavy_processes[:5]
        # Sugerir cierre preventivo si hay procesos anómalos
        if heavy_processes and report["anomalies_detected"]:
            top_suspect = heavy_processes[0]
            report["suggested_actions"].append(
                f"Sugerencia defensiva: Considere cerrar la aplicación '{top_suspect['name']}' "
                f"(PID: {top_suspect['pid']}) que consume {top_suspect['cpu_percent']}% de CPU "
                f"y {top_suspect['memory_percent']}% de RAM para estabilizar el sistema."
            )
        else:
            report["suggested_actions"].append(
                "El sistema opera bajo parámetros estables. No se requiere acción inmediata."
            )
        logging.info(
            "Auditoría predictiva de recursos completada exitosamente."
        )
    except Exception as e:
        logging.error(f"Error crítico durante la ejecución de la skill: {e}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat(),
        }
    # Salida estandarizada en formato JSON (compatible con sistemas de SIEM o gestión)
    return report