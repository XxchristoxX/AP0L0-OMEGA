"""
local_ai_enhanced.py - Modo Local Mejorado para AP0LO
Basado en OpenJarvis y A.D.A.
Soporta: Ollama, Wake Word, Múltiples modelos
"""

import os
import json
import queue
import time
import threading
import sounddevice as sd
import vosk
import pyttsx3
import ollama
import numpy as np

# ============================================================
# CONFIGURACIÓN
# ============================================================
MODELO_VOSK = "models/vosk-model-es"
MODELO_OLLAMA = "qwen2.5:3b"  # Cambiar a deepseek-r1:1.5b para mejor razonamiento
WAKE_WORD = "jarvis"          # Palabra de activación
SAMPLE_RATE = 16000
BLOCK_SIZE = 8000

# ============================================================
# DETECCIÓN DE WAKE WORD (versión simple)
# ============================================================
class WakeWordDetector:
    def __init__(self, wake_word=WAKE_WORD):
        self.wake_word = wake_word.lower()
        self.model = vosk.Model(MODELO_VOSK)
        self.recognizer = vosk.KaldiRecognizer(self.model, SAMPLE_RATE)
        self.audio_queue = queue.Queue()
        self.is_listening = False
        self.wake_detected = False
        self.callback = None

    def set_callback(self, callback):
        self.callback = callback

    def start_listening(self):
        self.is_listening = True
        self.audio_queue = queue.Queue()
        
        def callback(indata, frames, time, status):
            if self.is_listening:
                self.audio_queue.put(bytes(indata))
        
        self.stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            device=None,
            dtype='int16',
            channels=1,
            callback=callback
        )
        self.stream.start()
        self._monitor_thread = threading.Thread(target=self._monitor, daemon=True)
        self._monitor_thread.start()

    def _monitor(self):
        while self.is_listening:
            try:
                data = self.audio_queue.get(timeout=0.5)
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "").lower()
                    if self.wake_word in text:
                        self.wake_detected = True
                        if self.callback:
                            self.callback()
            except queue.Empty:
                continue

    def stop_listening(self):
        self.is_listening = False
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()

# ============================================================
# ASISTENTE LOCAL MEJORADO
# ============================================================
class LocalAssistantEnhanced:
    def __init__(self, model=MODELO_OLLAMA):
        self.model = model
        self.llm = ollama
        self.tts = pyttsx3.init()
        self._configure_tts()
        self.wake_detector = WakeWordDetector()
        self.wake_detector.set_callback(self._on_wake)
        self.contexto = "Eres un asistente personal útil llamado AP0LO. Responde en español de forma clara y concisa."
        self.is_active = False

    def _configure_tts(self):
        voices = self.tts.getProperty('voices')
        for voice in voices:
            if 'spanish' in voice.name.lower() or 'es' in voice.id.lower():
                self.tts.setProperty('voice', voice.id)
                break
        self.tts.setProperty('rate', 175)
        self.tts.setProperty('volume', 1.0)

    def _on_wake(self):
        self.is_active = True
        self.speak("Sí, señor. ¿En qué puedo ayudarle?")
        # Iniciar escucha después del wake word
        threading.Thread(target=self._listen_and_respond, daemon=True).start()

    def speak(self, text):
        self.tts.say(text)
        self.tts.runAndWait()

    def think(self, prompt):
        try:
            response = self.llm.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.contexto},
                    {"role": "user", "content": prompt}
                ]
            )
            return response['message']['content']
        except Exception as e:
            return f"Error al conectar con Ollama: {str(e)}"

    def _listen_and_respond(self):
        # Usar el STT de Vosk para escuchar después del wake
        stt = LocalSTT()
        question = stt.get_text(timeout=8)
        if question:
            answer = self.think(question)
            self.speak(answer)
        self.is_active = False

    def start_wake_detection(self):
        """Inicia la detección de wake word en segundo plano."""
        self.wake_detector.start_listening()
        print("🎤 Escuchando wake word... (di 'Jarvis' para activar)")

    def stop_wake_detection(self):
        self.wake_detector.stop_listening()

# ============================================================
# STT para escucha después del wake (igual que antes)
# ============================================================
class LocalSTT:
    def __init__(self):
        if not os.path.exists(MODELO_VOSK):
            raise FileNotFoundError(f"No se encontró el modelo de Vosk en: {MODELO_VOSK}")
        self.model = vosk.Model(MODELO_VOSK)
        self.recognizer = vosk.KaldiRecognizer(self.model, SAMPLE_RATE)
        self.audio_queue = queue.Queue()
        self.is_listening = False

    def start_listening(self):
        self.is_listening = True
        self.audio_queue = queue.Queue()
        def callback(indata, frames, time, status):
            if self.is_listening:
                self.audio_queue.put(bytes(indata))
        self.stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            device=None,
            dtype='int16',
            channels=1,
            callback=callback
        )
        self.stream.start()

    def stop_listening(self):
        self.is_listening = False
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()

    def get_text(self, timeout=5):
        self.start_listening()
        text = ""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                data = self.audio_queue.get(timeout=0.5)
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "")
                    if text:
                        break
            except queue.Empty:
                continue
        self.stop_listening()
        return text

# ============================================================
# PRUEBA RÁPIDA
# ============================================================
if __name__ == "__main__":
    print("=== ASISTENTE LOCAL MEJORADO ===")
    assistant = LocalAssistantEnhanced()
    assistant.speak("Hola, soy AP0LO. Di 'Jarvis' para activarme.")
    assistant.start_wake_detection()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        assistant.stop_wake_detection()
        print("\n🔴 Deteniendo...")