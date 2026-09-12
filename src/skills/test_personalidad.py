def run(params):
    questions = {
        "1": "¿Prefieres pasar tiempo solo o en grupo?",
        "2": "¿Te sientes más cómodo con planes estructurados o improvisados?",
        "3": "¿Tomas decisiones basándote en la lógica o en tus sentimientos?",
        "4": "¿Te gusta más la teoría o la práctica?",
        "5": "¿Eres más impulsivo o reflexivo?"
    }
    results = {
        "introvertido": 0,
        "extrovertido": 0,
        "estructurado": 0,
        "improvisado": 0,
        "logico": 0,
        "emocional": 0,
        "teorico": 0,
        "practico": 0,
        "impulsivo": 0,
        "reflexivo": 0
    }
    for key, question in questions.items():
        answer = params.get(key)
        if answer == "A":
            results["introvertido"] += 1
        elif answer == "B":
            results["extrovertido"] += 1
        elif answer == "C":
            results["estructurado"] += 1
        elif answer == "D":
            results["improvisado"] += 1
        elif answer == "E":
            results["logico"] += 1
        elif answer == "F":
            results["emocional"] += 1
        elif answer == "G":
            results["teorico"] += 1
        elif answer == "H":
            results["practico"] += 1
        elif answer == "I":
            results["impulsivo"] += 1
        elif answer == "J":
            results["reflexivo"] += 1
    personality_type = []
    if results["introvertido"] > results["extrovertido"]:
        personality_type.append("Introvertido")
    else:
        personality_type.append("Extrovertido")
    if results["estructurado"] > results["improvisado"]:
        personality_type.append("Estructurado")
    else:
        personality_type.append("Improvisado")
    if results["logico"] > results["emocional"]:
        personality_type.append("Lógico")
    else:
        personality_type.append("Emocional")
    if results["teorico"] > results["practico"]:
        personality_type.append("Teórico")
    else:
        personality_type.append("Práctico")
    if results["impulsivo"] > results["reflexivo"]:
        personality_type.append("Impulsivo")
    else:
        personality_type.append("Reflexivo")
    return {"personalidad": " ".join(personality_type)}