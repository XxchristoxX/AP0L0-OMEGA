def expresiones_faciales(datos):
    if not isinstance(datos, dict):
        return "Entrada inválida, se esperaba un diccionario."
    emociones = datos.get('emociones', [])
    if not isinstance(emociones, list):
        return "Entrada inválida, 'emociones' debe ser una lista."
    resultados = {}
    for emocion in emociones:
        if emocion not in resultados:
            resultados[emocion] = 1
        else:
            resultados[emocion] += 1
    return resultados
def run(datos):
    return expresiones_faciales(datos)