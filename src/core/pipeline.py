# src/core/pipeline.py
"""
Pipeline principal de JARVIS (versión adaptada a tu sistema).
Orquesta: STT → LLM → TTS usando los módulos que ya tienes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union, BinaryIO, List, Dict

# Importaciones de tus módulos existentes
from src.core.llm import LLM
from src.core.tts import edge_speak_base
from src.stt.recognition import record_voice as record_voice_google
from src.stt.vosk_stt import record_voice as record_voice_vosk
from src.stt.whisper_stt import transcribe_audio_local

log = logging.getLogger("jarvis.pipeline")

Message = Dict[str, str]


@dataclass
class PipelineResult:
    transcript: str       # Lo que dijo el usuario (STT)
    reply_text: str       # Respuesta del LLM
    reply_audio: bytes    # Audio TTS (bytes)
    reply_mime: str       # MIME type del audio
    provider: str = ""    # LLM que respondió
    stt_engine: str = ""  # Motor STT usado


def run_pipeline(
    audio_input: Optional[Union[str, Path, bytes, BinaryIO]] = None,
    stt_engine: str = "google",   # "google", "vosk", "whisper"
    extra_context: Optional[str] = None,
    history: Optional[List[Message]] = None,
    session_id: str = "",
) -> PipelineResult:
    """
    Pipeline completo (bloqueante):
    1. STT (elige motor: google, vosk, whisper)
    2. LLM (usa LLM unificado)
    3. TTS (usa edge_tts)
    """
    # ── 1. STT ──────────────────────────────────────────────────────────────
    transcript = ""

    if audio_input is None:
        # Modo micrófono (grabar desde el micrófono)
        if stt_engine == "google":
            transcript = record_voice_google(prompt="🎙 Escuchando...", timeout=5, phrase_time_limit=10) or ""
        elif stt_engine == "vosk":
            transcript = record_voice_vosk(prompt="🎙 Escuchando...") or ""
        else:
            log.error(f"[Pipeline] Motor STT '{stt_engine}' no soportado para micrófono.")
    else:
        # Audio ya cargado (archivo o bytes) → usar Whisper (más robusto)
        stt_engine = "whisper"
        transcript = transcribe_audio_local(audio_input)

    if not transcript:
        msg = "No escuché nada claro. ¿Puedes intentarlo de nuevo?"
        log.info("[Pipeline] Transcripción vacía — respondiendo genérico.")
        # Generar TTS genérico (usando edge_speak_base)
        audio_bytes = _synthesize_tts_sync(msg)
        return PipelineResult("", msg, audio_bytes, "audio/mpeg", "fallback", stt_engine)

    # ── 2. LLM ──────────────────────────────────────────────────────────────
    llm = LLM()
    system_prompt = extra_context or "Eres JARVIS, un asistente útil y conciso. Responde en el idioma del usuario."
    reply_text, provider = llm.generate(transcript, system_instruction=system_prompt)

    if not reply_text:
        reply_text = "Lo siento, no pude procesar tu solicitud en este momento."
        provider = "fallback"

    log.info(f"[Pipeline] LLM ({provider}): '{reply_text[:60]}...'")

    # ── 3. TTS ──────────────────────────────────────────────────────────────
    audio_bytes = _synthesize_tts_sync(reply_text)
    log.info(f"[Pipeline] TTS: {len(audio_bytes)} bytes generados")

    return PipelineResult(
        transcript=transcript,
        reply_text=reply_text,
        reply_audio=audio_bytes,
        reply_mime="audio/mpeg",
        provider=provider,
        stt_engine=stt_engine,
    )


def _synthesize_tts_sync(text: str) -> bytes:
    """
    Sintetiza TTS usando edge-tts (síncrono) y retorna bytes.
    """
    import io
    import asyncio
    import edge_tts

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        communicate = edge_tts.Communicate(text, "en-US-AndrewMultilingualNeural")
        audio_buffer = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.extend(chunk["data"])
        return bytes(audio_buffer)
    except Exception as e:
        log.error(f"[Pipeline] TTS error: {e}")
        return b""
    finally:
        loop.close()