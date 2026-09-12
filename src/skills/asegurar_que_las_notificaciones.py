def asegurar_que_las_notificaciones(notificaciones):
    if not isinstance(notificaciones, dict):
        return "Error: Se esperaba un diccionario"
    resultados = {}
    for clave, valor in notificaciones.items():
        if isinstance(valor, bool):
            resultados[clave] = valor
        else:
            resultados[clave] = False  # Valor no válido, se establece en False
    return resultados
def run(notificaciones):
    return asegurar_que_las_notificaciones(notificaciones)