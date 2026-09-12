# ============================================================
#  ha_config.py — Configuration Home Assistant & Météo
#  Personnalisez CE fichier selon votre installation domotique
#  Ne touchez pas main2.py pour la domotique, tout est ici.
#  Site : www.techenclair.fr
# ============================================================

import os
import json
import requests
import asyncio
from datetime import datetime
from dotenv import load_dotenv

def _charger_user_name():
    try:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        with open(_p, "r", encoding="utf-8") as _f:
            return json.load(_f).get("user_name", "Mickael")
    except Exception:
        return "Mickael"

_USER = _charger_user_name().lower()

def _update_ha_env():
    global HA_URL, HA_TOKEN, HA_HEADERS
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)
    HA_URL    = os.getenv("HA_URL", "").rstrip("/")
    HA_TOKEN  = os.getenv("HA_TOKEN", "")
    HA_HEADERS = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type" : "application/json"
    }

# Initial load
HA_URL = ""
HA_TOKEN = ""
HA_HEADERS = {}
_update_ha_env()

# ═══════════════════════════════════════════════════════════════
#  SECTION 1 — MÉTÉO PAR DÉFAUT
#  Remplacez par votre ville et ses coordonnées GPS.
#  Coordonnées : https://www.latlong.net/
# ═══════════════════════════════════════════════════════════════
VILLE_PAR_DEFAUT = "Amilly"   # ← Votre ville
LAT_PAR_DEFAUT   = 47.9742    # ← Latitude
LON_PAR_DEFAUT   = 2.7708     # ← Longitude

def reload_config_values():
    global VILLE_PAR_DEFAUT, LAT_PAR_DEFAUT, LON_PAR_DEFAUT
    try:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        if os.path.exists(_p):
            with open(_p, "r", encoding="utf-8") as _f:
                cfg = json.load(_f)
                if "user_city" in cfg and cfg["user_city"]:
                    VILLE_PAR_DEFAUT = cfg["user_city"]
                if "user_lat" in cfg and cfg["user_lat"] is not None:
                    LAT_PAR_DEFAUT = float(cfg["user_lat"])
                if "user_lon" in cfg and cfg["user_lon"] is not None:
                    LON_PAR_DEFAUT = float(cfg["user_lon"])
    except Exception as e:
        print(f"[HA_CONFIG] Erreur reload_config_values : {e}")

reload_config_values()

# ═══════════════════════════════════════════════════════════════
#  SECTION 2 — LUMIÈRES
#  Format : "nom vocal" : "entity_id Home Assistant"
#  Pour trouver un entity_id : HA → Paramètres → Appareils
#    → cliquez sur l'entité → "Informations sur l'entité"
# ═══════════════════════════════════════════════════════════════
PIECES_LUMIERES = {
    # Salon
    "salon"            : "light.salon",
    "plafond salon"    : "light.plafond",
    "canapes"          : "light.canapes",
    "lampadaire"       : "light.lampadaire",
    "lampe de chevet"  : "light.lampe_de_chevet_2",
    "grosse boule"     : "light.grosse_boule",
    "petite boule"     : "light.petite_boule",

    # Cuisine
    "cuisine"          : "light.lsc_smart_led_strip_rgbic_cctic_5m",
    "cuisine 2"        : "light.cuisine_2",

    # Mickael
    "mickael"          : "light.pc_3",
    "pc mickael"       : "light.pc_3",

    # Bureau
    "bureau"           : "light.bureau",
    "pc"               : "light.pc",
    "pc 2"             : "light.pc_2",

    # Parents
    "parents"          : "light.chambre_parentale",
    "chambre parentale": "light.chambre_parentale",
    "chambre"          : "light.chambre_parentale",
    "plafond chambre"  : "light.plafond_2",

    # Globaux
    "toutes"           : "light.all",
    "tout"             : "light.all",
}

# ═══════════════════════════════════════════════════════════════
#  SECTION 3 — PRISES CONNECTÉES
#  Format : "nom vocal" : "entity_id switch.xxx"
# ═══════════════════════════════════════════════════════════════
PIECES_PRISES = {
    "salon"   : "switch.prise_salon",
    "bureau"  : "switch.prise_bureau",
    "cuisine" : "switch.prise_cuisine",
}

# ═══════════════════════════════════════════════════════════════
#  SECTION 4 — CAPTEURS TEMPÉRATURE & DIVERS
#  Format : "nom vocal" : "entity_id sensor.xxx"
#  Vous pouvez ajouter autant de pièces que nécessaire.
# ═══════════════════════════════════════════════════════════════
PIECES_CAPTEURS = {
    "salon"        : "sensor.salon_temperature_2",
    "chambre"      : "sensor.miaomiaoc_de_blt_4_14kc52pmcgk00_t2_temperature_p_2_1",
    "bureau"       : "sensor.temp_temperature",
    "exterieur"    : "sensor.temperature_exterieure",
    "dehors"       : "sensor.temperature_exterieure",
    "consommation" : "sensor.lixee_zlinky_tic_puissance_apparente",
    "tiktok"       : "sensor.tiktok_followers_techenclair",
    "oeufs"        : "input_select.ramassage_des_oeufs",
}

# ═══════════════════════════════════════════════════════════════
#  SECTION 5 — CAPTEURS HUMIDITÉ
#  Format : "nom vocal" : "entity_id sensor.xxx"
# ═══════════════════════════════════════════════════════════════
PIECES_HUMIDITE = {
    "bureau" : "sensor.temp_humidite",
}

# ═══════════════════════════════════════════════════════════════
#  SECTION 6 — TARIFS ÉLECTRICITÉ (€/kWh)
#  Adaptez selon votre contrat EDF / fournisseur
#  p1-p6 = plages tarifaires Linky (heures creuses, pleines, etc.)
# ═══════════════════════════════════════════════════════════════
HA_TARIFS = {
    "p1": 0.1296,
    "p2": 0.1603,
    "p3": 0.1486,
    "p4": 0.1894,
    "p5": 0.1568,
    "p6": 0.7562,
}

# ═══════════════════════════════════════════════════════════════
#  SECTION 7 — SUIVI ÉNERGIE PAR APPAREIL
#  Format : "nom vocal" : "entity_id sensor.xxx_mensuel"
# ═══════════════════════════════════════════════════════════════
APPAREILS_ENERGIE = {
    "tv"             : "sensor.prise_1_salon_mensuel",
    "salon"          : "sensor.prise_1_salon_mensuel",
    "pc mickael"     : "sensor.prise_3_pc_mickael_mensuel",
    "mickael"        : "sensor.prise_3_pc_mickael_mensuel",
    "zoe"            : "sensor.zoe_mensuel",
    "voiture"        : "sensor.zoe_mensuel",
    "lave-vaisselle" : "sensor.prise_2_lave_vaisselle_mensuel",
    "pc salon"       : "sensor.pc_salon_conso_pc_salon_mensuel_2",
    "bureau"         : "sensor.bureau_mensuel",
}

# ═══════════════════════════════════════════════════════════════
#  SECTION 8 — BATTERIES DES APPAREILS
#  Format : "nom vocal" : "entity_id sensor.xxx_battery_level"
# ═══════════════════════════════════════════════════════════════
APPAREILS_BATTERIE = {
    "mon telephone"      : "sensor.sm_s921b_battery_level",
    "mickael"               : "sensor.sm_s921b_battery_level",
    _USER                : "sensor.sm_s921b_battery_level",
    "samsung mickael"       : "sensor.sm_s921b_battery_level",
    "mickael"              : "sensor.sm_mickael_battery_level",
    "maman"              : "sensor.sm_mickael_battery_level",
    "samsung maman"      : "sensor.sm_mickael_battery_level",
    "mickael"            : "sensor.mickael_battery_level",
    "honor"              : "sensor.honor_battery_level",
    "tablette honor"     : "sensor.honor_battery_level",
    "montre mickael"        : "sensor.galaxy_watch6_classic_d4he_battery_level",
    f"montre {_USER}"    : "sensor.galaxy_watch6_classic_d4he_battery_level",
    "montre maman"       : "sensor.galaxy_watch8_fbxh_battery_level",
    "montre mickael"       : "sensor.galaxy_watch8_fbxh_battery_level",
    "bob"                : "sensor.bob_batterie",
    "aspirateur bob"     : "sensor.bob_batterie",
    "dyad"               : "sensor.dyad_air_2024_batterie",
    "aspirateur dyad"    : "sensor.dyad_air_2024_batterie",
    "telecommande hue"   : "sensor.maison_interrupteur_batterie",
    "interrupteur"       : "sensor.maison_interrupteur_batterie",
    "toner"              : "sensor.samsung_m2020_series_black_toner_s_n_crum_17091625519",
    "imprimante"         : "sensor.samsung_m2020_series_black_toner_s_n_crum_17091625519",
    "boite aux lettres"  : "sensor.detecterur_batterie",
    "detecteur cuisine"  : "sensor.detecteur_1_batterie",
    "detecteur escalier" : "sensor.detecteur_2_batterie",
    "camera jardin"      : "sensor.arriere_cour_battery_percentage",
    "thermometre bureau" : "sensor.temp_batterie",
}

# ═══════════════════════════════════════════════════════════════
#  SECTION 9 — COULEURS RGB
#  Format : "nom vocal" : [R, G, B]
#  Vous pouvez ajouter vos propres couleurs.
# ═══════════════════════════════════════════════════════════════
COULEURS_MAP = {
    "rouge"     : [255, 0,   0  ],
    "bleu"      : [0,   0,   255],
    "vert"      : [0,   255, 0  ],
    "blanc"     : [255, 255, 255],
    "orange"    : [255, 140, 0  ],
    "violet"    : [148, 0,   211],
    "rose"      : [255, 20,  147],
    "jaune"     : [255, 255, 0  ],
    "cyan"      : [0,   255, 255],
    "magenta"   : [255, 0,   255],
    "turquoise" : [64,  224, 208],
    "or"        : [255, 215, 0  ],
    "argent"    : [192, 192, 192],
    "indigo"    : [75,  0,   130],
    "marron"    : [139, 69,  19 ],
    "citron"    : [255, 250, 0  ],
    "corail"    : [255, 127, 80 ],
    "lavande"   : [230, 230, 250],
}

# ── Codes météo Open-Meteo (ne pas modifier) ─────────────────
CODES_METEO = {
    0:  "degage",
    1:  "principalement clair", 2: "partiellement nuageux", 3: "couvert",
    45: "brouillard", 48: "brouillard givrant",
    51: "bruine legere", 53: "bruine moderee", 55: "bruine dense",
    61: "pluie faible", 63: "pluie moderee", 65: "pluie forte",
    71: "neige faible", 73: "neige moderee", 75: "neige forte",
    80: "averses faibles", 81: "averses moderees", 82: "averses violentes",
    85: "averses de neige", 86: "averses de neige fortes",
    95: "orage", 96: "orage avec grele", 99: "orage violent avec grele",
}

# ════════════════════════════════════════════════════════════════
#  ENTITÉS HOME ASSISTANT PERSONNALISÉES (chargées depuis jarvis_config.json)
#  Rechargé automatiquement à chaque sauvegarde dans les paramètres.
# ════════════════════════════════════════════════════════════════

_HA_CUSTOM_KEYS: dict = {"lumieres": set(), "prises": set(), "capteurs": set()}

def _charger_custom_ha_entities():
    global _HA_CUSTOM_KEYS
    _update_ha_env()
    for k in _HA_CUSTOM_KEYS["lumieres"]:
        PIECES_LUMIERES.pop(k, None)
    for k in _HA_CUSTOM_KEYS["prises"]:
        PIECES_PRISES.pop(k, None)
    for k in _HA_CUSTOM_KEYS["capteurs"]:
        PIECES_CAPTEURS.pop(k, None)
    _HA_CUSTOM_KEYS = {"lumieres": set(), "prises": set(), "capteurs": set()}
    try:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        with open(_p, "r", encoding="utf-8") as _f:
            _cfg = json.load(_f)
        custom = _cfg.get("ha_custom_entities", {})
        for entry in custom.get("lumieres", []):
            nom = entry["nom"].lower().strip()
            PIECES_LUMIERES[nom] = entry["entity_id"]
            _HA_CUSTOM_KEYS["lumieres"].add(nom)
        for entry in custom.get("prises", []):
            nom = entry["nom"].lower().strip()
            PIECES_PRISES[nom] = entry["entity_id"]
            _HA_CUSTOM_KEYS["prises"].add(nom)
        for entry in custom.get("capteurs", []):
            nom = entry["nom"].lower().strip()
            PIECES_CAPTEURS[nom] = entry["entity_id"]
            _HA_CUSTOM_KEYS["capteurs"].add(nom)
    except Exception:
        pass

_charger_custom_ha_entities()

# ════════════════════════════════════════════════════════════════
#  FONCTIONS API HOME ASSISTANT
#  Ne modifiez pas ces fonctions — elles appellent l'API HA.
# ════════════════════════════════════════════════════════════════

def ha_appeler_service(domaine, service, entity_id, donnees=None):
    _update_ha_env()
    try:
        payload = {"entity_id": entity_id}
        if donnees:
            payload.update(donnees)
        print(f"[HA DEBUG] Calling {domaine}/{service} for {entity_id} with {donnees}")
        r = requests.post(
            f"{HA_URL}/api/services/{domaine}/{service}",
            headers=HA_HEADERS, json=payload, timeout=5
        )
        print(f"[HA DEBUG] Response {r.status_code}: {r.text}")
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[HA] Erreur service : {e}")
        return False

def ha_get_etat(entity_id, attribut=None):
    _update_ha_env()
    try:
        url = f"{HA_URL}/api/states/{entity_id}"
        print(f"[HA DEBUG] GET {url}")
        r = requests.get(url, headers=HA_HEADERS, timeout=5)
        print(f"[HA DEBUG] Status={r.status_code}  Body={r.text[:200]!r}")
        data = r.json()
        if attribut:
            return data.get("attributes", {}).get(attribut, "inconnu")
        return data.get("state", "inconnu")
    except Exception as e:
        print(f"[HA] Erreur get etat : {e}")
        return "inconnu"

def ha_get_calendrier(entity_id):
    _update_ha_env()
    try:
        now   = datetime.now()
        start = now.strftime("%Y-%m-%dT00:00:00Z")
        end   = now.strftime("%Y-%m-%dT23:59:59Z")
        r = requests.get(
            f"{HA_URL}/api/calendars/{entity_id}",
            headers=HA_HEADERS,
            params={"start": start, "end": end},
            timeout=5
        )
        return r.json()
    except Exception as e:
        print(f"[HA] Erreur calendrier : {e}")
        return []

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

# ════════════════════════════════════════════════════════════════
#  FONCTIONS MÉTÉO
#  Utilisent Open-Meteo (gratuit) + Home Assistant en fallback.
# ════════════════════════════════════════════════════════════════

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
    except Exception as e:
        print(f"[METEO] Erreur geocoding : {e}")
    return None, None, ville, ""

def get_meteo_structuree(ville=None):
    """Retourne les données météo structurées pour le panneau visuel frontend."""
    try:
        nom_ville = ville or VILLE_PAR_DEFAUT
        lat, lon, nom_affiche, pays = geocoder_ville(nom_ville)
        if lat is None:
            lat, lon = LAT_PAR_DEFAUT, LON_PAR_DEFAUT
            nom_affiche = VILLE_PAR_DEFAUT
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
            "ville"      : nom_affiche,
            "temperature": round(float(cur.get("temperature_2m", 0))),
            "ressenti"   : round(float(cur.get("apparent_temperature", 0))),
            "humidite"   : round(float(cur.get("relative_humidity_2m", 0))),
            "vent"       : round(float(cur.get("wind_speed_10m", 0))),
            "code"       : code,
            "description": CODES_METEO.get(code, "inconnu"),
        }
    except Exception as e:
        print(f"[METEO_DATA] Erreur : {e}")
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
        desc = CODES_METEO.get(code, "conditions inconnues")
        temp = round(float(cur.get("temperature_2m", 0)))
        return f"À {nom_affiche}, il fait {temp} degrés et le ciel est {desc}. C'est tout."
    except Exception as e:
        print(f"[METEO] Erreur : {e}")
        return "Je n'arrive pas à récupérer la météo pour le moment."

def get_meteo_ha():
    """Lit la météo depuis Home Assistant. Fallback quand Gemini est KO."""
    _update_ha_env()
    try:
        r    = requests.get(f"{HA_URL}/api/states/weather.forecast_amilly", headers=HA_HEADERS, timeout=5)
        data = r.json()
        etat  = data.get("state", "inconnu")
        attrs = data.get("attributes", {})
        temp     = attrs.get("temperature", "?")
        humidite = attrs.get("humidity", None)
        vent     = attrs.get("wind_speed", None)
        etats_fr = {
            "sunny"          : "ensoleillé",
            "clear-night"    : "clair",
            "partlycloudy"   : "partiellement nuageux",
            "cloudy"         : "nuageux",
            "rainy"          : "pluvieux",
            "pouring"        : "forte pluie",
            "snowy"          : "neigeux",
            "snowy-rainy"    : "pluie et neige mêlées",
            "windy"          : "venteux",
            "windy-variant"  : "très venteux",
            "fog"            : "brumeux",
            "hail"           : "grêle",
            "lightning"      : "orageux",
            "lightning-rainy": "orage et pluie",
            "exceptional"    : "conditions exceptionnelles",
        }
        desc    = etats_fr.get(etat, etat)
        reponse = f"À {VILLE_PAR_DEFAUT}, il fait {temp} degrés et le ciel est {desc}"
        if humidite:
            reponse += f", humidité à {humidite}%"
        if vent:
            reponse += f", vent à {vent} km/h"
        reponse += f", {_charger_user_name()}."
        return reponse
    except Exception as e:
        print(f"[METEO HA] Erreur : {e}")
        return None

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
                "daily"   : "weathercode,precipitation_sum,wind_speed_10m_max",
                "timezone": "Europe/Paris", "forecast_days": 3,
            },
            timeout=8
        )
        data    = r.json()
        daily   = data["daily"]
        alertes = []
        for i in range(len(daily["weathercode"])):
            code  = daily["weathercode"][i]
            pluie = daily.get("precipitation_sum", [0]*3)[i] or 0
            vent  = daily.get("wind_speed_10m_max", [0]*3)[i] or 0
            jour  = ["aujourd hui", "demain", "apres-demain"][i]
            if code in [95, 96, 99]:
                alertes.append(f"Orage prevu {jour}")
            if code in [71, 73, 75, 85, 86]:
                alertes.append(f"Neige prevue {jour}")
            if pluie > 20:
                alertes.append(f"Fortes pluies {jour} ({pluie}mm)")
            if vent > 60:
                alertes.append(f"Vents forts {jour} ({vent} km/h)")
        if alertes:
            return f"Alertes meteo pour {nom_affiche} : " + ", ".join(alertes) + "."
        return f"Aucune alerte meteo pour {nom_affiche} dans les 3 prochains jours."
    except Exception as e:
        return f"Impossible de verifier les alertes meteo : {e}"


# ════════════════════════════════════════════════════════════════
#  NOUVEAUX SERVICES - DASHBOARD CENTRAL DE DOMOTIQUE
# ════════════════════════════════════════════════════════════════

def ha_get_all_states() -> list:
    """Récupère tous les états des entités de Home Assistant."""
    _update_ha_env()
    try:
        url = f"{HA_URL}/api/states"
        print(f"[HA] Récupération de tous les états depuis {url}")
        r = requests.get(url, headers=HA_HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"[HA] Échec récupération états. Code : {r.status_code}")
            return []
    except Exception as e:
        print(f"[HA] Erreur lors de la récupération de tous les états : {e}")
        return []

def ha_get_etat_complet(entity_id: str) -> dict | None:
    """Récupère l'état complet d'une entité spécifique."""
    _update_ha_env()
    try:
        url = f"{HA_URL}/api/states/{entity_id}"
        r = requests.get(url, headers=HA_HEADERS, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[HA] Erreur ha_get_etat_complet pour {entity_id} : {e}")
    return None

async def handle_ha_ws_message(data: dict, websocket, connected_clients: set) -> bool:
    """Gère les messages WebSocket liés à Home Assistant."""
    msg_type = data.get("type", "")

    if msg_type == "ha_get_states":
        states = await asyncio.to_thread(ha_get_all_states)
        await websocket.send(json.dumps({
            "type": "ha_states",
            "success": len(states) > 0 or HA_URL != "",
            "states": states
        }))
        return True

    elif msg_type == "ha_call_service":
        domain = data.get("domain", "")
        service = data.get("service", "")
        entity_id = data.get("entity_id", "")
        service_data = data.get("service_data", None)

        success = await asyncio.to_thread(ha_appeler_service, domain, service, entity_id, service_data)

        updated_state = None
        if success:
            updated_state = await asyncio.to_thread(ha_get_etat_complet, entity_id)

        await websocket.send(json.dumps({
            "type": "ha_service_result",
            "success": success,
            "entity_id": entity_id,
            "state": updated_state
        }))

        # Diffuser le changement d'état à tous les clients connectés pour synchroniser l'UI
        if success and updated_state:
            await _broadcast_ha(connected_clients, {
                "type": "ha_state_changed",
                "entity_id": entity_id,
                "state": updated_state
            })
        return True

    elif msg_type == "ha_add_voice_alias":
        entity_id = data.get("entity_id", "").strip()
        domain = data.get("domain", "").strip()
        alias = data.get("alias", "").strip().lower()
        if entity_id and alias:
            try:
                cat = "lumieres"
                if domain in ("switch", "input_boolean", "valve"):
                    cat = "prises"
                elif domain in ("sensor", "binary_sensor", "climate"):
                    cat = "capteurs"
                elif entity_id.startswith("light."):
                    cat = "lumieres"
                elif entity_id.startswith("switch."):
                    cat = "prises"
                elif entity_id.startswith("sensor.") or entity_id.startswith("binary_sensor."):
                    cat = "capteurs"

                _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
                cfg = {}
                if os.path.exists(_p):
                    with open(_p, "r", encoding="utf-8") as _f:
                        cfg = json.load(_f)

                ha_custom = cfg.get("ha_custom_entities", {})
                if cat not in ha_custom:
                    ha_custom[cat] = []

                existing = [e for e in ha_custom[cat] if e.get("nom", "").lower() != alias]
                existing.append({"nom": alias, "entity_id": entity_id})
                ha_custom[cat] = existing
                cfg["ha_custom_entities"] = ha_custom

                with open(_p, "w", encoding="utf-8") as _f:
                    json.dump(cfg, _f, ensure_ascii=False, indent=2)

                _charger_custom_ha_entities()

                await websocket.send(json.dumps({
                    "type": "ha_voice_alias_saved",
                    "success": True,
                    "alias": alias,
                    "entity_id": entity_id,
                    "category": cat
                }))
                return True
            except Exception as _e:
                print(f"[HA ALIAS WS] Erreur : {_e}")
                await websocket.send(json.dumps({
                    "type": "ha_voice_alias_saved",
                    "success": False,
                    "error": str(_e)
                }))
                return True

    return False

async def _broadcast_ha(clients: set, message: dict):
    if not clients:
        return
    msg = json.dumps(message)
    try:
        await asyncio.gather(*[c.send(msg) for c in clients], return_exceptions=True)
    except Exception as e:
        print(f"[HA-WS] Erreur broadcast : {e}")
