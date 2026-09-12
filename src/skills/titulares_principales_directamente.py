import sys
import subprocess
def instalar_si_falta(libreria, pip_nombre=None):
    if pip_nombre is None:
        pip_nombre = libreria
    try:
        __import__(libreria)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', pip_nombre])
def run(params):
    instalar_si_falta('feedparser', 'feedparser')
    instalar_si_falta('pyttsx3', 'pyttsx3')
    instalar_si_falta('plyer', 'plyer')
    import feedparser
    import pyttsx3
    from plyer import notification
    from datetime import datetime
    rss_urls = params.get('rss_urls', [
        'http://ep00.epimg.net/rss/elpais/portada.xml',
        'https://news.google.com/rss?hl=es&gl=ES&ceid=ES:es'
    ])
    keywords = params.get('keywords', ['tecnologia', 'inteligencia artificial', 'python', 'ciencia'])
    titulares_relevantes = []
    try:
        for url in rss_urls:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                titulo = entry.title.lower()
                for kw in keywords:
                    if kw.lower() in titulo:
                        titulares_relevantes.append(entry.title)
                        break
        if not titulares_relevantes:
            mensaje = "No se encontraron titulares recientes con tus palabras clave."
        else:
            mensaje = f"Boletín diario: Se encontraron {len(titulares_relevantes)} noticias relevantes."
        notification.notify(
            title='Resumen Temático Inteligente',
            message=mensaje,
            timeout=10
        )
        engine = pyttsx3.init()
        engine.say("Buenos días. Aquí tienes tus titulares principales.")
        for i, titular in enumerate(titulares_relevantes[:5]):
            print(f"- {titular}")
            engine.say(titular)
        if len(titulares_relectantes_si_hay := titulares_relevantes) > 5:
            engine.say("Tienes más noticias disponibles en el registro.")
        engine.runAndWait()
        return f"Ejecución exitosa. {len(titulares_relevantes)} titulares procesados y leídos."
    except Exception as e:
        error_msg = f"Error al generar el resumen temático: {str(e)}"
        print(error_msg)
        return error_msg