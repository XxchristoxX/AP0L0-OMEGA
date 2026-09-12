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
logger = logging.getLogger("pesados_antes_sufra")
def run(params):
    """Módulo de diagnóstico predictivo para la protección y auditoría de recursos del sistema.
    Analiza CPU, RAM y temperatura (si está disponible) en tiempo real,
    identifica procesos pesados y genera un reporte JSON con recomendaciones
    preventivas para evitar la saturación del sistema.
    """
    logger.info(
        "Iniciando diagnóstico predictivo de recursos..."
    )
    # Umbrales configurables vía parámetros con valores por defecto seguros
    cpu_threshold = params.get(
        "cpu_threshold", 85.0
    )  # Porcentaje
    ram_threshold = params.get(
        "ram_threshold", 85.0
    )  # Porcentaje
    temp_threshold = params.get(
        "temp_threshold", 80.0
    )  # Grados Celsius
    top_n = params.get(
        "top_n", 5
    )  # Número de procesos pesados a listar
    try:
        # 1. Monitoreo de CPU
        cpu_usage = psutil.cpu_percent(interval=1)
        logger.debug(f"Uso de CPU actual: {cpu_usage}%")
        # 2. Monitoreo de Memoria RAM
        ram_info = psutil.virtual_memory()
        ram_usage = ram_info.percent
        logger.debug(f"Uso de RAM actual: {ram_usage}%")
        # 3. Monitoreo de Temperatura (siempre que el hardware/SO lo permita)
        temperatures = {}
        try:
            if hasattr(psutil, "sensors_temps"):
                temps = psutil.sensors_temps()
                if temps:
                    for name, entries in temps.items():
                        for entry in entries:
                            temperatures[
                                f"{name}_{entry.label or 'core'}"
                            ] = entry.current
            logger.debug(f"Temperaturas leídas: {temperatures}")
        except Exception as temp_err:
            logger.warning(
                f"No se pudieron leer los sensores de temperatura: {temp_err}"
            )
        # 4. Identificación de procesos pesados (Top CPU y RAM)
        processes = []
        for proc in psutil.process_iter(
            ["pid", "name", "cpu_percent", "memory_percent"]
        ):
            try:
                pinfo = proc.info
                # Normalizar valores None
                pinfo["cpu_percent"] = pinfo["cpu_percent"] or 0.0
                pinfo["memory_percent"] = pinfo["memory_percent"] or 0.0
                processes.append(pinfo)
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue
        # Ordenar procesos por consumo de CPU y RAM combinados o separados
        top_cpu_procs = sorted(
            processes,
            key=lambda x: x["cpu_percent"],
            reverse=True,
        )[:top_n]
        top_ram_procs = sorted(
            processes,
            key=lambda x: x["memory_percent"],
            reverse=True,
        )[:top_n]
        # 5. Diagnóstico Predictivo y Recomendaciones
        warnings = []
        recommendations = []
        if cpu_usage >= cpu_threshold:
            warnings.warn = True
            warnings.append(
                f"Alerta: Uso crítico de CPU ({cpu_usage}% >= {cpu_threshold}%)"
            )
            recommendations.append(
                "Considere cerrar aplicaciones intensivas en CPU o suspender procesos en segundo plano no esenciales."
            )
        if ram_usage >= ram_threshold:
            warnings.append(
                f"Alerta: Uso crítico de RAM ({ram_usage}% >= {ram_threshold}%)"
            )
            recommendations.append(
                "Considere liberar memoria cerrando pestañas del navegador o aplicaciones con alta ocupación de RAM."
            )
        # Evaluar temperatura máxima
        max_temp = 0
        if temperatures:
            max_temp = max(temperatures.values())
            if max_temp >= temp_threshold:
                warnings.append(
                    f"Alerta: Temperatura elevada detectada ({max_temp}°C >= {temp_threshold}°C)"
                )
                recommendations.append(
                    "Verifique la ventilación del sistema para evitar estrangulamiento térmico (thermal throttling)."
                )
        status = "warning" if warnings else "optimal"
        if not warnings:
            recommendations.append(
                "El sistema opera bajo parámetros normales. No se requiere acción inmediata."
            )
        # Estructura del reporte final
        report = {
            "status": "success",
            "diagnostic_status": status,
            "scan_time": datetime.now().isoformat(),
            "metrics": {
                "cpu_usage_percent": cpu_usage,
                "ram_usage_percent": ram_usage,
                "ram_total_gb": round(
                    ram_info.total / (1024**3), 2
                ),
                "ram_available_gb": round(
                    ram_info.available / (1024**3), 2
                ),
                "temperatures_celsius": temperatures,
            },
            "heavy_processes": {
                "top_cpu": [
                    {
                        "pid": p["pid"],
                        "name": p["name"],
                        "cpu_percent": p["cpu_percent"],
                    }
                    for p in top_cpu_procs
                ],
                "top_ram": [
                    {
                        "pid": p["pid"],
                        "name": p["name"],
                        "memory_percent": round(
                            p["memory_percent"], 2
                        ),
                    }
                    for p in top_ram_procs
                ],
            },
            "warnings": warnings,
            "recommendations": recommendations,
        }
        logger.info(
            "Diagnóstico predictivo completado exitosamente."
        )
        return report
    except Exception as e:
        logger.error(
            f"Error crítico durante la ejecución del diagnóstico: {str(e)}"
        )
        return {
            "status": "error",
            "scan_time": datetime.now().isoformat(),
            "error_message": str(e),
        }