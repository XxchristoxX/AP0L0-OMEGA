def reconocimiento_objetos(imagen):
    # Simulación de un modelo de reconocimiento de objetos
    objetos_detectados = []
    if "perro" in imagen:
        objetos_detectados.append("perro")
    if "gato" in imagen:
        objetos_detectados.append("gato")
    if "auto" in imagen:
        objetos_detectados.append("auto")
    return objetos_detectados
def run(datos):
    resultados = {}
    for clave, imagen in datos.items():
        resultados[clave] = reconocimiento_objetos(imagen)
    return resultados
# Ejemplo de uso
if __name__ == "__main__":
    datos_prueba = {
        "imagen1": ["perro", "gato"],
        "imagen2": ["auto"],
        "imagen3": ["gato", "auto", "perro"]
    }
    print(run(datos_prueba))