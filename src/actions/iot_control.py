# src/actions/iot_control.py
"""
Control de dispositivos IoT: MQTT, Philips Hue, Home Assistant, Tuya.
"""

import os
import json

class IoTController:
    def __init__(self):
        self.broker = os.getenv("MQTT_BROKER", "localhost")
        self.client = None
        self._hue_bridge = None
        self._ha_url = os.getenv("HA_URL", "http://localhost:8123")
        self._ha_token = os.getenv("HA_TOKEN", "")
        self._tuya_device_id = os.getenv("TUYA_DEVICE_ID", "")
        self._tuya_device_key = os.getenv("TUYA_DEVICE_KEY", "")
        self._init_mqtt()
        self._init_hue()
        self._init_home_assistant()
        self._init_tuya()

    def _init_mqtt(self):
        """Inicializa conexión MQTT."""
        try:
            import paho.mqtt.client as mqtt
            self.mqtt = mqtt
            self.client = mqtt.Client()
            self.client.connect(self.broker, 1883, 60)
            print("[IoTController] Conectado a MQTT broker local.")
        except ImportError:
            print("[IoTController] paho-mqtt no instalado. Instala: pip install paho-mqtt")
            self.client = None
        except Exception as e:
            print(f"[IoTController] Error de conexión MQTT: {e}")
            self.client = None

    def _init_hue(self):
        """Inicializa conexión con Philips Hue."""
        try:
            from phue import Bridge
            bridge_ip = os.getenv("HUE_BRIDGE_IP", "192.168.1.100")
            self._hue_bridge = Bridge(bridge_ip)
            self._hue_bridge.connect()
            print("[IoTController] Philips Hue conectado.")
        except ImportError:
            print("[IoTController] phue no instalado. Instala: pip install phue")
        except Exception as e:
            print(f"[IoTController] Hue no disponible: {e}")

    def _init_home_assistant(self):
        """Inicializa conexión con Home Assistant."""
        if self._ha_token:
            print("[IoTController] Home Assistant configurado.")
        else:
            print("[IoTController] Home Assistant no configurado (HA_TOKEN vacío).")

    def _init_tuya(self):
        """Inicializa conexión con Tuya."""
        if self._tuya_device_id and self._tuya_device_key:
            print("[IoTController] Tuya configurado.")
        else:
            print("[IoTController] Tuya no configurado (faltan credenciales).")

    def control_mqtt(self, device: str, action: str) -> str:
        """Controla un dispositivo vía MQTT."""
        if not self.client:
            return "MQTT no disponible. Instala paho-mqtt y configura el broker."
        topic = f"home/{device}/command"
        self.client.publish(topic, action)
        return f"Comando '{action}' enviado a {device} (MQTT)."

    def control_hue(self, light_id: int, action: str, brightness: int = None) -> str:
        """Controla una luz Philips Hue."""
        if not self._hue_bridge:
            return "Philips Hue no disponible. Instala phue y configura HUE_BRIDGE_IP."
        try:
            if action == "toggle":
                # Obtener estado actual y alternar
                state = self._hue_bridge.get_light(light_id, 'on')
                self._hue_bridge.set_light(light_id, 'on', not state)
            else:
                self._hue_bridge.set_light(light_id, 'on', action == "on")
            if brightness is not None:
                self._hue_bridge.set_light(light_id, 'bri', brightness)
            return f"Luz {light_id} {'encendida' if action in ('on','toggle') and action!='off' else 'apagada'}."
        except Exception as e:
            return f"Error Hue: {e}"

    def control_home_assistant(self, entity_id: str, action: str) -> str:
        """Controla un dispositivo en Home Assistant."""
        if not self._ha_token:
            return "Home Assistant no configurado. Define HA_TOKEN."
        try:
            import requests
            url = f"{self._ha_url}/api/services/homeassistant/turn_{'on' if action == 'on' else 'off'}"
            if action == "toggle":
                # Toggle no soportado directamente, consultar estado primero
                state_url = f"{self._ha_url}/api/states/{entity_id}"
                headers = {"Authorization": f"Bearer {self._ha_token}"}
                resp = requests.get(state_url, headers=headers)
                if resp.status_code == 200:
                    state = resp.json().get('state', 'off')
                    new_action = 'off' if state == 'on' else 'on'
                    return self.control_home_assistant(entity_id, new_action)
                else:
                    return f"Error al obtener estado de {entity_id}"
            headers = {
                "Authorization": f"Bearer {self._ha_token}",
                "Content-Type": "application/json"
            }
            requests.post(url, json={"entity_id": entity_id}, headers=headers, timeout=5)
            return f"Dispositivo {entity_id} {'encendido' if action == 'on' else 'apagado'}."
        except Exception as e:
            return f"Error HA: {e}"

    def control_tuya(self, action: str) -> str:
        """Controla un dispositivo Tuya."""
        if not self._tuya_device_id or not self._tuya_device_key:
            return "Tuya no configurado. Define TUYA_DEVICE_ID y TUYA_DEVICE_KEY."
        try:
            import tinytuya
            # Asumimos un dispositivo tipo enchufe/outlet
            d = tinytuya.OutletDevice(
                self._tuya_device_id,
                os.getenv("TUYA_DEVICE_IP", "192.168.1.100"),
                self._tuya_device_key
            )
            d.set_version(3.3)
            if action == "on":
                d.turn_on()
            elif action == "off":
                d.turn_off()
            elif action == "toggle":
                # Obtener estado actual y alternar
                status = d.status()
                current = status.get('dps', {}).get('1', False)  # DPS 1 suele ser el relé
                d.turn_on() if not current else d.turn_off()
            else:
                return f"Acción Tuya '{action}' no soportada."
            return f"Tuya: {action}."
        except ImportError:
            return "tinytuya no instalado. Instala: pip install tinytuya"
        except Exception as e:
            return f"Error Tuya: {e}"

    def control_device(self, platform: str, device: str, action: str, **kwargs) -> str:
        """Punto de entrada unificado para control de dispositivos."""
        platform = platform.lower()
        if platform == "mqtt":
            return self.control_mqtt(device, action)
        elif platform == "hue":
            try:
                light_id = int(device)
            except ValueError:
                return f"ID de luz inválido: {device}"
            brightness = kwargs.get("brightness")
            return self.control_hue(light_id, action, brightness)
        elif platform == "homeassistant":
            return self.control_home_assistant(device, action)
        elif platform == "tuya":
            return self.control_tuya(action)
        else:
            return f"Plataforma '{platform}' no soportada. Opciones: mqtt, hue, homeassistant, tuya"

# ===== FUNCIÓN EXPORTABLE =====
def iot_control(parameters: dict, player=None, speak=None) -> str:
    """Herramienta de control IoT."""
    platform = parameters.get("platform", "mqtt")
    device = parameters.get("device", "")
    action = parameters.get("action", "toggle")
    brightness = parameters.get("brightness")
    controller = IoTController()
    result = controller.control_device(platform, device, action, brightness=brightness)
    if speak:
        speak(result)
    return result