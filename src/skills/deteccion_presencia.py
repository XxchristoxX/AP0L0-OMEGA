import os
import subprocess
import json
def detect_room():
    # Simulación de la detección de presencia en la habitación
    # Aquí puedes implementar la lógica específica de detección
    return bool(os.environ.get('ROOM_PRESENT', False))
def run(params):
    if detect_room():
        return {"status": "activated", "params": params}
    else:
        return {"status": "not activated"}