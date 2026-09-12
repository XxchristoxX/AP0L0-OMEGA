# src/actions/ha_config.py
"""
Configuración de Home Assistant y Meteorología para AP0L0
Fusionado con la versión de JARVIS
"""

import os
import json
import requests
import asyncio
from datetime import datetime
import random

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "api_keys.json")

# ===== FUNCIONES DE CONFIGURACIÓN =====
def _load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_config(config):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

def _get_user_name():
    return _load_config().get("user_name", "Christopher")

USER_NAME = _get_user_name()

# ===== CONFIGURACIÓN HA =====
def _load_ha_env():
    global HA_URL, HA_TOKEN, HA_HEADERS
    cfg = _load_config()
    HA_URL = cfg.get("ha_url", "").rstrip("/")
    HA_TOKEN = cfg.get("ha_token", "")
    HA_HEADERS = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }

HA_URL = ""
HA_TOKEN = ""
HA_HEADERS = {}
_load_ha_env()

# ===== METEOROLOGÍA POR DEFECTO =====
VILLE_PAR_DEFAUT = "Amilly"
LAT_PAR_DEFAUT = 47.9742
LON_PAR_DEFAUT = 2.7708

def reload_config_values():
    global VILLE_PAR_DEFAUT, LAT_PAR_DEFAUT, LON_PAR_DEFAUT
    cfg = _load_config()
    VILLE_PAR_DEFAUT = cfg.get("user_city", "Amilly")
    LAT_PAR_DEFAUT = cfg.get("user_lat", 47.9742)
    LON_PAR_DEFAUT = cfg.get("user_lon", 2.7708)
reload_config_values()

# ===== DISPOSITIVOS HA =====
PIECES_LUMIERES = {
    "salon": "light.salon",
    "plafond salon": "light.plafond",
    "canapes": "light.canapes",
    "lampadaire": "light.lampadaire",
    "cuisine": "light.lsc_smart_led_strip_rgbic_cctic_5m",
    "christopher": "light.pc_3",
    "bureau": "light.bureau",
    "pc": "light.pc",
    "parents": "light.chambre_parentale",
    "chambre": "light.chambre_parentale",
    "toutes": "light.all",
    "tout": "light.all"
}

PIECES_PRISES = {
    "salon": "switch.prise_salon",
    "bureau": "switch.prise_bureau",
    "cuisine": "switch.prise_cuisine"
}

PIECES_CAPTEURS = {
    "salon": "sensor.salon_temperature_2",
    "chambre": "sensor.miaomiaoc_de_blt_4_14kc52pmcgk00_t2_temperature_p_2_1",
    "bureau": "sensor.temp_temperature",
    "exterieur": "sensor.temperature_exterieure",
    "dehors": "sensor.temperature_exterieure",
    "consommation": "sensor.lixee_zlinky_tic_puissance_apparente",
    "tiktok": "sensor.tiktok_followers_techenclair",
    "oeufs": "input_select.ramassage_des_oeufs"
}

PIECES_HUMIDITE = {
    "bureau": "sensor.temp_humidite"
}

HA_TARIFS = {
    "p1": 0.1296, "p2": 0.1603, "p3": 0.1486,
    "p4": 0.1894, "p5": 0.1568, "p6": 0.7562
}

APPAREILS_ENERGIE = {
    "tv": "sensor.prise_1_salon_mensuel",
    "salon": "sensor.prise_1_salon_mensuel",
    "christopher": "sensor.prise_3_pc_christopher_mensuel",
    "pc": "sensor.prise_3_pc_christopher_mensuel",
    "zoe": "sensor.zoe_mensuel",
    "voiture": "sensor.zoe_mensuel",
    "lave-vaisselle": "sensor.prise_2_lave_vaisselle_mensuel",
    "bureau": "sensor.bureau_mensuel"
}

APPAREILS_BATTERIE = {
    "mon telephone": "sensor.sm_s921b_battery_level",
    "christopher": "sensor.sm_christopher_battery_level",
    "maman": "sensor.sm_christopher_battery_level",
    "honor": "sensor.honor_battery_level",
    "montre christopher": "sensor.galaxy_watch6_classic_d4he_battery_level",
    "montre maman": "sensor.galaxy_watch8_fbxh_battery_level",
    "bob": "sensor.bob_batterie",
    "aspirateur bob": "sensor.bob_batterie",
    "dyad": "sensor.dyad_air_2024_batterie",
    "telecommande hue": "sensor.maison_interrupteur_batterie",
    "toner": "sensor.samsung_m2020_series_black_toner_s_n_crum_17091625519",
    "imprimante": "sensor.samsung_m2020_series_black_toner_s_n_crum_17091625519"
}

COULEURS_MAP = {
    "rouge": [255,0,0], "bleu": [0,0,255], "vert": [0,255,0],
    "blanc": [255,255,255], "orange": [255,140,0], "violet": [148,0,211],
    "rose": [255,20,147], "jaune": [255,255,0], "cyan": [0,255,255],
    "magenta": [255,0,255], "turquoise": [64,224,208], "or": [255,215,0]
}

CODES_METEO = {
    0: "despejado", 1: "mayormente claro", 2: "parcialmente nublado",
    3: "nublado", 45: "niebla", 48: "niebla helada",
    51: "llovizna ligera", 53: "llovizna moderada", 55: "llovizna densa",
    61: "lluvia ligera", 63: "lluvia moderada", 65: "lluvia fuerte",
    71: "nieve ligera", 73: "nieve moderada", 75: "nieve fuerte",
    80: "chubascos ligeros", 81: "chubascos moderados", 82: "chubascos violentos",
    85: "chubascos de nieve", 86: "chubascos de nieve fuertes",
    95: "tormenta", 96: "tormenta con granizo", 99: "tormenta violenta"
}

# ===== FUNCIONES API HA =====

def ha_appeler_service(domaine, service, entity_id, donnees=None):
    _load_ha_env()
    try:
        payload = {"entity_id": entity_id}
        if donnees:
            payload.update(donnees)
        r = requests.post(
            f"{HA_URL}/api/services/{domaine}/{service}",
            headers=HA_HEADERS, json=payload, timeout=5
        )
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[HA] Error llamando servicio: {e}")
        return False


def ha_get_etat(entity_id, attribut=None):
    _load_ha_env()
    try:
        r = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=HA_HEADERS, timeout=5)
        data = r.json()
        if attribut:
            return data.get("attributes", {}).get(attribut, "inconnu")
        return data.get("state", "inconnu")
    except Exception:
        return "inconnu"


def ha_lumiere(entity_id, etat="on", luminosite=None, rgb=None):
    service_name = "toggle" if etat == "toggle" else ("turn_on" if etat == "on" else "turn_off")
    donnees = {}
    if etat == "on":
        if luminosite is not None:
            donnees["brightness"] = int(luminosite)
        if rgb is not None:
            donnees["rgb_color"] = rgb
    return ha_appeler_service("light", service_name, entity_id, donnees)


def ha_interrupteur(entity_id, etat="on"):
    service_name = "turn_on" if etat == "on" else "turn_off"
    return ha_appeler_service("switch", service_name, entity_id)


def ha_thermostat(entity_id, temperature):
    return ha_appeler_service("climate", "set_temperature", entity_id, {"temperature": temperature})


def ha_scene(scene_id):
    return ha_appeler_service("scene", "turn_on", scene_id)


def ha_verrou(entity_id, etat="lock"):
    service_name = "lock" if etat == "lock" else "unlock"
    return ha_appeler_service("lock", service_name, entity_id)

# ===== METEO =====

def geocoder_ville(ville):
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": ville, "count": 1, "language": "fr", "format": "json"},
            timeout=5
        )
        data = r.json()
        if data.get("results"):
            res = data["results"][0]
            return res["latitude"], res["longitude"], res.get("name", ville), res.get("country", "")
    except Exception:
        pass
    return None, None, ville, ""


def get_meteo_structuree(ville=None):
    try:
        nom_ville = ville or VILLE_PAR_DEFAUT
        lat, lon, nom_affiche, pays = geocoder_ville(nom_ville)
        if lat is None:
            lat, lon = LAT_PAR_DEFAUT, LON_PAR_DEFAUT
            nom_affiche = VILLE_PAR_DEFAUT
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weathercode",
                "timezone": "Europe/Paris",
            },
            timeout=8
        )
        cur = r.json()["current"]
        code = cur.get("weathercode", 0)
        return {
            "ville": nom_affiche,
            "temperature": round(float(cur.get("temperature_2m", 0))),
            "ressenti": round(float(cur.get("apparent_temperature", 0))),
            "humidite": round(float(cur.get("relative_humidity_2m", 0))),
            "vent": round(float(cur.get("wind_speed_10m", 0))),
            "code": code,
            "description": CODES_METEO.get(code, "inconnu")
        }
    except Exception as e:
        print(f"[METEO] Error: {e}")
        return None


def get_meteo_actuelle(ville=None):
    try:
        nom_ville = ville or VILLE_PAR_DEFAUT
        lat, lon, nom_affiche, pays = geocoder_ville(nom_ville)
        if lat is None:
            lat, lon = LAT_PAR_DEFAUT, LON_PAR_DEFAUT
            nom_affiche = VILLE_PAR_DEFAUT
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weathercode",
                "timezone": "Europe/Paris",
            },
            timeout=8
        )
        cur = r.json()["current"]
        code = cur.get("weathercode", 0)
        desc = CODES_METEO.get(code, "condiciones desconocidas")
        temp = round(float(cur.get("temperature_2m", 0)))
        return f"En {nom_affiche}, {temp}°C, cielo {desc}."
    except Exception:
        return "No pude obtener el clima."


def get_alertes_meteo(ville=None):
    try:
        nom_ville = ville or VILLE_PAR_DEFAUT
        lat, lon, nom_affiche, _ = geocoder_ville(nom_ville)
        if lat is None:
            lat, lon, nom_affiche = LAT_PAR_DEFAUT, LON_PAR_DEFAUT, VILLE_PAR_DEFAUT
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "daily": "weathercode,precipitation_sum,wind_speed_10m_max",
                "timezone": "Europe/Paris", "forecast_days": 3,
            },
            timeout=8
        )
        daily = r.json()["daily"]
        alertes = []
        jours = ["hoy", "mañana", "pasado mañana"]
        for i in range(3):
            code = daily["weathercode"][i]
            pluie = daily.get("precipitation_sum", [0]*3)[i] or 0
            vent = daily.get("wind_speed_10m_max", [0]*3)[i] or 0
            if code in [95,96,99]:
                alertes.append(f"Tormenta prevista {jours[i]}")
            if code in [71,73,75,85,86]:
                alertes.append(f"Nieve prevista {jours[i]}")
            if pluie > 20:
                alertes.append(f"Fuertes lluvias {jours[i]} ({pluie}mm)")
            if vent > 60:
                alertes.append(f"Vientos fuertes {jours[i]} ({vent} km/h)")
        if alertes:
            return f"Alertas para {nom_affiche}: " + ", ".join(alertes)
        return f"No hay alertas para {nom_affiche}."
    except Exception:
        return "No pude obtener alertas."


# ===== FUNCIÓN EXPORTABLE PARA AP0L0 =====

async def ha_control(params: dict, player=None, speak=None) -> str:
    action = params.get("action", "").lower()
    if action == "light":
        piece = params.get("piece", "salon")
        etat = params.get("etat", "on")
        couleur = params.get("couleur")
        luminosite = params.get("luminosite")
        entity_id = PIECES_LUMIERES.get(piece, f"light.{piece}")
        rgb = COULEURS_MAP.get(couleur) if couleur else None
        ha_lumiere(entity_id, etat, luminosite, rgb)
        result = f"Luz {piece} {'encendida' if etat == 'on' else 'apagada'}"
    elif action == "switch":
        piece = params.get("piece", "bureau")
        etat = params.get("etat", "on")
        entity_id = PIECES_PRISES.get(piece, f"switch.{piece}")
        ha_interrupteur(entity_id, etat)
        result = f"Enchufe {piece} {'activado' if etat == 'on' else 'desactivado'}"
    elif action == "temperature":
        piece = params.get("piece", "salon")
        entity_id = PIECES_CAPTEURS.get(piece)
        if not entity_id:
            return f"No hay sensor para {piece}"
        temp = ha_get_etat(entity_id)
        result = f"Temperatura en {piece}: {temp}°C"
    elif action == "humidity":
        piece = params.get("piece", "bureau")
        entity_id = PIECES_HUMIDITE.get(piece) or PIECES_CAPTEURS.get(piece)
        if not entity_id:
            return f"No hay sensor de humedad para {piece}"
        hum = ha_get_etat(entity_id)
        result = f"Humedad en {piece}: {hum}%"
    elif action == "battery":
        appareil = params.get("appareil", "").lower()
        entity_id = APPAREILS_BATTERIE.get(appareil)
        if not entity_id:
            return f"No hay batería para {appareil}"
        batt = ha_get_etat(entity_id)
        result = f"Batería de {appareil}: {batt}%"
    elif action == "thermostat":
        temp = params.get("temperature", 20)
        ha_thermostat("climate.thermostat", temp)
        result = f"Termostato ajustado a {temp}°C"
    elif action == "scene":
        nom = params.get("nom", "")
        scene_id = f"scene.{nom}"
        ha_scene(scene_id)
        result = f"Escena {nom} activada"
    elif action == "alarm":
        etat = params.get("etat", "on")
        if etat == "on":
            ha_appeler_service("alarm_control_panel", "alarm_arm_away", "alarm_control_panel.home_base_2")
        else:
            ha_appeler_service("alarm_control_panel", "alarm_disarm", "alarm_control_panel.home_base_2")
        result = f"Alarma {'activada' if etat == 'on' else 'desactivada'}"
    elif action == "lock":
        entity_id = params.get("entity_id", "lock.porte_maison")
        etat = params.get("etat", "lock")
        ha_verrou(entity_id, etat)
        result = "Puerta bloqueada" if etat == "lock" else "Puerta desbloqueada"
    elif action == "energy":
        periode = params.get("periode", "mois")
        appareil = params.get("appareil", "")
        if appareil:
            entite = APPAREILS_ENERGIE.get(appareil.lower())
            if entite:
                val = ha_get_etat(entite)
                result = f"Consumo de {appareil} este mes: {val} kWh"
            else:
                result = f"No hay datos para {appareil}"
        else:
            total_kwh = 0
            total_cost = 0
            for i in range(1,7):
                e_id = f"sensor.lixee_zlinky_tic_zlinky_p{i}_mensuel"
                val = ha_get_etat(e_id)
                if val != "inconnu":
                    k = float(val)
                    total_kwh += k
                    total_cost += k * HA_TARIFS.get(f"p{i}", 0.16)
            result = f"Consumo mensual total: {total_kwh:.1f} kWh, coste estimado: {total_cost:.2f} €"
    elif action == "weather":
        ville = params.get("ville")
        result = get_meteo_actuelle(ville)
    elif action == "weather_alerts":
        ville = params.get("ville")
        result = get_alertes_meteo(ville)
    else:
        result = f"Acción HA '{action}' no soportada"
    if speak:
        speak(result)
    if player:
        player.write_log(f"[HA] {result}")
    return result