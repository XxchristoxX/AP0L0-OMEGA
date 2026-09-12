import json
import datetime
def documentar_habilidad(nombre, descripcion, parametros, ejemplo):
    habilidad = {
        "nombre": nombre,
        "descripcion": descripcion,
        "parametros": parametros,
        "ejemplo": ejemplo,
        "fecha_creacion": datetime.datetime.now().isoformat()
    }
    with open(f"{nombre}.json", "w", encoding="utf-8") as f:
        json.dump(habilidad, f, ensure_ascii=False, indent=4)
def run(parametros):
    # Aquí se puede implementar la lógica de la habilidad
    resultado = {key: f"Procesado: {value}" for key, value in parametros.items()}
    return resultado
if __name__ == "__main__":
    # Ejemplo de uso
    nombre_habilidad = "suma"
    descripcion_habilidad = "Calcula la suma de dos números."
    parametros_habilidad = {
        "numero1": "El primer número a sumar.",
        "numero2": "El segundo número a sumar."
    }
    ejemplo_habilidad = "suma({'numero1': 5, 'numero2': 3})"
    documentar_habilidad(nombre_habilidad, descripcion_habilidad, parametros_habilidad, ejemplo_habilidad)