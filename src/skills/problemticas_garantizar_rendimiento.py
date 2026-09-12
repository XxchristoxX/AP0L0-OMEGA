from datetime import datetime
import json
import logging
import os
import psutil
# Configuración de logs para depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("problemticas_garantizar_rendimiento")
def run(params):
    """Módulo de diagnóstico predictivo y gestión de rendimiento para auditoría
    y defensa de sistemas. Analiza CPU, RAM y temperatura (si está disponible),
    detectando anomalías o procesos colgados de forma segura.
    """
    logger.info("Iniciando diagnóstico predictivo de rendimiento.")
    # Umbrales configurables vía parámetros con valores por defecto seguros
    cpu_threshold = params.get("cpu_threshold", 85.0)
    ram_threshold = params.get("ram_threshold", 85.0)
    auto_mitigate = params.get("auto_mitigate", False)
    metrics = {}
    anomalies = []
    recommendations = []
    terminated_processes = []
    try:
        # 1. Análisis de CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        metrics["cpu_usage_percent"] = cpu_percent
        logger.info(f"Uso de CPU actual: {cpu_percent}%")
        if cpu_percent > cpu_threshold:
            anomalies.append(
                f"Uso crítico de CPU detectado: {cpu_percent}% (Umbral: {cpu_threshold}%)"
            )
            recommendations.append(
                "Identificar procesos que consumen alta CPU y considerar su terminación."
            )
        # 2. Análisis de Memoria RAM
        ram = psutil.virtual_memory()
        metrics["ram"] = {
            "total_gb": round(ram.total / (1024**3), 2),
            "available_gb": round(ram.available / (1024**3), 2),
            "used_percent": ram.percent,
        }
        logger.info(f"Uso de RAM actual: {ram.percent}%")
        if ram.percent > ram_threshold:
            anomalies.append(
                f"Uso crítico de RAM detectado: {ram.percent}% (Umbral: {ram_threshold}%)"
            )
            recommendations.append(
                "Liberar memoria cerrando aplicaciones secundarias o incrementando el espacio de intercambio (Swap)."
            )
        # 3. Análisis de Temperatura (siempre que el hardware/SO lo soporte)
        temperatures = {}
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        temperatures[name] = [
                            {
                                "label": entry.label or "N/A",
                                "current": entry.current,
                                "high": entry.high,
                            }
                            for entry in entries
                        ]
                        for entry in entries:
                            if entry.high and entry.current >= entry.high:
                                anomalies.append(
                                    f"Temperatura alta en {name} ({entry.label}): {entry.current}°C"
                                )
                else:
                    temperatures["status"] = (
                        "Sensores de temperatura no disponibles en este entorno."
                    )
        except Exception as temp_err:
            logger.warning(
                f"No se pudieron leer los sensores de temperatura: {temp_err}"
            )
            temperatures["error"] = str(temp_err)
        metrics["temperatures"] = temperatures
        # 4. Detección de procesos colgados o anómalos (ej. uso excesivo de recursos por proceso individual)
        suspicious_processes = []
        for proc in psutil.process_iter(
            ["pid", "name", "cpu_percent", "memory_percent"]
        ):
            try:
                pinfo = proc.info
                # Consideramos anomalía si un proceso individual supera el 50% de CPU sostenido o RAM
                if (
                    pinfo["cpu_percent"] is not None
                    and pinfo["cpu_percent"] > 50.0
                ) or (
                    pinfo["memory_percent"] is not None
                    and pinfo["memory_percent"] > 50.0
                ):
                    suspicious_processes.append(pinfo)
                    logger.warning(
                        f"Proceso anómalo detectado: PID {pinfo['pid']} ({pinfo['name']}) - CPU: {pinfo['cpu_percent']}%, RAM: {pinfo['memory_percent']}%"
                    )
                    # Mitigación segura y opcional (Solo sugerencia a menos que auto_mitigate sea True)
                    if auto_mitigate:
                        # Excluir procesos críticos del sistema para evitar caídas
                        critical_processes = [
                            "systemd",
                            "kernel",
                            "explorer.exe",
                            "launchd",
                            "python",
                            "sshd",
                        ]
                        if pinfo["name"] not in critical_processes:
                            p = psutil.Process(pinfo["pid"])
                            p.terminate()  # Cierre seguro (SIGTERM)
                            terminated_processes.append(
                                {
                                    "pid": pinfo["pid"],
                                    "name": pinfo["name"],
                                    "action": "terminated_gracefully",
                                }
                            )
                            logger.info(
                                f"Proceso {pinfo['name']} (PID: {pinfo['pid']}) terminado automáticamente por alto consumo."
                            )
                        else:
                            logger.warning(
                                f"Se omitió la terminación automática del proceso crítico del sistema: {pinfo['name']}"
                            )
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                pass
        metrics["suspicious_processes_detected"] = len(suspicious_processes)
        # Construcción del reporte final en formato JSON estructurado
        report = {
            "status": "success",
            "audit_time": datetime.now().isoformat(),
            "metrics": metrics,
            "anomalies_detected": anomalies,
            "suspicious_processes": suspicious_processes,
            "recommendations": recommendations,
            "mitigation_actions": terminated_processes,
        }
        logger.info(
            "Diagnóstico predictivo completado exitosamente sin errores fatales."
        )
        return report
    except Exception as e:
        logger.error(
            f"Error crítico durante la ejecución de la habilidad: {str(e)}"
        )
        return {
            "status": "error",
            "audit_time": datetime.now().isoformat(),
            "message": str(e),
        }