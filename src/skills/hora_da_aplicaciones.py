from datetime import datetime
import json
import logging
import os
import psutil
# Configuración de logging para depuración y auditoría defensiva
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - AP0L0-DEFENSE - %(levelname)s - %(message)s",
)
def run(params):
    """Módulo de Optimización Contextual de Tareas y Auditoría de Procesos.
    Analiza las aplicaciones activas en el sistema para evaluar la
    contextualización
    de tareas, detectar posibles riesgos operativos y generar un reporte JSON.
    """
    logging.info(
        "Iniciando auditoría de contexto y aplicaciones activas (hora_da_aplicaciones)..."
    )
    try:
        # Obtener lista de procesos activos y aplicaciones en ejecución
        active_applications = []
        for proc in psutil.process_iter(
            ["pid", "name", "username", "create_time", "cpu_percent", "memory_percent"]
        ):
            try:
                pinfo = proc.info
                # Filtrar información relevante y segura
                active_applications.append(
                    {
                        "pid": pinfo.get("pid"),
                        "name": pinfo.get("name"),
                        "username": pinfo.get("username"),
                        "cpu_usage_percent": pinfo.get("cpu_percent", 0.0),
                        "memory_usage_percent": pinfo.get(
                            "memory_percent", 0.0
                        ),
                        "start_time": (
                            datetime.fromtimestamp(
                                pinfo.get("create_time")
                            ).isoformat()
                            if pinfo.get("create_time")
                            else None
                        ),
                    }
                )
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue
        # Análisis contextual básico para sugerencias de productividad/seguridad
        # Identificar si hay alto consumo de recursos o aplicaciones de red comunes
        high_resource_apps = [
            app
            for app in active_applications
            if app["cpu_usage_percent"]
            and app["cpu_usage_percent"] > 10.0
        ]
        report_data = {
            "status": "success",
            "module": "hora_da_aplicaciones",
            "timestamp": datetime.now().isoformat(),
            "total_processes_analyzed": len(active_applications),
            "high_resource_processes_count": len(high_resource_apps),
            "applications": active_applications,
            "contextual_recommendation": (
                "Optimización contextual completada de forma segura. "
                "Se han indexado las tareas activas para la reprogramación en segundo plano."
            ),
        }
        # Generación opcional de archivo de reporte JSON si se solicita en params
        output_path = params.get(
            "output_path", "/tmp/ap0l0_app_context_report.json"
        )
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=4, ensure_ascii=False)
            logging.info(f"Reporte generado exitosamente en: {output_path}")
        except Exception as file_err:
            logging.warning(
                f"No se pudo escribir el archivo de reporte en disco: {file_err}"
            )
        return report_data
    except Exception as e:
        logging.error(f"Error crítico en el módulo hora_da_aplicaciones: {e}")
        return {
            "status": "error",
            "module": "hora_da_aplicaciones",
            "timestamp": datetime.now().isoformat(),
            "error_message": str(e),
        }