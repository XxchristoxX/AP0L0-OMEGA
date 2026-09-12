import sympy as sp
def run(params):
    equation = params.get('equation')
    variable = params.get('variable', 'x')
    if equation is None:
        return {"error": "No equation provided."}
    # Definir la variable
    var = sp.symbols(variable)
    # Resolver la ecuación
    try:
        solution = sp.solve(sp.sympify(equation), var)
        steps = sp.solve(sp.sympify(equation), var, dict=True)
        return {
            "solution": solution,
            "steps": [str(step) for step in steps]
        }
    except Exception as e:
        return {"error": str(e)}