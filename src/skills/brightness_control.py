import subprocess
import json
def adjust_brightness(value):
    if not 0 <= value <= 100:
        return {"error": "El valor debe estar entre 0 y 100."}
    try:
        subprocess.run(["powershell", "-Command", f"(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {value})"], check=True)
        return {"success": f"Brillo ajustado al {value}%."}
    except subprocess.CalledProcessError as e:
        return {"error": str(e)}
def run(params):
    if 'brightness' not in params:
        return {"error": "Falta el parámetro 'brightness'."}
    brightness_value = params['brightness']
    return adjust_brightness(brightness_value)