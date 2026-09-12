import os
import subprocess
def notify_voice(message):
    # Comando para utilizar el sintetizador de voz 'espeak'
    subprocess.call(['espeak', message])
def run(params):
    if 'message' in params:
        notify_voice(params['message'])
        return {"status": "notificación enviada", "message": params['message']}
    else:
        return {"status": "error", "message": "falta el parámetro 'message'"}