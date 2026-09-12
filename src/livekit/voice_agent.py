# src/livekit/voice_agent.py
"""
Agente de voz para LiveKit.
Permite comunicación bidireccional con la app Android en tiempo real.
"""

import asyncio
import logging
from typing import Optional, Callable

try:
    from livekit import rtc
    from livekit.agents import Agent, AutoSubscribe, JobContext, JobProcess
    LIVEKIT_AVAILABLE = True
except ImportError:
    LIVEKIT_AVAILABLE = False
    print("[LiveKit] No instalado. Ejecuta: pip install livekit livekit-agents")

logger = logging.getLogger("LiveKitVoiceAgent")

class VoiceAgent:
    """
    Agente de voz para LiveKit.
    """

    def __init__(
        self,
        url: str,
        token: str,
        room_name: str = "apolo_room",
        identity: str = "apolo_agent",
        on_audio_received: Optional[Callable] = None,
    ):
        if not LIVEKIT_AVAILABLE:
            raise ImportError("LiveKit no está instalado.")

        self.url = url
        self.token = token
        self.room_name = room_name
        self.identity = identity
        self.on_audio_received = on_audio_received
        self.room = None
        self.audio_source = None
        self.audio_track = None
        self._running = False

    async def connect(self) -> bool:
        """Conecta al servidor LiveKit."""
        try:
            self.room = rtc.Room()
            await self.room.connect(self.url, self.token)

            # Crear fuente de audio
            self.audio_source = rtc.AudioSource(
                sample_rate=16000,
                num_channels=1,
            )
            self.audio_track = rtc.LocalAudioTrack.create_audio_track(
                "apolo_audio",
                self.audio_source,
            )

            # Publicar track
            await self.room.local_participant.publish_track(
                self.audio_track,
                rtc.TrackPublishOptions(
                    name="apolo_audio",
                    source=rtc.TrackSource.SOURCE_MICROPHONE,
                )
            )

            # Suscribirse a audio de otros participantes
            @self.room.on("track_subscribed")
            def on_track_subscribed(track, publication, participant):
                if track.kind == rtc.TrackKind.KIND_AUDIO:
                    logger.info(f"Audio suscrito de {participant.identity}")
                    self._listen_to_track(track)

            self._running = True
            logger.info(f"Conectado a {self.url} (room: {self.room_name})")
            return True

        except Exception as e:
            logger.error(f"Error de conexión: {e}")
            return False

    def _listen_to_track(self, track):
        """Escucha audio entrante."""
        @track.on("frame")
        def on_frame(frame):
            if self.on_audio_received and self._running:
                audio_data = frame.data.tobytes()
                self.on_audio_received(audio_data)

    async def send_audio(self, audio_data: bytes):
        """Envía audio al servidor."""
        if not self.audio_source or not self._running:
            return
        try:
            frame = rtc.AudioFrame(
                data=audio_data,
                sample_rate=16000,
                num_channels=1,
                samples_per_channel=len(audio_data) // 2,
            )
            await self.audio_source.capture_frame(frame)
        except Exception as e:
            logger.error(f"Error al enviar audio: {e}")

    async def disconnect(self):
        """Desconecta del servidor."""
        self._running = False
        if self.room:
            await self.room.disconnect()
            logger.info("Desconectado.")