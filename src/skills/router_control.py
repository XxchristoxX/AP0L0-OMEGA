def router_control(config):
    try:
        if not isinstance(config, dict):
            raise ValueError("El argumento debe ser un diccionario.")
        # Ejemplo de configuración esperada
        required_keys = ['ip', 'subnet_mask', 'gateway']
        for key in required_keys:
            if key not in config:
                raise KeyError(f"Falta la clave requerida: {key}")
        ip = config['ip']
        subnet_mask = config['subnet_mask']
        gateway = config['gateway']
        # Simulando la lógica de control del router
        result = {
            'status': 'success',
            'ip': ip,
            'subnet_mask': subnet_mask,
            'gateway': gateway,
            'message': 'Configuración del router aplicada correctamente.'
        }
        return result
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
def run(config):
    return router_control(config)