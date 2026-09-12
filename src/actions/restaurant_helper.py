# src/actions/restaurant_helper.py
"""
Búsqueda de restaurantes para AP0L0
"""

import requests
import json
import random
import os

from src.core.config import _get_config


def obtener_ciudad_por_ip():
    try:
        r = requests.get("https://ipapi.co/json/", timeout=4)
        if r.status_code == 200:
            data = r.json()
            city = data.get("city")
            if city:
                return f"{city}, {data.get('country_name')}"
    except Exception:
        pass
    return "Amilly, France"


def rechercher_restaurants_proches(location, lat=None, lng=None, exclure=None):
    cfg = _get_config()
    serp_key = cfg.get("serpapi_api_key", "")
    if serp_key:
        try:
            params = {
                "engine": "google",
                "q": f"restaurantes en {location}",
                "api_key": serp_key,
                "hl": "fr",
                "gl": "fr"
            }
            r = requests.get("https://serpapi.com/search.json", params=params, timeout=8)
            data = r.json()
            places = data.get("local_results", {}).get("places", [])
            if places:
                results = []
                for p in places[:6]:
                    nom = p.get("title", "")
                    if exclure and nom in exclure:
                        continue
                    results.append({
                        "nom": nom,
                        "cuisine": p.get("type", "Restaurante"),
                        "adresse": p.get("address", location),
                        "note": p.get("rating", 4.0),
                        "telephone": "Inconnu",
                        "site_web": "Inconnu",
                        "horaires": "Inconnu",
                        "coordonnees": "Inconnu",
                        "details_speciaux": p.get("description", ""),
                        "distance_estimee": "Cerca",
                        "angle_radar": random.randint(0, 360),
                        "distance_radar": random.randint(20, 85)
                    })
                if results:
                    return results
        except Exception as e:
            print(f"[Restaurant] SerpAPI error: {e}")
    # Fallback con datos mock
    return _obtener_mock_restaurants(location, exclure)


def _obtener_mock_restaurants(location, exclure=None):
    nombre_ciudad = location.split(",")[0].strip()
    mock_data = [
        {"nom": f"Le Bistrot de {nombre_ciudad}", "cuisine": "Tradicional",
         "adresse": f"12 Rue de la République, {nombre_ciudad}", "note": 4.6,
         "telephone": "01 34 56 78 90", "site_web": "https://bistrot.fr",
         "horaires": "12:00-14:30, 19:00-22:30", "coordonnees": "48.8566,2.3522",
         "details_speciaux": "Cocina de autor", "distance_estimee": "250m",
         "angle_radar": 45, "distance_radar": 35},
        {"nom": f"L'Atelier des Saveurs", "cuisine": "Gastronómica",
         "adresse": f"45 Avenue des Champs, {nombre_ciudad}", "note": 4.8,
         "telephone": "01 23 45 67 89", "site_web": "https://atelier.fr",
         "horaires": "19:00-23:00", "coordonnees": "48.8738,2.2950",
         "details_speciaux": "Menú degustación", "distance_estimee": "680m",
         "angle_radar": 120, "distance_radar": 60},
        {"nom": f"Bella Italia", "cuisine": "Italiano",
         "adresse": f"8 Rue du Théâtre, {nombre_ciudad}", "note": 4.3,
         "telephone": "01 45 67 89 01", "site_web": "https://bellaitalia.it",
         "horaires": "12:00-14:00, 19:00-22:00", "coordonnees": "48.8650,2.3200",
         "details_speciaux": "Pizzas al horno de leña", "distance_estimee": "400m",
         "angle_radar": 290, "distance_radar": 45},
        {"nom": f"Le Phare Gourmand", "cuisine": "Pescados",
         "adresse": f"2 Place de la Marine, {nombre_ciudad}", "note": 4.5,
         "telephone": "01 56 78 90 12", "site_web": "https://phare.fr",
         "horaires": "12:00-14:30, 19:00-22:30", "coordonnees": "48.8400,2.3700",
         "details_speciaux": "Mariscos frescos", "distance_estimee": "1.1km",
         "angle_radar": 180, "distance_radar": 85},
        {"nom": f"Le Wok d'Or", "cuisine": "Asiático",
         "adresse": f"67 Boulevard Carnot, {nombre_ciudad}", "note": 4.2,
         "telephone": "01 67 89 01 23", "site_web": "https://wok.fr",
         "horaires": "11:30-14:30, 18:30-22:30", "coordonnees": "48.8800,2.3100",
         "details_speciaux": "Buffet a volonté", "distance_estimee": "820m",
         "angle_radar": 30, "distance_radar": 70},
        {"nom": f"Chez l'Oncle Sam", "cuisine": "Burgers",
         "adresse": f"19 Rue de Verdun, {nombre_ciudad}", "note": 4.4,
         "telephone": "01 78 90 12 34", "site_web": "https://onclesam.fr",
         "horaires": "11:30-23:00", "coordonnees": "48.8300,2.3400",
         "details_speciaux": "Burgers gourmet", "distance_estimee": "510m",
         "angle_radar": 230, "distance_radar": 50}
    ]
    if exclure:
        mock_data = [r for r in mock_data if r["nom"] not in exclure]
    return mock_data[:6]


# ===== FUNCIÓN EXPORTABLE =====

async def restaurant_search(params: dict, player=None, speak=None) -> str:
    location = params.get("location", "")
    if not location:
        location = obtener_ciudad_por_ip()
    results = rechercher_restaurants_proches(location)
    if not results:
        return f"No se encontraron restaurantes en {location}."
    formatted = f"Restaurantes cerca de {location}:\n"
    for i, r in enumerate(results[:5], 1):
        formatted += f"{i}. {r['nom']} - {r['cuisine']} ({r['note']}★) - {r['adresse']}\n"
    if speak:
        speak(formatted)
    if player:
        player.write_log(f"[Restaurant] {formatted}")
    return formatted