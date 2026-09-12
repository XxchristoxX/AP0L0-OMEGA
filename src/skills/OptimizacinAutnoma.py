class OptimizacinAutnoma:
    def __init__(self):
        pass
    def run(self, params):
        if not isinstance(params, dict):
            raise ValueError("El parámetro debe ser un diccionario")
        # Lógica de optimización (ejemplo)
        resultado = {}
        for key, value in params.items():
            if isinstance(value, (int, float)):
                resultado[key] = value * 2  # Ejemplo de procesamiento
            else:
                resultado[key] = value
        return resultado
# Ejemplo de uso
optimizacion = OptimizacinAutnoma()
resultado = optimizacion.run({'a': 1, 'b': 2.5, 'c': 'texto'})
print(resultado)