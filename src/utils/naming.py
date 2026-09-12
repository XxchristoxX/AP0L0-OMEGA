import re
import time

STOP_WORDS = {
    "propongo", "gustara", "gustaría", "me", "crear", "desarrollar",
    "implementar", "una", "habilidad", "para", "con", "sin", "sobre",
    "puede", "podria", "podría", "hacer", "como", "poder", "usando",
    "mediante", "que", "del", "al", "lo", "las", "los", "sus",
    "nueva", "nuevo", "mejorar", "mejora", "funcion", "función",
    "sistema", "asistente", "de", "la", "el", "un", "unos", "unas"
}

def generate_skill_name(description: str, max_words: int = 3, fallback: str = None) -> str:
    """
    Genera un nombre de habilidad a partir de una descripción.
    Elimina stopwords, toma las últimas palabras significativas,
    las une con guiones bajos y limpia caracteres.
    """
    if not description:
        if fallback:
            return fallback
        return f"skill_auto_{int(time.time()) % 100000}"

    # Extraer palabras de 3+ letras (incluye acentos)
    words = re.findall(r'\b[a-zA-ZáéíóúñÁÉÍÓÚÑ]{3,}\b', description.lower())

    # Tomar las últimas palabras (más relevantes al final)
    if len(words) > 6:
        words = words[-6:]

    # Filtrar stopwords
    filtered = [w for w in words if w not in STOP_WORDS]

    if not filtered:
        filtered = words[-3:] if len(words) >= 3 else words

    # Limpiar y unir
    name = '_'.join(filtered[:max_words]).lower()
    name = re.sub(r'[^a-zA-Z0-9_]', '', name)

    if not name:
        if fallback:
            return fallback
        return f"skill_auto_{int(time.time()) % 100000}"

    return name[:40]  # límite de longitud