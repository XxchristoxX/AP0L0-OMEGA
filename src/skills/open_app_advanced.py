import subprocess
import json
def open_app(app_name, params=None):
    if params is None:
        params = {}
    
    # Convertir parámetros a una cadena de argumentos
    args = ' '.join([f"--{key}={value}" for key, value in params.items()])
    
    # Comando para abrir la aplicación con los parámetros
    command = f"{app_name} {args}"
    
    # Ejecutar el comando
    try:
        subprocess.run(command, check=True, shell=True)
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": str(e)}

    return {"success": True}
def run(params):
    # Implementar lógica de la función 'run'
    # Aquí se puede procesar el diccionario de parámetros y devolver un resultado
    result = {key: value for key, value in params.items()}
    return result