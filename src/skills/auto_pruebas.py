import json
import unittest

class Skill:
    def __init__(self, name, level):
        self.name = name
        self.level = level

class SkillTest(unittest.TestCase):
    def setUp(self):
        self.skill = Skill("Python", "Advanced")

    def test_skill_name(self):
        self.assertEqual(self.skill.name, "Python")

    def test_skill_level(self):
        self.assertEqual(self.skill.level, "Advanced")

def run(params):
    """
    Skill que ejecuta pruebas unitarias sobre la clase Skill.
    Espera params: {'name': 'Python', 'level': 'Advanced'}
    """
    try:
        # Si no se pasan parámetros, usamos valores por defecto para evitar errores
        name = params.get('name', 'Python')
        level = params.get('level', 'Advanced')
        
        # Instanciamos la habilidad con los parámetros recibidos
        skill = Skill(name, level)
        
        # Cargamos y ejecutamos las pruebas
        suite = unittest.TestLoader().loadTestsFromTestCase(SkillTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        
        return {
            'success': result.wasSuccessful(),
            'failures': len(result.failures),
            'errors': len(result.errors),
            'skill_name': skill.name,
            'skill_level': skill.level
        }
    except Exception as e:
        return {'error': str(e)}

# Si se ejecuta directamente, corre las pruebas automáticamente
if __name__ == "__main__":
    # Ejemplo de ejecución del skill desde consola
    print(run({'name': 'Python', 'level': 'Advanced'}))
    # También se pueden ejecutar las pruebas unitarias directamente
    unittest.main()