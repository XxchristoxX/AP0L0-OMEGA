def detectar_intrusiones(ruta_archivo):
    palabras_clave = ['Failed password', 'error', 'intrusion']
    lineas_sospechosas = []
    with open(ruta_archivo, 'r') as archivo:
        for linea in archivo:
            if any(palabra in linea for palabra in palabras_clave):
                lineas_sospechosas.append(linea.strip())
    return lineas_sospechosas
def run(parametros):
    ruta_archivo = parametros.get('ruta_archivo')
    if not ruta_archivo:
        return "Se requiere la ruta del archivo."
    try:
        resultados = detectar_intrusiones(ruta_archivo)
        return resultados
    except FileNotFoundError:
        return "Archivo no encontrado."
    except Exception as e:
        return str(e)