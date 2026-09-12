import os
import sys
import subprocess
import json
from datetime import datetime, timedelta
def check_and_install(package):
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
def run(params):
    try:
        check_and_install('plyer')
        from plyer import notification
        logs_path = params.get('logs_path', 'interaction_logs.json')
        tasks_path = params.get('tasks_path', 'pending_tasks.json')
        default_logs = [
            {"timestamp": str(datetime.now() - timedelta(hours=2)), "activity": "Revisión de correo urgente", "urgency": 5, "duration_mins": 30},
            {"timestamp": str(datetime.now() - timedelta(hours=1)), "activity": "Desarrollo de módulo backend", "urgency": 3, "duration_mins": 120},
            {"timestamp": str(datetime.now()), "activity": "Pausa café", "urgency": 1, "duration_mins": 15}
        ]
        default_tasks = [
            {"task": "Actualizar documentación", "deadline": str(datetime.now() + timedelta(days=2)), "base_priority": 2},
            {"task": "Corregir bug crítico en producción", "deadline": str(datetime.now() + timedelta(hours=4)), "base_priority": 5},
            {"task": "Preparar presentación semanal", "deadline": str(datetime.now() + timedelta(days=1)), "base_priority": 3}
        ]
        if not os.path.exists(logs_path):
            with open(logs_path, 'w', encoding='utf-8') as f:
                json.dump(default_logs, f, indent=4)
        if not os.path.exists(tasks_path):
            with open(tasks_path, 'w', encoding='utf-8') as f:
                json.dump(default_tasks, f, indent=4)
        with open(logs_path, 'r', encoding='utf-8') as f:
            logs = json.load(f)
        with open(tasks_path, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
        avg_urgency = sum(log.get('urgency', 3) for log in logs) / len(logs) if logs else 3
        for task in tasks:
            deadline_str = task.get('deadline')
            if deadline_str:
                deadline_dt = datetime.fromisoformat(deadline_str)
                time_left = (deadline_dt - datetime.now()).total_seconds() / 3600
                if time_left <= 0:
                    time_left = 0.1
                urgency_multiplier = max(1.0, 24.0 / time_left)
            else:
                urgency_multiplier = 1.0
            calculated_score = (task.get('base_priority', 1) * 0.4) + (avg_urgency * 0.3) + (urgency_multiplier * 0.3)
            task['calculated_score'] = round(calculated_score, 2)
        tasks.sort(key=lambda x: x['calculated_score'], reverse=True)
        sorted_tasks_path = 'optimized_tasks.json'
        with open(sorted_tasks_path, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, indent=4)
        top_task = tasks[0]['task'] if tasks else "Ninguna"
        notification.notify(
            title="Motor de Priorización Contextual",
            message=f"Tareas reorganizadas. Siguiente prioridad: {top_task}",
            timeout=5
        )
        return {
            "status": "success",
            "message": f"Tareas priorizadas exitosamente. Archivo guardado en {sorted_tasks_path}.",
            "top_priority_task": top_task
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error al ejecutar el motor de priorización: {str(e)}"
        }