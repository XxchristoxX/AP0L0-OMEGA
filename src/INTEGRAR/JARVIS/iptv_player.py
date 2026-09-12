"""
iptv_player.py — J.A.R.V.I.S IPTV y Reproductor de Video Backend v2
============================================================
Nuevas funcionalidades:
  - Servidor HTTP local (puerto 8766) para streaming de video con soporte Range
  - Transcodificación AAC mediante ffmpeg para archivos MKV/AVI/WMV (audio incompatible con navegador)
  - Detección de pistas de audio mediante ffprobe
  - Selección de pista de audio dinámica
"""

import os
import re
import json
import asyncio
import subprocess
import threading
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from http.server import HTTPServer, BaseHTTPRequestHandler

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
EXTENSIONES_VIDEO_SOPORTADAS_IPTV = {".mp4", ".mkv", ".avi", ".mov", ".wmv",
                                ".flv", ".webm", ".m4v", ".mpg", ".mpeg",
                                ".3gp", ".ts", ".m2ts"}
EXTENSIONES_PLAYLIST_SOPORTADAS_IPTV = {".m3u", ".m3u8", ".xspf", ".pls"}

# Puerto del servidor HTTP de video local (diferente al WS en 8765)
PUERTO_VIDEO_IPTV = 8766

# ─── Estado del servidor HTTP ──────────────────────────────────────────────────
_servidor_video: HTTPServer | None = None
_hilo_servidor_video: threading.Thread | None = None

# ─── Pista de audio actual (por sesión) ───────────────────────────────────
_pista_audio_actual: int = 0


# ---------------------------------------------------------------------------
# Ayudantes ffmpeg / ffprobe
# ---------------------------------------------------------------------------

def _ffmpeg_disponible() -> bool:
    """Verifica si ffmpeg está disponible en el PATH."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3)
        return True
    except Exception:
        return False


def _ffprobe_disponible() -> bool:
    """Verifica si ffprobe está disponible en el PATH."""
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=3)
        return True
    except Exception:
        return False


def sondear_info_archivo(ruta_archivo: str) -> dict:
    """
    Usa ffprobe para extraer pistas de audio, duración y códec de video.
    Devuelve {"audio_tracks": [...], "duration": float, "video_codec": str, "error": str|None}
    """
    if not os.path.exists(ruta_archivo):
        return {"audio_tracks": [], "duration": 0, "video_codec": "", "error": "Archivo no encontrado"}

    if not _ffprobe_disponible():
        return {"audio_tracks": [], "duration": 0, "video_codec": "", "error": "ffprobe no disponible"}

    try:
        resultado = subprocess.run([
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            ruta_archivo
        ], capture_output=True, text=True, timeout=10,
           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

        datos = json.loads(resultado.stdout)
        flujos = datos.get("streams", [])
        fmt     = datos.get("format", {})

        pistas_audio = []
        codec_video  = ""

        for s in flujos:
            tipo = s.get("codec_type", "")
            if tipo == "audio":
                idx     = len(pistas_audio)
                idioma  = s.get("tags", {}).get("language", f"pista {idx + 1}")
                codec   = s.get("codec_name", "?")
                titulo  = s.get("tags", {}).get("title", "")
                canales = s.get("channels", 2)
                nombre_canales = {1: "Mono", 2: "Estéreo", 6: "5.1", 8: "7.1"}.get(canales, f"{canales}ch")
                etiqueta = titulo or f"{idioma.upper()} — {codec.upper()} {nombre_canales}"
                pistas_audio.append({"index": idx, "label": etiqueta,
                                     "codec": codec, "lang": idioma, "channels": canales})
            elif tipo == "video" and not codec_video:
                codec_video = s.get("codec_name", "")

        duracion = float(fmt.get("duration", 0))
        return {
            "audio_tracks": pistas_audio,
            "duration": duracion,
            "video_codec": codec_video,
            "error": None
        }
    except Exception as e:
        print(f"[IPTV] Error en ffprobe: {e}")
        return {"audio_tracks": [], "duration": 0, "video_codec": "", "error": str(e)}


# ---------------------------------------------------------------------------
# Servidor HTTP de video local
# ---------------------------------------------------------------------------

class _ManejadorVideoIPTV(BaseHTTPRequestHandler):
    """Manejador HTTP para servir videos locales con soporte Range y transcodificación ffmpeg."""

    def log_message(self, fmt, *args):
        pass  # Silencia los logs HTTP

    def do_OPTIONS(self):
        self.send_response(200)
        self._agregar_cors()
        self.end_headers()

    def _agregar_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range")

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            if parsed.path == "/video":
                ruta  = urllib.parse.unquote(params.get("path", [""])[0])
                aidx   = int(params.get("audio", ["0"])[0])
                self._servir_video(ruta, aidx)
            elif parsed.path == "/probe":
                ruta = urllib.parse.unquote(params.get("path", [""])[0])
                info  = sondear_info_archivo(ruta)
                cuerpo  = json.dumps(info).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(cuerpo)))
                self._agregar_cors()
                self.end_headers()
                self.wfile.write(cuerpo)
            else:
                self.send_error(404)
        except Exception as e:
            print(f"[IPTV-HTTP] Error en solicitud: {e}")

    # ── Despachador ─────────────────────────────────────────────────────────
    def _servir_video(self, ruta_archivo: str, indice_audio: int = 0):
        if not ruta_archivo or not os.path.exists(ruta_archivo):
            self.send_error(404, "Archivo no encontrado")
            return
        ext = os.path.splitext(ruta_archivo)[1].lower()

        # Para formatos que pueden tener códecs de audio incompatibles
        necesita_transcodificar = ext in (".mkv", ".avi", ".wmv", ".flv", ".mov", ".mpg", ".mpeg", ".ts", ".m2ts")
        # MP4/WebM → servir directamente con soporte Range (búsqueda nativa)
        if not necesita_transcodificar or not _ffmpeg_disponible():
            self._servir_directo(ruta_archivo)
        else:
            self._servir_ffmpeg(ruta_archivo, indice_audio)

    # ── Transcodificación ffmpeg ──────────────────────────────────────────────────
    def _servir_ffmpeg(self, ruta_archivo: str, indice_audio: int = 0):
        """Stream del archivo transcodificado a MP4/AAC mediante ffmpeg."""
        cmd = [
            "ffmpeg", "-loglevel", "quiet",
            "-i", ruta_archivo,
            "-map", "0:v:0",
            "-map", f"0:a:{indice_audio}",
            "-c:v", "copy",            # copia de video sin recodificar (rápido)
            "-c:a", "aac",             # transcodificar audio → AAC (compatible con navegador)
            "-b:a", "192k",
            "-f", "mp4",
            "-movflags", "frag_keyframe+empty_moov+default_base_moof",
            "pipe:1"
        ]
        cf = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self._agregar_cors()
            self.end_headers()

            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=cf
            )
            try:
                while True:
                    fragmento = proc.stdout.read(65536)
                    if not fragmento:
                        break
                    try:
                        self.wfile.write(fragmento)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        break
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except Exception:
                    proc.kill()
        except Exception as e:
            print(f"[IPTV-HTTP] Error en ffmpeg: {e}")
            # Fallback: intento directo
            try:
                self._servir_directo(ruta_archivo)
            except Exception:
                pass

    # ── Servicio directo de archivo (con soporte Range para búsqueda) ──────────────
    def _servir_directo(self, ruta_archivo: str):
        """Sirve el archivo directamente con soporte para solicitudes Range."""
        try:
            tamano_archivo = os.path.getsize(ruta_archivo)
            ext = os.path.splitext(ruta_archivo)[1].lower()
            mapa_tipos = {
                ".mp4": "video/mp4", ".m4v": "video/mp4",
                ".webm": "video/webm",
                ".mkv":  "video/x-matroska",
                ".avi":  "video/avi",
                ".mov":  "video/quicktime",
                ".ts":   "video/mp2t",
            }
            tipo_contenido = mapa_tipos.get(ext, "application/octet-stream")

            cabecera_range = self.headers.get("Range", "")
            if cabecera_range:
                m = re.match(r"bytes=(\d+)-(\d*)", cabecera_range)
                if m:
                    inicio = int(m.group(1))
                    fin   = int(m.group(2)) if m.group(2) else tamano_archivo - 1
                    fin   = min(fin, tamano_archivo - 1)
                    longitud = fin - inicio + 1
                    self.send_response(206)
                    self.send_header("Content-Type", tipo_contenido)
                    self.send_header("Content-Range", f"bytes {inicio}-{fin}/{tamano_archivo}")
                    self.send_header("Content-Length", str(longitud))
                    self.send_header("Accept-Ranges", "bytes")
                    self._agregar_cors()
                    self.end_headers()
                    with open(ruta_archivo, "rb") as f:
                        f.seek(inicio)
                        restante = longitud
                        while restante > 0:
                            datos = f.read(min(65536, restante))
                            if not datos:
                                break
                            try:
                                self.wfile.write(datos)
                            except (BrokenPipeError, OSError):
                                break
                            restante -= len(datos)
                    return

            self.send_response(200)
            self.send_header("Content-Type", tipo_contenido)
            self.send_header("Content-Length", str(tamano_archivo))
            self.send_header("Accept-Ranges", "bytes")
            self._agregar_cors()
            self.end_headers()
            with open(ruta_archivo, "rb") as f:
                while True:
                    datos = f.read(65536)
                    if not datos:
                        break
                    try:
                        self.wfile.write(datos)
                    except (BrokenPipeError, OSError):
                        break
        except Exception as e:
            print(f"[IPTV-HTTP] Error en servir_directo: {e}")


# ---------------------------------------------------------------------------
# Inicio / Parada del servidor HTTP
# ---------------------------------------------------------------------------

def iniciar_servidor_video() -> bool:
    """Lanza el servidor HTTP de video en PUERTO_VIDEO_IPTV (idempotente)."""
    global _servidor_video, _hilo_servidor_video
    if _servidor_video is not None:
        return True
    try:
        _servidor_video = HTTPServer(("127.0.0.1", PUERTO_VIDEO_IPTV), _ManejadorVideoIPTV)
        _hilo_servidor_video = threading.Thread(
            target=_servidor_video.serve_forever,
            daemon=True,
            name="IPTV-HTTP-Server"
        )
        _hilo_servidor_video.start()
        print(f"[IPTV] Servidor HTTP de video iniciado en http://127.0.0.1:{PUERTO_VIDEO_IPTV}")
        return True
    except Exception as e:
        print(f"[IPTV] Error al iniciar servidor HTTP: {e}")
        _servidor_video = None
        return False


def detener_servidor_video():
    """Detiene el servidor HTTP de video."""
    global _servidor_video, _hilo_servidor_video
    if _servidor_video:
        _servidor_video.shutdown()
        _servidor_video = None
        _hilo_servidor_video = None
        print("[IPTV] Servidor HTTP de video detenido.")


# Inicio automático al importar el módulo
iniciar_servidor_video()


# ---------------------------------------------------------------------------
# Parseo de M3U / M3U8
# ---------------------------------------------------------------------------

def _parsear_contenido_m3u(contenido: str) -> list:
    canales = []
    lineas = contenido.splitlines()
    i = 0
    while i < len(lineas):
        linea = lineas[i].strip()
        if linea.startswith("#EXTINF"):
            meta = linea[len("#EXTINF:"):]
            nombre, logo, grupo = "", "", ""
            if "," in meta:
                parte_atributos, nombre = meta.rsplit(",", 1)
                nombre = nombre.strip()
            else:
                parte_atributos = meta
            logo_m  = re.search(r'tvg-logo="([^"]*)"',   parte_atributos)
            tvgn_m  = re.search(r'tvg-name="([^"]*)"',   parte_atributos)
            grupo_m = re.search(r'group-title="([^"]*)"', parte_atributos)
            if logo_m:  logo  = logo_m.group(1)
            if tvgn_m and not nombre: nombre = tvgn_m.group(1)
            if grupo_m: grupo = grupo_m.group(1)
            i += 1
            while i < len(lineas) and (not lineas[i].strip() or lineas[i].strip().startswith("#")):
                i += 1
            if i < len(lineas):
                url = lineas[i].strip()
                if url:
                    canales.append({"name": nombre or url, "url": url, "logo": logo, "group": grupo})
        i += 1
    return canales


def _parsear_contenido_xspf(contenido: str) -> list:
    canales = []
    try:
        root = ET.fromstring(contenido)
        ns = {"xspf": "http://xspf.org/ns/0/"}
        tracklist = root.find("xspf:trackList", ns) or root.find("trackList")
        if tracklist is None:
            return canales
        for track in tracklist:
            loc   = track.find("{http://xspf.org/ns/0/}location") or track.find("location")
            titulo = track.find("{http://xspf.org/ns/0/}title")   or track.find("title")
            img   = track.find("{http://xspf.org/ns/0/}image")   or track.find("image")
            url   = loc.text.strip()   if loc   is not None and loc.text   else ""
            nombre  = titulo.text.strip() if titulo is not None and titulo.text else url
            logo  = img.text.strip()   if img   is not None and img.text   else ""
            if url:
                canales.append({"name": nombre, "url": url, "logo": logo, "group": ""})
    except Exception as e:
        print(f"[IPTV] Error al parsear XSPF: {e}")
    return canales


def _parsear_contenido_pls(contenido: str) -> list:
    canales = []
    archivos, titulos = {}, {}
    for linea in contenido.splitlines():
        fm = re.match(r'^File(\d+)=(.+)$', linea.strip(), re.IGNORECASE)
        tm = re.match(r'^Title(\d+)=(.+)$', linea.strip(), re.IGNORECASE)
        if fm: archivos[fm.group(1)]  = fm.group(2).strip()
        if tm: titulos[tm.group(1)] = tm.group(2).strip()
    for idx, url in archivos.items():
        canales.append({"name": titulos.get(idx, url), "url": url, "logo": "", "group": ""})
    return canales


def parsear_archivo_playlist(ruta_archivo: str) -> dict:
    try:
        if not os.path.exists(ruta_archivo):
            return {"success": False, "channels": [], "error": "Archivo no encontrado"}
        ext = os.path.splitext(ruta_archivo)[1].lower()
        with open(ruta_archivo, "r", encoding="utf-8", errors="ignore") as f:
            contenido = f.read()
        if ext in (".m3u", ".m3u8"):
            canales = _parsear_contenido_m3u(contenido)
        elif ext == ".xspf":
            canales = _parsear_contenido_xspf(contenido)
        elif ext == ".pls":
            canales = _parsear_contenido_pls(contenido)
        else:
            return {"success": False, "channels": [], "error": f"Formato no soportado: {ext}"}
        print(f"[IPTV] Playlist parseada: {len(canales)} canal(es)")
        return {"success": True, "channels": canales, "error": None}
    except Exception as e:
        return {"success": False, "channels": [], "error": str(e)}


def parsear_playlist_url(url: str) -> dict:
    try:
        import requests
        resp = requests.get(url, headers={"User-Agent": "JARVIS/8.0"}, timeout=15)
        resp.raise_for_status()
        contenido = resp.text
        contenido_lower = contenido.strip().lower()
        url_lower = url.lower().split("?")[0]
        if "#extm3u" in contenido_lower[:1000] or "#extinf" in contenido_lower or url_lower.endswith(".m3u") or url_lower.endswith(".m3u8"):
            canales = _parsear_contenido_m3u(contenido)
        elif "<tracklist" in contenido_lower or "xspf" in contenido_lower[:500]:
            canales = _parsear_contenido_xspf(contenido)
        elif "[playlist]" in contenido_lower[:200]:
            canales = _parsear_contenido_pls(contenido)
        else:
            canales = _parsear_contenido_m3u(contenido)
        return {"success": True, "channels": canales, "error": None}
    except Exception as e:
        return {"success": False, "channels": [], "error": str(e)}


# ---------------------------------------------------------------------------
# Detección del tipo de stream
# ---------------------------------------------------------------------------

def detectar_tipo_stream(url: str) -> str:
    u = url.lower().split("?")[0]
    if u.endswith(".m3u8") or "m3u8" in u: return "hls"
    if u.endswith(".mpd"):                  return "dash"
    if any(u.endswith(e) for e in (".mp4", ".m4v", ".webm")): return "mp4"
    if u.startswith("rtsp://") or u.startswith("rtmp://"):     return "rtsp"
    return "direct"


def obtener_url_stream_video(ruta_archivo: str, pista_audio: int = 0) -> str:
    """Devuelve la URL HTTP local para hacer streaming del archivo de video."""
    codificada = urllib.parse.quote(ruta_archivo, safe="")
    return f"http://127.0.0.1:{PUERTO_VIDEO_IPTV}/video?path={codificada}&audio={pista_audio}"


# ---------------------------------------------------------------------------
# Manejador de mensajes WebSocket
# ---------------------------------------------------------------------------

async def manejar_mensaje_iptv_ws(data: dict, websocket, clientes_conectados: set) -> bool:
    global _pista_audio_actual
    tipo_msg = data.get("type", "")

    # ── Abrir el panel ─────────────────────────────────────────────────
    if tipo_msg == "iptv_open":
        await _difundir_iptv(clientes_conectados, {"type": "iptv_open"})
        return True

    # ── Parsear una playlist local ────────────────────────────────────────
    if tipo_msg == "iptv_parse_m3u":
        ruta_archivo = data.get("path", "")
        if not ruta_archivo:
            await websocket.send(json.dumps({"type": "iptv_playlist_error", "error": "Ruta faltante"}))
            return True
        resultado = await asyncio.to_thread(parsear_archivo_playlist, ruta_archivo)
        await websocket.send(json.dumps({
            "type": "iptv_playlist",
            "success": resultado["success"],
            "channels": resultado["channels"],
            "source_path": ruta_archivo,
            "source_name": os.path.basename(ruta_archivo),
            "stream_type": detectar_tipo_stream(ruta_archivo),
            "error": resultado.get("error")
        }))
        return True

    # ── Parsear una playlist desde URL ────────────────────────────────
    if tipo_msg == "iptv_parse_url":
        url = data.get("url", "")
        if not url:
            await websocket.send(json.dumps({"type": "iptv_playlist_error", "error": "URL faltante"}))
            return True
        
        # Intento de parseo como playlist primero
        resultado = await asyncio.to_thread(parsear_playlist_url, url)
        if resultado["success"] and len(resultado["channels"]) > 0:
            await websocket.send(json.dumps({
                "type": "iptv_playlist",
                "success": True,
                "channels": resultado["channels"],
                "source_path": url,
                "source_name": url.split("/")[-1].split("?")[0] or "Playlist IPTV",
                "stream_type": detectar_tipo_stream(url),
                "error": None
            }))
        else:
            # Fallback a stream directo
            await websocket.send(json.dumps({
                "type": "iptv_direct_stream",
                "url": url,
                "stream_type": detectar_tipo_stream(url),
                "name": url.split("/")[-1].split("?")[0] or "Stream directo"
            }))
        return True

    # ── Abrir un archivo de video o playlist local ────────────────────────
    if tipo_msg == "iptv_open_file":
        ruta_archivo = data.get("path", "")
        if not ruta_archivo:
            await websocket.send(json.dumps({"type": "iptv_playlist_error", "error": "Ruta faltante"}))
            return True
        ext = os.path.splitext(ruta_archivo)[1].lower()

        if ext in EXTENSIONES_PLAYLIST_SOPORTADAS_IPTV:
            resultado = await asyncio.to_thread(parsear_archivo_playlist, ruta_archivo)
            await websocket.send(json.dumps({
                "type": "iptv_playlist",
                "success": resultado["success"],
                "channels": resultado["channels"],
                "source_path": ruta_archivo,
                "source_name": os.path.basename(ruta_archivo),
                "stream_type": "m3u",
                "error": resultado.get("error")
            }))
        elif ext in EXTENSIONES_VIDEO_SOPORTADAS_IPTV:
            _pista_audio_actual = 0
            url_stream = obtener_url_stream_video(ruta_archivo, 0)

            # Sondear pistas de audio en segundo plano
            info_archivo = await asyncio.to_thread(sondear_info_archivo, ruta_archivo)

            await websocket.send(json.dumps({
                "type": "iptv_stream_ready",
                "url": url_stream,
                "stream_type": "mp4",  # la salida de ffmpeg siempre es mp4
                "name": os.path.basename(ruta_archivo),
                "local_path": ruta_archivo,
                "audio_tracks": info_archivo.get("audio_tracks", []),
                "video_codec": info_archivo.get("video_codec", ""),
                "ffmpeg_available": _ffmpeg_disponible(),
                "duration": info_archivo.get("duration", 0)
            }))
        else:
            await websocket.send(json.dumps({
                "type": "iptv_playlist_error",
                "error": f"Formato no soportado: {ext}"
            }))
        return True

    # ── Cambiar la pista de audio ────────────────────────────────────────────
    if tipo_msg == "iptv_set_audio_track":
        ruta_archivo   = data.get("path", "")
        pista_audio = int(data.get("audio_track", 0))
        _pista_audio_actual = pista_audio

        if not ruta_archivo or not os.path.exists(ruta_archivo):
            await websocket.send(json.dumps({"type": "iptv_playlist_error", "error": "Archivo no encontrado"}))
            return True

        url_stream = obtener_url_stream_video(ruta_archivo, pista_audio)
        await websocket.send(json.dumps({
            "type": "iptv_stream_ready",
            "url": url_stream,
            "stream_type": "mp4",
            "name": os.path.basename(ruta_archivo),
            "local_path": ruta_archivo,
            "audio_track_changed": True,
            "audio_track": pista_audio
        }))
        return True

    return False


async def _difundir_iptv(clientes: set, mensaje: dict):
    if not clientes:
        return
    msg = json.dumps(mensaje)
    try:
        await asyncio.gather(*[c.send(msg) for c in clientes], return_exceptions=True)
    except Exception as e:
        print(f"[IPTV] Error en difusión: {e}")