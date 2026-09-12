import os
import subprocess
import sys
from pathlib import Path

class YouTubeDownloader:
    """Servicio para descargar videos de YouTube usando yt-dlp."""

    def __init__(self):
        self.download_path = Path.home() / "Downloads" / "YouTube"
        self.download_path.mkdir(parents=True, exist_ok=True)
        print(f"[YouTubeDownloader] Descargas guardadas en: {self.download_path}")

    def _check_ytdlp(self):
        """Verifica si yt-dlp está instalado."""
        try:
            subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def download(self, url: str, quality: str = "best", audio_only: bool = False) -> str:
        """
        Descarga un video de YouTube.
        
        Args:
            url (str): URL del video.
            quality (str): 'best', '720p', '1080p', 'audio'.
            audio_only (bool): Si solo descarga audio (MP3).
        """
        if not url or "youtube.com" not in url and "youtu.be" not in url:
            return "URL de YouTube no válida."

        if not self._check_ytdlp():
            return "yt-dlp no está instalado. Ejecuta: pip install yt-dlp"

        try:
            # Formato de salida
            filename_template = "%(title)s.%(ext)s"
            
            if audio_only:
                cmd = [
                    "yt-dlp",
                    "-x",  # Extraer audio
                    "--audio-format", "mp3",
                    "--audio-quality", "0",
                    "-o", str(self.download_path / filename_template),
                    url
                ]
            else:
                # Calidad
                format_str = "bestvideo[height<=1080]+bestaudio/best" if "1080" in quality else "best"
                if quality == "720p":
                    format_str = "bestvideo[height<=720]+bestaudio/best"
                elif quality == "best":
                    format_str = "bestvideo+bestaudio/best"
                
                cmd = [
                    "yt-dlp",
                    "-f", format_str,
                    "--merge-output-format", "mp4",
                    "-o", str(self.download_path / filename_template),
                    url
                ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                return f"Error al descargar: {error_msg[:200]}"

            # Encontrar el archivo descargado
            files = list(self.download_path.glob("*"))
            latest_file = max(files, key=lambda f: f.stat().st_ctime) if files else None

            if latest_file:
                return f"Descarga completada: {latest_file.name} (Guardado en {self.download_path})"
            else:
                return "Descarga completada, pero no se encontró el archivo."

        except subprocess.TimeoutExpired:
            return "La descarga excedió el tiempo límite (5 minutos)."
        except Exception as e:
            return f"Error en la descarga: {str(e)}"