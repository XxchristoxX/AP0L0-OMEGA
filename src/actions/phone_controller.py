# src/actions/phone_controller.py
import subprocess
import json
import re
from pathlib import Path
from datetime import datetime

class PhoneController:
    def __init__(self, device_id=None):
        self.device_id = device_id
        self._check_adb()
        self._connected_device = None

    def _check_adb(self):
        try:
            result = subprocess.run(["adb", "version"], capture_output=True, text=True)
            if result.returncode != 0:
                print("[PhoneController] ⚠️ ADB no encontrado. Instala Android SDK Platform-Tools.")
                return False
            print("[PhoneController] ✅ ADB disponible.")
            return True
        except FileNotFoundError:
            print("[PhoneController] ⚠️ ADB no encontrado.")
            return False

    def get_devices(self):
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')[1:]
            devices = []
            for line in lines:
                if line.strip() and 'device' in line:
                    device_id = line.split()[0]
                    devices.append(device_id)
            return devices
        except Exception as e:
            print(f"[PhoneController] Error: {e}")
            return []

    def send_command(self, command):
        if not self.device_id:
            devices = self.get_devices()
            if not devices:
                return None, "No hay dispositivos Android conectados."
            self.device_id = devices[0]
            self._connected_device = self.device_id
        try:
            cmd = ["adb", "-s", self.device_id] + command.split()
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout, result.stderr
        except Exception as e:
            return None, str(e)

    # ---- SMS ----
    def get_sms(self, limit=10):
        stdout, stderr = self.send_command(f"shell content query --uri content://sms/inbox --projection address,body,date --sort 'date DESC' --limit {limit}")
        if stderr:
            return f"Error: {stderr}"
        return self._parse_sms(stdout)

    def _parse_sms(self, output):
        messages = []
        # Parsear la salida del content query (formato simple)
        lines = output.strip().split('\n')
        if len(lines) < 2:
            return "No hay mensajes."
        for line in lines[1:]:
            parts = line.split(',', 2)
            if len(parts) >= 3:
                address = parts[0].strip()
                body = parts[2].strip()
                messages.append(f"De: {address}\nMensaje: {body}")
        return "\n\n".join(messages) if messages else "No hay mensajes."

    def send_sms(self, number, message):
        stdout, stderr = self.send_command(f"shell service call isms 7 i32 0 s16 'null' s16 '{number}' s16 'null' s16 '{message}' s16 'null' s16 'null'")
        if stderr:
            return f"Error: {stderr}"
        return f"SMS enviado a {number}."

    # ---- Llamadas ----
    def make_call(self, number):
        stdout, stderr = self.send_command(f"shell am start -a android.intent.action.CALL -d tel:{number}")
        if stderr:
            return f"Error: {stderr}"
        return f"Llamando a {number}..."

    def end_call(self):
        stdout, stderr = self.send_command("shell input keyevent KEYCODE_ENDCALL")
        if stderr:
            return f"Error: {stderr}"
        return "Llamada finalizada."

    # ---- Notificaciones ----
    def get_notifications(self, limit=5):
        stdout, stderr = self.send_command(f"shell dumpsys notification --recent --count {limit}")
        if stderr:
            return f"Error: {stderr}"
        return self._parse_notifications(stdout)

    def _parse_notifications(self, output):
        lines = output.split('\n')
        notifications = []
        for line in lines:
            if 'NotificationRecord' in line:
                match = re.search(r'pkg=([^ ]+)', line)
                if match:
                    notifications.append(f"App: {match.group(1)}")
            if 'contentText' in line:
                match = re.search(r'contentText=([^ ]+)', line)
                if match:
                    notifications[-1] += f" - {match.group(1)}"
        return "\n".join(notifications) if notifications else "No hay notificaciones."


def phone_control(parameters: dict, player=None, speak=None) -> str:
    action = parameters.get("action", "list_devices")
    phone = PhoneController()

    if action == "list_devices":
        devices = phone.get_devices()
        if not devices:
            return "No hay dispositivos Android conectados."
        return "Dispositivos: " + ", ".join(devices)

    elif action == "get_sms":
        limit = int(parameters.get("limit", 10))
        return phone.get_sms(limit)

    elif action == "send_sms":
        number = parameters.get("number")
        message = parameters.get("message")
        if not number or not message:
            return "Faltan número o mensaje."
        return phone.send_sms(number, message)

    elif action == "make_call":
        number = parameters.get("number")
        if not number:
            return "Falta el número."
        return phone.make_call(number)

    elif action == "end_call":
        return phone.end_call()

    elif action == "get_notifications":
        limit = int(parameters.get("limit", 5))
        return phone.get_notifications(limit)

    else:
        return f"Acción '{action}' no soportada. Usa: list_devices, get_sms, send_sms, make_call, end_call, get_notifications"