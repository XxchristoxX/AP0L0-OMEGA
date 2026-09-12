import sys
import subprocess
import os
from pathlib import Path
def instalar_si_no_existe(paquete, nombre_importacion=None):
    if nombre_importacion is None:
        nombre_importacion = paquete
    try:
        __import__(nombre_importacion)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', paquete])
def run(params):
    instalar_si_no_existe('feedparser', 'feedparser')
    instalar_si_no_existe('gtts', 'gtts')
    instalar_si_no_existe('plyer', 'plyer')
    import feedparser
    from gtts import gTTS
    from plyer import notification
    try:
        feeds = [
            "https://feeds.elpais.com/recientes-s/rss.xml",
            "https://www.europapress.es/rss/rss.aspx?ch=00066"
        ]
        titulares = []
        for url in feeds:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:3]:
                titulares.append(entry.title)
        if not titulares:
            return "No se pudieron obtener titulares de las fuentes RSS."
        resumen_texto = "Buenos días. Aquí tienes tu síntesis de prensa contextual de dos minutos. "
        resumen_texto += ". ".join(titulares[:6])
        resumen_texto += ". Que tengas un excelente día."
        output_dir = Path.home() / "Desktop"
        output_dir.mkdir(parents=True, exist_ok=True)
        audio_path = output_dir / "minutos_listo_reproducir.mp3"
        tts = gTTS(text=resumen_texto, lang='es', slow=False)
        tts.save(str(audio_path))
        notification.notify(
            title="Síntesis de Prensa Contextual",
            message="Audio de 2 minutos generado en el Escritorio.",
            timeout=5
        )
        return f"Habilidad ejecutada con éxito. Audio guardado en: {audio_path}"
    except Exception as e:
        return f"Error al generar la síntesis de prensa: {str(e)}"