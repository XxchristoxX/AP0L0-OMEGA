# src/actions/emotion_detector.py
"""
Detección de emociones en voz usando SpeechBrain o librerías similares.
"""

import os
import tempfile
import subprocess
import json
import numpy as np

class EmotionDetector:
    def __init__(self):
        self._available = False
        self._check_dependencies()

    def _check_dependencies(self):
        """Verifica si las librerías necesarias están instaladas."""
        try:
            # Intentar importar speechbrain
            import speechbrain as sb
            self._available = True
            print("[EmotionDetector] SpeechBrain disponible.")
        except ImportError:
            # Fallback: usar modelo más simple
            try:
                from transformers import pipeline
                self._pipeline = pipeline("audio-classification", model="superb/wav2vec2-base-superb-ic")
                self._available = True
                print("[EmotionDetector] Hugging Face pipeline disponible.")
            except ImportError:
                print("[EmotionDetector] No disponible. Instala: pip install speechbrain")
                self._available = False

    def detect_emotion(self, audio_bytes: bytes) -> dict:
        """
        Detecta la emoción en un audio.
        Retorna: dict con emoción dominante y porcentajes.
        """
        if not self._available:
            return {"error": "Emotion detection not available."}

        try:
            # Guardar audio temporalmente
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_bytes)
                audio_path = f.name

            if hasattr(self, '_pipeline'):
                # Usar Hugging Face pipeline
                result = self._pipeline(audio_path)
                emotions = {item['label']: item['score'] for item in result}
                dominant = max(emotions, key=emotions.get)
                return {
                    "dominant": dominant,
                    "scores": emotions,
                    "method": "huggingface"
                }
            else:
                # Usar SpeechBrain
                import speechbrain as sb
                from speechbrain.pretrained import EncoderClassifier
                classifier = EncoderClassifier.from_hparams(
                    source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP",
                    run_opts={"device": "cpu"}
                )
                signal, fs = sb.dataio.dataio.read_audio(audio_path)
                signal = signal.unsqueeze(0)  # batch dimension
                out_prob, score, index, text = classifier.classify_batch(signal)
                emotions = {
                    "neutral": float(out_prob[0][0]),
                    "happy": float(out_prob[0][1]),
                    "sad": float(out_prob[0][2]),
                    "angry": float(out_prob[0][3])
                }
                dominant = max(emotions, key=emotions.get)
                return {
                    "dominant": dominant,
                    "scores": emotions,
                    "method": "speechbrain"
                }

        except Exception as e:
            return {"error": str(e)}
        finally:
            try:
                os.unlink(audio_path)
            except:
                pass

def detect_emotion(parameters: dict, player=None, speak=None) -> str:
    """Herramienta para detectar emociones en voz."""
    audio_bytes = parameters.get("audio_bytes")
    if not audio_bytes:
        return "No se proporcionó audio para analizar."

    detector = EmotionDetector()
    result = detector.detect_emotion(audio_bytes)

    if "error" in result:
        return f"Error: {result['error']}"

    emotion = result.get("dominant", "desconocida")
    scores = result.get("scores", {})
    response = f"Emoción detectada: {emotion}. Confianza: {scores.get(emotion, 0)*100:.1f}%."
    if speak:
        speak(response)
    return response