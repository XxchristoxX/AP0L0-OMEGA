import sys
import subprocess
def instalar_si_no_existe(libreria):
    try:
        __import__(libreria)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', libreria])
for lib in ['speech_recognition', 'pyttsx3', 'numpy']:
    instalar_si_no_existe(lib)
import speech_recognition as sr
import pyttsx3
import numpy as np
def run(params):
    texto = params.get('text', 'Hola, este es el control adaptativo de velocidad por contexto.')
    try:
        recognizer = sr.Recognizer()
        mic = sr.Microphone()
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
            audio = recognizer.listen(source, timeout=3, phrase_time_limit=3)
        audio_data = np.frombuffer(audio.get_raw_data(), dtype=np.int16)
        nivel_ruido = np.abs(audio_data).mean()
    except Exception:
        nivel_ruido = 500.0
    urgente = params.get('urgent', False)
    engine = pyttsx3.init()
    base_rate = 175
    if urgente:
        base_rate += 40
    if nivel_ruido > 1000:
        base_rate += 25
        volume = 1.0
    else:
        volume = 0.9
    engine.setProperty('rate', base_rate)
    engine.setProperty('volume', volume)
    engine.say(texto)
    engine.runAndWait()
    return f"Voz ejecutada. Ruido ambiental detectado: {nivel_ruido:.2f}, Velocidad configurada: {base_rate}"