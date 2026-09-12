def run(params):
    import json
    from datetime import datetime
    
    # Validar parámetros
    if not isinstance(params, dict):
        return {"error": "Invalid parameters"}
    
    # Procesar parámetros
    start_time = datetime.now()
    result = {}

    # Ejemplo de procesamiento: sumar números si están en el diccionario
    if 'numbers' in params and isinstance(params['numbers'], list):
        result['sum'] = sum(params['numbers'])
    
    # Ejemplo de procesamiento: contar palabras en un texto
    if 'text' in params and isinstance(params['text'], str):
        result['word_count'] = len(params['text'].split())
    
    # Calcular tiempo de ejecución
    result['execution_time'] = (datetime.now() - start_time).total_seconds()
    
    return result