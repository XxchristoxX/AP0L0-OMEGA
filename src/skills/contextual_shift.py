import datetime
def change_theme(hour):
    if 5 <= hour < 12:
        return "morning_digest"
    elif 12 <= hour < 18:
        return "productivity_focus"
    else:
        return "leisure_mode"
def run(params):
    current_hour = datetime.datetime.now().hour
    theme = change_theme(current_hour)
    if theme == "morning_digest":
        return {
            "theme": theme,
            "message": "Buenos días! Vamos a revisar las noticias y planificar tu día."
        }
    elif theme == "productivity_focus":
        return {
            "theme": theme,
            "message": "Es hora de concentrarse en las tareas. ¿Qué necesitas lograr hoy?"
        }
    else:
        return {
            "theme": theme,
            "message": "Buenas noches! ¿Te gustaría disfrutar de un poco de entretenimiento o un resumen del día?"
        }