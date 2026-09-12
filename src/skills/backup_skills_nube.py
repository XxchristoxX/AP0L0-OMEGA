def backup_skills_nube(data):
    if not isinstance(data, dict):
        return "Error: El argumento debe ser un diccionario."
    required_keys = ['nombre', 'habilidades', 'nube']
    for key in required_keys:
        if key not in data:
            return f"Error: Falta la clave '{key}' en el diccionario."
    if not isinstance(data['habilidades'], list):
        return "Error: 'habilidades' debe ser una lista."
    backup_result = {
        'nombre': data['nombre'],
        'habilidades': data['habilidades'],
        'nube': data['nube'],
        'estado': 'Backup completado'
    }
    return backup_result
def run(data):
    return backup_skills_nube(data)