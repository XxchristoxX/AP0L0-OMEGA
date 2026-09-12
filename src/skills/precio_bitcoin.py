def precio_bitcoin(datos):
    try:
        return datos['precio'] * datos['cantidad']
    except KeyError:
        return "Error: Claves 'precio' y 'cantidad' deben estar presentes en el diccionario."
def run(datos):
    resultado = precio_bitcoin(datos)
    return resultado
# Ejemplo de uso
# datos = {'precio': 30000, 'cantidad': 0.5}
# print(run(datos))