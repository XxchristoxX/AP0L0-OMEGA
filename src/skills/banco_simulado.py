import json
def run(params):
    if 'account_id' not in params or 'api_key' not in params:
        return json.dumps({'error': 'Faltan parámetros requeridos.'})
    account_id = params['account_id']
    api_key = params['api_key']
    # Simulación de conexión a un banco
    # En un caso real, se haría una solicitud HTTP a una API
    # Aquí simplemente se simula la respuesta
    simulated_database = {
        '12345': 1000.0,
        '67890': 250.75,
        '54321': 0.0
    }
    saldo = simulated_database.get(account_id, None)
    if saldo is None:
        return json.dumps({'error': 'Cuenta no encontrada.'})
    return json.dumps({'account_id': account_id, 'saldo': saldo})