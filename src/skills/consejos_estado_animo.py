import json
import requests
def analyze_mood(voice_data):
    # Simulación de análisis de voz para detectar el estado de ánimo
    # En una implementación real, se utilizaría un modelo de ML o API
    if "feliz" in voice_data:
        return "feliz"
    elif "triste" in voice_data:
        return "triste"
    elif "enojado" in voice_data:
        return "enojado"
    else:
        return "neutral"
def provide_advice(mood):
    advice = {
        "feliz": "Disfruta de tu día y comparte tu alegría con otros.",
        "triste": "Está bien sentirse así. Habla con alguien de confianza.",
        "enojado": "Tómate un momento para respirar y reflexionar.",
        "neutral": "Aprovecha el momento para planificar tu día."
    }
    return advice.get(mood, "Recuerda cuidar de ti mismo.")
def run(params):
    voice_data = params.get('voice_data', '')
    mood = analyze_mood(voice_data)
    return provide_advice(mood)