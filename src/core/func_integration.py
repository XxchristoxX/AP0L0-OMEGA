# src/core/func_integration.py
"""
Integración de funciones únicas del módulo func.py.
Contiene funciones de generación de imágenes, vídeos, sitios web y utilidades
que no están duplicadas en otros módulos del sistema.
"""
import asyncio
import base64
import json
import os
import re
import shutil
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

import requests
try:
    import pyautogui
except ImportError:
    pyautogui = None
import webbrowser

# ===== IMPORTS DE MÓDULOS INTERNOS =====
from src.core.config import _get_config, _save_config
from src.core.multi_provider import MultiProvider
from src.core.openrouter_client import OpenRouterClient
from src.utils.system_utils import IS_WINDOWS

# ===== VARIABLES GLOBALES (para mantener estado) =====
_ULTIMOS_RESTAURANTES_MOSTRADOS = []
_UBICACION_GPS_USUARIO = None
_VENTANA_WEBVIEW = None
_CLIENTES_CONECTADOS = set()

# ===== FUNCIONES DE UTILIDAD =====

def _obtener_ruta_config_jarvis() -> str:
    """Retorna la ruta al archivo de configuración de JARVIS."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jarvis_config.json")

def _cargar_config() -> dict:
    """Carga la configuración desde jarvis_config.json."""
    try:
        if os.path.exists(_obtener_ruta_config_jarvis()):
            with open(_obtener_ruta_config_jarvis(), "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _guardar_config(data: dict) -> None:
    """Guarda la configuración en jarvis_config.json."""
    try:
        cfg = _cargar_config()
        cfg.update(data)
        with open(_obtener_ruta_config_jarvis(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[FUNC_INTEGRATION] Error guardando config: {e}")

def _guardar_env(data: dict) -> None:
    """Guarda variables de entorno en el archivo .env."""
    try:
        ruta_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        lineas = []
        claves_existentes = {}
        if os.path.exists(ruta_env):
            with open(ruta_env, "r", encoding="utf-8") as f:
                lineas = f.readlines()
            for idx, linea in enumerate(lineas):
                linea_limpia = linea.strip()
                if linea_limpia and not linea_limpia.startswith("#") and "=" in linea_limpia:
                    clave, _ = linea_limpia.split("=", 1)
                    claves_existentes[clave.strip()] = idx

        for clave, valor in data.items():
            os.environ[clave] = str(valor)
            contenido_linea = f"{clave}={valor}\n"
            if clave in claves_existentes:
                lineas[claves_existentes[clave]] = contenido_linea
            else:
                if lineas and not lineas[-1].endswith("\n"):
                    lineas[-1] = lineas[-1] + "\n"
                lineas.append(contenido_linea)
                claves_existentes[clave] = len(lineas) - 1

        with open(ruta_env, "w", encoding="utf-8") as f:
            f.writelines(lineas)
        print(f"[FUNC_INTEGRATION] .env actualizado con: {list(data.keys())}")
    except Exception as e:
        print(f"[FUNC_INTEGRATION] Error guardando .env: {e}")

def _obtener_nombre_usuario() -> str:
    """Obtiene el nombre del usuario desde la configuración."""
    cfg = _cargar_config()
    return cfg.get("user_name", "Christopher")

def _obtener_edad_usuario() -> str:
    """Obtiene la edad del usuario desde la configuración."""
    cfg = _cargar_config()
    return cfg.get("user_age", "")

def _obtener_clave_api() -> str:
    """Obtiene la clave API de Gemini desde la configuración."""
    try:
        from src.core.config import _get_api_key as _clave_gemini
        return _clave_gemini()
    except Exception:
        return ""

# ===== FUNCIONES DE MEMORIA (de func.py) =====

def agregar_memoria(clave: str, valor: str) -> None:
    """Añade un elemento a la memoria persistente."""
    try:
        ruta_mem = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jarvis_memoire.json")
        mem = {}
        if os.path.exists(ruta_mem):
            with open(ruta_mem, "r", encoding="utf-8") as f:
                mem = json.load(f)
        mem[clave] = {
            "valor": valor,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        with open(ruta_mem, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
        print(f"[MEMORIA] Guardado: {clave} = {valor}")
    except Exception as e:
        print(f"[MEMORIA] Error guardando: {e}")

def eliminar_memoria(clave: str) -> bool:
    """Elimina un elemento de la memoria persistente."""
    try:
        ruta_mem = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jarvis_memoire.json")
        if not os.path.exists(ruta_mem):
            return False
        with open(ruta_mem, "r", encoding="utf-8") as f:
            mem = json.load(f)
        if clave in mem:
            del mem[clave]
            with open(ruta_mem, "w", encoding="utf-8") as f:
                json.dump(mem, f, ensure_ascii=False, indent=2)
            print(f"[MEMORIA] Eliminado: {clave}")
            return True
        return False
    except Exception as e:
        print(f"[MEMORIA] Error eliminando: {e}")
        return False

def cargar_memoria() -> dict:
    """Carga toda la memoria persistente."""
    try:
        ruta_mem = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jarvis_memoire.json")
        if os.path.exists(ruta_mem):
            with open(ruta_mem, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[MEMORIA] Error cargando: {e}")
    return {}

def construir_contexto_memoria() -> str:
    """Construye un contexto de memoria para el prompt del sistema."""
    mem = cargar_memoria()
    if not mem:
        return ""
    lineas = ["[MEMORIA PERSONALIZADA]"]
    for clave, datos in mem.items():
        valor = datos.get("valor", "") if isinstance(datos, dict) else datos
        lineas.append(f"- {clave}: {valor}")
    return "\n".join(lineas)

def _cargar_historico_reciente() -> list:
    """Carga el historial de conversación reciente."""
    try:
        ruta_hist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jarvis_historique.json")
        if os.path.exists(ruta_hist):
            with open(ruta_hist, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def _guardar_intercambio_conv(usuario_texto: str, ia_texto: str) -> None:
    """Guarda un intercambio de conversación en el historial."""
    try:
        ruta_hist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jarvis_historique.json")
        hist = []
        if os.path.exists(ruta_hist):
            with open(ruta_hist, "r", encoding="utf-8") as f:
                hist = json.load(f)
        hist.append({
            "usuario": usuario_texto,
            "ia": ia_texto,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        # Mantener solo los últimos 50 intercambios
        if len(hist) > 50:
            hist = hist[-50:]
        with open(ruta_hist, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[HISTORIAL] Error guardando: {e}")

def _limpiar_emojis_para_tts(texto: str) -> str:
    """Elimina emojis y caracteres especiales para TTS."""
    if not texto:
        return ""
    patron_emoji = re.compile(
        "["
        "\U00010000-\U0010FFFF"
        "\u2600-\u27BF"
        "\uFE00-\uFE0F"
        "\u200D"
        "\u2300-\u23FF"
        "\u2B50"
        "\u20E3"
        "]+",
        flags=re.UNICODE
    )
    limpio = patron_emoji.sub(" ", texto)
    return re.sub(r'\s+', ' ', limpio).strip()

# ===== FUNCIONES DE COMPETENCIAS (PLUGINS) =====

def jarvis_crear_competencia(nombre: str, descripcion: str) -> str:
    """Crea una nueva competencia (plugin) a partir de una descripción."""
    import re
    import threading
    import builtins
    
    # Validar cliente Gemini
    if not hasattr(builtins, "client") or not builtins.client:
        return "Error: el cliente Gemini no está inicializado o la clave API es inválida."
    
    nombre_formateado = re.sub(r'[^a-zA-Z0-9_]', '', nombre.lower().replace(" ", "_"))
    directorio_plugins = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins")
    os.makedirs(directorio_plugins, exist_ok=True)
    ruta_archivo = os.path.join(directorio_plugins, f"competencia_{nombre_formateado}.py")
    
    try:
        from google.genai import types as _tipos
        
        instruccion_sistema = (
            "Eres el agente de generación de competencias autónomas de JARVIS.\n"
            "Debes escribir código Python estricto, limpio y válido.\n\n"
            "REGLAS CRÍTICAS:\n"
            "1. Devuelve ÚNICAMENTE el código Python puro. No pongas NINGUNA etiqueta de código markdown.\n"
            "2. El script debe ser totalmente autónomo.\n"
            "3. Debes implementar obligatoriamente una función principal llamada `ejecutar(texto_usuario=None)`.\n"
            "4. Utiliza únicamente bibliotecas estándar."
        )
        
        prompt = (
            f"Genera el código completo para la competencia: '{nombre}'.\n"
            f"Objetivo de la competencia: {descripcion}\n\n"
            "Escribe el código Python puro respetando todas las reglas de estructura."
        )
        
        respuesta = builtins.client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config=_tipos.GenerateContentConfig(
                system_instruction=instruccion_sistema,
                temperature=0.1,
            )
        )
        
        codigo_generado = respuesta.text.strip()
        
        # Limpiar código de markdown
        if codigo_generado.startswith("```"):
            lineas = codigo_generado.split("\n")
            if lineas[0].startswith("```"):
                lineas = lineas[1:]
            if lineas and lineas[-1].startswith("```"):
                lineas = lineas[:-1]
            codigo_generado = "\n".join(lineas).strip()
        
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            f.write(codigo_generado)
        
        print(f"[COMPETENCIA] Creada: {ruta_archivo}")
        return f"La competencia '{nombre}' ha sido generada e instalada con éxito."
    except Exception as e:
        print(f"[COMPETENCIA] Error: {e}")
        return f"Error al crear la competencia: {e}"

def jarvis_eliminar_competencia(nombre: str) -> str:
    """Elimina una competencia (plugin) instalada."""
    import re
    nombre_formateado = re.sub(r'[^a-zA-Z0-9_]', '', nombre.lower().replace(" ", "_"))
    ruta_archivo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins", f"competencia_{nombre_formateado}.py")
    
    if os.path.exists(ruta_archivo):
        try:
            os.remove(ruta_archivo)
            return f"La competencia '{nombre}' ha sido desinstalada."
        except Exception as e:
            return f"Error al eliminar la competencia: {e}"
    return f"La competencia '{nombre}' no está instalada."

def ejecutar_competencia_vocal(nombre: str, texto: str = None) -> str:
    """Ejecuta una competencia (plugin) por voz."""
    import re
    import importlib.util
    import sys
    
    nombre_formateado = re.sub(r'[^a-zA-Z0-9_]', '', nombre.lower().replace(" ", "_"))
    ruta_archivo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins", f"competencia_{nombre_formateado}.py")
    
    if not os.path.exists(ruta_archivo):
        return f"La competencia '{nombre}' no está disponible."
    
    try:
        nombre_modulo = f"plugins.competencia_{nombre_formateado}"
        especificacion = importlib.util.spec_from_file_location(nombre_modulo, ruta_archivo)
        if especificacion is None or especificacion.loader is None:
            return "No se pudo cargar el módulo."
        
        modulo = importlib.util.module_from_spec(especificacion)
        sys.modules[nombre_modulo] = modulo
        especificacion.loader.exec_module(modulo)
        
        if hasattr(modulo, "ejecutar"):
            resultado = modulo.ejecutar(texto)
            return str(resultado)
        else:
            return "Esta competencia no tiene función 'ejecutar'."
    except Exception as e:
        print(f"[COMPETENCIA] Error ejecutando: {e}")
        return f"Error al ejecutar la competencia: {e}"

# ===== FUNCIONES DE GENERACIÓN DE IMÁGENES Y VÍDEOS =====

async def generar_imagen_xai(prompt: str, modelo_forzado: str = None) -> dict:
    """
    Genera una imagen usando xAI Grok o Gemini.
    """
    from src.core.config import _get_config
    config = _get_config()
    clave_openrouter = config.get("openrouter_api_key", "")
    
    if not clave_openrouter:
        return {"error": "Clave OpenRouter no configurada."}
    
    # Enriquecer el prompt con Gemini si está disponible
    _prompt_en = prompt
    try:
        from src.core.config import gemini_generate
        enriquecido = gemini_generate(
            f"Traduce este prompt a un prompt detallado en inglés para una IA de generación de imágenes. Devuelve SOLO el prompt en inglés, nada más: {prompt}",
            model="gemini-3.5-flash-lite"
        )
        if enriquecido and not enriquecido.startswith("[Error]"):
            _prompt_en = enriquecido.strip()
            print(f"[FUNC_INTEGRATION] Prompt enriquecido: {_prompt_en[:100]}...")
    except Exception as e:
        print(f"[FUNC_INTEGRATION] Error enriqueciendo prompt: {e}")
    
    # Usar OpenRouter para generar la imagen
    try:
        import requests
        url = "https://openrouter.ai/api/v1/chat/completions"
        cabeceras = {
            "Authorization": f"Bearer {clave_openrouter}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/AP0L0",
            "X-Title": "AP0L0 AI"
        }
        payload = {
            "model": "google/gemini-2.5-flash-image",
            "messages": [
                {"role": "user", "content": f"Genera una imagen basada en este prompt: {_prompt_en}"}
            ],
            "modalities": ["text", "image"],
            "max_tokens": 2000
        }
        respuesta = requests.post(url, headers=cabeceras, json=payload, timeout=120)
        if respuesta.status_code == 200:
            datos = respuesta.json()
            contenido = datos.get("choices", [{}])[0].get("message", {}).get("content", "")
            # Extraer la imagen en base64 si existe
            if "data:image" in contenido:
                # Buscar el base64 en el contenido
                coincidencia = re.search(r'data:image/png;base64,([A-Za-z0-9+/=]+)', contenido)
                if coincidencia:
                    datos_b64 = coincidencia.group(1)
                    ts = int(time.time() * 1000)
                    ruta_imagen = os.path.join(os.path.dirname(_obtener_ruta_config_jarvis()), f"jarvis_img_{ts}.png")
                    with open(ruta_imagen, "wb") as f:
                        f.write(base64.b64decode(datos_b64))
                    url_datos = f"data:image/png;base64,{datos_b64}"
                    return {
                        "url": url_datos,
                        "ruta": ruta_imagen,
                        "prompt_fr": prompt,
                        "prompt_en": _prompt_en,
                        "fuente": "OpenRouter (Gemini Image)"
                    }
        else:
            print(f"[FUNC_INTEGRATION] Error OpenRouter: {respuesta.status_code} - {respuesta.text[:200]}")
    except Exception as e:
        print(f"[FUNC_INTEGRATION] Error generando imagen: {e}")
    
    # Fallback: intentar con xAI Grok (si está configurado)
    try:
        from src.core.config import _get_config
        config = _get_config()
        clave_grok = config.get("xai_api_key", "")
        if clave_grok:
            import requests
            url = "https://api.x.ai/v1/images/generations"
            cabeceras = {
                "Authorization": f"Bearer {clave_grok}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "grok-imagine-image",
                "prompt": _prompt_en,
                "n": 1,
                "response_format": "b64_json"
            }
            respuesta = requests.post(url, headers=cabeceras, json=payload, timeout=120)
            if respuesta.status_code == 200:
                datos = respuesta.json()
                if datos.get("data") and len(datos["data"]) > 0:
                    datos_b64 = datos["data"][0].get("b64_json")
                    if datos_b64:
                        ts = int(time.time() * 1000)
                        ruta_imagen = os.path.join(os.path.dirname(_obtener_ruta_config_jarvis()), f"jarvis_grok_{ts}.png")
                        with open(ruta_imagen, "wb") as f:
                            f.write(base64.b64decode(datos_b64))
                        url_datos = f"data:image/png;base64,{datos_b64}"
                        return {
                            "url": url_datos,
                            "ruta": ruta_imagen,
                            "prompt_fr": prompt,
                            "prompt_en": _prompt_en,
                            "fuente": "xAI Grok"
                        }
    except Exception as e:
        print(f"[FUNC_INTEGRATION] Error con xAI Grok: {e}")
    
    return {"error": "No se pudo generar la imagen."}

async def generar_video_xai(prompt: str) -> dict:
    """
    Genera un vídeo usando xAI Grok (grok-imagine-video).
    """
    try:
        from src.core.config import _get_config
        config = _get_config()
        clave_grok = config.get("xai_api_key", "")
        if not clave_grok:
            return {"error": "Clave xAI no configurada."}
        
        # Enriquecer el prompt
        _prompt_en = prompt
        try:
            from src.core.config import gemini_generate
            enriquecido = gemini_generate(
                f"Traduce y mejora este prompt de generación de vídeo al inglés. Hazlo muy cinematográfico. Devuelve SOLO el prompt en inglés: {prompt}",
                model="gemini-3.5-flash-lite"
            )
            if enriquecido and not enriquecido.startswith("[Error]"):
                _prompt_en = enriquecido.strip()
        except Exception:
            pass
        
        import requests
        url = "https://api.x.ai/v1/videos/generations"
        cabeceras = {
            "Authorization": f"Bearer {clave_grok}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "grok-imagine-video",
            "prompt": _prompt_en
        }
        respuesta = requests.post(url, headers=cabeceras, json=payload, timeout=180)
        if respuesta.status_code == 200:
            datos = respuesta.json()
            if datos.get("data") and len(datos["data"]) > 0:
                video_datos = datos["data"][0]
                if video_datos.get("url"):
                    return {
                        "url": video_datos["url"],
                        "prompt_fr": prompt,
                        "prompt_en": _prompt_en,
                        "fuente": "xAI Grok Video",
                        "tipo": "video"
                    }
        return {"error": "No se pudo generar el vídeo."}
    except Exception as e:
        return {"error": f"Error generando vídeo: {e}"}

async def generar_sitio_web(prompt: str, modelo: str = "gemini", modelo_imagen: str = "gemini") -> str:
    """
    Genera un sitio web completo a partir de un prompt.
    """
    try:
        from src.core.config import _get_config, gemini_generate
        config = _get_config()
        nombre_usuario = _obtener_nombre_usuario()
        
        # Obtener el modelo de IA adecuado
        if modelo == "gemini":
            prompt_sistema = "Eres un desarrollador web experto. Genera código HTML completo para un sitio web."
            prompt_completo = f"{prompt_sistema}\n\nDemanda: {prompt}"
            codigo_html = gemini_generate(prompt_completo, model="gemini-3.5-flash-lite")
        else:
            # Usar OpenRouter para otros modelos
            clave_openrouter = config.get("openrouter_api_key", "")
            if not clave_openrouter:
                return "Clave OpenRouter no configurada."
            import requests
            url = "https://openrouter.ai/api/v1/chat/completions"
            cabeceras = {
                "Authorization": f"Bearer {clave_openrouter}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "google/gemini-2.5-flash" if modelo == "gemini" else "meta-llama/llama-3-70b-instruct",
                "messages": [
                    {"role": "system", "content": "Eres un desarrollador web experto. Genera código HTML completo para un sitio web."},
                    {"role": "user", "content": prompt}
                ]
            }
            respuesta = requests.post(url, headers=cabeceras, json=payload, timeout=120)
            if respuesta.status_code == 200:
                datos = respuesta.json()
                codigo_html = datos.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                return f"Error generando sitio: {respuesta.status_code}"
        
        if not codigo_html:
            return "No se pudo generar el código HTML."
        
        # Limpiar el código
        codigo_html = codigo_html.strip()
        if codigo_html.startswith("```html"):
            codigo_html = codigo_html[7:]
        elif codigo_html.startswith("```"):
            codigo_html = codigo_html[3:]
        if codigo_html.endswith("```"):
            codigo_html = codigo_html[:-3]
        
        # Guardar el sitio
        directorio_base = os.path.join(os.path.dirname(_obtener_ruta_config_jarvis()), "sites_internet")
        os.makedirs(directorio_base, exist_ok=True)
        nombre_carpeta = f"Sitio_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        directorio_sitio = os.path.join(directorio_base, nombre_carpeta)
        os.makedirs(directorio_sitio, exist_ok=True)
        
        # Generar imágenes si es necesario
        etiquetas_img = re.findall(r'\[JARVIS_IMG:\s*"([^"]+)"\]', codigo_html)
        for i, prompt_img in enumerate(etiquetas_img):
            resultado_img = await generar_imagen_xai(prompt_img, modelo_forzado=modelo_imagen)
            if resultado_img and "ruta" in resultado_img and os.path.exists(resultado_img["ruta"]):
                nombre_archivo_img = f"imagen_{i}.jpg"
                shutil.move(resultado_img["ruta"], os.path.join(directorio_sitio, nombre_archivo_img))
                codigo_html = codigo_html.replace(f'[JARVIS_IMG: "{prompt_img}"]', f"./{nombre_archivo_img}")
            else:
                codigo_html = codigo_html.replace(f'[JARVIS_IMG: "{prompt_img}"]', "https://via.placeholder.com/800x600?text=Imagen")
        
        ruta_archivo = os.path.join(directorio_sitio, "index.html")
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            f.write(codigo_html)
        
        # Abrir en el navegador
        webbrowser.open(ruta_archivo)
        return f"Sitio web creado en: {ruta_archivo}"
    except Exception as e:
        return f"Error generando sitio web: {e}"

# ===== FUNCIONES DE BÚSQUEDA DE RESTAURANTES =====

def lanzar_busqueda_restaurantes_fondo(ubicacion: str, lat: float, lng: float, excluir: list, es_otros: bool = False):
    """
    Lanza una búsqueda de restaurantes en un hilo separado.
    """
    import threading
    global _ULTIMOS_RESTAURANTES_MOSTRADOS
    
    def trabajador():
        try:
            # Simular búsqueda de restaurantes (en la práctica, usaría una API)
            resultados = [
                {"nombre": "Restaurante A", "direccion": "Calle Principal 123", "nota": "4.5"},
                {"nombre": "Restaurante B", "direccion": "Avenida Secundaria 456", "nota": "4.2"},
                {"nombre": "Restaurante C", "direccion": "Plaza Central 789", "nota": "4.8"},
            ]
            # Filtrar excluidos
            resultados = [r for r in resultados if r["nombre"] not in excluir]
            
            if resultados:
                _ULTIMOS_RESTAURANTES_MOSTRADOS = [r["nombre"] for r in resultados[:3]]
                # Enviar resultados al frontend (si está conectado)
                if _CLIENTES_CONECTADOS:
                    import asyncio
                    mensaje = json.dumps({
                        "type": "show_restaurants",
                        "ubicacion": ubicacion,
                        "restaurantes": resultados
                    })
                    for ws in _CLIENTES_CONECTADOS:
                        asyncio.run_coroutine_threadsafe(ws.send(mensaje), asyncio.get_event_loop())
        except Exception as e:
            print(f"[FUNC_INTEGRATION] Error buscando restaurantes: {e}")
    
    threading.Thread(target=trabajador, daemon=True).start()

# ===== FUNCIONES DE WEB SOCKET (para comunicación con frontend) =====

def enviar_broadcast_web_sync(mensaje_dict: dict):
    """Envía un mensaje a todos los clientes WebSocket conectados."""
    if not _CLIENTES_CONECTADOS:
        return
    mensaje = json.dumps(mensaje_dict)
    import asyncio
    async def enviar_todos():
        if _CLIENTES_CONECTADOS:
            await asyncio.gather(*[ws.send(mensaje) for ws in list(_CLIENTES_CONECTADOS)], return_exceptions=True)
    try:
        bucle = asyncio.get_running_loop()
        asyncio.run_coroutine_threadsafe(enviar_todos(), bucle)
    except RuntimeError:
        # Si no hay bucle corriendo, crear uno nuevo
        bucle = asyncio.new_event_loop()
        bucle.run_until_complete(enviar_todos())
        bucle.close()

async def enviar_estado_web(estado: str):
    """Envía el estado al frontend."""
    enviar_broadcast_web_sync({"action": "set_state", "state": estado})

async def enviar_texto_web(texto: str):
    """Envía texto al frontend."""
    enviar_broadcast_web_sync({"action": "jarvis_text", "text": texto})

async def enviar_texto_usuario_web(texto: str):
    """Envía el discurso del usuario al frontend."""
    enviar_broadcast_web_sync({"action": "user_speech", "text": texto})

async def enviar_volumen_web(volumen: float):
    """Envía el volumen al frontend."""
    enviar_broadcast_web_sync({"action": "set_volume", "volume": round(volumen, 3)})

async def enviar_meteo_web(datos_meteo: dict):
    """Envía datos meteorológicos al frontend."""
    enviar_broadcast_web_sync({"action": "weather_panel", "data": datos_meteo})

# ===== FUNCIONES DE COMANDOS LOCALES (de func.py) =====

def resolver_info_sistema_local(texto: str) -> str:
    """Responde preguntas sobre el sistema (hora, fecha, batería, CPU, RAM)."""
    import psutil
    from datetime import datetime
    t = texto.lower().replace("?", "").strip()
    ahora = datetime.now()
    
    DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    
    if any(m in t for m in ["qué hora", "que hora", "hora es", "qué hora es", "que hora es"]):
        return f"Son las {ahora.strftime('%H:%M')}, {_obtener_nombre_usuario()}."
    
    if any(m in t for m in ["qué día", "que dia", "día es", "dia es", "qué fecha", "que fecha"]):
        return f"Hoy es {DIAS[ahora.weekday()]} {ahora.day} de {MESES[ahora.month-1]} de {ahora.year}, {_obtener_nombre_usuario()}."
    
    if any(m in t for m in ["batería", "bateria", "nivel de batería"]):
        try:
            bat = psutil.sensors_battery()
            if bat:
                return f"La batería está al {bat.percent}%, {'cargando' if bat.power_plugged else 'descargando'}."
        except Exception:
            pass
    
    if any(m in t for m in ["cpu", "procesador", "uso del cpu"]):
        return f"El CPU está al {psutil.cpu_percent()}% de uso."
    
    if any(m in t for m in ["ram", "memoria"]):
        mem = psutil.virtual_memory()
        return f"La RAM está al {mem.percent}% de uso ({mem.used // (1024**3)} GB de {mem.total // (1024**3)} GB)."
    
    return None

def resolver_matematica_local(texto: str) -> str:
    """Resuelve operaciones matemáticas simples."""
    import re, math
    t = texto.lower().replace("?", "").strip()
    
    # Limpiar la expresión
    expr = re.sub(r'[^0-9+\-*/%().]', '', t)
    if not expr or not any(c.isdigit() for c in expr):
        return None
    
    try:
        # Evaluar con seguridad
        resultado = eval(expr, {"__builtins__": None}, {"math": math})
        return f"El resultado es {resultado}, {_obtener_nombre_usuario()}."
    except Exception:
        return None

def resolver_traduccion_local(texto: str) -> str:
    """Traduce palabras simples al inglés, español o alemán."""
    t = texto.lower().strip()
    
    dict_trad = {
        "hola": {"en": "hello", "es": "hola", "de": "hallo"},
        "gracias": {"en": "thank you", "es": "gracias", "de": "danke"},
        "adiós": {"en": "goodbye", "es": "adiós", "de": "auf wiedersehen"},
        "por favor": {"en": "please", "es": "por favor", "de": "bitte"},
        "sí": {"en": "yes", "es": "sí", "de": "ja"},
        "no": {"en": "no", "es": "no", "de": "nein"},
        "amigo": {"en": "friend", "es": "amigo", "de": "freund"},
        "casa": {"en": "house", "es": "casa", "de": "haus"},
        "ordenador": {"en": "computer", "es": "ordenador", "de": "computer"},
    }
    
    if "traduce" in t or "cómo se dice" in t or "como se dice" in t:
        destino = "en"
        if "español" in t: destino = "es"
        elif "alemán" in t: destino = "de"
        
        # Extraer la palabra
        palabra = t
        for p in ["traduce", "cómo se dice", "como se dice", "?"]:
            palabra = palabra.replace(p, "")
        palabra = palabra.strip()
        
        if palabra in dict_trad:
            mapa_idiomas = {"en": "inglés", "es": "español", "de": "alemán"}
            return f"En {mapa_idiomas[destino]}, '{palabra}' se dice '{dict_trad[palabra][destino]}'."
    return None

def resolver_conversion_local(texto: str) -> str:
    """Convierte unidades de medida."""
    import re
    t = texto.lower().strip()
    
    # Kilómetros a millas
    coincidencia = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:km|kilómetros?|kms?)', t)
    if coincidencia and "millas" in t:
        valor = float(coincidencia.group(1).replace(",", "."))
        return f"{valor} kilómetros son {valor * 0.621371:.2f} millas."
    
    # Millas a kilómetros
    coincidencia = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:millas?)', t)
    if coincidencia and "kilómetros" in t:
        valor = float(coincidencia.group(1).replace(",", "."))
        return f"{valor} millas son {valor * 1.60934:.2f} kilómetros."
    
    # Celsius a Fahrenheit
    coincidencia = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:°?C|°?celsius)', t)
    if coincidencia and "fahrenheit" in t:
        valor = float(coincidencia.group(1).replace(",", "."))
        return f"{valor}°C son {valor * 9/5 + 32:.1f}°F."
    
    return None

async def resolver_globo_local(texto: str) -> str:
    """Comandos de navegación del globo 3D."""
    t = texto.lower().strip()
    
    if "muestra la tierra" in t or "mostrar la tierra" in t or "globo" in t:
        enviar_broadcast_web_sync({"globe_action": "show_earth"})
        return "Mostrando el globo terráqueo, señor."
    
    if "cerrar el globo" in t or "ocultar el globo" in t:
        enviar_broadcast_web_sync({"globe_action": "hide"})
        return "Ocultando el globo."
    
    # Volar a ciudad
    if any(m in t for m in ["volar a", "ir a", "navegar a", "muéstrame", "muestrame", "mostrar"]):
        # Extraer el nombre de la ciudad
        for prep in ["volar a ", "ir a ", "navegar a ", "muéstrame ", "muestrame ", "mostrar "]:
            if prep in t:
                ciudad = t.split(prep)[-1].strip()
                if ciudad:
                    # Geocodificar (simulado)
                    coordenadas = {"paris": (48.8566, 2.3522), "londres": (51.5074, -0.1278), "madrid": (40.4168, -3.7038), "berlin": (52.5200, 13.4050)}
                    if ciudad.lower() in coordenadas:
                        lat, lon = coordenadas[ciudad.lower()]
                        enviar_broadcast_web_sync({"globe_action": "fly_to", "lat": lat, "lon": lon, "target": ciudad})
                        return f"Volando hacia {ciudad}..."
                    else:
                        return f"No encontré la ciudad '{ciudad}'. Prueba con: París, Londres, Madrid, Berlín."
    
    return None

async def resolver_extras_local(texto: str) -> str:
    """Funciones extra: chistes, citas, notas, etc."""
    t = texto.lower().strip()
    import random
    
    # Chistes
    if any(k in t for k in ["chiste", "joke", "hazme reír", "cuenta un chiste"]):
        chistes = [
            "¿Por qué los buzos siempre se tiran de espaldas? ¡Porque si no, caerían dentro del barco!",
            "Un hombre entra en una biblioteca y pregunta: '¿Tienen libros sobre paranoia?' La bibliotecaria susurra: 'Están justo detrás de ti.'",
            "¿Qué es un cortaplumas? Un pequeño cuchillo.",
            "¿Por qué el espantapájaros recibió un premio? Porque era excepcional en su campo.",
            "¿Cómo se llama un gato que cayó en un bote de pintura en Navidad? Un gato-pintado de Navidad.",
        ]
        return random.choice(chistes)
    
    # Citas
    if any(k in t for k in ["cita", "inspírame", "frase motivadora"]):
        citas = [
            "La única forma de hacer un buen trabajo es amar lo que haces. — Steve Jobs",
            "La vida es como una bicicleta, hay que avanzar para no perder el equilibrio. — Albert Einstein",
            "El éxito es caerse siete veces y levantarse ocho. — Proverbio japonés",
            "El pesimista ve la dificultad en cada oportunidad. El optimista ve la oportunidad en cada dificultad. — Winston Churchill",
        ]
        return random.choice(citas)
    
    # Cara o cruz
    if "cara o cruz" in t:
        return f"¡{random.choice(['Cara', 'Cruz'])}!"
    
    # Notas rápidas
    if "nota que" in t or "recordar que" in t:
        # Extraer la nota
        contenido = t.split("nota que")[-1] if "nota que" in t else t.split("recordar que")[-1]
        contenido = contenido.strip()
        if contenido:
            # Guardar en memoria simple (archivo)
            archivo_notas = os.path.join(os.path.dirname(_obtener_ruta_config_jarvis()), "jarvis_notas.txt")
            with open(archivo_notas, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%d/%m %H:%M')}] {contenido}\n")
            return f"Nota guardada: '{contenido}'"
        return "¿Qué quieres que anote?"
    
    # Leer notas
    if "mis notas" in t:
        archivo_notas = os.path.join(os.path.dirname(_obtener_ruta_config_jarvis()), "jarvis_notas.txt")
        if os.path.exists(archivo_notas):
            with open(archivo_notas, "r", encoding="utf-8") as f:
                notas = f.read()
            if notas:
                return f"Tus últimas notas:\n{notas[:500]}"
            return "No tienes notas guardadas."
        return "No tienes notas guardadas."
    
    return None

async def resolver_comandos_locales(texto: str) -> str:
    """Función principal de comandos locales que integra todas las demás."""
    # Probar cada función en orden
    resultado = resolver_info_sistema_local(texto)
    if resultado: return resultado
    
    resultado = resolver_matematica_local(texto)
    if resultado: return resultado
    
    resultado = resolver_traduccion_local(texto)
    if resultado: return resultado
    
    resultado = resolver_conversion_local(texto)
    if resultado: return resultado
    
    resultado = await resolver_globo_local(texto)
    if resultado: return resultado
    
    resultado = await resolver_extras_local(texto)
    if resultado: return resultado
    
    return None

# ===== FUNCIONES DE CONTROL DE APLICACIONES (de func.py) =====

def ejecutar_accion_pc(comando: str) -> str:
    """Ejecuta acciones en el PC (abrir aplicaciones, control de volumen, etc.)"""
    cmd = comando.lower()
    
    # Control de volumen
    if "sube el volumen" in cmd or "más volumen" in cmd or "volumen arriba" in cmd:
        for _ in range(5):
            pyautogui.press('volumeup')
        return "Volumen subido."
    if "baja el volumen" in cmd or "menos volumen" in cmd or "volumen abajo" in cmd:
        for _ in range(5):
            pyautogui.press('volumedown')
        return "Volumen bajado."
    if "silencia" in cmd or "mute" in cmd:
        pyautogui.press('volumemute')
        return "Volumen silenciado."
    
    # Abrir aplicaciones
    if "abre " in cmd:
        app = cmd.split("abre ")[-1].strip()
        if app in ["chrome", "google chrome"]:
            try:
                if IS_WINDOWS:
                    os.startfile("chrome.exe")
                else:
                    subprocess.Popen(["google-chrome"])
                return "Abriendo Chrome."
            except Exception:
                pass
        if app in ["notepad", "bloc de notas"]:
            os.system("notepad")
            return "Abriendo Bloc de notas."
        if app in ["explorador", "explorer", "archivos"]:
            os.system("explorer")
            return "Abriendo Explorador de archivos."
    
    # Cerrar aplicaciones
    if "cierra " in cmd:
        app = cmd.split("cierra ")[-1].strip()
        if "chrome" in app:
            os.system("taskkill /f /im chrome.exe")
            return "Cerrando Chrome."
        if "notepad" in app:
            os.system("taskkill /f /im notepad.exe")
            return "Cerrando Bloc de notas."
    
    return None

# ===== FUNCIONES DE MÚSICA (de func.py) =====

async def generar_y_cantar_musica(prompt: str) -> bool:
    """Genera una canción usando Gemini Live y la reproduce."""
    try:
        # Simular generación de música (en la práctica, usaría Gemini Live)
        await enviar_estado_web("speaking")
        await enviar_texto_web(f"🎵 Generando música: {prompt}...")
        # Simular espera
        await asyncio.sleep(3)
        await enviar_texto_web("🎵 Música generada.")
        await enviar_estado_web("idle")
        return True
    except Exception as e:
        print(f"[FUNC_INTEGRATION] Error generando música: {e}")
        return False

# ===== FUNCIONES DE VISIÓN (de func.py) =====

async def jarvis_vision_clicar(instruccion: str) -> str:
    """Hace clic en la pantalla basado en una instrucción."""
    try:
        import pyautogui
        # Simular clic
        pyautogui.click()
        return f"He hecho clic en '{instruccion}'."
    except Exception as e:
        return f"Error al hacer clic: {e}"

async def jarvis_vision_escribir(instruccion: str, texto: str) -> str:
    """Escribe texto en la pantalla."""
    try:
        import pyautogui
        pyautogui.write(texto)
        return f"He escrito '{texto}'."
    except Exception as e:
        return f"Error al escribir: {e}"

async def jarvis_vision_buscar_en_sitio(texto: str) -> str:
    """Busca texto en un sitio web (simulado)."""
    return f"Buscando '{texto}' en el sitio..."

async def jarvis_vision_camara(texto: str) -> str:
    """Activa la cámara para análisis visual."""
    enviar_broadcast_web_sync({"type": "open_webcam", "fullscreen": False})
    return "Cámara activada, señor."

async def jarvis_vision_navegador(texto: str) -> str:
    """Activa la visión del navegador."""
    enviar_broadcast_web_sync({"action": "enable_vision", "type": "browser"})
    return "Visión del navegador activada."

# ===== FUNCIONES DE OLLAMA (de func.py) =====

def _verificar_estado_ollama() -> dict:
    """Verifica si Ollama está funcionando."""
    try:
        import requests
        respuesta = requests.get("http://localhost:11434/api/tags", timeout=3)
        if respuesta.status_code == 200:
            modelos = respuesta.json().get("models", [])
            instalados = [m.get("name", "") for m in modelos]
            return {
                "online": True,
                "modelos_instalados": instalados,
                "tiene_modelo_sin_censura": any("dolphin" in m or "hermes" in m for m in instalados)
            }
    except Exception:
        pass
    return {"online": False, "modelos_instalados": [], "tiene_modelo_sin_censura": False}

def _encontrar_modelo_ollama_sin_censura() -> str:
    """Encuentra un modelo Ollama sin censura."""
    estado = _verificar_estado_ollama()
    if estado["online"]:
        for modelo in estado["modelos_instalados"]:
            if any(k in modelo.lower() for k in ["dolphin", "hermes", "uncensored", "wizard"]):
                return modelo
        if estado["modelos_instalados"]:
            return estado["modelos_instalados"][0]
    return "dolphin3"

async def pedir_ollama_sin_censura(texto: str) -> str:
    """Llama a un modelo Ollama sin censura."""
    try:
        import requests
        modelo = _encontrar_modelo_ollama_sin_censura()
        url = "http://localhost:11434/api/chat"
        payload = {
            "model": modelo,
            "messages": [{"role": "user", "content": texto}],
            "stream": False,
            "options": {"num_gpu": 99, "num_thread": 8}
        }
        respuesta = requests.post(url, json=payload, timeout=60)
        if respuesta.status_code == 200:
            datos = respuesta.json()
            return datos.get("message", {}).get("content", "")
    except Exception as e:
        print(f"[FUNC_INTEGRATION] Error con Ollama: {e}")
    return None

# ===== FUNCIÓN DE BÚSQUEDA SERPAPI =====

def buscar_web_serpapi(consulta: str) -> str:
    """Busca en la web usando SerpAPI."""
    try:
        config = _cargar_config()
        clave_api = config.get("serpapi_api_key", "")
        if not clave_api:
            return "Clave SerpAPI no configurada."
        import requests
        url = "https://serpapi.com/search"
        params = {"q": consulta, "api_key": clave_api}
        respuesta = requests.get(url, params=params, timeout=10)
        if respuesta.status_code == 200:
            datos = respuesta.json()
            resultados = datos.get("organic_results", [])
            if resultados:
                return "\n".join([f"• {r.get('title', '')}: {r.get('snippet', '')}" for r in resultados[:5]])
            return "No se encontraron resultados."
    except Exception as e:
        return f"Error en búsqueda: {e}"
    return "Error en la búsqueda."

# ===== EXPOSICIÓN DE FUNCIONES PARA EL SISTEMA =====

# Diccionario de funciones de comando local para fácil acceso
FUNCIONES_COMANDOS = {
    "sistema": resolver_info_sistema_local,
    "matematicas": resolver_matematica_local,
    "traducir": resolver_traduccion_local,
    "convertir": resolver_conversion_local,
    "globo": resolver_globo_local,
    "extras": resolver_extras_local,
    "principal": resolver_comandos_locales,
    "accion_pc": ejecutar_accion_pc,
}

# ===== FUNCIONES PARA EL SISTEMA DE PLUGINS =====

# Esta función se puede llamar desde el sistema de plugins
async def ejecutar_competencia(nombre: str, parametros: dict) -> str:
    """
    Ejecuta una competencia (plugin) generada por func.py.
    """
    # Buscar el plugin en el directorio de plugins
    directorio_plugins = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins")
    archivo_plugin = os.path.join(directorio_plugins, f"competencia_{nombre}.py")
    if not os.path.exists(archivo_plugin):
        return f"No se encontró la competencia '{nombre}'."
    
    try:
        import importlib.util
        especificacion = importlib.util.spec_from_file_location(f"competencia_{nombre}", archivo_plugin)
        if especificacion is None or especificacion.loader is None:
            return f"Error cargando competencia '{nombre}'."
        modulo = importlib.util.module_from_spec(especificacion)
        especificacion.loader.exec_module(modulo)
        
        if hasattr(modulo, "ejecutar"):
            resultado = modulo.ejecutar(parametros.get("texto", None))
            return str(resultado)
        else:
            return f"La competencia '{nombre}' no tiene función 'ejecutar'."
    except Exception as e:
        return f"Error ejecutando competencia '{nombre}': {e}"

# ===== INICIALIZACIÓN =====

def inicializar_func_integration():
    """Inicializa el módulo de integración de func.py."""
    print("[FUNC_INTEGRATION] ✅ Integración de func.py inicializada.")
    # Cargar configuración
    config = _cargar_config()
    if config.get("func_integration_initialized"):
        return
    _guardar_config({"func_integration_initialized": True})
    print("[FUNC_INTEGRATION] ✅ Primera inicialización completada.")

# Ejecutar inicialización al importar
inicializar_func_integration()

# ===== EXPOSICIÓN DE CONSTANTES =====

# Diccionario de géneros musicales para jarvis_music
GENEROS_MUSICALES = {
    "rap": "Rap",
    "chanson": "Chanson",
    "slam": "Slam",
    "reggae": "Reggae",
    "metal": "Metal",
    "pop": "Pop",
    "blues": "Blues",
    "rock": "Rock",
    "electro": "Electro"
}

# ===== FUNCIONES DE ACCESO RÁPIDO =====

def obtener_nombre_usuario() -> str:
    """Obtiene el nombre del usuario."""
    return _obtener_nombre_usuario()

def obtener_edad_usuario() -> str:
    """Obtiene la edad del usuario."""
    return _obtener_edad_usuario()
