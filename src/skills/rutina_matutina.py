import json
import datetime
import os
import subprocess
def run(params):
    try:
        # Obtener la hora actual
        current_time = datetime.datetime.now().time()
        morning_start = datetime.time(6, 0)  # 6:00 AM
        morning_end = datetime.time(12, 0)    # 12:00 PM
        if morning_start <= current_time <= morning_end:
            # Ejecutar rutina matutina
            results = {}
            # Encender luces
            if 'lights' in params:
                results['lights'] = control_device('lights', params['lights'])
            # Ajustar termostato
            if 'thermostat' in params:
                results['thermostat'] = control_device('thermostat', params['thermostat'])
            # Reproducir música
            if 'music' in params:
                results['music'] = control_device('music', params['music'])
            return json.dumps({"status": "success", "results": results})
        else:
            return json.dumps({"status": "error", "message": "No es hora de la rutina matutina."})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
def control_device(device, action):
    # Simulación de control de dispositivos
    command = f"echo {action} {device}"
    subprocess.run(command, shell=True)
    return f"{device} {action} exitosamente."