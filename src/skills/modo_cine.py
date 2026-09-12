import os
import subprocess
import json
def bajar_luces():
    # Simulación de bajar las luces (aquí se puede integrar con un sistema de domótica)
    print("Luces bajadas.")
def activar_spotify():
    # Simulación de abrir Spotify
    print("Spotify activado.")
def silenciar_notificaciones():
    # Simulación de silenciar notificaciones
    print("Notificaciones silenciadas.")
def run(params):
    if params.get('modo') == 'cine':
        bajar_luces()
        activar_spotify()
        silenciar_notificaciones()
        return json.dumps({"resultado": "Modo cine activado."})
    return json.dumps({"resultado": "Parámetro no válido."})