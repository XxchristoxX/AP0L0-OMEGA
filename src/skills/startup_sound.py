import os
import subprocess
def play_audio(file_name):
    audio_path = os.path.join('audio', file_name)
    if os.path.exists(audio_path):
        subprocess.run(['afplay', audio_path])  # Para macOS
        # subprocess.run(['aplay', audio_path])  # Para Linux
        # subprocess.run(['start', audio_path], shell=True)  # Para Windows
    else:
        print("El archivo de audio no existe.")
def run(params):
    audio_file = params.get('audio_file', 'default_sound.mp3')
    play_audio(audio_file)
    return {"status": "audio played", "file": audio_file}