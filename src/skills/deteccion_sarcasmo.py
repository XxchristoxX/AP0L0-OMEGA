import random
def analizar_sentido_humor(interacciones):
    """Analiza las interacciones para determinar el estilo de humor."""
    estilos = {
        'sarcastico': 0,
        'absurdo': 0,
        'inteligente': 0,
        'ligero': 0
    }
    
    for interaccion in interacciones:
        if 'sarcasmo' in interaccion:
            estilos['sarcastico'] += 1
        elif 'absurdo' in interaccion:
            estilos['absurdo'] += 1
        elif 'inteligente' in interaccion:
            estilos['inteligente'] += 1
        elif 'ligero' in interaccion:
            estilos['ligero'] += 1
    
    return max(estilos, key=estilos.get)
def generar_chiste(estilo):
    """Genera un chiste basado en el estilo de humor."""
    chistes = {
        'sarcastico': ["Claro, porque eso es exactamente lo que necesitaba.", 
                       "Oh, sí, porque eso tiene mucho sentido."],
        'absurdo': ["¿Por qué los pájaros no usan Facebook? Porque ya tienen Twitter.", 
                    "Si las vacas pudieran volar, no habría más hamburguesas."],
        'inteligente': ["¿Por qué los programadores prefieren la oscuridad? Porque la luz atrae a los bugs.", 
                        "La estadística es como la bikini: lo que revela es sugerente, pero lo que oculta es vital."],
        'ligero': ["¿Por qué los esqueletos no pelean entre sí? Porque no tienen agallas.", 
                   "¿Qué hace una abeja en el gimnasio? Zum-ba."],
    }
    
    return random.choice(chistes[estilo])
def run(params):
    interacciones = params.get('interacciones', [])
    estilo_humor = analizar_sentido_humor(interacciones)
    chiste_personalizado = generar_chiste(estilo_humor)
    
    return {
        'estilo_humor': estilo_humor,
        'chiste': chiste_personalizado
    }