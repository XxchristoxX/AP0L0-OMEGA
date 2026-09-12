from datetime import datetime
import json
import logging
import psutil
# Configuración de logging para depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
def run(params):
    """Monitorea el uso de CPU, RAM y disco en tiempo real.
    Sugiere cerrar procesos pesados para prevenir ralentizaciones o cuelgues.
    """
    # Umbrales por defecto para la alerta preventiva (porcentajes)
    cpu_threshold = params.get("cpu_threshold", 85.0)
    ram_threshold = params.get("ram_threshold", 85.0)
    disk_threshold = params.get("disk_threshold", 90.0)
    logging.info("Iniciando monitoreo preventivo de recursos del sistema.")
    try:
        # Obtener métricas actuales del sistema
        cpu_usage = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        ram_usage = ram.percent
        disk_usage = disk.percent
        logging.info(
            f"Métricas actuales -> CPU: {cpu_usage}%, RAM: {ram_usage}%, Disco: {disk_usage}%"
        )
        # Identificar procesos que consumen más recursos
        heavy_processes = []
        for proc in psutil.process_iter(
            ["pid", "name", "cpu_percent", "memory_percent"]
        ):
            try:
                pinfo = proc.info
                cpu_p = pinfo.get("cpu_percent") or 0.0
                mem_p = pinfo.get("memory_percent") or 0.0
                # Filtrar procesos con uso relevante para evitar lista gigante
                if cpu_p > 5.0 or mem_p > 5.0:
                    heavy_processes.append(
                        {
                            "pid": pinfo["pid"],
                            "name": pinfo["name"],
                            "cpu_percent": cpu_p,
                            "memory_percent": round(mem_p, 2),
                        }
                    )
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue
        # Ordenar procesos por mayor consumo de CPU y RAM
        heavy_processes = sorted(
            heavy_processes,
            key=lambda x: (x["cpu_percent"], x["memory_percent"]),
            reverse=True,
        )
        # Evaluar estado de salud del sistema y generar advertencias
        warnings = []
        status = "healthy"
        if cpu_usage >= cpu_threshold:
            status = "warning"
            warn_msg = f"Uso crítico de CPU detectado: {cpu_usage}% (Umbral: {cpu_threshold}%)"
            warnings.append(warn_msg)
            logging.warning(warn_msg)
        if ram_usage >= ram_threshold:
            status = "warning"
            warn_msg = f"Uso crítico de RAM detectado: {ram_usage}% (Umbral: {ram_threshold}%)"
            warnings.append(warn_msg)
            logging.warning(warn_msg)
        if disk_usage >= disk_threshold:
            status = "warning"
            warn_msg = f"Espacio en disco bajo crítico: {disk_usage}% (Umbral: {disk_threshold}%)"
            warnings.append(warn_msg)
            logging.warning(warn_msg)
        recommendations = []
        if status == "warning":
            recommendations.append(
                "Considere cerrar las siguientes aplicaciones pesadas para evitar un cuelgue del sistema:"
            )
            # Top 5 procesos pesados
            for p in heavy_processes[:5]:
                recommendations.append(
                    f"PID: {p['pid']} - Nombre: {p['name']} (CPU: {p['cpu_percent']}%, RAM: {p['memory_percent']}%)"
                )
        else:
            recommendations.append(
                "El sistema opera dentro de los parámetros normales de rendimiento."
            )
        report = {
            "status": "success",
            "system_health": status,
            "scan_time": datetime.now().isoformat(),
            "metrics": {
                "cpu_usage_percent": cpu_usage,
                "ram_usage_percent": ram_usage,
                "disk_usage_percent": disk_usage,
            },
            "thresholds": {
                "cpu": cpu_threshold,
                "ram": ram_threshold,
                "disk": disk_threshold,
            },
            "warnings": warnings,
            "top_heavy_processes": heavy_processes[:10],
            "recommendations": recommendations,
        }
        logging.info("Monitoreo preventivo completado exitosamente. Reporte generado.")
        return report
    except Exception as e:
        logging.error(f"Error durante el monitoreo de recursos: {str(e)}")
        return {
            "status": "error",
            "scan_time": datetime.now().isoformat(),
            "message": str(e),
        }