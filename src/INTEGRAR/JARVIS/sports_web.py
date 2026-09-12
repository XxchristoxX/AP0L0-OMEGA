import requests
import json
import os
from dotenv import load_dotenv
import google.genai as genai
from google.genai import types

load_dotenv()
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
if SERPAPI_API_KEY == "VOTRE_CLE_ICI":
    SERPAPI_API_KEY = None

def buscar_imagenes_gemini(consulta, num_imagenes=6):
    """Busca imágenes pidiendo a Gemini (con Google Search Grounding) que devuelva URLs de imágenes."""
    import builtins
    if not hasattr(builtins, "client") or builtins.client is None:
        print("[IMAGEN] Cliente Gemini no disponible en builtins.")
        return []
    
    try:
        print(f"[IMAGEN] Buscando imágenes con Gemini (con Google Search) para: {consulta}")
        prompt = (
            f"Realiza una búsqueda en internet para encontrar imágenes de '{consulta}'. "
            f"Dame una lista de {num_imagenes} URLs de imágenes directas o de fuentes de imágenes válidas (por ejemplo, que terminen en .jpg, .png, .jpeg o que provengan de bancos de imágenes o artículos de prensa). "
            f"Devuelve únicamente un array JSON con estas URLs (ejemplo: [\"https://sitio.com/imagen.jpg\", ...]). "
            f"Importante: No pongas texto explicativo antes ni después del JSON, ni etiquetas ```json, solo el array JSON en bruto."
        )
        
        nombre_modelo = getattr(builtins, "CHOSEN_MODEL", "gemini-2.5-flash")
        
        response = builtins.client.models.generate_content(
            model=nombre_modelo,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                system_instruction="Eres un asistente especializado en búsqueda de imágenes en internet. Solo debes devolver un array JSON de URLs."
            )
        )
        texto = response.text.strip()
        
        if texto.startswith("```"):
            lineas = texto.splitlines()
            if lineas[0].startswith("```"):
                lineas = lineas[1:]
            if lineas[-1].startswith("```"):
                lineas = lineas[:-1]
            texto = "\n".join(lineas).strip()
            
        urls = json.loads(texto)
        if isinstance(urls, list):
            urls_validas = [u for u in urls if isinstance(u, str) and (u.startswith("http://") or u.startswith("https://"))]
            print(f"[IMAGEN] {len(urls_validas)} imagen(es) encontrada(s) mediante Gemini.")
            return urls_validas[:num_imagenes]
    except Exception as e:
        print(f"[IMAGEN] Error en búsqueda de imágenes con Gemini: {e}")
    return []

def buscar_imagenes_web(consulta, num_imagenes=6, motor="serpapi"):
    """Busca imágenes en internet usando el motor especificado (serpapi, gemini, duckduckgo)."""
    urls = []
    
    # ── Motor Gemini ────────────────────────────────────────────────────────
    if motor == "gemini":
        urls = buscar_imagenes_gemini(consulta, num_imagenes)
        if urls:
            return urls
        print("[IMAGEN] Fallo o sin resultados mediante Gemini. Probando con el fallback...")
        
    # ── Motor SerpAPI ───────────────────────────────────────────────────────
    elif motor == "serpapi":
        if _clave_valida(SERPAPI_API_KEY):
            try:
                print(f"[IMAGEN] Buscando con SerpAPI Images para: {consulta}")
                params = {
                    "engine": "google_images",
                    "q": consulta,
                    "api_key": SERPAPI_API_KEY,
                    "hl": "es",
                    "gl": "es",
                    "num": num_imagenes,
                }
                r = requests.get("https://serpapi.com/search.json", params=params, timeout=10)
                data = r.json()
                resultados_imagenes = data.get("images_results", [])
                for img in resultados_imagenes[:num_imagenes]:
                    src = img.get("original") or img.get("thumbnail")
                    if src:
                        urls.append(src)
                if urls:
                    print(f"[IMAGEN] {len(urls)} imagen(es) encontrada(s) mediante SerpAPI.")
                    return urls
            except Exception as e:
                print(f"[IMAGEN] Error en SerpAPI Images: {e}")
        else:
            print("[IMAGEN] Clave SerpAPI no válida o no configurada.")
            
    # ── Motor DuckDuckGo (o fallback global) ────────────────────────────────
    try:
        print(f"[IMAGEN] Buscando con DuckDuckGo Images para: {consulta}")
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(
            "https://duckduckgo.com/",
            params={"q": consulta, "iax": "images", "ia": "images"},
            headers=headers, timeout=8
        )
        import re as _re
        match_vqd = _re.search(r'vqd=([\d-]+)', r.text)
        if match_vqd:
            vqd = match_vqd.group(1)
            r2 = requests.get(
                "https://duckduckgo.com/i.js",
                params={"l": "es-es", "o": "json", "q": consulta, "vqd": vqd, "f": ",,,,,", "p": "1"},
                headers=headers, timeout=8
            )
            data2 = r2.json()
            for item in data2.get("results", [])[:num_imagenes]:
                img_url = item.get("image")
                if img_url:
                    urls.append(img_url)
            if urls:
                print(f"[IMAGEN] {len(urls)} imagen(es) encontrada(s) mediante DuckDuckGo.")
                return urls
    except Exception as e:
        print(f"[IMAGEN] Error en DuckDuckGo Images: {e}")

    print(f"[IMAGEN] No se encontraron imágenes para: {consulta}")
    return []


def buscar_web_serpapi(consulta):
    """Realiza una búsqueda en Google mediante SerpAPI."""
    if not _clave_valida(SERPAPI_API_KEY):
        return None
    
    try:
        print(f"[WEB] Buscando con SerpAPI para: {consulta}")
        params = {
            "engine": "google",
            "q": consulta,
            "api_key": SERPAPI_API_KEY,
            "hl": "es",
            "gl": "es"
        }
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=10)
        data = r.json()
        
        # Extracción de noticias si están presentes
        if "news_results" in data:
            noticias = data["news_results"][:3]
            respuesta = f"Estas son las últimas noticias sobre {consulta}:\n"
            for n in noticias:
                fuente = n.get("source", "Fuente desconocida")
                titulo = n.get("title", "")
                respuesta += f"- {titulo} (vía {fuente})\n"
            return respuesta
            
        # Extracción de resultados orgánicos en su defecto
        if "organic_results" in data:
            resultados = data["organic_results"][:3]
            respuesta = f"Esto es lo que he encontrado en la web sobre {consulta}:\n"
            for r in resultados:
                titulo = r.get("title", "")
                snippet = r.get("snippet", "")
                respuesta += f"- {titulo} : {snippet}\n"
            return respuesta
            
        return f"No he encontrado nada relevante en la web sobre: {consulta}."
    except Exception as e:
        print(f"[WEB] Error en SerpAPI: {e}")
        return "Se ha producido un error en la búsqueda en internet."

THESPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/3"

def obtener_resultados_futbol(equipo=None, liga=None):
    try:
        if equipo:
            print(f"[DEPORTE] Buscando para el equipo: {equipo}")
            r = requests.get(f"{THESPORTSDB_BASE}/searchteams.php", params={"t": equipo}, timeout=5)
            data = r.json()
            equipos = data.get("teams")
            if not equipos:
                return f"No he encontrado el equipo {equipo}."
            
            equipo_id   = equipos[0]["idTeam"]
            nombre_equipo = equipos[0]["strTeam"]
            
            # Buscar los últimos Y los próximos partidos
            res_ultimos = requests.get(f"{THESPORTSDB_BASE}/eventslast.php", params={"id": equipo_id}, timeout=5).json()
            res_proximos = requests.get(f"{THESPORTSDB_BASE}/eventsnext.php", params={"id": equipo_id}, timeout=5).json()
            
            partidos_pasados = res_ultimos.get("results", [])
            partidos_futuros = res_proximos.get("events", [])
            
            respuesta = f"Con respecto al {nombre_equipo}: "
            
            if partidos_futuros:
                m = partidos_futuros[0]
                fecha_m = m.get("dateEvent", "fecha desconocida")
                hora_m = m.get("strTime", "")
                respuesta += f"El próximo partido será el {fecha_m} a las {hora_m} contra {m.get('strOpponent')}. "
            
            if partidos_pasados:
                m = partidos_pasados[0]
                respuesta += f"Su último resultado fue {m.get('intHomeScore')} a {m.get('intAwayScore')} contra {m.get('strOpponent')}."
            
            if not partidos_futuros and not partidos_pasados:
                return f"No tengo información reciente o futura para {nombre_equipo}."
                
            return respuesta
        else:
            nombre_liga = liga or "Liga 1"
            ids_liga = {
                "liga 1": "4334", "premier league": "4328", "liga": "4335",
                "bundesliga": "4331", "serie a": "4332",
                "champions league": "4480", "liga de campeones": "4480",
            }
            liga_id = ids_liga.get(nombre_liga.lower(), "4334")
            r = requests.get(f"{THESPORTSDB_BASE}/eventspastleague.php", params={"id": liga_id}, timeout=5)
            data   = r.json()
            partidos = data.get("events", [])
            if not partidos:
                return f"No se encontraron resultados para {nombre_liga}."
            respuesta = f"Últimos resultados de {nombre_liga}: "
            lineas  = []
            for m in partidos[-6:]:
                local    = m.get("strHomeTeam", "?")
                visitante    = m.get("strAwayTeam", "?")
                goles_local = m.get("intHomeScore", "?")
                goles_visitante = m.get("intAwayScore", "?")
                fecha    = m.get("dateEvent", "?")
                lineas.append(f"{local} {goles_local}-{goles_visitante} {visitante} ({fecha})")
            return respuesta + " | ".join(lineas)
    except Exception as e:
        print(f"[DEPORTE] Error en fútbol: {e}")
        return f"No se pudieron recuperar los resultados de fútbol: {e}"

def obtener_clasificacion_futbol(liga=None):
    try:
        nombre_liga = liga or "Liga 1"
        ids_liga = {
            "liga 1": "4334", "premier league": "4328", "liga": "4335",
            "bundesliga": "4331", "serie a": "4332",
            "champions league": "4480", "liga de campeones": "4480",
        }
        liga_id = ids_liga.get(nombre_liga.lower(), "4334")
        r = requests.get(f"{THESPORTSDB_BASE}/lookuptable.php", params={"l": liga_id, "s": "2024-2025"}, timeout=8)
        data    = r.json()
        tabla = data.get("table", [])
        if not tabla:
            return f"Clasificación de {nombre_liga} no disponible por el momento."
        respuesta = f"Clasificación de {nombre_liga}: "
        lineas  = []
        for eq in tabla[:10]:
            pos   = eq.get("intRank", "?")
            nombre   = eq.get("strTeam", "?")
            pts   = eq.get("intPoints", "?")
            jugados = eq.get("intPlayed", "?")
            lineas.append(f"{pos}. {nombre} - {pts}pts ({jugados}J)")
        return respuesta + " | ".join(lineas)
    except Exception as e:
        print(f"[DEPORTE] Error en clasificación: {e}")
        return f"No se pudo recuperar la clasificación: {e}"

def obtener_resultados_deporte_gemini(pregunta_deporte):
    try:
        import builtins
        client = builtins.client
        modelo = getattr(builtins, "CHOSEN_MODEL", "gemini-2.5-flash")
        response = client.models.generate_content(
            model=modelo,
            contents=[types.Content(role="user", parts=[types.Part(text=
                f"Dame los últimos resultados y noticias deportivas en 2026 "
                f"para: {pregunta_deporte}. "
                f"Sé preciso, da los marcadores y fechas. Responde en español."
            )])],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                system_instruction=(
                    "Eres un experto deportivo. Da resultados precisos y actualizados. "
                    "Responde de forma concisa y conversacional en español."
                )
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"[DEPORTE] Error en Gemini deportes: {e}")
        return "No puedo recuperar los resultados deportivos en este momento."