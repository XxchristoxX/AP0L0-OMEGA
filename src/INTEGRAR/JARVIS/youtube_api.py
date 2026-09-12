"""
youtube_api.py — Módulo YouTube para JARVIS
==============================================
Todas las funcionalidades avanzadas mediante la API de YouTube Data v3.
La búsqueda simple (buscar_youtube) permanece en main2.py y NO se modifica.

Funciones disponibles:
  - yt_infos_video(video_id_o_url)   → título, vistas, likes, duración, canal
  - yt_buscar_multi(busqueda, n=5) → N primeros resultados (título + url)
  - yt_tendencias(categoria, pais)      → top 5 vídeos en tendencia
  - yt_infos_canal(nombre_canal)       → suscriptores, número de vídeos, descripción
  - yt_resumir_video(url_o_id)       → subtítulos → resumen IA
  - yt_ultimos_videos(nombre_canal)   → 3 últimos vídeos publicados
"""

import os
import re
import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Carga de la clave API (independiente de main2.py)
# ---------------------------------------------------------------------------
_RUTA_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_RUTA_ENV)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# Reutiliza el validador global de Jarvis si está disponible, sino fallback local
try:
    import builtins as _b
    _clave_valida = _b._clave_valida  # type: ignore
except AttributeError:
    _MARCAS_POSICION = frozenset({"VOTRE_CLE_ICI", "Votre ID", "votre_id", "VOTRE_TOKEN_ICI", ""})
    def _clave_valida(key):
        return bool(key) and str(key).strip() not in _MARCAS_POSICION

_BASE_URL = "https://www.googleapis.com/youtube/v3"
_TIMEOUT  = 7  # segundos


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

def _extraer_video_id(url_o_id: str) -> str:
    """Extrae el ID de vídeo desde una URL de YouTube o devuelve el ID directamente."""
    patrones = [
        r"(?:v=|youtu\.be/|/embed/|/v/)([a-zA-Z0-9_-]{11})",
    ]
    for pat in patrones:
        m = re.search(pat, url_o_id)
        if m:
            return m.group(1)
    # Si ya es un ID bruto (11 caracteres)
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_o_id.strip()):
        return url_o_id.strip()
    return ""


def _duracion_iso_a_legible(duracion_iso: str) -> str:
    """Convierte PT4M13S en '4 min 13 seg'."""
    m = re.search(r"(\d+)H", duracion_iso)
    horas = int(m.group(1)) if m else 0
    m = re.search(r"(\d+)M", duracion_iso)
    minutos = int(m.group(1)) if m else 0
    m = re.search(r"(\d+)S", duracion_iso)
    segundos = int(m.group(1)) if m else 0
    partes = []
    if horas:
        partes.append(f"{horas}h")
    if minutos:
        partes.append(f"{minutos} min")
    if segundos:
        partes.append(f"{segundos} seg")
    return " ".join(partes) if partes else "duración desconocida"


def _formatear_numero(n: int) -> str:
    """1234567 → '1,2 millón', 8500 → '8 500'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} millón{'es' if n >= 2_000_000 else ''}"
    if n >= 1_000:
        return f"{n:,}".replace(",", " ")
    return str(n)


def _buscar_id_canal(nombre_canal: str) -> tuple[str, str]:
    """Devuelve (channel_id, título_oficial) para un nombre de canal."""
    if not _clave_valida(YOUTUBE_API_KEY):
        return "", ""
    try:
        r = requests.get(
            f"{_BASE_URL}/search",
            params={
                "part": "snippet",
                "q": nombre_canal,
                "type": "channel",
                "maxResults": 1,
                "key": YOUTUBE_API_KEY,
            },
            timeout=_TIMEOUT,
        )
        data = r.json()
        if not data.get("items"):
            return "", ""
        item = data["items"][0]
        return item["id"]["channelId"], item["snippet"]["title"]
    except Exception:
        return "", ""


# ---------------------------------------------------------------------------
# 1. Información detallada de un vídeo
# ---------------------------------------------------------------------------

def yt_infos_video(url_o_id: str) -> str:
    """
    Devuelve la información de un vídeo de YouTube: título, canal, vistas, likes, duración.
    Desencadenantes: 'información del vídeo', 'cuántas vistas', 'qué es este vídeo'
    """
    if not _clave_valida(YOUTUBE_API_KEY):
        return "La clave de API de YouTube no está configurada, Mickael."

    video_id = _extraer_video_id(url_o_id)
    if not video_id:
        return "No he podido extraer el identificador de este vídeo, Mickael."

    try:
        r = requests.get(
            f"{_BASE_URL}/videos",
            params={
                "part": "snippet,statistics,contentDetails",
                "id": video_id,
                "key": YOUTUBE_API_KEY,
            },
            timeout=_TIMEOUT,
        )
        data = r.json()
        if not data.get("items"):
            return "Vídeo no encontrado en YouTube."

        item = data["items"][0]
        snip  = item["snippet"]
        stats = item.get("statistics", {})
        details = item.get("contentDetails", {})

        titulo   = snip.get("title", "Título desconocido")
        canal  = snip.get("channelTitle", "Canal desconocido")
        vistas    = _formatear_numero(int(stats.get("viewCount", 0)))
        likes   = _formatear_numero(int(stats.get("likeCount", 0))) if "likeCount" in stats else "no público"
        duracion   = _duracion_iso_a_legible(details.get("duration", ""))
        fecha    = snip.get("publishedAt", "")[:10]

        return (
            f"El vídeo « {titulo} » del canal {canal} "
            f"se publicó el {fecha}. "
            f"Tiene una duración de {duracion}, acumula {vistas} visualizaciones "
            f"y {likes} likes."
        )
    except Exception as e:
        return f"Error al recuperar la información del vídeo: {e}"


# ---------------------------------------------------------------------------
# 2. Búsqueda con múltiples resultados (5 vídeos)
# ---------------------------------------------------------------------------

def yt_buscar_multi(busqueda: str, n: int = 5) -> str:
    """
    Devuelve los N primeros resultados de YouTube para una búsqueda.
    Desencadenantes: 'busca [X] en youtube', 'muéstrame vídeos de [X]'
    """
    if not _clave_valida(YOUTUBE_API_KEY):
        return "La clave de API de YouTube no está configurada, Mickael."

    if not busqueda.strip():
        return "Dígame qué debo buscar en YouTube."

    try:
        r = requests.get(
            f"{_BASE_URL}/search",
            params={
                "part": "snippet",
                "q": busqueda,
                "type": "video",
                "maxResults": n,
                "relevanceLanguage": "fr",
                "key": YOUTUBE_API_KEY,
            },
            timeout=_TIMEOUT,
        )
        items = r.json().get("items", [])
        if not items:
            return f"No se encontraron resultados para « {busqueda} » en YouTube."

        lineas = [f"Estos son los {len(items)} mejores resultados para « {busqueda} »:"]
        for i, item in enumerate(items, 1):
            titulo   = item["snippet"]["title"]
            canal  = item["snippet"]["channelTitle"]
            vid_id  = item["id"]["videoId"]
            url     = f"https://www.youtube.com/watch?v={vid_id}"
            lineas.append(f"{i}. {titulo} — por {canal} | {url}")

        return "\n".join(lineas)
    except Exception as e:
        return f"Error al buscar en YouTube: {e}"


# ---------------------------------------------------------------------------
# 3. Vídeos en tendencia / populares
# ---------------------------------------------------------------------------

# Mapeo de categorías de texto → ID de YouTube
_CATEGORIAS_YT = {
    "musica": "10",
    "juegos": "20",
    "juego": "20",
    "gaming": "20",
    "deporte": "17",
    "deportes": "17",
    "ciencia": "28",
    "tecnologia": "28",
    "tech": "28",
    "cine": "1",
    "cinema": "1",
    "pelicula": "1",
    "actualidad": "25",
    "actualidades": "25",
    "info": "25",
    "informacion": "25",
    "comedia": "23",
    "comedia": "23",
    "humor": "23",
}

def yt_tendencias(categoria: str = "", pais: str = "FR") -> str:
    """
    Devuelve los 5 vídeos en tendencia en YouTube.
    Desencadenantes: 'tendencias de youtube', 'vídeos populares', 'top youtube'
    """
    if not _clave_valida(YOUTUBE_API_KEY):
        return "La clave de API de YouTube no está configurada, Mickael."

    params = {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": pais.upper(),
        "maxResults": 5,
        "key": YOUTUBE_API_KEY,
    }
    cat_id = _CATEGORIAS_YT.get(categoria.lower().strip(), "")
    if cat_id:
        params["videoCategoryId"] = cat_id

    try:
        r = requests.get(f"{_BASE_URL}/videos", params=params, timeout=_TIMEOUT)
        items = r.json().get("items", [])
        if not items:
            return "No se pudieron obtener las tendencias de YouTube en este momento."

        etiqueta_cat = f" en {categoria}" if categoria else ""
        lineas = [f"Este es el top {len(items)} de vídeos en tendencia{etiqueta_cat} en YouTube ahora mismo:"]
        for i, item in enumerate(items, 1):
            titulo  = item["snippet"]["title"]
            canal = item["snippet"]["channelTitle"]
            vistas   = _formatear_numero(int(item["statistics"].get("viewCount", 0)))
            vid_id = item["id"]
            url    = f"https://www.youtube.com/watch?v={vid_id}"
            lineas.append(f"{i}. {titulo} — {canal} ({vistas} visualizaciones) | {url}")

        return "\n".join(lineas)
    except Exception as e:
        return f"Error al recuperar las tendencias: {e}"


# ---------------------------------------------------------------------------
# 4. Información de un canal de YouTube
# ---------------------------------------------------------------------------

def yt_infos_canal(nombre_canal: str) -> str:
    """
    Devuelve la información de un canal: suscriptores, número de vídeos, descripción.
    Desencadenantes: 'cuántos suscriptores tiene [X]', 'información del canal [X]'
    """
    if not _clave_valida(YOUTUBE_API_KEY):
        return "La clave de API de YouTube no está configurada, Mickael."

    canal_id, titulo_oficial = _buscar_id_canal(nombre_canal)
    if not canal_id:
        return f"No he encontrado el canal « {nombre_canal} » en YouTube."

    try:
        r = requests.get(
            f"{_BASE_URL}/channels",
            params={
                "part": "snippet,statistics",
                "id": canal_id,
                "key": YOUTUBE_API_KEY,
            },
            timeout=_TIMEOUT,
        )
        items = r.json().get("items", [])
        if not items:
            return f"No se pudieron recuperar los datos del canal « {nombre_canal} »."

        item  = items[0]
        stats = item.get("statistics", {})
        snip  = item.get("snippet", {})

        suscriptores     = _formatear_numero(int(stats.get("subscriberCount", 0))) if stats.get("subscriberCount") else "no público"
        num_videos   = _formatear_numero(int(stats.get("videoCount", 0)))
        num_vistas     = _formatear_numero(int(stats.get("viewCount", 0)))
        descripcion = snip.get("description", "")[:150].strip()
        if descripcion and not descripcion.endswith("."):
            descripcion += "…"

        respuesta = (
            f"El canal de YouTube « {titulo_oficial} » tiene {suscriptores} suscriptores, "
            f"{num_videos} vídeos y {num_vistas} visualizaciones en total."
        )
        if descripcion:
            respuesta += f" Descripción: {descripcion}"
        return respuesta
    except Exception as e:
        return f"Error al recuperar la información del canal: {e}"


# ---------------------------------------------------------------------------
# 5. Resumen de vídeo mediante subtítulos (caption)
# ---------------------------------------------------------------------------

def yt_resumir_video(url_o_id: str) -> str:
    """
    Intenta recuperar los subtítulos de un vídeo de YouTube y los envía a la IA.
    Desencadenantes: 'resume este vídeo', 'de qué trata este vídeo'
    Requiere el paquete 'youtube_transcript_api' (pip install youtube-transcript-api)
    """
    if not _clave_valida(YOUTUBE_API_KEY):
        return "La clave de API de YouTube no está configurada, Mickael."

    video_id = _extraer_video_id(url_o_id)
    if not video_id:
        return "No he podido extraer el identificador de este vídeo, Mickael."

    # Recuperación de metadatos (título) mediante la API
    titulo = "este vídeo"
    try:
        r = requests.get(
            f"{_BASE_URL}/videos",
            params={"part": "snippet", "id": video_id, "key": YOUTUBE_API_KEY},
            timeout=_TIMEOUT,
        )
        items = r.json().get("items", [])
        if items:
            titulo = items[0]["snippet"]["title"]
    except Exception:
        pass

    # Intento de recuperación de subtítulos
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled  # type: ignore
        try:
            lista_transcripciones = YouTubeTranscriptApi.list_transcripts(video_id)
            # Prioridad: francés, sino inglés, sino primera disponible
            try:
                transcripcion = lista_transcripciones.find_transcript(["fr"])
            except NoTranscriptFound:
                try:
                    transcripcion = lista_transcripciones.find_transcript(["en"])
                except NoTranscriptFound:
                    transcripcion = lista_transcripciones._manually_created_transcripts and \
                                   list(lista_transcripciones._manually_created_transcripts.values())[0] or \
                                   list(lista_transcripciones._generated_transcripts.values())[0]

            segmentos = transcripcion.fetch()
            texto_bruto = " ".join(seg["text"] for seg in segmentos)

            # Límite a ~3000 palabras para no saturar la IA
            palabras = texto_bruto.split()
            if len(palabras) > 3000:
                texto_bruto = " ".join(palabras[:3000]) + "…"

            # Resumen mediante el módulo de IA de Jarvis (Gemini/Anthropic)
            try:
                import google.genai as genai  # type: ignore
                _clave_gemini = os.getenv("GEMINI_API_KEY", "")
                if _clave_valida(_clave_gemini):
                    cliente = genai.Client(api_key=_clave_gemini)
                    prompt = (
                        f"Resume en español en 4-5 frases concisas el contenido "
                        f"del vídeo de YouTube titulado « {titulo} » "
                        f"a partir de su transcripción:\n\n{texto_bruto}"
                    )
                    resp = cliente.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt,
                    )
                    return f"Este es el resumen de « {titulo} »: {resp.text.strip()}"
            except Exception:
                pass

            # Fallback: devuelve los primeros 500 caracteres de la transcripción
            extracto = texto_bruto[:500].strip()
            return (
                f"No he podido generar un resumen con IA para « {titulo} », "
                f"pero aquí está el comienzo de su transcripción: {extracto}…"
            )

        except (NoTranscriptFound, TranscriptsDisabled):
            return (
                f"El vídeo « {titulo} » no tiene subtítulos disponibles, "
                f"por lo que no puedo resumirlo."
            )
    except ImportError:
        return (
            "El módulo 'youtube-transcript-api' no está instalado. "
            "Dígame y lo instalaré para activar esta funcionalidad."
        )
    except Exception as e:
        return f"Error al recuperar los subtítulos: {e}"


# ---------------------------------------------------------------------------
# 6. Últimos vídeos de un canal
# ---------------------------------------------------------------------------

def yt_ultimos_videos(nombre_canal: str, n: int = 3) -> str:
    """
    Devuelve los N últimos vídeos publicados por un canal.
    Desencadenantes: 'últimos vídeos de [X]', 'qué hay de nuevo en el canal [X]'
    """
    if not _clave_valida(YOUTUBE_API_KEY):
        return "La clave de API de YouTube no está configurada, Mickael."

    canal_id, titulo_oficial = _buscar_id_canal(nombre_canal)
    if not canal_id:
        return f"No he encontrado el canal « {nombre_canal} » en YouTube."

    try:
        r = requests.get(
            f"{_BASE_URL}/search",
            params={
                "part": "snippet",
                "channelId": canal_id,
                "order": "date",
                "type": "video",
                "maxResults": n,
                "key": YOUTUBE_API_KEY,
            },
            timeout=_TIMEOUT,
        )
        items = r.json().get("items", [])
        if not items:
            return f"No se encontraron vídeos recientes para el canal « {titulo_oficial} »."

        lineas = [f"Los {len(items)} últimos vídeos de « {titulo_oficial} »:"]
        for i, item in enumerate(items, 1):
            titulo   = item["snippet"]["title"]
            fecha    = item["snippet"]["publishedAt"][:10]
            vid_id  = item["id"]["videoId"]
            url     = f"https://www.youtube.com/watch?v={vid_id}"
            lineas.append(f"{i}. [{fecha}] {titulo} | {url}")

        return "\n".join(lineas)
    except Exception as e:
        return f"Error al recuperar los últimos vídeos: {e}"