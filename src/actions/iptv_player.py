# src/actions/iptv_player.py
"""
iptv_player.py — J.A.R.V.I.S IPTV & Video Player Backend v2
Adaptado para AP0L0
============================================================
Nuevas funcionalidades :
  - Servidor HTTP local (puerto 8766) para streaming de vídeo con soporte Range
  - Transcoding AAC vía ffmpeg para archivos MKV/AVI/WMV (audio incompatible con navegador)
  - Detección de pistas de audio vía ffprobe
  - Selección dinámica de pista de audio
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
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
IPTV_SUPPORTED_VIDEO_EXTS   = {".mp4", ".mkv", ".avi", ".mov", ".wmv",
                                ".flv", ".webm", ".m4v", ".mpg", ".mpeg",
                                ".3gp", ".ts", ".m2ts"}
IPTV_SUPPORTED_PLAYLIST_EXTS = {".m3u", ".m3u8", ".xspf", ".pls"}

# Puerto del servidor HTTP de vídeo local (diferente del WS en 8765)
IPTV_VIDEO_PORT = 8766

# ─── Estado del servidor HTTP ──────────────────────────────────────────────────
_video_server: HTTPServer | None = None
_video_server_thread: threading.Thread | None = None

# ─── Pista de audio actual (por sesión) ───────────────────────────────────
_current_audio_track: int = 0


# ---------------------------------------------------------------------------
# ffmpeg / ffprobe helpers
# ---------------------------------------------------------------------------

def _ffmpeg_available() -> bool:
    """Verifica si ffmpeg está disponible en el PATH."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3)
        return True
    except Exception:
        return False


def _ffprobe_available() -> bool:
    """Verifica si ffprobe está disponible en el PATH."""
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=3)
        return True
    except Exception:
        return False


def probe_file_info(file_path: str) -> dict:
    """
    Usa ffprobe para extraer pistas de audio, duración y codec de vídeo.
    Retorna {"audio_tracks": [...], "duration": float, "video_codec": str, "error": str|None}
    """
    if not os.path.exists(file_path):
        return {"audio_tracks": [], "duration": 0, "video_codec": "", "error": "Archivo no encontrado"}

    if not _ffprobe_available():
        return {"audio_tracks": [], "duration": 0, "video_codec": "", "error": "ffprobe no disponible"}

    try:
        result = subprocess.run([
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            file_path
        ], capture_output=True, text=True, timeout=10,
           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        fmt     = data.get("format", {})

        audio_tracks = []
        video_codec  = ""

        for s in streams:
            ctype = s.get("codec_type", "")
            if ctype == "audio":
                idx     = len(audio_tracks)
                lang    = s.get("tags", {}).get("language", f"pista {idx + 1}")
                codec   = s.get("codec_name", "?")
                title   = s.get("tags", {}).get("title", "")
                ch      = s.get("channels", 2)
                ch_name = {1: "Mono", 2: "Estéreo", 6: "5.1", 8: "7.1"}.get(ch, f"{ch}ch")
                label   = title or f"{lang.upper()} — {codec.upper()} {ch_name}"
                audio_tracks.append({"index": idx, "label": label,
                                     "codec": codec, "lang": lang, "channels": ch})
            elif ctype == "video" and not video_codec:
                video_codec = s.get("codec_name", "")

        duration = float(fmt.get("duration", 0))
        return {
            "audio_tracks": audio_tracks,
            "duration": duration,
            "video_codec": video_codec,
            "error": None
        }
    except Exception as e:
        print(f"[IPTV] Error en ffprobe: {e}")
        return {"audio_tracks": [], "duration": 0, "video_codec": "", "error": str(e)}


# ---------------------------------------------------------------------------
# Servidor HTTP de vídeo local
# ---------------------------------------------------------------------------

class _IPTVVideoHandler(BaseHTTPRequestHandler):
    """Handler HTTP para servir vídeos locales con soporte Range y transcoding ffmpeg."""

    def log_message(self, fmt, *args):
        pass  # Silencia los logs HTTP

    def do_OPTIONS(self):
        self.send_response(200)
        self._add_cors()
        self.end_headers()

    def _add_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range")

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            if parsed.path == "/video":
                fpath  = urllib.parse.unquote(params.get("path", [""])[0])
                aidx   = int(params.get("audio", ["0"])[0])
                self._serve_video(fpath, aidx)
            elif parsed.path == "/probe":
                fpath = urllib.parse.unquote(params.get("path", [""])[0])
                info  = probe_file_info(fpath)
                body  = json.dumps(info).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self._add_cors()
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)
        except Exception as e:
            print(f"[IPTV-HTTP] Error en solicitud: {e}")

    # ── Dispatcher ─────────────────────────────────────────────────────────
    def _serve_video(self, file_path: str, audio_idx: int = 0):
        if not file_path or not os.path.exists(file_path):
            self.send_error(404, "Archivo no encontrado")
            return
        ext = os.path.splitext(file_path)[1].lower()

        # Para formatos que pueden tener codecs de audio incompatibles
        needs_transcode = ext in (".mkv", ".avi", ".wmv", ".flv", ".mov", ".mpg", ".mpeg", ".ts", ".m2ts")
        # MP4/WebM → servir directamente con soporte Range (seek nativo)
        if not needs_transcode or not _ffmpeg_available():
            self._serve_direct(file_path)
        else:
            self._serve_ffmpeg(file_path, audio_idx)

    # ── Transcoding ffmpeg ──────────────────────────────────────────────────
    def _serve_ffmpeg(self, file_path: str, audio_idx: int = 0):
        """Transmite el archivo transcodificado a MP4/AAC vía ffmpeg."""
        cmd = [
            "ffmpeg", "-loglevel", "quiet",
            "-i", file_path,
            "-map", "0:v:0",
            "-map", f"0:a:{audio_idx}",
            "-c:v", "copy",            # copia de vídeo sin recodificar (rápido)
            "-c:a", "aac",             # transcodifica audio → AAC (compatible con navegador)
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
            self._add_cors()
            self.end_headers()

            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=cf
            )
            try:
                while True:
                    chunk = proc.stdout.read(65536)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
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
                self._serve_direct(file_path)
            except Exception:
                pass

    # ── Servicio directo de archivo (con soporte Range para el seek) ──────────────
    def _serve_direct(self, file_path: str):
        """Sirve el archivo directamente con soporte para solicitudes Range."""
        try:
            file_size = os.path.getsize(file_path)
            ext = os.path.splitext(file_path)[1].lower()
            ctype_map = {
                ".mp4": "video/mp4", ".m4v": "video/mp4",
                ".webm": "video/webm",
                ".mkv":  "video/x-matroska",
                ".avi":  "video/avi",
                ".mov":  "video/quicktime",
                ".ts":   "video/mp2t",
            }
            ctype = ctype_map.get(ext, "application/octet-stream")

            range_hdr = self.headers.get("Range", "")
            if range_hdr:
                m = re.match(r"bytes=(\d+)-(\d*)", range_hdr)
                if m:
                    start = int(m.group(1))
                    end   = int(m.group(2)) if m.group(2) else file_size - 1
                    end   = min(end, file_size - 1)
                    length = end - start + 1
                    self.send_response(206)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(length))
                    self.send_header("Accept-Ranges", "bytes")
                    self._add_cors()
                    self.end_headers()
                    with open(file_path, "rb") as f:
                        f.seek(start)
                        remaining = length
                        while remaining > 0:
                            data = f.read(min(65536, remaining))
                            if not data:
                                break
                            try:
                                self.wfile.write(data)
                            except (BrokenPipeError, OSError):
                                break
                            remaining -= len(data)
                    return

            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self._add_cors()
            self.end_headers()
            with open(file_path, "rb") as f:
                while True:
                    data = f.read(65536)
                    if not data:
                        break
                    try:
                        self.wfile.write(data)
                    except (BrokenPipeError, OSError):
                        break
        except Exception as e:
            print(f"[IPTV-HTTP] Error en serve_direct: {e}")


# ---------------------------------------------------------------------------
# Inicio / parada del servidor HTTP
# ---------------------------------------------------------------------------

def start_video_server() -> bool:
    """Lanza el servidor HTTP de vídeo en IPTV_VIDEO_PORT (idempotente)."""
    global _video_server, _video_server_thread
    if _video_server is not None:
        return True
    try:
        _video_server = HTTPServer(("127.0.0.1", IPTV_VIDEO_PORT), _IPTVVideoHandler)
        _video_server_thread = threading.Thread(
            target=_video_server.serve_forever,
            daemon=True,
            name="IPTV-HTTP-Server"
        )
        _video_server_thread.start()
        print(f"[IPTV] Servidor HTTP de vídeo iniciado en http://127.0.0.1:{IPTV_VIDEO_PORT}")
        return True
    except Exception as e:
        print(f"[IPTV] Error al iniciar servidor HTTP: {e}")
        _video_server = None
        return False


def stop_video_server():
    """Detiene el servidor HTTP de vídeo."""
    global _video_server, _video_server_thread
    if _video_server:
        _video_server.shutdown()
        _video_server = None
        _video_server_thread = None
        print("[IPTV] Servidor HTTP de vídeo detenido.")


# Inicio automático al importar el módulo
start_video_server()


# ---------------------------------------------------------------------------
# Parsing de M3U / M3U8
# ---------------------------------------------------------------------------

def _parse_m3u_content(content: str) -> list:
    channels = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            meta = line[len("#EXTINF:"):]
            name, logo, group = "", "", ""
            if "," in meta:
                attrs_part, name = meta.rsplit(",", 1)
                name = name.strip()
            else:
                attrs_part = meta
            logo_m  = re.search(r'tvg-logo="([^"]*)"',   attrs_part)
            tvgn_m  = re.search(r'tvg-name="([^"]*)"',   attrs_part)
            group_m = re.search(r'group-title="([^"]*)"', attrs_part)
            if logo_m:  logo  = logo_m.group(1)
            if tvgn_m and not name: name = tvgn_m.group(1)
            if group_m: group = group_m.group(1)
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith("#")):
                i += 1
            if i < len(lines):
                url = lines[i].strip()
                if url:
                    channels.append({"name": name or url, "url": url, "logo": logo, "group": group})
        i += 1
    return channels


def _parse_xspf_content(content: str) -> list:
    channels = []
    try:
        root = ET.fromstring(content)
        ns = {"xspf": "http://xspf.org/ns/0/"}
        tracklist = root.find("xspf:trackList", ns) or root.find("trackList")
        if tracklist is None:
            return channels
        for track in tracklist:
            loc   = track.find("{http://xspf.org/ns/0/}location") or track.find("location")
            title = track.find("{http://xspf.org/ns/0/}title")   or track.find("title")
            img   = track.find("{http://xspf.org/ns/0/}image")   or track.find("image")
            url   = loc.text.strip()   if loc   is not None and loc.text   else ""
            name  = title.text.strip() if title is not None and title.text else url
            logo  = img.text.strip()   if img   is not None and img.text   else ""
            if url:
                channels.append({"name": name, "url": url, "logo": logo, "group": ""})
    except Exception as e:
        print(f"[IPTV] Error al parsear XSPF: {e}")
    return channels


def _parse_pls_content(content: str) -> list:
    channels = []
    files, titles = {}, {}
    for line in content.splitlines():
        fm = re.match(r'^File(\d+)=(.+)$', line.strip(), re.IGNORECASE)
        tm = re.match(r'^Title(\d+)=(.+)$', line.strip(), re.IGNORECASE)
        if fm: files[fm.group(1)]  = fm.group(2).strip()
        if tm: titles[tm.group(1)] = tm.group(2).strip()
    for idx, url in files.items():
        channels.append({"name": titles.get(idx, url), "url": url, "logo": "", "group": ""})
    return channels


def parse_playlist_file(file_path: str) -> dict:
    try:
        if not os.path.exists(file_path):
            return {"success": False, "channels": [], "error": "Archivo no encontrado"}
        ext = os.path.splitext(file_path)[1].lower()
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if ext in (".m3u", ".m3u8"):
            channels = _parse_m3u_content(content)
        elif ext == ".xspf":
            channels = _parse_xspf_content(content)
        elif ext == ".pls":
            channels = _parse_pls_content(content)
        else:
            return {"success": False, "channels": [], "error": f"Formato no soportado: {ext}"}
        print(f"[IPTV] Playlist parseada: {len(channels)} canal(es)")
        return {"success": True, "channels": channels, "error": None}
    except Exception as e:
        return {"success": False, "channels": [], "error": str(e)}


def parse_playlist_url(url: str) -> dict:
    try:
        import requests
        resp = requests.get(url, headers={"User-Agent": "AP0L0/1.0"}, timeout=15)
        resp.raise_for_status()
        content = resp.text
        content_lower = content.strip().lower()
        url_lower = url.lower().split("?")[0]
        if "#extm3u" in content_lower[:1000] or "#extinf" in content_lower or url_lower.endswith(".m3u") or url_lower.endswith(".m3u8"):
            channels = _parse_m3u_content(content)
        elif "<tracklist" in content_lower or "xspf" in content_lower[:500]:
            channels = _parse_xspf_content(content)
        elif "[playlist]" in content_lower[:200]:
            channels = _parse_pls_content(content)
        else:
            channels = _parse_m3u_content(content)
        return {"success": True, "channels": channels, "error": None}
    except Exception as e:
        return {"success": False, "channels": [], "error": str(e)}


# ---------------------------------------------------------------------------
# Detección del tipo de stream
# ---------------------------------------------------------------------------

def detect_stream_type(url: str) -> str:
    u = url.lower().split("?")[0]
    if u.endswith(".m3u8") or "m3u8" in u: return "hls"
    if u.endswith(".mpd"):                  return "dash"
    if any(u.endswith(e) for e in (".mp4", ".m4v", ".webm")): return "mp4"
    if u.startswith("rtsp://") or u.startswith("rtmp://"):     return "rtsp"
    return "direct"


def get_video_stream_url(file_path: str, audio_track: int = 0) -> str:
    """Retorna la URL del stream HTTP local para el archivo de vídeo."""
    encoded = urllib.parse.quote(file_path, safe="")
    return f"http://127.0.0.1:{IPTV_VIDEO_PORT}/video?path={encoded}&audio={audio_track}"


# ===== FUNCIÓN EXPORTABLE PARA AP0L0 =====

async def iptv_play(params: dict, player=None, speak=None) -> str:
    """
    Punto de entrada para la herramienta IPTV.
    Parámetros:
        action: "play", "playlist", "open_file", "parse_url"
        path: ruta del archivo (playlist o vídeo)
        url: URL de lista M3U o stream directo
        audio_track: índice de pista de audio (para vídeos)
    """
    action = params.get("action", "").lower()
    path = params.get("path", "")
    url = params.get("url", "")
    audio_track = int(params.get("audio_track", 0))

    if action == "play":
        if not path:
            return "Se requiere una ruta de archivo para reproducir."
        ext = os.path.splitext(path)[1].lower()
        if ext in IPTV_SUPPORTED_VIDEO_EXTS:
            # Vídeo local → generar URL de streaming
            if not os.path.exists(path):
                return f"Archivo no encontrado: {path}"
            stream_url = get_video_stream_url(path, audio_track)
            # Probar información del archivo (opcional)
            info = probe_file_info(path)
            msg = f"Reproduciendo: {os.path.basename(path)}"
            if info.get("audio_tracks"):
                msg += f" | Pistas de audio: {len(info['audio_tracks'])}"
            if speak:
                speak(msg)
            if player:
                player.write_log(f"[IPTV] {msg}")
            return f"{msg}\nStream URL: {stream_url}"
        elif ext in IPTV_SUPPORTED_PLAYLIST_EXTS:
            result = parse_playlist_file(path)
            if result["success"]:
                channels = result["channels"]
                if channels:
                    msg = f"Playlist cargada: {len(channels)} canales."
                    if speak:
                        speak(msg)
                    if player:
                        player.write_log(f"[IPTV] {msg}")
                    # Mostrar primeros 5 canales en el log
                    for ch in channels[:5]:
                        player.write_log(f"  - {ch['name']} ({ch['url'][:50]}...)")
                    return msg
                else:
                    return "No se encontraron canales en la playlist."
            else:
                return f"Error al parsear playlist: {result.get('error')}"
        else:
            return f"Formato no soportado: {ext}"

    elif action == "playlist":
        if url:
            # URL remota
            result = parse_playlist_url(url)
            if result["success"]:
                channels = result["channels"]
                if channels:
                    msg = f"Playlist remota cargada: {len(channels)} canales."
                    if speak:
                        speak(msg)
                    if player:
                        player.write_log(f"[IPTV] {msg}")
                    for ch in channels[:5]:
                        player.write_log(f"  - {ch['name']} ({ch['url'][:50]}...)")
                    return msg
                else:
                    return "No se encontraron canales en la URL."
            else:
                return f"Error al parsear URL: {result.get('error')}"
        else:
            return "Se requiere una URL para cargar una playlist remota."

    elif action == "parse_url":
        # Similar a playlist pero devuelve la lista completa en JSON (para el frontend)
        if not url:
            return "Se requiere una URL."
        result = parse_playlist_url(url)
        if result["success"]:
            return json.dumps({"success": True, "channels": result["channels"]})
        else:
            return json.dumps({"success": False, "error": result.get("error")})

    else:
        return f"Acción '{action}' no soportada. Usa: play, playlist, parse_url"