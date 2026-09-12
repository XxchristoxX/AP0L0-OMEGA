def analizar_contrasena(contrasena):
    longitud = len(contrasena)
    tiene_mayusculas = any(c.isupper() for c in contrasena)
    tiene_minusculas = any(c.islower() for c in contrasena)
    tiene_digitos = any(c.isdigit() for c in contrasena)
    tiene_simbolos = any(c in "!@#$%^&*()-_=+[]{}|;:',.<>?/" for c in contrasena)
    puntaje = 0
    if longitud >= 8:
        puntaje += 1
    if tiene_mayusculas:
        puntaje += 1
    if tiene_minusculas:
        puntaje += 1
    if tiene_digitos:
        puntaje += 1
    if tiene_simbolos:
        puntaje += 1
    if puntaje <= 2:
        return 'débil'
    elif puntaje == 3:
        return 'media'
    else:
        return 'fuerte'
def run(params):
    contrasena = params.get('contrasena', '')
    return analizar_contrasena(contrasena)