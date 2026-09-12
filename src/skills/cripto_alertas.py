def cripto_alertas(datos):
    alertas = []
    for cripto, valor in datos.items():
        if valor < 100:
            alertas.append(f'Alerta: {cripto} está por debajo de 100, valor actual: {valor}')
        elif valor > 1000:
            alertas.append(f'Alerta: {cripto} está por encima de 1000, valor actual: {valor}')
    return alertas
def run(datos):
    return cripto_alertas(datos)