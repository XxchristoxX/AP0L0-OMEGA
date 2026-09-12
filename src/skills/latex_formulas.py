def generate_latex_formula(description):
    # Mapeo de descripciones a fórmulas LaTeX
    formulas = {
        "energía cinética": r"E_k = \frac{1}{2}mv^2",
        "ley de gravitación": r"F = \frac{G m_1 m_2}{r^2}",
        "ecuación de estado": r"PV = nRT",
        "ecuación cuadrática": r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a",
        "fuerza": r"F = ma"
    }
    return formulas.get(description.lower(), "Descripción no encontrada.")
def run(params):
    description = params.get('description', '')
    return generate_latex_formula(description)