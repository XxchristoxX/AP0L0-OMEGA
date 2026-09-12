# src/actions/nemotron_asr.py
"""
NVIDIA Nemotron ASR (Canary-1B) para AP0L0
"""

import os
import sys
import tempfile
import wave
import struct
import time
import warnings
import importlib

warnings.filterwarnings("ignore")
os.environ["NEMO_LOG_LEVEL"] = "ERROR"
os.environ["HYDRA_FULL_ERROR"] = "0"

_NEMO_AVAILABLE = False
_TORCH_AVAILABLE = False

try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None

try:
    import nemo.collections.asr as nemo_asr
    _NEMO_AVAILABLE = True
except ImportError:
    nemo_asr = None


class NemotronASR:
    DEFAULT_MODEL = "nvidia/canary-1b"

    def __init__(self, model_name=None):
        self._model = None
        self._model_name = model_name or self.DEFAULT_MODEL
        self._device = None
        self._charge = False

    @staticmethod
    def is_nemo_installed():
        return _NEMO_AVAILABLE and _TORCH_AVAILABLE

    @staticmethod
    def is_gpu_available():
        return _TORCH_AVAILABLE and torch.cuda.is_available()

    def charger_modele(self):
        if self._charge:
            return {"success": True, "device": self._device, "warnings": [], "error": None}
        if not _NEMO_AVAILABLE or not _TORCH_AVAILABLE:
            return {"success": False, "error": "NeMo o PyTorch no instalados"}
        try:
            if self.is_gpu_available():
                self._device = "cuda"
            else:
                self._device = "cpu"
            self._model = nemo_asr.models.ASRModel.from_pretrained(self._model_name)
            if self._device == "cuda":
                self._model = self._model.cuda()
            else:
                self._model = self._model.cpu()
            self._model.eval()
            self._charge = True
            return {"success": True, "device": self._device, "warnings": [], "error": None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def transcrire(self, raw_audio_data, sample_rate=16000):
        if not self._charge or self._model is None:
            result = self.charger_modele()
            if not result["success"]:
                return ""
        tmp_path = None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav", prefix="jarvis_asr_")
            os.close(tmp_fd)
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(raw_audio_data)
            with torch.no_grad():
                transcriptions = self._model.transcribe([tmp_path], batch_size=1, source_lang="fr", target_lang="fr")
            if isinstance(transcriptions, list) and len(transcriptions) > 0:
                texte = transcriptions[0]
                if hasattr(texte, "text"):
                    texte = texte.text
                return str(texte).strip()
            return ""
        except Exception as e:
            print(f"[ASR] Error: {e}")
            return ""
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def liberer(self):
        if self._model is not None:
            del self._model
            self._model = None
        self._charge = False
        self._device = None
        if _TORCH_AVAILABLE and torch.cuda.is_available():
            torch.cuda.empty_cache()
        import gc
        gc.collect()


# ===== FUNCIÓN EXPORTABLE =====

async def nemotron_asr(params: dict, player=None, speak=None) -> str:
    action = params.get("action", "transcribe")
    audio_bytes = params.get("audio_bytes", b"")
    if action == "transcribe":
        if not audio_bytes:
            return "No se proporcionaron datos de audio."
        asr = NemotronASR()
        result = asr.transcrire(audio_bytes)
        if result:
            if speak:
                speak(result)
            return result
        return "No se pudo transcribir el audio."
    elif action == "load":
        asr = NemotronASR()
        res = asr.charger_modele()
        return f"Modelo cargado: {res['success']}" if res["success"] else f"Error: {res['error']}"
    else:
        return "Acción no soportada."