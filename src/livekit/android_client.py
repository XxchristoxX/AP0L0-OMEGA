# src/livekit/android_client.py
"""
Cliente de prueba para Android Bridge.
Se conecta al WebSocket del bridge, envía comandos y simula audio.
Útil para probar la conexión sin necesidad de una app Android real.
"""

import asyncio
import json
import base64
import websockets
import numpy as np
import sounddevice as sd
import threading
import time
from typing import Optional, Callable

class AndroidClient:
    """
    Cliente que se conecta al AndroidBridge vía WebSocket.
    Permite enviar comandos, recibir respuestas y transmitir audio simulado.
    """

    def __init__(self, url: str = "ws://localhost:8765"):
        self.url = url
        self.websocket = None
        self._running = False
        self._receive_thread = None
        self._on_message_callback: Optional[Callable] = None

    def set_message_callback(self, callback: Callable):
        """Callback que se ejecuta al recibir un mensaje del bridge."""
        self._on_message_callback = callback

    async def connect(self):
        """Conecta al servidor WebSocket."""
        try:
            self.websocket = await websockets.connect(self.url)
            print(f"[AndroidClient] Conectado a {self.url}")
            self._running = True
            # Iniciar hilo de recepción
            self._receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._receive_thread.start()
            return True
        except Exception as e:
            print(f"[AndroidClient] Error de conexión: {e}")
            return False

    async def disconnect(self):
        """Desconecta del servidor."""
        self._running = False
        if self.websocket:
            await self.websocket.close()
            print("[AndroidClient] Desconectado.")

    def _receive_loop(self):
        """Bucle de recepción de mensajes (ejecutado en hilo)."""
        asyncio.run(self._async_receive())

    async def _async_receive(self):
        """Recibe mensajes del servidor de forma asíncrona."""
        while self._running and self.websocket:
            try:
                message = await self.websocket.recv()
                data = json.loads(message)
                if self._on_message_callback:
                    self._on_message_callback(data)
                else:
                    print(f"[AndroidClient] Recibido: {data}")
            except websockets.ConnectionClosed:
                print("[AndroidClient] Conexión cerrada.")
                break
            except Exception as e:
                print(f"[AndroidClient] Error en recepción: {e}")
                break

    async def send_command(self, command: str) -> Optional[str]:
        """Envía un comando al bridge y espera la respuesta."""
        if not self.websocket:
            return None
        try:
            await self.websocket.send(json.dumps({
                "type": "command",
                "command": command
            }))
            # Esperar respuesta (el callback la manejará, pero aquí esperamos síncrono)
            # Esto es simplificado; en producción usarías una cola de respuestas.
            return "Comando enviado"
        except Exception as e:
            print(f"[AndroidClient] Error enviando comando: {e}")
            return None

    async def send_audio(self, audio_bytes: bytes):
        """Envía audio codificado en base64 al bridge."""
        if not self.websocket:
            return
        try:
            audio_b64 = base64.b64encode(audio_bytes).decode()
            await self.websocket.send(json.dumps({
                "type": "audio",
                "audio": audio_b64
            }))
            print(f"[AndroidClient] Audio enviado: {len(audio_bytes)} bytes")
        except Exception as e:
            print(f"[AndroidClient] Error enviando audio: {e}")

    def send_command_sync(self, command: str) -> Optional[str]:
        """Versión síncrona de send_command (usa asyncio.run)."""
        return asyncio.run(self.send_command(command))

    def send_audio_sync(self, audio_bytes: bytes):
        """Versión síncrona de send_audio."""
        asyncio.run(self.send_audio(audio_bytes))

    # ---- Funciones para simular audio ----
    @staticmethod
    def generate_test_audio(duration: float = 2.0, sample_rate: int = 16000) -> bytes:
        """Genera un tono de prueba (beep) y lo devuelve como bytes PCM."""
        t = np.linspace(0, duration, int(sample_rate * duration))
        tone = 0.5 * np.sin(2 * np.pi * 440 * t)  # 440 Hz
        audio = (tone * 32767).astype(np.int16)
        return audio.tobytes()

    @staticmethod
    def record_audio(duration: float = 2.0, sample_rate: int = 16000) -> bytes:
        """Graba audio desde el micrófono y devuelve bytes PCM."""
        print(f"[AndroidClient] Grabando {duration}s...")
        recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
        sd.wait()
        return recording.tobytes()


# ===== FUNCIÓN PARA USAR COMO HERRAMIENTA =====
def android_client_tool(parameters: dict = None, player=None, speak=None) -> str:
    """
    Herramienta que permite interactuar con el bridge Android desde el asistente.
    """
    action = parameters.get("action", "connect") if parameters else "connect"

    if action == "connect":
        if not hasattr(android_client_tool, "_client"):
            client = AndroidClient()
            success = asyncio.run(client.connect())
            if success:
                android_client_tool._client = client
                android_client_tool._client.set_message_callback(
                    lambda msg: player.write_log(f"[Android] {msg}") if player else None
                )
                return "Cliente Android conectado al bridge."
            else:
                return "No se pudo conectar al bridge."
        else:
            return "El cliente Android ya está conectado."

    elif action == "disconnect":
        if hasattr(android_client_tool, "_client") and android_client_tool._client:
            asyncio.run(android_client_tool._client.disconnect())
            del android_client_tool._client
            return "Cliente Android desconectado."
        else:
            return "No hay cliente activo."

    elif action == "send_command":
        command = parameters.get("command", "")
        if not command:
            return "No se especificó ningún comando."
        if hasattr(android_client_tool, "_client") and android_client_tool._client:
            result = android_client_tool._client.send_command_sync(command)
            return f"Comando '{command}' enviado. Respuesta: {result}"
        else:
            return "Cliente no conectado."

    elif action == "send_audio":
        if hasattr(android_client_tool, "_client") and android_client_tool._client:
            # Generar audio de prueba
            audio = AndroidClient.generate_test_audio(1.0)
            android_client_tool._client.send_audio_sync(audio)
            return "Audio de prueba enviado al bridge."
        else:
            return "Cliente no conectado."

    else:
        return f"Acción '{action}' no soportada. Usa: connect, disconnect, send_command, send_audio"