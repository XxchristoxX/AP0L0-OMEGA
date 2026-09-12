import sys
import subprocess
from pathlib import Path
def ensure_package(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    try:
        __import__(import_name)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', package_name])
def run(params):
    ensure_package('feedparser', 'feedparser')
    ensure_package('gtts', 'gtts')
    ensure_package('plyer', 'plyer')
    import feedparser
    from gtts import gTTS
    from plyer import notification
    import os
    rss_urls = params.get('rss_urls', [
        'https://feeds.feedburner.com/TheHackersNews',
        'https://smoda.elpais.com/feed/',
        'https://www.xataka.com/index.xml'
    ])
    output_filename = params.get('output_filename', 'resumen_matutino.mp3')
    output_path = Path.cwd() / output_filename
    noticias = []
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]:
                titulo = entry.get('title', '')
                if titulo:
                    noticias.append(titulo)
        except Exception as e:
            continue
    if not noticias:
        return "No se pudieron extraer noticias de las fuentes RSS configuradas."
    texto_resumen = "Buenos días. Aquí tienes tu síntesis matutina contextual. " + ". ".join(noticias[:5]) + "."
    try:
        tts = gTTS(text=texto_resumen, lang='es', slow=False)
        tts.save(str(output_path))
    except Exception as e:
        return f"Error al generar el archivo de audio: {str(e)}"
    try:
        notification.notify(
            title='AP0L0 - Síntesis Matutina',
            message=f'Audio de 2 minutos listo para reproducirse: {output_filename}',
            timeout=10
        )
    except Exception:
        pass
    return f"Síntesis matutina generada exitosamente en: {output_path.resolve()}"