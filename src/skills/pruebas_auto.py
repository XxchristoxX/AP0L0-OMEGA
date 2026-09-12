import unittest
import json

def run(params):
    """
    Skill que devuelve el valor de la clave 'key' o 'default' si no existe.
    """
    # Implementa la lógica de tu función aquí
    return params.get("key", "default")

class TestRunFunction(unittest.TestCase):
    def test_with_existing_key(self):
        params = {"key": "value"}
        result = run(params)
        self.assertEqual(result, "value")

    def test_with_non_existing_key(self):
        params = {}
        result = run(params)
        self.assertEqual(result, "default")

    def test_with_none_key(self):
        params = {"key": None}
        result = run(params)
        self.assertEqual(result, None)

# EJECUCIÓN DE PRUEBAS CORREGIDA:
# Antes estaba mal indentado dentro de un método y fuera del bloque if.
# Ahora solo se ejecuta si llamamos al script directamente.
if __name__ == "__main__":
    unittest.main()