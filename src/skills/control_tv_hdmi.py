import subprocess
import json
def run(params):
    try:
        action = params.get("action")
        device = params.get("device")
        if action == "turn_on":
            command = f"echo 'on {device}' | cec-client -s -d 1"
        elif action == "turn_off":
            command = f"echo 'standby {device}' | cec-client -s -d 1"
        elif action == "volume_up":
            command = f"echo 'volume up' | cec-client -s -d 1"
        elif action == "volume_down":
            command = f"echo 'volume down' | cec-client -s -d 1"
        else:
            return json.dumps({"error": "Acción no válida"})
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return json.dumps({"result": result.stdout.strip(), "error": result.stderr.strip()})
    except Exception as e:
        return json.dumps({"error": str(e)})