import json
import os
import subprocess
from datetime import datetime
def run(params):
    # Optimización de uso de memoria
    result = {}

    # Procesar parámetros
    for key, value in params.items():
        if isinstance(value, str):
            result[key] = value.strip()
        elif isinstance(value, (int, float)):
            result[key] = value
        elif isinstance(value, list):
            result[key] = [str(v) for v in value if v is not None]

    # Ejemplo de uso de subprocess para obtener información del sistema
    system_info = subprocess.check_output(['uname', '-a'], text=True).strip()
    result['system_info'] = system_info

    # Guardar resultado en un archivo temporal para liberar memoria
    temp_file = 'result.json'
    with open(temp_file, 'w') as f:
        json.dump(result, f)

    # Leer el archivo y devolver el contenido
    with open(temp_file, 'r') as f:
        final_result = json.load(f)

    # Eliminar archivo temporal
    os.remove(temp_file)

    return final_result