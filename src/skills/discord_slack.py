import requests
import json
import datetime
import os
import subprocess
def run(params):
    webhook_url = params.get('webhook_url')
    important_keywords = params.get('important_keywords', [])
    channel_id = params.get('channel_id')
    if not webhook_url or not channel_id:
        return "Faltan parámetros necesarios."
    headers = {
        'Authorization': f"Bot {params.get('bot_token')}",
        'Content-Type': 'application/json'
    }
    response = requests.get(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=headers)
    if response.status_code != 200:
        return "Error al acceder a los mensajes."
    messages = json.loads(response.text)
    important_messages = []
    for message in messages:
        if any(keyword in message['content'] for keyword in important_keywords):
            important_messages.append(message['content'])
    if important_messages:
        notify(important_messages)
    return "Revisión completa."
def notify(messages):
    for msg in messages:
        subprocess.run(["notify-send", "Mensaje Importante", msg])  # Solo en sistemas Linux
    # })