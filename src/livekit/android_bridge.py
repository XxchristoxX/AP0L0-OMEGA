# src/livekit/android_bridge.py
"""
Puente para conectar con la app Android vía WebSocket.
Permite recibir comandos y audio desde un dispositivo móvil.
"""

import asyncio
import json
import threading
import base64
import logging

logger = logging.getLogger("AndroidBridge")

class AndroidBridge:
    """
    Servidor WebSocket simple que recibe comandos y audio desde Android.
    """

    def __init__(self, host="0.0.0.0", port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        self._running = False
        self._server_task = None
        self._command_callback = None  # función que recibe (comando: str) -> respuesta: str
        self._audio_callback = None    # función que recibe (audio_bytes: bytes)

    def set_command_callback(self, callback):
        """Establece la función que manejará los comandos desde Android."""
        self._command_callback = callback

    def set_audio_callback(self, callback):
        """Establece la función que manejará el audio desde Android."""
        self._audio_callback = callback

    async def start(self):
        """Inicia el servidor WebSocket en segundo plano."""
        import websockets
        self._running = True
        async with websockets.serve(self._handler, self.host, self.port):
            logger.info(f"AndroidBridge escuchando en ws://{self.host}:{self.port}")
            await asyncio.Future()  # Ejecuta indefinidamente

    async def _handler(self, websocket, path):
        """Maneja una conexión WebSocket entrante."""
        self.clients.add(websocket)
        logger.info(f"Cliente Android conectado: {websocket.remote_address}")

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "command":
                        command = data.get("command", "")
                        if self._command_callback:
                            result = self._command_callback(command)
                            await websocket.send(json.dumps({
                                "type": "response",
                                "result": result
                            }))
                        else:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": "No hay callback para comandos"
                            }))

                    elif msg_type == "audio":
                        audio_b64 = data.get("audio", "")
                        if audio_b64 and self._audio_callback:
                            audio_bytes = base64.b64decode(audio_b64)
                            self._audio_callback(audio_bytes)
                        else:
                            logger.warning("Audio recibido sin callback o vacío")

                    elif msg_type == "ping":
                        await websocket.send(json.dumps({"type": "pong"}))

                    else:
                        logger.warning(f"Tipo de mensaje desconocido: {msg_type}")

                except json.JSONDecodeError as e:
                    logger.error(f"JSON inválido: {e}")
                except Exception as e:
                    logger.error(f"Error procesando mensaje: {e}")

        except Exception as e:
            logger.error(f"Error en handler: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info("Cliente Android desconectado")

    async def broadcast(self, message: str):
        """Envía un mensaje a todos los clientes conectados."""
        if not self.clients:
            return
        payload = json.dumps({"type": "message", "text": message})
        for ws in self.clients.copy():
            try:
                await ws.send(payload)
            except Exception as e:
                logger.warning(f"No se pudo enviar a un cliente: {e}")

    async def send_audio(self, audio_bytes: bytes):
        """Envía audio a todos los clientes conectados (ej. para reproducción en Android)."""
        if not self.clients:
            return
        audio_b64 = base64.b64encode(audio_bytes).decode()
        payload = json.dumps({"type": "audio", "audio": audio_b64})
        for ws in self.clients.copy():
            try:
                await ws.send(payload)
            except Exception as e:
                logger.warning(f"No se pudo enviar audio: {e}")

    def start_in_thread(self):
        """Inicia el servidor en un hilo separado para no bloquear la UI."""
        def _run():
            asyncio.run(self.start())
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return thread

    def stop(self):
        """Detiene el servidor."""
        self._running = False
        if self._server_task:
            self._server_task.cancel()