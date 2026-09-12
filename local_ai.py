"""
Módulo de IA Local para AP0LO (MARK L) - VERSIÓN CORREGIDA
- STT: Vosk (offline)
- LLM: Ollama (offline)
- TTS: pyttsx3 con bloqueo para evitar errores de hilos
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

# ============================================================
# CONFIGURACIÓN
# ============================================================
MODELO_VOSK = "models/vosk-model-es"   # Ruta al modelo de Vosk
MODELO_OLLAMA = "qwen2.5:3b"           # Modelo de Ollama (cámbialo si usas otro)
SAMPLE_RATE = 16000
BLOCK_SIZE = 8000

# ============================================================
# RECONOCIMIENTO DE VOZ (STT) - Vosk
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
# GENERACIÓN DE RESPUESTAS (LLM) - Ollama
# ============================================================
class LocalLLM:
    def __init__(self, model=MODELO_OLLAMA):
        self.model = model

    def ask(self, prompt, context=None):
        messages = []
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": prompt})
        try:
            response = ollama.chat(model=self.model, messages=messages)
            return response['message']['content']
        except Exception as e:
            return f"Error al conectar con Ollama: {str(e)}"

# ============================================================
# SÍNTESIS DE VOZ (TTS) - pyttsx3 con bloqueo de hilos
# ============================================================
class LocalTTS:
    def __init__(self):
        self.engine = pyttsx3.init()
        # Buscar voz en español
        voices = self.engine.getProperty('voices')
        for voice in voices:
            if 'spanish' in voice.name.lower() or 'es' in voice.id.lower():
                self.engine.setProperty('voice', voice.id)
                break
        self.engine.setProperty('rate', 175)
        self.engine.setProperty('volume', 1.0)
        self.lock = threading.Lock()  # <--- NUEVO: evita conflictos entre hilos

    def speak(self, text):
        """Habla el texto (bloqueante, pero con lock)."""
        with self.lock:
            self.engine.say(text)
            self.engine.runAndWait()

    def speak_async(self, text):
        """Habla en un hilo separado (no bloqueante)."""
        threading.Thread(target=self.speak, args=(text,), daemon=True).start()

# ============================================================
# ASISTENTE LOCAL COMPLETO
# ============================================================
class LocalAssistant:
    def __init__(self):
        self.stt = LocalSTT()
        self.llm = LocalLLM()
        self.tts = LocalTTS()
        self.contexto = "Eres un asistente personal útil llamado AP0LO. Responde en español de forma clara y concisa."

    def listen(self, timeout=5):
        return self.stt.get_text(timeout)

    def think(self, question):
        return self.llm.ask(question, self.contexto)

    def speak(self, text):
        self.tts.speak_async(text)

    def process_voice_command(self, timeout=5):
        print("🎤 Escuchando...")
        question = self.listen(timeout)
        if not question:
            return "No te he entendido. ¿Puedes repetir?"
        print(f"📝 Has dicho: {question}")
        answer = self.think(question)
        print(f"🤖 Respuesta: {answer}")
        self.speak(answer)
        return answer

# ============================================================
# PRUEBA RÁPIDA
# ============================================================
if __name__ == "__main__":
    print("=== PRUEBA DEL ASISTENTE LOCAL ===")
    assistant = LocalAssistant()
    assistant.speak("Hola, soy AP0LO. Estoy listo para ayudarte.")
    while True:
        print("\nPresiona Enter para hablar (o escribe 'salir' para terminar)...")
        entrada = input("> ")
        if entrada.lower() == "salir":
            break
        if entrada.strip() == "":
            assistant.process_voice_command()
        else:
            respuesta = assistant.think(entrada)
            print(f"🤖 {respuesta}")
            assistant.speak(respuesta)