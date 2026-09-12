from datetime import datetime
import json
import logging
import os
import psutil
# Configuración de logging para depuración de seguridad y auditoría de procesos
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
def run(params):
    """Habilidad de seguridad: 'diaria_tiempo_reduciendo'
    Propósito: Auditar la carga de trabajo y el estrés del sistema analizando
    el uso de recursos locales (CPU/Memoria) en correlación con tareas
    pendientes para prevenir la fatiga mental y asegurar la estabilidad
    operativa del usuario (Defensa y Optimización de Carga).
    """
    logging.info(
        "Iniciando auditoría de recursos y priorización contextual..."
    )
    tasks = params.get("tasks", [])
    user_peak_hours = params.get(
        "peak_hours", [9, 10, 11, 14, 15]
    )  # Horas por defecto de alta energía
    current_hour = datetime.now().hour
    audit_results = []
    prioritized_tasks = []
    try:
        # Auditoría de seguridad y rendimiento del sistema (Uso de psutil)
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_info = psutil.virtual_memory()
        system_status = {
            "cpu_usage_percent": cpu_usage,
            "memory_usage_percent": memory_info.percent,
            "system_load_safe": cpu_usage < 85 and memory_info.percent < 85,
        }
        logging.info(
            f"Estado del sistema - CPU: {cpu_usage}%, Memoria: {memory_info.percent}%"
        )
        # Análisis y priorización contextual de tareas
        is_peak_time = current_hour in user_peak_hours
        for task in tasks:
            title = task.get("title", "Tarea sin nombre")
            complexity = task.get(
                "complexity", "media"
            )  # alta, media, baja
            impact = task.get("impact", "medio")  # alto, medio, bajo
            action = "mantener"
            # Lógica defensiva contra la sobrecarga cognitiva (Burnout)
            if complexity == "alta" and not is_peak_time:
                action = (
                    "posponer_para_horas_pico"  # Mover a hora de mayor energía
                )
            elif impact == "bajo" and complexity == "alta":
                action = (
                    "delegar_o_descartar"  # Bajo impacto, alto esfuerzo -> Riesgo
                )
            elif is_peak_time and complexity == "alta":
                action = "ejecutar_ahora"  # Ventana óptima
            prioritized_tasks.append(
                {
                    "title": title,
                    "complexity": complexity,
                    "impact": impact,
                    "recommended_action": action,
                }
            )
        report = {
            "status": "success",
            "audit_timestamp": datetime.now().isoformat(),
            "system_metrics": system_status,
            "context": {
                "current_hour": current_hour,
                "is_user_peak_productivity_time": is_peak_time,
            },
            "prioritized_tasks": prioritized_tasks,
        }
        logging.info(
            "Auditoría y priorización completada exitosamente sin alteraciones destructivas."
        )
        # Retorna el reporte estructurado en JSON para integración defensiva
        return report
    except Exception as e:
        logging.error(
            f"Error crítico durante la ejecución de la habilidad: {str(e)}"
        )
        return {
            "status": "error",
            "audit_timestamp": datetime.now().isoformat(),
            "error_message": str(e),
        }