import sys
import subprocess
def instalar_si_no_existe(paquete, import_nombre=None):
    if import_nombre is None:
        import_nombre = paquete
    try:
        __import__(import_nombre)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', paquete])
def run(params):
    try:
        instalar_si_no_existe('requests')
        instalar_si_no_existe('beautifulsoup4', 'bs4')
        instalar_si_no_existe('gtts')
        instalar_si_no_existe('playsound')
        import requests
        from bs4 import BeautifulSoup
        from gtts import gTTS
        import os
        import platform
        intereses = params.get('intereses', 'tecnologia inteligencia artificial')
        url = f"https://news.google.com/search?q={requests.utils.quote(intereses)}&hl=es&gl=ES&ceid=ES%3Aes"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return "Error al acceder a las fuentes de noticias."
        soup = BeautifulSoup(response.text, 'html.parser')
        titulares = []
        for item in soup.find_all('a', class_='JtKRv', limit=5):
            titulo = item.get_text()
            if titulo and titulo not in titulares:
                titulares.append(titulo)
        if not titulares:
            for item in soup.find_all('h3', limit=5):
                titulo = item.get_text()
                if titulo:
                    titulares.append(titulo)
        if not titulares:
            texto_resumen = "Buenos días. No se encontraron noticias recientes para tus intereses el día de hoy."
        else:
            texto_resumen = f"Buenos días AP0L0. Aquí tienes tu digest matutino de dos minutos. Las principales noticias sobre {intereses} son: "
            for i, tit in enumerate(titulares[:3], 1.
):
                texto_resumen += f"Noticia {i}: {tit}. "
        tts = gTTS(text=texto_resumen, lang='es', slow=False)
        audio_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'digest_matutino.mp3')
        tts.save(audio_path)
        sistema = platform.system()
        if sistema == 'Windows':
            os.startfile(audio_path)
        elif sistema == 'Darwin':
            subprocess.run(['afplay', audio_path])
        else:
            subprocess.run(['xdg-open', audio_path])
        return f"Digest matutino generado y reproducido con éxito. Archivo guardado en: {audio_path}"
    except Exception as e:
        return f"Error en la ejecución de la habilidad audio_minutos_directamente: {str(e)}"