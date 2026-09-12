import json
import os
import subprocess
import time
from datetime import datetime
def get_system_metrics():
    cpu_usage = subprocess.check_output(['wmic', 'cpu', 'get', 'loadpercentage']).decode().split('\n')[1].strip()
    ram_usage = subprocess.check_output(['wmic', 'os', 'get', 'freephysicalmemory']).decode().split('\n')[1].strip()
    gpu_temp = 'N/A'  # Placeholder, requires specific methods for GPU
    return {
        "cpu": cpu_usage,
        "ram": ram_usage,
        "gpu": gpu_temp,
        "timestamp": datetime.now().isoformat()
    }
def generate_dashboard(metrics):
    dashboard = f"""
    Dashboard de Rendimiento
    =========================
    Hora: {metrics['timestamp']}
    Uso de CPU: {metrics['cpu']}%
    Uso de RAM: {metrics['ram']} MB
    Temperatura de GPU: {metrics['gpu']} °C
    """
    return dashboard
def status_page():
    while True:
        metrics = get_system_metrics()
        dashboard = generate_dashboard(metrics)
        os.system('cls' if os.name == 'nt' else 'clear')
        print(dashboard)
        time.sleep(1)  # Actualizar cada segundo
def run(params):
    if 'status' in params and params['status']:
        status_page()
    return {"result": "Dashboard en ejecución"}