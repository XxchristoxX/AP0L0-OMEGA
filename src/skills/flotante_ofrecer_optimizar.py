from datetime import datetime
import json
import logging
import os
import psutil
# Configuración de logging para depuración y auditoría
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
)
logger = logging.getLogger("flotante_ofrecer_optimizar")
def run(params):
    """Habilidad de autodiagnóstico predictivo para auditar recursos del sistema (CPU, RAM, Temperatura).
    Detecta anomalías de consumo en segundo plano, simula una alerta flotante
    y ofrece mitigación segura (optimización de procesos no críticos).
    """
    logger.info("Iniciando autodiagnóstico predictivo de recursos del sistema.")
    # Umbrales configurables mediante parámetros o valores por defecto seguros
    cpu_threshold = params.get("cpu_threshold", 85.0)  # Porcentaje
    ram_threshold = params.get("ram_threshold", 85.0)  # Porcentaje
    temp_threshold = params.get("temp_threshold", 80.0)  # Celsius
    auto_optimize = params.get("auto_optimize", False)
    anomalies = []
    process_audit = []
    try:
        # 1. Auditoría de CPU
        cpu_usage = psutil.cpu_percent(interval=1)
        logger.info(f"Uso actual de CPU: {cpu_usage}%")
        if cpu_usage > cpu_threshold:
            anomalies.append(
                f"Consumo crítico de CPU detectado: {cpu_usage}% (Umbral: {cpu_threshold}%)"
            )
        # 2. Auditoría de Memoria RAM
        ram_info = psutil.virtual_memory()
        ram_usage = ram_info.percent
        logger.info(f"Uso actual de RAM: {ram_usage}%")
        if ram_usage > ram_threshold:
            anomalies.append(
                f"Consumo crítico de RAM detectado: {ram_usage}% (Umbral: {ram_threshold}%)"
            )
        # 3. Auditoría de Temperatura (siempre que el hardware/SO lo soporte)
        temp_data = {}
        high_temp_detected = False
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        for entry in entries:
                            temp_name = entry.label or name
                            temp_current = entry.current
                            temp_data[temp_name] = temp_current
                            logger.info(
                                f"Sensor {temp_name}: {temp_current}°C"
                            )
                            if temp_current > temp_threshold:
                                high_temp_detected = True
                                anomalies.append(
                                    f"Temperatura elevada en {temp_name}: {temp_current}°C (Umbral: {temp_threshold}%)"
                                )
                else:
                    logger.info(
                        "No se encontraron sensores de temperatura disponibles en este sistema."
                    )
        except Exception as temp_err:
            logger.warning(
                f"No se pudo leer la temperatura del sistema: {str(temp_err)}"
            )
        # 4. Identificación de procesos anómalos en segundo plano (Top consumidores)
        logger.info("Analizando procesos en ejecución...")
        for proc in psutil.process_iter(
            ["pid", "name", "cpu_percent", "memory_percent"]
        ):
            try:
                pinfo = proc.info
                # Filtrar procesos con uso relevante para el reporte
                if (
                    pinfo["cpu_percent"] is not None
                    and pinfo["cpu_percent"] > 10.0
                ) or (
                    pinfo["memory_percent"] is not None
                    and pinfo["memory_percent"] > 10.0
                ):
                    process_audit.append(
                        {
                            "pid": pinfo["pid"],
                            "name": pinfo["name"],
                            "cpu_percent": pinfo["cpu_percent"],
                            "memory_percent": round(
                                pinfo["memory_percent"], 2
                            ),
                        }
                    )
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue
        # Ordenar procesos por consumo de CPU descendiente
        process_audit = sorted(
            process_audit, key=lambda k: k["cpu_percent"], reverse=True
        )
        # 5. Generación de Alerta Flotante y Optimización Defensiva
        alert_triggered = len(anomalies) > 0
        optimization_action = "Ninguna requerida"
        if alert_triggered:
            logger.warning(
                f"¡ALERTA FLOTANTE GENERADA! Anomalías detectadas: {anomalies}"
            )
            if auto_optimize:
                logger.info(
                    "Modo de optimización automática activado. Tomando medidas defensivas seguras..."
                )
                # Acción segura: nicear procesos no esenciales en lugar de matarlos destructivamente
                optimized_count = 0
                for item in process_audit[:3]:  # Top 3 consumidores
                    try:
                        p = psutil.Process(item["pid"])
                        # Evitar tocar procesos del sistema crítico o el propio script
                        if p.name().lower() not in [
                            "system",
                            "kernel",
                            "python",
                            "init",
                        ]:
                            # Incrementar la prioridad (nice) de forma segura para liberar recursos al sistema
                            p.nice(psutil.IDLE_PRIORITY_CLASS)
                            optimized_count += 1
                            logger.info(
                                f"Proceso optimizado (prioridad reducida): {item['name']} (PID: {item['pid']})"
                            )
                    except Exception as e:
                        logger.error(
                            f"No se pudo optimizar el proceso PID {item['pid']}: {str(e)}"
                        )
                optimization_action = f"Se ajustó la prioridad de {optimized_count} procesos en segundo plano."
            else:
                optimization_action = (
                    "Alerta enviada al usuario. Esperando confirmación para optimizar."
                )
        else:
            logger.info(
                "El sistema opera en parámetros normales. No se requieren acciones."
            )
        # 6. Estructuración del Reporte Final en JSON
        report = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "cpu_usage_percent": cpu_usage,
                "ram_usage_percent": ram_usage,
                "temperatures_celsius": temp_data,
            },
            "thresholds": {
                "cpu": cpu_threshold,
                "ram": ram_threshold,
                "temperature": temp_threshold,
            },
            "alert_triggered": alert_triggered,
            "anomalies_detected": anomalies,
            "top_resource_consumers": process_audit[:5],  # Top 5
            "defense_action": optimization_action,
        }
        return report
    except Exception as e:
        logger.error(
            f"Error crítico ejecutando la habilidad 'flotante_ofrecer_optimizar': {str(e)}",
            exc_info=True,
        )
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "message": str(e),
        }