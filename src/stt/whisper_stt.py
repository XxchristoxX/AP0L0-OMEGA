# src/stt/whisper_stt.py
"""
STT con faster-whisper (offline, local).
Requiere: pip install faster-whisper
También necesita ffmpeg instalado en el sistema.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Union, BinaryIO, IO

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.core.config import get_api_key

log = logging.getLogger("jarvis.whisper_stt")

# ── Configuración por defecto (puedes sobrescribir en api_keys.json) ──
WHISPER_MODEL = "base"          # "tiny", "base", "small", "medium", "large"
WHISPER_COMPUTE_TYPE = "int8"   # "int8", "float16", "float32"
WHISPER_LANGUAGE = "es"         # "es", "en", "auto", etc.

# ── Carga del modelo (singleton) ──────────────────────────────────────────
_WHISPER = None

def _load_whisper():
    global _WHISPER
    if _WHISPER is not None:
        return _WHISPER
    try:
        from faster_whisper import WhisperModel
        log.info(f"[WhisperSTT] Cargando modelo '{WHISPER_MODEL}' compute='{WHISPER_COMPUTE_TYPE}'...")
        _WHISPER = WhisperModel(
            WHISPER_MODEL,
            device="auto",
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        log.info("[WhisperSTT] Modelo listo.")
    except ImportError:
        log.error("[WhisperSTT] faster-whisper no instalado. Ejecuta: pip install faster-whisper")
        _WHISPER = None
    except Exception as exc:
        log.error(f"[WhisperSTT] Error cargando modelo: {exc}")
        _WHISPER = None
    return _WHISPER

def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None

def _convert_to_wav_16k(in_path: Path, out_path: Path) -> None:
    if not have_ffmpeg():
        raise RuntimeError("ffmpeg no encontrado. Instálalo (ej: brew install ffmpeg o apt install ffmpeg)")
    cmd = [
        "ffmpeg", "-y", "-i", str(in_path),
        "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="ignore"))

def transcribe_audio_local(
    audio_input: Union[str, Path, bytes, BinaryIO, IO],
    language: str = None,
) -> str:
    """
    Transcribe audio a texto usando faster-whisper.
    Acepta: ruta (str/Path), bytes, o file-like object.
    Retorna string con el texto transcrito (vacío si falla o no hay voz).
    """
    model = _load_whisper()
    if model is None:
        log.warning("[WhisperSTT] Modelo no disponible.")
        return ""

    lang = language or WHISPER_LANGUAGE
    if lang == "auto":
        lang = None

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Normalizar entrada a Path
        if isinstance(audio_input, (str, Path)):
            src = Path(audio_input)
        elif isinstance(audio_input, bytes):
            src = tmp / "input.webm"
            src.write_bytes(audio_input)
        else:
            # file-like
            src = tmp / "input.webm"
            src.write_bytes(audio_input.read())

        # Convertir a WAV 16k si es posible
        wav = tmp / "input.wav"
        try:
            _convert_to_wav_16k(src, wav)
            audio_path = str(wav)
        except Exception as e:
            log.warning(f"[WhisperSTT] ffmpeg no disponible ({e}), usando archivo original")
            audio_path = str(src)

        log.info(f"[WhisperSTT] Transcribiendo ({lang or 'auto'})...")
        try:
            segments, info = model.transcribe(audio_path, language=lang, vad_filter=True)
            text = "".join(seg.text for seg in segments).strip()
            log.info(f"[WhisperSTT] Texto: '{text[:80]}...' " if len(text) > 80 else f"[WhisperSTT] '{text}'")
            return text
        except Exception as exc:
            log.error(f"[WhisperSTT] Error en transcripción: {exc}")
            return ""