# plugins/mi_plugin.py
PLUGIN = {
    "name": "mi_plugin",
    "description": "Descripción de lo que hace",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "mensaje": {"type": "STRING", "description": "Mensaje a mostrar"}
        }
    }
}

def run(parameters, player=None, session_memory=None):
    mensaje = parameters.get("mensaje", "Hola desde el plugin")
    if player:
        player.write_log(f"[Plugin] {mensaje}")
    return f"Plugin ejecutado: {mensaje}"