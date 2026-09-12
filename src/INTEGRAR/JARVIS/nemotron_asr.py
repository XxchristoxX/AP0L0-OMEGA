# ══════════════════════════════════════════════════════════════
#  NVIDIA Nemotron / Canary ASR — Módulo local para J.A.R.V.I.S
#  Sitio: www.techenclair.fr
# ══════════════════════════════════════════════════════════════
#  Este módulo es 100% opcional. Solo se activa si el usuario
#  activa el interruptor "NEMOTRON ASR" en la interfaz.
#
#  Requisitos previos (opcionales):
#    pip install nemo_toolkit[asr] torch
#
#  Modelo utilizado: nvidia/canary-1b (multilingüe — español)
#  Tamaño: ~4 GB (descargado automáticamente en el primer lanzamiento)
# ══════════════════════════════════════════════════════════════

import os
import tempfile
import wave
import struct
import time

# Indicador global de disponibilidad
_NEMO_DISPONIBLE = False
_TORCH_DISPONIBLE = False

# IMPORTACIÓN RESTRINGIDA DE DLL Y CONFLICTOS BINARIOS (WINDOWS)
import sys
import warnings

# Silenciar advertencias y registros verbosos de NeMo/Megatron/PyTorch
warnings.filterwarnings("ignore")
os.environ["NEMO_LOG_LEVEL"] = "ERROR"
os.environ["HYDRA_FULL_ERROR"] = "0"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"

# Redirección robusta a nivel de sistema operativo (descriptores de archivos 1 y 2)
# para interceptar las salidas C/C++ de Pygame, PyTorch y OneLogger.
sys.stdout.flush()
sys.stderr.flush()
_redireccion_os = False

try:
    _fd_devnull = os.open(os.devnull, os.O_WRONLY)
    _old_stdout_fd = os.dup(1)
    _old_stderr_fd = os.dup(2)
    os.dup2(_fd_devnull, 1)
    os.dup2(_fd_devnull, 2)
    _redireccion_os = True
except Exception:
    pass

# Redirección a nivel de Python
_old_sys_stdout = sys.stdout
_old_sys_stderr = sys.stderr
sys.stdout = open(os.devnull, 'w', encoding='utf-8')
sys.stderr = open(os.devnull, 'w', encoding='utf-8')

try:
    # 1. Cargar pyarrow.dataset antes que torch para evitar conflictos binarios (OpenMP/MKL) en Windows
    try:
        import pyarrow.dataset
    except Exception:
        pass

    # 2. Cargar torch y añadir su directorio lib a las DLL de Windows para torchaudio/NeMo
    try:
        import torch
        _TORCH_DISPONIBLE = True
        try:
            torch_lib_dir = os.path.join(os.path.dirname(torch.__file__), "lib")
            if os.path.exists(torch_lib_dir) and hasattr(os, "add_dll_directory"):
                os.add_dll_directory(torch_lib_dir)
        except Exception:
            pass
    except Exception:
        torch = None
        _TORCH_DISPONIBLE = False

    # 3. Cargar nemo.collections.asr
    try:
        import nemo.collections.asr as nemo_asr
        _NEMO_DISPONIBLE = True
    except Exception:
        nemo_asr = None
        _NEMO_DISPONIBLE = False
finally:
    # Restaurar la redirección de Python
    try:
        sys.stdout.close()
    except Exception:
        pass
    try:
        sys.stderr.close()
    except Exception:
        pass
    sys.stdout = _old_sys_stdout
    sys.stderr = _old_sys_stderr

    # Restaurar la redirección a nivel de sistema operativo
    if _redireccion_os:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(_old_stdout_fd, 1)
            os.dup2(_old_stderr_fd, 2)
            os.close(_fd_devnull)
            os.close(_old_stdout_fd)
            os.close(_old_stderr_fd)
        except Exception:
            pass


class NemotronASR:
    """
    Encapsula el modelo NVIDIA Canary-1B (NeMo) para la transcripción
    de voz 100% local.

    Características:
      - Carga diferida (el modelo solo se carga en la primera llamada)
      - Liberación explícita de la memoria GPU/CPU
      - Detección automática de GPU vs CPU con advertencias
      - Limpieza de VRAM después de cada transcripción
    """

    MODELO_POR_DEFECTO = "nvidia/canary-1b"

    def __init__(self, nombre_modelo: str | None = None):
        self._modelo = None
        self._nombre_modelo = nombre_modelo or self.MODELO_POR_DEFECTO
        self._dispositivo = None  # "cuda" o "cpu"
        self._cargando = False
        self._cargado = False

    # ── Detección de hardware ──────────────────────────────────────

    @staticmethod
    def is_nemo_installed() -> bool:
        """Devuelve True si nemo_toolkit[asr] está instalado."""
        return _NEMO_DISPONIBLE and _TORCH_DISPONIBLE

    @staticmethod
    def is_gpu_available() -> bool:
        """Devuelve True si hay una GPU NVIDIA CUDA disponible."""
        if not _TORCH_DISPONIBLE:
            return False
        return torch.cuda.is_available()

    def obtener_info_dispositivo(self) -> dict:
        """Devuelve información sobre el dispositivo utilizado."""
        info = {
            "nemo_instalado": _NEMO_DISPONIBLE,
            "torch_instalado": _TORCH_DISPONIBLE,
            "gpu_disponible": self.is_gpu_available(),
            "dispositivo": self._dispositivo or ("cuda" if self.is_gpu_available() else "cpu"),
            "modelo": self._nombre_modelo,
            "cargado": self._cargado,
        }
        if self.is_gpu_available() and _TORCH_DISPONIBLE:
            try:
                info["nombre_gpu"] = torch.cuda.get_device_name(0)
                info["vram_gpu_mb"] = round(
                    torch.cuda.get_device_properties(0).total_mem / 1024 / 1024
                )
            except Exception:
                pass
        return info

    # ── Carga / descarga del modelo ───────────────────────────────────────

    def cargar_modelo(self) -> dict:
        """
        Carga el modelo NeMo en memoria.

        Devuelve un dict con la información de carga:
          {"success": bool, "device": str, "warnings": [str], "error": str|None}
        """
        if self._cargado:
            return {
                "success": True,
                "device": self._dispositivo,
                "warnings": [],
                "error": None,
            }

        if self._cargando:
            return {
                "success": False,
                "device": None,
                "warnings": [],
                "error": "Carga ya en curso…",
            }

        if not _NEMO_DISPONIBLE or not _TORCH_DISPONIBLE:
            msgs = []
            if not _TORCH_DISPONIBLE:
                msgs.append("PyTorch no instalado (pip install torch)")
            if not _NEMO_DISPONIBLE:
                msgs.append("NeMo no instalado (pip install nemo_toolkit[asr])")
            return {
                "success": False,
                "device": None,
                "warnings": [],
                "error": " | ".join(msgs),
            }

        self._cargando = True
        advertencias = []

        try:
            # Elección del dispositivo
            if self.is_gpu_available():
                self._dispositivo = "cuda"
                print(f"[ASR] 🟢 GPU NVIDIA detectada: {torch.cuda.get_device_name(0)}")
            else:
                self._dispositivo = "cpu"
                advertencias.append(
                    "No se detectó GPU NVIDIA. Se usará el modo CPU — "
                    "la transcripción será LENTA (10-30s por frase)."
                )
                print("[ASR] ⚠ Sin GPU NVIDIA — modo CPU (lento)")

            print(f"[ASR] Cargando modelo {self._nombre_modelo}…")
            print(f"[ASR] ⚠ Primer lanzamiento: descarga de ~4 GB si es necesario")

            t0 = time.time()

            # Carga del modelo NeMo ASR
            ruta_local_modelo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "canary-1b.nemo")
            if self._nombre_modelo == "nvidia/canary-1b" and os.path.exists(ruta_local_modelo):
                print(f"[ASR] Cargando modelo local desde {ruta_local_modelo}…")
                self._modelo = nemo_asr.models.ASRModel.restore_from(
                    restore_path=ruta_local_modelo
                )
            else:
                self._modelo = nemo_asr.models.ASRModel.from_pretrained(
                    model_name=self._nombre_modelo
                )

            # Mover al dispositivo correcto
            if self._dispositivo == "cuda":
                self._modelo = self._modelo.cuda()
            else:
                self._modelo = self._modelo.cpu()

            # Modo evaluación (sin gradientes — ahorra memoria)
            self._modelo.eval()

            dt = round(time.time() - t0, 1)
            print(f"[ASR] ✔ Modelo cargado en {dt}s en {self._dispositivo.upper()}")

            self._cargado = True
            self._cargando = False

            return {
                "success": True,
                "device": self._dispositivo,
                "warnings": advertencias,
                "error": None,
            }

        except Exception as e:
            self._cargando = False
            self._modelo = None
            print(f"[ASR] ✖ Error al cargar el modelo: {e}")
            return {
                "success": False,
                "device": None,
                "warnings": advertencias,
                "error": str(e),
            }

    def liberar(self):
        """Libera el modelo y limpia la memoria GPU/CPU."""
        if self._modelo is not None:
            del self._modelo
            self._modelo = None

        self._cargado = False
        self._dispositivo = None

        if _TORCH_DISPONIBLE and torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            except Exception:
                pass

        # Recolector de basura de Python
        import gc
        gc.collect()

        print("[ASR] ✔ Modelo Nemotron descargado — memoria liberada")

    # ── Transcripción ─────────────────────────────────────────────

    def transcribir(self, datos_audio_crudos: bytes, frecuencia_muestreo: int = 16000) -> str:
        """
        Transcribe un segmento de audio sin procesar (PCM 16-bit mono).

        Args:
            datos_audio_crudos : bytes PCM 16-bit little-endian mono
            frecuencia_muestreo    : tasa de muestreo (por defecto 16000 Hz)

        Returns:
            Texto transcrito (str), o cadena vacía en caso de error.
        """
        if not self._cargado or self._modelo is None:
            # Auto-carga si aún no se ha hecho
            resultado = self.cargar_modelo()
            if not resultado["success"]:
                print(f"[ASR] No se puede transcribir: {resultado['error']}")
                return ""

        # Guardar el audio en un archivo WAV temporal
        # (NeMo espera un archivo de audio como entrada)
        ruta_tmp = None
        try:
            fd_tmp, ruta_tmp = tempfile.mkstemp(suffix=".wav", prefix="jarvis_asr_")
            os.close(fd_tmp)

            with wave.open(ruta_tmp, "wb") as wf:
                wf.setnchannels(1)        # mono
                wf.setsampwidth(2)        # 16-bit
                wf.setframerate(frecuencia_muestreo)
                wf.writeframes(datos_audio_crudos)

            # Transcripción con NeMo
            t0 = time.time()

            with _contexto_sin_grad():
                transcripciones = self._modelo.transcribe(
                    [ruta_tmp],
                    batch_size=1,
                    source_lang="es",
                    target_lang="es",
                )

            dt = round(time.time() - t0, 2)

            # NeMo devuelve una lista de resultados
            if isinstance(transcripciones, list) and len(transcripciones) > 0:
                # Según la versión de NeMo, es una str o un objeto
                texto = transcripciones[0]
                if hasattr(texto, "text"):
                    texto = texto.text
                texto = str(texto).strip()
            else:
                texto = ""

            print(f"[ASR] Transcripción ({dt}s): \"{texto}\"")

            # Limpieza de memoria GPU después de cada transcripción
            self._limpiar_cache_gpu()

            return texto

        except Exception as e:
            print(f"[ASR] ✖ Error en transcripción: {e}")
            return ""

        finally:
            # Eliminar el archivo WAV temporal
            if ruta_tmp and os.path.exists(ruta_tmp):
                try:
                    os.remove(ruta_tmp)
                except Exception:
                    pass

    # ── Utilidades internas ──────────────────────────────────────

    def _limpiar_cache_gpu(self):
        """Libera la memoria GPU temporal sin descargar el modelo."""
        if _TORCH_DISPONIBLE and torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass


def _contexto_sin_grad():
    """Devuelve el gestor de contexto torch.no_grad() si está disponible."""
    if _TORCH_DISPONIBLE:
        return torch.no_grad()
    # Fallback: gestor de contexto neutro
    from contextlib import nullcontext
    return nullcontext()