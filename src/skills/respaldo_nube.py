def respaldo_nube(datos):
    if not isinstance(datos, dict):
        return "Error: Se espera un diccionario."
    respaldos = {}
    for clave, valor in datos.items():
        if isinstance(valor, str):
            respaldos[clave] = f"Respaldo de {valor} realizado."
        else:
            respaldos[clave] = "Error: El valor debe ser una cadena."
    return respaldos
def run(datos):
    return respaldo_nube(datos)