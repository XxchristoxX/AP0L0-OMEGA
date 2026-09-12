# src/actions/youtube_api.py
"""
YouTube API avanzada para AP0L0
Funciones: info, search, trending, channel, summarize, latest
"""

import os
import re
import requests
from src.core.config import _get_config

YOUTUBE_API_KEY = _get_config().get("youtube_api_key", "")
BASE_URL = "https://www.googleapis.com/youtube/v3"
TIMEOUT = 7


def _extraer_video_id(url_ou_id):
    patterns = [
        r"(?:v=|youtu\.be/|/embed/|/v/)([a-zA-Z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url_ou_id)
        if m:
            return m.group(1)
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_ou_id.strip()):
        return url_ou_id.strip()
    return ""


def _duree_iso_to_lisible(duree_iso):
    m = re.search(r"(\d+)H", duree_iso)
    heures = int(m.group(1)) if m else 0
    m = re.search(r"(\d+)M", duree_iso)
    minutes = int(m.group(1)) if m else 0
    m = re.search(r"(\d+)S", duree_iso)
    secondes = int(m.group(1)) if m else 0
    partes = []
    if heures:
        partes.append(f"{heures}h")
    if minutes:
        partes.append(f"{minutes} min")
    if secondes:
        partes.append(f"{secondes} seg")
    return " ".join(partes) if partes else "duración desconocida"


def _formater_nombre(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} millón"
    if n >= 1_000:
        return f"{n:,}".replace(",", " ")
    return str(n)


def _chercher_chaine_id(nom_chaine):
    if not YOUTUBE_API_KEY:
        return "", ""
    try:
        r = requests.get(
            f"{BASE_URL}/search",
            params={"part": "snippet", "q": nom_chaine, "type": "channel", "maxResults": 1, "key": YOUTUBE_API_KEY},
            timeout=TIMEOUT
        )
        data = r.json()
        if data.get("items"):
            item = data["items"][0]
            return item["id"]["channelId"], item["snippet"]["title"]
    except Exception:
        pass
    return "", ""


# ---- FUNCIONES ----

def yt_infos_video(url_ou_id):
    if not YOUTUBE_API_KEY:
        return "Falta API Key de YouTube."
    video_id = _extraer_video_id(url_ou_id)
    if not video_id:
        return "No se pudo extraer el ID del video."
    try:
        r = requests.get(
            f"{BASE_URL}/videos",
            params={"part": "snippet,statistics,contentDetails", "id": video_id, "key": YOUTUBE_API_KEY},
            timeout=TIMEOUT
        )
        data = r.json()
        if not data.get("items"):
            return "Video no encontrado."
        item = data["items"][0]
        snip = item["snippet"]
        stats = item.get("statistics", {})
        details = item.get("contentDetails", {})
        titulo = snip.get("title", "Título desconocido")
        canal = snip.get("channelTitle", "Canal desconocido")
        vistas = _formater_nombre(int(stats.get("viewCount", 0)))
        likes = _formater_nombre(int(stats.get("likeCount", 0))) if "likeCount" in stats else "no público"
        duracion = _duree_iso_to_lisible(details.get("duration", ""))
        fecha = snip.get("publishedAt", "")[:10]
        return f"Video '{titulo}' de {canal}, publicado el {fecha}. Duración: {duracion}. Vistas: {vistas}, Likes: {likes}."
    except Exception as e:
        return f"Error: {e}"


def yt_chercher_multi(recherche, n=5):
    if not YOUTUBE_API_KEY:
        return "Falta API Key de YouTube."
    if not recherche:
        return "Indica qué buscar."
    try:
        r = requests.get(
            f"{BASE_URL}/search",
            params={"part": "snippet", "q": recherche, "type": "video", "maxResults": n, "relevanceLanguage": "fr", "key": YOUTUBE_API_KEY},
            timeout=TIMEOUT
        )
        items = r.json().get("items", [])
        if not items:
            return f"No se encontraron resultados para '{recherche}'."
        lines = [f"Resultados para '{recherche}':"]
        for i, item in enumerate(items, 1):
            titulo = item["snippet"]["title"]
            canal = item["snippet"]["channelTitle"]
            vid_id = item["id"]["videoId"]
            url = f"https://www.youtube.com/watch?v={vid_id}"
            lines.append(f"{i}. {titulo} - {canal} | {url}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def yt_trending(categorie="", pays="FR"):
    if not YOUTUBE_API_KEY:
        return "Falta API Key de YouTube."
    params = {"part": "snippet,statistics", "chart": "mostPopular", "regionCode": pays.upper(), "maxResults": 5, "key": YOUTUBE_API_KEY}
    categories = {
        "musique": "10", "jeux": "20", "gaming": "20", "sport": "17",
        "science": "28", "technologie": "28", "cinéma": "1", "actualité": "25"
    }
    cat_id = categories.get(categorie.lower().strip(), "")
    if cat_id:
        params["videoCategoryId"] = cat_id
    try:
        r = requests.get(f"{BASE_URL}/videos", params=params, timeout=TIMEOUT)
        items = r.json().get("items", [])
        if not items:
            return "No se pudieron obtener tendencias."
        lines = [f"Tendencias {categorie if categorie else 'generales'}:"]
        for i, item in enumerate(items, 1):
            titulo = item["snippet"]["title"]
            canal = item["snippet"]["channelTitle"]
            vistas = _formater_nombre(int(item["statistics"].get("viewCount", 0)))
            vid_id = item["id"]
            url = f"https://www.youtube.com/watch?v={vid_id}"
            lines.append(f"{i}. {titulo} - {canal} ({vistas} vistas) | {url}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def yt_infos_chaine(nom_chaine):
    if not YOUTUBE_API_KEY:
        return "Falta API Key de YouTube."
    channel_id, titre_officiel = _chercher_chaine_id(nom_chaine)
    if not channel_id:
        return f"No se encontró la cadena '{nom_chaine}'."
    try:
        r = requests.get(
            f"{BASE_URL}/channels",
            params={"part": "snippet,statistics", "id": channel_id, "key": YOUTUBE_API_KEY},
            timeout=TIMEOUT
        )
        items = r.json().get("items", [])
        if not items:
            return f"No se pudieron obtener datos de '{nom_chaine}'."
        item = items[0]
        stats = item.get("statistics", {})
        snip = item.get("snippet", {})
        abonnes = _formater_nombre(int(stats.get("subscriberCount", 0))) if stats.get("subscriberCount") else "no público"
        nb_videos = _formater_nombre(int(stats.get("videoCount", 0)))
        nb_vues = _formater_nombre(int(stats.get("viewCount", 0)))
        desc = snip.get("description", "")[:150]
        return f"Canal '{titre_officiel}': {abonnes} suscriptores, {nb_videos} videos, {nb_vues} vistas totales. {desc}..."
    except Exception as e:
        return f"Error: {e}"


def yt_resumer_video(url_ou_id):
    if not YOUTUBE_API_KEY:
        return "Falta API Key de YouTube."
    video_id = _extraer_video_id(url_ou_id)
    if not video_id:
        return "ID de video inválido."
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_transcript(["fr"])
        except:
            try:
                transcript = transcript_list.find_transcript(["en"])
            except:
                transcript = list(transcript_list._manually_created_transcripts.values())[0] if transcript_list._manually_created_transcripts else list(transcript_list._generated_transcripts.values())[0]
        segments = transcript.fetch()
        texto = " ".join(seg["text"] for seg in segments)
        # Usar Gemini para resumir (opcional)
        try:
            from src.core.ai_providers import generate
            resumen = generate(f"Resume este texto en español en 3 frases: {texto[:3000]}", provider="gemini")
            return f"Resumen: {resumen}"
        except:
            return f"Transcripción (primeros 500 caracteres): {texto[:500]}..."
    except ImportError:
        return "Instala youtube-transcript-api: pip install youtube-transcript-api"
    except Exception as e:
        return f"Error con subtítulos: {e}"


def yt_dernieres_videos(nom_chaine, n=3):
    if not YOUTUBE_API_KEY:
        return "Falta API Key de YouTube."
    channel_id, titre_officiel = _chercher_chaine_id(nom_chaine)
    if not channel_id:
        return f"No se encontró la cadena '{nom_chaine}'."
    try:
        r = requests.get(
            f"{BASE_URL}/search",
            params={"part": "snippet", "channelId": channel_id, "order": "date", "type": "video", "maxResults": n, "key": YOUTUBE_API_KEY},
            timeout=TIMEOUT
        )
        items = r.json().get("items", [])
        if not items:
            return f"No hay videos recientes para '{titre_officiel}'."
        lines = [f"Últimos {len(items)} videos de '{titre_officiel}':"]
        for i, item in enumerate(items, 1):
            titulo = item["snippet"]["title"]
            fecha = item["snippet"]["publishedAt"][:10]
            vid_id = item["id"]["videoId"]
            url = f"https://www.youtube.com/watch?v={vid_id}"
            lines.append(f"{i}. [{fecha}] {titulo} | {url}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


# ===== FUNCIÓN EXPORTABLE =====

async def youtube_advanced(params: dict, player=None, speak=None) -> str:
    """
    Punto de entrada para la herramienta youtube_advanced.
    Parámetros:
        action: "info" | "search" | "trending" | "channel" | "summarize" | "latest"
        query: URL/ID de video, término de búsqueda o nombre de canal
        category: categoría para trending (música, juegos, deporte, etc.)
        region: código de región (FR, US, etc.)
        max_results: número máximo de resultados (default 5)
    """
    action = params.get("action", "info").lower()
    query = params.get("query", "")
    region = params.get("region", "FR")
    category = params.get("category", "")
    max_results = params.get("max_results", 5)

    if action == "info":
        if not query:
            return "Falta URL o ID del video."
        result = yt_infos_video(query)

    elif action == "search":
        if not query:
            return "Falta la búsqueda."
        result = yt_chercher_multi(query, max_results)

    elif action == "trending":
        result = yt_trending(category, region)

    elif action == "channel":
        if not query:
            return "Falta el nombre del canal."
        result = yt_infos_chaine(query)

    elif action == "summarize":
        if not query:
            return "Falta URL o ID del video."
        result = yt_resumer_video(query)

    elif action == "latest":
        if not query:
            return "Falta el nombre del canal."
        result = yt_dernieres_videos(query, max_results)

    else:
        result = f"Acción '{action}' no soportada. Opciones: info, search, trending, channel, summarize, latest"

    if speak:
        speak(result)
    if player:
        player.write_log(f"[YouTube] {result}")
    return result