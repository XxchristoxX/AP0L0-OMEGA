def run(params):
    nevera = params.get('nevera', {})
    lista_compras = params.get('lista_compras', [])
    falta = []
    for item in lista_compras:
        if item not in nevera or nevera[item] <= 0:
            falta.append(item)
    return {'falta': falta}
    # print(resultado)  # Debería mostrar {'falta': ['huevos', 'pan']}