import sys
import subprocess
def instalar_si_no_existe(modulo, paquete=None):
    if paquete is None:
        paquete = modulo
    try:
        __import__(modulo)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', paquete])
def run(params):
    try:
        instalar_si_no_existe('requests', 'requests')
        instalar_si_no_existe('bs4', 'beautifulsoup4')
        instalar_si_no_existe('pyttsx3', 'pyttsx3')
        instalar_si_no_existe('plyer', 'plyer')
        import requests
        from bs4 import BeautifulSoup
        import pyttsx3
        from plyer import notification
        import datetime
        proyectos = params.get('proyectos', ['python', 'inteligencia artificial', 'automatizacion'])
        url = 'https://news.google.com/rss?hl=es&gl=ES&ceid=ES:es'
        respuesta = requests.get(url, timeout=10)
        if respuesta.status_code != 200:
            return "Error: No se pudo obtener el feed de noticias."
        soup = BeautifulSoup(respuesta.content, features='xml')
        items = soup.findAll('item')
        noticias_filtradas = []
        for item in items:
            titulo = item.title.text.lower()
            for proyecto in proyectos:
                if proyecto.lower() in titulo:
                    noticias_filtradas.append(item.title.text)
                    break
        if not noticias_filtradas:
            resumen = "No se encontraron noticias críticas para tus proyectos activos hoy."
        else:
            resumen = f"Buenos días. He encontrado {len(noticias_filtradas)} noticias relevantes para tus proyectos. "
            resumen += " ".join(noticias_filtradas[:3])
        fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d")
        nombre_archivo = f"resumen_diario_{fecha_hoy}.txt"
        with open(nombre_archivo, "w", encoding="utf-8") as f:
            f.write(resumen)
        try:
            notification.notify(
                title='Resumen Contextual Diario',
                message='Boletín matutino generado con éxito.',
                app_name='destacando_solo_informacin',
                timeout=5
            )
        except Exception:
            pass
        try:
            engine = pyttsx3.init()
            engine.say(resumen)
            engine.runAndWait()
        except Exception:
            pass
        return f"Éxito: Resumen diario generado y guardado en {nombre_archivo}."
    except Exception as e:
        return f"Error en la ejecución de la habilidad: {str(e)}"