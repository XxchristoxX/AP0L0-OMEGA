class AsistenteClimaHora:
    def __init__(self):
        pass
    def obtener_clima(self, ciudad):
        # Lógica para obtener el clima de la ciudad
        return f"El clima en {ciudad} es soleado."
    def run(self, params):
        if 'ciudad' not in params:
            return "Error: Se requiere el parámetro 'ciudad'."
        ciudad = params['ciudad']
        clima = self.obtener_clima(ciudad)
        return clima
asistente = AsistenteClimaHora()
resultado = asistente.run({'ciudad': 'Madrid'})