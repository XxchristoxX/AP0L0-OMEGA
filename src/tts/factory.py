# src/tts/factory.py
"""
Fábrica unificada de motores de Síntesis de Voz (TTS).
Soporta: EdgeTTS, Kokoro, pyttsx3, Gemini TTS.
"""

import os
import asyncio
import tempfile
from typing import Optional, Callable, Any
from pathlib import Path

from src.core.config import get_config


# ──────────────────────────────────────────────────────────────
# INTERFAZ BASE
# ──────────────────────────────────────────────────────────────

class TTSEngine:
    """Interfaz base para todos los motores TTS."""

    def speak(self, text: str) -> bytes:
        """Sintetiza texto a audio. Retorna bytes del audio."""
        raise NotImplementedError

    def speak_to_file(self, text: str, file_path: str) -> bool:
        """Sintetiza texto y guarda en archivo."""
        raise NotImplementedError

    def is_available(self) -> bool:
        """Verifica si el motor está disponible."""
        return True

    def get_info(self) -> dict:
        """Retorna información del motor."""
        return {"name": self.__class__.__name__, "available": self.is_available()}


# ──────────────────────────────────────────────────────────────
# MOTOR: EDGE TTS (Cloud, gratuito)
# ──────────────────────────────────────────────────────────────

class EdgeTTSEngine(TTSEngine):
    """Motor Edge TTS de Microsoft (cloud, gratuito)."""

    def __init__(self, voice: str = "es-ES-ElviraNeural", rate: str = "+10%", pitch: str = "-5Hz"):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self._available = False
        self._check_available()

    def _check_available(self):
        try:
            import edge_tts
            self._edge_tts = edge_tts
            self._available = True
        except ImportError:
            print("[TTS] edge-tts no instalado. Ejecuta: pip install edge-tts")
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def speak(self, text: str) -> bytes:
        if not self.is_available():
            return b""
        try:
            communicate = self._edge_tts.Communicate(text, self.voice, rate=self.rate, pitch=self.pitch)
            audio_data = bytearray()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            async def _synth():
                nonlocal audio_data
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_data.extend(chunk["data"])
            loop.run_until_complete(_synth())
            loop.close()
            return bytes(audio_data)
        except Exception as e:
            print(f"[TTS] Error en EdgeTTS: {e}")
            return b""

    def speak_to_file(self, text: str, file_path: str) -> bool:
        if not self.is_available():
            return False
        try:
            communicate = self._edge_tts.Communicate(text, self.voice, rate=self.rate, pitch=self.pitch)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            async def _synth():
                await communicate.save(file_path)
            loop.run_until_complete(_synth())
            loop.close()
            return os.path.exists(file_path)
        except Exception as e:
            print(f"[TTS] Error en EdgeTTS archivo: {e}")
            return False

    def get_info(self) -> dict:
        return {
            "name": "EdgeTTS",
            "available": self.is_available(),
            "voice": self.voice,
            "type": "cloud"
        }


# ──────────────────────────────────────────────────────────────
# MOTOR: KOKORO (Offline, local)
# ──────────────────────────────────────────────────────────────

class KokoroTTSEngine(TTSEngine):
    """Motor Kokoro TTS (offline, local)."""

    def __init__(self, voice: str = "af_heart", speed: float = 1.0):
        self.voice = voice
        self.speed = speed
        self._model = None
        self._available = False
        self._load_model()

    def _load_model(self):
        try:
            from kokoro_onnx import Kokoro
            model_dir = Path("kokoro_model")
            model_dir.mkdir(exist_ok=True)
            onnx_path = model_dir / "kokoro-v1.0.onnx"
            voices_path = model_dir / "voices-v1.0.bin"

            # Descargar modelos si no existen
            if not onnx_path.exists():
                import urllib.request
                print("[TTS] Descargando modelo Kokoro (~300MB)...")
                urllib.request.urlretrieve(
                    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
                    onnx_path
                )
            if not voices_path.exists():
                import urllib.request
                print("[TTS] Descargando voces Kokoro...")
                urllib.request.urlretrieve(
                    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
                    voices_path
                )

            self._model = Kokoro(str(onnx_path), str(voices_path))
            self._available = True
            print(f"[TTS] Kokoro cargado (voz: {self.voice})")
        except ImportError:
            print("[TTS] kokoro-onnx no instalado. Ejecuta: pip install kokoro-onnx")
            self._available = False
        except Exception as e:
            print(f"[TTS] Error cargando Kokoro: {e}")
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def speak(self, text: str) -> bytes:
        if not self.is_available():
            return b""
        try:
            import soundfile as sf
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                samples, sample_rate = self._model.create(text, voice=self.voice, speed=self.speed)
                sf.write(f.name, samples, sample_rate)
                with open(f.name, "rb") as audio_f:
                    audio_data = audio_f.read()
                os.unlink(f.name)
                return audio_data
        except Exception as e:
            print(f"[TTS] Error en Kokoro: {e}")
            return b""

    def speak_to_file(self, text: str, file_path: str) -> bool:
        if not self.is_available():
            return False
        try:
            import soundfile as sf
            samples, sample_rate = self._model.create(text, voice=self.voice, speed=self.speed)
            sf.write(file_path, samples, sample_rate)
            return os.path.exists(file_path)
        except Exception as e:
            print(f"[TTS] Error en Kokoro archivo: {e}")
            return False

    def get_info(self) -> dict:
        return {
            "name": "Kokoro",
            "available": self.is_available(),
            "voice": self.voice,
            "speed": self.speed,
            "type": "offline"
        }


# ──────────────────────────────────────────────────────────────
# MOTOR: PYTTSX3 (Offline, local)
# ──────────────────────────────────────────────────────────────

class Pyttsx3Engine(TTSEngine):
    """Motor pyttsx3 (offline, local)."""

    def __init__(self, voice_id: Optional[str] = None, rate: int = 175, volume: float = 1.0):
        self.voice_id = voice_id
        self.rate = rate
        self.volume = volume
        self._engine = None
        self._load_engine()

    def _load_engine(self):
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            if self.voice_id:
                self._engine.setProperty('voice', self.voice_id)
            self._engine.setProperty('rate', self.rate)
            self._engine.setProperty('volume', self.volume)
            print("[TTS] pyttsx3 cargado")
        except ImportError:
            print("[TTS] pyttsx3 no instalado. Ejecuta: pip install pyttsx3")
            self._engine = None

    def is_available(self) -> bool:
        return self._engine is not None

    def speak(self, text: str) -> bytes:
        if not self.is_available():
            return b""
        try:
            import tempfile
            import wave
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                self._engine.save_to_file(text, f.name)
                self._engine.runAndWait()
                with open(f.name, "rb") as audio_f:
                    audio_data = audio_f.read()
                os.unlink(f.name)
                return audio_data
        except Exception as e:
            print(f"[TTS] Error en pyttsx3: {e}")
            return b""

    def speak_to_file(self, text: str, file_path: str) -> bool:
        if not self.is_available():
            return False
        try:
            self._engine.save_to_file(text, file_path)
            self._engine.runAndWait()
            return os.path.exists(file_path)
        except Exception as e:
            print(f"[TTS] Error en pyttsx3 archivo: {e}")
            return False

    def get_info(self) -> dict:
        return {
            "name": "pyttsx3",
            "available": self.is_available(),
            "rate": self.rate,
            "volume": self.volume,
            "type": "offline"
        }


# ──────────────────────────────────────────────────────────────
# MOTOR: GEMINI TTS (Cloud)
# ──────────────────────────────────────────────────────────────

class GeminiTTSEngine(TTSEngine):
    """Motor Gemini TTS (cloud, requiere API key)."""

    def __init__(self, voice: str = "Charon", model: str = "gemini-2.5-flash-preview-tts"):
        self.voice = voice
        self.model = model
        self._client = None
        self._load_client()

    def _load_client(self):
        try:
            from google import genai
            api_key = get_config().get("gemini_api_key", "")
            if api_key:
                self._client = genai.Client(api_key=api_key)
                print("[TTS] Gemini TTS inicializado")
            else:
                print("[TTS] Gemini API key no configurada")
                self._client = None
        except ImportError:
            print("[TTS] google-genai no instalado. Ejecuta: pip install google-genai")
            self._client = None

    def is_available(self) -> bool:
        return self._client is not None

    def speak(self, text: str) -> bytes:
        if not self.is_available():
            return b""
        try:
            from google.genai import types
            speech_config = types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice)
                )
            )
            response = self._client.models.generate_content(
                model=self.model,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=speech_config,
                )
            )
            if response.candidates:
                audio_data = response.candidates[0].content.parts[0].inline_data.data
                return audio_data
            return b""
        except Exception as e:
            print(f"[TTS] Error en Gemini TTS: {e}")
            return b""

    def speak_to_file(self, text: str, file_path: str) -> bool:
        audio_data = self.speak(text)
        if audio_data:
            with open(file_path, "wb") as f:
                f.write(audio_data)
            return True
        return False

    def get_info(self) -> dict:
        return {
            "name": "Gemini TTS",
            "available": self.is_available(),
            "voice": self.voice,
            "model": self.model,
            "type": "cloud"
        }


# ──────────────────────────────────────────────────────────────
# FÁBRICA PRINCIPAL
# ──────────────────────────────────────────────────────────────

def create_tts_engine(engine_name: str = None, **kwargs) -> TTSEngine:
    """
    Crea un motor TTS según el nombre especificado.

    Args:
        engine_name: "edgetts", "kokoro", "pyttsx3", "gemini"
        **kwargs: Parámetros específicos del motor

    Returns:
        Instancia de TTSEngine
    """
    if engine_name is None:
        engine_name = get_config().preferred_tts

    engine_name = engine_name.lower().strip()

    if engine_name == "edgetts":
        return EdgeTTSEngine(**kwargs)
    elif engine_name == "kokoro":
        return KokoroTTSEngine(**kwargs)
    elif engine_name == "pyttsx3":
        return Pyttsx3Engine(**kwargs)
    elif engine_name == "gemini":
        return GeminiTTSEngine(**kwargs)
    else:
        # Fallback a EdgeTTS
        print(f"[TTS] Motor '{engine_name}' no soportado, usando EdgeTTS")
        return EdgeTTSEngine(**kwargs)


def get_available_tts_engines() -> list:
    """Retorna la lista de motores TTS disponibles."""
    engines = []
    for name, cls in [
        ("edgetts", EdgeTTSEngine),
        ("kokoro", KokoroTTSEngine),
        ("pyttsx3", Pyttsx3Engine),
        ("gemini", GeminiTTSEngine),
    ]:
        try:
            engine = cls()
            if engine.is_available():
                engines.append(engine.get_info())
        except Exception:
            pass
    return engines


def synthesize_speech(
    text: str,
    engine: str = None,
    **kwargs
) -> bytes:
    """
    Función de conveniencia para sintetizar voz.

    Args:
        text: Texto a sintetizar
        engine: Nombre del motor a usar
        **kwargs: Parámetros adicionales

    Returns:
        Datos de audio
    """
    tts = create_tts_engine(engine, **kwargs)
    return tts.speak(text)


def synthesize_speech_to_file(
    text: str,
    file_path: str,
    engine: str = None,
    **kwargs
) -> bool:
    """
    Función de conveniencia para sintetizar voz y guardar en archivo.

    Args:
        text: Texto a sintetizar
        file_path: Ruta del archivo de salida
        engine: Nombre del motor a usar
        **kwargs: Parámetros adicionales

    Returns:
        True si se guardó correctamente
    """
    tts = create_tts_engine(engine, **kwargs)
    return tts.speak_to_file(text, file_path)