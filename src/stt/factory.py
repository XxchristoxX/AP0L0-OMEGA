# src/stt/factory.py
"""
Fábrica unificada de motores de Reconocimiento de Voz (STT).
Soporta: Vosk, Whisper, Google Speech, Nemotron ASR.
"""

import os
from typing import Optional, Callable, Any
from pathlib import Path

from src.core.config import get_config


# ──────────────────────────────────────────────────────────────
# INTERFAZ BASE
# ──────────────────────────────────────────────────────────────

class STTEngine:
    """Interfaz base para todos los motores STT."""

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """Transcribe audio a texto."""
        raise NotImplementedError

    def transcribe_file(self, file_path: str) -> str:
        """Transcribe un archivo de audio."""
        raise NotImplementedError

    def is_available(self) -> bool:
        """Verifica si el motor está disponible."""
        return True

    def get_info(self) -> dict:
        """Retorna información del motor."""
        return {"name": self.__class__.__name__, "available": self.is_available()}


# ──────────────────────────────────────────────────────────────
# MOTOR: VOSK (Offline)
# ──────────────────────────────────────────────────────────────

class VoskSTT(STTEngine):
    """Motor Vosk para reconocimiento de voz offline."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or get_config().vosk_model
        self._model = None
        self._recognizer = None
        self._load_model()

    def _load_model(self):
        try:
            import vosk
            # Verificar que el modelo existe
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Modelo Vosk no encontrado: {self.model_path}")
            self._model = vosk.Model(self.model_path)
            self._recognizer = vosk.KaldiRecognizer(self._model, 16000)
            print(f"[STT] Vosk modelo cargado desde: {self.model_path}")
        except ImportError:
            print("[STT] Vosk no instalado. Ejecuta: pip install vosk")
            self._model = None
        except Exception as e:
            print(f"[STT] Error cargando Vosk: {e}")
            self._model = None

    def is_available(self) -> bool:
        return self._model is not None

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        if not self.is_available():
            return ""
        try:
            import json
            if self._recognizer.AcceptWaveform(audio_data):
                result = json.loads(self._recognizer.Result())
                return result.get("text", "")
            return ""
        except Exception as e:
            print(f"[STT] Error en Vosk: {e}")
            return ""

    def transcribe_file(self, file_path: str) -> str:
        if not self.is_available():
            return ""
        try:
            import wave
            import json
            wf = wave.open(file_path, "rb")
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != 16000:
                wf.close()
                return "El archivo debe ser WAV mono PCM a 16kHz"
            rec = vosk.KaldiRecognizer(self._model, wf.getframerate())
            text = ""
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text += result.get("text", "") + " "
            wf.close()
            return text.strip()
        except Exception as e:
            print(f"[STT] Error en Vosk archivo: {e}")
            return ""

    def get_info(self) -> dict:
        return {
            "name": "Vosk",
            "available": self.is_available(),
            "model_path": self.model_path,
            "type": "offline"
        }


# ──────────────────────────────────────────────────────────────
# MOTOR: WHISPER (Offline, GPU/CPU)
# ──────────────────────────────────────────────────────────────

class WhisperSTT(STTEngine):
    """Motor Whisper para reconocimiento de voz offline (faster-whisper)."""

    def __init__(self, model_name: str = "base", language: str = "es"):
        self.model_name = model_name
        self.language = language
        self._model = None
        self._load_model()

    def _load_model(self):
        try:
            from faster_whisper import WhisperModel
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            self._model = WhisperModel(self.model_name, device=device, compute_type=compute_type)
            print(f"[STT] Whisper cargado (modelo: {self.model_name}, device: {device})")
        except ImportError:
            print("[STT] faster-whisper no instalado. Ejecuta: pip install faster-whisper")
            self._model = None
        except Exception as e:
            print(f"[STT] Error cargando Whisper: {e}")
            self._model = None

    def is_available(self) -> bool:
        return self._model is not None

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        if not self.is_available():
            return ""
        try:
            import numpy as np
            audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            segments, _ = self._model.transcribe(
                audio,
                language=self.language,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300}
            )
            return " ".join(s.text for s in segments).strip()
        except Exception as e:
            print(f"[STT] Error en Whisper: {e}")
            return ""

    def transcribe_file(self, file_path: str) -> str:
        if not self.is_available():
            return ""
        try:
            segments, _ = self._model.transcribe(
                file_path,
                language=self.language,
                vad_filter=True,
            )
            return " ".join(s.text for s in segments).strip()
        except Exception as e:
            print(f"[STT] Error en Whisper archivo: {e}")
            return ""

    def get_info(self) -> dict:
        return {
            "name": "Whisper",
            "available": self.is_available(),
            "model": self.model_name,
            "language": self.language,
            "type": "offline"
        }


# ──────────────────────────────────────────────────────────────
# MOTOR: GOOGLE SPEECH (Cloud)
# ──────────────────────────────────────────────────────────────

class GoogleSTT(STTEngine):
    """Motor Google Speech Recognition (cloud)."""

    def __init__(self, language: str = "es-ES"):
        self.language = language
        self._recognizer = None
        self._load_recognizer()

    def _load_recognizer(self):
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            print("[STT] Google Speech inicializado")
        except ImportError:
            print("[STT] speech_recognition no instalado. Ejecuta: pip install SpeechRecognition")
            self._recognizer = None

    def is_available(self) -> bool:
        return self._recognizer is not None

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        if not self.is_available():
            return ""
        try:
            import speech_recognition as sr
            import io
            # Crear un archivo WAV en memoria
            audio = sr.AudioData(audio_data, sample_rate, 2)
            return self._recognizer.recognize_google(audio, language=self.language)
        except sr.UnknownValueError:
            return ""
        except Exception as e:
            print(f"[STT] Error en Google Speech: {e}")
            return ""

    def transcribe_file(self, file_path: str) -> str:
        if not self.is_available():
            return ""
        try:
            import speech_recognition as sr
            with sr.AudioFile(file_path) as source:
                audio = self._recognizer.record(source)
            return self._recognizer.recognize_google(audio, language=self.language)
        except sr.UnknownValueError:
            return ""
        except Exception as e:
            print(f"[STT] Error en Google Speech archivo: {e}")
            return ""

    def get_info(self) -> dict:
        return {
            "name": "Google Speech",
            "available": self.is_available(),
            "language": self.language,
            "type": "cloud"
        }


# ──────────────────────────────────────────────────────────────
# MOTOR: NEMOTRON ASR (Local, GPU)
# ──────────────────────────────────────────────────────────────

class NemotronSTT(STTEngine):
    """Motor Nemotron ASR (NVIDIA Canary-1B) local."""

    def __init__(self, model_name: str = "nvidia/canary-1b"):
        self.model_name = model_name
        self._model = None
        self._loaded = False
        self._load_model()

    def _load_model(self):
        try:
            import torch
            import nemo.collections.asr as nemo_asr
            self._torch = torch
            self._nemo_asr = nemo_asr
            self._loaded = True
            print("[STT] Nemotron ASR disponible (cargado bajo demanda)")
        except ImportError:
            print("[STT] Nemotron ASR no disponible. Instala: pip install nemo_toolkit[asr] torch")
            self._loaded = False

    def _ensure_model(self):
        if not self._loaded or self._model is not None:
            return
        try:
            model_path = Path("models/canary-1b.nemo")
            if model_path.exists():
                self._model = self._nemo_asr.models.ASRModel.restore_from(str(model_path))
            else:
                self._model = self._nemo_asr.models.ASRModel.from_pretrained(self.model_name)
            if self._torch.cuda.is_available():
                self._model = self._model.cuda()
            self._model.eval()
            print("[STT] Nemotron ASR modelo cargado")
        except Exception as e:
            print(f"[STT] Error cargando Nemotron: {e}")

    def is_available(self) -> bool:
        return self._loaded

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        if not self.is_available():
            return ""
        self._ensure_model()
        if self._model is None:
            return ""

        import tempfile
        import wave
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wf = wave.open(f, "wb")
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
                wf.close()
                f.close()

                with self._torch.no_grad():
                    transcriptions = self._model.transcribe(
                        [f.name],
                        batch_size=1,
                        source_lang="fr",
                        target_lang="fr",
                    )
                text = transcriptions[0] if transcriptions else ""
                if hasattr(text, "text"):
                    text = text.text
                return str(text).strip()
        except Exception as e:
            print(f"[STT] Error en Nemotron: {e}")
            return ""
        finally:
            try:
                os.unlink(f.name)
            except:
                pass

    def transcribe_file(self, file_path: str) -> str:
        if not self.is_available():
            return ""
        self._ensure_model()
        if self._model is None:
            return ""
        try:
            with self._torch.no_grad():
                transcriptions = self._model.transcribe(
                    [file_path],
                    batch_size=1,
                    source_lang="fr",
                    target_lang="fr",
                )
            text = transcriptions[0] if transcriptions else ""
            if hasattr(text, "text"):
                text = text.text
            return str(text).strip()
        except Exception as e:
            print(f"[STT] Error en Nemotron archivo: {e}")
            return ""

    def get_info(self) -> dict:
        return {
            "name": "Nemotron ASR",
            "available": self.is_available(),
            "model": self.model_name,
            "type": "offline",
            "gpu_available": self._torch.cuda.is_available() if self._loaded else False,
        }


# ──────────────────────────────────────────────────────────────
# FÁBRICA PRINCIPAL
# ──────────────────────────────────────────────────────────────

def create_stt_engine(engine_name: str = None, **kwargs) -> STTEngine:
    """
    Crea un motor STT según el nombre especificado.

    Args:
        engine_name: "vosk", "whisper", "google", "nemotron"
        **kwargs: Parámetros específicos del motor

    Returns:
        Instancia de STTEngine
    """
    if engine_name is None:
        engine_name = get_config().preferred_stt

    engine_name = engine_name.lower().strip()

    if engine_name == "vosk":
        return VoskSTT(**kwargs)
    elif engine_name == "whisper":
        return WhisperSTT(**kwargs)
    elif engine_name == "google":
        return GoogleSTT(**kwargs)
    elif engine_name == "nemotron":
        return NemotronSTT(**kwargs)
    else:
        # Fallback a Whisper
        print(f"[STT] Motor '{engine_name}' no soportado, usando Whisper")
        return WhisperSTT(**kwargs)


def get_available_stt_engines() -> list:
    """Retorna la lista de motores STT disponibles."""
    engines = []
    for name, cls in [
        ("vosk", VoskSTT),
        ("whisper", WhisperSTT),
        ("google", GoogleSTT),
        ("nemotron", NemotronSTT),
    ]:
        try:
            engine = cls()
            if engine.is_available():
                engines.append(engine.get_info())
        except Exception:
            pass
    return engines


def transcribe_audio(
    audio_data: bytes,
    engine: str = None,
    sample_rate: int = 16000,
    **kwargs
) -> str:
    """
    Función de conveniencia para transcribir audio.

    Args:
        audio_data: Datos de audio en PCM (16-bit)
        engine: Nombre del motor a usar
        sample_rate: Frecuencia de muestreo
        **kwargs: Parámetros adicionales

    Returns:
        Texto transcrito
    """
    stt = create_stt_engine(engine, **kwargs)
    return stt.transcribe(audio_data, sample_rate)