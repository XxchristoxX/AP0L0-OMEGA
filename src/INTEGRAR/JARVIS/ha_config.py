# ============================================================
#  ha_config.py — Configuración Home Assistant y Clima
#  Personalice ESTE archivo según su instalación domótica
#  No toque main2.py para la domótica, todo está aquí.
#  Sitio: www.techenclair.fr
# ============================================================

import os
import json
import requests
import asyncio
from datetime import datetime
from dotenv import load_dotenv

def _cargar_nombre_usuario():
    try:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        with open(_p, "r", encoding="utf-8") as _f:
            return json.load(_f).get("user_name", "Christopher")
    except Exception:
        return "Christopher"

_USUARIO = _cargar_nombre_usuario().lower()

def _actualizar_ha_env():
    global HA_URL, HA_TOKEN, HA_HEADERS
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)
    HA_URL    = os.getenv("HA_URL", "").rstrip("/")
    HA_TOKEN  = os.getenv("HA_TOKEN", "")
    HA_HEADERS = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type" : "application/json"
    }

# Carga inicial
HA_URL = ""
HA_TOKEN = ""
HA_HEADERS = {}
_actualizar_ha_env()

# ═══════════════════════════════════════════════════════════════
#  SECCIÓN 1 — CLIMA POR DEFECTO
#  Reemplace con su ciudad y sus coordenadas GPS.
#  Coordenadas: https://www.latlong.net/
# ═══════════════════════════════════════════════════════════════
CIUDAD_POR_DEFECTO = "Amilly"   # ← Su ciudad
LAT_POR_DEFECTO   = 47.9742    # ← Latitud
LON_POR_DEFECTO   = 2.7708     # ← Longitud

def recargar_valores_config():
    global CIUDAD_POR_DEFECTO, LAT_POR_DEFECTO, LON_POR_DEFECTO
    try:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        if os.path.exists(_p):
            with open(_p, "r", encoding="utf-8") as _f:
                cfg = json.load(_f)
                if "user_city" in cfg and cfg["user_city"]:
                    CIUDAD_POR_DEFECTO = cfg["user_city"]
                if "user_lat" in cfg and cfg["user_lat"] is not None:
                    LAT_POR_DEFECTO = float(cfg["user_lat"])
                if "user_lon" in cfg and cfg["user_lon"] is not None:
                    LON_POR_DEFECTO = float(cfg["user_lon"])
    except Exception as e:
        print(f"[HA_CONFIG] Error al recargar valores: {e}")

recargar_valores_config()

# ═══════════════════════════════════════════════════════════════
#  SECCIÓN 2 — LUCES
#  Formato: "nombre vocal" : "entity_id Home Assistant"
#  Para encontrar un entity_id: HA → Configuración → Dispositivos
#    → haga clic en la entidad → "Información de la entidad"
# ═══════════════════════════════════════════════════════════════
PIEZAS_LUCES = {
    # Salón
    "salon"            : "light.salon",
    "techo salon"      : "light.plafond",
    "sofas"            : "light.canapes",
    "lampara de pie"   : "light.lampadaire",
    "lampara de noche" : "light.lampe_de_chevet_2",
    "bola grande"      : "light.grosse_boule",
    "bola pequeña"     : "light.petite_boule",

    # Cocina
    "cocina"           : "light.lsc_smart_led_strip_rgbic_cctic_5m",
    "cocina 2"         : "light.cuisine_2",

    # Christopher
    "christopher"          : "light.pc_3",
    "pc christopher"       : "light.pc_3",

    # Oficina
    "oficina"          : "light.bureau",
    "pc"               : "light.pc",
    "pc 2"             : "light.pc_2",

    # Padres
    "padres"           : "light.chambre_parentale",
    "habitacion padres": "light.chambre_parentale",
    "habitacion"       : "light.chambre_parentale",
    "techo habitacion" : "light.plafond_2",

    # Globales
    "todas"            : "light.all",
    "todo"             : "light.all",
}

# ═══════════════════════════════════════════════════════════════
#  SECCIÓN 3 — ENCHUFES INTELIGENTES
#  Formato: "nombre vocal" : "entity_id switch.xxx"
# ═══════════════════════════════════════════════════════════════
PIEZAS_ENCHUFES = {
    "salon"   : "switch.prise_salon",
    "oficina" : "switch.prise_bureau",
    "cocina"  : "switch.prise_cuisine",
}

# ═══════════════════════════════════════════════════════════════
#  SECCIÓN 4 — SENSORES DE TEMPERATURA Y DIVERSOS
#  Formato: "nombre vocal" : "entity_id sensor.xxx"
#  Puede agregar tantas piezas como sea necesario.
# ═══════════════════════════════════════════════════════════════
PIEZAS_SENSORES = {
    "salon"        : "sensor.salon_temperature_2",
    "habitacion"   : "sensor.miaomiaoc_de_blt_4_14kc52pmcgk00_t2_temperature_p_2_1",
    "oficina"      : "sensor.temp_temperature",
    "exterior"     : "sensor.temperature_exterieure",
    "fuera"        : "sensor.temperature_exterieure",
    "consumo"      : "sensor.lixee_zlinky_tic_puissance_apparente",
    "tiktok"       : "sensor.tiktok_followers_techenclair",
    "huevos"       : "input_select.ramassage_des_oeufs",
}

# ═══════════════════════════════════════════════════════════════
#  SECCIÓN 5 — SENSORES DE HUMEDAD
#  Formato: "nombre vocal" : "entity_id sensor.xxx"
# ═══════════════════════════════════════════════════════════════
PIEZAS_HUMEDAD = {
    "oficina" : "sensor.temp_humidite",
}

# ═══════════════════════════════════════════════════════════════
#  SECCIÓN 6 — TARIFAS ELÉCTRICAS (€/kWh)
#  Adapte según su contrato EDF / proveedor
#  p1-p6 = rangos tarifarios Linky (horas valle, punta, etc.)
# ═══════════════════════════════════════════════════════════════
HA_TARIFAS = {
    "p1": 0.1296,
    "p2": 0.1603,
    "p3": 0.1486,
    "p4": 0.1894,
    "p5": 0.1568,
    "p6": 0.7562,
}

# ═══════════════════════════════════════════════════════════════
#  SECCIÓN 7 — SEGUIMIENTO DE ENERGÍA POR DISPOSITIVO
#  Formato: "nombre vocal" : "entity_id sensor.xxx_mensual"
# ═══════════════════════════════════════════════════════════════
DISPOSITIVOS_ENERGIA = {
    "tv"             : "sensor.prise_1_salon_mensuel",
    "salon"          : "sensor.prise_1_salon_mensuel",
    "pc christopher"     : "sensor.prise_3_pc_christopher_mensuel",
    "christopher"        : "sensor.prise_3_pc_christopher_mensuel",
    "zoe"            : "sensor.zoe_mensuel",
    "coche"          : "sensor.zoe_mensuel",
    "lavavajillas"   : "sensor.prise_2_lave_vaisselle_mensuel",
    "pc salon"       : "sensor.pc_salon_conso_pc_salon_mensuel_2",
    "oficina"        : "sensor.bureau_mensuel",
}

# ═══════════════════════════════════════════════════════════════
#  SECCIÓN 8 — BATERÍAS DE DISPOSITIVOS
#  Formato: "nombre vocal" : "entity_id sensor.xxx_battery_level"
# ═══════════════════════════════════════════════════════════════
DISPOSITIVOS_BATERIA = {
    "mi telefono"        : "sensor.sm_s921b_battery_level",
    "christopher"        : "sensor.sm_s921b_battery_level",
    _USUARIO             : "sensor.sm_s921b_battery_level",
    "samsung christopher": "sensor.sm_s921b_battery_level",
    "christopher"        : "sensor.sm_christopher_battery_level",
    "mama"               : "sensor.sm_christopher_battery_level",
    "samsung mama"       : "sensor.sm_christopher_battery_level",
    "christopher"        : "sensor.christopher_battery_level",
    "honor"              : "sensor.honor_battery_level",
    "tablet honor"       : "sensor.honor_battery_level",
    "reloj christopher"  : "sensor.galaxy_watch6_classic_d4he_battery_level",
    f"reloj {_USUARIO}"  : "sensor.galaxy_watch6_classic_d4he_battery_level",
    "reloj mama"         : "sensor.galaxy_watch8_fbxh_battery_level",
    "reloj christopher"  : "sensor.galaxy_watch8_fbxh_battery_level",
    "bob"                : "sensor.bob_batterie",
    "aspirador bob"      : "sensor.bob_batterie",
    "dyad"               : "sensor.dyad_air_2024_batterie",
    "aspirador dyad"     : "sensor.dyad_air_2024_batterie",
    "mando hue"          : "sensor.maison_interrupteur_batterie",
    "interruptor"        : "sensor.maison_interrupteur_batterie",
    "toner"              : "sensor.samsung_m2020_series_black_toner_s_n_crum_17091625519",
    "impresora"          : "sensor.samsung_m2020_series_black_toner_s_n_crum_17091625519",
    "buzón"              : "sensor.detecterur_batterie",
    "detector cocina"    : "sensor.detecteur_1_batterie",
    "detector escalera"  : "sensor.detecteur_2_batterie",
    "camara jardin"      : "sensor.arriere_cour_battery_percentage",
    "termometro oficina" : "sensor.temp_batterie",
}

# ═══════════════════════════════════════════════════════════════
#  SECCIÓN 9 — COLORES RGB
#  Formato: "nombre vocal" : [R, G, B]
#  Puede agregar sus propios colores.
# ═══════════════════════════════════════════════════════════════
MAP_COLORES = {
    "rojo"     : [255, 0,   0  ],
    "azul"     : [0,   0,   255],
    "verde"    : [0,   255, 0  ],
    "blanco"   : [255, 255, 255],
    "naranja"  : [255, 140, 0  ],
    "violeta"  : [148, 0,   211],
    "rosa"     : [255, 20,  147],
    "amarillo" : [255, 255, 0  ],
    "cian"     : [0,   255, 255],
    "magenta"  : [255, 0,   255],
    "turquesa" : [64,  224, 208],
    "oro"      : [255, 215, 0  ],
    "plata"    : [192, 192, 192],
    "añil"     : [75,  0,   130],
    "marrón"   : [139, 69,  19 ],
    "limón"    : [255, 250, 0  ],
    "coral"    : [255, 127, 80 ],
    "lavanda"  : [230, 230, 250],
}

# ── Códigos de clima Open-Meteo (no modificar) ─────────────────
CODIGOS_CLIMA = {
    0:  "despejado",
    1:  "principalmente despejado", 2: "parcialmente nublado", 3: "nublado",
    45: "niebla", 48: "niebla helada",
    51: "llovizna ligera", 53: "llovizna moderada", 55: "llovizna densa",
    61: "lluvia débil", 63: "lluvia moderada", 65: "lluvia fuerte",
    71: "nieve débil", 73: "nieve moderada", 75: "nieve fuerte",
    80: "chubascos débiles", 81: "chubascos moderados", 82: "chubascos violentos",
    85: "chubascos de nieve", 86: "chubascos de nieve fuertes",
    95: "tormenta", 96: "tormenta con granizo", 99: "tormenta violenta con granizo",
}

# ════════════════════════════════════════════════════════════════
#  ENTIDADES HOME ASSISTANT PERSONALIZADAS (cargadas desde jarvis_config.json)
#  Recargado automáticamente en cada guardado en la configuración.
# ════════════════════════════════════════════════════════════════

_HA_KEYS_PERSONALIZADAS: dict = {"luces": set(), "enchufes": set(), "sensores": set()}

def _cargar_entidades_ha_personalizadas():
    global _HA_KEYS_PERSONALIZADAS
    _actualizar_ha_env()
    for k in _HA_KEYS_PERSONALIZADAS["luces"]:
        PIEZAS_LUCES.pop(k, None)
    for k in _HA_KEYS_PERSONALIZADAS["enchufes"]:
        PIEZAS_ENCHUFES.pop(k, None)
    for k in _HA_KEYS_PERSONALIZADAS["sensores"]:
        PIEZAS_SENSORES.pop(k, None)
    _HA_KEYS_PERSONALIZADAS = {"luces": set(), "enchufes": set(), "sensores": set()}
    try:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        with open(_p, "r", encoding="utf-8") as _f:
            _cfg = json.load(_f)
        custom = _cfg.get("ha_custom_entities", {})
        for entry in custom.get("luces", []):
            nom = entry["nom"].lower().strip()
            PIEZAS_LUCES[nom] = entry["entity_id"]
            _HA_KEYS_PERSONALIZADAS["luces"].add(nom)
        for entry in custom.get("enchufes", []):
            nom = entry["nom"].lower().strip()
            PIEZAS_ENCHUFES[nom] = entry["entity_id"]
            _HA_KEYS_PERSONALIZADAS["enchufes"].add(nom)
        for entry in custom.get("sensores", []):
            nom = entry["nom"].lower().strip()
            PIEZAS_SENSORES[nom] = entry["entity_id"]
            _HA_KEYS_PERSONALIZADAS["sensores"].add(nom)
    except Exception:
        pass

_cargar_entidades_ha_personalizadas()

# ════════════════════════════════════════════════════════════════
#  FUNCIONES API HOME ASSISTANT
#  No modifique estas funciones: llaman a la API de HA.
# ════════════════════════════════════════════════════════════════

def ha_llamar_servicio(dominio, servicio, entity_id, datos=None):
    _actualizar_ha_env()
    try:
        payload = {"entity_id": entity_id}
        if datos:
            payload.update(datos)
        print(f"[HA DEBUG] Llamando a {dominio}/{servicio} para {entity_id} con {datos}")
        r = requests.post(
            f"{HA_URL}/api/services/{dominio}/{servicio}",
            headers=HA_HEADERS, json=payload, timeout=5
        )
        print(f"[HA DEBUG] Respuesta {r.status_code}: {r.text}")
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[HA] Error al llamar al servicio: {e}")
        return False

def ha_obtener_estado(entity_id, atributo=None):
    _actualizar_ha_env()
    try:
        url = f"{HA_URL}/api/states/{entity_id}"
        print(f"[HA DEBUG] GET {url}")
        r = requests.get(url, headers=HA_HEADERS, timeout=5)
        print(f"[HA DEBUG] Estado={r.status_code}  Cuerpo={r.text[:200]!r}")
        data = r.json()
        if atributo:
            return data.get("attributes", {}).get(atributo, "desconocido")
        return data.get("state", "desconocido")
    except Exception as e:
        print(f"[HA] Error al obtener estado: {e}")
        return "desconocido"

def ha_obtener_calendario(entity_id):
    _actualizar_ha_env()
    try:
        ahora = datetime.now()
        inicio = ahora.strftime("%Y-%m-%dT00:00:00Z")
        fin = ahora.strftime("%Y-%m-%dT23:59:59Z")
        r = requests.get(
            f"{HA_URL}/api/calendars/{entity_id}",
            headers=HA_HEADERS,
            params={"start": inicio, "end": fin},
            timeout=5
        )
        return r.json()
    except Exception as e:
        print(f"[HA] Error al obtener calendario: {e}")
        return []

def ha_luz(entity_id, estado="on", luminosidad=None, rgb=None):
    nombre_servicio = "toggle" if estado == "toggle" else ("turn_on" if estado == "on" else "turn_off")
    datos = {}
    if estado == "on":
        if luminosidad is not None:
            datos["brightness"] = int(luminosidad)
        if rgb is not None:
            datos["rgb_color"] = rgb
    return ha_llamar_servicio("light", nombre_servicio, entity_id, datos)

def ha_enchufe(entity_id, estado="on"):
    nombre_servicio = "turn_on" if estado == "on" else "turn_off"
    return ha_llamar_servicio("switch", nombre_servicio, entity_id)

def ha_termostato(entity_id, temperatura):
    return ha_llamar_servicio("climate", "set_temperature", entity_id, {"temperature": temperatura})

def ha_escena(scene_id):
    return ha_llamar_servicio("scene", "turn_on", scene_id)

def ha_cerradura(entity_id, estado="lock"):
    nombre_servicio = "lock" if estado == "lock" else "unlock"
    return ha_llamar_servicio("lock", nombre_servicio, entity_id)

# ════════════════════════════════════════════════════════════════
#  FUNCIONES CLIMA
#  Usan Open-Meteo (gratuito) + Home Assistant como respaldo.
# ════════════════════════════════════════════════════════════════

def geocodificar_ciudad(ciudad):
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": ciudad, "count": 1, "language": "es", "format": "json"},
            timeout=5
        )
        data = r.json()
        if data.get("results"):
            res = data["results"][0]
            return res["latitude"], res["longitude"], res.get("name", ciudad), res.get("country", "")
    except Exception as e:
        print(f"[CLIMA] Error de geocodificación: {e}")
    return None, None, ciudad, ""

def obtener_clima_estructurado(ciudad=None):
    """Devuelve los datos climáticos estructurados para el panel visual frontend."""
    try:
        nombre_ciudad = ciudad or CIUDAD_POR_DEFECTO
        lat, lon, nombre_mostrar, pais = geocodificar_ciudad(nombre_ciudad)
        if lat is None:
            lat, lon = LAT_POR_DEFECTO, LON_POR_DEFECTO
            nombre_mostrar = CIUDAD_POR_DEFECTO
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude" : lat, "longitude": lon,
                "current"  : "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weathercode",
                "timezone" : "Europe/Paris",
            },
            timeout=8
        )
        cur  = r.json()["current"]
        code = cur.get("weathercode", 0)
        return {
            "ciudad"     : nombre_mostrar,
            "temperatura": round(float(cur.get("temperature_2m", 0))),
            "sensacion"  : round(float(cur.get("apparent_temperature", 0))),
            "humedad"    : round(float(cur.get("relative_humidity_2m", 0))),
            "viento"     : round(float(cur.get("wind_speed_10m", 0))),
            "code"       : code,
            "descripcion": CODIGOS_CLIMA.get(code, "desconocido"),
        }
    except Exception as e:
        print(f"[CLIMA_DATA] Error: {e}")
        return None

def obtener_clima_actual(ciudad=None):
    try:
        nombre_ciudad = ciudad or CIUDAD_POR_DEFECTO
        lat, lon, nombre_mostrar, pais = geocodificar_ciudad(nombre_ciudad)
        if lat is None:
            lat, lon = LAT_POR_DEFECTO, LON_POR_DEFECTO
            nombre_mostrar = CIUDAD_POR_DEFECTO
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude"       : lat, "longitude": lon,
                "current"        : "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,wind_direction_10m,weathercode,precipitation",
                "hourly"         : "temperature_2m,precipitation_probability",
                "daily"          : "temperature_2m_max,temperature_2m_min,weathercode,precipitation_sum,wind_speed_10m_max,sunrise,sunset",
                "timezone"       : "Europe/Paris",
                "forecast_days"  : 3,
                "wind_speed_unit": "kmh",
            },
            timeout=8
        )
        data = r.json()
        cur  = data["current"]
        code = cur.get("weathercode", 0)
        desc = CODIGOS_CLIMA.get(code, "condiciones desconocidas")
        temp = round(float(cur.get("temperature_2m", 0)))
        return f"En {nombre_mostrar}, hace {temp} grados y el cielo está {desc}. Eso es todo."
    except Exception as e:
        print(f"[CLIMA] Error: {e}")
        return "No puedo obtener el clima en este momento."

def obtener_clima_ha():
    """Lee el clima desde Home Assistant. Respaldo cuando Gemini falla."""
    _actualizar_ha_env()
    try:
        r    = requests.get(f"{HA_URL}/api/states/weather.forecast_amilly", headers=HA_HEADERS, timeout=5)
        data = r.json()
        estado  = data.get("state", "desconocido")
        attrs = data.get("attributes", {})
        temp     = attrs.get("temperature", "?")
        humedad = attrs.get("humidity", None)
        viento     = attrs.get("wind_speed", None)
        estados_es = {
            "sunny"          : "soleado",
            "clear-night"    : "despejado",
            "partlycloudy"   : "parcialmente nublado",
            "cloudy"         : "nublado",
            "rainy"          : "lluvioso",
            "pouring"        : "fuertemente lluvioso",
            "snowy"          : "nevado",
            "snowy-rainy"    : "lluvia y nieve mezcladas",
            "windy"          : "ventoso",
            "windy-variant"  : "muy ventoso",
            "fog"            : "brumoso",
            "hail"           : "granizo",
            "lightning"      : "tormentoso",
            "lightning-rainy": "tormenta y lluvia",
            "exceptional"    : "condiciones excepcionales",
        }
        desc    = estados_es.get(estado, estado)
        respuesta = f"En {CIUDAD_POR_DEFECTO}, hace {temp} grados y el cielo está {desc}"
        if humedad:
            respuesta += f", humedad al {humedad}%"
        if viento:
            respuesta += f", viento de {viento} km/h"
        respuesta += f", {_cargar_nombre_usuario()}."
        return respuesta
    except Exception as e:
        print(f"[CLIMA HA] Error: {e}")
        return None

def obtener_alertas_clima(ciudad=None):
    try:
        nombre_ciudad = ciudad or CIUDAD_POR_DEFECTO
        lat, lon, nombre_mostrar, _ = geocodificar_ciudad(nombre_ciudad)
        if lat is None:
            lat, lon, nombre_mostrar = LAT_POR_DEFECTO, LON_POR_DEFECTO, CIUDAD_POR_DEFECTO
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "daily"   : "weathercode,precipitation_sum,wind_speed_10m_max",
                "timezone": "Europe/Paris", "forecast_days": 3,
            },
            timeout=8
        )
        data    = r.json()
        daily   = data["daily"]
        alertas = []
        for i in range(len(daily["weathercode"])):
            code  = daily["weathercode"][i]
            lluvia = daily.get("precipitation_sum", [0]*3)[i] or 0
            viento  = daily.get("wind_speed_10m_max", [0]*3)[i] or 0
            dia  = ["hoy", "mañana", "pasado mañana"][i]
            if code in [95, 96, 99]:
                alertas.append(f"Tormenta prevista {dia}")
            if code in [71, 73, 75, 85, 86]:
                alertas.append(f"Nieve prevista {dia}")
            if lluvia > 20:
                alertas.append(f"Fuertes lluvias {dia} ({lluvia}mm)")
            if viento > 60:
                alertas.append(f"Vientos fuertes {dia} ({viento} km/h)")
        if alertas:
            return f"Alertas climáticas para {nombre_mostrar}: " + ", ".join(alertas) + "."
        return f"No hay alertas climáticas para {nombre_mostrar} en los próximos 3 días."
    except Exception as e:
        return f"No se pudieron verificar las alertas climáticas: {e}"


# ════════════════════════════════════════════════════════════════
#  NUEVOS SERVICIOS - PANEL DE CONTROL CENTRAL DE DOMÓTICA
# ════════════════════════════════════════════════════════════════

def ha_obtener_todos_estados() -> list:
    """Recupera todos los estados de las entidades de Home Assistant."""
    _actualizar_ha_env()
    try:
        url = f"{HA_URL}/api/states"
        print(f"[HA] Recuperando todos los estados desde {url}")
        r = requests.get(url, headers=HA_HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"[HA] Fallo al recuperar estados. Código: {r.status_code}")
            return []
    except Exception as e:
        print(f"[HA] Error al recuperar todos los estados: {e}")
        return []

def ha_obtener_estado_completo(entity_id: str) -> dict | None:
    """Recupera el estado completo de una entidad específica."""
    _actualizar_ha_env()
    try:
        url = f"{HA_URL}/api/states/{entity_id}"
        r = requests.get(url, headers=HA_HEADERS, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[HA] Error en ha_obtener_estado_completo para {entity_id}: {e}")
    return None

async def manejar_mensaje_ha_ws(data: dict, websocket, clientes_conectados: set) -> bool:
    """Maneja los mensajes WebSocket relacionados con Home Assistant."""
    tipo_msg = data.get("type", "")

    if tipo_msg == "ha_get_states":
        estados = await asyncio.to_thread(ha_obtener_todos_estados)
        await websocket.send(json.dumps({
            "type": "ha_states",
            "success": len(estados) > 0 or HA_URL != "",
            "states": estados
        }))
        return True

    elif tipo_msg == "ha_call_service":
        dominio = data.get("domain", "")
        servicio = data.get("service", "")
        entity_id = data.get("entity_id", "")
        datos_servicio = data.get("service_data", None)

        exito = await asyncio.to_thread(ha_llamar_servicio, dominio, servicio, entity_id, datos_servicio)

        estado_actualizado = None
        if exito:
            estado_actualizado = await asyncio.to_thread(ha_obtener_estado_completo, entity_id)

        await websocket.send(json.dumps({
            "type": "ha_service_result",
            "success": exito,
            "entity_id": entity_id,
            "state": estado_actualizado
        }))

        # Difundir el cambio de estado a todos los clientes conectados para sincronizar la UI
        if exito and estado_actualizado:
            await _broadcast_ha(clientes_conectados, {
                "type": "ha_state_changed",
                "entity_id": entity_id,
                "state": estado_actualizado
            })
        return True

    return False

async def _broadcast_ha(clientes: set, mensaje: dict):
    if not clientes:
        return
    msg = json.dumps(mensaje)
    try:
        await asyncio.gather(*[c.send(msg) for c in clientes], return_exceptions=True)
    except Exception as e:
        print(f"[HA-WS] Error al difundir: {e}")