# src/actions/environment_controller.py
import psutil
import subprocess
import platform
import json

class EnvironmentController:
    def __init__(self):
        self._os = platform.system()
        self._current_mode = "normal"

    def get_system_state(self):
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        battery = psutil.sensors_battery()
        return {"cpu": cpu, "memory": mem, "battery": battery.percent if battery else None}

    def apply_contextual_mode(self, mode="auto"):
        """
        Ajusta el sistema según el modo.
        Modes: "auto", "power_saver", "performance", "focus", "normal"
        """
        state = self.get_system_state()
        cpu = state["cpu"]
        mem = state["memory"]
        battery = state["battery"] if state["battery"] else 100

        if mode == "auto":
            if cpu > 80 or mem > 85:
                mode = "performance"
            elif battery < 20:
                mode = "power_saver"
            else:
                mode = "normal"

        if mode == "power_saver":
            self._set_power_saver(True)
            self._adjust_brightness(30)
            self._set_focus_mode(True)
        elif mode == "performance":
            self._set_power_saver(False)
            self._adjust_brightness(80)
            self._set_focus_mode(True)
        elif mode == "focus":
            self._set_focus_mode(True)
            self._adjust_brightness(50)
        else:
            self._set_power_saver(False)
            self._adjust_brightness(60)
            self._set_focus_mode(False)

        self._current_mode = mode
        return f"Modo contextual cambiado a: {mode}"

    def _set_power_saver(self, enable):
        if self._os == "Windows":
            # Activar/desactivar ahorro de energía
            subprocess.run(["powercfg", "-setactive", "a1841308-3541-4fab-bc81-f71556f20b4a" if enable else "381b4222-f694-41f0-9685-ff5bb260df2e"], capture_output=True)
        elif self._os == "Linux":
            subprocess.run(["systemctl", "set-property", "user", "CPUQuota", "50%" if enable else "100%"], capture_output=True)

    def _adjust_brightness(self, percent):
        if self._os == "Windows":
            try:
                import wmi
                w = wmi.WMI(namespace="root/wmi")
                methods = w.WmiMonitorBrightnessMethods()[0]
                methods.WmiSetBrightness(percent, 1)
            except:
                pass
        elif self._os == "Linux":
            subprocess.run(["brightnessctl", "set", f"{percent}%"], capture_output=True)
        elif self._os == "Darwin":
            subprocess.run(["osascript", "-e", f"tell application 'System Events' to repeat 5 times\nkey code 144\nend repeat"], capture_output=True)

    def _set_focus_mode(self, enable):
        if self._os == "Windows":
            # Activar/desactivar modo de enfoque
            subprocess.run(["powershell", "-Command", f"Set-ExecutionPolicy Bypass -Scope Process; (New-Object -ComObject 'Wscript.Shell').SendKeys('%+')"], capture_output=True)

    def get_status(self):
        return f"Modo actual: {self._current_mode}"


def environment_control(parameters: dict, player=None, speak=None) -> str:
    env = EnvironmentController()
    action = parameters.get("action", "status")

    if action == "status":
        return env.get_status()
    elif action == "set_mode":
        mode = parameters.get("mode", "auto")
        return env.apply_contextual_mode(mode)
    else:
        return f"Acción '{action}' no soportada. Usa: status, set_mode"