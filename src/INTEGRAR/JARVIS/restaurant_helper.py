import requests
import json
import random
import builtins
from google.genai import types

def obtener_ciudad_por_ip():
    """Detecta la ciudad del usuario por IP usando una API pública gratuita."""
    try:
        r = requests.get("https://ipapi.co/json/", timeout=4)
        if r.status_code == 200:
            data = r.json()
            ciudad = data.get("city")
            pais = data.get("country_name")
            if ciudad:
                print(f"[RESTAURANTE] Geolocalización por IP: {ciudad}, {pais}")
                return f"{ciudad}, {pais}"
    except Exception as e:
        print(f"[RESTAURANTE] Error en geolocalización por IP: {e}")
    return "París, Francia"

def buscar_restaurantes_cerca(ubicacion, lat=None, lng=None, excluir=None):
    """Busca restaurantes cercanos (SerpAPI primero, Gemini como fallback)."""
    import os
    import json
    import random
    import requests
    import google.genai as genai
    from dotenv import load_dotenv
    
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    
    ubicacion_objetivo = ubicacion if ubicacion else "Amilly"
    
    # 1. Intentar con SerpAPI (rápido y fiable)
    clave_serp = os.getenv("SERPAPI_API_KEY")
    if clave_serp and clave_serp != "VOTRE_CLE_ICI":
        try:
            print(f"[RESTAURANTE] Búsqueda con SerpAPI para la ciudad: {ubicacion_objetivo}")
            params = {
                "engine": "google",
                "q": f"restaurantes en {ubicacion_objetivo}",
                "api_key": clave_serp,
                "hl": "es",
                "gl": "es"
            }
            r = requests.get("https://serpapi.com/search.json", params=params, timeout=8)
            data = r.json()
            lugares = data.get("local_results", {}).get("places", [])
            if lugares:
                resultados = []
                for p in lugares:
                    nombre = p.get("title", "")
                    if excluir and nombre in excluir:
                        continue
                    
                    tipo_cocina = p.get("type", "Restaurante")
                    direccion = p.get("address", ubicacion_objetivo)
                    nota = p.get("rating", 4.2)
                    horarios = p.get("hours", "Desconocido")
                    desc = p.get("description", "Dirección gourmet local.")
                    
                    coords = "Desconocido"
                    if "gps_coordinates" in p:
                        coords = f"{p['gps_coordinates']['latitude']}, {p['gps_coordinates']['longitude']}"
                        
                    resultados.append({
                        "nom": nombre,
                        "cuisine": tipo_cocina,
                        "adresse": direccion,
                        "note": nota,
                        "telephone": "Desconocido",
                        "site_web": "Desconocido",
                        "horaires": horarios,
                        "coordonnees": coords,
                        "details_speciaux": desc,
                        "distance_estimee": "Cerca",
                        "angle_radar": random.randint(0, 360),
                        "distance_radar": random.randint(20, 85)
                    })
                if resultados:
                    print(f"[RESTAURANTE] {len(resultados)} restaurantes encontrados mediante SerpAPI.")
                    return resultados[:6]
        except Exception as e:
            print(f"[RESTAURANTE] SerpAPI falló: {e}")

    # 2. Fallback con Gemini (sin coordenadas GPS en el prompt)
    clave_api = os.getenv("GEMINI_API_KEY")
    if clave_api:
        try:
            cliente_local = genai.Client(api_key=clave_api)
            nombre_modelo = getattr(builtins, "CHOSEN_MODEL", "gemini-2.5-flash")
            
            print(f"[RESTAURANTE] Fallback con Gemini para la ciudad: {ubicacion_objetivo}")
            prompt = (
                f"Realiza una búsqueda en Google para encontrar buenos restaurantes (o direcciones gourmet) cerca de '{ubicacion_objetivo}'. "
                f"Dame una lista de 6 restaurantes reales. "
                f"Para cada restaurante, debes proporcionar la información exacta en el siguiente formato JSON. "
                f"Devuelve únicamente un array JSON con objetos que tengan estas claves:\n"
                f"- 'nom': Nombre del restaurante\n"
                f"- 'cuisine': Tipo de cocina (ej: 'Italiano', 'Bistrot', 'Gastronómico')\n"
                f"- 'adresse': Dirección física simplificada\n"
                f"- 'note': Nota sobre 5 (número decimal o entero, ej: 4.5)\n"
                f"- 'telephone': Número de teléfono del restaurante (ej: '01 30 22 45 67' o 'Desconocido')\n"
                f"- 'site_web': URL de su sitio web o enlace de Google Maps (ej: 'https://...' o 'Desconocido')\n"
                f"- 'horaires': Horarios de apertura simplificados (ej: '12:00-14:30, 19:00-22:30' o 'Desconocido')\n"
                f"- 'coordonnees': Coordenadas GPS en formato 'latitud, longitud' (ej: '48.8566, 2.3522' o 'Desconocido')\n"
                f"- 'details_speciaux': Una frase de descripción de su especialidad o plato estrella (ej: 'Especialista en fondue saboyana al fuego de leña' o 'Desconocido')\n"
                f"- 'distance_estimee': Distancia estimada desde '{ubicacion_objetivo}' (ej: '350m', '1.2km')\n"
                f"- 'angle_radar': Un ángulo de posicionamiento aleatorio o realista entre 0 y 360 (para visualización en pantalla radar)\n"
                f"- 'distance_radar': Un radio de posicionamiento en el radar entre 20 y 90 (para la visualización en pantalla radar)\n\n"
                f"Importante: Devuelve únicamente el JSON en bruto. Sin texto explicativo antes o después, sin etiquetas ```json, solo el array JSON."
            )
            if excluir and isinstance(excluir, list) and len(excluir) > 0:
                prompt += f"\nImportante: NO muestres estos restaurantes (exclúyelos absolutamente de la búsqueda porque ya se han mostrado) : {', '.join(excluir)}."

            print(f"[RESTAURANTE] Enviando solicitud a Gemini (Modelo: {nombre_modelo})...")
            import time
            t_inicio = time.time()
            response = cliente_local.models.generate_content(
                model=nombre_modelo,
                contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    system_instruction="Eres un asistente experto en gastronomía local. Solo debes devolver JSON puro."
                )
            )
            print(f"[RESTAURANTE] Respuesta de Gemini recibida en {time.time() - t_inicio:.2f} segundos.")
            texto = response.text.strip()
            
            if texto.startswith("```"):
                lineas = texto.splitlines()
                if lineas[0].startswith("```"):
                    lineas = lineas[1:]
                if lineas[-1].startswith("```"):
                    lineas = lineas[:-1]
                texto = "\n".join(lineas).strip()
                
            restaurantes = json.loads(texto)
            if isinstance(restaurantes, list) and len(restaurantes) > 0:
                print(f"[RESTAURANTE] {len(restaurantes)} restaurantes encontrados mediante Gemini Search.")
                return restaurantes
        except Exception as e:
            print(f"[RESTAURANTE] Error en búsqueda con Gemini: {e}")
            import traceback
            traceback.print_exc()

    return obtener_restaurantes_mock(ubicacion_objetivo, excluir=excluir)

def obtener_restaurantes_mock(ubicacion, excluir=None):
    """Devuelve una lista de restaurantes simulados (fallback seguro)."""
    print(f"[RESTAURANTE] Usando fallback de restaurantes simulados para: {ubicacion}")
    nombre_localidad = ubicacion.split(",")[0].strip()
    
    datos_mock = [
        {
            "nom": f"El Bistrot de {nombre_localidad}",
            "cuisine": "Cocina Tradicional",
            "adresse": f"12 Calle de la República, {nombre_localidad}",
            "note": 4.6,
            "telephone": "01 34 56 78 90",
            "site_web": "https://www.bistrot-local-test.es",
            "horaires": "12:00-14:30, 19:00-22:30",
            "coordonnees": "48.8566, 2.3522",
            "details_speciaux": "Famoso por su cocina de terruño y su tarta tatin casera.",
            "distance_estimee": "250m",
            "angle_radar": 45,
            "distance_radar": 35
        },
        {
            "nom": "El Taller de Sabores",
            "cuisine": "Gastronómico",
            "adresse": f"45 Avenida de los Campos, {nombre_localidad}",
            "note": 4.8,
            "telephone": "01 23 45 67 89",
            "site_web": "https://www.taller-sabores-test.es",
            "horaires": "19:00-23:00",
            "coordonnees": "48.8738, 2.2950",
            "details_speciaux": "Menú degustación refinado con maridajes de vinos de excepción.",
            "distance_estimee": "680m",
            "angle_radar": 120,
            "distance_radar": 60
        },
        {
            "nom": "Bella Italia",
            "cuisine": "Italiano",
            "adresse": f"8 Calle del Teatro, {nombre_localidad}",
            "note": 4.3,
            "telephone": "01 45 67 89 01",
            "site_web": "https://www.bella-italia-test.it",
            "horaires": "12:00-14:00, 19:00-22:00",
            "coordonnees": "48.8650, 2.3200",
            "details_speciaux": "Pizzas al horno de leña y pastas frescas caseras.",
            "distance_estimee": "400m",
            "angle_radar": 290,
            "distance_radar": 45
        },
        {
            "nom": "El Faro Gourmet",
            "cuisine": "Pescados y Mariscos",
            "adresse": f"2 Plaza de la Marina, {nombre_localidad}",
            "note": 4.5,
            "telephone": "01 56 78 90 12",
            "site_web": "https://www.faro-gourmet-test.com",
            "horaires": "12:00-14:30, 19:00-22:30",
            "coordonnees": "48.8400, 2.3700",
            "details_speciaux": "Mariscadas frescas llegadas cada mañana.",
            "distance_estimee": "1.1km",
            "angle_radar": 180,
            "distance_radar": 85
        },
        {
            "nom": "El Wok de Oro",
            "cuisine": "Asiático",
            "adresse": f"67 Bulevar Carnot, {nombre_localidad}",
            "note": 4.2,
            "telephone": "01 67 89 01 23",
            "site_web": "https://www.wok-de-oro-test.cn",
            "horaires": "11:30-14:30, 18:30-22:30",
            "coordonnees": "48.8800, 2.3100",
            "details_speciaux": "Bufé asiático libre y parrillas a la plancha.",
            "distance_estimee": "820m",
            "angle_radar": 30,
            "distance_radar": 70
        },
        {
            "nom": "Casa del Tío Sam",
            "cuisine": "Hamburguesas y Parrilla",
            "adresse": f"19 Calle de Verdún, {nombre_localidad}",
            "note": 4.4,
            "telephone": "01 78 90 12 34",
            "site_web": "https://www.tiosam-grill-test.us",
            "horaires": "11:30-23:00 (sin interrupción)",
            "coordonnees": "48.8300, 2.3400",
            "details_speciaux": "Hamburguesas americanas gourmet de carne de origen local.",
            "distance_estimee": "510m",
            "angle_radar": 230,
            "distance_radar": 50
        }
    ]
    
    if excluir and isinstance(excluir, list):
        filtrados = [r for r in datos_mock if r["nom"] not in excluir]
        if len(filtrados) < 4:
            sufijos = ['El Reloj', 'El Anexo', 'El Rincón', "La Posada"]
            for i in range(6):
                var_r = dict(datos_mock[i % len(datos_mock)])
                var_r["nom"] = var_r["nom"] + f" ({random.choice(sufijos)})"
                var_r["note"] = round(min(5.0, var_r["note"] + random.uniform(-0.3, 0.2)), 1)
                var_r["angle_radar"] = (var_r["angle_radar"] + 90) % 360
                if var_r["nom"] not in excluir:
                    filtrados.append(var_r)
        return filtrados[:6]
    return datos_mock