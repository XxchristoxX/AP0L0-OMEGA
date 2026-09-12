def desarrollar_e_integrar_un(diccionario):
    resultado = {}
    for clave, valor in diccionario.items():
        if isinstance(valor, list):
            resultado[clave] = [v * 2 for v in valor]
        else:
            resultado[clave] = valor
    return resultado
def run(diccionario):
    return desarrollar_e_integrar_un(diccionario)