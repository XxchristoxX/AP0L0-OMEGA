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
    """Módulo 'memoria_ram_durante': Auditoría y defensa de procesos
    y consumo de memoria RAM para la detección de anomalías o
    optimización segura en sistemas locales.
    """
    threshold_mb = params.get("threshold_mb", 500)
    audit_action = params.get("action", "audit")
    logging.info(
        f"Iniciando habilidad 'memoria_ram_durante' con acción: {audit_action}"
    )
    process_data = []
    anomalies = []
    try:
        # Obtener estadísticas globales de la memoria RAM
        virtual_memory = psutil.virtual_memory()
        ram_stats = {
            "total_gb": round(
                virtual_memory.total / (1024**3), 2
            ),
            "available_gb": round(
                virtual_memory.available / (1024**3), 2
            ),
            "used_gb": round(
                virtual_memory.used / (1024**3), 2
            ),
            "percent_used": virtual_memory.percent,
        }
        # Auditar procesos activos en busca de alto consumo de memoria RAM
        for proc in psutil.process_iter(
            ["pid", "name", "username", "memory_info"]
        ):
            try:
                pinfo = proc.info
                mem_info = pinfo.get("memory_info")
                if mem_info:
                    # Convertir RSS a MB
                    rss_mb = round(
                        mem_info.rss / (1024 * 1024), 2
                    )
                    proc_info = {
                        "pid": pinfo.get("pid"),
                        "name": pinfo.get("name"),
                        "username": pinfo.get("username"),
                        "memory_rss_mb": rss_mb,
                    }
                    process_data.append(proc_info)
                    # Detección defensiva: identificar procesos que superen el umbral de RAM
                    if rss_mb > threshold_mb:
                        anomalies.append(
                            {
                                "pid": pinfo.get("pid"),
                                "name": pinfo.get("name"),
                                "memory_rss_mb": rss_mb,
                                "warning": f"Proceso consume más de {threshold_mb}MB de RAM.",
                            }
                        )
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue
        # Ordenar procesos por mayor consumo de memoria
        process_data = sorted(
            process_data,
            key=lambda k: k["memory_rss_mb"],
            reverse=True,
        )
        report = {
            "status": "success",
            "module": "memoria_ram_durante",
            "timestamp": datetime.now().isoformat(),
            "ram_overview": ram_stats,
            "threshold_mb": threshold_mb,
            "high_memory_anomalies_detected": len(
                anomalies
            ),
            "anomalies": anomalies,
            "top_processes": process_data[
                :10
            ],  # Top 10 procesos con mayor consumo
        }
        # Guardar reporte en JSON para auditoría defensiva
        report_filename = f"audit_ram_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(
            report_filename, "w", encoding="utf-8"
        ) as f:
            json.dump(report, f, indent=4)
        logging.info(
            f"Auditoría completada exitosamente. Reporte guardado en {report_filename}"
        )
        return report
    except Exception as e:
        logging.error(
            f"Error crítico en el módulo 'memoria_ram_durante': {str(e)}"
        )
        return {
            "status": "error",
            "module": "memoria_ram_durante",
            "timestamp": datetime.now().isoformat(),
            "error_message": str(e),
        }