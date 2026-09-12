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
logger = logging.getLogger("procesos_segundo_plano")
def run(params):
    """Módulo de monitoreo predictivo para auditoría de recursos del sistema.
    Analiza CPU, RAM y temperatura (si está disponible), identificando
    procesos anómalos o de alto consumo para prevenir fallos en el sistema.
    """
    logger.info("Iniciando auditoría de procesos en segundo plano y recursos.")
    # Parámetros de umbral configurables con valores por defecto seguros
    cpu_threshold = params.get("cpu_threshold", 85.0)
    ram_threshold = params.get("ram_threshold", 85.0)
    temp_threshold = params.get("temp_threshold", 80.0)  # Grados Celsius
    try:
        # Monitoreo de recursos globales
        cpu_usage = psutil.cpu_percent(interval=1)
        ram_info = psutil.virtual_memory()
        ram_usage = ram_info.percent
        logger.info(
            f"Métricas actuales - CPU: {cpu_usage}%, RAM: {ram_usage}%"
        )
        # Obtención de temperatura (si el hardware/OS lo soporta)
        temperatures = {}
        overheating = False
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        for entry in entries:
                            temp_value = entry.current
                            temperatures[
                                f"{name}_{entry.label or 'core'}"
                            ] = temp_value
                            if temp_value >= temp_threshold:
                                overheating = True
        except Exception as temp_err:
            logger.warning(
                f"No se pudieron leer las temperaturas del sistema: {temp_err}"
            )
        # Identificación de procesos con consumo elevado
        heavy_processes = []
        for proc in psutil.process_iter(
            ["pid", "name", "cpu_percent", "memory_percent"]
        ):
            try:
                pinfo = proc.info
                # Filtrar procesos propios vacíos o del sistema crítico si es necesario
                p_cpu = pinfo.get("cpu_percent") or 0.0
                p_mem = pinfo.get("memory_percent") or 0.0
                if p_cpu > 20.0 or p_mem > 15.0:
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
        # Ordenar procesos por mayor consumo de CPU
        heavy_processes = sorted(
            heavy_processes, key=lambda k: k["cpu_percent"], reverse=True
        )
        # Generación de sugerencias predictivas y de defensa
        suggestions = []
        status = "normal"
        if cpu_usage >= cpu_threshold:
            status = "warning"
            suggestions.append(
                f"Uso crítico de CPU detectado ({cpu_usage}%). Se recomienda pausar los procesos pesados listados."
            )
        if ram_usage >= ram_threshold:
            status = "warning"
            suggestions.append(
                f"Uso crítico de Memoria RAM detectado ({ram_usage}%). Considere cerrar aplicaciones en segundo plano."
            )
        if overheating:
            status = "critical"
            suggestions.append(
                f"¡Alerta de sobrecalentamiento! Una o más sondas superan los {temp_threshold}°C. Verifique la ventilación del sistema."
            )
        if not suggestions:
            suggestions.append(
                "El sistema opera dentro de los parámetros normales de seguridad y rendimiento."
            )
        report = {
            "status": "success",
            "audit_status": status,
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "cpu_usage_percent": cpu_usage,
                "ram_usage_percent": ram_usage,
                "ram_total_gb": round(
                    ram_info.total / (1024.3 * 1024 * 1024), 2
                ),
                "temperatures_celsius": temperatures,
            },
            "heavy_processes_detected": heavy_processes,
            "defensive_suggestions": suggestions,
        }
        logger.info(
            "Auditoría de recursos completada exitosamente sin alteraciones en el sistema."
        )
        return report
    except Exception as e:
        logger.error(
            f"Error crítico durante la ejecución del módulo de procesos: {str(e)}"
        )
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "message": str(e),
        }