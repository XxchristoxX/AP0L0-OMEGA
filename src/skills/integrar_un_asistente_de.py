import os
import json
import subprocess
import vosk
import wave
def run(params):
    model_path = params.get("model_path", "model")
    sample_rate = params.get("sample_rate", 16000)
    commands = params.get("commands", {})
    result = {"success": False, "message": ""}
    if not os.path.exists(model_path):
        return {"success": False, "message": "Model path not found"}
    vosk.SetLogLevel(0)
    model = vosk.Model(model_path)
    rec = vosk.KaldiRecognizer(model, sample_rate)
    with wave.open(params.get("audio_file", "audio.wav"), "rb") as wf:
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != sample_rate:
            return {"success": False, "message": "Audio file must be WAV format mono PCM."}
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result_json = rec.Result()
                result_dict = json.loads(result_json)
                if 'text' in result_dict:
                    command = result_dict['text']
                    if command in commands:
                        result["success"] = True
                        result["message"] = commands[command]
                        execute_command(commands[command])
                        break
    return result
def execute_command(command):
    subprocess.run(command, shell=True)