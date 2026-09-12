def bloquear_distracciones(config):
    if not isinstance(config, dict):
        return "Error: Se espera un diccionario como entrada."
    bloqueados = config.get("bloquear", [])
    if not isinstance(bloqueados, list):
        return "Error: La clave 'bloquear' debe ser una lista."
    for item in bloqueados:
        if not isinstance(item, str):
            return "Error: Todos los elementos en 'bloquear' deben ser cadenas."
    return f"Distracciones bloqueadas: {', '.join(bloqueados)}"
def run(config):
    resultado = bloquear_distracciones(config)
    return resultado