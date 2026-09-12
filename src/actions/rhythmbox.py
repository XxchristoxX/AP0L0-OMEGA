# actions/rhythmbox.py
import subprocess
import platform

class RhythmboxController:
    def __init__(self):
        self._os = platform.system()
        if self._os != "Linux":
            print("[Rhythmbox] Solo disponible en Linux.")

    def control(self, action: str) -> str:
        if self._os != "Linux":
            return "Rhythmbox solo funciona en Linux."

        cmds = {
            "play": "rhythmbox-client --play",
            "pause": "rhythmbox-client --pause",
            "play_pause": "rhythmbox-client --play-pause",
            "next": "rhythmbox-client --next",
            "previous": "rhythmbox-client --previous",
            "stop": "rhythmbox-client --stop",
            "volume_up": "rhythmbox-client --volume-up",
            "volume_down": "rhythmbox-client --volume-down",
        }
        cmd = cmds.get(action)
        if not cmd:
            return f"Acción '{action}' no soportada."
        try:
            subprocess.run(cmd.split(), capture_output=True, check=True)
            return f"Rhythmbox: {action}"
        except Exception as e:
            return f"Error al controlar Rhythmbox: {e}"