import json
from datetime import datetime
def generar_informe_gastos(apuntes):
    informe = {}
    for fecha, gastos in apuntes.items():
        mes = datetime.strptime(fecha, "%Y-%m").strftime("%B %Y")
        total_gastos = sum(gastos)
        informe[mes] = total_gastos
    return informe
def run(params):
    apuntes = params.get('apuntes', {})
    informe = generar_informe_gastos(apuntes)
    return json.dumps(informe, indent=4)