import requests
import json
import datetime
def obtener_noticias():
    url = "https://newsapi.org/v2/top-headlines?country=us&apiKey=YOUR_API_KEY"
    response = requests.get(url)
    if response.status_code == 200:
        noticias = json.loads(response.text)
        resumen = []
        for article in noticias['articles'][:5]:
            resumen.append(f"{article['title']} - {article['source']['name']}")
        return "\n".join(resumen)
    else:
        return "No se pudo obtener noticias."
def obtener_chiste():
    chistes = [
        "¿Por qué los pájaros no usan Facebook? Porque ya tienen Twitter.",
        "¿Qué hace una abeja en el gimnasio? Zum-ba.",
        "¿Cómo se despiden los químicos? Ácido un placer."
    ]
    return chistes[0]
def run(parametros):
    if not parametros.get('dormido_bien', False):
        resumen_noticias = obtener_noticias()
        chiste = obtener_chiste()
        return f"Resumen de noticias:\n{resumen_noticias}\n\nChiste:\n{chiste}"
    return "Todo va bien, ¡sigue así!"
    # print(resultado)