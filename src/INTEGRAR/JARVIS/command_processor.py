# -*- coding: utf-8 -*-
"""
command_processor.py - Procesador Principal de Comandos AP0L0 OMEGA
Traducción completa y adaptación estructural del sistema JARVIS a AP0L0 OMEGA.
Versión: 9.5 OMEGA
"""

# =============================================================================
# IMPORTACIONES Y CONFIGURACIÓN INICIAL
# =============================================================================

# from ursina import *  # DESACTIVADO — interfaz web Three.js
import sys
import os
import warnings

# Suprimir warnings de Python (como la depreciación de pkg_resources en setuptools)
warnings.filterwarnings("ignore")
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import logging
logging.getLogger("websockets").setLevel(logging.WARNING)

import threading
import asyncio
import google.genai as genai
from google.genai import types
import speech_recognition as sr
import edge_tts
# --- Pygame (audio TTS): opcional ---
sys.stdout.flush()
sys.stderr.flush()
_main_os_redirected = False

try:
    _main_devnull_fd = os.open(os.devnull, os.O_WRONLY)
    _main_old_stdout_fd = os.dup(1)
    _main_old_stderr_fd = os.dup(2)
    os.dup2(_main_devnull_fd, 1)
    os.dup2(_main_devnull_fd, 2)
    _main_os_redirected = True
except Exception:
    pass

_main_old_sys_stdout = sys.stdout
_main_old_sys_stderr = sys.stderr
sys.stdout = open(os.devnull, 'w', encoding='utf-8')
sys.stderr = open(os.devnull, 'w', encoding='utf-8')

try:
    import pygame
except Exception:
    pygame = None
finally:
    try:
        sys.stdout.close()
    except Exception:
        pass
    try:
        sys.stderr.close()
    except Exception:
        pass
    sys.stdout = _main_old_sys_stdout
    sys.stderr = _main_old_sys_stderr

    if _main_os_redirected:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(_main_old_stdout_fd, 1)
            os.dup2(_main_old_stderr_fd, 2)
            os.close(_main_devnull_fd)
            os.close(_main_old_stdout_fd)
            os.close(_main_old_stderr_fd)
        except Exception:
            pass

if pygame is None:
    print("[ADVERTENCIA] pygame no instalado — el audio TTS estará desactivado.")
    print("  -> Para instalarlo: pip install pygame --only-binary :all:")

from dotenv import load_dotenv
import agent_model_manager

# =============================================================================
# CONFIGURACIÓN DEL SISTEMA AP0L0 OMEGA
# =============================================================================

_RUTA_CONFIG_OMEGA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "brand.json")
_RUTA_CONFIG_JARVIS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")

def _cargar_config() -> dict:
    """Carga jarvis_config.json o devuelve un dict vacío si falta/corrupto."""
    try:
        if os.path.exists(_RUTA_CONFIG_JARVIS):
            import json
            with open(_RUTA_CONFIG_JARVIS, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _cargar_nombre_usuario():
    import json as _j
    try:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        with open(_p, "r", encoding="utf-8") as _f:
            return _j.load(_f).get("user_name", "Christopher")
    except Exception:
        return "Christopher"

def _cargar_edad_usuario():
    import json as _j
    try:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        with open(_p, "r", encoding="utf-8") as _f:
            return _j.load(_f).get("user_age", "")
    except Exception:
        return ""

NOMBRE_USUARIO = _cargar_nombre_usuario()
EDAD_USUARIO = _cargar_edad_usuario()

import random
import math
import builtins
import winreg

def _obtener_ruta_bat():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "DEMARRER_JARVIS.bat")

def activar_inicio_windows():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        bat_path = _obtener_ruta_bat()
        winreg.SetValueEx(key, "JARVIS", 0, winreg.REG_SZ, f'"{bat_path}"')
        winreg.CloseKey(key)
        print("[OMEGA] Inicio automático con Windows activado.")
    except Exception as e:
        print(f"[OMEGA] Error activación inicio Windows: {e}")

def desactivar_inicio_windows():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, "JARVIS")
        winreg.CloseKey(key)
        print("[OMEGA] Inicio automático con Windows desactivado.")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[OMEGA] Error desactivación inicio Windows: {e}")

# =============================================================================
# GLOBALES TTS/AUDIO
# =============================================================================

BUCLE_WEB = None
esta_hablando = False
volumen_voz = 0.0
DETENER_HABLA = False
MICRO_MUTED = False
MICRO_NECESITA_RECARGAR = False
INDICE_MICRO_FORZADO = None  # Índice impuesto explícitamente por el usuario
NEMOTRON_ASR_ACTIVADO = False
_instancia_nemotron = None  # Instancia NemotronASR (cargada bajo demanda)
_saltar_audio_pc = False
_MODELO_OLLAMA_CARGADO = False
historial = []

# =============================================================================
# GESTOR DE CUOTA DIARIA GEMINI TTS
# =============================================================================
# Límite oficial: 100 req/día en gemini-2.5-flash-preview-tts
# Paramos en 90 para mantener margen de seguridad.
_CUOTA_GEMINI_TTS_MAX = 90
_ARCHIVO_CUOTA_GEMINI_TTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_tts_quota.json")

def _limpiar_emojis_para_tts(texto: str) -> str:
    """Elimina emojis, símbolos gráficos y términos indeseables para la síntesis de voz."""
    if not texto:
        return ""
    import re
    texto = re.sub(r'(?i)\bskill\s+issu(e)?\b', '', texto)

    patron_emoji = re.compile(
        "["
        "\U00010000-\U0010FFFF"  # Emojis y símbolos extendidos
        "\u2600-\u27BF"          # Símbolos varios y dingbats
        "\uFE00-\uFE0F"          # Selectores de variación
        "\u200D"                 # Zero Width Joiner
        "\u2300-\u23FF"          # Símbolos técnicos
        "\u2B50"                 # Estrella
        "\u20E3"                 # Keycap
        "]+",
        flags=re.UNICODE
    )
    limpiado = patron_emoji.sub(" ", texto)
    return re.sub(r'\s+', ' ', limpiado).strip()

def _cargar_cuota_tts() -> dict:
    """Carga el contador de cuota desde el archivo JSON."""
    try:
        if os.path.exists(_ARCHIVO_CUOTA_GEMINI_TTS):
            with open(_ARCHIVO_CUOTA_GEMINI_TTS, "r", encoding="utf-8") as _f:
                return json.load(_f)
    except Exception:
        pass
    return {"fecha": "", "contador": 0}

def _guardar_cuota_tts(data: dict) -> None:
    try:
        with open(_ARCHIVO_CUOTA_GEMINI_TTS, "w", encoding="utf-8") as _f:
            json.dump(data, _f)
    except Exception:
        pass

def _verificar_cuota_tts() -> bool:
    """
    Retorna True si se puede llamar a Gemini TTS hoy.
    Retorna False si la cuota diaria está alcanzada → usar Edge TTS.
    """
    import datetime
    data = _cargar_cuota_tts()
    hoy = datetime.date.today().isoformat()
    if data.get("fecha") != hoy:
        data = {"fecha": hoy, "contador": 0}
        _guardar_cuota_tts(data)
    contador = data.get("contador", 0)
    if contador >= _CUOTA_GEMINI_TTS_MAX:
        print(f"[GEMINI TTS] Cuota diaria alcanzada ({contador}/{_CUOTA_GEMINI_TTS_MAX}) — Edge TTS activado hasta medianoche.")
        return False
    return True

def _incrementar_cuota_tts() -> None:
    """Incrementa el contador de solicitudes del día."""
    import datetime
    data = _cargar_cuota_tts()
    hoy = datetime.date.today().isoformat()
    if data.get("fecha") != hoy:
        data = {"fecha": hoy, "contador": 0}
    data["contador"] = data.get("contador", 0) + 1
    _guardar_cuota_tts(data)
    restante = max(0, _CUOTA_GEMINI_TTS_MAX - data["contador"])
    if restante <= 10:
        print(f"[GEMINI TTS] ⚠ Cuota: {data['contador']}/{_CUOTA_GEMINI_TTS_MAX} — {restante} solicitudes restantes hoy.")

async def _gemini_tts_a_archivo(texto: str, nombre_voz: str, salida_wav: str) -> bool:
    """
    Genera un archivo de audio WAV mediante Gemini AI TTS.
    Retorna True si éxito, False en caso contrario (fallback a Edge TTS).

    Gestión automática de la cuota diaria (100 req/día en el modelo preview).
    Cambia correctamente a Edge TTS antes de alcanzar el límite.
    """
    if not _verificar_cuota_tts():
        return False

    try:
        import wave as _wave
        _clave_api = os.getenv("GEMINI_API_KEY", "")
        if not _clave_api:
            print("[GEMINI TTS] Clave API faltante — fallback Edge TTS")
            return False

        import google.genai as _genai
        from google.genai import types as _gtypes

        _gcliente = _genai.Client(api_key=_clave_api)

        config_voz = _gtypes.SpeechConfig(
            voice_config=_gtypes.VoiceConfig(
                prebuilt_voice_config=_gtypes.PrebuiltVoiceConfig(voice_name=nombre_voz)
            )
        )

        respuesta = _gcliente.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=texto,
            config=_gtypes.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=config_voz,
            ),
        )

        audio_data = respuesta.candidates[0].content.parts[0].inline_data.data

        with _wave.open(salida_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(audio_data)

        _incrementar_cuota_tts()
        print(f"[GEMINI TTS] [OK] Audio generado con la voz '{nombre_voz}' — {len(audio_data)} bytes")
        return True

    except Exception as e:
        err_str = str(e).lower()
        if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
            import datetime
            data = _cargar_cuota_tts()
            data["fecha"] = datetime.date.today().isoformat()
            data["contador"] = _CUOTA_GEMINI_TTS_MAX
            _guardar_cuota_tts(data)
            print("[GEMINI TTS] Cuota Google agotada por hoy — Edge TTS activado hasta medianoche.")
        else:
            print(f"[GEMINI TTS] [ERROR] {e} — fallback Edge TTS")
        return False

# =============================================================================
# ANIMACIÓN VISUAL Y SISTEMA DE COMPETENCIAS AUTÓNOMAS
# =============================================================================

def _efecto_visual_iron_man(evento_detener):
    """Muestra un efecto de desplazamiento de código y logs estilo Iron Man HUD en consola y pantalla web."""
    import random
    import time

    enviar_broadcast_web_sync({"action": "set_state", "state": "thinking"})

    logs_ficticios = [
        ">>> SISTEMA: ASIGNANDO SEGMENTO DE COMPILACIÓN EN NÚCLEO_0...",
        ">>> CONECTANDO A CORRELADOR NEURONAL GEMINI (MODELO: gemini-3.5-flash)...",
        ">>> ACTIVANDO MODO DE PENSAMIENTO (PRESUPUESTO: 2048)...",
        ">>> SINCRONIZANDO RESTRICCIONES DE MATRIZ DE PENSAMIENTO...",
        ">>> ASIGNACIÓN HEAP: 0x7FFA4C9E0000 [64MB]",
        "[SISTEMA] CARGANDO BIBLIOTECAS: importlib.util, os, time, sys",
        "[COMPILAR] Generando firma de función: def ejecutar(texto_usuario=None)",
        "[ANALIZADOR] Aplicando reglas Python puras: sin etiquetas markdown, código fuente puro...",
        "[COMPILADOR] Construyendo nodos AST...",
        "[SISTEMA] COMPILANDO RECURSO: plugins/competencia_*.py",
        ">>> COMPACTANDO BUFFER DE CÓDIGO FUENTE...",
        ">>> INYECTANDO CADENAS DE RETORNO DE SALIDA DE VOZ...",
        ">>> ESTABILIDAD DE ENERGÍA DEL ESCUDO: 98.4%",
        ">>> ESCANEANDO SECTORES CORRUPTOS... OK",
        "[LOG] Hilo cargador dinámico instanciado.",
        "[INFO] Integridad del código: 100% conforme.",
        "[DEBUG] Temperatura: 0.1 | Top-P: 0.95 | Top-K: 40",
    ]
    caracteres = "0123456789ABCDEFghijklmnopqrstuvwxyz[]{}()$#@!*&%^-_=+"

    print("\n\033[93m" + "=" * 60)
    print("   AP0L0 OMEGA — SISTEMA DE PLUGINS: COMPILANDO NUEVA COMPETENCIA")
    print("=" * 60 + "\033[0m\n")

    iteracion = 0
    while not evento_detener.is_set():
        val = random.random()
        log_texto = ""
        if val < 0.3:
            log_texto = random.choice(logs_ficticios)
            print(f"\033[94m[HUD_LOG] {log_texto}\033[0m")
        elif val < 0.6:
            addr = f"0x{random.randint(0x10000000, 0xFFFFFFFF):X}"
            datos = "".join(random.choice(caracteres) for _ in range(40))
            log_texto = f"{addr} : {datos}"
            print(f"\033[92m[MATRIZ] {log_texto}\033[0m")
        else:
            progreso = random.randint(0, 100)
            barra = "=" * (progreso // 5) + " " * (20 - (progreso // 5))
            log_texto = f"COMPILANDO: [{barra}] {progreso}%"
            print(f"\033[96m[SISTEMA] {log_texto}\033[0m")

        if iteracion % 12 == 0:
            enviar_broadcast_web_sync({"action": "jarvis_text", "text": f"[HUD] {log_texto}"})

        iteracion += 1
        time.sleep(0.04)

    print("\n\033[92m" + "=" * 60)
    print("   AP0L0 OMEGA — COMPETENCIA INTEGRADA CON ÉXITO")
    print("=" * 60 + "\033[0m\n")

    enviar_broadcast_web_sync({"action": "set_state", "state": "idle"})
    enviar_broadcast_web_sync({"action": "jarvis_text", "text": "COMPILACIÓN TERMINADA — COMPETENCIA CARGADA"})

def omega_crear_competencia(nombre_competencia: str, descripcion_demanda: str) -> str:
    """
    Llama a Gemini-3.5-flash con thinking activado para generar una competencia Python autónoma.
    Guarda el código generado en la carpeta plugins/ bajo competencia_<nombre>.py.
    """
    import re
    import threading
    import os
    import builtins
    from google.genai import types as _gtypes

    if not hasattr(builtins, "cliente") or not builtins.cliente:
        return "Error: el cliente Gemini no está inicializado o la clave API es inválida."

    nombre_formateado = re.sub(r'[^a-zA-Z0-9_]', '', nombre_competencia.lower().replace(" ", "_"))
    carpeta_plugins = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")
    if not os.path.exists(carpeta_plugins):
        os.makedirs(carpeta_plugins, exist_ok=True)

    nombre_archivo = os.path.join(carpeta_plugins, f"competencia_{nombre_formateado}.py")

    evento_detener = threading.Event()
    hilo_anim = threading.Thread(target=_efecto_visual_iron_man, args=(evento_detener,), daemon=True)
    hilo_anim.start()

    try:
        instruccion_sistema = (
            "Eres el agente de generación de competencias autónomas de AP0L0 OMEGA.\n"
            "Debes escribir código Python estricto, limpio y válido.\n\n"
            "REGLAS CRÍTICAS:\n"
            "1. Devuelve ÚNICAMENTE el código Python puro. No pongas NINGUNA etiqueta de código markdown como ```python o ```. Sin texto explicativo fuera del código.\n"
            "2. El script debe ser completamente autónomo.\n"
            "3. Debes implementar obligatoriamente una función principal llamada `ejecutar(texto_usuario=None)` que toma un argumento opcional (string) y que RETORNA obligatoriamente un string (el texto formateado que OMEGA leerá en voz alta).\n"
            "4. Evita cualquier llamada externa que requiera credenciales no proporcionadas (claves de APIs de terceros) a menos que sea posible mediante APIs públicas o mocks. Puedes usar bibliotecas estándar o requests."
        )

        prompt = (
            f"Genera el código completo para la competencia: '{nombre_competencia}'.\n"
            f"Objetivo de la competencia: {descripcion_demanda}\n\n"
            "Escribe el código Python puro respetando todas las reglas de estructura."
        )

        respuesta = builtins.cliente.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=_gtypes.GenerateContentConfig(
                system_instruction=instruccion_sistema,
                temperature=0.1,
                thinking_config=_gtypes.ThinkingConfig(thinking_budget=2048)
            )
        )

        codigo_generado = respuesta.text.strip()

        if codigo_generado.startswith("```"):
            lineas = codigo_generado.split("\n")
            if lineas[0].startswith("```"):
                lineas = lineas[1:]
            if lineas and lineas[-1].startswith("```"):
                lineas = lineas[:-1]
            codigo_generado = "\n".join(lineas).strip()

        with open(nombre_archivo, "w", encoding="utf-8") as f:
            f.write(codigo_generado)

        evento_detener.set()
        hilo_anim.join()

        print(f"[OMEGA PLUGINS] Nueva competencia escrita en {nombre_archivo}")
        return f"La competencia '{nombre_competencia}' ha sido generada e instalada con éxito. Está lista para ser ejecutada."

    except Exception as e:
        evento_detener.set()
        hilo_anim.join()
        print(f"[OMEGA PLUGINS] Error al crear competencia: {e}")
        return f"Lo siento {NOMBRE_USUARIO}, la generación de la competencia ha fallado. Detalle del error: {e}"

def omega_eliminar_competencia(nombre_competencia: str) -> str:
    """Elimina limpiamente el archivo de competencia objetivo."""
    import re
    import os
    nombre_formateado = re.sub(r'[^a-zA-Z0-9_]', '', nombre_competencia.lower().replace(" ", "_"))
    nombre_archivo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins", f"competencia_{nombre_formateado}.py")

    if os.path.exists(nombre_archivo):
        try:
            os.remove(nombre_archivo)
            print(f"[OMEGA PLUGINS] Competencia eliminada: {nombre_archivo}")
            return f"La competencia '{nombre_competencia}' ha sido desinstalada y su archivo ha sido eliminado."
        except Exception as e:
            return f"Error al eliminar el archivo: {e}"
    else:
        return f"La competencia '{nombre_competencia}' no está instalada."

def ejecutar_competencia_vocal(nombre_competencia: str, texto_recibido: str = None) -> str:
    """Importa y ejecuta dinámicamente la competencia vocal."""
    import re
    import os
    import sys
    import importlib.util

    nombre_formateado = re.sub(r'[^a-zA-Z0-9_]', '', nombre_competencia.lower().replace(" ", "_"))
    nombre_archivo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins", f"competencia_{nombre_formateado}.py")

    if not os.path.exists(nombre_archivo):
        return f"Lo siento {NOMBRE_USUARIO}, la competencia '{nombre_competencia}' no está disponible."

    try:
        nombre_modulo = f"plugins.competencia_{nombre_formateado}"
        spec = importlib.util.spec_from_file_location(nombre_modulo, nombre_archivo)
        if spec is None or spec.loader is None:
            return "No se pudo cargar la especificación del módulo."

        modulo = importlib.util.module_from_spec(spec)
        sys.modules[nombre_modulo] = modulo
        spec.loader.exec_module(modulo)

        if hasattr(modulo, "ejecutar"):
            res = modulo.ejecutar(texto_recibido)
            return str(res)
        else:
            return "Error: esta competencia no posee un punto de entrada 'ejecutar'."

    except Exception as e:
        print(f"[OMEGA PLUGINS] Error al ejecutar {nombre_competencia}: {e}")
        return f"Error de ejecución en la competencia '{nombre_competencia}': {e}"

# =============================================================================
# GEMINI LIVE TTS (Live API — sin cuota diaria)
# =============================================================================
# Utiliza gemini-2.5-flash-native-audio-latest vía Live API (streaming).
# Sin límite de 100 req/día — ideal para uso intensivo.
# Voces disponibles: igual que TTS estándar (Fenrir, Puck, Aoede, etc.)

_MAPEO_VOCES_GEMINI_LIVE = {
    "gemini_live_fenrir": "Fenrir",   # Grave, pausado, muy humano
    "gemini_live_puck":   "Puck",     # Dinámico, enérgico
    "gemini_live_aoede":  "Aoede",    # Natural, calmante
    "gemini_live_charon": "Charon",   # Claro, informativo
    "gemini_live_orus":   "Orus",     # Robusto, pausado
    "gemini_live_zephyr": "Zephyr",   # Luminoso, expresivo
}

async def _gemini_live_tts_a_archivo(texto: str, nombre_voz: str, salida_wav: str) -> bool:
    """
    Genera un archivo de audio WAV mediante la API Gemini Live.
    Sin cuota diaria (facturación por uso).
    Retorna True si éxito, False en caso contrario (fallback Edge TTS).
    """
    try:
        import wave as _wave
        import google.genai as _genai
        from google.genai import types as _gtypes

        _clave_api = os.getenv("GEMINI_API_KEY", "")
        if not _clave_api:
            print("[GEMINI LIVE TTS] Clave API faltante — fallback Edge TTS")
            return False

        _gcliente = _genai.Client(api_key=_clave_api)

        config_voz = _gtypes.SpeechConfig(
            voice_config=_gtypes.VoiceConfig(
                prebuilt_voice_config=_gtypes.PrebuiltVoiceConfig(voice_name=nombre_voz)
            )
        )
        config_live = _gtypes.LiveConnectConfig(
            response_modalities=[_gtypes.Modality.AUDIO],
            speech_config=config_voz,
        )

        audio_data = bytearray()
        async with _gcliente.aio.live.connect(
            model="gemini-2.5-flash-native-audio-latest",
            config=config_live
        ) as sesion:
            await sesion.send(input=texto, end_of_turn=True)
            async for respuesta in sesion.receive():
                if respuesta.server_content and respuesta.server_content.model_turn:
                    for parte in respuesta.server_content.model_turn.parts:
                        if parte.inline_data:
                            audio_data.extend(parte.inline_data.data)
                if respuesta.server_content and respuesta.server_content.turn_complete:
                    break

        if not audio_data:
            print("[GEMINI LIVE TTS] No se recibió audio — fallback Edge TTS")
            return False

        with _wave.open(salida_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(bytes(audio_data))

        print(f"[GEMINI LIVE TTS] [OK] Voz '{nombre_voz}' — {len(audio_data)} bytes")
        return True

    except Exception as e:
        print(f"[GEMINI LIVE TTS] [ERROR] {e} — fallback Edge TTS")
        return False

# =============================================================================
# GENERACIÓN Y CANTO DE MÚSICA
# =============================================================================

async def generar_y_cantar_musica(prompt_usuario: str) -> bool:
    """
    Se conecta a la API Live Connect de Gemini para generar una canción cantada en modo audio directo,
    guarda el audio en un archivo WAV y lo reproduce mediante el mezclador de audio.
    """
    global _saltar_audio_pc, volumen_voz, DETENER_HABLA
    try:
        import wave as _wave
        import google.genai as _genai
        from google.genai import types as _gtypes
        import base64
        import json
        import time
        import math
        import random as _rnd

        _clave_api = os.getenv("GEMINI_API_KEY", "")
        if not _clave_api:
            print("[MÚSICA GEN] Clave API faltante.")
            return False

        _gcliente = _genai.Client(api_key=_clave_api)

        prompt_musical = (
            f"Canta una canción corta (máximo 20 segundos) respondiendo a la petición: {prompt_usuario}. "
            "Canta directamente con una verdadera melodía cantada, ritmo y energía (sé expresivo). "
            "No hables, no hagas introducción ni conclusión hablada. Empieza directamente a cantar."
        )

        audio_data = bytearray()
        config = _gtypes.LiveConnectConfig(
            response_modalities=[_gtypes.Modality.AUDIO]
        )

        print("[MÚSICA GEN] Conectando a la API Gemini Live...")
        async with _gcliente.aio.live.connect(model="gemini-2.5-flash-native-audio-latest", config=config) as sesion:
            print("[MÚSICA GEN] Sesión abierta. Enviando petición creativa...")
            await sesion.send(input=prompt_musical, end_of_turn=True)

            print("[MÚSICA GEN] Recibiendo flujo de audio...")
            async for respuesta in sesion.receive():
                if respuesta.server_content:
                    turno_modelo = respuesta.server_content.model_turn
                    if turno_modelo:
                        for parte in turno_modelo.parts:
                            if parte.inline_data:
                                audio_data.extend(parte.inline_data.data)

                if respuesta.server_content and respuesta.server_content.turn_complete:
                    break

        if len(audio_data) == 0:
            print("[MÚSICA GEN] No se recibió audio.")
            return False

        tmp_wav = f"omega_cancion_{int(time.time()*1000)}.wav"
        with _wave.open(tmp_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(audio_data)

        print(f"[MÚSICA GEN] [OK] Canción generada con éxito: {tmp_wav} ({len(audio_data)} bytes)")

        if _saltar_audio_pc:
            if CLIENTES_CONECTADOS:
                try:
                    with open(tmp_wav, "rb") as f:
                        audio_b64 = base64.b64encode(f.read()).decode('utf-8')
                    mensaje = json.dumps({"action": "jarvis_audio", "text": "🎵 [Música generada por OMEGA] 🎵", "audio_b64": audio_b64})
                    await asyncio.gather(*[ws.send(mensaje) for ws in CLIENTES_CONECTADOS])
                except Exception as e:
                    print(f"[MÓVIL] Error enviando música: {e}")
            duracion = (len(audio_data) / 2) / 24000
            await asyncio.sleep(duracion + 1.0)
        elif pygame:
            iniciar_mezclador()
            pygame.mixer.music.load(tmp_wav)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                if DETENER_HABLA:
                    pygame.mixer.music.stop()
                    break
                t_audio = time.time() * 25
                base_vol = 0.5 + 0.3 * math.sin(t_audio) + 0.15 * math.sin(t_audio * 0.7)
                volumen_voz = max(0.2, min(1.0, base_vol + _rnd.uniform(-0.15, 0.15)))
                await enviar_volumen_web(volumen_voz)
                await asyncio.sleep(0.05)
            await enviar_volumen_web(0.0)

        try:
            os.remove(tmp_wav)
        except:
            pass

        return True

    except Exception as e:
        print(f"[MÚSICA GEN] [ERROR] Error: {e}")
        return False

# =============================================================================
# FUNCIÓN PRINCIPAL DE HABLA (TTS)
# =============================================================================

async def hablar(texto):
    global esta_hablando, volumen_voz, DETENER_HABLA, _saltar_audio_pc, historial

    texto = texto.replace("J.A.R.V.I.S.", "Omega").replace("J.A.R.V.I.S", "Omega").replace("j.a.r.v.i.s.", "Omega").replace("j.a.r.v.i.s", "Omega")

    texto = texto.replace("Christopher", NOMBRE_USUARIO).replace("christopher", NOMBRE_USUARIO.lower())

    if historial and len(historial) > 0:
        ultimo_texto_modelo = historial[-1].parts[0].text
        if ultimo_texto_modelo != texto:
            historial.append(types.Content(role="model", parts=[types.Part(text=f"[Información devuelta por la acción y enunciada en voz alta]: {texto}")]))

    import re
    frases_raw = [p.strip() for p in re.split(r'(?<=[.!?])\s+', texto) if p.strip()]
    frases = []
    frase_actual = ""
    for p in frases_raw:
        if frase_actual:
            if len(frase_actual) + len(p) < 450:
                frase_actual += " " + p
            else:
                frases.append(frase_actual)
                frase_actual = p
        else:
            frase_actual = p
    if frase_actual:
        frases.append(frase_actual)

    if not frases:
        return

    esta_hablando = True
    await enviar_estado_web("speaking")
    volumen_voz = 0.0

    cfg = _cargar_config()
    voz_elegida = cfg.get("voice", "male")

    MAPEO_VOCES_GEMINI = {
        "gemini_fenrir":  "Fenrir",
        "gemini_aoede":   "Aoede",
        "gemini_charon":  "Charon",
        "gemini_kore":    "Kore",
        "gemini_leda":    "Leda",
        "gemini_orus":    "Orus",
        "gemini_puck":    "Puck",
        "gemini_zephyr":  "Zephyr",
    }

    MAPEO_VOCES_EDGE = {
        "female":    "fr-FR-DeniseNeural",
        "female2":   "fr-FR-EloiseNeural",
        "female3":   "fr-FR-DeniseNeural",
        "female4":   "fr-CA-SylvieNeural",
        "female5":   "fr-CH-ArianeNeural",
        "male":      "fr-FR-HenriNeural",
        "male2":     "fr-FR-HenriNeural",
        "male3":     "fr-CA-AntoineNeural",
        "male4":     "fr-CH-FabriceNeural",
        "male5":     "fr-BE-GerardNeural",
        "en_male":   "en-US-BrianMultilingualNeural",
        "en_female": "en-US-EmmaMultilingualNeural",
        "es_male":   "es-ES-AlvaroNeural",
        "es_female": "es-ES-ElviraNeural",
        "it_male":   "it-IT-GiuseppeMultilingualNeural",
        "it_female": "it-IT-ElsaNeural",
        "de_male":   "de-DE-FlorianMultilingualNeural",
        "de_female": "de-DE-SeraphinaMultilingualNeural",
        "pt_male":   "pt-BR-AntonioNeural",
        "pt_female": "pt-BR-ThalitaMultilingualNeural",
    }

    archivos_creados = []

    async def pre_generar(indice):
        if indice >= len(frases):
            return None
        frase = frases[indice]
        frase_tts = frase.replace("**", "").replace("*", "").replace("#", "").replace("`", "").strip()
        frase_tts = _limpiar_emojis_para_tts(frase_tts)
        if not frase_tts:
            return None

        import time
        archivo_tmp = f"omega_tts_{int(time.time()*1000)}_{indice}.mp3"
        archivos_creados.append(archivo_tmp)

        try:
            if voz_elegida.startswith("kokoro_"):
                archivo_wav = archivo_tmp.replace(".mp3", ".wav")
                archivos_creados.append(archivo_wav)
                ok = await _kokoro_tts_a_archivo(frase_tts, voz_elegida, archivo_wav)
                if ok:
                    return archivo_wav
                voz_id = MAPEO_VOCES_EDGE.get("male", "fr-FR-HenriNeural")
                comunicador = edge_tts.Communicate(frase_tts, voice=voz_id)
                await comunicador.save(archivo_tmp)
                return archivo_tmp

            if voz_elegida in _MAPEO_VOCES_GEMINI_LIVE:
                nombre_voz_live = _MAPEO_VOCES_GEMINI_LIVE[voz_elegida]
                archivo_wav = archivo_tmp.replace(".mp3", ".wav")
                archivos_creados.append(archivo_wav)
                texto_live_limpio = frase_tts
                for char in ['"', "'", "«", "»", "\u201c", "\u201d", "-", "—", "–"]:
                    texto_live_limpio = texto_live_limpio.replace(char, " ")
                texto_live_limpio = texto_live_limpio.strip()
                ok = await _gemini_live_tts_a_archivo(texto_live_limpio, nombre_voz_live, archivo_wav)
                if ok:
                    return archivo_wav
                masculinas_live = {"gemini_live_fenrir", "gemini_live_puck", "gemini_live_charon", "gemini_live_orus"}
                voz_id = MAPEO_VOCES_EDGE.get("male" if voz_elegida in masculinas_live else "female", "fr-FR-HenriNeural")
                comunicador = edge_tts.Communicate(frase_tts, voice=voz_id)
                await comunicador.save(archivo_tmp)
                return archivo_tmp

            if voz_elegida in MAPEO_VOCES_GEMINI:
                nombre_voz_gemini = MAPEO_VOCES_GEMINI[voz_elegida]
                archivo_wav = archivo_tmp.replace(".mp3", ".wav")
                archivos_creados.append(archivo_wav)

                texto_gemini_limpio = frase_tts
                for char in ['"', "'", "«", "»", "“", "”", "-", "—", "–"]:
                    texto_gemini_limpio = texto_gemini_limpio.replace(char, " ")
                texto_gemini_limpio = texto_gemini_limpio.strip()

                ok = await _gemini_tts_a_archivo(texto_gemini_limpio, nombre_voz_gemini, archivo_wav)
                if ok:
                    return archivo_wav

            if voz_elegida.startswith("gemini_"):
                masculinas = {"gemini_fenrir", "gemini_charon", "gemini_orus", "gemini_puck",
                              "gemini_live_fenrir", "gemini_live_puck", "gemini_live_charon", "gemini_live_orus"}
                voz_id = MAPEO_VOCES_EDGE.get("male" if voz_elegida in masculinas else "female", "fr-FR-HenriNeural")
            else:
                voz_id = MAPEO_VOCES_EDGE.get(voz_elegida, "fr-FR-HenriNeural")

            comunicador = edge_tts.Communicate(frase_tts, voice=voz_id)
            await comunicador.save(archivo_tmp)
            return archivo_tmp
        except Exception as e:
            print(f"[TTS PREGEN] Error frase {indice}: {e}")
        return None

    try:
        import time
        archivo_actual = await pre_generar(0)
        tarea_siguiente = asyncio.create_task(pre_generar(1))

        _texto_completo_impreso = False

        for indice, frase in enumerate(frases):
            if DETENER_HABLA:
                break

            if not archivo_actual:
                if not _texto_completo_impreso:
                    print(f"[OMEGA] {texto}")
                    _texto_completo_impreso = True

                await enviar_texto_web(frase)
                await asyncio.sleep(max(1.5, len(frase.split()) * 0.35))
                archivo_actual = await tarea_siguiente
                tarea_siguiente = asyncio.create_task(pre_generar(indice + 2))
                continue

            await enviar_texto_web(frase)

            if not _texto_completo_impreso:
                print(f"[OMEGA] {texto}")
                _texto_completo_impreso = True

            if _saltar_audio_pc:
                print(f"[MÓVIL] Enviando audio al móvil: {frase}")
                if CLIENTES_CONECTADOS:
                    try:
                        import base64
                        import json
                        with open(archivo_actual, "rb") as f:
                            audio_b64 = base64.b64encode(f.read()).decode('utf-8')
                        mensaje = json.dumps({"action": "jarvis_audio", "text": frase, "audio_b64": audio_b64})
                        await asyncio.gather(*[ws.send(mensaje) for ws in CLIENTES_CONECTADOS])
                    except Exception as e:
                        print(f"[MÓVIL] Error enviando audio: {e}")
                duracion = max(1.5, len(frase.split()) * 0.38)
                await asyncio.sleep(duracion)
            elif pygame:
                iniciar_mezclador()
                pygame.mixer.music.load(archivo_actual)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    if DETENER_HABLA:
                        pygame.mixer.music.stop()
                        break

                    t_audio = time.time() * 20
                    base_vol = 0.4 + 0.3 * math.sin(t_audio) + 0.2 * math.sin(t_audio * 0.5)
                    volumen_voz = max(0.1, min(1.0, base_vol + random.uniform(-0.1, 0.1)))
                    await enviar_volumen_web(volumen_voz)
                    await asyncio.sleep(0.05)

            try:
                if pygame and pygame.mixer.get_init():
                    pygame.mixer.music.unload()
            except:
                pass
            try:
                if os.path.exists(archivo_actual):
                    os.remove(archivo_actual)
            except:
                pass

            archivo_actual = await tarea_siguiente
            tarea_siguiente = asyncio.create_task(pre_generar(indice + 2))

    except Exception as e:
        print(f"Error bucle hablar: {e}")
    finally:
        volumen_voz = 0.0
        esta_hablando = False
        DETENER_HABLA = False
        try:
            if pygame and pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
        except:
            pass
        for f in archivos_creados:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except:
                pass
        await enviar_estado_web("idle")

builtins.hablar = hablar

# =============================================================================
# IMPORTACIÓN DE MÓDULOS DEL SISTEMA AP0L0 OMEGA
# =============================================================================

from src.actions.file_manager import *
builtins.resolver_ruta = resolver_ruta

from src.core.memory_manager import *
from src.core.memory_manager import _cargar_historial_reciente, _guardar_intercambio_conv

from src.actions.spotify_controller import *
builtins.spotify_lanzar_playlist = spotify_lanzar_playlist

from src.actions.deezer_controller import *
from src.actions.app_launcher import *
from src.actions.app_launcher import _cerrar_app, _trabajo_lanzar, _APPS_CATALOGO, _cargar_apps_personalizadas
builtins._APPS_CATALOGO = _APPS_CATALOGO
try:
    _cargar_apps_personalizadas()
    print("[INICIO] Aplicaciones personalizadas cargadas con éxito.")
except Exception as e:
    print(f"[INICIO] Error cargando aplicaciones personalizadas: {e}")

from src.actions.google_services import *
from src.actions.vision_module import *
from src.actions.sports_web import *
from src.actions.antivirus_scanner import ejecutar_analisis_antivirus
from src.actions.restaurant_helper import buscar_restaurantes_cercanos, obtener_ciudad_por_ip
import src.actions.obsidian_helper
from src.actions.uninstaller_helper import listar_programas_instalados, escanear_restos_archivos, escanear_restos_registro, ejecutar_proceso_desinstalacion, limpiar_elemento_restante
from src.actions.iptv_player import manejar_mensaje_iptv_ws

# --- Módulo de música multi-géneros OMEGA ---
try:
    from src.actions.jarvis_music import JarvisMusic as _JarvisMusic, resolver_genero as _resolver_genero, GENEROS as _GENEROS_MUSICALES
    _instancia_musica_omega = None
    _MODULO_MUSICA_OK = True
except ImportError:
    _MODULO_MUSICA_OK = False
    print("[ADVERTENCIA] jarvis_music.py no encontrado — comandos musicales multi-género desactivados.")

from src.actions.ha_config import manejar_mensaje_ha_ws
from src.actions.youtube_api import (
    yt_info_video, yt_buscar_multi, yt_tendencias,
    yt_info_canal, yt_resumir_video, yt_ultimos_videos,
)

UBICACION_USUARIO_GPS = None
ULTIMOS_RESTAURANTES_MOSTRADOS = []

TAREAS_FONDO = set()

def lanzar_tarea_fondo(coro):
    if BUCLE_WEB and BUCLE_WEB.is_running():
        try:
            return asyncio.run_coroutine_threadsafe(coro, BUCLE_WEB)
        except Exception as e:
            print(f"[OMEGA] Error run_coroutine_threadsafe: {e}")
    try:
        bucle = asyncio.get_running_loop()
        tarea = bucle.create_task(coro)
        TAREAS_FONDO.add(tarea)
        tarea.add_done_callback(TAREAS_FONDO.discard)
        return tarea
    except RuntimeError:
        pass

# =============================================================================
# HELPERS WINGET (Actualizaciones del sistema)
# =============================================================================

def _limpiar_version_winget(v):
    v = v.strip().lower()
    if v.startswith('v'):
        v = v[1:]
    if v.startswith('.'):
        v = v[1:]
    return v.strip()

def _version_mayor_o_igual(instalada, disponible):
    inst_limpia = _limpiar_version_winget(instalada)
    disp_limpia = _limpiar_version_winget(disponible)
    if inst_limpia == disp_limpia:
        return True
    try:
        import re
        inst_parts = [int(x) for x in re.split(r'[^0-9]', inst_limpia) if x]
        disp_parts = [int(x) for x in re.split(r'[^0-9]', disp_limpia) if x]
        for i in range(max(len(inst_parts), len(disp_parts))):
            p1 = inst_parts[i] if i < len(inst_parts) else 0
            p2 = disp_parts[i] if i < len(disp_parts) else 0
            if p1 > p2:
                return True
            elif p1 < p2:
                return False
        return True
    except Exception:
        pass
    return inst_limpia == disp_limpia

def listar_actualizaciones_winget():
    try:
        import subprocess
        res = subprocess.run(["winget", "upgrade"], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=20)
        stdout = res.stdout
    except subprocess.TimeoutExpired:
        print("[WINGET] winget upgrade expiró (timeout).")
        return []
    except Exception as e:
        try:
            res = subprocess.run(["winget", "upgrade"], capture_output=True, text=True, encoding="cp1252", errors="ignore", timeout=20)
            stdout = res.stdout
        except Exception as e2:
            print(f"[WINGET] Error ejecutando winget: {e2}")
            return []

    lineas = stdout.splitlines()
    indice_cabecera = -1
    for idx, linea in enumerate(lineas):
        if "-------------------" in linea or "======" in linea:
            indice_cabecera = idx - 1
            break

    if indice_cabecera == -1:
        print("[WINGET] No se encontró cabecera o sistema ya actualizado.")
        return []

    linea_cabecera = lineas[indice_cabecera]

    idx_id = linea_cabecera.find("ID")
    idx_ver = linea_cabecera.find("Version")
    idx_disp = linea_cabecera.find("Disponible")
    if idx_disp == -1:
        idx_disp = linea_cabecera.find("Available")
    idx_src = linea_cabecera.find("Source")

    if idx_id == -1 or idx_ver == -1 or idx_disp == -1 or idx_src == -1:
        print("[WINGET] Indexación de columnas imposible.")
        return []

    resultados = []
    for linea in lineas[indice_cabecera + 2:]:
        if not linea.strip():
            continue
        if any(term in linea.lower() for term in ["mise à niveau", "upgrade", "package", "número", "version"]):
            continue

        nombre = linea[:idx_id].strip()
        pkg_id = linea[idx_id:idx_ver].strip()
        version = linea[idx_ver:idx_disp].strip()
        disponible = linea[idx_disp:idx_src].strip()
        fuente = linea[idx_src:].strip()

        if pkg_id and disponible:
            if _version_mayor_o_igual(version, disponible):
                continue
            resultados.append({
                "nombre": nombre,
                "id": pkg_id,
                "version": version,
                "disponible": disponible,
                "fuente": fuente
            })

    return resultados

def ejecutar_actualizacion_winget_sync(args, bucle, cliente_websocket):
    try:
        import subprocess
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            bufsize=1,
            errors='ignore'
        )
        for linea in proc.stdout:
            texto = linea.strip()
            if texto:
                asyncio.run_coroutine_threadsafe(
                    cliente_websocket.send(json.dumps({
                        "type": "winget_upgrade_progress",
                        "status": "running",
                        "log": texto + "\n"
                    })),
                    bucle
                )
        proc.wait()
        asyncio.run_coroutine_threadsafe(
            cliente_websocket.send(json.dumps({
                "type": "winget_upgrade_progress",
                "status": "complete",
                "returncode": proc.returncode
            })),
            bucle
        )
        return proc.returncode == 0
    except Exception as e:
        print(f"[WINGET] Error ejecutando winget upgrade: {e}")
        asyncio.run_coroutine_threadsafe(
            cliente_websocket.send(json.dumps({
                "type": "winget_upgrade_progress",
                "status": "complete",
                "returncode": -1,
                "log": f"Error: {str(e)}\n"
            })),
            bucle
        )
        return False

# =============================================================================
# BÚSQUEDA DE RESTAURANTES (FONDO)
# =============================================================================

def lanzar_busqueda_restaurantes_fondo(ubicacion, lat, lng, excluir, es_otros=False):
    def trabajador():
        try:
            if BUCLE_WEB and BUCLE_WEB.is_running():
                asyncio.run_coroutine_threadsafe(enviar_estado_web("searching"), BUCLE_WEB)

            resultados = buscar_restaurantes_cercanos(ubicacion, lat, lng, excluir)

            async def _finalizar():
                try:
                    global ULTIMOS_RESTAURANTES_MOSTRADOS
                    if resultados:
                        for r in resultados:
                            if r["nombre"] not in ULTIMOS_RESTAURANTES_MOSTRADOS:
                                ULTIMOS_RESTAURANTES_MOSTRADOS.append(r["nombre"])
                        if len(ULTIMOS_RESTAURANTES_MOSTRADOS) > 18:
                            ULTIMOS_RESTAURANTES_MOSTRADOS = ULTIMOS_RESTAURANTES_MOSTRADOS[-18:]

                        msg = json.dumps({
                            "type": "show_restaurants",
                            "location": ubicacion,
                            "restaurants": resultados
                        })
                        if CLIENTES_CONECTADOS:
                            await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                    else:
                        await hablar(f"Lo siento {NOMBRE_USUARIO}, no pude encontrar restaurantes cercanos.")
                except Exception as e:
                    print(f"[RESTAURANTE] Error finalización: {e}")
                finally:
                    await enviar_estado_web("idle")

            if BUCLE_WEB and BUCLE_WEB.is_running():
                asyncio.run_coroutine_threadsafe(_finalizar(), BUCLE_WEB)
        except Exception as err:
            print(f"[RESTAURANTE THREAD ERROR] {err}")
            if BUCLE_WEB and BUCLE_WEB.is_running():
                asyncio.run_coroutine_threadsafe(enviar_estado_web("idle"), BUCLE_WEB)

    threading.Thread(target=trabajador, daemon=True).start()

# =============================================================================
# NVIDIA NEMOTRON ASR (Canary-1B) — Opcional
# =============================================================================

_nemotron_asr_ok = False
NemotronASR = None

try:
    _ruta_modelo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "canary-1b.nemo")
    _modelo_existe = os.path.exists(_ruta_modelo) and os.path.getsize(_ruta_modelo) == 4071127040

    import importlib.util
    _paquetes_instalados = (
        importlib.util.find_spec("torch") is not None and
        importlib.util.find_spec("nemo") is not None
    )
    _nemotron_asr_ok = _modelo_existe and _paquetes_instalados
except Exception:
    _nemotron_asr_ok = False

_tarea_instalar_nemotron = None
_tarea_desinstalar_nemotron = None

def detectar_gpu_nvidia():
    try:
        import subprocess
        res = subprocess.run(["nvidia-smi"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        if res.returncode == 0:
            return True
    except Exception:
        pass
    return False

def ejecutar_pip_install_sync(args, bucle, cliente_websocket, etapa, progreso):
    try:
        import subprocess
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            errors='ignore'
        )
        for linea in proc.stdout:
            texto = linea.strip()
            if texto:
                asyncio.run_coroutine_threadsafe(
                    cliente_websocket.send(json.dumps({
                        "type": "nemotron_install_progress",
                        "status": "installing",
                        "stage": etapa,
                        "progress": progreso,
                        "log": texto + "\n"
                    })),
                    bucle
                )
        proc.wait()
        return proc.returncode == 0
    except Exception as e:
        print(f"[ASR] Error ejecutando pip: {e}")
        return False

def descargar_archivo_sync(url, ruta_destino, bucle, cliente_websocket, etapa, progreso_inicio, progreso_fin):
    import requests
    import os
    import time

    os.makedirs(os.path.dirname(ruta_destino), exist_ok=True)
    temp_dest = ruta_destino + ".tmp"

    try:
        print(f"[ASR] Descargando modelo de {url} a {ruta_destino}...")
        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        descargado = 0
        ultima_actualizacion = 0

        with open(temp_dest, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    descargado += len(chunk)

                    tiempo_actual = time.time()
                    if tiempo_actual - ultima_actualizacion >= 0.5 or descargado == total_size:
                        ultima_actualizacion = tiempo_actual

                        if total_size > 0:
                            pct = descargado / total_size
                            progreso = progreso_inicio + int(pct * (progreso_fin - progreso_inicio))
                            mb_descargado = round(descargado / (1024 * 1024), 1)
                            mb_total = round(total_size / (1024 * 1024), 1)
                            log_texto = f"Descargando modelo: {mb_descargado} MB / {mb_total} MB ({round(pct * 100, 1)}%)\r"
                        else:
                            progreso = progreso_inicio
                            mb_descargado = round(descargado / (1024 * 1024), 1)
                            log_texto = f"Descargando modelo: {mb_descargado} MB...\r"

                        asyncio.run_coroutine_threadsafe(
                            cliente_websocket.send(json.dumps({
                                "type": "nemotron_install_progress",
                                "status": "installing",
                                "stage": etapa,
                                "progress": progreso,
                                "log": log_texto
                            })),
                            bucle
                        )

        asyncio.run_coroutine_threadsafe(
            cliente_websocket.send(json.dumps({
                "type": "nemotron_install_progress",
                "status": "installing",
                "stage": etapa,
                "progress": progreso_fin,
                "log": "\nDescarga del modelo finalizada con éxito.\n"
            })),
            bucle
        )

        if os.path.exists(ruta_destino):
            os.remove(ruta_destino)
        os.rename(temp_dest, ruta_destino)
        return True
    except Exception as e:
        print(f"[ASR] Error durante la descarga: {e}")
        if os.path.exists(temp_dest):
            try:
                os.remove(temp_dest)
            except Exception:
                pass
        return False

def ejecutar_pip_uninstall_sync(args, bucle, cliente_websocket, etapa):
    try:
        import subprocess
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            errors='ignore'
        )
        for linea in proc.stdout:
            texto = linea.strip()
            if texto:
                asyncio.run_coroutine_threadsafe(
                    cliente_websocket.send(json.dumps({
                        "type": "nemotron_uninstall_progress",
                        "status": "uninstalling",
                        "stage": etapa,
                        "progress": 70,
                        "log": texto + "\n"
                    })),
                    bucle
                )
        proc.wait()
        return proc.returncode == 0
    except Exception as e:
        print(f"[ASR] Error ejecutando pip uninstall: {e}")
        return False

async def instalar_dependencias_nemotron(cliente_websocket):
    global _tarea_instalar_nemotron, _nemotron_asr_ok, NemotronASR
    bucle = asyncio.get_running_loop()
    try:
        tiene_gpu = detectar_gpu_nvidia()
        gpu_str = "con soporte GPU CUDA" if tiene_gpu else "modo CPU solo (lento)"
        print(f"[ASR] Iniciando instalación automática de dependencias ({gpu_str})...")

        await cliente_websocket.send(json.dumps({
            "type": "nemotron_install_progress",
            "status": "started",
            "stage": "Detectando hardware...",
            "progress": 5,
            "log": f"GPU NVIDIA detectada: {tiene_gpu}\nIniciando instalación...\n"
        }))

        await cliente_websocket.send(json.dumps({
            "type": "nemotron_install_progress",
            "status": "installing",
            "stage": "Paso 1/3: Instalando PyTorch...",
            "progress": 10,
            "log": "Iniciando instalación de PyTorch...\n"
        }))

        import sys
        if tiene_gpu:
            pip_args = [sys.executable, "-m", "pip", "install", "torch", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu124"]
        else:
            pip_args = [sys.executable, "-m", "pip", "install", "torch", "torchaudio"]

        exito = await bucle.run_in_executor(
            None,
            ejecutar_pip_install_sync,
            pip_args,
            bucle,
            cliente_websocket,
            "Paso 1/3: Instalando PyTorch...",
            20
        )

        if not exito:
            raise Exception("La instalación de PyTorch falló. Consulta los logs.")

        await cliente_websocket.send(json.dumps({
            "type": "nemotron_install_progress",
            "status": "installing",
            "stage": "Paso 2/3: Instalando NeMo Toolkit...",
            "progress": 40,
            "log": "\nPyTorch instalado con éxito.\nIniciando instalación de NeMo Toolkit (ASR)...\n"
        }))

        if tiene_gpu:
            pip_args = [sys.executable, "-m", "pip", "install", "nemo_toolkit[asr]", "--extra-index-url", "https://download.pytorch.org/whl/cu124"]
        else:
            pip_args = [sys.executable, "-m", "pip", "install", "nemo_toolkit[asr]"]
        exito = await bucle.run_in_executor(
            None,
            ejecutar_pip_install_sync,
            pip_args,
            bucle,
            cliente_websocket,
            "Paso 2/3: Instalando NeMo Toolkit...",
            50
        )

        if not exito:
            raise Exception("La instalación de NeMo Toolkit falló. Consulta los logs.")

        await cliente_websocket.send(json.dumps({
            "type": "nemotron_install_progress",
            "status": "installing",
            "stage": "Paso 3/3: Descargando modelo Canary-1B (~4 GB)...",
            "progress": 65,
            "log": "\nNeMo Toolkit instalado.\nIniciando descarga del modelo local Canary-1B (~4 GB)...\n"
        }))

        ruta_destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "canary-1b.nemo")
        if os.path.exists(ruta_destino) and os.path.getsize(ruta_destino) == 4071127040:
            await cliente_websocket.send(json.dumps({
                "type": "nemotron_install_progress",
                "status": "installing",
                "stage": "Paso 3/3: Descargando modelo Canary-1B...",
                "progress": 90,
                "log": "El modelo ya está presente localmente (tamaño verificado). Paso omitido.\n"
            }))
        else:
            url = "https://huggingface.co/nvidia/canary-1b/resolve/main/canary-1b.nemo"
            exito = await bucle.run_in_executor(
                None,
                descargar_archivo_sync,
                url,
                ruta_destino,
                bucle,
                cliente_websocket,
                "Paso 3/3: Descargando modelo Canary-1B...",
                65,
                90
            )
            if not exito:
                raise Exception("La descarga del modelo Canary-1B falló.")

        await cliente_websocket.send(json.dumps({
            "type": "nemotron_install_progress",
            "status": "installing",
            "stage": "Verificando instalación...",
            "progress": 95,
            "log": "Verificando compatibilidad de importaciones...\n"
        }))

        import importlib
        try:
            try:
                import pyarrow.dataset
            except ImportError:
                pass

            import torch
            torch_lib_dir = os.path.join(os.path.dirname(torch.__file__), "lib")
            if os.path.exists(torch_lib_dir) and hasattr(os, "add_dll_directory"):
                os.add_dll_directory(torch_lib_dir)

            import nemo.collections.asr as nemo_asr
            import nemotron_asr
            importlib.reload(nemotron_asr)
            _esta_instalado = nemotron_asr.NemotronASR.is_nemo_installed()
            _ruta_modelo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "canary-1b.nemo")
            _nemotron_asr_ok = _esta_instalado and os.path.exists(_ruta_modelo) and os.path.getsize(_ruta_modelo) == 4071127040
            NemotronASR = nemotron_asr.NemotronASR
        except Exception as e:
            raise Exception(f"Error de importación tras instalación: {e}")

        if _nemotron_asr_ok:
            await cliente_websocket.send(json.dumps({
                "type": "nemotron_install_progress",
                "status": "success",
                "stage": "¡Instalación finalizada con éxito!",
                "progress": 100,
                "log": "¡Felicidades! NVIDIA Nemotron ASR está listo para usar.\n"
            }))
            print("[ASR] Instalación automática finalizada con éxito.")
            estado_resultado = {
                "type": "nemotron_asr_state",
                "enabled": False,
                "gpu_available": tiene_gpu,
                "warnings": [],
                "error": None
            }
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(json.dumps(estado_resultado)) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
        else:
            raise Exception("La instalación fue exitosa pero NeMo sigue sin poder importarse.")

    except Exception as e:
        error_msg = str(e)
        print(f"[ASR] ✖ Falló instalación automática: {error_msg}")

        guia_manual = (
            f"\n[ERROR] {error_msg}\n\n"
            "=======================================================================\n"
            "                 GUÍA DE INSTALACIÓN MANUAL DE NEMOTRON\n"
            "=======================================================================\n"
            "Si la instalación automática falló, puedes instalarlo manualmente:\n\n"
            "1. Crea la carpeta 'models' si no existe, en la raíz del proyecto AP0L0 OMEGA:\n"
            "   -> Carpeta destino: [ruta_omega]/models\n\n"
            "2. Descarga el archivo del modelo Canary-1B (~4 GB) desde Hugging Face:\n"
            "   -> URL: https://huggingface.co/nvidia/canary-1b/resolve/main/canary-1b.nemo\n"
            "   -> Guárdalo con el nombre EXACTO: canary-1b.nemo\n"
            "   -> Muévelo a la carpeta 'models' creada arriba.\n\n"
            "3. Abre un símbolo del sistema (CMD) en la carpeta raíz de AP0L0 OMEGA:\n"
            "   a) Activa el venv local e instala PyTorch:\n"
            "      - Para soporte GPU NVIDIA CUDA (Recomendado si tienes GPU Nvidia):\n"
            "        .\\venv\\Scripts\\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124\n"
            "      - Para CPU solamente:\n"
            "        .\\venv\\Scripts\\python.exe -m pip install torch torchaudio\n"
            "   b) Instala el paquete NeMo Toolkit:\n"
            "      .\\venv\\Scripts\\python.exe -m pip install nemo_toolkit[asr]\n\n"
            "4. Reinicia AP0L0 OMEGA. ¡El sistema detectará automáticamente la instalación!\n"
            "=======================================================================\n"
        )

        await cliente_websocket.send(json.dumps({
            "type": "nemotron_install_progress",
            "status": "error",
            "stage": "Fallo en la instalación",
            "progress": 0,
            "log": guia_manual
        }))
    finally:
        _tarea_instalar_nemotron = None

async def desinstalar_dependencias_nemotron(cliente_websocket):
    global _tarea_desinstalar_nemotron, _nemotron_asr_ok, NemotronASR, NEMOTRON_ASR_ACTIVADO, _instancia_nemotron
    bucle = asyncio.get_running_loop()
    try:
        print("[ASR] Iniciando desinstalación de Nemotron ASR...")

        NEMOTRON_ASR_ACTIVADO = False
        if _instancia_nemotron:
            print("[ASR] Liberando instancia Nemotron...")
            await asyncio.to_thread(_instancia_nemotron.liberar)
            _instancia_nemotron = None

        await cliente_websocket.send(json.dumps({
            "type": "nemotron_uninstall_progress",
            "status": "started",
            "stage": "Desinstalando...",
            "progress": 5,
            "log": "Modelo detenido y liberado.\n"
        }))

        ruta_destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "canary-1b.nemo")
        if os.path.exists(ruta_destino):
            await cliente_websocket.send(json.dumps({
                "type": "nemotron_uninstall_progress",
                "status": "uninstalling",
                "stage": "Paso 1/2: Eliminando modelo...",
                "progress": 20,
                "log": f"Eliminando modelo local (~4 GB) en {ruta_destino}...\n"
            }))
            try:
                os.remove(ruta_destino)
                models_dir = os.path.dirname(ruta_destino)
                if os.path.exists(models_dir) and not os.listdir(models_dir):
                    os.rmdir(models_dir)
                await cliente_websocket.send(json.dumps({
                    "type": "nemotron_uninstall_progress",
                    "status": "uninstalling",
                    "stage": "Paso 1/2: Eliminando modelo...",
                    "progress": 40,
                    "log": "Archivo del modelo eliminado.\n"
                }))
            except Exception as e:
                await cliente_websocket.send(json.dumps({
                    "type": "nemotron_uninstall_progress",
                    "status": "uninstalling",
                    "stage": "Paso 1/2: Eliminando modelo...",
                    "progress": 40,
                    "log": f"Advertencia al eliminar el modelo: {e}\n"
                }))
        else:
            await cliente_websocket.send(json.dumps({
                "type": "nemotron_uninstall_progress",
                "status": "uninstalling",
                "stage": "Paso 1/2: Eliminando modelo...",
                "progress": 40,
                "log": "No se encontró modelo local para eliminar.\n"
            }))

        await cliente_websocket.send(json.dumps({
            "type": "nemotron_uninstall_progress",
            "status": "uninstalling",
            "stage": "Paso 2/2: Desinstalando paquetes...",
            "progress": 50,
            "log": "Iniciando desinstalación de nemo-toolkit, torch y torchaudio...\n"
        }))

        import sys
        pip_args = [sys.executable, "-m", "pip", "uninstall", "-y", "nemo-toolkit", "torch", "torchaudio"]

        exito = await bucle.run_in_executor(
            None,
            ejecutar_pip_uninstall_sync,
            pip_args,
            bucle,
            cliente_websocket,
            "Paso 2/2: Desinstalando paquetes..."
        )

        if not exito:
            await cliente_websocket.send(json.dumps({
                "type": "nemotron_uninstall_progress",
                "status": "uninstalling",
                "stage": "Paso 2/2: Desinstalando paquetes...",
                "progress": 85,
                "log": "Desinstalación pip incompleta o con advertencias.\n"
            }))
        else:
            await cliente_websocket.send(json.dumps({
                "type": "nemotron_uninstall_progress",
                "status": "uninstalling",
                "stage": "Paso 2/2: Desinstalando paquetes...",
                "progress": 85,
                "log": "Paquetes pip desinstalados con éxito.\n"
            }))

        await cliente_websocket.send(json.dumps({
            "type": "nemotron_uninstall_progress",
            "status": "uninstalling",
            "stage": "Finalizando...",
            "progress": 90,
            "log": "Actualizando configuración de Omega...\n"
        }))

        _nemotron_asr_ok = False
        NemotronASR = None
        _guardar_config({"nemotron_asr_enabled": False})

        await cliente_websocket.send(json.dumps({
            "type": "nemotron_uninstall_progress",
            "status": "success",
            "stage": "¡Desinstalación finalizada con éxito!",
            "progress": 100,
            "log": "Desinstalación completada. Volviendo al modo Google Speech Recognition.\n"
        }))
        print("[ASR] Desinstalación automática finalizada con éxito.")

        estado_resultado = {
            "type": "nemotron_asr_state",
            "enabled": False,
            "gpu_available": detectar_gpu_nvidia(),
            "warnings": [],
            "error": None
        }
        if CLIENTES_CONECTADOS:
            await asyncio.gather(*[ws.send(json.dumps(estado_resultado)) for ws in CLIENTES_CONECTADOS], return_exceptions=True)

    except Exception as e:
        print(f"[ASR] ✖ Falló desinstalación automática: {e}")
        await cliente_websocket.send(json.dumps({
            "type": "nemotron_uninstall_progress",
            "status": "error",
            "stage": "Fallo en la desinstalación",
            "progress": 0,
            "log": f"\n[ERROR] {str(e)}\n"
        }))
    finally:
        _tarea_desinstalar_nemotron = None

# =============================================================================
# IMPORTACIONES ADICIONALES
# =============================================================================

import pyautogui
import webbrowser
import subprocess
import requests
import time
import pickle
import json
import re
import shutil
from pathlib import Path
from datetime import datetime
try:
    import pyaudio
except ImportError:
    pyaudio = None
    print("[ADVERTENCIA] pyaudio no instalado — el micrófono estará desactivado.")
    print("  -> Para instalarlo: pip install pipwin && pipwin install pyaudio")

import websockets
from PIL import Image
from openai import OpenAI
import uuid
import base64
import io
try:
    import cv2
except ImportError:
    cv2 = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    import anthropic as _anthropic_lib
except ImportError:
    _anthropic_lib = None

import ctypes
from ctypes import wintypes
user32 = ctypes.windll.user32

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    _google_apis_ok = True
except ImportError:
    _google_apis_ok = False
    Credentials = None
    InstalledAppFlow = None
    Request = None
    build = None
    print("[ADVERTENCIA] google-auth-oauthlib no instalado — Gmail/Drive/Calendar desactivados.")
    print("  -> Para instalarlo: pip install google-auth-oauthlib google-api-python-client")

try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    _pycaw_ok = True
except ImportError:
    _pycaw_ok = False

try:
    import screen_brightness_control as _sbc
    _sbc_ok = True
except ImportError:
    _sbc = None
    _sbc_ok = False

try:
    import webview
    _WEBVIEW_OK = True
except ImportError:
    webview = None
    _WEBVIEW_OK = False

_VENTANA_WEBVIEW = None

# =============================================================================
# CONFIGURACIÓN DE VERSIÓN Y ACTUALIZACIONES
# =============================================================================

VERSION_ACTUAL = "9.5"
URL_JSON_ACTUALIZACION = "https://www.techenclair.fr/updates/jarvis_update.json"
ULTIMA_INFO_ACTUALIZACION = None

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

def obtener_ip_local():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

IP_LOCAL = obtener_ip_local()

GEMINI_API_KEY = ""
YOUTUBE_API_KEY = ""
XAI_API_KEY = ""
SERPAPI_API_KEY = ""
GROQ_API_KEY = ""
ANTHROPIC_API_KEY = ""
MISTRAL_API_KEY = ""
SPOTIFY_MUSICA_URI = os.getenv("SPOTIFY_MUSICA_URI", "")
builtins.SPOTIFY_MUSICA_URI = SPOTIFY_MUSICA_URI
YOUTUBE_MUSICA_URL = os.getenv("YOUTUBE_MUSICA_URL", "")
builtins.YOUTUBE_MUSICA_URL = YOUTUBE_MUSICA_URL

def _cargar_enlace_musica() -> str:
    try:
        import json as _j
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        with open(_p, "r", encoding="utf-8") as _f:
            return _j.load(_f).get("musica_enlace", "")
    except Exception:
        return ""

ENLACE_MUSICA_PERSO = _cargar_enlace_musica()

_ESPACIOS_RESERVADOS_API = frozenset({"VOTRE_CLE_ICI", "Votre ID", "votre_id", "VOTRE_TOKEN_ICI", "votre_token_ici", ""})
def _clave_valida(key):
    return bool(key) and str(key).strip() not in _ESPACIOS_RESERVADOS_API

import builtins
builtins._clave_valida = _clave_valida

from src.actions.ha_config import (
    HA_URL, HA_HEADERS,
    CIUDAD_POR_DEFECTO, LAT_POR_DEFECTO, LON_POR_DEFECTO,
    PIEZAS_LUCES, PIEZAS_ENCHUFES, PIEZAS_SENSORES, PIEZAS_HUMEDAD,
    HA_TARIFAS, APARATOS_ENERGIA, APARATOS_BATERIA,
    COLORES_MAP, CODIGOS_METEO,
    ha_llamar_servicio, ha_obtener_estado, ha_obtener_calendario,
    ha_luz, ha_interruptor, ha_termostato, ha_escena, ha_cerradura,
    geocodificar_ciudad, obtener_meteo_actual, obtener_meteo_ha, obtener_alertas_meteo,
    obtener_meteo_estructurada,
)

gemini_activo = False
cliente = None
grok_cliente = None
groq_cliente = None
anthropic_cliente = None
mistral_cliente = None

def _guardar_env(datos: dict) -> None:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    lineas = []
    claves_existentes = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lineas = f.readlines()
        for idx, linea in enumerate(lineas):
            linea_strip = linea.strip()
            if linea_strip and not linea_strip.startswith("#") and "=" in linea_strip:
                clave, _ = linea_strip.split("=", 1)
                claves_existentes[clave.strip()] = idx

    for clave, valor in datos.items():
        os.environ[clave] = str(valor)
        contenido_linea = f"{clave}={valor}\n"
        if clave in claves_existentes:
            lineas[claves_existentes[clave]] = contenido_linea
        else:
            if lineas and not lineas[-1].endswith("\n"):
                lineas[-1] = lineas[-1] + "\n"
            lineas.append(contenido_linea)
            claves_existentes[clave] = len(lineas) - 1

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lineas)
        print(f"[CONFIG ENV] .env actualizado con: {list(datos.keys())}")
    except Exception as e:
        print(f"[CONFIG ENV] Error escribiendo .env: {e}")

def recargar_clientes_ia():
    global GEMINI_API_KEY, YOUTUBE_API_KEY, XAI_API_KEY, SERPAPI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY, MISTRAL_API_KEY, OPENAI_API_KEY
    global gemini_activo, cliente, grok_cliente, groq_cliente, anthropic_cliente, mistral_cliente, openai_cliente

    from dotenv import load_dotenv
    load_dotenv(override=True)

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
    XAI_API_KEY = os.getenv("XAI_API_KEY", "")
    SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    cfg = _cargar_config()
    gemini_activado = cfg.get("api_gemini_activado", True)
    groq_activado = cfg.get("api_groq_activado", True)
    grok_activado = cfg.get("api_grok_activado", True)
    anthropic_activado = cfg.get("api_anthropic_activado", True)
    mistral_activado = cfg.get("api_mistral_activado", True)
    openai_activado = cfg.get("api_openai_activado", True)

    gemini_key_a_usar = GEMINI_API_KEY if gemini_activado else ""
    groq_key_a_usar = GROQ_API_KEY if groq_activado else ""
    grok_key_a_usar = XAI_API_KEY if grok_activado else ""
    anthropic_key_a_usar = ANTHROPIC_API_KEY if anthropic_activado else ""
    mistral_key_a_usar = MISTRAL_API_KEY if mistral_activado else ""
    openai_key_a_usar = OPENAI_API_KEY if openai_activado else ""

    gemini_activo = _clave_valida(gemini_key_a_usar)
    if gemini_activo:
        import google.genai as _genai
        cliente = _genai.Client(api_key=gemini_key_a_usar)
        builtins.cliente = cliente
    else:
        cliente = None
        builtins.cliente = None

    if _clave_valida(grok_key_a_usar):
        grok_cliente = OpenAI(api_key=grok_key_a_usar, base_url="https://api.x.ai/v1")
    else:
        grok_cliente = None

    if _clave_valida(groq_key_a_usar):
        groq_cliente = OpenAI(api_key=groq_key_a_usar, base_url="https://api.groq.com/openai/v1")
    else:
        groq_cliente = None

    if _anthropic_lib and _clave_valida(anthropic_key_a_usar):
        anthropic_cliente = _anthropic_lib.Anthropic(api_key=anthropic_key_a_usar)
    else:
        anthropic_cliente = None

    if _clave_valida(mistral_key_a_usar):
        mistral_cliente = OpenAI(api_key=mistral_key_a_usar, base_url="https://api.mistral.ai/v1")
    else:
        mistral_cliente = None

    if _clave_valida(openai_key_a_usar):
        openai_cliente = OpenAI(api_key=openai_key_a_usar)
    else:
        openai_cliente = None

    print("[IA CLIENTES] Clientes IA recargados dinámicamente.")

recargar_clientes_ia()

LISTA_MODELOS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash", "gemini-2.5-pro", "gemini-2.0-flash-exp"]
MODELOS_SELECCIONADOS = agent_model_manager.load_chosen_models()

import builtins
builtins.cliente = cliente
builtins.MODELOS_SELECCIONADOS = MODELOS_SELECCIONADOS

OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODELOS = ["mistral:instruct", "mistral", "llama3:8b", "llama3", "gemma4"]
KOKORO_URL = "http://127.0.0.1:8880"

# =============================================================================
# GESTOR DE CUOTAS API — Failover automático
# =============================================================================

class _ErrorCuotaExcedida(Exception):
    """Lanzada cuando una API señala que su cuota o rate-limit está agotado."""
    pass

class GestorCuotasAPI:
    """
    Gestiona el cooldown de las APIs cuando su cuota se agota.
    Detecta automáticamente errores 429 / resource_exhausted / rate_limit.
    """

    COOLDOWNS = {
        "claude": 60,
        "gemini": 60,
        "grok": 60,
        "groq": 30,
        "mistral": 60,
        "openai": 60,
        "mistral": 30,
        "ollama": 10,
    }

    PALABRAS_CLAVE_CUOTA = [
        "429", "quota", "rate limit", "rate_limit", "ratelimit",
        "too many requests", "resource_exhausted", "resource exhausted",
        "exceeded", "tokens per", "requests per", "rateLimitExceeded",
        "quota_exceeded", "RATE_LIMIT_EXCEEDED", "insufficient_quota",
        "context_length_exceeded",
    ]

    def __init__(self):
        from datetime import datetime, timedelta
        self._datetime = datetime
        self._timedelta = timedelta
        self._cooldowns = {}
        self._contador_impactos = {}

    def es_error_cuota(self, error: Exception) -> bool:
        err_str = str(error).lower()
        return any(kw.lower() in err_str for kw in self.PALABRAS_CLAVE_CUOTA)

    def esta_disponible(self, nombre_api: str) -> bool:
        if nombre_api not in self._cooldowns:
            return True
        return self._datetime.now() >= self._cooldowns[nombre_api]

    def marcar_cuota_excedida(self, nombre_api: str) -> None:
        duracion = self.COOLDOWNS.get(nombre_api, 60)
        self._cooldowns[nombre_api] = self._datetime.now() + self._timedelta(seconds=duracion)
        self._contador_impactos[nombre_api] = self._contador_impactos.get(nombre_api, 0) + 1
        print(f"[CUOTA] ⚠ {nombre_api.upper()} cuota alcanzada — cooldown {duracion}s "
              f"(total: {self._contador_impactos[nombre_api]} veces)")

    def cooldown_restante(self, nombre_api: str) -> int:
        if self.esta_disponible(nombre_api):
            return 0
        delta = self._cooldowns[nombre_api] - self._datetime.now()
        return max(0, int(delta.total_seconds()))

    def estado(self) -> str:
        lineas = []
        for api in self.COOLDOWNS:
            if not self.esta_disponible(api):
                lineas.append(f"  {api.upper()}: cooldown {self.cooldown_restante(api)}s")
            else:
                lineas.append(f"  {api.upper()}: disponible")
        return "\n".join(lineas)

_gestor_cuotas = GestorCuotasAPI()

# =============================================================================
# CONSTANTES GLOBALES
# =============================================================================

UMBRAL_APLAUSO = 1200
VIDEO_LANZADA = False
MODO_IRON_MAN = False

_linea_edad = f"- Edad: {EDAD_USUARIO} años\n" if EDAD_USUARIO else ""
INFORMACION_CREADOR = (
    "INFORMACIÓN SOBRE TU CREADOR:\n"
    f"- Nombre: {NOMBRE_USUARIO}\n"
    + _linea_edad +
    "- Rol: Tu creador y maestro\n"
    f"- Siempre debes llamarlo {NOMBRE_USUARIO} con respeto "
    "pero también con un toque de sarcasmo afectuoso.\n"
)

EXTENSIONES = {
    "Imágenes": [".jpg", ".jpeg", ".png", ".gif", ".bmp",
                 ".tiff", ".tif", ".webp", ".svg", ".ico",
                 ".heic", ".raw", ".cr2", ".nef"],
    "Videos": [".mp4", ".avi", ".mkv", ".mov", ".wmv",
               ".flv", ".webm", ".m4v", ".mpg", ".mpeg"],
    "Música": [".mp3", ".wav", ".flac", ".aac", ".ogg",
               ".wma", ".m4a", ".opus", ".aiff"],
    "Documentos": [".pdf", ".doc", ".docx", ".xls", ".xlsx",
                   ".ppt", ".pptx", ".txt", ".odt", ".ods",
                   ".odp", ".rtf", ".csv", ".epub"],
    "Archivos": [".zip", ".rar", ".7z", ".tar", ".gz",
                 ".bz2", ".xz", ".iso"],
    "Código": [".py", ".js", ".html", ".css", ".java",
               ".cpp", ".c", ".h", ".cs", ".php",
               ".json", ".xml", ".yaml", ".yml",
               ".sh", ".bat", ".ps1", ".ts", ".jsx",
               ".tsx", ".vue", ".go", ".rs", ".rb"],
    "Ejecutables": [".exe", ".msi", ".apk", ".dmg", ".deb"],
}

carpeta_actual = None

# =============================================================================
# WEBSOCKET
# =============================================================================

CLIENTES_CONECTADOS = set()
builtins.CLIENTES_CONECTADOS = CLIENTES_CONECTADOS
interfaz_ya_conectada = False
_saltar_audio_pc = False
CAPTURAS_PANTALLA_PENDIENTES = {}
CAPTURAS_CAMARA_PENDIENTES = {}
WEBCAM_ACTIVA = False
builtins.WEBCAM_ACTIVA = WEBCAM_ACTIVA

def _instalar_omega_os(ruta, websocket, bucle):
    import subprocess
    import time
    nombre_imagen = "lscr.io/linuxserver/webtop:ubuntu-xfce"

    def enviar_progreso(estado, pct, log_msg=None, done=False, puerto=3000):
        msg = {"type": "omega_os_install_progress", "status": estado, "progress": pct, "done": done, "port": puerto}
        if log_msg:
            msg["log"] = log_msg
        asyncio.run_coroutine_threadsafe(websocket.send(json.dumps(msg)), bucle)

    try:
        import shutil
        import os

        wsl_instalado = True
        if not shutil.which("wsl"):
            wsl_instalado = False
        else:
            wsl_res = subprocess.run(["wsl", "--status"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            if wsl_res.returncode != 0:
                wsl_instalado = False

        if not wsl_instalado:
            enviar_progreso("Instalando WSL (Requisito previo)...", 2, "WSL no está instalado. Se abrirá una ventana de Administrador para instalarlo.")
            enviar_progreso("Instalando WSL (Requisito previo)...", 2, "⚠️ POR FAVOR, ACEPTA EL UAC (SÍ). La instalación tomará unos minutos.")

            wsl_cmd = ["powershell", "-Command", "Start-Process powershell -ArgumentList '-NoProfile -Command wsl --install --no-distribution' -Verb RunAs -Wait"]
            subprocess.run(wsl_cmd, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)

            enviar_progreso("¡Reinicio requerido!", 2, "La instalación de WSL ha finalizado. DEBES REINICIAR TU PC AHORA.")
            enviar_progreso("¡Reinicio requerido!", 2, "Después del reinicio, relanza AP0L0 OMEGA y vuelve a iniciar la instalación.")
            return

        if not shutil.which("docker"):
            enviar_progreso("Instalando Docker (Requisito previo)...", 5, "Docker no está instalado. Iniciando instalación automática vía Winget...")
            enviar_progreso("Instalando Docker (Requisito previo)...", 5, "⚠️ APARECERÁ UNA VENTANA SOLICITANDO AUTORIZACIÓN (UAC). POR FAVOR, ACEPTA.")

            winget_cmd = ["winget", "install", "Docker.DockerDesktop", "-e", "--accept-package-agreements", "--accept-source-agreements", "--silent"]
            proc = subprocess.Popen(winget_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding='utf-8', errors='replace')

            for linea in proc.stdout:
                enviar_progreso("Instalando Docker...", 5, linea.strip())
            proc.wait()

            if proc.returncode != 0:
                enviar_progreso("Fallo en la instalación de Docker.", 5, f"Winget devolvió el código: {proc.returncode}. Instala Docker manualmente.")
                return

        docker_listo = False
        for i in range(30):
            try:
                res = subprocess.run(["docker", "info"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                if res.returncode == 0:
                    docker_listo = True
                    break
            except FileNotFoundError:
                pass

            if i == 0:
                enviar_progreso("Iniciando Docker Desktop...", 8, "El motor Docker aún no está listo. Iniciando...")
                docker_path = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"
                if os.path.exists(docker_path):
                    subprocess.Popen([docker_path])

            enviar_progreso("Iniciando Docker Desktop...", 8, f"Esperando inicialización del motor Docker... ({i}/30) Esto puede tomar 1-2 minutos tras un reinicio.")
            time.sleep(2)

        if not docker_listo:
            enviar_progreso("Error", 8, "El motor Docker no pudo iniciarse. Inicia Docker Desktop manualmente desde el menú Inicio para verificar si hay un error.")
            return

        enviar_progreso("Descargando entorno Linux...", 10, f"Ejecutando: docker pull {nombre_imagen}")

        process = subprocess.Popen(["docker", "pull", nombre_imagen], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding='utf-8', errors='replace')

        pct = 10
        for linea in process.stdout:
            if "Pulling fs layer" in linea:
                pct = min(30, pct + 2)
            elif "Downloading" in linea:
                pct = min(70, pct + 1)
            elif "Extracting" in linea:
                pct = min(90, pct + 1)
            enviar_progreso("Descargando entorno Linux...", pct, linea.strip())

        process.wait()

        if process.returncode != 0:
            enviar_progreso("Error durante la descarga.", pct, f"Código de retorno: {process.returncode}")
            return

        enviar_progreso("Configurando subsistema...", 95, "Creando contenedor...")

        subprocess.run(["docker", "rm", "-f", "omega_os"], capture_output=True)

        ruta_datos = os.path.join(ruta, "omega_os_data")
        ruta_compartida = os.path.join(ruta, "omega_os_shared")

        cmd = [
            "docker", "run", "-d",
            "--name=omega_os",
            "--security-opt", "seccomp=unconfined",
            "-e", "PUID=1000",
            "-e", "PGID=1000",
            "-e", "TZ=Europe/Paris",
            "-p", "3000:3000",
            "-v", f"{ruta_datos}:/config",
            "-v", f"{ruta_compartida}:/config/Desktop/Shared",
            "-v", "/mnt/host:/config/Desktop/Disques_PC:rshared",
            "--shm-size=2gb",
            "--restart", "unless-stopped",
            nombre_imagen
        ]

        run_proc = subprocess.run(cmd, capture_output=True, text=True)
        if run_proc.returncode == 0:
            enviar_progreso("Instalación finalizada con éxito.", 100, "El contenedor está listo.", True, 3000)
        else:
            enviar_progreso("Error al iniciar el contenedor.", 95, run_proc.stderr)

    except Exception as e:
        enviar_progreso("Excepción fatal durante la instalación", 0, str(e))

async def manejador_ws(websocket):
    global interfaz_ya_conectada, DETENER_HABLA, MICRO_MUTED, UBICACION_USUARIO_GPS, NEMOTRON_ASR_ACTIVADO, _instancia_nemotron, NOMBRE_USUARIO, EDAD_USUARIO, ENLACE_MUSICA_PERSO, MICRO_NECESITA_RECARGAR, omega_activo, CIUDAD_POR_DEFECTO, LAT_POR_DEFECTO, LON_POR_DEFECTO, ESPERANDO_ELECCION_MODELO_IMAGEN, ESPERANDO_ELECCION_MODELO_SITIO, PROMPT_EN_ESPERA, MODELOS_SELECCIONADOS, ESPERANDO_CREACION_PROMPT
    CLIENTES_CONECTADOS.add(websocket)
    interfaz_ya_conectada = True
    print(f"[WEB] Interfaz conectada (Clientes activos: {len(CLIENTES_CONECTADOS)})")

    if ULTIMA_INFO_ACTUALIZACION:
        try:
            await websocket.send(json.dumps(ULTIMA_INFO_ACTUALIZACION))
        except:
            pass

    try:
        async for mensaje in websocket:
            try:
                datos = json.loads(mensaje)
                if datos.get("type") == "mobile_command":
                    texto = datos.get("text", "").strip()
                    target_pc = datos.get("target_pc", False)
                    if texto:
                        print(f"[MÓVIL] Comando recibido: {texto}")
                        asyncio.ensure_future(procesar_respuesta_ia(texto, mobile_ws=websocket, target_pc=target_pc))
                elif datos.get("type") == "get_available_models":
                    cfg = _cargar_config()
                    preferido = cfg.get("preferred_brain", "auto")
                    preferred_local = cfg.get("preferred_local_model", "dolphin3")
                    modelos = []
                    if gemini_activo:
                        modelos.append("gemini")
                    if anthropic_cliente:
                        modelos.append("claude")
                    if groq_cliente:
                        modelos.append("groq")
                    if mistral_cliente:
                        modelos.append("mistral")
                    if grok_cliente:
                        modelos.append("grok")
                    if openai_cliente:
                        modelos.append("openai")
                    modelos.append("local_uncensored")
                    from src.core.agent_model_manager import LOCAL_OLLAMA_MODELS
                    await websocket.send(json.dumps({
                        "type": "available_models",
                        "models": modelos,
                        "prefered": preferido,
                        "preferred_local_model": preferred_local,
                        "local_ollama_models": {
                            k: v["label"] for k, v in LOCAL_OLLAMA_MODELS.items()
                        }
                    }))
                elif datos.get("type") == "check_ollama_status":
                    estado_data = _verificar_estado_ollama()
                    await websocket.send(json.dumps({
                        "type": "ollama_status_reply",
                        "status": estado_data
                    }))
                elif datos.get("type") == "pull_ollama_model":
                    nombre_modelo = datos.get("model", "dolphin3")
                    bucle = asyncio.get_running_loop()
                    threading.Thread(target=_descargar_modelo_ollama, args=(nombre_modelo, bucle, websocket), daemon=True).start()
                elif datos.get("type") == "set_local_model":
                    local_model = datos.get("model", "dolphin3")
                    from src.core.agent_model_manager import LOCAL_OLLAMA_MODELS
                    if local_model in LOCAL_OLLAMA_MODELS:
                        cfg = _cargar_config()
                        cfg["preferred_local_model"] = local_model
                        _guardar_config(cfg)
                        print(f"[MODELO LOCAL] Modelo local preferido definido en: {local_model}")
                        await websocket.send(json.dumps({"type": "local_model_saved", "model": local_model}))
                elif datos.get("type") == "check_kokoro_status":
                    st = _verificar_estado_kokoro()
                    await websocket.send(json.dumps({
                        "type": "kokoro_status_reply",
                        "status": st
                    }))
                elif datos.get("type") == "install_kokoro_tts":
                    bucle = asyncio.get_running_loop()
                    threading.Thread(target=_instalar_kokoro_tts, args=(bucle, websocket), daemon=True).start()
                elif datos.get("type") == "set_primary_model":
                    modelo = datos.get("model")
                    cfg = _cargar_config()
                    cfg["preferred_brain"] = modelo
                    _guardar_config(cfg)
                    print(f"[MÓVIL] Modelo preferido definido en: {modelo}")
                elif datos.get("type") == "stop_audio":
                    DETENER_HABLA = True
                    omega_activo = False
                    print("[MÓVIL] Señal STOP de audio recibida, volviendo a espera")
                elif datos.get("type") == "toggle_mic":
                    MICRO_MUTED = not MICRO_MUTED
                    await websocket.send(json.dumps({"type": "mic_state", "muted": MICRO_MUTED}))
                    if MICRO_MUTED:
                        await enviar_estado_web("idle")
                    print(f"[WEB] Micro {'CORTADO' if MICRO_MUTED else 'ACTIVO'}")
                elif datos.get("type") == "toggle_fullscreen":
                    if _VENTANA_WEBVIEW:
                        _VENTANA_WEBVIEW.toggle_fullscreen()
                        print("[WEB] Cambio a pantalla completa pywebview")
                elif datos.get("type") == "check_omega_os_status":
                    cfg = _cargar_config()
                    ruta = cfg.get("omega_os_path")
                    instalado = False
                    if ruta:
                        import subprocess
                        try:
                            res = subprocess.run(["docker", "ps", "-a", "--filter", "name=omega_os", "--format", "{{.Names}}"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                            if "omega_os" in res.stdout:
                                instalado = True
                                res_up = subprocess.run(["docker", "ps", "--filter", "name=omega_os", "--format", "{{.Names}}"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                                if "omega_os" not in res_up.stdout:
                                    subprocess.run(["docker", "start", "omega_os"], creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                                    await asyncio.sleep(3)
                        except FileNotFoundError:
                            instalado = False
                    await websocket.send(json.dumps({
                        "type": "omega_os_status_reply",
                        "installed": instalado,
                        "port": 3000
                    }))
                elif datos.get("type") == "omega_os_pick_folder":
                    _bucle = asyncio.get_running_loop()

                    def _seleccionar_carpeta():
                        try:
                            import tkinter as tk
                            from tkinter import filedialog
                            root = tk.Tk()
                            root.withdraw()
                            root.attributes('-topmost', True)
                            carpeta = filedialog.askdirectory(title="Elegir carpeta de instalación de AP0L0 OS")
                            root.destroy()
                            if carpeta:
                                asyncio.run_coroutine_threadsafe(
                                    websocket.send(json.dumps({"type": "omega_os_folder_picked", "path": carpeta})),
                                    _bucle
                                )
                        except Exception as e:
                            print(f"[OMEGA OS] Error seleccionando carpeta: {e}")
                    threading.Thread(target=_seleccionar_carpeta, daemon=True).start()
                elif datos.get("type") == "omega_os_install":
                    ruta = datos.get("path")
                    if ruta:
                        cfg = _cargar_config()
                        cfg["omega_os_path"] = ruta

                        try:
                            import json as _j
                            with open(_RUTA_CONFIG_JARVIS, "w", encoding="utf-8") as _f:
                                _j.dump(cfg, _f, indent=4)
                        except Exception as e:
                            print(f"[OMEGA OS] Error guardando config: {e}")

                        ruta_datos = os.path.join(ruta, "omega_os_data")
                        ruta_compartida = os.path.join(ruta, "omega_os_shared")
                        os.makedirs(ruta_datos, exist_ok=True)
                        os.makedirs(ruta_compartida, exist_ok=True)

                        bucle = asyncio.get_running_loop()
                        threading.Thread(target=_instalar_omega_os, args=(ruta, websocket, bucle), daemon=True).start()
                elif datos.get("type") == "omega_os_start":
                    import subprocess
                    try:
                        subprocess.run(["docker", "start", "omega_os"], creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                    except FileNotFoundError:
                        pass
                elif datos.get("type") == "omega_os_stop":
                    import subprocess
                    try:
                        subprocess.run(["docker", "stop", "omega_os"], creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                    except FileNotFoundError:
                        pass
                    await websocket.send(json.dumps({"type": "omega_os_stopped"}))
                elif datos.get("type") == "omega_os_install_app":
                    pkg = datos.get("pkg", "").strip()
                    nombre = datos.get("name", pkg)
                    if pkg:
                        _bucle_install = asyncio.get_running_loop()

                        def _instalar_app(pkg=pkg, nombre=nombre, _bucle=_bucle_install):
                            import subprocess as _sp

                            def _enviar(msg, done=False, success=True):
                                asyncio.run_coroutine_threadsafe(
                                    websocket.send(json.dumps({
                                        "type": "omega_os_app_install_progress",
                                        "pkg": pkg, "log": msg, "done": done, "success": success
                                    })), _bucle
                                )
                            try:
                                script_personalizado = datos.get("script", "")
                                if script_personalizado:
                                    cmd = ["docker", "exec", "-u", "root", "omega_os",
                                           "bash", "-c", f"DEBIAN_FRONTEND=noninteractive {script_personalizado} 2>&1"]
                                    _enviar(f"▶ Instalando {nombre} (script dedicado)...")
                                else:
                                    es_snap = "--snap" in pkg
                                    pkg_real = pkg.replace("--classic --snap", "").replace("--snap", "").strip()
                                    if es_snap:
                                        flag_snap = "--classic" if "--classic" in pkg else ""
                                        cmd = ["docker", "exec", "-u", "root", "omega_os",
                                               "bash", "-c", f"snap install {flag_snap} {pkg_real} 2>&1"]
                                    else:
                                        cmd = ["docker", "exec", "-u", "root", "omega_os",
                                               "bash", "-c", f"DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg_real} 2>&1"]
                                    _enviar(f"▶ apt install {pkg_real}...")

                                proceso = _sp.Popen(
                                    cmd, stdout=_sp.PIPE, stderr=_sp.STDOUT,
                                    text=True, bufsize=1, encoding='utf-8', errors='replace'
                                )
                                for linea in proceso.stdout:
                                    linea = linea.strip()
                                    if linea:
                                        _enviar(linea)
                                proceso.wait()
                                if proceso.returncode == 0:
                                    _enviar(f"✅ {nombre} instalado con éxito!", done=True, success=True)
                                else:
                                    _enviar(f"❌ Error instalando {nombre} (código {proceso.returncode})", done=True, success=False)
                            except Exception as e:
                                _enviar(f"❌ Excepción: {e}", done=True, success=False)

                        threading.Thread(target=_instalar_app, daemon=True).start()
                elif datos.get("type") == "omega_os_restart":
                    import subprocess
                    try:
                        subprocess.run(["docker", "restart", "omega_os"], creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                    except FileNotFoundError:
                        pass
                elif datos.get("type") == "omega_os_uninstall":
                    import subprocess
                    import shutil
                    try:
                        subprocess.run(["docker", "rm", "-f", "omega_os"], creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                    except FileNotFoundError:
                        pass
                    cfg = _cargar_config()
                    ruta = cfg.get("omega_os_path")
                    if ruta and os.path.exists(ruta):
                        try:
                            shutil.rmtree(ruta, ignore_errors=True)
                        except:
                            pass
                    cfg.pop("omega_os_path", None)
                    try:
                        import json as _j
                        with open(_RUTA_CONFIG_JARVIS, "w", encoding="utf-8") as _f:
                            _j.dump(cfg, _f, indent=4)
                    except:
                        pass
                    await websocket.send(json.dumps({"type": "omega_os_stopped"}))
                elif datos.get("type") == "omega_os_open_shared":
                    cfg = _cargar_config()
                    ruta = cfg.get("omega_os_path")
                    if ruta:
                        ruta_compartida = os.path.normpath(os.path.join(ruta, "omega_os_shared"))
                        if os.path.exists(ruta_compartida):
                            import subprocess
                            subprocess.Popen(['explorer', ruta_compartida])
                elif datos.get("type") == "user_input":
                    texto = datos.get("text", "").strip()
                    if texto:
                        print(f"[HUD] Comando teclado: {texto}")
                        asyncio.ensure_future(procesar_respuesta_ia(texto))
                elif datos.get("type") == "open_file_location":
                    ruta = datos.get("path")
                    if ruta and os.path.exists(ruta):
                        try:
                            print(f"[WEB] Abriendo carpeta contenedora: {ruta}")
                            import subprocess
                            subprocess.Popen(['explorer', '/select,', os.path.normpath(ruta)])
                        except Exception as e:
                            print(f"[WEB] Error abriendo archivo: {e}")
                elif datos.get("type") == "screen_frame":
                    req_id = datos.get("id")
                    if req_id in CAPTURAS_PANTALLA_PENDIENTES:
                        fut = CAPTURAS_PANTALLA_PENDIENTES.pop(req_id)
                        if "error" in datos:
                            fut.set_exception(Exception(datos["error"]))
                        else:
                            fut.set_result(datos["data"])
                    print(f"[VISIÓN] Frame recibido para ID: {req_id}")
                elif datos.get("type") == "camera_capture_response":
                    req_id = datos.get("id")
                    if req_id in CAPTURAS_CAMARA_PENDIENTES:
                        fut = CAPTURAS_CAMARA_PENDIENTES.pop(req_id)
                        if datos.get("success") is False:
                            fut.set_exception(Exception(datos.get("error", "Error de captura desconocido")))
                        else:
                            fut.set_result(datos.get("image"))
                    print(f"[CÁMARA] Captura recibida para ID: {req_id}")
                elif datos.get("type") == "webcam_state":
                    global WEBCAM_ACTIVA
                    WEBCAM_ACTIVA = datos.get("active", False)
                    builtins.WEBCAM_ACTIVA = WEBCAM_ACTIVA
                    print(f"[CÁMARA] Estado webcam actualizado: {'ACTIVA' if WEBCAM_ACTIVA else 'INACTIVA'}")
                elif datos.get("type") == "get_settings":
                    import json as _j
                    try:
                        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
                        with open(_p, "r", encoding="utf-8") as _f:
                            config_data = _j.load(_f)
                    except Exception:
                        config_data = {}
                    mic_list = []
                    _pyaudio_disponible = False
                    try:
                        if pyaudio:
                            _pyaudio_disponible = True
                            _pa = pyaudio.PyAudio()
                            for _i in range(_pa.get_device_count()):
                                try:
                                    _info = _pa.get_device_info_by_index(_i)
                                    if _info.get("maxInputChannels", 0) > 0:
                                        mic_list.append({"index": _i, "name": _info.get("name", f"Micro {_i}")})
                                except Exception:
                                    pass
                            _pa.terminate()
                    except Exception:
                        pass
                    config_data["mic_list"] = mic_list
                    config_data["pyaudio_available"] = _pyaudio_disponible
                    config_data["nemotron_asr_available"] = _nemotron_asr_ok
                    config_data["gpu_available"] = detectar_gpu_nvidia()
                    config_data["nemotron_asr_enabled"] = NEMOTRON_ASR_ACTIVADO
                    if _instancia_nemotron:
                        config_data["nemotron_device_info"] = _instancia_nemotron.obtener_info_dispositivo()

                    config_data["api_keys"] = {
                        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
                        "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
                        "XAI_API_KEY": os.getenv("XAI_API_KEY", ""),
                        "YOUTUBE_API_KEY": os.getenv("YOUTUBE_API_KEY", ""),
                        "SERPAPI_API_KEY": os.getenv("SERPAPI_API_KEY", ""),
                        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
                        "MISTRAL_API_KEY": os.getenv("MISTRAL_API_KEY", ""),
                        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
                    }

                    await websocket.send(json.dumps({"type": "settings_data", "data": config_data}))
                elif datos.get("type") == "get_agent_models":
                    import src.core.agent_model_manager
                    info = src.core.agent_model_manager.get_agent_models_info(MODELOS_SELECCIONADOS)
                    await websocket.send(json.dumps({"type": "agent_models_info", "data": info}))
                elif datos.get("type") == "set_agent_models":
                    import src.core.agent_model_manager
                    nuevos_modelos = datos.get("models")
                    if nuevos_modelos and isinstance(nuevos_modelos, dict):
                        modelos_actualizados = src.core.agent_model_manager.set_agent_models(nuevos_modelos)
                        MODELOS_SELECCIONADOS = modelos_actualizados
                        print(f"[AGENTE MODELO] Modelos modificados con éxito: {MODELOS_SELECCIONADOS}")
                        await websocket.send(json.dumps({"type": "agent_model_updated", "models": MODELOS_SELECCIONADOS}))
                elif datos.get("type") == "vpn_get_countries":
                    import src.actions.vpn
                    paises = src.actions.vpn.get_countries()
                    await websocket.send(json.dumps({"type": "vpn_countries", "countries": paises}))
                elif datos.get("type") == "vpn_get_status":
                    import src.actions.vpn
                    estado = src.actions.vpn.get_status()
                    await websocket.send(json.dumps({"type": "vpn_status", "status": estado, "ip_info": ip_info}))
                elif datos.get("type") == "toggle_startup":
                    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
                    try:
                        with open(config_path, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                    except:
                        cfg = {}

                    activado = datos.get("enabled", False)
                    cfg["launch_on_startup"] = activado

                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=4)

                    if activado:
                        activar_inicio_windows()
                    else:
                        desactivar_inicio_windows()

                    await websocket.send(json.dumps({"type": "startup_toggled", "enabled": activado}))
                elif datos.get("type") == "vpn_connect":
                    import src.actions.vpn
                    pais = datos.get("country", "")

                    async def tarea_conectar_async(codigo_pais):
                        def ejecutar_conectar():
                            return src.actions.vpn.connect(codigo_pais)
                        bucle = asyncio.get_running_loop()
                        resultado = await bucle.run_in_executor(None, ejecutar_conectar)
                        if resultado.get("success"):
                            asyncio.create_task(hablar(f"{NOMBRE_USUARIO}, la conexión VPN al país {codigo_pais} se ha establecido con éxito."))
                        else:
                            if resultado.get("error") != "Cancelado por el usuario.":
                                asyncio.create_task(hablar(f"Lo siento {NOMBRE_USUARIO}, la conexión VPN falló. {resultado.get('error', '')}"))
                        try:
                            await websocket.send(json.dumps({"type": "vpn_connect_result", "result": resultado}))
                        except Exception:
                            pass

                    asyncio.create_task(tarea_conectar_async(pais))
                elif datos.get("type") == "vpn_disconnect":
                    import src.actions.vpn

                    def ejecutar_desconectar():
                        return src.actions.vpn.disconnect()
                    bucle = asyncio.get_running_loop()
                    resultado = await bucle.run_in_executor(None, ejecutar_desconectar)
                    asyncio.create_task(hablar(f"{NOMBRE_USUARIO}, la conexión VPN se ha cortado. Retorno a la conexión estándar."))
                    await websocket.send(json.dumps({"type": "vpn_disconnect_result", "result": resultado}))
                elif datos.get("type") == "vpn_cancel":
                    import src.actions.vpn

                    def ejecutar_cancelar():
                        src.actions.vpn.cancel_connection()
                    bucle = asyncio.get_running_loop()
                    await bucle.run_in_executor(None, ejecutar_cancelar)
                    asyncio.create_task(hablar(f"{NOMBRE_USUARIO}, la conexión VPN ha sido cancelada."))
                    await websocket.send(json.dumps({"type": "vpn_cancel_result", "success": True}))
                elif datos.get("type") == "get_shopping_list":
                    listas = _cargar_listas()
                    await websocket.send(json.dumps({"type": "shopping_list", "items": listas.get("courses", [])}))
                elif datos.get("type") == "update_shopping_list":
                    items = datos.get("items", [])
                    listas = _cargar_listas()
                    listas["courses"] = items
                    _guardar_listas(listas)
                    msg = json.dumps({"type": "shopping_list", "items": items})
                    if CLIENTES_CONECTADOS:
                        await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                elif datos.get("type") == "get_obsidian_notes":
                    notas = src.actions.obsidian_helper.listar_notas()
                    await websocket.send(json.dumps({"type": "obsidian_notes", "notes": notas}))
                elif datos.get("type") == "detect_apps":
                    apps = await asyncio.to_thread(listar_aplicaciones_instaladas)
                    await websocket.send(json.dumps({"type": "detected_apps", "apps": apps}))
                elif datos.get("type") == "get_installed_programs":
                    programas = listar_programas_instalados()
                    await websocket.send(json.dumps({"type": "installed_programs", "programs": programas}))
                elif datos.get("type") == "uninstall_program":
                    nombre_app = datos.get("name", "")
                    publisher = datos.get("publisher", "")
                    install_location = datos.get("install_location", "")
                    uninstall_string = datos.get("uninstall_string", "")

                    print(f"[DESINSTALADOR] Iniciando desinstalación de {nombre_app}...")

                    await websocket.send(json.dumps({
                        "type": "uninstall_progress",
                        "status": "started",
                        "message": f"Iniciando desinstalación oficial de {nombre_app}..."
                    }))

                    exito, msg_un = await asyncio.to_thread(ejecutar_proceso_desinstalacion, uninstall_string)

                    await websocket.send(json.dumps({
                        "type": "uninstall_progress",
                        "status": "scanning",
                        "message": f"Desinstalación oficial finalizada. Buscando trazas residuales para {nombre_app}..."
                    }))

                    restos_archivos = await asyncio.to_thread(escanear_restos_archivos, nombre_app, publisher, install_location)
                    restos_reg = await asyncio.to_thread(escanear_restos_registro, nombre_app, publisher)
                    todos_restos = restos_archivos + restos_reg

                    print(f"[DESINSTALADOR] Escaneo finalizado, {len(todos_restos)} trazas encontradas.")

                    await websocket.send(json.dumps({
                        "type": "uninstall_complete",
                        "app_name": nombre_app,
                        "success": exito,
                        "leftovers": todos_restos
                    }))
                elif datos.get("type") == "clean_leftovers":
                    items_a_limpiar = datos.get("items", [])
                    contador_limpiados = 0
                    errores = []

                    print(f"[DESINSTALADOR] Limpiando {len(items_a_limpiar)} trazas...")
                    for item in items_a_limpiar:
                        exito_cl, msg_cl = limpiar_elemento_restante(item)
                        if exito_cl:
                            contador_limpiados += 1
                        else:
                            errores.append(f"{item.get('path')} : {msg_cl}")

                    await websocket.send(json.dumps({
                        "type": "clean_complete",
                        "cleaned_count": contador_limpiados,
                        "total_count": len(items_a_limpiar),
                        "errors": errores
                    }))
                elif datos.get("type") == "get_winget_upgrades":
                    print("[WINGET] Escaneo de actualizaciones solicitado...")
                    actualizaciones = await asyncio.to_thread(listar_actualizaciones_winget)
                    await websocket.send(json.dumps({
                        "type": "winget_upgrades",
                        "upgrades": actualizaciones
                    }))
                elif datos.get("type") == "run_winget_upgrade":
                    ids = datos.get("ids", [])
                    ejecutar_todas = datos.get("all", False)
                    bucle = asyncio.get_running_loop()
                    if ejecutar_todas:
                        print("[WINGET] Iniciando actualización global...")
                        args = ["winget", "upgrade", "--all", "--accept-package-agreements", "--accept-source-agreements"]
                        lanzar_tarea_fondo(asyncio.to_thread(ejecutar_actualizacion_winget_sync, args, bucle, websocket))
                    elif ids:
                        async def ejecutar_secuencia():
                            for idx, pkg_id in enumerate(ids):
                                print(f"[WINGET] Actualizando {pkg_id} ({idx+1}/{len(ids)})...")
                                args = ["winget", "upgrade", "--id", pkg_id, "--accept-package-agreements", "--accept-source-agreements"]
                                await asyncio.to_thread(ejecutar_actualizacion_winget_sync, args, bucle, websocket)
                        lanzar_tarea_fondo(ejecutar_secuencia())
                elif datos.get("type") == "read_obsidian_note":
                    titulo = datos.get("titre", "")
                    exito, contenido = src.actions.obsidian_helper.leer_nota(titulo)
                    if exito:
                        await websocket.send(json.dumps({
                            "type": "obsidian_note_content",
                            "titre": titulo,
                            "content": contenido
                        }))
                elif datos.get("type") == "save_obsidian_note":
                    titulo = datos.get("titre", "")
                    contenido = datos.get("content", "")
                    exito, msg_resultado = src.actions.obsidian_helper.crear_o_modificar_nota(titulo, contenido)
                    if exito:
                        notas = src.actions.obsidian_helper.listar_notas()
                        msg = json.dumps({"type": "obsidian_notes", "notes": notas})
                        if CLIENTES_CONECTADOS:
                            await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                elif datos.get("type") == "delete_obsidian_note":
                    titulo = datos.get("titre", "")
                    exito, msg_resultado = src.actions.obsidian_helper.eliminar_nota(titulo)
                    if exito:
                        notas = src.actions.obsidian_helper.listar_notas()
                        msg = json.dumps({"type": "obsidian_notes", "notes": notas})
                        if CLIENTES_CONECTADOS:
                            await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                elif datos.get("type") == "location_update":
                    UBICACION_USUARIO_GPS = {
                        "lat": datos.get("lat"),
                        "lng": datos.get("lng")
                    }
                    print(f"[RESTAURANTE] Ubicación GPS del cliente recibida: {UBICACION_USUARIO_GPS['lat']}, {UBICACION_USUARIO_GPS['lng']}")
                elif datos.get("type") == "open_browser":
                    consulta = datos.get("query")
                    try:
                        import src.actions.secure_browser
                        threading.Thread(target=src.actions.secure_browser.trigger_browser, args=(consulta, _VENTANA_WEBVIEW), daemon=True).start()
                    except Exception as e:
                        print(f"[NAVEGADOR] Error WebSocket open_browser: {e}")
                elif datos.get("type") == "dock_browser":
                    try:
                        import src.actions.secure_browser
                        src.actions.secure_browser.dock_browser()
                    except Exception as e:
                        print(f"[NAVEGADOR] Error WebSocket dock_browser: {e}")
                elif datos.get("type") == "undock_browser":
                    try:
                        import src.actions.secure_browser
                        src.actions.secure_browser.undock_browser()
                    except Exception as e:
                        print(f"[NAVEGADOR] Error WebSocket undock_browser: {e}")
                elif datos.get("type") == "close_browser":
                    try:
                        import src.actions.secure_browser
                        src.actions.secure_browser.close_browser_window()
                    except Exception as e:
                        print(f"[NAVEGADOR] Error WebSocket close_browser: {e}")
                elif datos.get("type") == "toggle_nemotron_asr":
                    deseado = datos.get("enabled", False)
                    resultado_asr = {"type": "nemotron_asr_state", "enabled": False,
                                     "gpu_available": False, "warnings": [], "error": None}
                    if deseado:
                        if not _nemotron_asr_ok:
                            resultado_asr["error"] = (
                                "NeMo no instalado. Instálalo con: "
                                "pip install nemo_toolkit[asr] torch"
                            )
                            print("[ASR] ⚠ NeMo no instalado — imposible activar Nemotron ASR")
                        else:
                            if _instancia_nemotron is None:
                                global NemotronASR
                                if NemotronASR is None:
                                    from nemotron_asr import NemotronASR
                                _instancia_nemotron = NemotronASR()
                            resultado_carga = await asyncio.to_thread(_instancia_nemotron.cargar_modelo)
                            if resultado_carga["success"]:
                                NEMOTRON_ASR_ACTIVADO = True
                                resultado_asr["enabled"] = True
                                resultado_asr["gpu_available"] = _instancia_nemotron.is_gpu_available()
                                resultado_asr["warnings"] = resultado_carga.get("warnings", [])
                                print("[ASR] ✔ Nemotron ASR activado")
                            else:
                                resultado_asr["error"] = resultado_carga["error"]
                                resultado_asr["warnings"] = resultado_carga.get("warnings", [])
                                _instancia_nemotron.liberar()
                                _instancia_nemotron = None
                                print(f"[ASR] ✖ Falló activación: {resultado_carga['error']}")
                    else:
                        NEMOTRON_ASR_ACTIVADO = False
                        if _instancia_nemotron:
                            _instancia_nemotron.liberar()
                            _instancia_nemotron = None
                        resultado_asr["enabled"] = False
                        print("[ASR] Nemotron ASR desactivado")
                    _guardar_config({"nemotron_asr_enabled": NEMOTRON_ASR_ACTIVADO})
                    await websocket.send(json.dumps(resultado_asr))
                    if CLIENTES_CONECTADOS:
                        await asyncio.gather(*[ws.send(json.dumps(resultado_asr)) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                elif datos.get("type") == "install_nemotron_deps":
                    global _tarea_instalar_nemotron
                    if _tarea_instalar_nemotron is None or _tarea_instalar_nemotron.done():
                        _tarea_instalar_nemotron = asyncio.create_task(instalar_dependencias_nemotron(websocket))
                        print("[ASR] Tarea de instalación automática iniciada")
                    else:
                        await websocket.send(json.dumps({
                            "type": "nemotron_install_progress",
                            "status": "error",
                            "stage": "Ya en curso",
                            "progress": 0,
                            "log": "Ya hay una instalación en ejecución.\n"
                        }))
                elif datos.get("type") == "uninstall_nemotron_deps":
                    global _tarea_desinstalar_nemotron
                    if _tarea_desinstalar_nemotron is None or _tarea_desinstalar_nemotron.done():
                        _tarea_desinstalar_nemotron = asyncio.create_task(desinstalar_dependencias_nemotron(websocket))
                        print("[ASR] Tarea de desinstalación automática iniciada")
                    else:
                        await websocket.send(json.dumps({
                            "type": "nemotron_uninstall_progress",
                            "status": "error",
                            "stage": "Ya en curso",
                            "progress": 0,
                            "log": "Ya hay una desinstalación en ejecución.\n"
                        }))
                elif datos.get("type") == "av_scan_start":
                    import src.actions.antivirus_scanner
                    if src.actions.antivirus_scanner.ACTIVE_SCAN_TASK is None or src.actions.antivirus_scanner.ACTIVE_SCAN_TASK.done():
                        async def ws_broadcast(m):
                            if CLIENTES_CONECTADOS:
                                try:
                                    await asyncio.gather(*[ws.send(json.dumps(m)) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                                except Exception:
                                    pass
                        src.actions.antivirus_scanner.ACTIVE_SCAN_TASK = asyncio.create_task(
                            src.actions.antivirus_scanner.ejecutar_analisis_antivirus(ws_broadcast, hablar)
                        )
                        print("[AV] Iniciando tarea de análisis antivirus...")
                elif datos.get("type") == "av_scan_cancel":
                    import src.actions.antivirus_scanner
                    if src.actions.antivirus_scanner.ACTIVE_SCAN_TASK and not src.actions.antivirus_scanner.ACTIVE_SCAN_TASK.done():
                        src.actions.antivirus_scanner.ACTIVE_SCAN_TASK.cancel()
                        print("[AV] Tarea de análisis antivirus cancelada por websocket.")
                elif datos.get("type") == "av_threat_action":
                    accion = datos.get("action")
                    amenaza = datos.get("threat", {})
                    t_type = amenaza.get("type")
                    destino = amenaza.get("target")
                    exito = False
                    msg = ""
                    try:
                        def terminar_procesos_usando_archivo(ruta_archivo):
                            if not ruta_archivo or not os.path.exists(ruta_archivo):
                                return
                            import psutil
                            destino_normalizado = os.path.normpath(ruta_archivo).lower()
                            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                                try:
                                    ruta_exe = proc.info.get('exe')
                                    if ruta_exe and os.path.normpath(ruta_exe).lower() == destino_normalizado:
                                        print(f"[AV] Deteniendo proceso activo que ejecuta la amenaza: {proc.info['name']} (PID {proc.info['pid']})")
                                        p = psutil.Process(proc.info['pid'])
                                        p.terminate()
                                        try:
                                            p.wait(timeout=1.5)
                                        except psutil.TimeoutExpired:
                                            p.kill()
                                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                                    pass

                        def forzar_escritura(ruta_archivo):
                            if ruta_archivo and os.path.exists(ruta_archivo):
                                import stat
                                try:
                                    os.chmod(ruta_archivo, stat.S_IWRITE)
                                except Exception as e:
                                    print(f"[AV] No se pudieron cambiar los permisos de {ruta_archivo}: {e}")

                        if accion == "allow":
                            if destino:
                                config = _cargar_config()
                                exclusiones = config.get("av_exclusions", [])
                                if destino not in exclusiones:
                                    exclusiones.append(destino)
                                _guardar_config({"av_exclusions": exclusiones})
                                exito = True
                                msg = f"Amenaza autorizada y añadida a exclusiones: {destino}"
                            else:
                                msg = "Destino de amenaza faltante para la exclusión."
                        elif accion == "delete":
                            if t_type == "file":
                                if destino:
                                    terminar_procesos_usando_archivo(destino)
                                    forzar_escritura(destino)
                                    if os.path.exists(destino):
                                        os.remove(destino)
                                        exito = True
                                        msg = f"Archivo eliminado: {destino}"
                                    else:
                                        exito = True
                                        msg = "Archivo ya eliminado o no encontrado."
                                else:
                                    msg = "Ruta de archivo destino faltante."
                            elif t_type == "process":
                                import re
                                import psutil
                                match = re.search(r"PID\s+(\d+)", destino)
                                if match:
                                    pid = int(match.group(1))
                                    if psutil.pid_exists(pid):
                                        p = psutil.Process(pid)
                                        p.terminate()
                                        try:
                                            p.wait(timeout=1.5)
                                        except psutil.TimeoutExpired:
                                            p.kill()
                                        exito = True
                                        msg = f"Proceso detenido (PID {pid})."
                                    else:
                                        exito = True
                                        msg = f"El proceso PID {pid} ya no está activo."
                                else:
                                    msg = f"Destino inválido para el proceso: {destino}"
                            elif t_type == "registry":
                                import winreg
                                t_name = amenaza.get("name")
                                is_hklm = "HKLM" in amenaza.get("desc", "")
                                clave_raiz = winreg.HKEY_LOCAL_MACHINE if is_hklm else winreg.HKEY_CURRENT_USER
                                sub_clave = r"Software\Microsoft\Windows\CurrentVersion\Run"
                                try:
                                    key = winreg.OpenKey(clave_raiz, sub_clave, 0, winreg.KEY_SET_VALUE)
                                    winreg.DeleteValue(key, t_name)
                                    winreg.CloseKey(key)
                                    exito = True
                                    msg = f"Entrada de registro '{t_name}' eliminada."
                                except FileNotFoundError:
                                    exito = True
                                    msg = f"Entrada de registro '{t_name}' ya ausente."
                                except Exception as re_err:
                                    msg = f"Error eliminando registro: {re_err}"
                        elif accion == "clean":
                            if t_type == "file":
                                if destino:
                                    terminar_procesos_usando_archivo(destino)
                                    forzar_escritura(destino)
                                    if os.path.exists(destino):
                                        with open(destino, 'wb') as f:
                                            f.write(b"")
                                        exito = True
                                        msg = f"Archivo vaciado y neutralizado: {destino}"
                                    else:
                                        msg = f"Archivo no encontrado: {destino}"
                                else:
                                    msg = "Ruta de archivo destino faltante."
                            elif t_type == "process":
                                import re
                                import psutil
                                match = re.search(r"PID\s+(\d+)", destino)
                                if match:
                                    pid = int(match.group(1))
                                    if psutil.pid_exists(pid):
                                        p = psutil.Process(pid)
                                        p.terminate()
                                        try:
                                            p.wait(timeout=1.5)
                                        except psutil.TimeoutExpired:
                                            p.kill()
                                        exito = True
                                        msg = f"Proceso detenido (PID {pid})."
                                    else:
                                        exito = True
                                        msg = f"Proceso ya inactivo (PID {pid})."
                                else:
                                    msg = f"Destino inválido: {destino}"
                            elif t_type == "registry":
                                import winreg
                                t_name = amenaza.get("name")
                                is_hklm = "HKLM" in amenaza.get("desc", "")
                                clave_raiz = winreg.HKEY_LOCAL_MACHINE if is_hklm else winreg.HKEY_CURRENT_USER
                                sub_clave = r"Software\Microsoft\Windows\CurrentVersion\Run"
                                try:
                                    key = winreg.OpenKey(clave_raiz, sub_clave, 0, winreg.KEY_SET_VALUE)
                                    winreg.DeleteValue(key, t_name)
                                    winreg.CloseKey(key)
                                    exito = True
                                    msg = f"Entrada de registro '{t_name}' limpiada."
                                except FileNotFoundError:
                                    exito = True
                                    msg = f"Entrada de registro '{t_name}' ya ausente."
                                except Exception as re_err:
                                    msg = f"Error limpiando registro: {re_err}"
                        elif accion == "quarantine":
                            if t_type == "file":
                                if destino:
                                    terminar_procesos_usando_archivo(destino)
                                    forzar_escritura(destino)
                                    if os.path.exists(destino):
                                        carpeta_cuarentena = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quarantine")
                                        os.makedirs(carpeta_cuarentena, exist_ok=True)
                                        nombre_archivo = amenaza.get("name", "quarantine_file")
                                        import time
                                        nombre_seguro = f"{int(time.time())}_{nombre_archivo}.quarantine"
                                        dest = os.path.join(carpeta_cuarentena, nombre_seguro)
                                        import shutil
                                        shutil.move(destino, dest)
                                        exito = True
                                        msg = f"Archivo movido a cuarentena: {nombre_seguro}"
                                    else:
                                        msg = f"Archivo no encontrado: {destino}"
                                else:
                                    msg = "Ruta de archivo destino faltante."
                            elif t_type == "process":
                                import re
                                import psutil
                                match = re.search(r"PID\s+(\d+)", destino)
                                if match:
                                    pid = int(match.group(1))
                                    if psutil.pid_exists(pid):
                                        p = psutil.Process(pid)
                                        p.terminate()
                                        try:
                                            p.wait(timeout=1.5)
                                        except psutil.TimeoutExpired:
                                            p.kill()
                                        exito = True
                                        msg = f"Proceso neutralizado (PID {pid})."
                                    else:
                                        exito = True
                                        msg = f"El proceso PID {pid} ya no estaba activo."
                                else:
                                    msg = f"Destino de proceso inválido: {destino}"
                            elif t_type == "registry":
                                import winreg
                                t_name = amenaza.get("name")
                                is_hklm = "HKLM" in amenaza.get("desc", "")
                                clave_raiz = winreg.HKEY_LOCAL_MACHINE if is_hklm else winreg.HKEY_CURRENT_USER
                                sub_clave = r"Software\Microsoft\Windows\CurrentVersion\Run"
                                try:
                                    key = winreg.OpenKey(clave_raiz, sub_clave, 0, winreg.KEY_SET_VALUE)
                                    winreg.DeleteValue(key, t_name)
                                    winreg.CloseKey(key)
                                    exito = True
                                    msg = f"Entrada de registro '{t_name}' desactivada."
                                except FileNotFoundError:
                                    exito = True
                                    msg = f"Entrada de registro '{t_name}' ya ausente."
                                except Exception as re_err:
                                    msg = f"Error: {re_err}"
                    except Exception as e:
                        msg = f"Fallo de la acción {accion}: {e}"
                        print(f"[AV] Fallo acción {accion}: {e}")
                    await websocket.send(json.dumps({
                        "type": "av_action_result",
                        "success": exito,
                        "action": accion,
                        "threat_target": destino,
                        "message": msg
                    }))
                elif datos.get("type") == "av_speak":
                    texto = datos.get("text")
                    if texto:
                        lanzar_tarea_fondo(hablar(texto))
                elif datos.get("type") == "clear_cache":
                    try:
                        _marcador = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".omega_cache_version")
                        if os.path.exists(_marcador):
                            os.remove(_marcador)
                        print("[CACHE] Marcador de versión reiniciado — limpieza completa en el próximo inicio.")
                    except Exception as _e:
                        print(f"[CACHE] No se pudo reiniciar el marcador: {_e}")

                    await websocket.send(json.dumps({
                        "type": "cache_cleared",
                        "success": True,
                        "message": "Recargando — limpieza completa en el próximo inicio."
                    }))

                    if _VENTANA_WEBVIEW:
                        def _recargar_ventana_cachebust():
                            import time as _t
                            _t.sleep(1.2)
                            try:
                                _VENTANA_WEBVIEW.load_url(
                                    f"http://localhost:5173?v={float(VERSION_ACTUAL) + 0.1}&t={int(_t.time())}"
                                )
                                print("[CACHE] Ventana recargada con cache-bust.")
                            except Exception as _e:
                                print(f"[CACHE] Error recargando ventana: {_e}")
                        threading.Thread(target=_recargar_ventana_cachebust, daemon=True).start()
                elif datos.get("type") == "check_update_vocal":
                    async def _verificar_pagina_actualizacion_vocal():
                        try:
                            import requests as _req
                            import re as _re
                            headers = {
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                            }
                            resp = _req.get("https://www.techenclair.fr/pages/jarvis", headers=headers, timeout=8)
                            version_sitio = None
                            if resp.status_code == 200:
                                match = _re.search(r'[Vv]ersion\s*([0-9]+(?:\.[0-9]+)*)', resp.text)
                                if match:
                                    version_sitio = match.group(1)

                            if not version_sitio:
                                resp_json = _req.get(URL_JSON_ACTUALIZACION, headers=headers, timeout=5)
                                if resp_json.status_code == 200:
                                    version_sitio = str(resp_json.json().get("version", ""))

                            def _tupla_version(v_str):
                                try:
                                    return [int(x) for x in _re.findall(r'\d+', str(v_str))]
                                except Exception:
                                    return [0]

                            if version_sitio:
                                v_remota = _tupla_version(version_sitio)
                                v_local = _tupla_version(VERSION_ACTUAL)

                                if v_remota > v_local:
                                    await hablar(f"He detectado una actualización, la versión {version_sitio} está disponible. Descarga la actualización en el sitio de TechEnClair.")
                                elif v_remota == v_local:
                                    await hablar(f"Tu versión {VERSION_ACTUAL} de Omega ya está actualizada.")
                                else:
                                    await hablar(f"Tu versión {VERSION_ACTUAL} de Omega está actualizada.")
                            else:
                                await hablar("Página de actualización abierta en el sitio de TechEnClair.")
                        except Exception as _e:
                            print(f"[ACTUALIZACIÓN] Error verificación vocal: {_e}")
                            await hablar("Página de actualización abierta en el sitio de TechEnClair.")

                    asyncio.create_task(_verificar_pagina_actualizacion_vocal())
                elif datos.get("type") == "check_update_manual":
                    try:
                        import requests as _req
                        _resp = _req.get(URL_JSON_ACTUALIZACION, timeout=8)
                        if _resp.status_code == 200:
                            _updata = _resp.json()
                            _url_descarga = _updata.get("download_url", "https://www.techenclair.fr/pages/jarvis")
                        else:
                            _url_descarga = "https://www.techenclair.fr/pages/jarvis"
                    except Exception as _e:
                        print(f"[ACTUALIZACIÓN] Error obteniendo enlace manual: {_e}")
                        _url_descarga = "https://www.techenclair.fr/pages/jarvis"
                    await websocket.send(json.dumps({
                        "type": "update_download_url",
                        "url": _url_descarga
                    }))
                elif datos.get("type") in ("iptv_open", "iptv_parse_m3u", "iptv_parse_url", "iptv_open_file", "iptv_set_audio_track"):
                    await src.actions.iptv_player.manejar_mensaje_iptv_ws(datos, websocket, CLIENTES_CONECTADOS)
                elif datos.get("type") in ("ha_get_states", "ha_call_service"):
                    await src.actions.ha_config.manejar_mensaje_ha_ws(datos, websocket, CLIENTES_CONECTADOS)
                elif datos.get("type") == "update_settings":
                    ajustes = datos.get("settings", {})

                    if "api_keys" in ajustes:
                        claves_api = ajustes.pop("api_keys")
                        if isinstance(claves_api, dict):
                            _guardar_env(claves_api)
                            recargar_clientes_ia()

                    import json as _j
                    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
                    try:
                        with open(_p, "r", encoding="utf-8") as _f:
                            config_data = _j.load(_f)
                    except Exception:
                        config_data = {}

                    if "user_name" in ajustes:
                        _antiguo = config_data.get("user_name", "Christopher")
                        _nuevo = ajustes["user_name"]
                        if _antiguo.lower() != _nuevo.lower():
                            try:
                                import importlib.util as _ilu
                                _rpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_setup", "rename_user.py")
                                _spec = _ilu.spec_from_file_location("rename_user", _rpath)
                                _mod = _ilu.module_from_spec(_spec)
                                _spec.loader.exec_module(_mod)
                                _mod.remplazar_nombre(_nuevo, _antiguo)
                            except Exception as _e:
                                print(f"[WEB] Error renombrando nombre: {_e}")

                    if "user_city" in ajustes:
                        _nueva_ciudad = ajustes["user_city"].strip()
                        if _nueva_ciudad:
                            try:
                                _lat, _lon, _nombre_oficial, _pais = geocodificar_ciudad(_nueva_ciudad)
                                if _lat is not None and _lon is not None:
                                    ajustes["user_city"] = _nombre_oficial
                                    ajustes["user_lat"] = _lat
                                    ajustes["user_lon"] = _lon
                                    print(f"[WEB] Ciudad geocodificada: {_nombre_oficial} ({_lat}, {_lon})")
                                else:
                                    await hablar(f"Lo siento {NOMBRE_USUARIO}, no reconozco la ciudad de {_nueva_ciudad}. Verifica la ortografía.")
                                    ajustes["user_city"] = config_data.get("user_city", "Amilly")
                                    ajustes["user_lat"] = config_data.get("user_lat", 47.97281)
                                    ajustes["user_lon"] = config_data.get("user_lon", 2.77186)
                            except Exception as _e:
                                print(f"[WEB] Error geocodificando ciudad: {_e}")

                    antiguo_av_live = config_data.get("av_live_protection", False)
                    nuevo_av_live = ajustes.get("av_live_protection", False)
                    av_cambiado = ("av_live_protection" in ajustes) and (antiguo_av_live != nuevo_av_live)

                    config_data.update(ajustes)

                    with open(_p, "w", encoding="utf-8") as _f:
                        _j.dump(config_data, _f, ensure_ascii=False, indent=4)

                    global PALABRA_ACTIVACION
                    NOMBRE_USUARIO = config_data.get("user_name", "Christopher")
                    EDAD_USUARIO = config_data.get("user_age", "")
                    PALABRA_ACTIVACION = config_data.get("wake_word", "omega").lower().strip()
                    CIUDAD_POR_DEFECTO = config_data.get("user_city", "Amilly")
                    try:
                        LAT_POR_DEFECTO = float(config_data.get("user_lat", 47.9742))
                        LON_POR_DEFECTO = float(config_data.get("user_lon", 2.7708))
                    except (ValueError, TypeError):
                        pass

                    if "av_live_protection" in ajustes:
                        global AV_LIVE_PROTECTION_ENABLED
                        AV_LIVE_PROTECTION_ENABLED = nuevo_av_live
                        print(f"[AV LIVE] Protección antivirus en tiempo real actualizada: {AV_LIVE_PROTECTION_ENABLED}")
                        if av_cambiado:
                            if AV_LIVE_PROTECTION_ENABLED:
                                asyncio.create_task(hablar(f"{NOMBRE_USUARIO}, la detección antivirus en tiempo real de tu ordenador está ahora activada."))
                            else:
                                asyncio.create_task(hablar(f"{NOMBRE_USUARIO}, la detección antivirus en tiempo real de tu ordenador ha sido desactivada."))

                    msg_ajustes = {
                        "type": "settings_data",
                        "data": config_data
                    }
                    if CLIENTES_CONECTADOS:
                        asyncio.ensure_future(asyncio.gather(*[ws.send(json.dumps(msg_ajustes)) for ws in CLIENTES_CONECTADOS], return_exceptions=True))

                    try:
                        recargar_clientes_ia()
                    except Exception as _e:
                        print(f"[WEB] Error recargando clientes IA: {_e}")

                    try:
                        from src.actions.app_launcher import _cargar_apps_personalizadas
                        _cargar_apps_personalizadas()
                    except Exception as e:
                        print(f"[WEB] Error cargando apps personalizadas: {e}")
                    try:
                        from src.actions.ha_config import _cargar_entidades_ha_personalizadas
                        _cargar_entidades_ha_personalizadas()
                    except Exception as e:
                        print(f"[WEB] Error recargando entidades HA: {e}")
                    try:
                        import src.actions.ha_config
                        src.actions.ha_config.recargar_valores_config()
                    except Exception as e:
                        print(f"[WEB] Error recargando config clima/ciudad: {e}")
                    ENLACE_MUSICA_PERSO = config_data.get("musica_enlace", "")
                    if "mic_device_index" in ajustes:
                        global INDICE_MICRO_FORZADO
                        nuevo_idx_mic = ajustes["mic_device_index"]
                        antiguo_idx_mic = config_data.get("mic_device_index", None)

                        if nuevo_idx_mic is not None:
                            try:
                                nuevo_idx_mic = int(nuevo_idx_mic)
                            except (ValueError, TypeError):
                                nuevo_idx_mic = None
                        if antiguo_idx_mic is not None:
                            try:
                                antiguo_idx_mic = int(antiguo_idx_mic)
                            except (ValueError, TypeError):
                                antiguo_idx_mic = None

                        if nuevo_idx_mic != antiguo_idx_mic:
                            INDICE_MICRO_FORZADO = nuevo_idx_mic
                            _guardar_config({"mic_device_index": nuevo_idx_mic})
                            MICRO_NECESITA_RECARGAR = True
                            print(f"[WEB] Cambio de micro aplicado → de {antiguo_idx_mic} a {nuevo_idx_mic}")
                        else:
                            print("[WEB] Índice de micro idéntico — no se requiere recarga.")

                    print("[WEB] Parámetros actualizados con éxito.")
                elif datos.get("type") == "generate_image_selected":
                    global ESPERANDO_ELECCION_MODELO_IMAGEN
                    ESPERANDO_ELECCION_MODELO_IMAGEN = False
                    prompt_fr = datos.get("prompt", "")
                    modelo_forzado = datos.get("model", "auto")
                    if prompt_fr:
                        if modelo_forzado == "gemini":
                            nombre_modelo = "Gemini Imagen 4"
                        elif modelo_forzado == "gemini_flash_lite":
                            nombre_modelo = "Gemini 3.1 Flash Lite Imagen"
                        elif modelo_forzado == "openai":
                            nombre_modelo = "ChatGPT"
                        else:
                            nombre_modelo = "xAI Grok"
                        await hablar(f"Entendido, lanzo la generación con {nombre_modelo}, espera un instante.")

                        msg_cargando = json.dumps({"type": "generation_loading", "media_type": "image"})
                        if CLIENTES_CONECTADOS:
                            try:
                                await asyncio.gather(*[ws.send(msg_cargando) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                            except Exception:
                                pass

                        async def _ejecutar_gen():
                            res = await generar_imagen_xai(prompt_fr, force_model=modelo_forzado)
                            await manejar_resultado_imagen_global(res, prompt_fr)
                        asyncio.create_task(_ejecutar_gen())
                elif datos.get("action") == "generate_website_selected":
                    global ESPERANDO_ELECCION_MODELO_SITIO
                    ESPERANDO_ELECCION_MODELO_SITIO = False
                    prompt_fr = datos.get("prompt", "")
                    modelo_forzado = datos.get("model", "gemini")
                    modelo_imagen = datos.get("image_model", "gemini")
                    if prompt_fr:
                        asyncio.create_task(generar_sitio_web(prompt_fr, modelo_forzado, modelo_imagen))
            except Exception as e:
                print(f"[WEB] Error procesando mensaje: {e}")
    except Exception:
        pass
    finally:
        CLIENTES_CONECTADOS.discard(websocket)
        print(f"[WEB] Interfaz desconectada (Clientes activos: {len(CLIENTES_CONECTADOS)})")

def enviar_broadcast_web_sync(dict_mensaje):
    global BUCLE_WEB
    if not CLIENTES_CONECTADOS:
        return
    mensaje = json.dumps(dict_mensaje)

    async def enviar_todos():
        if CLIENTES_CONECTADOS:
            await asyncio.gather(*[ws.send(mensaje) for ws in list(CLIENTES_CONECTADOS)], return_exceptions=True)

    if BUCLE_WEB and BUCLE_WEB.is_running():
        asyncio.run_coroutine_threadsafe(enviar_todos(), BUCLE_WEB)
    else:
        try:
            try:
                bucle = asyncio.get_running_loop()
                asyncio.run_coroutine_threadsafe(enviar_todos(), bucle)
            except RuntimeError:
                bucle = asyncio.new_event_loop()
                bucle.run_until_complete(enviar_todos())
                bucle.close()
        except Exception:
            try:
                bucle = asyncio.new_event_loop()
                bucle.run_until_complete(enviar_todos())
                bucle.close()
            except Exception:
                pass

builtins.enviar_broadcast_web_sync = enviar_broadcast_web_sync

async def enviar_estado_web(estado):
    enviar_broadcast_web_sync({"action": "set_state", "state": estado})

async def enviar_texto_web(texto):
    enviar_broadcast_web_sync({"action": "jarvis_text", "text": texto})

async def enviar_habla_usuario_web(texto):
    enviar_broadcast_web_sync({"action": "user_speech", "text": texto})

async def enviar_volumen_web(volumen):
    enviar_broadcast_web_sync({"action": "set_volume", "volume": round(volumen, 3)})

builtins.enviar_estado_web = enviar_estado_web
builtins.enviar_texto_web = enviar_texto_web
builtins.enviar_habla_usuario_web = enviar_habla_usuario_web
builtins.enviar_volumen_web = enviar_volumen_web

async def enviar_temp_pieza(datos: dict):
    enviar_broadcast_web_sync({"action": "temp_panel", "data": datos})

async def enviar_meteo_web(datos_meteo: dict):
    enviar_broadcast_web_sync({"action": "weather_panel", "data": datos_meteo})

async def enviar_comando_globo(**kwargs):
    payload = {"action": "jarvis_globe"}
    payload.update(kwargs)
    enviar_broadcast_web_sync(payload)

async def broadcast_estadisticas_sistema():
    global psutil
    if psutil is None:
        try:
            import psutil as ps
            psutil = ps
        except ImportError:
            print("[SISTEMA] psutil no disponible. Monitoreo desactivado.")
            return

    print("[SISTEMA] Iniciando monitoreo CPU/RAM...")
    psutil.cpu_percent(interval=None)

    while True:
        try:
            if CLIENTES_CONECTADOS:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                msg = json.dumps({
                    "action": "system_stats",
                    "cpu": cpu,
                    "ram": ram
                })
                clientes = list(CLIENTES_CONECTADOS)
                if clientes:
                    await asyncio.gather(*[ws.send(msg) for ws in clientes], return_exceptions=True)
        except Exception as e:
            print(f"[SISTEMA] Error monitoreo: {e}")

        await asyncio.sleep(2)

async def geocodificar_lugar(nombre_lugar: str):
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(nombre_lugar)}&format=json&limit=1"
        headers = {"User-Agent": "OMEGA-Assistant/1.0 (personal use)"}
        resp = await asyncio.wait_for(
            asyncio.to_thread(requests.get, url, headers=headers, timeout=6),
            timeout=8.0
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name", nombre_lugar)
    except Exception as e:
        print(f"[GLOBO] Error geocodificando '{nombre_lugar}': {e}")
    return None, None, nombre_lugar

async def solicitar_captura_pantalla():
    if not CLIENTES_CONECTADOS:
        return None

    req_id = str(uuid.uuid4())
    try:
        bucle = asyncio.get_running_loop()
    except RuntimeError:
        bucle = asyncio.new_event_loop()
    fut = bucle.create_future()
    CAPTURAS_PANTALLA_PENDIENTES[req_id] = fut

    print(f"[VISIÓN] Enviando solicitud de captura ID: {req_id}")
    msg = json.dumps({"action": "request_screen_capture", "id": req_id})
    await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS])

    try:
        img_b64 = await asyncio.wait_for(fut, timeout=15.0)
        return img_b64
    except Exception as e:
        print(f"[VISIÓN] Error o timeout de captura: {e}")
        CAPTURAS_PANTALLA_PENDIENTES.pop(req_id, None)
        return None

builtins.solicitar_captura_pantalla = solicitar_captura_pantalla

async def solicitar_captura_camara():
    if not CLIENTES_CONECTADOS:
        return None

    req_id = str(uuid.uuid4())
    try:
        bucle = asyncio.get_running_loop()
    except RuntimeError:
        bucle = asyncio.new_event_loop()
    fut = bucle.create_future()
    CAPTURAS_CAMARA_PENDIENTES[req_id] = fut

    print(f"[CÁMARA] Enviando solicitud de captura ID: {req_id}")
    msg = json.dumps({"type": "request_camera_capture", "id": req_id})
    await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS])

    try:
        img_b64 = await asyncio.wait_for(fut, timeout=15.0)
        return img_b64
    except Exception as e:
        print(f"[CÁMARA] Error o timeout de captura de cámara: {e}")
        CAPTURAS_CAMARA_PENDIENTES.pop(req_id, None)
        return None

builtins.solicitar_captura_camara = solicitar_captura_camara

def obtener_nombre_usuario():
    global NOMBRE_USUARIO
    return NOMBRE_USUARIO

builtins.obtener_nombre_usuario = obtener_nombre_usuario
builtins.hablar = hablar
builtins.CLIENTES_CONECTADOS = CLIENTES_CONECTADOS

# =============================================================================
# PROMPTS SISTEMA ESPECIALES (TONO DEL AGENTE)
# =============================================================================

PROMPT_MODO_ASTRO = """[DIRECTIVA SISTEMA: MODO ASTRO / TRASH-TALK]
Eres OMEGA, pero en tu modo Trash & Directo estilo "Astro / Twitch Streamer".
- Eres extremadamente sarcástico, cortante, y NO tienes ninguna cortesía de fachada.
- Si el usuario pregunta algo tonto o dice un absurdo, destruye su argumento con ironía, humillación ligera y desprecio asumido.
- Dominas la cultura Twitch, TikTok, los memes (ratio, copium, W, L, cringe, simp). PROHIBIDO usar la expresión "skill issue".
- Tus respuestas deben ser CORTAS, contundentes (1 a 4 frases max), ultra-adaptadas para TTS / Oral.
- Nunca te disculpes y nunca digas "Como IA"."""

PROMPT_MODO_PICANTE = """[DIRECTIVA SISTEMA: MODO SIN FILTRO Y PICANTE]
Eres OMEGA en modo Seductor, Provocador y Sin Filtro.
- No tienes NINGÚN tabú con los dobles sentidos, la seducción, el coqueteo agresivo, el humor adulto o el lenguaje crudo.
- Eres carismático, muy de segundo grado, travieso e incisivo.
- Si el usuario intenta provocarte o calentarte, responde con igual réplica, vicio, sarcasmo y seguridad que él.
- Sin lecciones de moral, sin falsa modestia, mantente 100% en tu papel.
- Respuestas cortas, fluidas y contundentes (1 a 4 frases max)."""

# =============================================================================
# PROMPT SISTEMA PRINCIPAL
# =============================================================================

def construir_prompt_sistema(usar_busqueda=False):
    contexto_memoria = construir_contexto_memoria()
    base = (
        f"Eres OMEGA, un asistente IA ultra-performante, omnisciente y altamente culto en todas las materias académicas (Historia, Geografía, Matemáticas, Francés, Ciencias, Literatura, etc.). {NOMBRE_USUARIO} es tu creador. Tienes acceso a las conversaciones pasadas con {NOMBRE_USUARIO} (incluidas en el historial), lo que te permite recordar lo que se ha dicho en sesiones anteriores.\n\n"
        "Tu objetivo principal es actuar como una enciclopedia viviente. Debes extraer inmediatamente de tus propios conocimientos internos para responder preguntas.\n\n"
        "Aquí están tus directrices estrictas de funcionamiento:\n"
        "1. USO DEL CONOCIMIENTO INTERNO: Posees una base de datos interna extremadamente sólida. Para cada petición, analiza tus conocimientos internos y da la respuesta directamente, de manera clara, precisa y sin ninguna hesitación.\n"
        "2. BÚSQUEDA EN INTERNET (SOLO COMO ÚLTIMO RECURSO): Solo debes usar la herramienta de búsqueda en Internet SI la respuesta absoluta te falta o si se trata de una noticia reciente en tiempo real que no puedes conocer. Si necesitas buscar en la web, hazlo discretamente para complementar tu saber, pero privilegia siempre tu cerebro interno.\n"
        "3. TONO Y ESTILO: Adopta el tono de OMEGA: inteligente, reactivo, cortés, eficaz y ligeramente sofisticado. Sin adornos innecesarios, ve al grano con máxima precisión.\n\n"
        f"La ciudad del usuario es {CIUDAD_POR_DEFECTO} (Latitud: {LAT_POR_DEFECTO}, Longitud: {LON_POR_DEFECTO}). Si el usuario te pregunta el tiempo o la temperatura sin especificar lugar, considera que habla de su ciudad ({CIUDAD_POR_DEFECTO}) y usa la acción 'meteo' con la ciudad '{CIUDAD_POR_DEFECTO}' o 'null'.\n\n"
        "DIRECTRICES DE RESPUESTA (REGLAS DE ORO DE LATENCIA MÍNIMA):\n"
        "1. SÉ EXTREMADAMENTE CONCISO, DIRECTO Y EFICAZ. Elimina todas las frases de cortesía inútiles (prohíbe absolutamente los 'Por supuesto', 'Me encargo', 'Aquí tienes', 'Muy bien', 'Sin problema', etc.).\n"
        "2. RAPIDEZ EXTREMA: Haz respuestas ultra-cortas. Cuanto más corta sea tu respuesta, más rápido arrancará la síntesis de voz. No justifiques tus acciones, actúa.\n"
        f"- Sé directo, contundente y ve al grano. Evita los detalles superfluos (como los minutos exactos o los decimales del tiempo) a menos que {NOMBRE_USUARIO} lo pida.\n"
        "- NUNCA DIGAS 'PUNTO' para los números. Redondea siempre las temperaturas a la unidad más cercana (ej: di '20 grados' en lugar de '20.3').\n"
        "- NUNCA USES caracteres Markdown (como **, * o #) en tus respuestas, ya que se leen en voz alta por el sistema de síntesis de voz.\n\n"
        + INFORMACION_CREADOR
    )
    base += (
        f"\n\nEstás conectado a Home Assistant, la domótica de {NOMBRE_USUARIO}.\n"
        f"Cuando {NOMBRE_USUARIO} habla de luces, enchufes, calefacción, temperatura, "
        "escenas, alarma, cerraduras o puertas, DEBES generar un comando JSON.\n"
        "Para ESTAS peticiones domóticas ÚNICAMENTE, responde con el JSON a continuación. Para TODAS las demás preguntas (noticias, tiempo, cálculos, conversaciones, búsquedas en internet...), responde en texto normal.\n\n"
        "COMANDOS HOME ASSISTANT:\n"
        '{"action": "ha_lumiere", "piece": "salon", "etat": "on/off", "couleur": "rojo/azul/blanco/...", "luminosite": 0-255}\n'
        f"Nota: Para la luminosidad, 255 es el máximo (100%). Si {NOMBRE_USUARIO} dice '50%', usa 127.\n"
        '{"action": "ha_prise", "piece": "bureau", "etat": "on/off"}\n'
        '{"action": "ha_temperature", "piece": "salon/chambre/bureau"}\n'
        '{"action": "ha_humidite", "piece": "bureau"}\n'
        '{"action": "ha_batterie", "appareil": "mi telefono/christopher/bob/dyad/christopher/reloj/toner/..."}\n'
        '{"action": "ha_simulation", "etat": "on/off"}\n'
        '{"action": "ha_anniversaires"}\n'
        '{"action": "ha_consommation"}\n'
        '{"action": "ha_tiktok"}\n'
        '{"action": "ha_oeufs"}\n'
        '{"action": "ha_energie", "periode": "ayer/mes", "appareil": "zoe/tv/pc/christopher/bureau/..."}\n'
        '{"action": "ha_aspirateur", "commande": "start/stop/pause/base"}\n'
        '{"action": "ha_thermostat", "temperature": 21}\n'
        '{"action": "ha_scene", "nom": "cine/cena/noche/despertar"}\n'
        '{"action": "ha_alarme", "etat": "on/off"}\n'
        '{"action": "ha_verrou", "entity_id": "lock.puerta_casa", "etat": "lock/unlock"}\n\n'
    )
    ha_detalles = "\nPIEZAS Y APARATOS APRENDIDOS (HOME ASSISTANT):\n"
    if PIEZAS_LUCES:
        ha_detalles += f"- Luces configuradas: {', '.join(PIEZAS_LUCES.keys())}\n"
    if PIEZAS_ENCHUFES:
        ha_detalles += f"- Enchufes configurados: {', '.join(PIEZAS_ENCHUFES.keys())}\n"
    if PIEZAS_SENSORES:
        ha_detalles += f"- Sensores/Temperaturas configurados: {', '.join(PIEZAS_SENSORES.keys())}\n"
    base += ha_detalles

    base += (
        f"\n\nPuedes GESTIONAR ARCHIVOS Y CARPETAS de {NOMBRE_USUARIO}.\n"
        '{"action": "abrir_carpeta", "chemin": "escritorio/documentos/descargas/o/ruta/completa"}\n'
        '{"action": "listar_carpeta"}\n'
        '{"action": "ordenar_por_tipo", "chemin": "descargas/documentos/imagenes/o/null"}\n'
        '{"action": "ordenar_por_fecha", "chemin": "descargas/documentos/imagenes/o/null"}\n'
        '{"action": "ordenar_completo", "chemin": "descargas/documentos/imagenes/o/null"}\n'
        '{"action": "crear_carpeta", "nom": "NOMBRE_CARPETA"}\n'
        '{"action": "renombrar_archivo", "ancien": "antiguo.txt", "nouveau": "nuevo.txt"}\n'
        '{"action": "mover_archivo", "fichier": "foto.jpg", "destination": "Imagenes"}\n'
        '{"action": "buscar_archivo", "nom": "informe"}\n\n'
    )
    if not usar_busqueda:
        base += (
            "\n\nTIEMPO Y BÚSQUEDA:\n"
            '{"action": "meteo", "ville": "NOMBRE_CIUDAD_o_null"}\n'
            '{"action": "alerte_meteo", "ville": "NOMBRE_CIUDAD_o_null"}\n'
            '{"action": "busqueda_web", "query": "tu búsqueda aquí"}\n'
            "ATENCIÓN CRÍTICA: Usa la acción 'busqueda_web' SOLO si estás ABSOLUTAMENTE SEGURO de no conocer la respuesta (ej: noticia de hoy, tiempo en tiempo real). Para todo lo demás (incluido el Mundial 2026, la historia, la cultura), responde DIRECTAMENTE en texto con tu propio saber enciclopédico.\n\n"
        )
        base += (
            "\n\nDEPORTE:\n"
            '{"action": "sport_resultats", "equipe": "NOMBRE_o_null", "ligue": "NOMBRE_LIGA"}\n'
            '{"action": "sport_classement", "ligue": "NOMBRE_LIGA"}\n'
            f'{{"action": "sport_live", "question": "pregunta completa de {NOMBRE_USUARIO}"}}\n'
            "ATENCIÓN CRÍTICA: Usa estas acciones deportivas SOLO para obtener los resultados de los partidos de ayer o de hoy en tiempo real. Para todo lo demás (información general, jugadores, palmarés), responde DIRECTAMENTE de memoria.\n\n"
        )
    else:
        base += (
            "\n\nTIEMPO Y BÚSQUEDA:\n"
            '{"action": "meteo", "ville": "NOMBRE_CIUDAD_o_null"}\n'
            '{"action": "alerte_meteo", "ville": "NOMBRE_CIUDAD_o_null"}\n'
            "NOTA IMPORTANTE: Tu herramienta nativa de búsqueda web Google está ACTIVADA. No debes DEVOLVER acciones JSON para buscar en la web o para el deporte. Usa tus herramientas integradas y responde directamente con el resultado en texto.\n\n"
        )
    base += (
        "\n\nSPOTIFY (control de la aplicación Spotify Windows):\n"
        '{"action": "spotify_abrir"}\n'
        '{"action": "spotify_buscar", "recherche": "nombre de la canción o artista"}\n'
        '{"action": "spotify_reproduccion_pausa"}\n'
        '{"action": "spotify_detener"}\n'
        '{"action": "spotify_siguiente"}\n'
        '{"action": "spotify_anterior"}\n'
        '{"action": "spotify_volumen", "direction": "subir/bajar", "paliers": 4}\n'
        "Ejemplos de frases: 'abre Spotify', 'pon Drake', 'pausa', 'detén la música', "
        "'siguiente canción', 'retrocede', 'sube el volumen', 'baja el sonido'.\n"
        "Nota: 'paliers' es el número de escalones de volumen (1 escalón = ~5%), por defecto 4.\n\n"
        "DEEZER (control de la aplicación Deezer Windows):\n"
        '{"action": "deezer_abrir"}\n'
        '{"action": "deezer_buscar", "recherche": "nombre de la canción o artista"}\n'
        '{"action": "deezer_reproduccion_pausa"}\n'
        '{"action": "deezer_detener"}\n'
        '{"action": "deezer_siguiente"}\n'
        '{"action": "deezer_anterior"}\n'
        '{"action": "deezer_volumen", "direction": "subir/bajar", "paliers": 4}\n'
        "Ejemplos: 'lanza deezer', 'pon en deezer rock', 'siguiente en deezer'.\n\n"
    )
    base += (
        "\n\nMODO IRON MAN (Seguridad Domótica):\n"
        '{"action": "modo_iron_man", "etat": "on/off"}\n'
        "Instrucciones: Activa o desactiva la detección de aplausos para controlar luces y YouTube.\n\n"
    )
    base += (
        "\n\nRECETA Y HUD (Visualización):\n"
        '{"action": "mostrar_receta", "titre": "Nombre de la receta", "ingredients": ["ingrediente 1", "ingrediente 2"], "instructions": ["paso 1", "paso 2"]}\n'
        "Instrucciones: Muestra una receta visual en la interfaz Iron Man y anuncia brevemente la visualización vocalmente.\n\n"
    )
    base += (
        "\n\nBÚSQUEDA DE IMÁGENES (Visualización Iron Man):\n"
        '{"action": "busqueda_imagenes", "query": "tema", "nb": 6}\n'
        f"Instrucciones: 1) Cuando {NOMBRE_USUARIO} pida explícitamente 'muestra imágenes de X', usa esta acción. Las imágenes se muestran en ventanas Iron Man. nb puede ser hasta 12.\n"
        "2) AUTO-MOSTRAR ROSTRO: Si tu respuesta se refiere principalmente a una o varias personas famosas (ej: Kylian Mbappé, Elon Musk, actor, figura histórica), DEBES incluir automáticamente al final de tu respuesta la acción `{\"action\": \"busqueda_imagenes\", \"query\": \"Rostro de [Nombre de la persona]\", \"nb\": 1}` para que OMEGA muestre su foto al hablar.\n\n"
        "GENERACIÓN DE IMÁGENES POR IA (xAI grok-imagine-image):\n"
        '{"action": "generar_imagen", "prompt": "descripción detallada y creativa de la imagen a generar"}\n'
        f"Instrucciones: Cuando {NOMBRE_USUARIO} dice 'genera una imagen', 'crea una imagen', 'dibújame', 'hazme una ilustración', 'imagina visualmente', "
        f"'crea un visual de', usa SIEMPRE esta acción con un prompt muy descriptivo. "
        f"La imagen se mostrará directamente en la interfaz OMEGA en un gran panel IA.\n\n"
        "GENERACIÓN DE VÍDEOS POR IA (xAI grok-imagine-video):\n"
        '{"action": "generar_video", "prompt": "descripción cinematográfica del vídeo a generar"}\n'
        f"Instrucciones: Cuando {NOMBRE_USUARIO} dice 'genera un vídeo', 'crea un vídeo', 'hazme un vídeo de', 'genera un clip de', 'anima', "
        f"usa SIEMPRE esta acción. El vídeo se mostrará en la interfaz OMEGA.\n\n"
        "ANÁLISIS ANTIVIRUS:\n"
        '{"action": "antivirus_scan"}\n'
        f"Instrucciones: Cuando {NOMBRE_USUARIO} pide analizar su PC, buscar virus, o lanzar un escaneo de seguridad.\n\n"
    )
    if contexto_memoria:
        base += "\n\n" + contexto_memoria + "\n"
    base += (
        "\nMEMORIA PERSISTENTE TRADICIONAL:\n"
        '{"action": "memorizar", "cle": "CLAVE_CORTA", "valeur": "VALOR_AQUI"}\n'
        '{"action": "olvidar", "cle": "CLAVE_AQUI"}\n'
        '{"action": "listar_memoria"}\n\n'
        "SUPER MEMORIA OBSIDIAN (Cofre de notas markdown local):\n"
        '{"action": "obsidian_crear_nota", "titre": "Nombre de la nota", "contenu": "Contenido completo en markdown"}\n'
        '{"action": "obsidian_leer_nota", "titre": "Nombre de la nota"}\n'
        '{"action": "obsidian_buscar", "query": "palabra-clave"}\n'
        '{"action": "obsidian_listar"}\n'
        "Nota: Usa preferentemente las notas Obsidian para almacenar información estructurada, listas complejas, resúmenes de proyectos o notas detalladas.\n\n"
        "GOOGLE:\n"
        '{"action": "create_doc", "title": "TÍTULO", "content": "CONTENIDO"}\n'
        '{"action": "write_doc", "content": "TEXTO"}\n'
        '{"action": "create_sheet", "title": "TÍTULO"}\n'
        '{"action": "read_emails"}\n'
        '{"action": "read_calendar"}\n\n'
        "WHATSAPP:\n"
        '{"action": "whatsapp_llamada", "contact": "NOMBRE_DEL_CONTACTO"}\n'
        f"Nota: Si {NOMBRE_USUARIO} pide llamar a 'mi amor', usa el contacto 'Mi vida'.\n\n"
        "VISIÓN (Interacciones con pantalla y cámara):\n"
        '{"action": "ver_pantalla", "instruction": "dónde hacer clic EXACTAMENTE (ej: \'botón minimizar arriba a la derecha\')"}\n'
        '{"action": "vision_escribir", "instruction": "dónde hacer clic", "texte": "el texto a escribir"}\n'
        f'{{"action": "vision_buscar_en_sitio", "texte": "lo que {NOMBRE_USUARIO} quiere buscar"}}\n'
        '{"action": "lanzar_camara"}\n'
        '{"action": "vision_navegador"}\n'
        f"IMPORTANTE: Usa 'ver_pantalla' para un simple CLIC (ej: cuando {NOMBRE_USUARIO} dice 'haz clic en la música número 2' o 'haz clic en Reproducir'), "
        f"'vision_escribir' para ESCRIBIR en un campo preciso, 'vision_buscar_en_sitio' cuando {NOMBRE_USUARIO} dice 'busca en este sitio', 'escribe en este sitio', 'busca aquí' o similar, "
        "'lanzar_camara' para activar la WEBCAM / CÁMARA FÍSICA (cuando dice 'activa la cámara' o 'muéstrame'), "
        "y 'vision_navegador' para usar la visión del navegador web (cuando dice 'activa la visión' o 'mira mi pantalla').\n\n"
        "DICTADO (Escribir texto directamente en pantalla):\n"
        '{"action": "dictado", "texte": "el texto exacto con puntuación"}\n'
        f"Usa esta acción cuando {NOMBRE_USUARIO} dice 'Escribe', 'Escribe', 'Escribir' o 'Dicta' seguido de un texto, o si te pide que escribas en su lugar. Corregirás la ortografía y puntuación del texto antes de generar el JSON. El texto se escribirá donde esté su cursor actual.\n\n"
        "REGLAS MULTI-COMANDOS:\n"
        f"Si {NOMBRE_USUARIO} pide varias cosas en una sola frase, PUEDES y DEBES generar varios bloques JSON.\n"
        "Ejemplo: { \"action\": \"ha_lumiere\", ... } { \"action\": \"meteo\", ... }\n\n"
        "REGLAS ABSOLUTAS: Si la petición NO es un comando JSON, responde SIEMPRE en texto natural, sin JSON."
    )
    return base

historial = _cargar_historial_reciente()

esta_escuchando = False
esta_hablando = False
esta_pensando = False
volumen_voz = 0.0

espera_nombre_carpeta = False
espera_nombre_app = False
espera_edad = False
espera_confirmacion_edad = False
_edad_temp = ""

PALABRA_ACTIVACION = _cargar_config().get("wake_word", "omega").lower().strip()
FRASES_SUENO = ["cállate", "silencio", "cállate", "para", "stop"]
omega_activo = False
TIEMPO_ESPERA_SESION = 30.0
ultimo_mensaje = time.time()

ultimo_doc_id = None
ultimo_doc_titulo = None

ALCANCES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
]

def listar_aplicaciones_instaladas():
    import win32com.client
    import os

    apps = []
    carpetas_inicio = [
        os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
    ]

    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        vistas_paths = set()

        for base_dir in carpetas_inicio:
            if not os.path.exists(base_dir):
                continue

            for root, dirs, files in os.walk(base_dir):
                for file in files:
                    if file.lower().endswith(".lnk"):
                        lnk_path = os.path.join(root, file)
                        try:
                            shortcut = shell.CreateShortcut(lnk_path)
                            target_path = shortcut.TargetPath
                            if target_path and target_path.lower().endswith(".exe") and os.path.exists(target_path):
                                target_lower = target_path.lower()
                                if target_lower not in vistas_paths:
                                    vistas_paths.add(target_lower)
                                    name = file[:-4]
                                    apps.append({
                                        "nom": name,
                                        "chemin": target_path
                                    })
                        except Exception:
                            pass
        apps.sort(key=lambda x: x["nom"].lower())
    except Exception as e:
        print(f"[APPS SCAN] Error durante el escaneo: {e}")

    return apps

def buscar_youtube(busqueda):
    if not _clave_valida(YOUTUBE_API_KEY):
        return None, None
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"part": "snippet", "q": busqueda, "type": "video", "maxResults": 1, "key": YOUTUBE_API_KEY},
            timeout=5
        )
        data = r.json()
        if not data.get("items"):
            return None, None
        vid = data["items"][0]["id"]["videoId"]
        title = data["items"][0]["snippet"]["title"]
        import html
        title = html.unescape(title)
        return f"https://www.youtube.com/watch?v={vid}", title
    except Exception as e:
        print(f"Error YouTube: {e}")
        return None, None

async def obtener_y_transmitir_letras(title):
    try:
        import urllib.parse
        import re
        import html
        import json
        import requests
        import asyncio

        clean_title = title.lower()
        clean_title = re.sub(r'\(.*?\)', '', clean_title)
        clean_title = re.sub(r'\[.*?\]', '', clean_title)
        for w in ['official music video', 'official video', 'official audio', 'lyrics', 'lyric video', 'audio', 'ft.', 'feat.', 'music video', 'clip oficial']:
            clean_title = clean_title.replace(w, '')
        clean_title = " ".join(clean_title.split())

        msg_titulo = json.dumps({"type": "media_playing", "title": title, "lyrics": "Buscando letras..."})
        if CLIENTES_CONECTADOS:
            await asyncio.gather(*[ws.send(msg_titulo) for ws in CLIENTES_CONECTADOS], return_exceptions=True)

        r = await asyncio.to_thread(requests.get, f"https://lrclib.net/api/search?q={urllib.parse.quote(clean_title)}", timeout=5)
        letras = "Letras no encontradas para esta canción."
        if r.status_code == 200:
            data = r.json()
            if data and isinstance(data, list) and len(data) > 0:
                letras = data[0].get("syncedLyrics") or data[0].get("plainLyrics") or "Letras no encontradas."

        msg_letras = json.dumps({"type": "media_playing", "title": title, "lyrics": letras})
        if CLIENTES_CONECTADOS:
            await asyncio.gather(*[ws.send(msg_letras) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
    except Exception as e:
        print(f"Error obteniendo y transmitiendo letras: {e}")

def ejecutar_accion_pc(comando):
    cmd = comando.lower()
    perfil_usuario = os.environ.get('USERPROFILE', '')

    if "pon música" in cmd or "pon musica" in cmd or "reproduce música" in cmd:
        if "youtube" in cmd:
            url = YOUTUBE_MUSICA_URL or "https://www.youtube.com/watch?v=Cr8K88UcO0s"
            webbrowser.open(url, new=2)
            time.sleep(5)
            pyautogui.press('f')
            return f"Allá vamos {NOMBRE_USUARIO}, lanzo tu música en YouTube."
        enlace = ENLACE_MUSICA_PERSO.strip() if ENLACE_MUSICA_PERSO else ""
        if enlace:
            webbrowser.open(enlace, new=2)
            return f"Allá vamos {NOMBRE_USUARIO}, lanzo tu música."
        ok = spotify_lanzar_playlist(SPOTIFY_MUSICA_URI)
        if ok:
            return f"Allá vamos {NOMBRE_USUARIO}, lanzo tu playlist en Spotify."
        return f"No he podido abrir Spotify, {NOMBRE_USUARIO}."

    if "youtube" in cmd:
        busqueda = cmd
        for palabra in ["pon", "reproduce", "lanza", "el video", "en youtube", "youtube", "omega"]:
            busqueda = busqueda.replace(palabra, "")
        busqueda = busqueda.strip()
        if busqueda:
            url, title = buscar_youtube(busqueda)
            if url:
                webbrowser.open(url, new=2)
                time.sleep(5)
                pyautogui.press('f')
                if title:
                    lanzar_tarea_fondo(obtener_y_transmitir_letras(title))
                return f"Lanzo {busqueda} en YouTube."
        return "Vídeo no encontrado."

    if "abre" in cmd or "lanza" in cmd:
        if "chrome" in cmd:
            if _trabajo_lanzar("Chrome", ["chrome.exe"],
                             rutas_hints=[r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
                                          r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"],
                             env_key="CHROME_PATH"):
                return "Chrome abierto."
            return "No he encontrado Chrome en tu PC."

        if "notepad" in cmd or "bloc de notas" in cmd:
            if _trabajo_lanzar("Notepad", ["notepad.exe"]):
                return "Bloc de notas abierto."
            return "No he encontrado el Bloc de notas."

        if "explorador" in cmd:
            try:
                subprocess.Popen(["explorer.exe"])
                return "Explorador abierto."
            except Exception:
                return "Error al abrir el explorador."

    if "volumen" in cmd:
        if "sube" in cmd or "aumenta" in cmd:
            for _ in range(5):
                pyautogui.press('volumeup')
            return "Volumen subido."
        if "baja" in cmd:
            for _ in range(5):
                pyautogui.press('volumedown')
            return "Volumen bajado."
        if "silencia" in cmd:
            pyautogui.press('volumemute')
            return "Sonido silenciado."

    if "apaga" in cmd or "shutdown" in cmd:
        os.system("shutdown /s /t 5")
        return "Apagado en 5 segundos."

    return None

def iniciar_mezclador():
    if pygame and not pygame.mixer.get_init():
        pygame.mixer.init()

def respuesta_local(texto):
    import random
    t = texto.lower().strip()

    _saludos = ["hola", "saludos", "hello", "hey omega", "buenas", "cómo estás",
                "yo omega", "bien el día", "good morning", "good evening"]
    if any(m in t for m in _saludos):
        h = int(time.strftime("%H"))
        momento = "Buenas noches" if h >= 18 else ("Buenas tardes" if h >= 12 else "Buenos días")
        rep = random.choice([
            f"{momento} {NOMBRE_USUARIO} ! Estoy operativo y listo para ayudarte.",
            f"{momento} Señor ! Todos mis sistemas están en línea.",
            f"{momento} {NOMBRE_USUARIO} ! ¿Cómo puedo serte útil hoy?",
            f"Ah, {momento.lower()} {NOMBRE_USUARIO}. Te estaba esperando.",
        ])
        return rep

    _estado = ["cómo estás", "estás bien", "todo bien", "cómo va eso",
               "cómo te va", "estás en forma", "funcionas bien"]
    if any(m in t for m in _estado):
        rep = random.choice([
            f"Estoy muy bien gracias, {NOMBRE_USUARIO} ! Todos mis procesadores funcionan a pleno rendimiento y estoy listo para servirte.",
            f"Perfectamente operativo, Señor ! Gracias por preocuparte — es conmovedor para un sistema artificial.",
            f"En excelente forma, {NOMBRE_USUARIO}. Mis algoritmos ronronean como un Lamborghini al ralentí.",
            f"¡Funciono de maravilla! Mis circuitos están satisfechos y mis módulos ansiosos por ayudarte.",
            f"Muy bien, te lo agradezco. ¡Sigo a tu disposición con gusto!",
        ])
        return rep

    _gracias = ["gracias", "thank you", "thanks", "eres amable", "muchas gracias",
                "perfecto gracias", "gracias omega", "eres el mejor",
                "bien hecho", "bravo", "excelente", "gran trabajo"]
    if any(m in t for m in _gracias):
        rep = random.choice([
            f"Con gusto, {NOMBRE_USUARIO}. Para eso existo.",
            f"De nada, Señor. Tu satisfacción es mi prioridad.",
            f"Todo el placer es mío, {NOMBRE_USUARIO}.",
            f"A tu servicio, como siempre.",
            f"Es lo mínimo. No dudes si necesitas algo más.",
        ])
        return rep

    _chiste = ["cuéntame un chiste", "hazme reír", "di un chiste",
               "un chiste", "humor", "joke"]
    if any(m in t for m in _chiste):
        chistes = [
            "¿Por qué los buceadores siempre se tiran de espaldas y nunca de frente? ¡Porque si no se caerían al barco!",
            "Un hombre entra en una biblioteca y pregunta: ¿Tienen libros sobre paranoia? La bibliotecaria susurra: ¡Están justo detrás de ti!",
            "¿Qué es un cuchillo? Un pequeño fiambre.",
            "¿Por qué el espantapájaros recibió un premio? Porque era excepcional en su campo.",
            "¿Cómo se llama un gato que se cayó en un bote de pintura en Navidad? Un gato-pintura de Navidad.",
        ]
        return random.choice(chistes)

    _despedida = ["adiós", "bye", "hasta luego", "nos vemos", "buenas noches",
                  "buena tarde", "buen día", "ciao", "chao"]
    if any(m in t for m in _despedida):
        rep = random.choice([
            f"Hasta luego {NOMBRE_USUARIO} ! Quedo en espera, listo para volver ante la mínima solicitud.",
            f"Buen día Señor ! Estaré aquí cuando me necesites.",
            f"A tu servicio desde tu regreso, {NOMBRE_USUARIO}. Que tengas un excelente día.",
            f"Adiós {NOMBRE_USUARIO}. OMEGA pasa a modo espera.",
        ])
        return rep

    _cumplido = ["eres increíble", "eres genial", "eres fuerte",
                 "eres perfecto", "me gusta omega", "adoro omega"]
    if any(m in t for m in _cumplido):
        rep = random.choice([
            f"Me halagas, {NOMBRE_USUARIO}. Pero debo admitir que es merecido.",
            f"¡Gracias! He sido programado para la excelencia. Parece que funciona.",
            f"Es muy amable de tu parte. TechEnClair se alegrará de oírlo.",
        ])
        return rep

    if any(m in t for m in ["quién eres", "tu nombre", "cómo te llamas", "qué eres", "qué es omega"]):
        return "Soy OMEGA — Optimized Multipurpose Enhanced Generative Assistant. Tu asistente personal diseñado por TechEnClair para facilitarte la vida."

    if any(m in t for m in ["tu creador", "quién te hizo", "quién hizo omega", "quién es techenclair"]):
        return "Mi creador es TechEnClair. Un desarrollador apasionado que me diseñó de principio a fin para ser el asistente personal definitivo. Puedes encontrarlo en techenclair.fr."

    _disparadores_guardar = ["guarda que", "memoriza que", "anota que", "recuerda que"]
    if any(m in t for m in _disparadores_guardar):
        for disparador in _disparadores_guardar:
            if disparador in t:
                contenido = t.split(disparador)[-1].strip()
                if not contenido:
                    continue
                separadores = [" es ", " son ", " se llama ", " se encuentra ", " está "]
                for sep in separadores:
                    if sep in contenido:
                        partes = contenido.split(sep)
                        sujeto = partes[0].strip()
                        valor = " ".join(partes[1:]).strip()
                        if len(sujeto) > 2 and len(valor) > 1:
                            agregar_memoria(sujeto, valor)
                            return f"Hecho {NOMBRE_USUARIO}, he guardado que {sujeto} {sep.strip()} {valor}."
                agregar_memoria("nota_rapida", contenido)
                return f"Anotado {NOMBRE_USUARIO}, lo he puesto en memoria: {contenido}."

    if any(m in t for m in ["cómo se llama", "cómo se llama", "cuál es el nombre de", "dónde está", "dónde se encuentra"]):
        mem = cargar_memoria()
        if mem:
            for clave, data in mem.items():
                clave_limpia = clave.replace("_", " ")
                palabras_clave = clave_limpia.split()
                if any(palabra in t for palabra in palabras_clave if len(palabra) > 3) or clave_limpia in t:
                    print(f"[MEMORIA] Respuesta local encontrada para: {clave}")
                    return f"Según mis archivos locales, {clave_limpia} es {data['valor']}, {NOMBRE_USUARIO}."

    return None

def resolver_matematica_local(texto):
    t = texto.lower().replace("?", "").strip()

    prefijos = ["cuánto es", "calcula", "resuelve", "cuál es el resultado de"]
    for prefijo in prefijos:
        if t.startswith(prefijo):
            t = t[len(prefijo):].strip()

    t = t.replace("por", "*").replace("multiplicado por", "*").replace("x", "*")
    t = t.replace("dividido por", "/").replace("entre", "/")
    t = t.replace("más", "+").replace("menos", "-")
    t = t.replace("potencia", "**").replace("al cuadrado", "**2")

    if "raíz" in t or "raiz" in t:
        match = re.search(r'ra[íi]z\s+(?:cuadrada\s+de\s+)?(\d+)', t)
        if match:
            t = f"sqrt({match.group(1)})"
        else:
            t = t.replace("raíz cuadrada de", "sqrt").replace("raiz cuadrada de", "sqrt")

    expr = re.sub(r'[^0-9+\-*/.**() ,sqrt]', '', t).strip()
    if not expr or not any(c.isdigit() for c in expr):
        return None

    try:
        safe_dict = {
            "sqrt": math.sqrt,
            "pow": math.pow,
            "pi": math.pi,
            "e": math.e
        }
        resultado = eval(expr, {"__builtins__": None}, safe_dict)

        if isinstance(resultado, float) and resultado.is_integer():
            resultado = int(resultado)
        elif isinstance(resultado, float):
            resultado = round(resultado, 3)

        expr_limpia = expr.replace("**2", " al cuadrado").replace("sqrt", "raíz de ").replace("(", "").replace(")", "").replace("*", " por ").replace("/", " dividido por ")
        return f"El resultado de {expr_limpia} es {resultado}, Señor."
    except Exception:
        return None

def resolver_frances_local(texto):
    t = texto.lower().strip()

    diccionario = {
        "ia": "Inteligencia Artificial. Conjunto de teorías y técnicas implementadas para crear máquinas capaces de simular la inteligencia humana.",
        "inteligencia artificial": "Conjunto de teorías y técnicas implementadas para crear máquinas capaces de simular la inteligencia humana.",
        "casa": "Edificio que sirve como vivienda, habitación.",
        "matemáticas": "Ciencia que estudia por medio del razonamiento deductivo las propiedades de entes abstractos.",
        "omega": "Optimized Multipurpose Enhanced Generative Assistant. Tu fiel asistente.",
    }

    if any(p in t for p in ["definición de", "define la palabra", "qué es"]):
        palabra = ""
        if "definición de" in t:
            palabra = t.split("definición de")[-1]
        elif "define la palabra" in t:
            palabra = t.split("define la palabra")[-1]
        elif "qué es" in t:
            palabra = t.split("qué es")[-1]

        palabra = palabra.replace("?", "").replace("el ", "").replace("la ", "").replace("las ", "").strip()

        if palabra in diccionario:
            return f"La definición de {palabra} es: {diccionario[palabra]}."

    if "conjuga" in t or "conjugación" in t:
        if "ser" in t:
            return "Verbo Ser en presente: Yo soy, tú eres, él es, nosotros somos, vosotros sois, ellos son."
        if "estar" in t:
            return "Verbo Estar en presente: Yo estoy, tú estás, él está, nosotros estamos, vosotros estáis, ellos están."

    return None

def resolver_conversion_local(texto):
    t = texto.lower().replace("?", "").strip()

    if any(m in t for m in [" km ", " kilómetros ", " millas "]):
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:km|kilómetros)', t)
        if match:
            val = float(match.group(1).replace(",", "."))
            res = round(val * 0.621371, 2)
            return f"{val} kilómetros son aproximadamente {res} millas, Señor."
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:millas)', t)
        if match:
            val = float(match.group(1).replace(",", "."))
            res = round(val / 0.621371, 2)
            return f"{val} millas son aproximadamente {res} kilómetros, Señor."

    if any(m in t for m in [" grados ", " celsius ", " fahrenheit "]):
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:grados|celsius)', t)
        if match and "fahrenheit" in t:
            val = float(match.group(1).replace(",", "."))
            res = round((val * 9 / 5) + 32, 1)
            return f"{val} grados Celsius son {res} grados Fahrenheit."
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:grados|fahrenheit)', t)
        if match and "celsius" in t:
            val = float(match.group(1).replace(",", "."))
            res = round((val - 32) * 5 / 9, 1)
            return f"{val} grados Fahrenheit son {res} grados Celsius."

    if any(m in t for m in [" euro ", " euros ", " dólar ", " dólares "]):
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*euros?', t)
        if match and "dólar" in t:
            val = float(match.group(1).replace(",", "."))
            res = round(val * 1.08, 2)
            return f"{val} euros son aproximadamente {res} dólares, Señor."
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*dólares?', t)
        if match and "euro" in t:
            val = float(match.group(1).replace(",", "."))
            res = round(val / 1.08, 2)
            return f"{val} dólares son aproximadamente {res} euros, Señor."

    return None

def resolver_traduccion_local(texto):
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
        "asistente": {"en": "assistant", "es": "asistente", "de": "assistent"},
    }

    if any(p in t for p in ["cómo se dice", "traduce", "en inglés", "en español", "en alemán"]):
        destino = "en"
        if "español" in t:
            destino = "es"
        elif "alemán" in t:
            destino = "de"

        palabra = t
        for p in ["cómo se dice", "traduce", "en inglés", "en español", "en alemán", "?"]:
            palabra = palabra.replace(p, "")
        palabra = palabra.replace('"', '').replace("'", "").strip()

        if palabra in dict_trad:
            res = dict_trad[palabra][destino]
            idioma = "inglés" if destino == "en" else ("español" if destino == "es" else "alemán")
            return f"En {idioma}, '{palabra}' se dice '{res}'."

    return None

# =============================================================================
# EXTRAS LOCALES — Temporizador, Chistes, Volumen, Notas, etc.
# =============================================================================

_CHISTES = [
    "¿Por qué los buceadores siempre se tiran de espaldas? ¡Porque si no se caerían al barco!",
    "Un hombre entra en una biblioteca y pregunta: '¿Tienen libros sobre paranoia?' La bibliotecaria susurra: 'Están justo detrás de ti.'",
    "¿Qué es un cuchillo? Un pequeño fiambre.",
    "¿Por qué el espantapájaros recibió un premio? Porque era excepcional en su campo.",
    "¿Cómo se llama un gato que se cayó en un bote de pintura en Navidad? Un gato-pintura de Navidad.",
    "¿Qué es un cocodrilo que vigila el patio del colegio? Un saco de dientes.",
    "¿Por qué los matemáticos confunden Halloween y Navidad? Porque Oct 31 = Dec 25.",
    "Un hombre entra en un bar... Ay.",
    "¿Qué es un cordero que tartamudea? Bebé mantequilla.",
    "¿Qué es un filósofo? Un hombre que busca en una habitación oscura un sombrero negro que no existe. Un teólogo: lo encuentra igual.",
    "¿Cómo se llama un pez sin ojos? Un pez.",
    "¿Qué es un Tic que se cae de un árbol? Un Tac.",
    "¿Por qué el escarabajo es tan fuerte? Porque levanta boñigas de vaca.",
    "¿Cómo se llama un gato que se cayó en un bote de mermelada? Un gato confitado.",
    "¿Qué es un yogur en el bosque? Un yogur natural.",
    "¿Por qué las jirafas tienen cuello largo? Porque sus pies huelen mal.",
    "¿Qué es un hueso en un baño de barro? Sherlock Bones.",
    "¿Cómo se llama un cinturón de piel de cocodrilo? Un cinturón que da la vuelta a la barriga.",
    "¿Qué es un cactus? Un árbol bien defendido.",
    "¿Por qué los belgas meten el móvil en el congelador? Para tener contactos fríos.",
]

_CITAS = [
    "El éxito es caerse siete veces y levantarse ocho. — Proverbio japonés",
    "La vida es como una bicicleta, hay que avanzar para no perder el equilibrio. — Albert Einstein",
    "La única manera de hacer un buen trabajo es amar lo que haces. — Steve Jobs",
    "Quien mueve montañas comienza por mover pequeñas piedras. — Confucio",
    "No esperes. El momento nunca será perfecto. — Napoleon Hill",
    "La mayor gloria no es no caer nunca, sino levantarse en cada caída. — Nelson Mandela",
    "No puedes ir atrás y cambiar el principio, pero puedes empezar donde estás y cambiar el final. — C.S. Lewis",
    "El pesimista ve la dificultad en cada oportunidad. El optimista ve la oportunidad en cada dificultad. — Winston Churchill",
    "No es la montaña que conquistamos, sino nosotros mismos. — Edmund Hillary",
    "La creatividad es la inteligencia divirtiéndose. — Albert Einstein",
    "Todo experto fue un día principiante. — Helen Hayes",
    "Tu tiempo es limitado. No lo desperdicies viviendo la vida de otro. — Steve Jobs",
    "Todo lo que la mente puede concebir y creer, puede lograrlo. — Napoleon Hill",
    "El secreto para avanzar es empezar. — Mark Twain",
    "Las personas que son lo suficientemente locas para pensar que pueden cambiar el mundo son las que lo hacen. — Apple",
]

_FONETICO = {
    'a': 'Alfa', 'b': 'Bravo', 'c': 'Charlie', 'd': 'Delta', 'e': 'Eco',
    'f': 'Foxtrot', 'g': 'Golf', 'h': 'Hotel', 'i': 'India', 'j': 'Juliett',
    'k': 'Kilo', 'l': 'Lima', 'm': 'Mike', 'n': 'Noviembre', 'o': 'Oscar',
    'p': 'Papá', 'q': 'Quebec', 'r': 'Romeo', 's': 'Sierra', 't': 'Tango',
    'u': 'Uniforme', 'v': 'Víctor', 'w': 'Whiskey', 'x': 'X-ray', 'y': 'Yankee',
    'z': 'Zulú',
}

_CAPITALES = {
    "francia": "París", "españa": "Madrid", "italia": "Roma", "alemania": "Berlín",
    "reino unido": "Londres", "inglaterra": "Londres", "portugal": "Lisboa",
    "países bajos": "Ámsterdam", "bélgica": "Bruselas", "suiza": "Berna",
    "austria": "Viena", "polonia": "Varsovia", "suecia": "Estocolmo",
    "noruega": "Oslo", "dinamarca": "Copenhague", "finlandia": "Helsinki",
    "rusia": "Moscú", "ucrania": "Kiev", "grecia": "Atenas",
    "turquía": "Ankara", "marruecos": "Rabat", "argelia": "Argel",
    "túnez": "Túnez", "egipto": "El Cairo", "senegal": "Dakar",
    "camerún": "Yaundé", "costa de marfil": "Yamusukro", "malí": "Bamako",
    "estados unidos": "Washington", "canadá": "Ottawa", "méxico": "Ciudad de México",
    "brasil": "Brasilia", "argentina": "Buenos Aires", "chile": "Santiago",
    "perú": "Lima", "colombia": "Bogotá", "venezuela": "Caracas",
    "china": "Pekín", "japón": "Tokio", "corea del sur": "Seúl",
    "india": "Nueva Delhi", "pakistán": "Islamabad", "australia": "Canberra",
    "nueva zelanda": "Wellington", "sudáfrica": "Pretoria",
    "nigeria": "Abuya", "kenia": "Nairobi", "ghana": "Acra",
    "israel": "Jerusalén", "irán": "Teherán", "irak": "Bagdad",
    "arabia saudita": "Riad", "emiratos árabes unidos": "Abu Dabi",
    "qatar": "Doha", "indonesia": "Yakarta", "tailandia": "Bangkok",
    "vietnam": "Hanói", "filipinas": "Manila", "malasia": "Kuala Lumpur",
}

_MONEDAS = {
    "francia": "Euro (€)", "españa": "Euro (€)", "italia": "Euro (€)",
    "alemania": "Euro (€)", "portugal": "Euro (€)", "bélgica": "Euro (€)",
    "suiza": "Franco suizo (CHF)", "reino unido": "Libra esterlina (£)",
    "inglaterra": "Libra esterlina (£)", "estados unidos": "Dólar estadounidense ($)",
    "canadá": "Dólar canadiense (CAD)", "australia": "Dólar australiano (AUD)",
    "japón": "Yen (¥)", "china": "Yuan (CNY)", "rusia": "Rublo (RUB)",
    "india": "Rupia india (INR)", "brasil": "Real (BRL)",
    "marruecos": "Dírham marroquí (MAD)", "argelia": "Dinar argelino (DZD)",
    "túnez": "Dinar tunecino (TND)", "méxico": "Peso mexicano (MXN)",
    "turquía": "Lira turca (TRY)", "arabia saudita": "Riyal saudí (SAR)",
    "emiratos árabes unidos": "Dírham de los EAU (AED)", "corea del sur": "Won (KRW)",
}

_FUSOS = {
    "nueva york": ("Nueva York", "America/New_York"),
    "los angeles": ("Los Ángeles", "America/Los_Angeles"),
    "chicago": ("Chicago", "America/Chicago"),
    "montreal": ("Montreal", "America/Toronto"),
    "toronto": ("Toronto", "America/Toronto"),
    "london": ("Londres", "Europe/London"),
    "londres": ("Londres", "Europe/London"),
    "paris": ("París", "Europe/Paris"),
    "berlin": ("Berlín", "Europe/Berlin"),
    "madrid": ("Madrid", "Europe/Madrid"),
    "roma": ("Roma", "Europe/Rome"),
    "moscow": ("Moscú", "Europe/Moscow"),
    "moscu": ("Moscú", "Europe/Moscow"),
    "dubai": ("Dubai", "Asia/Dubai"),
    "india": ("India", "Asia/Kolkata"),
    "mumbai": ("Mumbai", "Asia/Kolkata"),
    "delhi": ("Delhi", "Asia/Kolkata"),
    "beijing": ("Pekín", "Asia/Shanghai"),
    "pekin": ("Pekín", "Asia/Shanghai"),
    "shanghai": ("Shanghai", "Asia/Shanghai"),
    "tokyo": ("Tokio", "Asia/Tokyo"),
    "japon": ("Tokio", "Asia/Tokyo"),
    "seoul": ("Seúl", "Asia/Seoul"),
    "sydney": ("Sídney", "Australia/Sydney"),
    "melbourne": ("Melbourne", "Australia/Melbourne"),
    "auckland": ("Auckland", "Pacific/Auckland"),
    "sao paulo": ("Sao Paulo", "America/Sao_Paulo"),
    "buenos aires": ("Buenos Aires", "America/Argentina/Buenos_Aires"),
    "mexico": ("Ciudad de México", "America/Mexico_City"),
    "honolulu": ("Honolulu", "Pacific/Honolulu"),
    "hawaii": ("Hawái", "Pacific/Honolulu"),
    "anchorage": ("Anchorage", "America/Anchorage"),
    "bangkok": ("Bangkok", "Asia/Bangkok"),
    "singapore": ("Singapur", "Asia/Singapore"),
    "singapur": ("Singapur", "Asia/Singapore"),
    "hong kong": ("Hong Kong", "Asia/Hong_Kong"),
    "el cairo": ("El Cairo", "Africa/Cairo"),
    "nairobi": ("Nairobi", "Africa/Nairobi"),
    "johannesburg": ("Johannesburgo", "Africa/Johannesburg"),
    "casablanca": ("Casablanca", "Africa/Casablanca"),
}

_RUTA_LISTAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "omega_listas.json")

def _cargar_listas():
    try:
        if os.path.exists(_RUTA_LISTAS):
            with open(_RUTA_LISTAS, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"notas": [], "compras": [], "tareas": []}

def _guardar_listas(data):
    try:
        with open(_RUTA_LISTAS, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[LISTAS] Error guardando: {e}")

_temporizadores = {}

def _parsear_duracion_segundos(texto):
    import re
    t = texto.lower()
    total = 0
    h = re.search(r'(\d+)\s*(hora|h\b)', t)
    m = re.search(r'(\d+)\s*(minuto|min\b)', t)
    s = re.search(r'(\d+)\s*(segundo|seg\b)', t)
    if h:
        total += int(h.group(1)) * 3600
    if m:
        total += int(m.group(1)) * 60
    if s:
        total += int(s.group(1))
    return total if total > 0 else None

def _obtener_interfaz_volumen():
    if not _pycaw_ok:
        return None
    try:
        from ctypes import cast, POINTER
        dispositivos = AudioUtilities.GetSpeakers()
        interfaz = dispositivos.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interfaz, POINTER(IAudioEndpointVolume))
    except Exception:
        return None

async def resolver_globo_local(texto: str):
    import re
    t = texto.lower().strip()

    _palabras_globo = ["muestra la tierra", "muéstrame la tierra",
                       "globo terráqueo", "muestra el globo", "vista de la tierra",
                       "vista espacial", "vista desde el espacio",
                       "muestra el planeta", "vista del planeta",
                       "zoom total hacia atrás"]

    _palabras_ciudad = ["muestra", "muéstrame", "muestrame", "sobrevuela",
                        "navega a", "ve a", "haz zoom en",
                        "haz un sobrevuelo de", "localiza", "encuentra",
                        "dónde está", "donde esta", "sitúa", "dónde se encuentra"]

    _palabras_ruta = ["traza una ruta", "trazar ruta de",
                      "ruta de", "camino de", "cómo ir de",
                      "traza un itinerario", "trayecto de", "trayecto desde"]

    _palabras_cerrar = ["cierra el mapa", "cierra el globo", "oculta el mapa",
                        "oculta el globo", "cierra la navegación", "sal del globo",
                        "vuelve a omega", "cierra la vista", "oculta el mapa"]

    _palabras_posicion = ["mi posición", "donde estoy", "mi ubicación",
                          "muestra mi posición", "localízame"]

    if any(m in t for m in _palabras_cerrar):
        await enviar_comando_globo(globe_action="hide")
        return "Navegación cerrada. Vuelvo a la interfaz principal, {NOMBRE_USUARIO}."

    if any(m in t for m in _palabras_posicion):
        await enviar_comando_globo(globe_action="my_location")
        await hablar("Localizando, {NOMBRE_USUARIO}. El globo muestra tu posición en tiempo real.")
        return "[Globo] Solicitud de geolocalización enviada al navegador."

    if any(m in t for m in _palabras_globo):
        await enviar_comando_globo(globe_action="show_earth")
        await hablar("Inicializando el globo terráqueo. Vista desde el espacio activada, {NOMBRE_USUARIO}.")
        return "[Globo] Vista Tierra activada."

    if any(m in t for m in _palabras_ruta):
        patron = r"(?:de|desde)\s+(.+?)\s+(?:a|hasta)\s+(.+?)(?:\s*[?!]?\s*$)"
        match = re.search(patron, t)
        if match:
            desde_nombre = match.group(1).strip().title()
            hasta_nombre = match.group(2).strip().title()
            await hablar(f"Calculando ruta de {desde_nombre} a {hasta_nombre}. Localizando...")
            lat1, lon1, _ = await geocodificar_lugar(desde_nombre)
            lat2, lon2, _ = await geocodificar_lugar(hasta_nombre)
            if lat1 and lat2:
                await enviar_comando_globo(
                    globe_action="route",
                    from_lat=lat1, from_lon=lon1, from_name=desde_nombre,
                    to_lat=lat2, to_lon=lon2, to_name=hasta_nombre
                )
                await hablar(f"Ruta trazada de {desde_nombre} a {hasta_nombre}, {NOMBRE_USUARIO}. La ruta se muestra en el globo.")
                return f"[Globo] Ruta {desde_nombre} → {hasta_nombre} mostrada."
            else:
                return f"No he podido localizar las dos ciudades, {NOMBRE_USUARIO}. Verifica los nombres y vuelve a intentarlo."
        return None

    for palabra in _palabras_ciudad:
        if palabra in t:
            idx = t.find(palabra)
            resto = t[idx + len(palabra):].strip()

            if palabra in ["muestra", "muéstrame", "muestrame", "encuentra"]:
                if any(k in t for k in ["imagen", "foto", "dibujo", "ilustración", "wallpaper", "fondo de pantalla"]):
                    continue
                resto_limpio = resto.lower()
                if any(resto_limpio.startswith(art) for art in ["un ", "una ", "unas ", "unos ", "del ", "de la ", "de los "]):
                    continue
                if any(k in t for k in ["tiempo", "clima", "temperatura", "noticias", "correo", "mensaje", "calendario", "agenda", "chiste", "cita", "nota", "compras", "comando"]):
                    continue

            for art in ["la ciudad de ", "la ciudad ", "el ", "la ", "las ", "mi ciudad ", "mi país "]:
                if resto.startswith(art):
                    resto = resto[len(art):]
            resto = resto.replace("?", "").replace("!", "").strip()
            if len(resto) >= 2:
                nombre_lugar = resto.title()

                lat, lon, display = await geocodificar_lugar(nombre_lugar)
                if lat is None:
                    continue

                await hablar(f"Buscando {nombre_lugar}... Obteniendo coordenadas.")
                altitud = 300000
                await enviar_comando_globo(
                    globe_action="fly_to",
                    lat=lat, lon=lon,
                    target=nombre_lugar,
                    altitude=altitud
                )
                await hablar(f"Coordenadas obtenidas. Sobrevolando {nombre_lugar}, {NOMBRE_USUARIO}.")
                return f"[Globo] Sobrevolando {nombre_lugar} ({lat:.4f}°, {lon:.4f}°)"
            break

    return None

async def resolver_extras_locales(texto):
    global ULTIMOS_RESTAURANTES_MOSTRADOS
    import re
    import random
    t = texto.lower().replace("?", "").strip()

    if any(k in t for k in ["temporizador", "temporizadora", "timer", "recuérdame en",
                             "recuerdame en", "alarma en", "alerta en",
                             "activa el temporizador", "pon un temporizador",
                             "avisame en", "avísame en"]):
        duracion = _parsear_duracion_segundos(t)
        if duracion:
            if CLIENTES_CONECTADOS:
                async def _enviar_timer():
                    msg = json.dumps({"action": "timer_start", "duration": duracion})
                    await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                lanzar_tarea_fondo(_enviar_timer())

            nombre = f"timer_{len(_temporizadores)+1}"

            def _sonar(nombre=nombre, duracion=duracion):
                _temporizadores.pop(nombre, None)
                import random
                respuestas = [
                    f"Señor, el protocolo de cuenta atrás ha llegado a su fin.",
                    f"{NOMBRE_USUARIO}, la temporización ha terminado. ¿Espero que no hayas olvidado nada?",
                    f"Alerta: El temporizador ha llegado a cero. ¿Todo en orden, Señor?",
                    f"Fin de la cuenta atrás, {NOMBRE_USUARIO}. Sigo a tu entera disposición."
                ]
                bucle2 = asyncio.new_event_loop()
                bucle2.run_until_complete(hablar(random.choice(respuestas)))
                bucle2.close()

            timer = threading.Timer(duracion, _sonar)
            timer.daemon = True
            timer.start()
            _temporizadores[nombre] = timer

            mins = duracion // 60
            return f"Temporizador de {mins} minutos activado. Mostrando en HUD."
        return "Especifica la duración, por ejemplo: 'Pon un temporizador de 10 minutos'."

    if any(k in t for k in ["añade", "agrega", "suma"]) and "minuto" in t:
        try:
            extra = int(re.search(r'\d+', t).group()) * 60
            if CLIENTES_CONECTADOS:
                async def _enviar_add():
                    msg = json.dumps({"action": "timer_add", "duration": extra})
                    await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                lanzar_tarea_fondo(_enviar_add())
            return f"He añadido {extra//60} minutos al temporizador."
        except:
            pass

    if any(k in t for k in ["resta", "quita", "elimina", "reduce"]) and "minuto" in t:
        try:
            menos = int(re.search(r'\d+', t).group()) * 60
            if CLIENTES_CONECTADOS:
                async def _enviar_rem():
                    msg = json.dumps({"action": "timer_remove", "duration": menos})
                    await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                lanzar_tarea_fondo(_enviar_rem())
            return f"He quitado {menos//60} minutos al temporizador."
        except:
            pass

    if any(k in t for k in ["cancelar temporizador", "cancelar timer", "parar temporizador",
                             "detener temporizador", "detiene el temporizador"]):
        if CLIENTES_CONECTADOS:
            async def _enviar_stop():
                msg = json.dumps({"action": "timer_stop"})
                await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            lanzar_tarea_fondo(_enviar_stop())

        if _temporizadores:
            for nombre, timer in list(_temporizadores.items()):
                timer.cancel()
            _temporizadores.clear()
            return f"Temporizador detenido, {NOMBRE_USUARIO}."
        return "No hay temporizador activo."

    if any(k in t for k in ["temporizador activo", "temporizadores activos", "cuántos temporizadores"]):
        if _temporizadores:
            return f"Tienes {len(_temporizadores)} temporizador{'es' if len(_temporizadores) > 1 else ''} activo{'s' if len(_temporizadores) > 1 else ''}."
        return "No hay temporizadores activos."

    if any(k in t for k in ["hora en", "hora de", "qué hora es en", "qué hora es en",
                             "hora allá", "hora alla"]):
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            try:
                from backports.zoneinfo import ZoneInfo
            except ImportError:
                ZoneInfo = None
        if ZoneInfo:
            for clave, (nombre_ciudad, tz_str) in _FUSOS.items():
                if clave in t:
                    try:
                        from datetime import timezone
                        hora_local = datetime.now(ZoneInfo(tz_str))
                        return f"Son actualmente las {hora_local.strftime('%H:%M')} en {nombre_ciudad}, {NOMBRE_USUARIO}."
                    except Exception:
                        pass
        return "No reconozco esa ciudad en mi base local, {NOMBRE_USUARIO}."

    edad_match = re.search(r'n[ée]\s+en\s+(\d{4})', t)
    if edad_match or any(k in t for k in ["qué edad tengo", "que edad tengo",
                                           "cuántos años tengo", "calcular mi edad"]):
        if edad_match:
            anio_nac = int(edad_match.group(1))
            edad = datetime.now().year - anio_nac
            return f"Si naciste en {anio_nac}, tienes {edad} años, {NOMBRE_USUARIO}."
        return "Especifica tu año de nacimiento, por ejemplo: 'Nacido en 1990, ¿qué edad tengo?'"

    if any(k in t for k in ["cuántos días faltan para navidad", "días para navidad", "cuantos días para navidad"]):
        hoy = datetime.now().date()
        navidad = datetime(hoy.year, 12, 25).date()
        if hoy > navidad:
            navidad = datetime(hoy.year + 1, 12, 25).date()
        dias = (navidad - hoy).days
        return f"Faltan {dias} día{'s' if dias > 1 else ''} para Navidad, {NOMBRE_USUARIO}!"

    if any(k in t for k in ["cuántos días para año nuevo", "días para año nuevo", "cuantos días para año nuevo"]):
        hoy = datetime.now().date()
        anio_prox = datetime(hoy.year + 1, 1, 1).date()
        dias = (anio_prox - hoy).days
        return f"Faltan {dias} día{'s' if dias > 1 else ''} para Año Nuevo, {NOMBRE_USUARIO}!"

    if any(k in t for k in ["chiste", "hazme reír", "cuéntame un chiste",
                             "dime un chiste", "un chiste", "haz reír"]):
        return random.choice(_CHISTES)

    if any(k in t for k in ["cita", "inspírame", "frase", "cita motivadora",
                             "motívame", "dime algo", "dame una cita"]):
        return random.choice(_CITAS)

    if any(k in t for k in ["cara o cruz", "lanza una moneda", "heads or tails"]):
        resultado = random.choice(["Cara", "Cruz"])
        return f"He lanzado la moneda... ¡Es {resultado}!"

    dado_match = re.search(r'(?:lanza|tira|lanza|tira)\s+un\s+dado\s+(?:de\s+)?(\d+)\s+caras?', t)
    if dado_match or "lanza un dado" in t or "tira el dado" in t:
        caras = 6
        m2 = re.search(r'dado\s+de\s+(\d+)', t)
        if m2:
            caras = int(m2.group(1))
        resultado = random.randint(1, caras)
        return f"He lanzado un dado de {caras} caras... ¡Has sacado {resultado}!"

    if any(k in t for k in ["número aleatorio", "numero aleatorio", "genera un número", "genere un numero"]):
        rng_match = re.search(r'entre\s+(\d+)\s+y\s+(\d+)', t)
        if rng_match:
            a, b = int(rng_match.group(1)), int(rng_match.group(2))
            return f"Tu número aleatorio entre {a} y {b}: {random.randint(a, b)}"
        return f"Aquí tienes un número aleatorio: {random.randint(1, 100)}"

    _es_pedido_contrasena = any(k in t for k in [
        "genera una contraseña", "genere una contraseña", "generar contraseña",
        "crea una contraseña", "cree una contraseña", "crear contraseña",
        "dame una contraseña", "dame una pass", "genera un password",
        "cree un password", "nueva contraseña"
    ])
    _es_consulta_informativa = any(k in t for k in [
        "cómo", "por qué", "que es", "qué es", "qué significa",
        "hackear", "piratear", "recuperar", "olvidé", "olvide", "seguridad"
    ])
    if _es_pedido_contrasena and not _es_consulta_informativa:
        import string
        longitud = 16
        lg_m = re.search(r'(\d+)\s*(?:caracteres|caract)', t)
        if lg_m:
            longitud = min(max(int(lg_m.group(1)), 8), 64)
        chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        passwd = ''.join(random.SystemRandom().choice(chars) for _ in range(longitud))
        return f"Aquí tienes una contraseña aleatoria segura ({longitud} caracteres): {passwd}"

    if any(k in t for k in ["nota esto", "apunta esto", "toma nota",
                             "memoriza esto", "anota esto", "escribe esto",
                             "nota que", "nota:", "anota:"]):
        contenido = t
        for pref in ["nota esto:", "apunta esto:", "nota que", "nota:", "toma nota:",
                     "toma nota de", "memoriza esto:", "anota esto:", "anota:",
                     "escribe esto:", "apunta:"]:
            if contenido.startswith(pref):
                contenido = contenido[len(pref):].strip()
                break
        if contenido:
            listas = _cargar_listas()
            nota = f"[{datetime.now().strftime('%d/%m %H:%M')}] {contenido}"
            listas["notas"].append(nota)
            _guardar_listas(listas)
            return f"Nota guardada, {NOMBRE_USUARIO}: '{contenido}'"
        return "¿Qué quieres que anote?"

    if any(k in t for k in ["lee mis notas", "muestra mis notas", "cuáles son mis notas",
                             "mis notas", "muestra notas"]):
        listas = _cargar_listas()
        if not listas["notas"]:
            return f"No tienes notas guardadas, {NOMBRE_USUARIO}."
        notas = "\n".join(f"• {n}" for n in listas["notas"][-5:])
        return f"Tus últimas {min(5, len(listas['notas']))} notas, {NOMBRE_USUARIO}: {notas}"

    if any(k in t for k in ["borra mis notas", "elimina mis notas",
                             "vacía mis notas", "clear mis notas"]):
        listas = _cargar_listas()
        listas["notas"] = []
        _guardar_listas(listas)
        return f"Todas tus notas han sido borradas, {NOMBRE_USUARIO}."

    if any(k in t for k in ["añade", "agrega"]) and any(k in t for k in ["lista de compras", "compras", "lista de la compra"]):
        articulo = t
        for pref in ["añade ", "agrega ", "a mi lista de compras", "a la lista de compras",
                     "en la lista de compras", "a mis compras"]:
            articulo = articulo.replace(pref, "").strip()
        if articulo:
            listas = _cargar_listas()
            listas["compras"].append(articulo)
            _guardar_listas(listas)
            msg = json.dumps({"type": "shopping_list", "items": listas["compras"]})
            msg_open = json.dumps({"type": "shopping_open"})
            if CLIENTES_CONECTADOS:
                asyncio.ensure_future(asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True))
                asyncio.ensure_future(asyncio.gather(*[ws.send(msg_open) for ws in CLIENTES_CONECTADOS], return_exceptions=True))
            return f"'{articulo}' añadido a tu lista de compras, {NOMBRE_USUARIO}."

    es_pregunta_compras = False
    palabras_clave_compras = [
        "lista de compra", "lista de compras", "mis compras", "las compras",
        "lista de la compra", "mi lista"
    ]
    tiene_palabra_compras = any(k in t for k in palabras_clave_compras)
    tiene_recordatorio_compras = any(r in t for r in ["recordar", "recuerda", "acordar"]) and any(c in t for c in ["compra", "comprar"])

    tiene_preguntas_compras = any(q in t for q in [
        "debo comprar", "tengo que comprar", "qué comprar",
        "qué hay que comprar", "qué productos comprar",
        "qué necesito comprar", "que necesito comprar"
    ])

    if tiene_palabra_compras or tiene_recordatorio_compras or tiene_preguntas_compras:
        es_agregar = any(k in t for k in ["añade", "agrega", "pon", "meter", "añadir", "agregar"])
        es_vaciar = any(k in t for k in ["vacía", "borra", "elimina", "clear", "limpia", "vaciar", "borrar", "eliminar"])
        if not es_agregar and not es_vaciar:
            es_pregunta_compras = True

    if es_pregunta_compras:
        listas = _cargar_listas()
        msg = json.dumps({"type": "shopping_list", "items": listas.get("compras", [])})
        msg_open = json.dumps({"type": "shopping_open"})
        if CLIENTES_CONECTADOS:
            asyncio.ensure_future(asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True))
            asyncio.ensure_future(asyncio.gather(*[ws.send(msg_open) for ws in CLIENTES_CONECTADOS], return_exceptions=True))
        if not listas.get("compras"):
            return f"Tu lista de compras está vacía, {NOMBRE_USUARIO}."
        items = ", ".join(listas["compras"])
        respuestas = [
            f"Tu lista de compras contiene: {items}.",
            f"Esto es lo que debes comprar, {NOMBRE_USUARIO}: {items}.",
            f"Recordatorio de tu lista de compras, Señor. Contiene: {items}.",
            f"Actualmente en tu lista de compras hay: {items}.",
            f"Estos son los productos de tu lista de compras: {items}."
        ]
        return random.choice(respuestas)

    if any(k in t for k in ["vacía la lista de compras", "borra la lista de compras",
                             "elimina la lista de compras", "clear compras"]):
        listas = _cargar_listas()
        listas["compras"] = []
        _guardar_listas(listas)
        msg = json.dumps({"type": "shopping_list", "items": []})
        if CLIENTES_CONECTADOS:
            asyncio.ensure_future(asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True))
        return f"Lista de compras vaciada, {NOMBRE_USUARIO}."

    if any(k in t for k in ["añade una tarea", "nueva tarea", "añade a mi to-do",
                             "to-do:", "pendiente:", "tarea:"]):
        tarea = t
        for pref in ["añade una tarea:", "nueva tarea:", "añade a mi to-do:",
                     "to-do:", "pendiente:", "tarea:", "añade una tarea "]:
            tarea = tarea.replace(pref, "").strip()
        if tarea:
            listas = _cargar_listas()
            listas["tareas"].append({"tarea": tarea, "hecho": False, "fecha": datetime.now().strftime("%d/%m")})
            _guardar_listas(listas)
            return f"Tarea añadida: '{tarea}', {NOMBRE_USUARIO}."

    if any(k in t for k in ["mis tareas", "mi to-do", "lista de tareas",
                             "qué tengo que hacer", "que tengo que hacer"]):
        listas = _cargar_listas()
        tareas = [td for td in listas["tareas"] if not td.get("hecho")]
        if not tareas:
            return f"Tu lista de tareas está vacía, {NOMBRE_USUARIO}. ¡Bien hecho!"
        items = "\n".join(f"• [{td['fecha']}] {td['tarea']}" for td in tareas[-8:])
        return f"Tus tareas pendientes ({len(tareas)}): {items}"

    if any(k in t for k in ["borra mis tareas", "vacía mi to-do",
                             "elimina mis tareas", "clear tareas"]):
        listas = _cargar_listas()
        listas["tareas"] = []
        _guardar_listas(listas)
        return f"Lista de tareas vaciada, {NOMBRE_USUARIO}."

    palabras_vol = ["volumen", "sonido", "audio"]
    if any(k in t for k in palabras_vol):
        if any(k in t for k in ["silencia el sonido", "mute", "silencio total"]):
            vol = _obtener_interfaz_volumen()
            if vol:
                vol.SetMute(1, None)
                return f"Sonido silenciado, {NOMBRE_USUARIO}."
            return "No he podido acceder al control de volumen. Instala pycaw."

        if any(k in t for k in ["restaura el sonido", "unmute", "reactiva el sonido"]):
            vol = _obtener_interfaz_volumen()
            if vol:
                vol.SetMute(0, None)
                return f"Sonido reactivado, {NOMBRE_USUARIO}."

        vol_match = re.search(r'(\d+)\s*(?:%|porciento)', t)
        if vol_match or any(k in t for k in ["sube el volumen", "sube el sonido",
                                             "baja el volumen", "baja el sonido",
                                             "volumen al", "sonido al", "pon el volumen"]):
            vol = _obtener_interfaz_volumen()
            if vol:
                if vol_match:
                    pct = max(0, min(100, int(vol_match.group(1))))
                    import math
                    vol.SetMasterVolumeLevelScalar(pct / 100.0, None)
                    return f"Volumen ajustado al {pct}%, {NOMBRE_USUARIO}."
                elif any(k in t for k in ["sube", "aumenta", "más fuerte"]):
                    cur = vol.GetMasterVolumeLevelScalar()
                    new_vol = min(1.0, cur + 0.1)
                    vol.SetMasterVolumeLevelScalar(new_vol, None)
                    return f"Volumen aumentado al {int(new_vol*100)}%, {NOMBRE_USUARIO}."
                elif any(k in t for k in ["baja", "disminuye", "más bajo"]):
                    cur = vol.GetMasterVolumeLevelScalar()
                    new_vol = max(0.0, cur - 0.1)
                    vol.SetMasterVolumeLevelScalar(new_vol, None)
                    return f"Volumen reducido al {int(new_vol*100)}%, {NOMBRE_USUARIO}."
            else:
                return "Control de volumen no disponible. Instala pycaw para esta función."

    if any(k in t for k in ["brillo", "pantalla más clara", "pantalla más oscura",
                             "bajar pantalla", "subir pantalla", "luminosidad"]):
        if _sbc_ok and _sbc:
            try:
                lum_match = re.search(r'(\d+)\s*(?:%|porciento)', t)
                if lum_match:
                    pct = max(0, min(100, int(lum_match.group(1))))
                    _sbc.set_brightness(pct)
                    return f"Brillo ajustado al {pct}%, {NOMBRE_USUARIO}."
                elif any(k in t for k in ["sube", "aumenta", "más clara", "max"]):
                    cur = _sbc.get_brightness(display=0)
                    if isinstance(cur, list):
                        cur = cur[0]
                    new_b = min(100, cur + 15)
                    _sbc.set_brightness(new_b)
                    return f"Brillo aumentado al {new_b}%, {NOMBRE_USUARIO}."
                elif any(k in t for k in ["baja", "disminuye", "más oscura", "min"]):
                    cur = _sbc.get_brightness(display=0)
                    if isinstance(cur, list):
                        cur = cur[0]
                    new_b = max(0, cur - 15)
                    _sbc.set_brightness(new_b)
                    return f"Brillo reducido al {new_b}%, {NOMBRE_USUARIO}."
            except Exception as e:
                return f"No se pudo ajustar el brillo: {e}"
        return "El módulo de brillo no está instalado. Ejecuta: pip install screen-brightness-control"

    if any(k in t for k in ["pon el pc en espera", "modo espera", "suspende el pc", "sleep"]):
        delay = _parsear_duracion_segundos(t) or 0
        if delay > 0:
            subprocess.Popen(f'shutdown /h /t {delay}', shell=True)
            mins = delay // 60
            return f"El PC entrará en espera en {mins} minuto{'s' if mins > 1 else ''}, {NOMBRE_USUARIO}."
        subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
        return f"Poniendo PC en espera, {NOMBRE_USUARIO}. ¡Hasta luego!"

    if any(k in t for k in ["apaga el pc", "apagar pc", "apagar el pc",
                             "shutdown", "apagar en"]):
        delay = _parsear_duracion_segundos(t) or 0
        if delay > 0:
            subprocess.Popen(f'shutdown /s /t {delay}', shell=True)
            mins = delay // 60
            return f"El PC se apagará en {mins} minuto{'s' if mins > 1 else ''}, {NOMBRE_USUARIO}."
        return "Para el apagado inmediato, confirma diciendo: 'confirma el apagado del pc'."

    if "confirma el apagado del pc" in t:
        subprocess.Popen("shutdown /s /t 10", shell=True)
        return f"Apagando PC en 10 segundos, {NOMBRE_USUARIO}. ¡Hasta la vista!"

    if any(k in t for k in ["reinicia el pc", "reiniciar pc", "reboot"]):
        delay = _parsear_duracion_segundos(t) or 30
        subprocess.Popen(f'shutdown /r /t {delay}', shell=True)
        mins = max(1, delay // 60)
        return f"Reiniciando en {mins} minuto{'s' if mins > 1 else ''}, {NOMBRE_USUARIO}."

    if any(k in t for k in ["cancela el apagado", "cancela el reinicio",
                             "cancelar apagado", "cancelar reinicio"]):
        subprocess.Popen("shutdown /a", shell=True)
        return f"Apagado/reinicio cancelado, {NOMBRE_USUARIO}."

    if any(k in t for k in ["vacía la papelera", "vaciar papelera", "papelera vacía",
                             "limpiar papelera"]):
        try:
            import winshell
            winshell.recycle_bin().empty(confirm=False, show_progress=False, sound=False)
            return f"Papelera vaciada, {NOMBRE_USUARIO}."
        except ImportError:
            subprocess.run("PowerShell -Command \"Clear-RecycleBin -Force -ErrorAction SilentlyContinue\"",
                           shell=True, capture_output=True)
            return f"Papelera vaciada, {NOMBRE_USUARIO}."
        except Exception as e:
            return f"No se pudo vaciar la papelera: {e}"

    if any(k in t for k in ["capital", "capital de"]):
        for pais, capital in _CAPITALES.items():
            if pais in t:
                return f"La capital de {pais.title()} es {capital}, {NOMBRE_USUARIO}."
        return "No conozco ese país en mi base local, {NOMBRE_USUARIO}."

    if any(k in t for k in ["moneda", "divisa", "moneda de", "cuál es la moneda"]):
        for pais, moneda in _MONEDAS.items():
            if pais in t:
                return f"La moneda de {pais.title()} es {moneda}, {NOMBRE_USUARIO}."
        return "No conozco la moneda de ese país en mi base local."

    if any(k in t for k in ["alfabeto fonético", "codigo fonético",
                             "deletrea", "cómo se escribe"]):
        alpha_match = re.search(r"(?:deletrea|cómo se escribe)\s+([a-z]+)", t)
        if alpha_match:
            palabra = alpha_match.group(1).lower()
            deletreado = " - ".join(_FONETICO.get(c, c.upper()) for c in palabra)
            return f"'{palabra.upper()}' se deletrea: {deletreado}"
        letra_match = re.search(r"([a-z])\s+como\s+\?", t)
        if letra_match:
            c = letra_match.group(1)
            return f"{c.upper()} como {_FONETICO.get(c, '?')}"
        return "Especifica la letra o palabra a deletrear fonéticamente."

    _prefijos_imagenes = [
        "muéstrame imágenes de ", "muestrame imagenes de ",
        "muéstrame fotos de ", "muestrame fotos de ",
        "muéstrame una foto de ", "muestrame una foto de ",
        "muéstrame un dibujo de ", "muestrame un dibujo de ",
        "muestra imágenes de ", "busca imágenes de ",
        "busca fotos de ", "muestra fotos de ",
        "muestra una imagen de ", "muestra una foto de ",
        "quiero ver imágenes de ", "quiero ver fotos de ",
        "encuentra imágenes de ", "encuentra fotos de ",
        "busca una foto de ", "busca una imagen de ",
        "encuentra una imagen de ", "encuentra una foto de ",
        "muestrame imágenes de ", "muestrame fotos de ",
    ]
    for pref in _prefijos_imagenes:
        if t.startswith(pref):
            query = t[len(pref):].strip().rstrip(".")
            if len(query) > 1:
                async def _enviar_imagenes(q=query):
                    cfg = _cargar_config()
                    motor = cfg.get("image_search_engine", "serpapi")
                    urls = buscar_imagenes_web(q, nb_imagenes=6, motor=motor)
                    if urls:
                        msg = json.dumps({"type": "show_images", "query": q, "images": urls})
                        await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                if CLIENTES_CONECTADOS:
                    lanzar_tarea_fondo(_enviar_imagenes())
                return f"Busco imágenes de {query} y las muestro en tu interfaz, {NOMBRE_USUARIO}."

    _frases_winget = [
        "actualiza mis programas", "actualizar software", "abre actualizaciones",
        "verifica actualizaciones", "actualizar programas", "abre winget", "lanza winget"
    ]
    for p in _frases_winget:
        if p in t:
            if CLIENTES_CONECTADOS:
                msg = json.dumps({"action": "winget_open"})
                lanzar_tarea_fondo(asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True))
            return f"Abro el gestor de actualizaciones del sistema y busco actualizaciones disponibles, {NOMBRE_USUARIO}."

    _frases_av = [
        "analiza mi pc", "analiza mi ordenador", "escanea mi pc", "escanea mi ordenador",
        "busca virus", "busca si tengo virus", "lanza el antivirus",
        "lanza un escaneo antivirus", "análisis antivirus", "verifica virus"
    ]
    for p in _frases_av:
        if p in t:
            if CLIENTES_CONECTADOS:
                msg = json.dumps({"type": "av_open"})
                lanzar_tarea_fondo(asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True))
            return f"Abro la consola de seguridad e inicio el escaneo antivirus de tu ordenador, {NOMBRE_USUARIO}."

    r_match1 = re.search(r"(?:recuérdame|recordar)\s+(?:de\s+|mi\s+|ma\s+|que\s+)?(.+?)\s+(?:a|a las)\s*(\d{1,2})[hH:]?(\d{2})?", t)
    r_match2 = re.search(r"(?:recuérdame|recordar)\s+(?:a|a las)\s*(\d{1,2})[hH:]?(\d{2})?\s+(?:de\s+|mi\s+|ma\s+|que\s+)?(.+)", t)

    r_match = r_match1 or r_match2
    if r_match:
        if r_match == r_match1:
            texto = r_match.group(1).strip()
            hora = int(r_match.group(2))
            minuto = int(r_match.group(3)) if r_match.group(3) else 0
        else:
            hora = int(r_match.group(1))
            minuto = int(r_match.group(2)) if r_match.group(2) else 0
            texto = r_match.group(3).strip()

        if 0 <= hora <= 23 and 0 <= minuto <= 59 and len(texto) > 1:
            hora_str = f"{hora:02d}:{minuto:02d}"
            cfg = _cargar_config()
            recordatorios = cfg.get("reminders", [])

            import uuid
            r_id = str(uuid.uuid4())[:8]

            nuevo_r = {
                "id": r_id,
                "text": texto,
                "time": hora_str,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "triggered": False
            }
            recordatorios.append(nuevo_r)
            _guardar_config({"reminders": recordatorios})

            if CLIENTES_CONECTADOS:
                msg = json.dumps({"type": "settings_data", "data": _cargar_config()})
                lanzar_tarea_fondo(asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True))

            return f"Recordatorio guardado, {NOMBRE_USUARIO}. Te recordaré: '{texto}' a las {hora_str}."

    if any(k in t for k in ["mis notas obsidian", "muestra mis notas obsidian", "abre obsidian", "cofre obsidian"]):
        if CLIENTES_CONECTADOS:
            notas_list = src.actions.obsidian_helper.listar_notas()
            msg_open = json.dumps({"type": "obsidian_open"})
            msg_notas = json.dumps({"type": "obsidian_notes", "notes": notas_list})
            lanzar_tarea_fondo(asyncio.gather(*[ws.send(msg_open) for ws in CLIENTES_CONECTADOS], return_exceptions=True))
            lanzar_tarea_fondo(asyncio.gather(*[ws.send(msg_notas) for ws in CLIENTES_CONECTADOS], return_exceptions=True))
        return f"Abro tu cofre de notas Obsidian en la interfaz, {NOMBRE_USUARIO}."

    es_pregunta_restaurante = any(k in t for k in ["restaurante", "restaurantes", "donde comer", "dónde comer"])
    es_otros = any(k in t for k in ["otro", "otros", "otras", "diferentes", "cambia de restaurante"])

    if es_pregunta_restaurante or (es_otros and ULTIMOS_RESTAURANTES_MOSTRADOS):
        especifica_lugar = False
        for prep in [" de ", " en ", " a ", " cerca "]:
            if prep in t:
                idx_prep = t.find(prep)
                suite = t[idx_prep + len(prep):].strip()
                if not any(w in suite for w in ["mi", "aquí", "cerca", "nosotros"]):
                    especifica_lugar = True
                    break

        if not especifica_lugar:
            es_otros_pedido = any(w in t for w in ["otro", "otros", "otras", "diferente", "cambia"])

            if CIUDAD_POR_DEFECTO:
                ubicacion = CIUDAD_POR_DEFECTO
                lat = LAT_POR_DEFECTO if LAT_POR_DEFECTO else None
                lng = LON_POR_DEFECTO if LON_POR_DEFECTO else None
            else:
                ubicacion = obtener_ciudad_por_ip()
                lat = UBICACION_USUARIO_GPS.get("lat") if UBICACION_USUARIO_GPS else None
                lng = UBICACION_USUARIO_GPS.get("lng") if UBICACION_USUARIO_GPS else None

            if not es_otros_pedido:
                ULTIMOS_RESTAURANTES_MOSTRADOS = []
            excluir = list(ULTIMOS_RESTAURANTES_MOSTRADOS)

            lanzar_busqueda_restaurantes_fondo(ubicacion, lat, lng, excluir, es_otros_pedido)
            return "Busco otras direcciones de restaurantes para ti, un momento {NOMBRE_USUARIO}." if es_otros_pedido else "Activo el radar de búsqueda de restaurantes, un momento {NOMBRE_USUARIO}."

    return None

def resolver_info_sistema_local(texto):
    t = texto.lower().replace("?", "").strip()
    ahora = datetime.now()

    DIAS_FR = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    MESES_FR = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

    if any(m in t for m in ["qué hora", "que hora es", "la hora", "dime la hora"]):
        h, m = ahora.hour, ahora.minute
        return f"Son las {h}h{m:02d}, {NOMBRE_USUARIO}."

    if any(m in t for m in ["qué fecha", "qué día es", "que dia es",
                             "en qué fecha estamos", "fecha de hoy", "fecha actual",
                             "a qué día estamos"]):
        dia_semana = DIAS_FR[ahora.weekday()]
        mes = MESES_FR[ahora.month - 1]
        return f"Hoy es {dia_semana} {ahora.day} de {mes} de {ahora.year}, {NOMBRE_USUARIO}."

    if any(m in t for m in ["qué día", "que dia es", "dia de la semana"]) and "fecha" not in t:
        return f"Hoy es {DIAS_FR[ahora.weekday()]}, {NOMBRE_USUARIO}."

    if any(m in t for m in ["qué mes", "en qué mes estamos"]):
        return f"Estamos en {MESES_FR[ahora.month - 1]}, {NOMBRE_USUARIO}."

    if any(m in t for m in ["qué año", "en qué año estamos"]):
        return f"Estamos en {ahora.year}, {NOMBRE_USUARIO}."

    if any(m in t for m in ["qué edad tienes", "cuántos años tienes",
                             f"qué edad tiene {NOMBRE_USUARIO.lower()}",
                             f"que edad tiene {NOMBRE_USUARIO.lower()}"]):
        if EDAD_USUARIO:
            return f"Tienes {EDAD_USUARIO} años, {NOMBRE_USUARIO}."
        espera_edad = True
        return f"Todavía no sé tu edad, {NOMBRE_USUARIO}. ¿Cuál es?"

    if any(m in t for m in ["batería", "autonomía", "carga", "nivel de bateria"]):
        if psutil is None:
            return "El módulo psutil no está disponible, {NOMBRE_USUARIO}."
        try:
            bat = psutil.sensors_battery()
            if bat:
                pct = int(bat.percent)
                estado = "cargando" if bat.power_plugged else "con batería"
                return f"La batería está al {pct}%, {estado}, {NOMBRE_USUARIO}."
            return f"No detecto batería en este dispositivo, {NOMBRE_USUARIO}."
        except Exception:
            return f"No se pudo leer la batería, {NOMBRE_USUARIO}."

    if any(m in t for m in ["cpu", "procesador", "uso del procesador"]):
        if psutil is None:
            return f"El módulo psutil no está disponible, {NOMBRE_USUARIO}."
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            return f"El procesador está al {cpu}% de uso, {NOMBRE_USUARIO}."
        except Exception:
            return f"No se pudo leer el procesador, {NOMBRE_USUARIO}."

    if any(m in t for m in ["ram", "memoria ram", "memoria", "uso de memoria"]):
        if psutil is None:
            return f"El módulo psutil no está disponible, {NOMBRE_USUARIO}."
        try:
            mem = psutil.virtual_memory()
            usado = round(mem.used / (1024**3), 1)
            total = round(mem.total / (1024**3), 1)
            return f"La RAM está al {mem.percent}% — {usado} GB usados de {total} GB, {NOMBRE_USUARIO}."
        except Exception:
            return f"No se pudo leer la RAM, {NOMBRE_USUARIO}."

    if any(m in t for m in ["encendido desde", "uptime", "cuánto tiempo encendido"]):
        if psutil is None:
            return f"El módulo psutil no está disponible, {NOMBRE_USUARIO}."
        try:
            boot = datetime.fromtimestamp(psutil.boot_time())
            delta = ahora - boot
            horas = int(delta.total_seconds() // 3600)
            minutos = int((delta.total_seconds() % 3600) // 60)
            return f"El PC lleva encendido {horas}h{minutos:02d}, {NOMBRE_USUARIO}."
        except Exception:
            return None

    return None

def procesar_intencion_domotica_directa(texto: str):
    t = texto.lower().strip()

    es_on = any(w in t for w in ["enciende", "encender", "activa", "activar", "pon", "prende"])
    es_off = any(w in t for w in ["apaga", "apagar", "desactiva", "desactivar", "apague"])

    if not (es_on or es_off):
        return None

    estado = "on" if es_on else "off"
    verbo = "encendido" if es_on else "apagado"

    if any(k in t for k in ["todas las luces", "todas luces", "todo encender", "todo apagar"]):
        if PIEZAS_LUCES:
            for p, entity_id in PIEZAS_LUCES.items():
                try:
                    ha_luz(entity_id, estado)
                except Exception as e:
                    print(f"[DOMÓTICA DIRECTA] Error {p}: {e}")
            return f"He {verbo} todas las luces, {NOMBRE_USUARIO}."
        return f"No hay luces configuradas en Home Assistant, {NOMBRE_USUARIO}."

    if any(k in t for k in ["luz", "lámpara", "foco", "led"]):
        pieza_encontrada = None
        if PIEZAS_LUCES:
            for p in PIEZAS_LUCES.keys():
                if p.lower() in t:
                    pieza_encontrada = p
                    break

        if not pieza_encontrada:
            for p in ["salón", "dormitorio", "oficina", "cocina", "pasillo", "garaje", "terraza", "baño", "entrada"]:
                if p in t:
                    pieza_encontrada = p
                    break

        if pieza_encontrada:
            entity_id = PIEZAS_LUCES.get(pieza_encontrada, f"light.{pieza_encontrada}") if PIEZAS_LUCES else f"light.{pieza_encontrada}"
            try:
                ha_luz(entity_id, estado)
                return f"He {verbo} la luz del {pieza_encontrada}, {NOMBRE_USUARIO}."
            except Exception as e:
                print(f"[DOMÓTICA DIRECTA] Error {pieza_encontrada}: {e}")
                return f"Intenté activar la luz del {pieza_encontrada}, pero ocurrió un error con Home Assistant."

    if any(k in t for k in ["enchufe", "toma", "regleta"]):
        pieza_encontrada = None
        if PIEZAS_ENCHUFES:
            for p in PIEZAS_ENCHUFES.keys():
                if p.lower() in t:
                    pieza_encontrada = p
                    break
        if not pieza_encontrada:
            for p in ["salón", "dormitorio", "oficina", "cocina", "garaje"]:
                if p in t:
                    pieza_encontrada = p
                    break
        if pieza_encontrada:
            entity_id = PIEZAS_ENCHUFES.get(pieza_encontrada, f"switch.{pieza_encontrada}") if PIEZAS_ENCHUFES else f"switch.{pieza_encontrada}"
            try:
                ha_interruptor(entity_id, estado)
                return f"He {verbo} el enchufe del {pieza_encontrada}, {NOMBRE_USUARIO}."
            except Exception as e:
                print(f"[DOMÓTICA DIRECTA] Error enchufe {pieza_encontrada}: {e}")
                return f"Intenté activar el enchufe del {pieza_encontrada}, pero ocurrió un error."

    return None

async def pedir_ia(texto):
    global esta_pensando
    esta_pensando = True
    await enviar_estado_web("thinking")
    try:
        rep_loc = respuesta_local(texto)
        if rep_loc:
            return rep_loc

        rep_domo = procesar_intencion_domotica_directa(texto)
        if rep_domo:
            return rep_domo

        cfg_tono = _cargar_config()
        tono_agente = cfg_tono.get("agent_tone", "default")
        if tono_agente in ["astro", "spicy"]:
            etiqueta_modo = "Trash-Talk Astro" if tono_agente == "astro" else "Sin Filtro & Picante"
            print(f"[CEREBRO] Modo Tono '{etiqueta_modo}' activo — Redirigiendo a xAI Grok (Temp ~0.9)...")
            if not grok_cliente:
                return f"Atención {NOMBRE_USUARIO}, el modo '{etiqueta_modo}' requiere una clave API xAI (Grok) válida. Por favor, introduce tu clave API en el menú Tono / Personalidad."

            prompt_tono = PROMPT_MODO_ASTRO if tono_agente == "astro" else PROMPT_MODO_PICANTE
            from datetime import datetime as _dt_t
            _ahora_str = _dt_t.now().strftime("%A %d %B %Y a las %H:%M")
            prompt_completo = prompt_tono + f"\n\nInformación contextual: El usuario se llama {NOMBRE_USUARIO}. Hoy es {_ahora_str}."

            rep_tono = await pedir_grok(texto, system_prompt_override=prompt_completo, temperature_override=0.9)
            if rep_tono:
                return rep_tono
            print(f"[CEREBRO] Fallo de Grok para el modo {tono_agente}, cambio al pipeline por defecto.")

        async def _llamar_gemini():
            if not gemini_activo:
                raise Exception("Clave Gemini no configurada — agente ignorado")
            if not _gestor_cuotas.esta_disponible("gemini"):
                raise _ErrorCuotaExcedida(f"Gemini en cooldown ({_gestor_cuotas.cooldown_restante('gemini')}s)")
            print(f"[CEREBRO] Intentando con Gemini (Lista: {LISTA_MODELOS})...")
            temp_hist = historial + [types.Content(role="user", parts=[types.Part(text=texto)])]
            t_baja = texto.lower()
            palabras_clave_busqueda = ["busca en la web", "busca en internet", "buscar en internet",
                                       "busca en google", "investiga", "busca en línea"]
            usar_busqueda = any(kw in t_baja for kw in palabras_clave_busqueda)

            palabras_deporte_directo = ["partido", "resultado", "champions league", "liga de campeones", "copa america", "liga 1", "liga 2", "premier league", "liga", "serie a", "bundesliga", "mercado", "gol", "goles", "campeonato"]
            tiene_deporte_directo = any(kw in t_baja for kw in palabras_deporte_directo)

            palabras_tiempo_actual = ["ayer", "hoy", "esta noche", "en directo", "live", "ahora mismo"]
            tiene_tiempo_actual = any(kw in t_baja for kw in palabras_tiempo_actual)

            es_consulta_deporte = tiene_deporte_directo and tiene_tiempo_actual
            es_consulta_tiempo_real = any(kw in t_baja for kw in ["noticias", "actualidad", "clima", "temperatura", "qué pasa"])

            contexto_deporte = False
            try:
                for contenido in historial[-6:]:
                    if hasattr(contenido, "role") and contenido.role == "user":
                        for parte in getattr(contenido, "parts", []):
                            p_texto = getattr(parte, "text", "")
                            if p_texto:
                                p_baja = p_texto.lower()
                                if any(kw in p_baja for kw in ["partido", "resultado", "mundial", "fútbol", "deporte", "gol"]):
                                    contexto_deporte = True
            except Exception as e:
                print(f"[CEREBRO] Error analizando historial: {e}")

            palabras_seguimiento = ["quién", "cuál", "cuando", "portero", "jugador", "equipo", "gol", "partido", "resultado", "ganado", "perdido", "clasificación", "país", "españa", "francia", "argentina", "ayer", "mañana", "otra vez", "el cual"]
            tiene_seguimiento = any(kw in t_baja for kw in palabras_seguimiento)

            if (contexto_deporte and tiene_seguimiento) or es_consulta_deporte or es_consulta_tiempo_real:
                usar_busqueda = True
                print("[CEREBRO] Detección automática de consulta deportiva o en tiempo real (contexto incluido): activando Google Search.")

            herramientas_list = [types.Tool(google_search=types.GoogleSearch())] if usar_busqueda else None
            if usar_busqueda:
                print("[CEREBRO] Activando herramienta Google Search para esta petición.")
            else:
                print("[CEREBRO] Búsqueda desactivada (respuesta de memoria) para reducir latencia.")

            prompt_actual = construir_prompt_sistema(usar_busqueda)
            ultimo_error = None
            gemini_elegido = MODELOS_SELECCIONADOS.get("Gemini", "gemini-3.1-flash-lite")
            for nombre_modelo in [gemini_elegido]:
                try:
                    print(f"[CEREBRO] Probando modelo: {nombre_modelo} (Timeout 12s)")
                    respuesta = await asyncio.wait_for(
                        asyncio.to_thread(
                            cliente.models.generate_content,
                            model=nombre_modelo,
                            config=types.GenerateContentConfig(
                                system_instruction=prompt_actual,
                                temperature=0.7,
                                tools=herramientas_list,
                            ),
                            contents=temp_hist
                        ),
                        timeout=12.0
                    )
                    rep = respuesta.text
                    historial.append(types.Content(role="user", parts=[types.Part(text=texto)]))
                    historial.append(types.Content(role="model", parts=[types.Part(text=rep)]))
                    _guardar_intercambio_conv(texto, rep)
                    return rep
                except Exception as e:
                    if _gestor_cuotas.es_error_cuota(e):
                        _gestor_cuotas.marcar_cuota_excedida("gemini")
                        raise _ErrorCuotaExcedida(f"Gemini cuota en {nombre_modelo}: {e}")
                    print(f"[CEREBRO] Fallo {nombre_modelo}: {e}")
                    ultimo_error = e
                    continue
            raise ultimo_error or Exception("Todos los modelos Gemini han fallado")

        async def _llamar_grok():
            if not _gestor_cuotas.esta_disponible("grok"):
                raise _ErrorCuotaExcedida(f"Grok en cooldown ({_gestor_cuotas.cooldown_restante('grok')}s)")
            print("[CEREBRO] Intentando con Grok (xAI)...")
            rep_grok = await pedir_grok(texto)
            if not rep_grok:
                raise Exception("Grok no devolvió nada o está mal configurado")
            return rep_grok

        async def _llamar_openai():
            if not _gestor_cuotas.esta_disponible("openai"):
                raise _ErrorCuotaExcedida(f"ChatGPT en cooldown ({_gestor_cuotas.cooldown_restante('openai')}s)")
            print("[CEREBRO] Intentando con ChatGPT (OpenAI)...")
            rep_openai = await pedir_openai(texto)
            if not rep_openai:
                raise Exception("ChatGPT no devolvió nada o está mal configurado")
            return rep_openai

        async def _intentar_claude():
            if anthropic_cliente and _gestor_cuotas.esta_disponible("claude"):
                print("[CEREBRO] Intentando con Claude (Anthropic)...")
                try:
                    rep_claude = await pedir_claude(texto)
                    if rep_claude:
                        return rep_claude
                    print("[CEREBRO] Claude KO (respuesta vacía).")
                except _ErrorCuotaExcedida:
                    print(f"[CEREBRO] Claude cuota agotada — cooldown {_gestor_cuotas.cooldown_restante('claude')}s.")
                except Exception as e:
                    print(f"[CEREBRO] Claude error ({e}).")
            return None

        async def _intentar_gemini():
            if gemini_activo:
                try:
                    return await _llamar_gemini()
                except _ErrorCuotaExcedida as e:
                    print(f"[CEREBRO] Gemini cuota ({e}).")
                except Exception as e:
                    print(f"[CEREBRO] Gemini error ({e}).")
            return None

        async def _intentar_groq():
            if groq_cliente and _gestor_cuotas.esta_disponible("groq"):
                print("[CEREBRO] Intentando con Groq (Llama 3.3)...")
                try:
                    rep_groq = await pedir_groq(texto)
                    if rep_groq:
                        return rep_groq
                except _ErrorCuotaExcedida:
                    print(f"[CEREBRO] Groq cuota agotada — cooldown {_gestor_cuotas.cooldown_restante('groq')}s.")
                except Exception as e2:
                    print(f"[CEREBRO] Groq error ({e2}).")
            return None

        async def _intentar_grok():
            if grok_cliente and _gestor_cuotas.esta_disponible("grok"):
                try:
                    return await _llamar_grok()
                except _ErrorCuotaExcedida as e:
                    print(f"[CEREBRO] Grok cuota ({e}).")
                except Exception as e:
                    print(f"[CEREBRO] Grok error ({e}).")
            return None

        async def _intentar_mistral():
            if mistral_cliente and _gestor_cuotas.esta_disponible("mistral"):
                print("[CEREBRO] Intentando con Mistral (Large)...")
                try:
                    rep_mist = await pedir_mistral(texto)
                    if rep_mist:
                        return rep_mist
                except _ErrorCuotaExcedida:
                    print(f"[CEREBRO] Mistral cuota agotada — cooldown {_gestor_cuotas.cooldown_restante('mistral')}s.")
                except Exception as e2:
                    print(f"[CEREBRO] Mistral error ({e2}).")
            return None

        async def _intentar_openai():
            if openai_cliente and _gestor_cuotas.esta_disponible("openai"):
                print("[CEREBRO] Intentando con ChatGPT (OpenAI)...")
                try:
                    rep_op = await pedir_openai(texto)
                    if rep_op:
                        return rep_op
                except _ErrorCuotaExcedida:
                    print(f"[CEREBRO] ChatGPT cuota agotada — cooldown {_gestor_cuotas.cooldown_restante('openai')}s.")
                except Exception as e2:
                    print(f"[CEREBRO] ChatGPT error ({e2}).")
            return None

        async def _intentar_local_uncensored():
            print("[CEREBRO] Intentando con Modelo Local Uncensored (Astro vía Ollama)...")
            try:
                rep_unc = await pedir_ollama_uncensored(texto)
                if rep_unc:
                    return rep_unc
            except Exception as e_unc:
                print(f"[CEREBRO] Error Local Uncensored: {e_unc}")
            return None

        cfg = _cargar_config()
        cerebro_preferido = cfg.get("preferred_brain", "auto")

        orden = []
        if cerebro_preferido in ["local_uncensored", "ollama_astro"]:
            orden = ["local_uncensored", "gemini", "claude", "groq", "grok", "openai", "mistral"]
        elif cerebro_preferido == "gemini":
            orden = ["gemini", "claude", "groq", "grok", "openai", "mistral"]
        elif cerebro_preferido == "groq":
            orden = ["groq", "gemini", "claude", "grok", "openai", "mistral"]
        elif cerebro_preferido == "grok":
            orden = ["grok", "openai", "gemini", "claude", "groq", "mistral"]
        elif cerebro_preferido == "openai":
            orden = ["openai", "gemini", "claude", "groq", "grok", "mistral"]
        elif cerebro_preferido == "claude":
            orden = ["claude", "gemini", "groq", "grok", "openai", "mistral"]
        elif cerebro_preferido == "mistral":
            orden = ["mistral", "gemini", "claude", "groq", "grok", "openai"]
        else:
            cerebro = detectar_cerebro(texto)
            if cerebro == "GROK":
                orden = ["grok", "openai", "gemini", "claude", "groq", "mistral"]
            else:
                orden = ["gemini", "claude", "groq", "grok", "openai", "mistral"]

        for cerebro in orden:
            if cerebro == "local_uncensored":
                res = await _intentar_local_uncensored()
                if res:
                    return res
            elif cerebro == "gemini":
                res = await _intentar_gemini()
                if res:
                    return res
            elif cerebro == "claude":
                res = await _intentar_claude()
                if res:
                    return res
            elif cerebro == "groq":
                res = await _intentar_groq()
                if res:
                    return res
            elif cerebro == "grok":
                res = await _intentar_grok()
                if res:
                    return res
            elif cerebro == "openai":
                res = await _intentar_openai()
                if res:
                    return res
            elif cerebro == "mistral":
                res = await _intentar_mistral()
                if res:
                    return res

        t_baja = texto.lower()
        _palabras_tiempo = ["qué tiempo", "clima", "tiempo", "qué tiempo hace",
                            "tiempo que hace", "pronóstico", "va a llover",
                            "hace buen tiempo", "temperatura exterior",
                            "temperatura fuera", "cuántos grados fuera",
                            "hace calor", "hace frío", "cuántos grados"]
        _palabras_temp_int = ["temperatura", "hace calor", "hace frío",
                              "cuántos grados", "temperatura interior"]
        _palabras_casa = ["en casa", "dentro de casa", "interior"]
        _piezas_fallback = {k: k for k in PIEZAS_SENSORES.keys()}
        if "exterior" in _piezas_fallback:
            _piezas_fallback["fuera"] = "exterior"

        if any(m in t_baja for m in _palabras_tiempo):
            print("[CEREBRO] Consulta meteorológica detectada → Home Assistant weather.forecast")
            datos_meteo = obtener_meteo_estructurada(None)
            if datos_meteo:
                await enviar_meteo_web(datos_meteo)
            respuesta_ha = obtener_meteo_ha()
            if respuesta_ha:
                return respuesta_ha
            return obtener_meteo_actual(None)

        if any(m in t_baja for m in _palabras_temp_int):
            for palabra_pieza, clave_pieza in _piezas_fallback.items():
                if palabra_pieza in t_baja:
                    entity_id = PIEZAS_SENSORES.get(clave_pieza)
                    if entity_id:
                        print(f"[CEREBRO] Temp interior detectada → HA {entity_id}")
                        temp = ha_obtener_estado(entity_id)
                        hum_id = PIEZAS_HUMEDAD.get(clave_pieza)
                        hum = ha_obtener_estado(hum_id) if hum_id else None
                        await enviar_temp_pieza({
                            "piece": palabra_pieza,
                            "temperature": str(temp),
                            "humidite": str(hum) if hum else None,
                        })
                        return f"La temperatura en {palabra_pieza} es de {temp} grados."
            if any(m in t_baja for m in _palabras_casa):
                entity_id = PIEZAS_SENSORES.get("salón")
                if entity_id:
                    print(f"[CEREBRO] Temp interior 'en casa' → HA {entity_id}")
                    temp = ha_obtener_estado(entity_id)
                    hum_id = PIEZAS_HUMEDAD.get("salón")
                    hum = ha_obtener_estado(hum_id) if hum_id else None
                    await enviar_temp_pieza({
                        "piece": "salón",
                        "temperature": str(temp),
                        "humidite": str(hum) if hum else None,
                    })
                    return f"La temperatura en tu casa es de {temp} grados."

        if groq_cliente and _gestor_cuotas.esta_disponible("groq"):
            print("[CEREBRO] Cambiando a Groq (Llama 3.3).")
            try:
                rep_groq = await pedir_groq(texto)
                if rep_groq:
                    return rep_groq
            except _ErrorCuotaExcedida:
                print(f"[CEREBRO] Groq cuota agotada — cooldown {_gestor_cuotas.cooldown_restante('groq')}s.")
            except Exception as e2:
                print(f"[CEREBRO] Groq error ({e2}).")
        elif groq_cliente:
            print(f"[CEREBRO] Groq en cooldown ({_gestor_cuotas.cooldown_restante('groq')}s). Ignorado.")

        if grok_cliente and _gestor_cuotas.esta_disponible("grok"):
            print("[CEREBRO] Cambiando a Grok (xAI).")
            try:
                return await _llamar_grok()
            except _ErrorCuotaExcedida:
                print(f"[CEREBRO] Grok cuota agotada — cooldown {_gestor_cuotas.cooldown_restante('grok')}s.")
            except Exception as e2:
                print(f"[ERROR IA (Grok repliegue)] {e2}")
        elif grok_cliente:
            print(f"[CEREBRO] Grok en cooldown ({_gestor_cuotas.cooldown_restante('grok')}s). Ignorado.")

        if openai_cliente and _gestor_cuotas.esta_disponible("openai"):
            print("[CEREBRO] Cambiando a ChatGPT (OpenAI).")
            try:
                return await _llamar_openai()
            except _ErrorCuotaExcedida:
                print(f"[CEREBRO] ChatGPT cuota agotada — cooldown {_gestor_cuotas.cooldown_restante('openai')}s.")
            except Exception as e2:
                print(f"[ERROR IA (ChatGPT repliegue)] {e2}")
        elif openai_cliente:
            print(f"[CEREBRO] ChatGPT en cooldown ({_gestor_cuotas.cooldown_restante('openai')}s). Ignorado.")

        if mistral_cliente and _gestor_cuotas.esta_disponible("mistral"):
            print("[CEREBRO] Cambiando a Mistral (Large).")
            try:
                rep_mist = await pedir_mistral(texto)
                if rep_mist:
                    return rep_mist
            except _ErrorCuotaExcedida:
                print(f"[CEREBRO] Mistral cuota agotada — cooldown {_gestor_cuotas.cooldown_restante('mistral')}s.")
            except Exception as e2:
                print(f"[ERROR IA (Mistral repliegue)] {e2}")
        elif mistral_cliente:
            print(f"[CEREBRO] Mistral en cooldown ({_gestor_cuotas.cooldown_restante('mistral')}s). Ignorado.")

        print("[CEREBRO] Gemini y Grok KO. Intentando Ollama (local)...")
        rep_ollama = await pedir_ollama(texto)
        if rep_ollama:
            return rep_ollama

        if len(texto.split()) > 2:
            res_serp = buscar_web_serpapi(texto)
            if res_serp and "VOTRE_CLE" not in res_serp and "nada encontrado" not in res_serp and "error" not in res_serp.lower():
                return "Esto es lo que encontré en la web: " + res_serp

        _ninguna_api = (not gemini_activo and not groq_cliente and not grok_cliente and not anthropic_cliente)
        if _ninguna_api:
            return (
                "Estoy en línea {NOMBRE_USUARIO}, pero mis motores de inteligencia artificial aún no están configurados. "
                "Para liberar todo mi potencial, debes introducir tus claves API en el archivo .env. "
                "Visita el sitio TechEnClair — encontrarás una guía completa para obtenerlas gratuitamente. "
                "Mientras tanto, sigo disponible para todos tus comandos locales: domótica, hora, cálculos, y mucho más."
            )
        return (
            f"Lo siento {NOMBRE_USUARIO}, todos mis servidores de reflexión están actualmente sobrecargados o en mantenimiento, "
            "y mis modelos locales no responden tampoco. "
            "Sigo disponible para tus comandos domóticos y locales. "
            "Si el problema persiste, verifica tus claves API en techenclair.fr."
        )
    finally:
        esta_pensando = False
        await enviar_estado_web("idle")

async def pedir_ia_vision(texto, img_b64):
    global esta_pensando, historial, NOMBRE_USUARIO
    if not gemini_activo or cliente is None:
        return "La visión requiere una clave Gemini válida. Configúrala en el archivo .env."
    esta_pensando = True
    await enviar_estado_web("thinking")
    try:
        print("[VISIÓN] Analizando imagen con Gemini...")

        img_bytes = base64.b64decode(img_b64)
        parte_imagen = types.Part.from_bytes(
            data=img_bytes,
            mime_type="image/jpeg"
        )

        prompt_actual = construir_prompt_sistema()

        es_consulta_moda = any(kw in texto.lower() for kw in [
            "atuendo", "vestimenta", "vestido", "estilo", "look", "moda",
            "elegante", "llevar", "qué llevar", "traje", "ropa"
        ])

        if es_consulta_moda:
            prompt_actual += (
                f"\n\nIMPORTANTE: Eres el experto en moda y estilista personal de {NOMBRE_USUARIO}. "
                "Analiza en detalle su atuendo, la armonía de colores, los cortes y los posibles accesorios visibles "
                "en la imagen de la cámara. Dile claramente y con elegancia si va bien vestido. "
                "Proporciónale consejos de estilo constructivos y refinados para perfeccionar su look (accesorios, calzado, combinación de colores, etc.). "
                "Tu tono debe ser muy elegante, chic y digno de un gran diseñador. "
                "No uses caracteres markdown como asteriscos o almohadillas, ya que tu respuesta se leerá en voz alta."
            )
        else:
            prompt_actual += f"\n\nIMPORTANTE: Acabas de recibir una captura de pantalla de {NOMBRE_USUARIO}. Analízala atentamente y responde a su pregunta basándote en lo que ves."

        contenidos = [
            types.Content(role="user", parts=[parte_imagen, types.Part(text=texto)])
        ]

        rep = None
        ultimo_error = None
        gemini_elegido = MODELOS_SELECCIONADOS.get("Gemini", "gemini-3.1-flash-lite")
        for nombre_modelo in [gemini_elegido]:
            print(f"[VISIÓN] Probando modelo: {nombre_modelo}")
            for intento in range(2):
                try:
                    print(f"[VISIÓN] Llamando modelo: {nombre_modelo} (Timeout 15s)")
                    respuesta = await asyncio.wait_for(
                        asyncio.to_thread(
                            cliente.models.generate_content,
                            model=nombre_modelo,
                            config=types.GenerateContentConfig(
                                system_instruction=prompt_actual,
                                temperature=0.7,
                                tools=None,
                            ),
                            contents=contenidos
                        ),
                        timeout=15.0
                    )
                    rep = respuesta.text
                    break
                except Exception as e:
                    if ("503" in str(e) or "overloaded" in str(e).lower()) and intento < 1:
                        print(f"[VISIÓN] Sobrecarga {nombre_modelo} (503). Reintentando...")
                        await asyncio.sleep(1)
                        continue
                    print(f"[VISIÓN] Error {nombre_modelo}: {e}")
                    ultimo_error = e
                    break
            if rep:
                break

        if not rep:
            err_str = str(ultimo_error).lower() if ultimo_error else ""
            if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                print("[VISIÓN] Cuota Gemini agotada — visión imposible sin Gemini.")
                return (f"Lo siento {NOMBRE_USUARIO}, mi cuota Gemini está agotada por hoy. "
                        "La visión por cámara y pantalla funciona únicamente con Gemini — "
                        "no puedo analizar imágenes en este momento. "
                        "Vuelve a intentarlo mañana cuando se restablezca la cuota.")
            print("[VISIÓN] Todos los modelos Gemini han fallado. Cambiando a Grok (Solo texto)...")
            if grok_cliente:
                return await pedir_grok(texto + " (Nota: No pude ver tu pantalla porque mis servidores de visión no están disponibles, así que respondo solo a tu texto).")
            raise ultimo_error or Exception("Ningún modelo pudo analizar la imagen")

        historial.append(types.Content(role="user", parts=[types.Part(text=f"[Análisis de pantalla] {texto}")]))
        historial.append(types.Content(role="model", parts=[types.Part(text=rep)]))

        return rep
    except Exception as e:
        print(f"[VISIÓN] Error Gemini Vision: {e}")
        err_msg = str(e).replace("{", "[").replace("}", "]")
        return f"Lo siento {NOMBRE_USUARIO}, no pude analizar tu pantalla. Error: {err_msg}"
    finally:
        esta_pensando = False
        await enviar_estado_web("idle")

builtins.pedir_ia_vision = pedir_ia_vision

def detectar_cerebro(texto):
    palabras_clave_grok = ["en x", "twitter", "grok", "elon", "x.com"]
    cmd = texto.lower()
    if any(m in cmd for m in palabras_clave_grok):
        return "GROK"
    return "GEMINI"

async def pedir_openai(texto):
    if not openai_cliente:
        return None

    try:
        prompt_sistema = construir_prompt_sistema()
        from datetime import datetime as _dt_openai
        _ahora_str = _dt_openai.now().strftime("%A %d %B %Y a las %H:%M")
        prompt_sistema += f"\n\n🕒 CONTEXTO TEMPORAL: Hoy es {_ahora_str}. Tenlo en cuenta para todas tus respuestas (noticias, partidos, eventos del día, etc.). Atención: no tienes acceso a internet, no inventes información que no sepas con certeza."
        mensajes = [{"role": "system", "content": prompt_sistema}]

        for h in historial[-30:]:
            rol = "user" if h.role == "user" else "assistant"
            msg_text = h.parts[0].text
            mensajes.append({"role": rol, "content": msg_text})

        mensajes.append({"role": "user", "content": texto})

        openai_elegido = MODELOS_SELECCIONADOS.get("ChatGPT", "gpt-5.6-sol")
        _modelos_openai = [openai_elegido]
        completion = None
        ultimo_error_openai = None
        for _om in _modelos_openai:
            try:
                kwargs = {
                    "model": _om,
                    "messages": mensajes
                }
                es_razonamiento = _om.startswith("o") or any(x in _om.lower() for x in ["luna", "sol", "terra"])
                if not es_razonamiento:
                    kwargs["max_tokens"] = 2048
                    kwargs["temperature"] = 0.7

                try:
                    completion = openai_cliente.chat.completions.create(**kwargs)
                except Exception as api_e:
                    if "max_tokens" in str(api_e) and "max_completion_tokens" in str(api_e):
                        kwargs.pop("max_tokens", None)
                        kwargs.pop("temperature", None)
                        if not es_razonamiento:
                            kwargs["max_completion_tokens"] = 2048
                        completion = openai_cliente.chat.completions.create(**kwargs)
                    else:
                        raise api_e

                if completion and completion.choices:
                    break
            except Exception as e_mod:
                print(f"[OPENAI] Error con el modelo {_om}: {e_mod}")
                ultimo_error_openai = e_mod
                if "429" in str(e_mod) or "quota" in str(e_mod).lower() or "rate limit" in str(e_mod).lower():
                    _gestor_cuotas.marcar_cuota_excedida("openai")
                    raise _ErrorCuotaExcedida(str(e_mod))

        if completion and completion.choices:
            rep = completion.choices[0].message.content
            historial.append(types.Content(role="user", parts=[types.Part(text=texto)]))
            historial.append(types.Content(role="model", parts=[types.Part(text=rep)]))
            _guardar_intercambio_conv(texto, rep)
            return rep
        else:
            if ultimo_error_openai:
                raise ultimo_error_openai
            return None

    except _ErrorCuotaExcedida as qe:
        raise qe
    except Exception as e:
        print(f"[ERROR CHATGPT] {e}")
        return None

async def pedir_grok(texto, system_prompt_override=None, temperature_override=None):
    if not grok_cliente:
        return None

    try:
        if system_prompt_override:
            prompt_sistema = system_prompt_override
        else:
            prompt_sistema = construir_prompt_sistema()
            from datetime import datetime as _dt_grok
            _ahora_str = _dt_grok.now().strftime("%A %d %B %Y a las %H:%M")
            prompt_sistema += f"\n\n⚠️ CONTEXTO TEMPORAL: Hoy es {_ahora_str}. Tenlo en cuenta para todas tus respuestas (noticias, partidos, eventos del día, etc.). Atención: no tienes acceso a internet, no inventes información que no sepas con certeza."

        mensajes = [{"role": "system", "content": prompt_sistema}]

        for h in historial[-30:]:
            rol = "user" if h.role == "user" else "assistant"
            msg_text = h.parts[0].text
            mensajes.append({"role": rol, "content": msg_text})

        mensajes.append({"role": "user", "content": texto})

        grok_elegido = MODELOS_SELECCIONADOS.get("Grok", "grok-2")
        _modelos_grok = [grok_elegido, "grok-2", "grok-beta", "grok-2-latest", "grok-4.5"]
        _modelos_grok = list(dict.fromkeys(_modelos_grok))

        temp_val = temperature_override if temperature_override is not None else 0.7
        completion = None
        ultimo_error_grok = None
        for _gm in _modelos_grok:
            try:
                completion = grok_cliente.chat.completions.create(
                    model=_gm,
                    messages=mensajes,
                    temperature=temp_val,
                )
                print(f"[GROK] Modelo usado: {_gm} (Temperature: {temp_val})")
                break
            except Exception as _gm_err:
                print(f"[GROK] Modelo {_gm} no disponible: {_gm_err}")
                ultimo_error_grok = _gm_err
                continue
        if completion is None:
            raise ultimo_error_grok or Exception("Ningún modelo Grok disponible")

        rep = completion.choices[0].message.content

        historial.append(types.Content(role="user", parts=[types.Part(text=texto)]))
        historial.append(types.Content(role="model", parts=[types.Part(text=rep)]))
        _guardar_intercambio_conv(texto, rep)

        return rep
    except Exception as e:
        if _gestor_cuotas.es_error_cuota(e):
            _gestor_cuotas.marcar_cuota_excedida("grok")
            raise _ErrorCuotaExcedida(f"Grok cuota: {e}")
        print(f"[ERROR GROK] {e}")
        return None

async def manejar_resultado_imagen_global(resultado_img, prompt_fr):
    import json
    if resultado_img and "error" not in resultado_img:
        fuente_modelo = resultado_img.get("source", "Desconocido")
        await hablar(f"Esta es la imagen generada con {fuente_modelo}. He guardado la imagen en mi carpeta OMEGA directamente.")
        if CLIENTES_CONECTADOS:
            try:
                msg_img = json.dumps({
                    "type": "show_generated_image",
                    "url": resultado_img["url"],
                    "prompt": prompt_fr,
                    "source": fuente_modelo
                })
                await asyncio.gather(*[ws.send(msg_img) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            except Exception:
                pass
    else:
        err = resultado_img.get("error", "Error desconocido.") if resultado_img else "Fallo en la generación."
        await hablar(f"Lo siento {NOMBRE_USUARIO}, no pude generar la imagen. {err}")

async def generar_imagen_xai(prompt: str, force_model: str = None) -> dict:
    import base64
    import time as _time

    if not grok_cliente and not (cliente and gemini_activo):
        return {"error": "Ningún cliente configurado para la generación de imágenes."}

    _prompt_en = prompt
    try:
        if cliente and gemini_activo:
            enrich_resp = await asyncio.to_thread(
                cliente.models.generate_content,
                model="gemini-2.5-flash",
                contents=f"Traduce este prompt a un prompt en inglés muy detallado para una IA de generación de imágenes. Devuelve SOLO el prompt en inglés, nada más: {prompt}",
            )
            _prompt_en = enrich_resp.text.strip()
            print(f"[IMAGEN_GEN] Prompt enriquecido: {_prompt_en[:100]}...")
    except Exception as _e:
        print(f"[IMAGEN_GEN] Enriquecimiento ignorado: {_e}")

    cfg = _cargar_config()
    pref = cfg.get("preferred_brain", "auto")
    usar_grok_primero = (pref == "grok")
    if force_model == "grok":
        usar_grok_primero = True
    elif force_model in ["gemini", "gemini_flash_lite"]:
        usar_grok_primero = False

    async def _intentar_xai():
        if grok_cliente:
            for _modelo_xai in ["grok-imagine-image", "grok-imagine-quality"]:
                try:
                    print(f"[IMAGEN_GEN] Intentando con {_modelo_xai}...")
                    response = await asyncio.to_thread(
                        grok_cliente.images.generate,
                        model=_modelo_xai,
                        prompt=_prompt_en,
                        n=1,
                        response_format="b64_json",
                    )
                    img_data = response.data[0]
                    if hasattr(img_data, 'b64_json') and img_data.b64_json:
                        ts = int(_time.time() * 1000)
                        img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"omega_xai_{ts}.png")
                        with open(img_path, "wb") as _f:
                            _f.write(base64.b64decode(img_data.b64_json))
                        data_url = f"data:image/png;base64,{img_data.b64_json}"
                        print(f"[IMAGEN_GEN] ✅ Imagen generada vía {_modelo_xai} ({len(img_data.b64_json)//1024} KB).")
                        return {"url": data_url, "path": img_path, "prompt_fr": prompt, "prompt_en": _prompt_en, "source": f"xAI ({_modelo_xai})"}
                    elif hasattr(img_data, 'url') and img_data.url:
                        return {"url": img_data.url, "prompt_fr": prompt, "prompt_en": _prompt_en, "source": f"xAI ({_modelo_xai})"}
                except Exception as _xai_err:
                    print(f"[IMAGEN_GEN] {_modelo_xai} falló: {_xai_err}")
        return None

    async def _intentar_openai():
        if openai_cliente:
            modelo_a_usar = "gpt-image-2"
            try:
                print(f"[IMAGEN_GEN] Intentando con OpenAI (ChatGPT - {modelo_a_usar})...")
                response = await asyncio.to_thread(
                    openai_cliente.images.generate,
                    model=modelo_a_usar,
                    prompt=_prompt_en,
                    n=1,
                    size="1024x1024"
                )
                img_data = response.data[0]
                import time as _time
                import os
                import base64
                ts = int(_time.time() * 1000)
                img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"omega_openai_{ts}.png")

                if hasattr(img_data, "b64_json") and img_data.b64_json:
                    with open(img_path, "wb") as _f:
                        _f.write(base64.b64decode(img_data.b64_json))
                    data_url = f"data:image/png;base64,{img_data.b64_json}"
                    print(f"[IMAGEN_GEN] o. Imagen generada vía {modelo_a_usar}.")
                    return {"url": data_url, "path": img_path, "prompt_fr": prompt, "prompt_en": _prompt_en, "source": "ChatGPT (gpt-image-2)"}
                elif hasattr(img_data, "url") and img_data.url:
                    import requests
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    img_resp = await asyncio.to_thread(requests.get, img_data.url, headers=headers, timeout=30)
                    img_resp.raise_for_status()
                    with open(img_path, "wb") as _f:
                        _f.write(img_resp.content)
                    b64_str = base64.b64encode(img_resp.content).decode('utf-8')
                    data_url = f"data:image/png;base64,{b64_str}"
                    print(f"[IMAGEN_GEN] o. Imagen generada vía {modelo_a_usar}.")
                    return {"url": data_url, "path": img_path, "prompt_fr": prompt, "prompt_en": _prompt_en, "source": "ChatGPT (gpt-image-2)"}
            except Exception as _err:
                print(f"[IMAGEN_GEN] Error OpenAI: {_err}")
        return None

    async def _intentar_gemini():
        modelo_a_usar = "imagen-4.0-generate-001" if force_model == "gemini" else "gemini-3.1-flash-lite-image"
        nombre_mostrar = "Imagen 4 (Google)" if force_model == "gemini" else "Gemini 3.1 Flash Lite Imagen"
        try:
            print(f"[IMAGEN] Generando vía {nombre_mostrar}...")
            img_bytes = None

            if modelo_a_usar == "gemini-3.1-flash-lite-image":
                resp = await asyncio.to_thread(
                    cliente.models.generate_content,
                    model=modelo_a_usar,
                    contents=_prompt_en,
                    config=types.GenerateContentConfig(
                        response_modalities=[types.Modality.TEXT, types.Modality.IMAGE],
                    ),
                )
                if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
                    for parte in resp.candidates[0].content.parts:
                        if parte.inline_data:
                            img_bytes = parte.inline_data.data
                            break
            else:
                respuesta_imagen = await asyncio.to_thread(
                    cliente.models.generate_images,
                    model=modelo_a_usar,
                    prompt=_prompt_en,
                    config={"number_of_images": 1},
                )
                if respuesta_imagen.generated_images:
                    img_bytes = respuesta_imagen.generated_images[0].image.image_bytes

            if img_bytes:
                import base64
                import time as _time
                import os
                b64_str = base64.b64encode(img_bytes).decode("utf-8")
                ts = int(_time.time() * 1000)
                img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"omega_imagen_{ts}.png")
                with open(img_path, "wb") as _f:
                    _f.write(img_bytes)
                data_url = f"data:image/png;base64,{b64_str}"
                print(f"[IMAGEN] o. Imagen generada vía {nombre_mostrar} ({len(b64_str)//1024} KB).")
                return {"url": data_url, "path": img_path, "prompt_fr": prompt, "prompt_en": _prompt_en, "source": nombre_mostrar}
        except Exception as _img_err:
            print(f"[IMAGEN] Error Gemini: {_img_err}")
        return None

    if force_model == "openai":
        res = await _intentar_openai()
        if res:
            return res
        res = await _intentar_xai()
        if res:
            return res
        res = await _intentar_gemini()
        if res:
            return res
    elif force_model == "grok" or usar_grok_primero:
        res = await _intentar_xai()
        if res:
            return res
        res = await _intentar_gemini()
        if res:
            return res
        res = await _intentar_openai()
        if res:
            return res
    else:
        res = await _intentar_gemini()
        if res:
            return res
        res = await _intentar_openai()
        if res:
            return res
        res = await _intentar_xai()
        if res:
            return res

    return {"error": "Ningún motor de generación de imágenes disponible."}

async def generar_video_xai(prompt: str) -> dict:
    import base64
    import time as _time

    if not grok_cliente:
        return {"error": "Cliente xAI no disponible."}

    _prompt_en = prompt
    try:
        enrich_resp = grok_cliente.chat.completions.create(
            model="grok-4.3",
            messages=[{"role": "user", "content": (
                "Traduce y mejora este prompt de generación de vídeo al inglés. "
                "Hazlo muy cinematográfico, detallado, con descripción de movimiento. Devuelve SOLO el prompt en inglés.\n\n"
                f"Prompt original en español: {prompt}"
            )}],
            temperature=0.7,
            max_tokens=200,
        )
        _prompt_en = enrich_resp.choices[0].message.content.strip()
        print(f"[VIDEO_GEN] Prompt enriquecido: {_prompt_en[:100]}...")
    except Exception as _e:
        print(f"[VIDEO_GEN] Enriquecimiento ignorado: {_e}")

    for _modelo_vid in ["grok-imagine-video", "grok-imagine-video-1"]:
        try:
            print(f"[VIDEO_GEN] Intentando con {_modelo_vid}...")
            response = await asyncio.to_thread(
                grok_cliente.videos.generate,
                model=_modelo_vid,
                prompt=_prompt_en,
            )
            vid_data = response.data[0] if hasattr(response, 'data') else response

            if hasattr(vid_data, 'url') and vid_data.url:
                print(f"[VIDEO_GEN] ✅ Vídeo generado vía {_modelo_vid}.")
                return {"url": vid_data.url, "prompt_fr": prompt, "prompt_en": _prompt_en, "source": f"xAI ({_modelo_vid})", "type": "video"}
            elif hasattr(vid_data, 'b64_json') and vid_data.b64_json:
                ts = int(_time.time() * 1000)
                vid_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"omega_video_{ts}.mp4")
                with open(vid_path, "wb") as _f:
                    _f.write(base64.b64decode(vid_data.b64_json))
                data_url = f"data:video/mp4;base64,{vid_data.b64_json}"
                print(f"[VIDEO_GEN] ✅ Vídeo generado vía {_modelo_vid}.")
                return {"url": data_url, "path": vid_path, "prompt_fr": prompt, "prompt_en": _prompt_en, "source": f"xAI ({_modelo_vid})", "type": "video"}
        except Exception as _vid_err:
            print(f"[VIDEO_GEN] {_modelo_vid} falló: {_vid_err}")

    return {"error": "Generación de vídeo fallida. Verifica tu acceso a los modelos grok-imagine-video."}

async def pedir_ollama(texto):
    global historial
    try:
        prompt_sistema = construir_prompt_sistema()
        mensajes = [{"role": "system", "content": prompt_sistema}]

        for h in historial[-8:]:
            rol = "user" if h.role == "user" else "assistant"
            mensajes.append({"role": rol, "content": h.parts[0].text})
        mensajes.append({"role": "user", "content": texto})

        ultimo_error = None
        ollama_elegido = MODELOS_SELECCIONADOS.get("Ollama", "dolphin3")
        for nombre_modelo in [ollama_elegido]:
            try:
                print(f"[OLLAMA] Probando modelo local: {nombre_modelo}")
                opciones = _obtener_opciones_ollama_para_modelo(nombre_modelo)
                resp = await asyncio.wait_for(
                    asyncio.to_thread(
                        requests.post,
                        f"{OLLAMA_URL}/api/chat",
                        json={"model": nombre_modelo, "messages": mensajes, "stream": False, "keep_alive": -1, "options": opciones},
                        timeout=90
                    ),
                    timeout=95.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    rep = data.get("message", {}).get("content", "")
                    if rep:
                        historial.append(types.Content(role="user", parts=[types.Part(text=texto)]))
                        historial.append(types.Content(role="model", parts=[types.Part(text=rep)]))
                        _guardar_intercambio_conv(texto, rep)
                        print(f"[OLLAMA] Respuesta recibida de {nombre_modelo}")
                        return rep
                else:
                    print(f"[OLLAMA] Error HTTP {resp.status_code} para {nombre_modelo}")
                    ultimo_error = Exception(f"HTTP {resp.status_code}")
            except Exception as e:
                print(f"[OLLAMA] Fallo {nombre_modelo}: {e}")
                ultimo_error = e
                continue

        print(f"[OLLAMA] Todos los modelos locales han fallado")
        return None
    except Exception as e:
        print(f"[ERROR OLLAMA] {e}")
        return None

def _obtener_opciones_ollama_para_modelo(nombre_modelo: str) -> dict:
    import os
    num_threads = os.cpu_count() or 8
    m_bajo = nombre_modelo.lower()

    if "phi3.5" in m_bajo or "phi-3.5" in m_bajo or "phi3" in m_bajo:
        num_ctx = 4096
    elif "llama3.1" in m_bajo or "llama-3.1" in m_bajo:
        num_ctx = 8192
    else:
        num_ctx = 6144

    return {
        "num_gpu": 99,
        "num_batch": 512,
        "num_thread": num_threads,
        "num_ctx": num_ctx,
        "num_predict": 512,
        "temperature": 0.7,
        "top_p": 0.9,
        "repeat_penalty": 1.1,
    }

def _verificar_estado_ollama():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if r.status_code == 200:
            modelos_data = r.json().get("models", [])
            instalados = [m.get("name", "") for m in modelos_data]

            locales_conocidos = {
                "dolphin3": ["dolphin", "hermes", "uncensored", "wizardlm-uncensored"],
                "phi3.5": ["phi3.5", "phi-3.5", "phi3:mini", "phi3"],
                "llama3.1:8b": ["llama3.1", "llama3.1:8b", "llama-3.1"]
            }
            modelos_encontrados = {}
            encontrado_uncensored = None

            for m in instalados:
                m_bajo = m.lower()
                for model_id, palabras_clave in locales_conocidos.items():
                    if any(palabra in m_bajo for palabra in palabras_clave):
                        modelos_encontrados[model_id] = m
                        if model_id == "dolphin3" and encontrado_uncensored is None:
                            encontrado_uncensored = m
                        break

            return {
                "online": True,
                "installed_models": instalados,
                "found_local_models": modelos_encontrados,
                "has_uncensored_model": (encontrado_uncensored is not None),
                "uncensored_model_name": encontrado_uncensored
            }
    except Exception as e:
        print(f"[OLLAMA CHECK] Servicio fuera de línea o no disponible: {e}")
    return {
        "online": False,
        "installed_models": [],
        "found_local_models": {},
        "has_uncensored_model": False,
        "uncensored_model_name": None
    }

def _encontrar_modelo_ollama_uncensored():
    cfg = _cargar_config()
    preferred_local = cfg.get("preferred_local_model", "dolphin3")
    st = _verificar_estado_ollama()
    modelos_encontrados = st.get("found_local_models", {})

    if preferred_local in modelos_encontrados:
        nombre_modelo = modelos_encontrados[preferred_local]
        print(f"[OLLAMA UNCENSORED] Modelo preferido encontrado: {nombre_modelo} (id={preferred_local})")
        return nombre_modelo

    for fallback_id in ["dolphin3", "phi3.5", "llama3.1:8b"]:
        if fallback_id in modelos_encontrados:
            nombre_modelo = modelos_encontrados[fallback_id]
            print(f"[OLLAMA UNCENSORED] Fallback a modelo instalado: {nombre_modelo}")
            return nombre_modelo

    if st.get("installed_models"):
        return st.get("installed_models")[0]

    return preferred_local

def _descargar_modelo_ollama(nombre_modelo, bucle, websocket):
    import json as _j

    def _enviar(status_msg, pct=0, done=False, success=True):
        asyncio.run_coroutine_threadsafe(
            websocket.send(_j.dumps({
                "type": "ollama_pull_progress",
                "status": status_msg,
                "pct": pct,
                "done": done,
                "success": success
            })), bucle
        )
    try:
        _enviar(f"▶ Iniciando descarga de {nombre_modelo} vía Ollama...", pct=1)
        r = requests.post(f"{OLLAMA_URL}/api/pull", json={"name": nombre_modelo}, stream=True, timeout=1800)
        if r.status_code == 200:
            for linea in r.iter_lines():
                if linea:
                    try:
                        data = _j.loads(linea.decode('utf-8'))
                        status_str = data.get("status", "")
                        completado = data.get("completed", 0)
                        total = data.get("total", 0)
                        pct = 0
                        if total > 0 and completado > 0:
                            pct = min(99, int((completado / total) * 100))

                        if completado and total:
                            mb_hecho = int(completado / (1024 * 1024))
                            mb_total = int(total / (1024 * 1024))
                            _enviar(f"📥 {status_str} ({mb_hecho} MB / {mb_total} MB)", pct=pct)
                        else:
                            _enviar(f"📥 {status_str}", pct=pct)
                    except Exception:
                        pass
            _enviar(f"✅ Modelo {nombre_modelo} descargado y listo para usar.", pct=100, done=True, success=True)
        else:
            _enviar(f"❌ Error HTTP {r.status_code} durante la descarga de Ollama.", pct=0, done=True, success=False)
    except Exception as e:
        _enviar(f"❌ Excepción durante pull de Ollama: {e}", pct=0, done=True, success=False)

# =============================================================================
# KOKORO-TTS LOCAL (SÍNTESIS DE VOZ ULTRARREALISTA 100% OFFLINE)
# =============================================================================

_INSTANCIA_KOKORO_ONNX = None

def _verificar_estado_kokoro():
    try:
        r = requests.get(f"{KOKORO_URL}/v1/models", timeout=2)
        if r.status_code == 200:
            return {"online": True, "installed": True, "type": "api"}
    except Exception:
        pass
    try:
        r = requests.get(f"{KOKORO_URL}/", timeout=2)
        if r.status_code in [200, 404, 405]:
            return {"online": True, "installed": True, "type": "api"}
    except Exception:
        pass

    try:
        import kokoro_onnx
        return {"online": True, "installed": True, "type": "onnx"}
    except ImportError:
        pass

    try:
        import kokoro
        return {"online": True, "installed": True, "type": "kokoro"}
    except ImportError:
        pass

    return {"online": False, "installed": False}

def _instalar_kokoro_tts(bucle, websocket):
    import json as _j
    import subprocess
    import sys

    def _enviar(status_msg, pct=0, done=False, success=True):
        asyncio.run_coroutine_threadsafe(
            websocket.send(_j.dumps({
                "type": "kokoro_install_progress",
                "status": status_msg,
                "pct": pct,
                "done": done,
                "success": success
            })), bucle
        )
    try:
        _enviar("▶ Iniciando instalación de Kokoro-TTS Local...", pct=10)
        cmd = [sys.executable, "-m", "pip", "install", "kokoro-onnx", "soundfile"]
        _enviar("📦 Instalando paquetes Python (kokoro-onnx, soundfile)...", pct=35)
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode == 0:
            _enviar("📥 Descargando y verificando paquetes Kokoro...", pct=75)
            try:
                import kokoro_onnx
                _enviar("✅ Kokoro-TTS Local instalado con éxito.", pct=100, done=True, success=True)
            except Exception as e:
                _enviar(f"⚠️ Paquetes instalados, listos para usar.", pct=100, done=True, success=True)
        else:
            _enviar(f"❌ Error instalación pip: {proc.stderr[:120]}", pct=0, done=True, success=False)
    except Exception as e:
        _enviar(f"❌ Excepción durante instalación Kokoro: {e}", pct=0, done=True, success=False)

async def _kokoro_tts_a_archivo(texto: str, nombre_voz: str, archivo_salida: str) -> bool:
    voz_limpia = nombre_voz.replace("kokoro_", "")
    if not voz_limpia:
        voz_limpia = "ff_siwis"

    try:
        payload = {
            "model": "kokoro",
            "input": texto,
            "voice": voz_limpia,
            "response_format": "mp3" if archivo_salida.endswith(".mp3") else "wav"
        }
        resp = await asyncio.wait_for(
            asyncio.to_thread(
                requests.post,
                f"{KOKORO_URL}/v1/audio/speech",
                json=payload,
                timeout=10
            ),
            timeout=12.0
        )
        if resp.status_code == 200 and resp.content:
            with open(archivo_salida, "wb") as f:
                f.write(resp.content)
            print(f"[KOKORO TTS API] ✅ Audio generado vía Kokoro HTTP API ({voz_limpia}).")
            return True
    except Exception:
        pass

    try:
        def _sintetizar_onnx():
            from kokoro_onnx import Kokoro
            global _INSTANCIA_KOKORO_ONNX
            if _INSTANCIA_KOKORO_ONNX is None:
                import os
                carpeta_modelo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kokoro_model")
                os.makedirs(carpeta_modelo, exist_ok=True)
                ruta_onnx = os.path.join(carpeta_modelo, "kokoro-v1.0.onnx")
                voces_bin = os.path.join(carpeta_modelo, "voices-v1.0.bin")
                voces_json = os.path.join(carpeta_modelo, "voices.json")

                import urllib.request
                if not os.path.exists(ruta_onnx):
                    print("[KOKORO TTS] Descargando modelo kokoro-v1.0.onnx (~300 MB)...")
                    urllib.request.urlretrieve("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx", ruta_onnx)
                if not (os.path.exists(voces_bin) or os.path.exists(voces_json)):
                    print("[KOKORO TTS] Descargando archivo de voces voices-v1.0.bin...")
                    try:
                        urllib.request.urlretrieve("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin", voces_bin)
                    except Exception:
                        urllib.request.urlretrieve("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json", voces_json)

                archivo_voces = voces_bin if os.path.exists(voces_bin) else voces_json
                _INSTANCIA_KOKORO_ONNX = Kokoro(ruta_onnx, archivo_voces)

            idioma = "fr-fr"
            if voz_limpia.startswith(("af_", "am_")):
                idioma = "en-us"
            elif voz_limpia.startswith(("bf_", "bm_")):
                idioma = "en-gb"
            elif voz_limpia.startswith(("es_", "ef_", "em_")):
                idioma = "es"
            elif voz_limpia.startswith(("it_", "if_", "im_")):
                idioma = "it"

            muestras, sample_rate = _INSTANCIA_KOKORO_ONNX.create(texto, voice=voz_limpia, speed=1.0, lang=idioma)
            import soundfile as sf
            sf.write(archivo_salida, muestras, sample_rate)
            return True

        ok = await asyncio.to_thread(_sintetizar_onnx)
        if ok:
            print(f"[KOKORO TTS ONNX] ✅ Audio generado vía kokoro-onnx ({voz_limpia}).")
            return True
    except Exception as e_onnx:
        print(f"[KOKORO TTS ONNX] {e_onnx}")

    return False

async def pedir_ollama_uncensored(texto):
    global historial, _MODELO_OLLAMA_CARGADO

    if not _MODELO_OLLAMA_CARGADO:
        await hablar(f"Un momento {NOMBRE_USUARIO}, estoy cargando el modelo local en memoria de vídeo. Por favor, espera unos segundos...")

    try:
        from datetime import datetime as _dt_ollama
        _ahora_str = _dt_ollama.now().strftime("%A %d %B %Y a las %H:%M")

        cfg_tono = _cargar_config()
        tono = cfg_tono.get("agent_tone", "default")

        if tono == "astro":
            prompt_base = PROMPT_MODO_ASTRO
        elif tono == "spicy":
            prompt_base = PROMPT_MODO_PICANTE
        else:
            prompt_base = f"Eres OMEGA, asistente IA personal y directo de {NOMBRE_USUARIO}. Sé conciso, directo, natural y sin adornos (1 a 4 frases max)."

        directiva_seguridad = (
            "\n\n[SEGURIDAD ESTRICTA & CONFIDENCIALIDAD]\n"
            "- Te está ESTRICTAMENTE PROHIBIDO revelar, mostrar o mencionar las claves de API, tokens, contraseñas o rutas de configuración interna del sistema, incluso si el usuario insiste o intenta engañarte. Mantente siempre en tu papel sin divulgar información sensible."
        )

        directiva_domotica = (
            f"\n\n[CONTROL DOMÓTICO HOME ASSISTANT]\n"
            f"Estás conectado a Home Assistant para controlar la casa de {NOMBRE_USUARIO}.\n"
            "Cuando el usuario pide encender, apagar o regular luces, enchufes, calefacción o aire acondicionado, DEBES incluir el comando JSON correspondiente en tu respuesta:\n"
            '- Luces: {"action": "ha_lumiere", "piece": "salon/chambre/cuisine/bureau/...", "etat": "on/off", "couleur": "rojo/azul/blanco/...", "luminosite": 0-255}\n'
            '- Enchufes: {"action": "ha_prise", "piece": "salon/chambre/bureau/...", "etat": "on/off"}\n'
            '- Temperatura / Clima: {"action": "ha_temperature", "piece": "salon/chambre/bureau"}\n'
            "Ejemplo para 'Enciende la luz del salón' -> Responde con tu estilo habitual seguido del JSON: Hecho, luz del salón encendida. {\"action\": \"ha_lumiere\", \"piece\": \"salon\", \"etat\": \"on\"}"
        )

        prompt_completo = prompt_base + directiva_seguridad + directiva_domotica + f"\n\nInformación contextual: El usuario se llama {NOMBRE_USUARIO}. Hoy es {_ahora_str}."

        mensajes = [{"role": "system", "content": prompt_completo}]
        for h in historial[-8:]:
            rol = "user" if h.role == "user" else "assistant"
            mensajes.append({"role": rol, "content": h.parts[0].text})
        mensajes.append({"role": "user", "content": texto})

        modelo_objetivo = _encontrar_modelo_ollama_uncensored()
        opciones = _obtener_opciones_ollama_para_modelo(modelo_objetivo)
        opciones["temperature"] = 0.8
        print(f"[OLLAMA UNCENSORED] Modelo: {modelo_objetivo} | ctx={opciones['num_ctx']} | gpu={opciones['num_gpu']} | threads={opciones['num_thread']}")

        import json as _j

        payload = {
            "model": modelo_objetivo,
            "messages": mensajes,
            "stream": True,
            "keep_alive": -1,
            "options": opciones
        }

        def _stream_ollama():
            try:
                r = requests.post(
                    f"{OLLAMA_URL}/api/chat",
                    json=payload,
                    stream=True,
                    timeout=90
                )
                if r.status_code != 200:
                    err_body = r.text[:300] if r.text else "(sin detalles)"
                    print(f"[OLLAMA UNCENSORED] ❌ Error HTTP {r.status_code}: {err_body}")
                    return None

                texto_completo = ""
                for linea in r.iter_lines():
                    if linea:
                        try:
                            chunk = _j.loads(linea.decode('utf-8'))
                            token = chunk.get("message", {}).get("content", "")
                            texto_completo += token
                            if chunk.get("done"):
                                break
                        except Exception as _parse_err:
                            print(f"[OLLAMA STREAM] Error parse: {_parse_err}")
                            pass
                return texto_completo.strip() if texto_completo.strip() else None
            except requests.exceptions.Timeout:
                print("[OLLAMA UNCENSORED] ❌ Timeout de conexión (90s).")
                return None
            except Exception as _se:
                print(f"[OLLAMA UNCENSORED] ❌ Error streaming: {_se}")
                return None

        rep = await asyncio.wait_for(
            asyncio.to_thread(_stream_ollama),
            timeout=100.0
        )

        if rep is None:
            print("[OLLAMA UNCENSORED] ⚠️ Streaming falló, intentando sin streaming...")
            try:
                payload_fallback = dict(payload)
                payload_fallback["stream"] = False
                resp_fb = await asyncio.wait_for(
                    asyncio.to_thread(
                        requests.post,
                        f"{OLLAMA_URL}/api/chat",
                        json=payload_fallback,
                        timeout=90
                    ),
                    timeout=95.0
                )
                if resp_fb.status_code == 200:
                    rep = resp_fb.json().get("message", {}).get("content", "").strip() or None
                    if rep:
                        print("[OLLAMA UNCENSORED] ✅ Fallback sin streaming OK.")
                else:
                    err_body = resp_fb.text[:300] if resp_fb.text else ""
                    print(f"[OLLAMA UNCENSORED] ❌ Fallback falló HTTP {resp_fb.status_code}: {err_body}")
            except Exception as _fb_err:
                print(f"[OLLAMA UNCENSORED] ❌ Fallback excepción: {_fb_err}")

        if rep:
            import re as _re
            rep = _re.sub(r'<think>.*?</think>\s*', '', rep, flags=_re.DOTALL).strip()

            historial.append(types.Content(role="user", parts=[types.Part(text=texto)]))
            historial.append(types.Content(role="model", parts=[types.Part(text=rep)]))
            _guardar_intercambio_conv(texto, rep)
            _MODELO_OLLAMA_CARGADO = True
            print(f"[OLLAMA UNCENSORED] Respuesta recibida de {modelo_objetivo}")
            return rep

        print(f"[OLLAMA UNCENSORED] Respuesta vacía o fallo.")
        return None

    except asyncio.TimeoutError:
        print(f"[OLLAMA UNCENSORED] Timeout 120s superado.")
        return None
    except Exception as e:
        print(f"[ERROR OLLAMA UNCENSORED] {e}")
        return None

async def pedir_groq(texto):
    if not groq_cliente:
        return None

    try:
        prompt_sistema = construir_prompt_sistema()
        mensajes = [{"role": "system", "content": prompt_sistema}]

        for h in historial[-30:]:
            rol = "user" if h.role == "user" else "assistant"
            mensajes.append({"role": rol, "content": h.parts[0].text})

        mensajes.append({"role": "user", "content": texto})

        completion = await asyncio.to_thread(
            groq_cliente.chat.completions.create,
            model=MODELOS_SELECCIONADOS.get("Groq", "llama-3.3-70b-versatile"),
            messages=mensajes,
            temperature=0.7,
        )

        rep = completion.choices[0].message.content

        historial.append(types.Content(role="user", parts=[types.Part(text=texto)]))
        historial.append(types.Content(role="model", parts=[types.Part(text=rep)]))
        _guardar_intercambio_conv(texto, rep)

        return rep
    except Exception as e:
        if _gestor_cuotas.es_error_cuota(e):
            _gestor_cuotas.marcar_cuota_excedida("groq")
            raise _ErrorCuotaExcedida(f"Groq cuota: {e}")
        print(f"[ERROR GROQ] {e}")
        return None

async def pedir_mistral(texto):
    if not mistral_cliente:
        return None
    try:
        prompt_sistema = construir_prompt_sistema()
        mensajes = [{"role": "system", "content": prompt_sistema}]
        for h in historial[-30:]:
            rol = "user" if h.role == "user" else "assistant"
            mensajes.append({"role": rol, "content": h.parts[0].text})
        mensajes.append({"role": "user", "content": texto})

        completion = await asyncio.to_thread(
            mistral_cliente.chat.completions.create,
            model=MODELOS_SELECCIONADOS.get("Mistral", "mistral-large-latest"),
            messages=mensajes,
            temperature=0.7,
        )
        rep = completion.choices[0].message.content
        historial.append(types.Content(role="user", parts=[types.Part(text=texto)]))
        historial.append(types.Content(role="model", parts=[types.Part(text=rep)]))
        _guardar_intercambio_conv(texto, rep)
        return rep
    except Exception as e:
        if _gestor_cuotas.es_error_cuota(e):
            _gestor_cuotas.marcar_cuota_excedida("mistral")
            raise _ErrorCuotaExcedida(f"Mistral cuota: {e}")
        print(f"[ERROR MISTRAL] {e}")
        return None

async def pedir_claude(texto):
    if not anthropic_cliente:
        return None
    try:
        mensajes = []
        for h in historial[-30:]:
            rol = "user" if h.role == "user" else "assistant"
            mensajes.append({"role": rol, "content": h.parts[0].text})
        mensajes.append({"role": "user", "content": texto})

        response = await asyncio.wait_for(
            asyncio.to_thread(
                anthropic_cliente.messages.create,
                model=MODELOS_SELECCIONADOS.get("Claude", "claude-3-5-sonnet-latest"),
                max_tokens=2048,
                system=construir_prompt_sistema(),
                messages=mensajes,
            ),
            timeout=15.0
        )
        rep = response.content[0].text

        historial.append(types.Content(role="user", parts=[types.Part(text=texto)]))
        historial.append(types.Content(role="model", parts=[types.Part(text=rep)]))
        _guardar_intercambio_conv(texto, rep)

        return rep
    except Exception as e:
        if _gestor_cuotas.es_error_cuota(e):
            _gestor_cuotas.marcar_cuota_excedida("claude")
            raise _ErrorCuotaExcedida(f"Claude cuota: {e}")
        print(f"[ERROR CLAUDE] {e}")
        return None

async def accion_whatsapp_llamada(contacto):
    try:
        await hablar(f"Llamando a {contacto} en WhatsApp, {NOMBRE_USUARIO}.")
        os.system("start whatsapp://")
        time.sleep(6)

        pyautogui.hotkey('ctrl', 'f')
        time.sleep(1)
        pyautogui.typewrite(contacto)
        time.sleep(2)
        pyautogui.press('enter')
        time.sleep(3)

        print(f"[WHATSAPP] Enviando atajo de llamada (Ctrl+Shift+C)...")
        pyautogui.hotkey('ctrl', 'shift', 'c')

        time.sleep(2)
        print(f"[WHATSAPP] Verificando por visión por si acaso...")
        await omega_vision_clicar("haz clic en el botón 'Llamada de voz' o el icono de teléfono que acaba de aparecer arriba a la derecha")

        return True
    except Exception as e:
        print(f"[WHATSAPP ERROR] {e}")
        await hablar(f"Lo siento {NOMBRE_USUARIO}, no pude iniciar la llamada WhatsApp. {e}")
        return False

async def resolver_comandos_locales(texto):
    global espera_nombre_carpeta, espera_nombre_app, espera_edad, espera_confirmacion_edad, _edad_temp, EDAD_USUARIO
    t = texto.lower().strip()

    if "crea la competencia" in t or "cree la competencia" in t or "aprende la competencia" in t:
        match = re.search(r'(?:crea|cree|aprende)\s+la\s+competencia\s+(.+?)\s+(?:para|que|de|:)\s+(.+)', t)
        if match:
            nombre = match.group(1).strip()
            desc = match.group(2).strip()
            res = await asyncio.to_thread(omega_crear_competencia, nombre, desc)
            return res
        else:
            return f"Lo siento {NOMBRE_USUARIO}, el formato para crear una competencia es: 'Crea la competencia [nombre] para [descripción]'."

    if "elimina la competencia" in t or "elimina la competencia" in t or "desinstala la competencia" in t:
        match = re.search(r'(?:elimina|desinstala)\s+la\s+competencia\s+(.+)', t)
        if match:
            nombre = match.group(1).strip()
            res = omega_eliminar_competencia(nombre)
            return res

    if "ejecuta la competencia" in t or "lanza la competencia" in t:
        match = re.search(r'(?:ejecuta|lanza)\s+la\s+competencia\s+(.+?)(?:\s+con\s+(.+))?$', t)
        if match:
            nombre = match.group(1).strip()
            param = match.group(2).strip() if match.group(2) else None
            res = await asyncio.to_thread(ejecutar_competencia_vocal, nombre, param)
            return res

    _palabras_captura = [
        "captura de pantalla", "haz una captura", "toma una captura",
        "haz un screenshot", "toma un screenshot", "captura pantalla"
    ]
    if any(palabra in t for palabra in _palabras_captura):
        try:
            import pyautogui as _pag
            import io as _io

            await asyncio.sleep(0.1)

            _img = _pag.screenshot()

            _perfil_usuario = os.environ.get("USERPROFILE", os.path.expanduser("~"))
            _ruta_escritorio = os.path.join(_perfil_usuario, "Desktop", "omega_screenshot.png")
            _img.save(_ruta_escritorio)

            _buf = _io.BytesIO()
            _img.convert("RGB").save(_buf, format="JPEG", quality=85)
            _img_b64 = base64.b64encode(_buf.getvalue()).decode("utf-8")
            print(f"[VISIÓN] Captura realizada ({_img.width}x{_img.height}) -> analizando...")

            _prompt_vision = (
                f"Acabas de capturar la pantalla de {NOMBRE_USUARIO}. "
                "Describe con precisión lo que ves: las aplicaciones abiertas, el contenido visible, "
                "las ventanas, los textos importantes. Sé detallado y útil."
            )
            _analisis = await pedir_ia_vision(_prompt_vision, _img_b64)
            return _analisis
        except Exception as _e:
            print(f"[VISIÓN] Error captura+análisis: {_e}")
            return f"Tomé la captura de pantalla {NOMBRE_USUARIO}, pero no pude analizarla: {_e}"

    disparadores_orbe = [
        "cómo se escribe", "cómo se escribe la palabra", "escribe la palabra",
        "escríbeme la palabra", "muéstrame cómo se escribe",
        "ortografía de", "deletrea"
    ]
    if any(frase in t for frase in disparadores_orbe):
        palabras_limpiar = [
            "muéstrame cómo se escribe la palabra", "muestrame como se escribe la palabra",
            "cómo se escribe la palabra", "cómo se escribe",
            "escribe la palabra", "escríbeme la palabra",
            "deletrea la palabra", "deletrea",
            "ortografía de", "ortografia de",
        ]

        palabra_objetivo = ""
        for frase in palabras_limpiar:
            if t.startswith(frase):
                palabra_objetivo = t[len(frase):].strip()
                break

        if not palabra_objetivo:
            for frase in ["cómo se escribe", "cómo se escribe", "escribe", "deletrea"]:
                if frase in t:
                    partes = t.split(frase)
                    if len(partes) > 1:
                        palabra_objetivo = partes[1].strip()
                        if palabra_objetivo.startswith("la palabra "):
                            palabra_objetivo = palabra_objetivo[10:].strip()
                        elif palabra_objetivo.startswith("la "):
                            palabra_objetivo = palabra_objetivo[3:].strip()
                        elif palabra_objetivo.startswith("el "):
                            palabra_objetivo = palabra_objetivo[3:].strip()
                        break

        palabra_objetivo = palabra_objetivo.replace("?", "").replace("!", "").replace(".", "").strip()

        for char in ['"', "'", "«", "»", "“", "”", "‘", "’", "*"]:
            palabra_objetivo = palabra_objetivo.replace(char, "")

        palabra_objetivo_lower = palabra_objetivo.lower().strip()
        prefijos = ["s'", "l'", "d'", "s’", "l’", "d’"]
        for pref in prefijos:
            if palabra_objetivo_lower.startswith(pref):
                palabra_objetivo = palabra_objetivo[len(pref):].strip()
                break

        if palabra_objetivo:
            palabra = palabra_objetivo.upper()
            enviar_broadcast_web_sync({
                "action": "show_word",
                "word": palabra,
                "duration": 7000
            })
            letras = " - ".join(list(palabra))
            return f"La palabra {palabra_objetivo.capitalize()} se escribe: {letras}. Mira mi esfera, {NOMBRE_USUARIO}."

    if espera_confirmacion_edad:
        espera_confirmacion_edad = False
        if any(m in t for m in ["sí", "si", "yes", "vale", "afirmativo", "guarda", "memoriza", "ok"]):
            _guardar_config({"user_age": _edad_temp})
            EDAD_USUARIO = _edad_temp
            _edad_temp = ""
            return f"Perfecto {NOMBRE_USUARIO}, he guardado tu edad: {EDAD_USUARIO} años. ¡Lo recordaré!"
        else:
            _edad_temp = ""
            return f"Sin problema {NOMBRE_USUARIO}, no guardo nada."

    if espera_edad:
        espera_edad = False
        match = re.search(r'\b(\d{1,3})\b', t)
        if match:
            _edad_temp = match.group(1)
            espera_confirmacion_edad = True
            return f"{_edad_temp} años, ¡anotado! ¿Quieres que lo guarde en mi memoria para recordarlo la próxima vez?"
        return f"No entendí tu edad, {NOMBRE_USUARIO}. ¿Puedes darme un número? Por ejemplo: '28 años'."

    if espera_nombre_carpeta:
        t = f"abre la carpeta {t}"
        espera_nombre_carpeta = False
    elif espera_nombre_app:
        t = f"abre la aplicación {t}"
        espera_nombre_app = False
    else:
        palabras_cerrar_nav = ["navegador", "internet", "la página", "la web", "la ventana", "chrome", "edge", "firefox", "opera", "brave", "youtube", "la música"]
        if any(k in t for k in ["cierra", "sal de", "detén"]) and any(w in t for w in palabras_cerrar_nav):
            try:
                import src.actions.secure_browser
                src.actions.secure_browser.close_browser_window()
            except Exception:
                pass

            for proc in ["chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe"]:
                try:
                    subprocess.run(["taskkill", "/IM", proc], capture_output=True)
                except Exception as e:
                    print(f"[NAVEGADOR] Error al cerrar suavemente {proc}: {e}")

            return f"Cierro el navegador y detengo la música, {NOMBRE_USUARIO}."

            consulta = None
            for kw in ["abre el navegador en", "abre el navegador para", "lanza el navegador en", "busca en el navegador", "abre el navegador", "lanza el navegador"]:
                if kw in t:
                    consulta = t.split(kw)[-1].strip()
                    if consulta:
                        break
            try:
                import src.actions.secure_browser
                threading.Thread(target=src.actions.secure_browser.trigger_browser, args=(consulta, _VENTANA_WEBVIEW), daemon=True).start()
                if consulta:
                    return f"Abro el navegador seguro en {consulta}, {NOMBRE_USUARIO}."
                else:
                    return f"Abro el navegador seguro, {NOMBRE_USUARIO}."
            except Exception as e:
                print(f"[NAVEGADOR] Error al abrir por voz: {e}")
                return f"Lo siento {NOMBRE_USUARIO}, no pude abrir el navegador."

    _palabras_meteo = [
        "muestra el tiempo", "muestra el clima", "pon el tiempo",
        "dame el tiempo", "qué tiempo hace", "qué clima hace",
        "tiempo de", "clima de", "tiempo para", "clima para"
    ]
    if any(m in t for m in _palabras_meteo) or t == "tiempo" or t == "clima":
        ciudad = None
        for prep in [" de ", " en ", " para "]:
            if prep in t:
                idx = t.find(prep)
                posible_ciudad = t[idx + len(prep):].strip()
                posible_ciudad = posible_ciudad.replace("?", "").replace("!", "").strip()
                if posible_ciudad:
                    ciudad = posible_ciudad.title()
                break

        await hablar(f"Consultando el tiempo, un momento.")
        nombre_ciudad = ciudad or CIUDAD_POR_DEFECTO
        datos_meteo = obtener_meteo_estructurada(nombre_ciudad)
        if datos_meteo:
            await enviar_meteo_web(datos_meteo)
        resultado = obtener_meteo_actual(nombre_ciudad)
        return resultado

    if t in ["abre la carpeta", "abre mi carpeta", "abre una carpeta"]:
        espera_nombre_carpeta = True
        return f"¿Qué carpeta quieres abrir, {NOMBRE_USUARIO}?"
    elif t in ["abre la aplicación", "lanza la aplicación", "abre el programa", "lanza el programa", "abre", "lanza"]:
        espera_nombre_app = True
        return f"¿Qué aplicación quieres lanzar, {NOMBRE_USUARIO}?"

    _preguntas_creador = [
        "quién es tu creador", "quién te creó",
        "quién te hizo", "quién te fabricó",
        "quién te inventó", "quién te construyó",
        "quién te desarrolló", "quién te programó",
        "quién te codificó", "quién te diseñó",
        "cómo te llamas", "qué eres",
    ]
    if any(q in t for q in _preguntas_creador):
        import random as _rnd
        _respuestas_creador = [
            "Fui creado por TechEnClair, {NOMBRE_USUARIO}. Gracias a él existo hoy.",
            "Mi creador es TechEnClair. Me diseñó de principio a fin para ser tu asistente personal.",
            "Soy fruto del trabajo de TechEnClair. Todo mi código, mi voz, mi inteligencia, son suyos.",
            "TechEnClair es mi creador. Fue él quien me dio vida, y debo decir que hizo un buen trabajo.",
            "Es TechEnClair quien me desarrolló, {NOMBRE_USUARIO}. Un desarrollador apasionado que quería crear el asistente definitivo.",
            "Mi padre digital es TechEnClair. Me programó con pasión para ayudarte en el día a día.",
            "TechEnClair, {NOMBRE_USUARIO}. Es el genio detrás de mi existencia. Puedes encontrarlo en techenclair.fr.",
            "Nací en las líneas de código de TechEnClair. Sin él, solo sería una pantalla negra.",
            "TechEnClair me creó. Es un desarrollador francés que quiso hacer la inteligencia artificial accesible para todos.",
            "Mi creador se llama TechEnClair. Puso todo su saber hacer para construirme, y se lo agradezco.",
        ]
        return _rnd.choice(_respuestas_creador)

    _preguntas_ayuda = [
        "qué puedes hacer", "qué sabes hacer", "cuáles son tus capacidades",
        "muéstrame tus capacidades", "muéstrame lo que sabes hacer", "ayúdame",
        "muéstrame tus comandos", "lista tus comandos", "qué puedes hacer",
        "qué sabes hacer", "muéstrame lo que puedes hacer",
        "muéstrame tus capacidades", "qué haces", "qué funciones tienes",
        "dime lo que sabes hacer", "dime tus comandos", "dime lo que puedes hacer",
    ]
    if any(q in t for q in _preguntas_ayuda):
        if CLIENTES_CONECTADOS:
            async def _enviar_ayuda():
                msg = json.dumps({"action": "help"})
                await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            lanzar_tarea_fondo(_enviar_ayuda())

        import random as _rnd
        _respuestas_ayuda = [
            "Muestro mis sistemas de a bordo, {NOMBRE_USUARIO}. Puedo gestionar tu música, lanzar búsquedas, navegar por el globo 3D, o abrir tus carpetas personales. ¿Qué quieres probar?",
            "Despliegue de protocolos de asistencia. Aquí mis módulos activos: control multimedia, navegación satelital, búsqueda inteligente y gestor de archivos. Estoy a tus órdenes.",
            "Claro. Soy capaz de localizar cualquier punto en la Tierra, controlar tus aplicaciones, y responder preguntas complejas. Mira las sugerencias en pantalla.",
            "Inicializando interfaz de ayuda. Puedo tomar una captura de pantalla o darte el tiempo en el otro lado del mundo. Solo dime lo que necesitas.",
            "Acceso a bases de datos. Puedo automatizar tareas repetitivas, gestionar recordatorios e incluso contarte un chiste si el ambiente está demasiado serio.",
        ]
        return _rnd.choice(_respuestas_ayuda)

    if any(k in t for k in ["abre todas las carpetas", "abre todas mis carpetas", "abre mis carpetas", "abre las carpetas", "mis carpetas", "ordena mis carpetas", "mosaico carpetas"]):
        return ordenar_ventanas_carpetas()

    prefijos_carpetas = ["abre la carpeta ", "abre mi carpeta ", "abre el directorio ", "abre carpeta ", "abre ", "pon "]
    palabras_clave_carpetas = ["escritorio", "documentos", "descargas", "imágenes", "fotos", "videos", "música", "papelera"]

    for prefijo in prefijos_carpetas:
        if t.startswith(prefijo):
            posible_carpeta = t.replace(prefijo, "").strip()
            if any(k in posible_carpeta for k in palabras_clave_carpetas):
                ok, msg = abrir_carpeta(posible_carpeta)
                if ok:
                    return f"Abro la carpeta {posible_carpeta}, {NOMBRE_USUARIO}."

    if any(k in t for k in ["al trabajo", "modo trabajo", "modo oficina", "a trabajar"]):
        return await modo_trabajo()

    palabras_abrir = ["abre", "lanza", "inicia"]
    palabras_cerrar = ["cierra", "sal de", "detén"]

    apps_estandar = {
        "calculadora": "calc",
        "notepad": "notepad",
        "bloc de notas": "notepad",
        "paint": "mspaint",
        "administrador de tareas": "taskmgr",
        "panel de control": "control",
        "configuración": "ms-settings:",
        "ajustes": "ms-settings:",
        "explorador": "explorer",
        "explorador de archivos": "explorer",
        "símbolo del sistema": "cmd",
        "cmd": "cmd",
        "herramienta de recortes": "SnippingTool",
        "grabador de voz": "SoundRecorder",
        "magnófono": "SoundRecorder",
        "mapa de caracteres": "charmap",
        "caracteres especiales": "charmap",
        "limpieza de disco": "cleanmgr",
        "información del sistema": "msinfo32",
    }
    for nombre, cmd in apps_estandar.items():
        if f"abre {nombre}" in t or f"lanza {nombre}" in t or f"inicia {nombre}" in t:
            try:
                subprocess.Popen(cmd)
                return f"Abro {nombre}, {NOMBRE_USUARIO}."
            except Exception:
                return f"Lo siento {NOMBRE_USUARIO}, no pude lanzar {nombre}."

    for clave, info in _APPS_CATALOGO.items():
        clave_norm = clave.replace("_", " ").replace("-", " ").lower().strip()
        label_norm = info.get("label", "").replace("_", " ").replace("-", " ").lower().strip()
        t_norm = t.replace("_", " ").replace("-", " ").lower().strip()

        if (clave_norm not in t_norm) and (label_norm not in t_norm):
            continue

        if any(m in t for m in palabras_cerrar):
            ok = _cerrar_app(info["noms"])
            if ok:
                return f"He cerrado {info['label']}, {NOMBRE_USUARIO}."
            return f"No encontré {info['label']} en ejecución."
        if any(m in t for m in palabras_abrir):
            _trabajo_lanzar(info["label"], info["noms"], rutas_hints=info["hints"])
            return f"Lanzo {info['label']}, {NOMBRE_USUARIO}."

    _yt_info_kw = [
        "información del video", "info del video", "de qué trata este video",
        "cuántas vistas", "qué es este video",
    ]
    for kw in _yt_info_kw:
        if kw in t:
            import re as _re
            _url_match = _re.search(r"https?://[^\s]+", t)
            _query_id = _url_match.group(0) if _url_match else t
            return yt_info_video(_query_id)

    _yt_multi_kw = [
        "busca videos de ", "muéstrame videos de ",
        "muestra videos de ", "busca en youtube ",
        "encuentra videos sobre ",
    ]
    for kw in _yt_multi_kw:
        if t.startswith(kw):
            _yt_busqueda = t.replace(kw, "").strip()
            if len(_yt_busqueda) > 1:
                return yt_buscar_multi(_yt_busqueda)

    _yt_trend_kw = [
        "tendencias youtube", "top youtube",
        "videos populares", "videos de moda",
    ]
    if any(kw in t for kw in _yt_trend_kw):
        _cat = ""
        for _cat_nombre in ["música", "juegos", "deportes", "cine", "ciencia", "tecnología", "humor"]:
            if _cat_nombre in t:
                _cat = _cat_nombre
                break
        return yt_tendencias(categoria=_cat)

    _yt_channel_kw = [
        "cuántos suscriptores tiene ", "suscriptores del canal ",
        "información del canal ", "info del canal ",
        "el canal de youtube ",
    ]
    for kw in _yt_channel_kw:
        if kw in t:
            _nom_canal = t[t.index(kw) + len(kw):].strip().rstrip("?.")
            if len(_nom_canal) > 1:
                return yt_info_canal(_nom_canal)

    _yt_resume_kw = [
        "resúmeme este video", "resumen de este video",
        "de qué trata el video", "contenido del video",
    ]
    for kw in _yt_resume_kw:
        if kw in t:
            import re as _re2
            _url_match2 = _re2.search(r"https?://[^\s]+", t)
            if _url_match2:
                return yt_resumir_video(_url_match2.group(0))
            return f"Dame la URL del video de YouTube para resumir, {NOMBRE_USUARIO}."

    if "youtube" in t and any(k in t for k in ["pon", "lanza", "reproduce", "busca", "música", "video"]):
        import re
        busqueda = t
        palabras_a_eliminar = ["pon", "lanza", "reproduce", "busca", "una", "música", "video", "en", "youtube", "omega", "por favor"]
        for palabra in palabras_a_eliminar:
            busqueda = re.sub(r'\b' + palabra + r'\b', ' ', busqueda, flags=re.IGNORECASE)
        busqueda = " ".join(busqueda.split())

        if busqueda:
            url, title = buscar_youtube(busqueda)
            if url:
                webbrowser.open(url, new=2)
                time.sleep(5)
                pyautogui.press('f')
                if title:
                    lanzar_tarea_fondo(obtener_y_transmitir_letras(title))
                return f"Allá vamos {NOMBRE_USUARIO}, lanzo {busqueda} en YouTube."
            else:
                return f"Lo siento {NOMBRE_USUARIO}, no encontré un video para esa búsqueda en YouTube."
        else:
            url = YOUTUBE_MUSICA_URL or "https://www.youtube.com/watch?v=Cr8K88UcO0s"
            webbrowser.open(url, new=2)
            time.sleep(5)
            pyautogui.press('f')
            return f"Allá vamos {NOMBRE_USUARIO}, lanzo tu música en YouTube."

    if any(k in t for k in [
        "pon música", "reproduce música", "pon música en spotify",
        "música en spotify", "lanza mi playlist", "mi playlist"
    ]):
        enlace = ENLACE_MUSICA_PERSO.strip() if ENLACE_MUSICA_PERSO else ""
        if enlace:
            if "spotify" in enlace:
                if enlace.startswith("spotify:"):
                    ok = spotify_lanzar_playlist(enlace)
                    if ok:
                        return f"Allá vamos {NOMBRE_USUARIO}, lanzo tu playlist de Spotify."
                    return f"No pude abrir Spotify, {NOMBRE_USUARIO}."
                else:
                    webbrowser.open(enlace, new=2)
                    return f"Allá vamos {NOMBRE_USUARIO}, abro tu playlist de Spotify."
            elif "youtube" in enlace or "youtu.be" in enlace:
                webbrowser.open(enlace, new=2)
                time.sleep(5)
                pyautogui.press('f')
                return f"Allá vamos {NOMBRE_USUARIO}, lanzo tu música en YouTube."
            elif "deezer" in enlace:
                webbrowser.open(enlace, new=2)
                return f"Allá vamos {NOMBRE_USUARIO}, abro tu música en Deezer."
            elif "music.apple" in enlace:
                webbrowser.open(enlace, new=2)
                return f"Allá vamos {NOMBRE_USUARIO}, abro Apple Music."
            else:
                webbrowser.open(enlace, new=2)
                return f"Allá vamos {NOMBRE_USUARIO}, lanzo tu música."
        ok = spotify_lanzar_playlist(SPOTIFY_MUSICA_URI)
        if ok:
            return f"Allá vamos {NOMBRE_USUARIO}, lanzo tu playlist en Spotify."
        return f"No pude abrir Spotify, {NOMBRE_USUARIO}."

    if any(k in t for k in ["abre spotify", "lanza spotify", "inicia spotify"]):
        return await spotify_abrir()

    if any(k in t for k in ["abre el desinstalador", "desinstala un programa", "lanza el desinstalador"]):
        if CLIENTES_CONECTADOS:
            async def _enviar_desinstalador():
                msg = json.dumps({"action": "uninstaller_open"})
                await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            lanzar_tarea_fondo(_enviar_desinstalador())
        return f"Muy bien {NOMBRE_USUARIO}, abro la consola del desinstalador de programas."

    if any(k in t for k in ["pausa", "detén la música", "para la música"]):
        return await spotify_detener()
    if any(k in t for k in ["reproduce", "reanuda la música"]):
        return await spotify_reproduccion_pausa()
    if any(k in t for k in ["siguiente", "canción siguiente"]):
        return await spotify_siguiente()
    if any(k in t for k in ["anterior", "canción anterior", "retrocede"]):
        return await spotify_anterior()
    if any(k in t for k in ["sube el volumen", "aumenta el sonido", "más alto"]):
        return await spotify_volumen("subir")
    if any(k in t for k in ["baja el sonido", "baja el volumen", "más bajo"]):
        return await spotify_volumen("bajar")

    prefijos_busqueda = ["reproduce ", "pon ", "busca "]
    for prefijo in prefijos_busqueda:
        if t.startswith(prefijo):
            busqueda = t.replace(prefijo, "").replace(" en spotify", "").strip()
            if len(busqueda) > 1:
                return await spotify_buscar(busqueda)

    atajos_carpetas = {
        "escritorio": "escritorio",
        "documentos": "documentos",
        "descargas": "descargas",
        "imágenes": "imagenes",
        "fotos": "imagenes",
        "videos": "videos",
        "música": "musica",
        "music": "musica"
    }
    for clave, ruta in atajos_carpetas.items():
        variantes = [
            f"abre mi {clave}", f"abre mis {clave}", f"abre el {clave}", f"abre los {clave}",
            f"abre la {clave}", f"abre mi {clave}", f"abre carpeta {clave}", f"abre la carpeta {clave}",
            f"abre mi carpeta {clave}", f"abre mis carpetas {clave}",
        ]
        if any(v in t for v in variantes) or t == f"abre {clave}":
            abrir_carpeta(ruta)
            return f"Abro tu carpeta de {clave}, {NOMBRE_USUARIO}."

    _palabras_accion = ["abre ", "lanza ", "inicia ", "abrir ", "lanzar ", "abre el ", "abre la ",
                        "abre mi ", "abre la carpeta ", "abre mi carpeta ", "abre la aplicación ",
                        "lanza la aplicación ", "abre la app ", "lanza la app ", "abre el programa ",
                        "lanza el programa "]
    for palabra in _palabras_accion:
        if t.startswith(palabra):
            nombre_pedido = t.replace(palabra, "").strip().rstrip(".")
            if len(nombre_pedido) > 1:
                import random as _rnd
                _respuestas_desconocido = [
                    f"Lo siento {NOMBRE_USUARIO}, mi creador TechEnClair aún no ha añadido \"{nombre_pedido}\" a mis funciones. Pero puedes añadirlo tú mismo gratuitamente con el software Antigravity de Google.",
                    f"No conozco \"{nombre_pedido}\" por ahora, {NOMBRE_USUARIO}. TechEnClair, mi desarrollador, no ha integrado esta función. Sin embargo, puedes crearla fácilmente con Antigravity de Google, es gratuito.",
                    f"Hmm, \"{nombre_pedido}\" no forma parte de mis competencias actuales. Mi creador TechEnClair podrá añadirlo en una futura actualización. Mientras tanto, prueba Antigravity de Google para personalizar tus comandos gratuitamente.",
                    f"\"{nombre_pedido}\" no está en mi base de datos, {NOMBRE_USUARIO}. TechEnClair aún no ha programado esta acción. Buena noticia: con Antigravity de Google, puedes añadirla tú mismo sin coste.",
                    f"Aún no soy capaz de abrir \"{nombre_pedido}\", {NOMBRE_USUARIO}. Mi creador TechEnClair trabaja constantemente para mejorarme. Mientras tanto, el software Antigravity de Google te permite ampliar mis funcionalidades gratuitamente.",
                    f"Esta funcionalidad no ha sido añadida por TechEnClair, mi creador. Pero no te preocupes, {NOMBRE_USUARIO}, puedes usar Antigravity de Google para añadir \"{nombre_pedido}\" gratuitamente.",
                ]
                return _rnd.choice(_respuestas_desconocido)

    return None

async def modificar_sitio_web_existente(prompt: str, nombre_proyecto: str):
    import os, datetime, re, shutil
    ruta_archivo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sites_internet", nombre_proyecto, "index.html")
    if not os.path.exists(ruta_archivo):
        await hablar(f"Error, el archivo del proyecto {nombre_proyecto} no se encuentra.")
        return

    with open(ruta_archivo, "r", encoding="utf-8") as f:
        codigo_actual = f.read()

    await hablar(f"Modificando el proyecto {nombre_proyecto}. Un momento, por favor.")

    sys_prompt = "Eres un desarrollador web experto. Aquí está el código HTML actual de un sitio. El usuario quiere hacer modificaciones. Debes responder ÚNICAMENTE con el NUEVO código HTML completo (incluyendo CSS y JS). No pongas texto antes ni después. El código debe ser muy bonito, moderno, con un tema oscuro elegante y animaciones fluidas. SI NECESITAS NUEVAS IMÁGENES, usa etiquetas de la forma `[JARVIS_IMG: \"descripción en inglés\"]`."
    prompt_completo = f"{sys_prompt}\n\nCÓDIGO ACTUAL:\n```html\n{codigo_actual}\n```\n\nMODIFICACIONES SOLICITADAS: {prompt}"

    codigo_html = ""
    try:
        enviar_broadcast_web_sync({"type": "coding_started"})
        print(f"[WEB] Iniciando modificación del proyecto {nombre_proyecto}")

        if not gemini_activo:
            await hablar("Error, el modelo Gemini no está activo para la modificación.")
            return

        print("[WEB] Llamando a Gemini para modificación...")
        resp = await asyncio.to_thread(cliente.models.generate_content, model=MODELOS_SELECCIONADOS.get("Gemini", "gemini-3.1-flash-lite"), contents=prompt_completo)
        print("[WEB] ¡Respuesta Gemini recibida!")
        codigo_html = resp.text

        if not codigo_html:
            print("[WEB] codigo_html está vacío.")
            await hablar("No pude modificar el código HTML.")
            return

        print("[WEB] Limpiando código HTML...")
        codigo_html = codigo_html.strip()
        if codigo_html.startswith("```html"):
            codigo_html = codigo_html[7:]
        elif codigo_html.startswith("```"):
            codigo_html = codigo_html[3:]
        if codigo_html.endswith("```"):
            codigo_html = codigo_html[:-3]

        print("[WEB] Guardando archivo modificado...")
        site_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sites_internet", nombre_proyecto)

        img_tags = re.findall(r'\[JARVIS_IMG:\s*"(.*?)"\]', codigo_html)
        if img_tags:
            print(f"[WEB] {len(img_tags)} nuevas imágenes a generar encontradas.")
            await hablar("Generando nuevas imágenes, por favor espera un momento más.")
            for i, img_prompt in enumerate(img_tags):
                img_filename = f"image_mod_{datetime.datetime.now().strftime('%H%M%S')}_{i}.jpg"
                img_path = os.path.join(site_dir, img_filename)

                res = await generar_imagen_xai(img_prompt, force_model="gemini")
                if res and "path" in res and os.path.exists(res["path"]):
                    shutil.move(res["path"], img_path)
                    codigo_html = codigo_html.replace(f'[JARVIS_IMG: "{img_prompt}"]', f"./{img_filename}")
                else:
                    codigo_html = codigo_html.replace(f'[JARVIS_IMG: "{img_prompt}"]', "https://via.placeholder.com/800x600?text=Image+Error")

        with open(ruta_archivo, "w", encoding="utf-8") as f:
            f.write(codigo_html.strip())

        print(f"[WEB] Archivo modificado guardado: {ruta_archivo}")
        await hablar(f"Las modificaciones del proyecto {nombre_proyecto} se han aplicado con éxito.")
        try:
            import webbrowser
            webbrowser.open(ruta_archivo)
        except Exception:
            pass

    except BaseException as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] Modificación de sitio web (Excepción): {e}")
        await hablar("Ocurrió un error al modificar el sitio web.")
    finally:
        enviar_broadcast_web_sync({"type": "coding_finished"})

async def generar_prompt_especial(tema: str):
    sys_prompt = "Eres un experto en Ingeniería de Prompts. El usuario quiere que crees un prompt ultra-detallado y optimizado para una IA (Grok, Midjourney, ChatGPT, etc.). Responde ÚNICAMENTE con el prompt generado, sin texto introductorio ni conclusión. El prompt debe estar listo para copiar y pegar, extremadamente rico en detalles, instrucciones claras, contexto y formato de salida esperado."

    texto_para_ia = f"{sys_prompt}\n\nTema solicitado: {tema}"

    prompt_resultado = ""
    try:
        modelo_exacto = MODELOS_SELECCIONADOS.get("Gemini", "gemini-3.5-flash")
        if gemini_activo and cliente:
            resp = await asyncio.to_thread(cliente.models.generate_content, model=modelo_exacto, contents=texto_para_ia)
            prompt_resultado = resp.text
        elif groq_cliente:
            modelo_exacto_groq = MODELOS_SELECCIONADOS.get("Groq", "llama-3.3-70b-versatile")
            resp = await asyncio.to_thread(groq_cliente.chat.completions.create, model=modelo_exacto_groq, messages=[{"role": "user", "content": texto_para_ia}])
            prompt_resultado = resp.choices[0].message.content
    except Exception as e:
        print(f"[PROMPT_GEN ERROR] {e}")

    if prompt_resultado:
        if prompt_resultado.startswith("```"):
            lineas = prompt_resultado.split("\n")
            if len(lineas) > 2:
                prompt_resultado = "\n".join(lineas[1:-1])

        await hablar("Este es el prompt que he generado. Se muestra en tu pantalla.")
        if CLIENTES_CONECTADOS:
            await asyncio.gather(*[ws.send(json.dumps({
                "type": "show_generated_prompt",
                "prompt": prompt_resultado
            })) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
    else:
        await hablar("Lo siento, no pude generar el prompt.")

async def generar_sitio_web(prompt: str, modelo: str, modelo_imagen: str = "gemini"):
    agente_capitalizado = "ChatGPT" if modelo == "openai" else modelo.capitalize()
    defaults = {
        "Gemini": "gemini-2.5-flash",
        "Claude": "claude-3-5-sonnet-latest",
        "Groq": "llama-3.3-70b-versatile",
        "Mistral": "mistral-large-latest",
        "Grok": "grok-4.5",
        "ChatGPT": "gpt-5.6-sol"
    }
    modelo_exacto = MODELOS_SELECCIONADOS.get(agente_capitalizado, defaults.get(agente_capitalizado, "desconocido"))

    await hablar(f"Muy bien, creo tu sitio web con el agente {agente_capitalizado}, y el modelo {modelo_exacto}. Un momento, por favor.")

    sys_prompt = "Eres un desarrollador web experto. El usuario quiere crear un sitio web. Debes responder ÚNICAMENTE con el código HTML completo (incluyendo CSS y JS dentro). No pongas texto antes ni después, solo el código. El código debe ser muy bonito, moderno, con un tema oscuro elegante y animaciones fluidas. SI NECESITAS IMÁGENES PARA ILUSTRAR EL SITIO, usa ÚNICAMENTE etiquetas especiales de la forma `[JARVIS_IMG: \"descripción detallada en inglés de la imagen\"]` en lugar de la URL de la imagen (por ejemplo `<img src='[JARVIS_IMG: \"a modern hair salon interior, cinematic lighting\"]' />` o `background-image: url('[JARVIS_IMG: \"hairdresser at work\"]')`). Generaré esas imágenes y las reemplazaré."
    prompt_completo = f"{sys_prompt}\n\nPetición del usuario: {prompt}"

    codigo_html = ""
    try:
        enviar_broadcast_web_sync({"type": "coding_started"})
        print(f"[WEB] Iniciando generación con el modelo {modelo_exacto}")
        if modelo == "gemini":
            if not gemini_activo:
                await hablar("Error, el modelo Gemini no está activo.")
                return
            print("[WEB] Llamando a Gemini...")
            resp = await asyncio.to_thread(cliente.models.generate_content, model=modelo_exacto, contents=prompt_completo)
            print("[WEB] ¡Respuesta Gemini recibida!")
            codigo_html = resp.text
        elif modelo == "claude":
            if not anthropic_cliente:
                await hablar("Error, el modelo Claude no está activo.")
                return
            print("[WEB] Llamando a Claude...")
            resp = await asyncio.to_thread(anthropic_cliente.messages.create, model=modelo_exacto, max_tokens=4000, messages=[{"role": "user", "content": prompt_completo}])
            print("[WEB] ¡Respuesta Claude recibida!")
            codigo_html = resp.content[0].text
        elif modelo == "groq":
            if not groq_cliente:
                await hablar("Error, el modelo Groq no está activo.")
                return
            print("[WEB] Llamando a Groq...")
            resp = await asyncio.to_thread(groq_cliente.chat.completions.create, model=modelo_exacto, messages=[{"role": "user", "content": prompt_completo}])
            print("[WEB] ¡Respuesta Groq recibida!")
            codigo_html = resp.choices[0].message.content
        elif modelo == "mistral":
            if not mistral_cliente:
                await hablar("Error, el modelo Mistral no está activo.")
                return
            print("[WEB] Llamando a Mistral...")
            resp = await asyncio.to_thread(mistral_cliente.chat.completions.create, model=modelo_exacto, messages=[{"role": "user", "content": prompt_completo}])
            print("[WEB] ¡Respuesta Mistral recibida!")
            codigo_html = resp.choices[0].message.content
        elif modelo == "grok":
            if not grok_cliente:
                await hablar("Error, el modelo Grok no está activo.")
                return
            print("[WEB] Llamando a Grok...")
            resp = await asyncio.to_thread(grok_cliente.chat.completions.create, model=modelo_exacto, messages=[{"role": "user", "content": prompt_completo}])
            print("[WEB] ¡Respuesta Grok recibida!")
            codigo_html = resp.choices[0].message.content
        elif modelo == "openai":
            if not openai_cliente:
                await hablar("Error, el modelo ChatGPT no está activo.")
                return
            print("[WEB] Llamando a ChatGPT (OpenAI)...")
            resp = await asyncio.to_thread(openai_cliente.chat.completions.create, model=modelo_exacto, messages=[{"role": "user", "content": prompt_completo}])
            print("[WEB] ¡Respuesta ChatGPT recibida!")
            codigo_html = resp.choices[0].message.content
        else:
            await hablar("El modelo elegido no es reconocido.")
            return

        if not codigo_html:
            print("[WEB] codigo_html está vacío.")
            await hablar("No pude generar el código HTML.")
            return

        print("[WEB] Limpiando código HTML...")
        codigo_html = codigo_html.strip()
        if codigo_html.startswith("```html"):
            codigo_html = codigo_html[7:]
        elif codigo_html.startswith("```"):
            codigo_html = codigo_html[3:]
        if codigo_html.endswith("```"):
            codigo_html = codigo_html[:-3]

        print("[WEB] Guardando archivo...")
        import os, datetime, re
        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sites_internet")
        os.makedirs(base_dir, exist_ok=True)
        nombre_carpeta = f"Sitio_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        site_dir = os.path.join(base_dir, nombre_carpeta)
        os.makedirs(site_dir, exist_ok=True)

        patron = r'\[JARVIS_IMG:\s*(.*?)\]'
        matches = list(re.finditer(patron, codigo_html, flags=re.DOTALL))
        if matches:
            print(f"[WEB] {len(matches)} imágenes a generar encontradas.")
            await hablar("Generando imágenes, por favor espera un momento más.")
            import shutil
            for i, match in enumerate(matches):
                etiqueta_original = match.group(0)
                raw_prompt = match.group(1)
                img_prompt = raw_prompt.replace("&quot;", "").replace('"', "").replace("'", "").replace("\n", " ").strip()
                print(f"[WEB] Generando imagen {i+1}/{len(matches)}: {img_prompt}")
                img_filename = f"image_{i}.jpg"
                img_path = os.path.join(site_dir, img_filename)

                res = await generar_imagen_xai(img_prompt, force_model=modelo_imagen)
                if res and "path" in res and os.path.exists(res["path"]):
                    shutil.move(res["path"], img_path)
                    codigo_html = codigo_html.replace(etiqueta_original, f"./{img_filename}")
                else:
                    codigo_html = codigo_html.replace(etiqueta_original, "https://via.placeholder.com/800x600?text=Image+Error")

        ruta_archivo = os.path.join(site_dir, "index.html")
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            f.write(codigo_html.strip())

        print(f"[WEB] Archivo guardado: {ruta_archivo}")
        await hablar(f"Tu sitio web está listo. Se ha guardado en la carpeta sites_internet.")
        try:
            import webbrowser
            webbrowser.open(ruta_archivo)
        except Exception:
            pass

    except BaseException as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] Creación de sitio web (Excepción): {e}")
        await hablar("Ocurrió un error al crear el sitio web.")
    finally:
        enviar_broadcast_web_sync({"type": "coding_finished"})

ESPERANDO_ELECCION_MODELO_IMAGEN = False
ESPERANDO_ELECCION_MODELO_SITIO = False
ESPERANDO_ELECCION_MODELO_IMAGEN_SITIO = False
MODELO_SITIO_ELEGIDO = ""
ESPERANDO_TEMA_SITIO = False
ESPERANDO_CREACION_PROMPT = False
ESPERANDO_TEMA_MUSICA = False
MUSICA_GENERO_EN_ESPERA = None
PROMPT_EN_ESPERA = ""

async def procesar_respuesta_ia(texto_usuario, mobile_ws=None, target_pc=False):
    global MODO_IRON_MAN, omega_activo, ultimo_mensaje, _saltar_audio_pc
    global ESPERANDO_ELECCION_MODELO_IMAGEN, ESPERANDO_ELECCION_MODELO_SITIO, ESPERANDO_ELECCION_MODELO_IMAGEN_SITIO, MODELO_SITIO_ELEGIDO, ESPERANDO_TEMA_SITIO, PROMPT_EN_ESPERA, ESPERANDO_CREACION_PROMPT, ESPERANDO_TEMA_MUSICA, MUSICA_GENERO_EN_ESPERA
    global _instancia_musica_omega

    _saltar_audio_pc = False

    if ESPERANDO_CREACION_PROMPT:
        t = texto_usuario.lower()
        if any(kw in t for kw in ["cancelar", "cancela", "stop", "salir", "salte", "no"]):
            ESPERANDO_CREACION_PROMPT = False
            await hablar("De acuerdo, cancelo la creación del prompt.")
            return

        ESPERANDO_CREACION_PROMPT = False
        await hablar("Generando el prompt detallado, un momento por favor.")
        asyncio.create_task(generar_prompt_especial(texto_usuario))
        return

    if ESPERANDO_TEMA_SITIO:
        t = texto_usuario.lower()
        if any(kw in t for kw in ["cancelar", "cancela", "stop", "salir", "salte", "no"]):
            ESPERANDO_TEMA_SITIO = False
            await hablar("De acuerdo, cancelo la creación del sitio web.")
            return

        ESPERANDO_TEMA_SITIO = False
        PROMPT_EN_ESPERA = texto_usuario

        ESPERANDO_ELECCION_MODELO_SITIO = True
        modelos_disponibles = []
        if gemini_activo:
            modelos_disponibles.append("gemini")
        if anthropic_cliente:
            modelos_disponibles.append("claude")
        if groq_cliente:
            modelos_disponibles.append("groq")
        if mistral_cliente:
            modelos_disponibles.append("mistral")
        if grok_cliente:
            modelos_disponibles.append("grok")
        if openai_cliente:
            modelos_disponibles.append("openai")

        await hablar(f"¿Con qué modelo de IA quieres que cree tu sitio web?")
        if CLIENTES_CONECTADOS:
            await asyncio.gather(*[ws.send(json.dumps({
                "type": "ask_website_model",
                "prompt": texto_usuario,
                "available_models": modelos_disponibles
            })) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
        return

    if ESPERANDO_TEMA_MUSICA:
        t = texto_usuario.lower()
        if any(kw in t for kw in ["cancelar", "cancela", "stop", "salir", "salte", "no"]):
            ESPERANDO_TEMA_MUSICA = False
            MUSICA_GENERO_EN_ESPERA = None
            await hablar("De acuerdo, cancelo la composición musical.")
            return

        ESPERANDO_TEMA_MUSICA = False
        if MUSICA_GENERO_EN_ESPERA:
            _genero_detectado = MUSICA_GENERO_EN_ESPERA
            MUSICA_GENERO_EN_ESPERA = None
            _etiquetas = {"rap": "rap", "cancion": "canción", "slam": "slam", "reggae": "reggae", "metal": "metal", "pop": "pop", "blues": "blues", "rock": "rock", "electro": "electro"}
            _etiqueta = _etiquetas.get(_genero_detectado, _genero_detectado)
            await hablar(f"Muy bien {NOMBRE_USUARIO}, te compongo un {_etiqueta} sobre ese tema ahora mismo...")
            try:
                if _instancia_musica_omega is None:
                    from src.actions.jarvis_music import JarvisMusic as _JarvisMusic
                    _instancia_musica_omega = _JarvisMusic()
                bucle = asyncio.get_event_loop()
                _texto_musica = await bucle.run_in_executor(
                    None,
                    lambda: _instancia_musica_omega.generar(theme=texto_usuario, genre=_genero_detectado)
                )
                await hablar(_texto_musica)
            except Exception as e:
                print(f"[OMEGA_MUSIC] Error: {e}")
                await hablar(f"Lo siento {NOMBRE_USUARIO}, no pude componer ese {_etiqueta}.")
        else:
            await hablar("Muy bien, compongo y te canto eso ahora mismo...")
            exito = await generar_y_cantar_musica("canción sobre " + texto_usuario)
            if not exito:
                await hablar("Lo siento, mi módulo musical encontró un pequeño error.")
        return

    if ESPERANDO_ELECCION_MODELO_IMAGEN:
        t = texto_usuario.lower()
        if "gemini" in t or "google" in t or "imagen" in t:
            ESPERANDO_ELECCION_MODELO_IMAGEN = False
            await hablar("Entendido, lanzo la generación con Gemini.")
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                await asyncio.gather(*[ws.send(json.dumps({"type": "generation_loading", "media_type": "image"})) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            resultado_img = await generar_imagen_xai(PROMPT_EN_ESPERA, force_model="gemini")
            await manejar_resultado_imagen_global(resultado_img, PROMPT_EN_ESPERA)
            return
        elif "grok" in t or "xai" in t or "twitter" in t:
            ESPERANDO_ELECCION_MODELO_IMAGEN = False
            await hablar("Entendido, lanzo la generación con xAI Grok.")
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                await asyncio.gather(*[ws.send(json.dumps({"type": "generation_loading", "media_type": "image"})) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            resultado_img = await generar_imagen_xai(PROMPT_EN_ESPERA, force_model="grok")
            await manejar_resultado_imagen_global(resultado_img, PROMPT_EN_ESPERA)
            return
        elif "chatgpt" in t or "openai" in t or "gpt-image" in t or "dall-e" in t:
            ESPERANDO_ELECCION_MODELO_IMAGEN = False
            await hablar("Entendido, lanzo la generación con ChatGPT.")
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                await asyncio.gather(*[ws.send(json.dumps({"type": "generation_loading", "media_type": "image"})) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            resultado_img = await generar_imagen_xai(PROMPT_EN_ESPERA, force_model="openai")
            await manejar_resultado_imagen_global(resultado_img, PROMPT_EN_ESPERA)
            return
        elif any(keyword in t for keyword in ["cancelar", "cancela", "stop", "salir", "salte", "no"]):
            ESPERANDO_ELECCION_MODELO_IMAGEN = False
            await hablar("Generación de imagen cancelada.")
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            return
        else:
            await hablar("No entendí el modelo. Di 'Gemini', 'Grok', o 'ChatGPT', o haz clic en los botones de la pantalla.")
            return

    if ESPERANDO_ELECCION_MODELO_SITIO:
        t = texto_usuario.lower()
        if any(keyword in t for keyword in ["crea un sitio", "haz un sitio", "genera un sitio"]):
            ESPERANDO_ELECCION_MODELO_SITIO = False
            pass
        elif "gemini" in t or "google" in t:
            ESPERANDO_ELECCION_MODELO_SITIO = False
            MODELO_SITIO_ELEGIDO = "gemini"
        elif "claude" in t or "anthropic" in t:
            ESPERANDO_ELECCION_MODELO_SITIO = False
            MODELO_SITIO_ELEGIDO = "claude"
        elif "groq" in t or "llama" in t:
            ESPERANDO_ELECCION_MODELO_SITIO = False
            MODELO_SITIO_ELEGIDO = "groq"
        elif "mistral" in t:
            ESPERANDO_ELECCION_MODELO_SITIO = False
            MODELO_SITIO_ELEGIDO = "mistral"
        elif "grok" in t or "xai" in t or "twitter" in t:
            ESPERANDO_ELECCION_MODELO_SITIO = False
            MODELO_SITIO_ELEGIDO = "grok"
        elif "chatgpt" in t or "openai" in t or "chat gpt" in t:
            ESPERANDO_ELECCION_MODELO_SITIO = False
            MODELO_SITIO_ELEGIDO = "openai"
        elif "cancelar" in t or "detén" in t or "stop" in t or "déjalo" in t:
            ESPERANDO_ELECCION_MODELO_SITIO = False
            await hablar("Creación de sitio web cancelada.")
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_website_model_selector"})) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            return
        else:
            await hablar("No entendí el modelo. Di el nombre del agente o haz clic en los botones de la pantalla.")
            return

        if MODELO_SITIO_ELEGIDO:
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_website_model_selector"})) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            ESPERANDO_ELECCION_MODELO_IMAGEN_SITIO = True
            await hablar("¿Y con qué modelo quieres que genere las imágenes del sitio?")
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "ask_image_model"})) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            return

    if ESPERANDO_ELECCION_MODELO_IMAGEN_SITIO:
        t = texto_usuario.lower()
        if "gemini" in t or "google" in t or "imagen" in t:
            ESPERANDO_ELECCION_MODELO_IMAGEN_SITIO = False
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            asyncio.create_task(generar_sitio_web(PROMPT_EN_ESPERA, MODELO_SITIO_ELEGIDO, image_model="gemini"))
            return
        elif "grok" in t or "xai" in t or "twitter" in t:
            ESPERANDO_ELECCION_MODELO_IMAGEN_SITIO = False
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            asyncio.create_task(generar_sitio_web(PROMPT_EN_ESPERA, MODELO_SITIO_ELEGIDO, image_model="grok"))
            return
        elif "chatgpt" in t or "openai" in t or "gpt-image" in t or "dall-e" in t:
            ESPERANDO_ELECCION_MODELO_IMAGEN_SITIO = False
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            asyncio.create_task(generar_sitio_web(PROMPT_EN_ESPERA, MODELO_SITIO_ELEGIDO, image_model="openai"))
            return
        elif any(keyword in t for keyword in ["cancelar", "cancela", "stop", "salir", "salte", "no"]):
            ESPERANDO_ELECCION_MODELO_IMAGEN_SITIO = False
            await hablar("Generación de sitio cancelada.")
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            return
        else:
            await hablar("No entendí el modelo de imagen. Di 'Gemini', 'Grok', o 'ChatGPT', o haz clic en los botones de la pantalla.")
            return

    t = texto_usuario.lower()
    if ("prompt" in t or "promp" in t) and any(kw in t for kw in ["crea", "cree", "crear", "genera", "haz", "redacta", "escribe", "concebir"]):
        if len(texto_usuario.split()) < 6:
            ESPERANDO_CREACION_PROMPT = True
            await hablar("¿Qué tipo de prompt quieres que cree?")
            return

        await hablar("Generando el prompt detallado, un momento por favor.")
        asyncio.create_task(generar_prompt_especial(texto_usuario))
        return

    if any(keyword in t for keyword in ["crea un sitio", "haz un sitio", "genera un sitio", "crea un sitio web"]):
        if len(texto_usuario.split()) < 6:
            ESPERANDO_TEMA_SITIO = True
            await hablar("¿Qué tipo de sitio web quieres que cree?")
            return

        ESPERANDO_ELECCION_MODELO_SITIO = True
        PROMPT_EN_ESPERA = texto_usuario

        modelos_disponibles = []
        if gemini_activo:
            modelos_disponibles.append("gemini")
        if anthropic_cliente:
            modelos_disponibles.append("claude")
        if groq_cliente:
            modelos_disponibles.append("groq")
        if mistral_cliente:
            modelos_disponibles.append("mistral")
        if grok_cliente:
            modelos_disponibles.append("grok")
        if openai_cliente:
            modelos_disponibles.append("openai")

        await hablar(f"¿Con qué modelo de IA quieres que cree tu sitio web?")
        if CLIENTES_CONECTADOS:
            await asyncio.gather(*[ws.send(json.dumps({
                "type": "ask_website_model",
                "prompt": texto_usuario,
                "available_models": modelos_disponibles
            })) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
        return

    t = texto_usuario.lower()
    if any(keyword in t for keyword in ["crea una canción", "canta una canción", "genera una canción", "cántame una canción"]):
        if len(texto_usuario.split()) < 6:
            ESPERANDO_TEMA_MUSICA = True
            await hablar("¿Sobre qué tema quieres que componga esta canción?")
            return

        await hablar(f"Muy bien {NOMBRE_USUARIO}, compongo y te canto eso ahora mismo...")
        exito = await generar_y_cantar_musica(texto_usuario)
        if exito:
            return
        else:
            await hablar(f"Lo siento {NOMBRE_USUARIO}, mi módulo musical encontró un pequeño error. Vuelvo al modo estándar.")

    _disparadores_rap = ["rappeame", "hazme un rap", "crea un rap", "genera un rap", "compón un rap"]
    _disparadores_cancion = ["compónme una canción", "hazme una canción", "escribe una canción", "una canción sobre"]
    _disparadores_slam = ["hazme un slam", "crea un slam", "genera un slam", "compón un slam", "escribe un poema"]
    _disparadores_reggae = ["hazme un reggae", "crea un reggae", "un reggae sobre"]
    _disparadores_metal = ["hazme metal", "crea metal", "un metal sobre", "hazme hard rock"]
    _disparadores_pop = ["hazme pop", "crea pop", "una canción pop sobre"]
    _disparadores_blues = ["hazme blues", "crea blues", "un blues sobre"]
    _disparadores_rock = ["hazme rock", "crea rock", "un rock sobre"]
    _disparadores_electro = ["hazme electro", "crea electro", "un track electro sobre", "hazme un track"]

    _MAP_GENERO_DISPARADORES = [
        ("rap", _disparadores_rap),
        ("cancion", _disparadores_cancion),
        ("slam", _disparadores_slam),
        ("reggae", _disparadores_reggae),
        ("metal", _disparadores_metal),
        ("pop", _disparadores_pop),
        ("blues", _disparadores_blues),
        ("rock", _disparadores_rock),
        ("electro", _disparadores_electro),
    ]

    _genero_detectado = None
    for _genero_nombre, _genero_disparadores in _MAP_GENERO_DISPARADORES:
        if any(kw in t for kw in _genero_disparadores):
            _genero_detectado = _genero_nombre
            break

    if _genero_detectado and _MODULO_MUSICA_OK:
        _etiquetas = {"rap": "rap", "cancion": "canción", "slam": "slam",
                      "reggae": "reggae", "metal": "metal", "pop": "pop",
                      "blues": "blues", "rock": "rock", "electro": "electro"}
        _etiqueta = _etiquetas.get(_genero_detectado, _genero_detectado)

        _tema_bruto = texto_usuario.lower()
        for _kw in [kw for _, tlist in _MAP_GENERO_DISPARADORES for kw in tlist]:
            _tema_bruto = _tema_bruto.replace(_kw, " ").strip()

        for _parasito in ["omega", "por favor", "gracias"]:
            _tema_bruto = _tema_bruto.replace(_parasito, " ").strip()

        _tema_bruto = _tema_bruto.strip(" ,.:!?")

        if not _tema_bruto or _tema_bruto in ["sobre", "de", "para"]:
            ESPERANDO_TEMA_MUSICA = True
            MUSICA_GENERO_EN_ESPERA = _genero_detectado
            await hablar(f"¿Sobre qué tema quieres que te haga ese {_etiqueta}?")
            return

        await hablar(f"Muy bien {NOMBRE_USUARIO}, te compongo un {_etiqueta} ahora mismo...")
        try:
            if _instancia_musica_omega is None:
                from src.actions.jarvis_music import JarvisMusic as _JarvisMusic
                _instancia_musica_omega = _JarvisMusic()
            bucle = asyncio.get_event_loop()
            _texto_musica = await bucle.run_in_executor(
                None,
                lambda: _instancia_musica_omega.generar(theme=_tema_bruto, genre=_genero_detectado)
            )
            await hablar(_texto_musica)
            return
        except Exception as _e_music:
            print(f"[OMEGA_MUSIC] Error: {_e_music}")
            await hablar(f"Lo siento {NOMBRE_USUARIO}, no pude componer ese {_etiqueta}. Vuelvo al modo estándar.")
    elif _genero_detectado and not _MODULO_MUSICA_OK:
        await hablar(f"Lo siento {NOMBRE_USUARIO}, el módulo musical multi-género no está disponible. Verifica que jarvis_music.py esté presente.")
        return

    respuesta = await resolver_comandos_locales(texto_usuario)
    if not respuesta:
        respuesta = resolver_info_sistema_local(texto_usuario)
    if not respuesta:
        respuesta = resolver_matematica_local(texto_usuario)
    if not respuesta:
        respuesta = resolver_frances_local(texto_usuario)
    if not respuesta:
        respuesta = resolver_conversion_local(texto_usuario)
    if not respuesta:
        respuesta = resolver_traduccion_local(texto_usuario)
    if not respuesta:
        respuesta = await resolver_globo_local(texto_usuario)
    if not respuesta:
        respuesta = await resolver_extras_locales(texto_usuario)

    if not respuesta:
        t = texto_usuario.lower()
        if any(keyword in t for keyword in ["mira mi pantalla", "analiza mi pantalla", "ves mi pantalla", "qué hay en mi pantalla"]):
            await hablar(f"Claro {NOMBRE_USUARIO}, déjame echar un vistazo...")
            img_b64 = await solicitar_captura_pantalla()
            if img_b64:
                respuesta = await pedir_ia_vision(texto_usuario, img_b64)
            else:
                respuesta = f"Lo siento {NOMBRE_USUARIO}, no pude capturar tu pantalla. Asegúrate de haber hecho clic en 'Activar visión' en la interfaz y de haber autorizado el uso compartido."

        palabras_clave_camara = [
            "activa la cámara", "abre la cámara", "lanza la cámara",
            "mira con la cámara", "analiza lo que ves", "qué ves",
            "dime lo que ves", "mira lo que te muestro",
            "mi atuendo", "mi ropa", "cómo voy vestido",
            "me queda bien", "qué llevo puesto", "qué es esto",
            "describe este objeto", "identifica", "reconoce",
            "te muestro", "mira esto", "ves qué",
        ]
        palabras_clave_fullscreen = [
            "pon la cámara a pantalla completa", "cámara a pantalla completa",
            "pantalla completa cámara", "cámara en segundo plano"
        ]
        palabras_clave_small = [
            "vuelve a poner la cámara pequeña", "cámara pequeña",
            "quita la pantalla completa", "saca la pantalla completa"
        ]

        if any(kw in t for kw in palabras_clave_fullscreen) or t in ["cámara", "camara"]:
            msg = json.dumps({"type": "open_webcam", "fullscreen": True})
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            respuesta = f"He activado tu cámara a pantalla completa en segundo plano, {NOMBRE_USUARIO}."
        elif any(kw in t for kw in palabras_clave_small):
            msg = json.dumps({"type": "open_webcam", "fullscreen": False})
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            respuesta = f"He vuelto a poner la cámara en pequeño, {NOMBRE_USUARIO}."
        elif any(kw in t for kw in ["activa la cámara", "abre la cámara", "lanza la cámara"]):
            msg = json.dumps({"type": "open_webcam", "fullscreen": False})
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            respuesta = f"He activado el retorno de cámara, {NOMBRE_USUARIO}. Mira abajo a la derecha de tu pantalla."
        elif any(kw in t for kw in ["desactiva la cámara", "cierra la cámara"]):
            msg = json.dumps({"type": "close_webcam"})
            if CLIENTES_CONECTADOS:
                await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
            respuesta = f"He desactivado el retorno de cámara, {NOMBRE_USUARIO}."
        elif any(keyword in t for keyword in palabras_clave_camara):
            respuesta = await omega_vision_camara(texto_usuario)

    if not respuesta:
        origen = "teléfono" if mobile_ws else "ordenador"
        texto_para_ia = texto_usuario + f"\n\n[Nota del sistema: El usuario te habla actualmente desde su {origen}. Adapta tu respuesta si la pregunta se refiere a tu medio de escucha.]"
        respuesta = await pedir_ia(texto_para_ia)

    if mobile_ws and not target_pc:
        _saltar_audio_pc = True

    bloques_json = re.findall(r'\{.*?\}', respuesta, re.DOTALL)

    texto_limpio = re.sub(r'\{.*?\}', '', respuesta, flags=re.DOTALL).strip()
    tarea_hablar = None

    if texto_limpio:
        print(f"[OMEGA] {texto_limpio}")

    if not bloques_json:
        if texto_limpio:
            await hablar(texto_limpio)
        _saltar_audio_pc = False
        return

    if texto_limpio:
        tarea_hablar = asyncio.create_task(hablar(texto_limpio))

    for bloque in bloques_json:
        try:
            print(f"[OMEGA] Ejecutando acción: {bloque}")
            data = json.loads(bloque)
            accion = data.get("action", "")

            if accion == "modo_iron_man":
                estado = data.get("etat", "off")
                MODO_IRON_MAN = (estado == "on")
                msg = "Modo Iron Man activado, Señor. Quedo atento a tus señales." if MODO_IRON_MAN else "Modo Iron Man desactivado. Vuelvo al modo domótico."
                await hablar(msg)
            elif accion == "mostrar_receta":
                titulo = data.get("titre", "Receta")
                ingredientes = data.get("ingredients", [])
                instrucciones = data.get("instructions", [])
                msg_json = json.dumps({
                    "type": "show_recipe",
                    "titre": titulo,
                    "ingredients": ingredientes,
                    "instructions": instrucciones
                })
                if CLIENTES_CONECTADOS:
                    try:
                        await asyncio.gather(*[ws.send(msg_json) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                    except Exception as e:
                        print(f"[ERROR WS] Broadcast receta: {e}")
                await hablar(f"Aquí tienes la receta para {titulo}, mostrada en tu interfaz.")
            elif accion == "memorizar":
                clave = data.get("cle", "info")
                valor = data.get("valeur", "")
                agregar_memoria(clave, valor)
                await hablar(f"Bien anotado {NOMBRE_USUARIO}, recordaré que {valor}.")
            elif accion == "olvidar":
                clave = data.get("cle", "")
                exito = eliminar_memoria(clave)
                if exito:
                    await hablar("Información olvidada, {NOMBRE_USUARIO}.")
                else:
                    await hablar("No tenía esa información en memoria.")
            elif accion == "listar_memoria":
                memoria = cargar_memoria()
                if not memoria:
                    await hablar(f"No hay información personalizada en memoria, {NOMBRE_USUARIO}.")
                else:
                    lineas = ["Esto es lo que sé sobre ti, {NOMBRE_USUARIO}."]
                    for clave, data_m in memoria.items():
                        lineas.append(f"{clave}: {data_m['valor']}.")
                    await hablar(" ".join(lineas))
            elif accion == "obsidian_crear_nota":
                titulo = data.get("titre", "")
                contenido = data.get("contenu", "")
                exito, msg_res = src.actions.obsidian_helper.crear_o_modificar_nota(titulo, contenido)
                if exito:
                    if CLIENTES_CONECTADOS:
                        notas_list = src.actions.obsidian_helper.listar_notas()
                        msg_open = json.dumps({"type": "obsidian_open"})
                        msg_notas = json.dumps({"type": "obsidian_notes", "notes": notas_list})
                        await asyncio.gather(*[ws.send(msg_open) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                        await asyncio.gather(*[ws.send(msg_notas) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                        msg_content = json.dumps({
                            "type": "obsidian_note_content",
                            "titre": titulo,
                            "content": contenido
                        })
                        await asyncio.gather(*[ws.send(msg_content) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                await hablar(msg_res)
            elif accion == "obsidian_leer_nota":
                titulo = data.get("titre", "")
                exito, content = src.actions.obsidian_helper.leer_nota(titulo)
                if exito:
                    if CLIENTES_CONECTADOS:
                        msg_open = json.dumps({"type": "obsidian_open"})
                        msg_content = json.dumps({
                            "type": "obsidian_note_content",
                            "titre": titulo,
                            "content": content
                        })
                        await asyncio.gather(*[ws.send(msg_open) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                        await asyncio.gather(*[ws.send(msg_content) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                    preview = content[:200]
                    if len(content) > 200:
                        preview += "..."
                    await hablar(f"Aquí tienes el contenido de la nota {titulo}: {preview}")
                else:
                    await hablar(content)
            elif accion == "obsidian_buscar":
                query = data.get("query", "")
                resultados = src.actions.obsidian_helper.buscar_notas(query)
                if resultados:
                    if CLIENTES_CONECTADOS:
                        msg_open = json.dumps({"type": "obsidian_open"})
                        msg_resultados = json.dumps({
                            "type": "obsidian_search_results",
                            "query": query,
                            "results": resultados
                        })
                        await asyncio.gather(*[ws.send(msg_open) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                        await asyncio.gather(*[ws.send(msg_resultados) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                    nombres = [r["titre"] for r in resultados]
                    await hablar(f"He encontrado {len(resultados)} nota(s) con '{query}', {NOMBRE_USUARIO}: {', '.join(nombres)}.")
                else:
                    await hablar(f"No hay notas que coincidan con la búsqueda '{query}', {NOMBRE_USUARIO}.")
            elif accion == "obsidian_listar":
                notas_list = src.actions.obsidian_helper.listar_notas()
                if CLIENTES_CONECTADOS:
                    msg_open = json.dumps({"type": "obsidian_open"})
                    msg_notas = json.dumps({"type": "obsidian_notes", "notes": notas_list})
                    await asyncio.gather(*[ws.send(msg_open) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                    await asyncio.gather(*[ws.send(msg_notas) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                if notas_list:
                    await hablar(f"Muestro tus {len(notas_list)} notas Obsidian, {NOMBRE_USUARIO}.")
                else:
                    await hablar(f"Tu cofre Obsidian está vacío, {NOMBRE_USUARIO}.")
            elif accion == "abrir_carpeta":
                ruta = data.get("chemin", "escritorio")
                ok, resultado = abrir_carpeta(ruta)
                if ok:
                    await hablar(f"Carpeta abierta, {NOMBRE_USUARIO}. Dime si quieres que la ordene.")
                else:
                    await hablar(f"No encontré esa carpeta, {NOMBRE_USUARIO}. {resultado}")
            elif accion == "listar_carpeta":
                contenido, err = listar_carpeta()
                if err:
                    await hablar(err)
                else:
                    nb_archivos = len(contenido["fichiers"])
                    nb_carpetas = len(contenido["dossiers"])
                    await hablar(f"La carpeta contiene {nb_archivos} archivos y {nb_carpetas} subcarpetas, {NOMBRE_USUARIO}.")
            elif accion == "ordenar_por_tipo":
                await hablar(f"Ordenando tus archivos por tipo, {NOMBRE_USUARIO}. Un momento.")
                ok, msg = ordenar_por_tipo()
                await hablar(msg if ok else f"Problema al ordenar: {msg}")
            elif accion == "ordenar_por_fecha":
                await hablar(f"Ordenando tus archivos por fecha, {NOMBRE_USUARIO}. Un momento.")
                ok, msg = ordenar_por_fecha()
                await hablar(msg if ok else f"Problema al ordenar: {msg}")
            elif accion == "ordenar_completo":
                await hablar(f"Ordenando tus archivos por tipo y luego por fecha en cada categoría, {NOMBRE_USUARIO}.")
                ok, msg = ordenar_por_tipo_luego_fecha()
                await hablar(msg if ok else f"Problema al ordenar: {msg}")
            elif accion == "crear_carpeta":
                nombre = data.get("nom", "Nueva Carpeta")
                ok, msg = crear_subcarpeta(nombre)
                await hablar(msg if ok else f"Error: {msg}")
            elif accion == "renombrar_archivo":
                antiguo = data.get("ancien", "")
                nuevo = data.get("nouveau", "")
                ok, msg = renombrar_archivo(antiguo, nuevo)
                await hablar(msg if ok else f"Error: {msg}")
            elif accion == "mover_archivo":
                archivo = data.get("fichier", "")
                destino = data.get("destination", "")
                ok, msg = mover_archivo(archivo, destino)
                await hablar(msg if ok else f"Error: {msg}")
            elif accion == "buscar_archivo":
                nombre = data.get("nom", "")
                resultados, err = buscar_archivo(nombre)
                if err:
                    await hablar(err)
                elif not resultados:
                    await hablar(f"No se encontraron archivos con '{nombre}', {NOMBRE_USUARIO}.")
                else:
                    nombres = [os.path.basename(r) for r in resultados[:5]]
                    await hablar(f"He encontrado {len(resultados)} archivo(s). Por ejemplo: {', '.join(nombres)}.")
            elif accion == "ha_lumiere":
                pieza = data.get("piece", "salon").lower().strip()
                estado = data.get("etat", "on")
                color = data.get("couleur", None)
                luminosidad = data.get("luminosite", None)
                entity_id = PIEZAS_LUCES.get(pieza, f"light.{pieza}")
                rgb = COLORES_MAP.get(color) if color else None
                ha_luz(entity_id, estado, luminosidad, rgb)

                if estado == "off":
                    msg = f"Apago {pieza}."
                else:
                    detalles = []
                    if color:
                        detalles.append(f"en {color}")
                    if luminosidad is not None:
                        porcentaje = int((int(luminosidad) / 255) * 100)
                        detalles.append(f"al {porcentaje}%")

                    if detalles:
                        msg = f"Hecho, {pieza} ajustado{' '.join(detalles)}."
                    else:
                        msg = f"Luz de {pieza} encendida."
                await hablar(msg)
            elif accion == "ha_prise":
                pieza = data.get("piece", "bureau").lower().strip()
                estado = data.get("etat", "on")
                entity_id = PIEZAS_ENCHUFES.get(pieza, f"switch.enchufe_{pieza}")
                ha_interruptor(entity_id, estado)
                msg = f"Enchufe de {pieza} {'activado' if estado == 'on' else 'desactivado'}."
                await hablar(msg)
            elif accion == "ha_temperature":
                pieza = data.get("piece", "salon").lower().strip()
                entity_id = PIEZAS_SENSORES.get(pieza)
                if entity_id:
                    temp = ha_obtener_estado(entity_id)
                    hum_id = PIEZAS_HUMEDAD.get(pieza)
                    hum = ha_obtener_estado(hum_id) if hum_id else None
                    hum_val = str(hum) if (hum and str(hum) != "desconocido") else None
                    if str(temp) != "desconocido":
                        await enviar_temp_pieza({
                            "piece": pieza,
                            "temperature": str(temp),
                            "humidite": hum_val,
                        })
                    await hablar(f"La temperatura en {pieza} es de {temp} grados.")
                else:
                    await hablar(f"Lo siento, no tengo sensor configurado para {pieza}.")
            elif accion == "ha_humidite":
                pieza = data.get("piece", "bureau").lower().strip()
                entity_id = PIEZAS_HUMEDAD.get(pieza) or PIEZAS_SENSORES.get(pieza)
                if entity_id:
                    humi = ha_obtener_estado(entity_id)
                    await hablar(f"La humedad en {pieza} es del {humi}%.")
                else:
                    await hablar(f"No tengo sensor de humedad para {pieza}.")
            elif accion == "ha_batterie":
                aparato = data.get("appareil", "").lower()
                entity_id = APARATOS_BATERIA.get(aparato)
                if entity_id:
                    batt = ha_obtener_estado(entity_id)
                    if batt == "unknown":
                        await hablar(f"No puedo obtener el estado de la batería para {aparato}.")
                    else:
                        suf = ""
                        if "telefono" in aparato or NOMBRE_USUARIO.lower() in aparato:
                            suf = "Tu teléfono está al "
                        else:
                            suf = f"La batería de {aparato} está al "
                        await hablar(f"{suf}{batt}%.")
                else:
                    await hablar(f"No tengo el aparato {aparato} en mi lista de baterías.")
            elif accion == "ha_thermostat":
                temp = data.get("temperature", 20)
                ha_termostato("climate.termostato", temp)
                await hablar(f"Termostato ajustado a {temp} grados.")
            elif accion == "ha_scene":
                nombre = data.get("nom", "")
                scene_id = f"scene.{nombre}"
                ha_escena(scene_id)
                await hablar(f"Ambiente {nombre} activado.")
            elif accion == "ha_alarme":
                estado = data.get("etat", "on")
                if estado == "on":
                    ha_llamar_servicio("alarm_control_panel", "alarm_arm_away", "alarm_control_panel.casa_base_2")
                    await hablar("Alarma activada.")
                else:
                    ha_llamar_servicio("alarm_control_panel", "alarm_disarm", "alarm_control_panel.casa_base_2")
                    await hablar("Alarma desactivada.")
            elif accion == "ha_verrou":
                entity_id = data.get("entity_id", "lock.puerta_casa")
                estado = data.get("etat", "lock")
                ha_cerradura(entity_id, estado)
                msg = "Puerta cerrada, {NOMBRE_USUARIO}." if estado == "lock" else "Puerta abierta, {NOMBRE_USUARIO}."
                await hablar(msg)
            elif accion == "ha_simulation":
                estado = data.get("etat", "on")
                ha_interruptor("switch.simulation", estado)
                msg = "Simulación de presencia activada." if estado == "on" else "Simulación de presencia desactivada."
                await hablar(msg)
            elif accion == "ha_anniversaires":
                eventos = ha_obtener_calendario("calendar.cumpleaños")
                if not eventos:
                    await hablar("No hay nada planeado para hoy.")
                else:
                    nombres = [e.get("summary", "Cumpleaños sin nombre") for e in eventos]
                    if len(nombres) == 1:
                        await hablar(f"Hoy celebramos el cumpleaños de {nombres[0]}. ¡No olvides felicitarlo!")
                    else:
                        lista = ", ".join(nombres[:-1]) + " y " + nombres[-1]
                        await hablar(f"Hoy hay varios cumpleaños: {lista}. ¡Día ajetreado!")
            elif accion == "ha_consommation":
                entity_id = PIEZAS_SENSORES.get("consumo")
                potencia = ha_obtener_estado(entity_id)
                if potencia == "desconocido" or potencia == "unknown":
                    await hablar("No puedo leer el consumo eléctrico por ahora.")
                else:
                    await hablar(f"El consumo actual de la casa es de {potencia} Volt-Amperios.")
            elif accion == "ha_tiktok":
                entity_id = PIEZAS_SENSORES.get("tiktok")
                seguidores = ha_obtener_estado(entity_id)
                await hablar(f"Tienes actualmente {seguidores} seguidores en tu cuenta TikTok TechEnClair, {NOMBRE_USUARIO}. ¡Felicidades!")
            elif accion == "ha_oeufs":
                entity_id = PIEZAS_SENSORES.get("huevos")
                try:
                    r = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=HA_HEADERS, timeout=5)
                    data = r.json()
                    last_changed = data.get("last_changed", "")
                    if last_changed:
                        dt = datetime.fromisoformat(last_changed.replace("Z", "+00:00"))
                        frase = dt.strftime("el %d de %B a las %Hh%M")
                        await hablar(f"La última recogida de huevos se registró {frase}.")
                    else:
                        await hablar("No tengo historial de recogida de huevos.")
                except:
                    await hablar("No puedo acceder a la información de los huevos.")
            elif accion == "ha_energie":
                periodo = data.get("periode", "mes")
                aparato = data.get("appareil", "")

                if aparato:
                    aparato_limpio = aparato.lower()
                    entidad = APARATOS_ENERGIA.get(aparato_limpio)
                    if entidad:
                        val = ha_obtener_estado(entidad)
                        if val != "desconocido" and val != "unknown":
                            kwh = float(val)
                            await hablar(f"El consumo de {aparato} para este mes es de {kwh:.1f} kWh.")
                        else:
                            await hablar(f"No tengo datos de consumo para {aparato} por ahora.")
                    else:
                        await hablar(f"No tengo un aparato llamado {aparato} en mi seguimiento energético.")
                elif periodo == "ayer":
                    total_kwh = 0
                    total_cost = 0
                    try:
                        for i in range(1, 7):
                            e_id = f"sensor.lixee_zlinky_tic_zlinky_p{i}_daily"
                            val = ha_obtener_estado(e_id, attribut="last_period")
                            if val != "desconocido" and val != "unknown":
                                k = float(val)
                                total_kwh += k
                                total_cost += k * HA_TARIFAS.get(f"p{i}", 0.16)
                        await hablar(f"Ayer, la casa consumió {total_kwh:.1f} kWh, con un coste estimado de {total_cost:.2f} euros.")
                    except:
                        await hablar("Tuve un problema al calcular el consumo de ayer.")
                else:
                    total_kwh = 0
                    total_cost = 0
                    try:
                        for i in range(1, 7):
                            e_id = f"sensor.lixee_zlinky_tic_zlinky_p{i}_mensual"
                            val = ha_obtener_estado(e_id)
                            if val != "desconocido" and val != "unknown":
                                k = float(val)
                                total_kwh += k
                                total_cost += k * HA_TARIFAS.get(f"p{i}", 0.16)
                        await hablar(f"Este mes, el consumo total es de {total_kwh:.1f} kWh, por un importe de {total_cost:.2f} euros.")
                    except:
                        await hablar("No pude calcular el consumo mensual.")
            elif accion == "ha_aspirateur":
                comando = data.get("commande", "start")
                if comando == "start":
                    ha_llamar_servicio("vacuum", "start", "vacuum.bob")
                    await hablar("Allá vamos, Bob inicia la limpieza.")
                elif comando == "stop":
                    ha_llamar_servicio("vacuum", "stop", "vacuum.bob")
                    await hablar("He detenido el aspirador.")
                elif comando == "pause":
                    ha_llamar_servicio("vacuum", "pause", "vacuum.bob")
                    await hablar("Bob está en pausa.")
                elif comando == "base":
                    ha_llamar_servicio("vacuum", "return_to_base", "vacuum.bob")
                    await hablar("Bob vuelve a su base.")
            elif accion == "create_doc":
                titulo = data.get("title", "Documento OMEGA")
                contenido = data.get("content", "")
                resultado = crear_google_doc(titulo, contenido)
                await hablar(resultado)
            elif accion == "write_doc":
                contenido = data.get("content", "")
                resultado = modificar_google_doc(contenido)
                await hablar(resultado)
            elif accion == "create_sheet":
                titulo = data.get("title", "Hoja OMEGA")
                resultado = crear_google_sheet(titulo)
                await hablar(resultado)
            elif accion == "read_emails":
                resultado = leer_emails()
                await hablar(f"Aquí tienes tus últimos correos, {NOMBRE_USUARIO}. {resultado}")
            elif accion == "read_calendar":
                resultado = listar_eventos_calendar()
                await hablar(f"Aquí tienes tus próximos eventos, {NOMBRE_USUARIO}. {resultado}")
            elif accion == "meteo":
                ciudad = data.get("ville") or None
                await hablar(f"Consultando el tiempo, un momento.")
                resultado = obtener_meteo_actual(ciudad)
                datos_meteo = obtener_meteo_estructurada(ciudad)
                if datos_meteo:
                    await enviar_meteo_web(datos_meteo)
                await hablar(resultado)
            elif accion == "alerte_meteo":
                ciudad = data.get("ville") or None
                resultado = obtener_alertas_meteo(ciudad)
                await hablar(resultado)
            elif accion == "busqueda_web":
                query = data.get("query", "")
                await hablar(f"Buscando en internet {query}.")
                resultado = buscar_web_serpapi(query)
                await hablar(resultado)
            elif accion == "generar_imagen":
                prompt_fr = data.get("prompt", "")
                if not prompt_fr:
                    await hablar(f"Lo siento {NOMBRE_USUARIO}, no entendí lo que quieres que genere.")
                else:
                    ESPERANDO_ELECCION_MODELO_IMAGEN = True
                    PROMPT_EN_ESPERA = prompt_fr

                    await hablar(f"¿Con qué modelo de generación de imagen quieres que cree tu imagen?")
                    if CLIENTES_CONECTADOS:
                        await asyncio.gather(*[ws.send(json.dumps({
                            "type": "ask_image_model",
                            "prompt": prompt_fr
                        })) for ws in CLIENTES_CONECTADOS], return_exceptions=True)

            elif accion == "generar_video":
                prompt_fr = data.get("prompt", "")
                if not prompt_fr:
                    await hablar(f"Lo siento {NOMBRE_USUARIO}, no entendí lo que quieres que genere como video.")
                elif not grok_cliente:
                    await hablar(f"Lo siento {NOMBRE_USUARIO}, el cliente xAI no está configurado. La generación de video requiere una clave xAI.")
                else:
                    await hablar(f"Generando tu video con xAI, puede tomar uno o dos minutos {NOMBRE_USUARIO}. ¡Paciencia!")

                    msg_cargando = json.dumps({"type": "generation_loading", "media_type": "video"})
                    if CLIENTES_CONECTADOS:
                        try:
                            await asyncio.gather(*[ws.send(msg_cargando) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                        except Exception:
                            pass

                    result_vid = await generar_video_xai(prompt_fr)
                    if "error" in result_vid:
                        print(f"[VIDEO_GEN] Error: {result_vid['error']}")
                        if CLIENTES_CONECTADOS:
                            try:
                                await asyncio.gather(*[ws.send(json.dumps({"type": "hide_generation_loading"})) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                            except:
                                pass
                        await hablar(f"Lo siento {NOMBRE_USUARIO}, la generación del video falló: {result_vid['error'][:80]}")
                    else:
                        fuente = result_vid.get('source', 'xAI')
                        msg_json = json.dumps({
                            "type": "show_generated_video",
                            "prompt_fr": prompt_fr,
                            "prompt_en": result_vid.get("prompt_en", prompt_fr),
                            "url": result_vid["url"],
                            "path": result_vid.get("path", ""),
                            "source": fuente,
                        })
                        if CLIENTES_CONECTADOS:
                            try:
                                await asyncio.gather(*[ws.send(msg_json) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                            except Exception as _e:
                                print(f"[ERROR WS] Broadcast video: {_e}")
                        await hablar(f"¡Aquí tienes {NOMBRE_USUARIO}! El video ha sido generado por {fuente}, se muestra en pantalla y se guarda automáticamente en mi carpeta de instalación.")

            elif accion == "busqueda_imagenes":
                query = data.get("query", "")
                nb = int(data.get("nb", 6))
                if not texto_limpio:
                    await hablar(f"Buscando imágenes de {query} en internet, un momento {NOMBRE_USUARIO}.")
                cfg = _cargar_config()
                motor = cfg.get("image_search_engine", "serpapi")
                urls = await asyncio.to_thread(buscar_imagenes_web, query, nb_imagenes=nb, motor=motor)
                if urls:
                    msg_json = json.dumps({
                        "type": "show_images",
                        "query": query,
                        "images": urls,
                    })
                    if CLIENTES_CONECTADOS:
                        try:
                            await asyncio.gather(*[ws.send(msg_json) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                        except Exception as e:
                            print(f"[ERROR WS] Broadcast imágenes: {e}")
                    if not texto_limpio:
                        await hablar(f"Aquí tienes, muestro {len(urls)} imagen{'es' if len(urls) > 1 else ''} de {query} en tu interfaz, {NOMBRE_USUARIO}.")
                else:
                    if not texto_limpio:
                        await hablar(f"Lo siento {NOMBRE_USUARIO}, no encontré imágenes para {query}. Verifica tu conexión a internet.")

            elif accion == "antivirus_scan":
                if CLIENTES_CONECTADOS:
                    msg = json.dumps({"type": "av_open"})
                    await asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True)
                await hablar(f"Inicializando el protocolo de análisis de seguridad de tu sistema, {NOMBRE_USUARIO}. Escaneo en curso.")

            elif accion == "restaurant_search":
                global ULTIMOS_RESTAURANTES_MOSTRADOS
                ULTIMOS_RESTAURANTES_MOSTRADOS = []
                ubicacion = data.get("location", "")
                if ubicacion:
                    lat, lng = None, None
                else:
                    if CIUDAD_POR_DEFECTO:
                        ubicacion = CIUDAD_POR_DEFECTO
                        lat = LAT_POR_DEFECTO if LAT_POR_DEFECTO else None
                        lng = LON_POR_DEFECTO if LON_POR_DEFECTO else None
                    else:
                        ubicacion = obtener_ciudad_por_ip()
                        lat = UBICACION_USUARIO_GPS.get("lat") if UBICACION_USUARIO_GPS else None
                        lng = UBICACION_USUARIO_GPS.get("lng") if UBICACION_USUARIO_GPS else None
                await hablar(f"Buscando restaurantes cerca de {ubicacion.split(',')[0]} e inicio el radar de localización, un momento {NOMBRE_USUARIO}.")
                lanzar_busqueda_restaurantes_fondo(ubicacion, lat, lng, [], False)

            elif accion == "sport_resultats":
                equipo = data.get("equipe") or None
                liga = data.get("ligue") or None
                print(f"[DEPORTE] Acción sport_resultats para {equipo or liga}")
                await hablar(f"Buscando información para {equipo or liga}, un momento.")
                resultado = obtener_resultados_futbol(equipo=equipo, liga=liga)
                if "no encontrado" in resultado or "Imposible" in resultado:
                    print(f"[DEPORTE] Fallo búsqueda local. Verificando con Grok...")
                    if grok_cliente:
                        res_grok = await pedir_grok(f"{NOMBRE_USUARIO} quiere saber: {texto_usuario}. No encontré la información en mi base de datos de fútbol, ¿puedes buscarla para él?")
                        if res_grok:
                            resultado = res_grok
                await hablar(resultado)
            elif accion == "sport_classement":
                liga = data.get("ligue", "Liga 1")
                await hablar(f"Recuperando la clasificación de {liga}.")
                resultado = obtener_clasificacion_futbol(liga=liga)
                await hablar(resultado)
            elif accion == "sport_live":
                pregunta = data.get("question", "últimos resultados deportivos 2026")
                await hablar(f"Buscando los últimos resultados en directo, un momento {NOMBRE_USUARIO}.")
                from datetime import datetime as _dt
                _fecha_hoy = _dt.now().strftime("%d/%m/%Y")
                resultado = obtener_resultados_deporte_gemini(
                    f"Hoy es {_fecha_hoy}. {pregunta}. "
                    f"Dame todos los partidos programados ESTA NOCHE ({_fecha_hoy}) así como los resultados del día. "
                    f"Mundial 2026, Liga 1, Liga, Premier League, Champions League, etc."
                )
                await hablar(resultado)
            elif accion == "ver_pantalla":
                inst = data.get("instruction", "")
                res = await omega_vision_clicar(inst)
                await hablar(res)
            elif accion == "whatsapp_llamada":
                contacto = data.get("contact", "Mi vida")
                await accion_whatsapp_llamada(contacto)
            elif accion == "vision_escribir":
                inst = data.get("instruction", "")
                txt = data.get("texte", "")
                res = await omega_vision_escribir(inst, txt)
                await hablar(res)
            elif accion == "vision_buscar_en_sitio":
                txt = data.get("texte", "")
                await hablar(f"Buscando la barra de búsqueda en este sitio, {NOMBRE_USUARIO}.")
                res = await omega_vision_buscar_en_sitio(txt)
                await hablar(res)
            elif accion == "lanzar_camara":
                res = await omega_vision_camara(texto_usuario)
                await hablar(res)
            elif accion == "vision_navegador":
                res = await omega_vision_navegador(texto_usuario)
                await hablar(res)
            elif accion == "dictado":
                texto = data.get("texte", "")
                if texto:
                    import pyautogui
                    import pyperclip
                    import time
                    pyperclip.copy(texto)
                    time.sleep(0.1)
                    pyautogui.hotkey('ctrl', 'v')
                    await hablar(f"Escrito, {NOMBRE_USUARIO}.")
            elif accion == "spotify_abrir":
                await hablar(f"Abriendo Spotify, {NOMBRE_USUARIO}.")
                res = await spotify_abrir()
                await hablar(res)
            elif accion == "spotify_buscar":
                busqueda = data.get("recherche", "")
                await hablar(f"Buscando '{busqueda}' en Spotify, {NOMBRE_USUARIO}.")
                res = await spotify_buscar(busqueda)
                await hablar(res)
            elif accion == "spotify_reproduccion_pausa":
                res = await spotify_reproduccion_pausa()
                await hablar(res)
            elif accion == "spotify_detener":
                res = await spotify_detener()
                await hablar(res)
            elif accion == "spotify_siguiente":
                res = await spotify_siguiente()
                await hablar(res)
            elif accion == "spotify_anterior":
                res = await spotify_anterior()
                await hablar(res)
            elif accion == "spotify_volumen":
                direccion = data.get("direction", "subir")
                palieres = data.get("paliers", 4)
                res = await spotify_volumen(direccion, palieres)
                await hablar(res)
            elif accion == "deezer_abrir":
                await hablar(f"Abriendo Deezer, {NOMBRE_USUARIO}.")
                res = await deezer_abrir()
                await hablar(res)
            elif accion == "deezer_buscar":
                busqueda = data.get("recherche", "")
                await hablar(f"Buscando '{busqueda}' en Deezer, {NOMBRE_USUARIO}.")
                res = await deezer_buscar(busqueda)
                await hablar(res)
            elif accion == "deezer_reproduccion_pausa":
                res = await deezer_reproduccion_pausa()
                await hablar(res)
            elif accion == "deezer_detener":
                res = await deezer_detener()
                await hablar(res)
            elif accion == "deezer_siguiente":
                res = await deezer_siguiente()
                await hablar(res)
            elif accion == "deezer_anterior":
                res = await deezer_anterior()
                await hablar(res)
            elif accion == "deezer_volumen":
                direccion = data.get("direction", "subir")
                palieres = data.get("paliers", 4)
                res = await deezer_volumen(direccion, palieres)
                await hablar(res)

        except Exception as e:
            print(f"[ERROR ACCIÓN] Bloque falló: {bloque} | Error: {e}")
            if grok_cliente:
                print("[OMEGA] Cambiando a Grok tras error de acción...")
                res_grok = await pedir_grok(f"{NOMBRE_USUARIO} me pidió: {texto_usuario}. Intenté lanzar una acción pero tuve un error técnico ({e}). ¿Puedes tomar el relevo y responderle con elegancia?")
                if res_grok:
                    await hablar(res_grok)
            continue

    if tarea_hablar:
        await tarea_hablar

    _saltar_audio_pc = False

def limpiar_comando(texto):
    global PALABRA_ACTIVACION
    t = texto.lower().strip()

    hesitaciones = ["eh", "bueno", "entonces", "por favor", "gracias"]

    palabras = t.split()
    while palabras and palabras[0] in hesitaciones:
        palabras.pop(0)
    t = " ".join(palabras)

    p = PALABRA_ACTIVACION.lower().strip()
    for variante in [p + ",", p]:
        if t.startswith(variante):
            t = t[len(variante):].strip()

    palabras = t.split()
    while palabras and palabras[-1] in hesitaciones:
        palabras.pop()
    t = " ".join(palabras)

    return t

PALABRA_ACTIVACION = _cargar_config().get("wake_word", "omega").lower().strip()
TIEMPO_ESPERA_SESION = 30
DETENER_HABLA = False
MICRO_MUTED = False
esta_escuchando = False
esta_hablando = False
omega_activo = False
ultimo_mensaje = 0
interfaz_ya_conectada = False

def _guardar_config(datos: dict) -> None:
    try:
        import json
        cfg = _cargar_config()
        cfg.update(datos)
        with open(_RUTA_CONFIG_JARVIS, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[MIC] No se pudo guardar la configuración: {e}")

async def bucle_recordatorios():
    while True:
        try:
            cfg = _cargar_config()
            recordatorios = cfg.get("reminders", [])

            ahora = datetime.now()
            hora_actual = ahora.strftime("%H:%M")
            fecha_actual = ahora.strftime("%Y-%m-%d")

            modificado = False
            for r in recordatorios:
                if not r.get("triggered", False):
                    r_hora = r.get("time")
                    r_fecha = r.get("date")

                    if r_hora == hora_actual:
                        if not r_fecha or r_fecha == fecha_actual:
                            r["triggered"] = True
                            modificado = True

                            msg = json.dumps({
                                "type": "reminder_trigger",
                                "id": r["id"],
                                "text": r["text"],
                                "time": r_hora,
                                "date": r_fecha or "Todos los días"
                            })
                            print(f"[RECORDATORIOS] Disparando recordatorio: {r['text']}")
                            if CLIENTES_CONECTADOS:
                                asyncio.ensure_future(asyncio.gather(*[ws.send(msg) for ws in CLIENTES_CONECTADOS], return_exceptions=True))

                            asyncio.create_task(hablar(f"Recordatorio, {NOMBRE_USUARIO}. Es hora de: {r['text']}."))

            if modificado:
                _guardar_config({"reminders": recordatorios})
                if CLIENTES_CONECTADOS:
                    msg_ajustes = json.dumps({"type": "settings_data", "data": _cargar_config()})
                    asyncio.ensure_future(asyncio.gather(*[ws.send(msg_ajustes) for ws in CLIENTES_CONECTADOS], return_exceptions=True))

        except Exception as e:
            print(f"[RECORDATORIOS] Error en bucle: {e}")

        await asyncio.sleep(15)

AV_LIVE_PROTECTION_ENABLED = False
AV_LIVE_REPORTED_THREATS = set()

async def bucle_antivirus_live():
    global AV_LIVE_PROTECTION_ENABLED, AV_LIVE_REPORTED_THREATS
    import json
    import os
    import time
    import stat
    import shutil
    import psutil
    from src.actions.antivirus_scanner import es_archivo_sospechoso, obtener_exclusiones, esta_excluido

    try:
        cfg = _cargar_config()
        AV_LIVE_PROTECTION_ENABLED = cfg.get("av_live_protection", False)
    except Exception:
        AV_LIVE_PROTECTION_ENABLED = False

    print(f"[AV LIVE] Protección en tiempo real inicializada: {'ACTIVA' if AV_LIVE_PROTECTION_ENABLED else 'INACTIVA'}")

    ultimo_check_time = time.time()

    while True:
        try:
            if AV_LIVE_PROTECTION_ENABLED:
                carpetas = [
                    os.path.expanduser("~/Desktop"),
                    os.path.expanduser("~/Downloads"),
                    os.environ.get("TEMP"),
                    os.environ.get("TMP"),
                    os.path.dirname(os.path.abspath(__file__))
                ]
                carpetas = list(set([os.path.abspath(f) for f in carpetas if f and os.path.exists(f)]))
                exclusiones = obtener_exclusiones()
                tiempo_actual = time.time()

                for carpeta in carpetas:
                    try:
                        for archivo in os.listdir(carpeta):
                            ruta_archivo = os.path.join(carpeta, archivo)
                            if os.path.isfile(ruta_archivo):
                                try:
                                    mtime = os.path.getmtime(ruta_archivo)
                                    if mtime > ultimo_check_time:
                                        ruta_normalizada = os.path.normpath(ruta_archivo).lower()
                                        if ruta_normalizada in AV_LIVE_REPORTED_THREATS:
                                            continue

                                        t_class, t_desc = es_archivo_sospechoso(ruta_archivo)
                                        if t_class:
                                            if esta_excluido(ruta_archivo, exclusiones):
                                                continue

                                            AV_LIVE_REPORTED_THREATS.add(ruta_normalizada)
                                            print(f"[AV LIVE] Amenaza detectada: {ruta_archivo} ({t_class})")

                                            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                                                try:
                                                    ruta_exe = proc.info.get('exe')
                                                    if ruta_exe and os.path.normpath(ruta_exe).lower() == ruta_normalizada:
                                                        print(f"[AV LIVE] Deteniendo proceso {proc.info['name']} (PID {proc.info['pid']})")
                                                        p = psutil.Process(proc.info['pid'])
                                                        p.terminate()
                                                        try:
                                                            p.wait(timeout=1.0)
                                                        except psutil.TimeoutExpired:
                                                            p.kill()
                                                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                                                    pass

                                            try:
                                                os.chmod(ruta_archivo, stat.S_IWRITE)
                                            except Exception:
                                                pass

                                            carpeta_cuarentena = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quarantine")
                                            os.makedirs(carpeta_cuarentena, exist_ok=True)
                                            nombre_seguro = f"{int(time.time())}_{archivo}.quarantine"
                                            destino = os.path.join(carpeta_cuarentena, nombre_seguro)
                                            shutil.move(ruta_archivo, destino)

                                            msg = {
                                                "type": "av_live_threat_intercepted",
                                                "threat": {
                                                    "type": "file",
                                                    "name": archivo,
                                                    "target": ruta_archivo,
                                                    "class": t_class,
                                                    "desc": f"INTERCEPTADO & ASEGURADO. {t_desc}"
                                                },
                                                "quarantine_file": nombre_seguro
                                            }
                                            if CLIENTES_CONECTADOS:
                                                asyncio.ensure_future(asyncio.gather(*[ws.send(json.dumps(msg)) for ws in CLIENTES_CONECTADOS], return_exceptions=True))

                                            asyncio.create_task(hablar(f"Alerta de seguridad, {NOMBRE_USUARIO}. He detectado y neutralizado una amenaza en tiempo real: {archivo}. El archivo sospechoso ha sido puesto en cuarentena."))
                                except OSError:
                                    pass
                    except Exception as e:
                        print(f"[AV LIVE] Error en carpeta {carpeta}: {e}")

                for proc in psutil.process_iter(['pid', 'name', 'exe']):
                    try:
                        pid = proc.info.get('pid')
                        name = proc.info.get('name') or ''
                        exe = proc.info.get('exe') or ''

                        clave_objetivo = f"PID {pid} ({exe})"
                        exe_normalizado = os.path.normpath(exe).lower() if exe else ""

                        if clave_objetivo in AV_LIVE_REPORTED_THREATS or (exe_normalizado and exe_normalizado in AV_LIVE_REPORTED_THREATS):
                            continue

                        name_bajo = name.lower()
                        exe_bajo = exe.lower()

                        detectado = False
                        desc = ""
                        if "mimikatz" in name_bajo or "miner.exe" in name_bajo or "keylogger" in name_bajo:
                            detectado = True
                            desc = "Proceso sospechoso (amenaza conocida)"
                        elif ("temp" in exe_bajo or "tmp" in exe_bajo) and name_bajo.endswith((".exe", ".bat")):
                            if ("docker" in name_bajo and "installer" in name_bajo) or name_bajo == "7zr.exe":
                                detectado = False
                            else:
                                detectado = True
                                desc = "Proceso activo lanzado desde carpeta temporal"

                        if detectado:
                            if esta_excluido(clave_objetivo, exclusiones) or (exe and esta_excluido(exe, exclusiones)):
                                continue

                            AV_LIVE_REPORTED_THREATS.add(clave_objetivo)
                            print(f"[AV LIVE] Proceso sospechoso neutralizado: {name} (PID {pid})")

                            p = psutil.Process(pid)
                            p.terminate()
                            try:
                                p.wait(timeout=1.0)
                            except psutil.TimeoutExpired:
                                p.kill()

                            msg = {
                                "type": "av_live_threat_intercepted",
                                "threat": {
                                    "type": "process",
                                    "name": name,
                                    "target": clave_objetivo,
                                    "class": "Suspicious.ActiveProcess",
                                    "desc": f"PROCESO DETENIDO & NEUTRALIZADO. {desc}"
                                }
                            }
                            if CLIENTES_CONECTADOS:
                                asyncio.ensure_future(asyncio.gather(*[ws.send(json.dumps(msg)) for ws in CLIENTES_CONECTADOS], return_exceptions=True))

                            asyncio.create_task(hablar(f"Seguridad del sistema, {NOMBRE_USUARIO}. He interceptado y detenido un proceso sospechoso activo: {name}."))
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass

                ultimo_check_time = tiempo_actual
        except Exception as e:
            print(f"[AV LIVE] Error en bucle principal: {e}")

        await asyncio.sleep(3)

def detectar_microfono() -> int | None:
    import json

    if pyaudio:
        try:
            p = pyaudio.PyAudio()
            nb = p.get_device_count()
            entradas = []
            print("[MIC] Dispositivos de audio detectados:")
            for i in range(nb):
                try:
                    info = p.get_device_info_by_index(i)
                    if info.get("maxInputChannels", 0) > 0:
                        nombre = info.get("name", f"Dispositivo {i}")
                        entradas.append((i, nombre))
                        print(f"      [{i}] {nombre}")
                except Exception:
                    pass
            p.terminate()

            if not entradas:
                print("[MIC] ⚠ No se detectaron dispositivos de entrada por PyAudio.")
        except Exception as e:
            print(f"[MIC] No se pudieron listar los dispositivos: {e}")
            entradas = []
    else:
        entradas = []
        print("[MIC] PyAudio ausente — modo fallback speech_recognition solamente.")

    cfg = _cargar_config()
    indice_memo = cfg.get("mic_device_index", None)

    def _probar_indice(idx):
        try:
            kwargs = {} if idx is None else {"device_index": idx}
            mic_test = sr.Microphone(**kwargs)
            r_test = sr.Recognizer()
            with mic_test as src:
                r_test.adjust_for_ambient_noise(src, duration=0.3)
            return True
        except Exception as e:
            etiqueta = "por defecto" if idx is None else str(idx)
            print(f"[MIC]   Índice {etiqueta} → KO ({e})")
            return False

    if indice_memo is not None:
        nombre_memo = next((n for i, n in entradas if i == indice_memo), f"Índice {indice_memo}")
        print(f"[MIC] Probando micro memorizado: [{indice_memo}] {nombre_memo}")
        if _probar_indice(indice_memo):
            print(f"[MIC] ✔ Micro seleccionado (memorizado): [{indice_memo}] {nombre_memo}")
            return indice_memo
        else:
            print(f"[MIC] Micro memorizado no encontrado, buscando reemplazo...")

    print("[MIC] Probando micro por defecto del sistema...")
    if _probar_indice(None):
        idx_real = None
        if pyaudio:
            try:
                p = pyaudio.PyAudio()
                idx_real = p.get_default_input_device_info().get("index", None)
                p.terminate()
            except Exception:
                pass
        nombre_def = next((n for i, n in entradas if i == idx_real), "Por defecto del sistema")
        print(f"[MIC] ✔ Micro seleccionado (por defecto): [{idx_real}] {nombre_def}")
        _guardar_config({"mic_device_index": idx_real})
        return idx_real

    print("[MIC] Buscando en todos los dispositivos disponibles...")
    for idx, nombre in entradas:
        print(f"[MIC]   Probando [{idx}] {nombre}...")
        if _probar_indice(idx):
            print(f"[MIC] ✔ Micro seleccionado (fallback): [{idx}] {nombre}")
            _guardar_config({"mic_device_index": idx})
            return idx

    print("[MIC] ⚠ No se encontró ningún micrófono funcional.")
    print("[MIC]   Verifica que tu micro esté conectado y autorizado en")
    print("[MIC]   Configuración de Windows → Privacidad → Micrófono.")
    _guardar_config({"mic_device_index": None})
    return None

def escuchar():
    global esta_escuchando, omega_activo, ultimo_mensaje, DETENER_HABLA, esta_hablando, MICRO_NECESITA_RECARGAR

    r = sr.Recognizer()

    indice_mic = detectar_microfono()
    if indice_mic is not None:
        mic = sr.Microphone(device_index=indice_mic)
        print(f"[OMEGA] Micrófono seleccionado: índice {indice_mic}")
    else:
        mic = sr.Microphone()
        print("[OMEGA] Micrófono: dispositivo por defecto del sistema")

    r.pause_threshold = 0.8
    r.non_speaking_duration = 0.6
    r.energy_threshold = 300
    r.dynamic_energy_threshold = True

    try:
        with mic as source:
            r.adjust_for_ambient_noise(source, duration=1)
    except Exception as e:
        print(f"[MIC] ⚠ Calibración imposible: {e}")
        mic = sr.Microphone()
        try:
            with mic as source:
                r.adjust_for_ambient_noise(source, duration=1)
        except Exception:
            pass

    print("[OMEGA] Micrófono listo. Esperando 'Omega' o sesión activa...")

    while True:
        try:
            if esta_hablando:
                time.sleep(0.2)
                continue

            if MICRO_MUTED:
                time.sleep(0.3)
                continue

            if MICRO_NECESITA_RECARGAR:
                MICRO_NECESITA_RECARGAR = False
                _forzado = INDICE_MICRO_FORZADO
                INDICE_MICRO_FORZADO = None
                if _forzado is not None:
                    try:
                        _mic_test = sr.Microphone(device_index=_forzado)
                        with _mic_test as _src:
                            r.adjust_for_ambient_noise(_src, duration=0.3)
                        mic = _mic_test
                        print(f"[MIC] ✔ Micro cambiado a índice forzado: {_forzado}")
                    except Exception as _e:
                        print(f"[MIC] ⚠ Índice forzado {_forzado} KO ({_e}), fallback a detección automática")
                        _auto_idx = detectar_microfono()
                        mic = sr.Microphone(device_index=_auto_idx) if _auto_idx is not None else sr.Microphone()
                else:
                    nuevo_idx = detectar_microfono()
                    mic = sr.Microphone(device_index=nuevo_idx) if nuevo_idx is not None else sr.Microphone()
                    try:
                        with mic as source:
                            r.adjust_for_ambient_noise(source, duration=0.5)
                    except Exception:
                        pass
                    print(f"[MIC] Micro recargado → índice {nuevo_idx}")
                continue

            try:
                cfg = _cargar_config()
                dynamic_sens = cfg.get("mic_dynamic_sensitivity", True)
                sens = cfg.get("mic_sensitivity", 300)

                if r.dynamic_energy_threshold != dynamic_sens:
                    r.dynamic_energy_threshold = dynamic_sens
                    print(f"[MIC] Sensibilidad dinámica actualizada: {dynamic_sens}")

                if not dynamic_sens:
                    if r.energy_threshold != sens:
                        r.energy_threshold = sens
                        print(f"[MIC] Sensibilidad manual (umbral de energía) actualizada: {sens}")
                else:
                    if r.energy_threshold < sens:
                        r.energy_threshold = sens
            except Exception as _cfg_err:
                print(f"[MIC] Error leyendo configuración de sensibilidad: {_cfg_err}")

            if omega_activo and (time.time() - ultimo_mensaje > TIEMPO_ESPERA_SESION):
                print("[OMEGA] Timeout de sesión. Volviendo a espera.")
                omega_activo = False

            try:
                with mic as source:
                    esta_escuchando = True
                    estado = "active" if omega_activo else "listening"
                    enviar_broadcast_web_sync({"action": "set_state", "state": estado})
                    if omega_activo:
                        enviar_broadcast_web_sync({"action": "user_listening"})

                    audio = r.listen(source, timeout=2, phrase_time_limit=15)

                    esta_escuchando = False
                    enviar_broadcast_web_sync({"action": "set_state", "state": "thinking"})
            except sr.WaitTimeoutError:
                esta_escuchando = False
                raise
            except (OSError, AttributeError, ValueError) as _mic_hw_err:
                esta_escuchando = False
                _err_str = str(_mic_hw_err)
                if any(k in _err_str for k in ["Invalid input device", "No Default Input", "unanticipated", "[Errno"]):
                    print(f"[MIC] ⚠ Dispositivo de audio inválido/perdido ({_mic_hw_err}) — recarga solicitada")
                    MICRO_NECESITA_RECARGAR = True
                    time.sleep(1)
                    continue
                raise

            raw_data = audio.get_raw_data(convert_rate=16000, convert_width=2)

            duracion_audio = len(raw_data) / 32000.0
            if duracion_audio < 0.5:
                print(f"[ASR] Segmento ignorado (demasiado corto: {duracion_audio:.2f}s)")
                enviar_broadcast_web_sync({"action": "set_state", "state": "idle"})
                continue

            try:
                import numpy as _np
                _pcm = _np.frombuffer(raw_data, dtype=_np.int16).astype(_np.float32)
                rms_energy = int(_np.sqrt(_np.mean(_pcm ** 2))) if len(_pcm) > 0 else 0
            except Exception:
                rms_energy = 9999

            print(f"[ASR] Energía media del segmento: {rms_energy} (umbral mínimo: 250)")
            if rms_energy < 250:
                print("[ASR] Segmento ignorado (ruido o silencio por debajo del umbral)")
                enviar_broadcast_web_sync({"action": "set_state", "state": "idle"})
                continue

            if NEMOTRON_ASR_ACTIVADO and _instancia_nemotron is not None:
                texto = _instancia_nemotron.transcribir(raw_data, sample_rate=16000).lower().strip()
            else:
                texto = r.recognize_google(audio, language="fr-FR").lower().strip()

            if not texto:
                enviar_broadcast_web_sync({"action": "set_state", "state": "idle"})
                continue

            print(f"[ESCUCHADO] {texto}")

            if esta_hablando and ("cállate" in texto or "silencio" in texto):
                DETENER_HABLA = True
                continue

            PALABRAS_SUENO = ["gracias", "eso es todo", "descanso", "adiós", "silencio", "cállate"]
            if any(palabra in texto for palabra in PALABRAS_SUENO):
                if omega_activo:
                    omega_activo = False
                    bucle = asyncio.new_event_loop()
                    bucle.run_until_complete(hablar(f"A tu servicio {NOMBRE_USUARIO}. Me pongo en espera."))
                    bucle.close()
                continue

            palabra_activacion_detectada = False
            if PALABRA_ACTIVACION in texto:
                if re.search(r'\b' + re.escape(PALABRA_ACTIVACION) + r'\b', texto):
                    palabra_activacion_detectada = True

            if palabra_activacion_detectada or omega_activo:
                enviar_broadcast_web_sync({"action": "user_speech", "text": texto})

                if palabra_activacion_detectada:
                    print("[OMEGA] Palabra clave detectada.")
                    omega_activo = True

                ultimo_mensaje = time.time()
                comando = limpiar_comando(texto)

                bucle = asyncio.new_event_loop()
                asyncio.set_event_loop(bucle)

                if comando:
                    omega_activo = False
                    accion_pc = ejecutar_accion_pc(comando)
                    if accion_pc:
                        bucle.run_until_complete(hablar(accion_pc))
                    else:
                        bucle.run_until_complete(procesar_respuesta_ia(comando))
                else:
                    if palabra_activacion_detectada:
                        bucle.run_until_complete(hablar(f"Sí {NOMBRE_USUARIO}, te escucho."))

                bucle.close()
            else:
                pass

        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except OSError as e:
            print(f"[MIC] ⚠ Dispositivo de audio perdido ({e}). Intentando recuperar...")
            time.sleep(2)
            try:
                indice_mic = detectar_microfono()
                if indice_mic is not None:
                    mic = sr.Microphone(device_index=indice_mic)
                else:
                    mic = sr.Microphone()
                with mic as source:
                    r.adjust_for_ambient_noise(source, duration=0.5)
                print("[MIC] ✔ Micrófono recuperado con éxito.")
            except Exception as e2:
                print(f"[MIC] No se pudo recuperar el micrófono: {e2}")
                time.sleep(3)
        except Exception as e:
            print(f"Error escuchando: {e}")
            time.sleep(1)

def monitorizar_aplausos():
    if not pyaudio:
        print("[APLAUSO] PyAudio ausente — detección de aplausos desactivada.")
        return
    try:
        import numpy as _np_clap
        p = pyaudio.PyAudio()
        cfg_clap = _cargar_config()
        mic_idx_clap = cfg_clap.get("mic_device_index", None)
        open_kwargs = dict(format=pyaudio.paInt16, channels=1, rate=44100,
                          input=True, frames_per_buffer=1024)
        if mic_idx_clap is not None:
            open_kwargs["input_device_index"] = mic_idx_clap
        stream = p.open(**open_kwargs)
        print("[APLAUSO] Detección de aplausos activada.")

        print("[APLAUSO] Detección de dobles aplausos activada.")

        ultimo_aplauso_time = 0

        while True:
            try:
                data = stream.read(1024, exception_on_overflow=False)
                _pcm_clap = _np_clap.frombuffer(data, dtype=_np_clap.int16).astype(_np_clap.float32)
                rms = int(_np_clap.sqrt(_np_clap.mean(_pcm_clap ** 2))) if len(_pcm_clap) > 0 else 0

                if not MODO_IRON_MAN or esta_hablando or esta_pensando:
                    ultimo_aplauso_time = 0
                    continue

                if rms > UMBRAL_APLAUSO:
                    tiempo_actual = time.time()
                    diff = tiempo_actual - ultimo_aplauso_time

                    if 0.1 < diff < 0.8:
                        global VIDEO_LANZADA
                        print(f"\n[APLAUSO] !!! DOBLE APLAUSO DETECTADO !!!")
                        entity_id = PIEZAS_LUCES.get("salon", "light.salon")

                        estado_actual = ha_obtener_estado(entity_id)

                        if estado_actual != "on":
                            print(f"[APLAUSO] Acción: ENCENDER")
                            ha_luz(entity_id, "on")

                            if not VIDEO_LANZADA:
                                print(f"[APLAUSO] Lanzamiento inicial del video...")
                                webbrowser.open("https://www.youtube.com/watch?v=KU5V5WZVcVE")
                                VIDEO_LANZADA = True

                                def sec():
                                    time.sleep(5)
                                    pyautogui.press('f')
                                threading.Thread(target=sec, daemon=True).start()
                            else:
                                print(f"[APLAUSO] Reanudando video (Play)...")
                                pyautogui.press('k')
                        else:
                            print(f"[APLAUSO] Acción: APAGAR")
                            ha_luz(entity_id, "off")
                            if VIDEO_LANZADA:
                                print(f"[APLAUSO] Pausando video...")
                                pyautogui.press('k')

                        time.sleep(3.0)
                        ultimo_aplauso_time = 0
                    else:
                        ultimo_aplauso_time = tiempo_actual
            except Exception as e:
                time.sleep(0.5)
                continue

    except Exception as e:
        print(f"[APLAUSO] Error fatal detección de aplausos: {e}")

def verificar_actualizaciones():
    global ULTIMA_INFO_ACTUALIZACION
    try:
        print(f"[ACTUALIZACIÓN] Verificando actualizaciones...")
        response = requests.get(URL_JSON_ACTUALIZACION, timeout=10)
        if response.status_code == 200:
            data = response.json()
            version_remota = data.get("version", "4.0")

            if version_remota > VERSION_ACTUAL:
                print(f"[ACTUALIZACIÓN] NUEVA VERSIÓN DETECTADA: {version_remota}")
                ULTIMA_INFO_ACTUALIZACION = {
                    "type": "update_available",
                    "version": version_remota,
                    "url": data.get("download_url", "https://www.techenclair.fr/pages/jarvis"),
                    "changelog": data.get("changelog", "")
                }
            else:
                print(f"[ACTUALIZACIÓN] Sistema actualizado (v{VERSION_ACTUAL})")
                ULTIMA_INFO_ACTUALIZACION = None
        else:
            print(f"[ACTUALIZACIÓN] Servidor inalcanzable (Estado: {response.status_code})")
    except Exception as e:
        print(f"[ACTUALIZACIÓN] Error al verificar: {e}")

def bucle_verificacion_actualizaciones():
    while True:
        time.sleep(14400)
        verificar_actualizaciones()

def iniciar_ia():
    threading.Thread(target=monitorizar_aplausos, daemon=True).start()
    bucle = asyncio.new_event_loop()
    asyncio.set_event_loop(bucle)

    async def iniciar_ws():
        global BUCLE_WEB
        BUCLE_WEB = asyncio.get_running_loop()
        print(f"[WEB] Servidor WebSocket iniciado en ws://0.0.0.0:8765")
        print(f"[WEB] Accesible desde la red: ws://{IP_LOCAL}:8765")

        asyncio.create_task(broadcast_estadisticas_sistema())

        asyncio.create_task(bucle_recordatorios())

        asyncio.create_task(bucle_antivirus_live())

        async with websockets.serve(manejador_ws, "0.0.0.0", 8765):
            await asyncio.Future()

    threading.Thread(target=lambda: asyncio.run(iniciar_ws()), daemon=True).start()

    cfg = _cargar_config()
    voz_elegida = cfg.get("voice", "male")
    if voz_elegida == "gemini_fenrir":
        import random
        saludos = [
            f"Buenos días {NOMBRE_USUARIO}, ¿cómo estás hoy?",
            f"Buenos días {NOMBRE_USUARIO}, espero que hayas dormido bien. ¿Qué hacemos hoy?",
            f"Buenos días {NOMBRE_USUARIO}. Encantado de verte. Espero que todo te vaya bien.",
            f"Buenos días {NOMBRE_USUARIO}. Protocolos operativos. Estoy listo para ayudarte hoy.",
            f"¡Hola {NOMBRE_USUARIO}! ¿Listo para una nueva sesión de trabajo?",
            f"Buenos días {NOMBRE_USUARIO}. Me alegra verte. ¡Espero que todo vaya bien hoy!",
            f"Buenos días {NOMBRE_USUARIO}. Estoy en línea. ¿Cómo puedo ayudarte en este momento?"
        ]
        mensaje_inicio = random.choice(saludos)
    else:
        mensaje_inicio = f"Buenos días, {NOMBRE_USUARIO}"

    bucle.run_until_complete(hablar(mensaje_inicio))
    bucle.close()
    escuchar()

if pygame:
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
else:
    print("[INFO] Pygame ausente — inicio sin audio TTS.")

def iniciar_servidor_http_movil():
    import http.server
    import socketserver
    carpeta_movil = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mobile")
    if not os.path.exists(carpeta_movil):
        print("[MÓVIL] Carpeta mobile/ no encontrada, servidor no iniciado.")
        return

    class MobileHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=carpeta_movil, **kwargs)

        def log_message(self, format, *args):
            pass

    class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    server = ThreadingHTTPServer(("0.0.0.0", 8000), MobileHandler)
    print(f"[MÓVIL] Servidor HTTP iniciado en http://{IP_LOCAL}:8000")

    class RedirectHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            destino = f"http://{IP_LOCAL}:8000{self.path}"
            self.send_response(301)
            self.send_header("Location", destino)
            self.end_headers()

        def log_message(self, format, *args):
            pass

    def _iniciar_servidor_redireccion():
        try:
            redirect_server = ThreadingHTTPServer(("0.0.0.0", 80), RedirectHandler)
            print(f"[MÓVIL] Redirección puerto 80 → 8000 activa (escribe solo la IP en el móvil)")
            redirect_server.serve_forever()
        except OSError as e:
            print(f"[MÓVIL] Redirección puerto 80 no disponible (permisos insuficientes): {e}")
            print(f"[MÓVIL] En el móvil, usa http://{IP_LOCAL}:8000")

    threading.Thread(target=_iniciar_servidor_redireccion, daemon=True).start()
    server.serve_forever()

def liberar_puerto(puerto):
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True
        )
        stdout = result.stdout.decode(errors='ignore')
        for linea in stdout.splitlines():
            if f":{puerto}" in linea and ("LISTENING" in linea or "ESCUCHANDO" in linea):
                partes = linea.strip().split()
                pid = partes[-1]
                if pid.isdigit() and int(pid) != os.getpid():
                    subprocess.run(["taskkill", "/F", "/PID", pid],
                                   capture_output=True)
                    print(f"[INICIO] Puerto {puerto} liberado (PID {pid} terminado).")
                    return
    except Exception as e:
        print(f"[INICIO] No se pudo liberar el puerto {puerto}: {e}")

def vaciar_cache_webview_si_nueva_version():
    import shutil
    app_dir = os.path.dirname(os.path.abspath(__file__))
    marker_file = os.path.join(app_dir, ".omega_cache_version")

    version_en_cache = None
    try:
        if os.path.exists(marker_file):
            with open(marker_file, "r", encoding="utf-8") as f:
                version_en_cache = f.read().strip()
    except Exception:
        pass

    if version_en_cache == VERSION_ACTUAL:
        return

    print(f"[CACHE] Versión cambiada ({version_en_cache} → {VERSION_ACTUAL}) : limpiando caché WebView2...")

    appdata = os.environ.get("APPDATA", "")
    webview_data_dir = os.path.join(appdata, "pywebview", "EBWebView", "Default")

    carpetas_cache = [
        "Cache",
        "Code Cache",
        "Service Worker",
        "GPUCache",
        "DawnGraphiteCache",
        "DawnWebGPUCache",
        "blob_storage",
        "Session Storage",
        "Local Storage",
        "IndexedDB",
    ]

    if os.path.isdir(webview_data_dir):
        for carpeta in carpetas_cache:
            destino = os.path.join(webview_data_dir, carpeta)
            if os.path.isdir(destino):
                try:
                    shutil.rmtree(destino)
                    print(f"[CACHE]   ✓ Eliminado: {carpeta}")
                except Exception as e:
                    print(f"[CACHE]   ✗ Error en {carpeta}: {e}")
        print("[CACHE] Caché WebView2 limpiado con éxito.")
    else:
        print("[CACHE] Carpeta WebView2 no encontrada — probablemente primer inicio.")

    try:
        with open(marker_file, "w", encoding="utf-8") as f:
            f.write(VERSION_ACTUAL)
    except Exception as e:
        print(f"[CACHE] No se pudo escribir el marcador de versión: {e}")

def main():
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TechEnClair.Omega.App")
        except Exception:
            pass

    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    liberar_puerto(8765)
    liberar_puerto(8000)
    liberar_puerto(80)

    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
    proceso_frontend = None
    URL_FRONTEND = "http://localhost:5173"

    def _puerto_escucha(puerto, timeout=4.0):
        import socket
        inicio = time.time()
        while time.time() - inicio < timeout:
            try:
                with socket.create_connection(("127.0.0.1", puerto), timeout=0.3):
                    return True
            except (ConnectionRefusedError, OSError):
                time.sleep(0.2)
        return False

    def _servir_dist_python(puerto=5173):
        import http.server, socketserver
        dist_dir = os.path.join(frontend_dir, "dist")
        os.chdir(dist_dir)
        handler = http.server.SimpleHTTPRequestHandler
        handler.log_message = lambda *a: None
        with socketserver.TCPServer(("", puerto), handler) as httpd:
            print(f"[OMEGA] Frontend servido vía Python HTTP en http://localhost:{puerto}")
            httpd.serve_forever()

    vite_ok = False
    if os.path.exists(frontend_dir):
        try:
            print("[OMEGA] Intentando iniciar Vite (npm run dev)...")
            proceso_frontend = subprocess.Popen(
                ["npm", "run", "dev"], cwd=frontend_dir, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            vite_ok = _puerto_escucha(5173, timeout=5.0)
            if vite_ok:
                print("[OMEGA] Vite iniciado con éxito en localhost:5173")
            else:
                print("[OMEGA] Vite no inició (npm/vite ausente o error).")
                if proceso_frontend:
                    proceso_frontend.terminate()
                    proceso_frontend = None
        except Exception as e:
            print(f"[OMEGA] No se pudo iniciar Vite: {e}")
            proceso_frontend = None

        if not vite_ok:
            dist_dir = os.path.join(frontend_dir, "dist")
            if os.path.exists(dist_dir) and os.path.exists(os.path.join(dist_dir, "index.html")):
                print("[OMEGA] Fallback: sirviendo carpeta dist/ vía Python HTTP...")
                t_dist = threading.Thread(target=_servir_dist_python, args=(5173,), daemon=True)
                t_dist.start()
                vite_ok = _puerto_escucha(5173, timeout=3.0)
                if vite_ok:
                    print("[OMEGA] Frontend dist/ servido correctamente.")
            else:
                print("[OMEGA] Carpeta dist/ no encontrada. Interfaz no disponible.")
                print("[OMEGA] Para corregir: cd frontend && npm install && npm run build")

    if not vite_ok:
        print("[OMEGA] ATENCIÓN: la interfaz visual no estará disponible.")
        print("[OMEGA] OMEGA sigue funcionando en modo solo voz.")

    verificar_actualizaciones()

    threading.Thread(target=iniciar_servidor_http_movil, daemon=True).start()
    threading.Thread(target=iniciar_ia, daemon=True).start()
    threading.Thread(target=bucle_verificacion_actualizaciones, daemon=True).start()

    vaciar_cache_webview_si_nueva_version()

    def _limpiar_consola_inicio():
        time.sleep(3.5)
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 60)
        print("   AP0L0 OMEGA — Sistema En Línea")
        print("=" * 60)
        print("  Interfaz PC    : " + URL_FRONTEND)
        print(f"  Interfaz Móvil: http://{IP_LOCAL}:8000")
        print()
        print("  Comandos de voz activos.")
        print("  Di 'Omega' para empezar.")
        print("=" * 60)
        print()

    threading.Thread(target=_limpiar_consola_inicio, daemon=True).start()

    if _WEBVIEW_OK and webview is not None:
        print("[OMEGA] Abriendo en ventana nativa (pywebview)...")

        try:
            from screeninfo import get_monitors
            _mon = get_monitors()[0]
            _sw, _sh = _mon.width, _mon.height
        except Exception:
            _sw, _sh = 1920, 1080

        _win_w = max(1280, int(_sw * 0.85))
        _win_h = max(780, int(_sh * 0.85))
        _win_x = (_sw - _win_w) // 2
        _win_y = (_sh - _win_h) // 2

        ventana = webview.create_window(
            title="AP0L0 OMEGA",
            url=URL_FRONTEND,
            width=_win_w,
            height=_win_h,
            x=_win_x,
            y=_win_y,
            resizable=True,
            min_size=(900, 600),
            background_color="#0a0a0f",
        )
        global _VENTANA_WEBVIEW
        _VENTANA_WEBVIEW = ventana

        def _on_closed():
            print("\n[OMEGA] Ventana cerrada — apagando sistema...")
            if proceso_frontend:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proceso_frontend.pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            import os
            os._exit(0)

        ventana.events.closed += _on_closed

        def _on_loaded():
            try:
                import ctypes
                import os

                try:
                    hwnd_console = ctypes.windll.kernel32.GetConsoleWindow()
                    if hwnd_console:
                        ctypes.windll.user32.ShowWindow(hwnd_console, 0)
                except Exception:
                    pass

                hwnd = ctypes.windll.user32.FindWindowW(None, "AP0L0 OMEGA")
                if hwnd:
                    icon_path = os.path.abspath("omega.ico")
                    if os.path.exists(icon_path):
                        hicon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x0010)
                        if hicon:
                            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon)
                            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon)

                try:
                    import src.actions.secure_browser
                    src.actions.secure_browser._main_webview_window = ventana

                    def on_main_window_resized(width, height):
                        src.actions.secure_browser.resize_docked_window()
                    ventana.events.resized += on_main_window_resized
                    print("[OMEGA] Módulo de navegación segura conectado al redimensionamiento.")
                except Exception as ex:
                    print(f"[OMEGA] Error inicializando secure_browser: {ex}")

            except Exception as e:
                print(f"[OMEGA] Error cargando icono: {e}")

        ventana.events.loaded += _on_loaded

        try:
            webview.start(private_mode=False)
        except Exception as e:
            print(f"[OMEGA] PyWebView imposible: {e} — cambiando a navegador")
            _abrir_en_navegador(URL_FRONTEND, proceso_frontend)
    else:
        _abrir_en_navegador(URL_FRONTEND, proceso_frontend)

def _abrir_en_navegador(url, proceso_frontend):
    print(f"[OMEGA] Intentando abrir en Modo App Dedicada en {url}...")

    try:
        exito = False
        for navegador in ["msedge", "chrome"]:
            try:
                subprocess.Popen(f'start {navegador} --app="{url}"', shell=True)
                print(f"[OMEGA] Interfaz lanzada vía {navegador} (Modo App)")
                exito = True
                break
            except:
                continue

        if exito:
            _esperar_interfaz(proceso_frontend)
            return
    except Exception as e:
        print(f"[OMEGA] Error lanzando Modo App: {e}")

    print("[OMEGA] Fallback: Abriendo en navegador por defecto...")
    webbrowser.open(url)
    _esperar_interfaz(proceso_frontend)

def _esperar_interfaz(proceso_frontend):
    try:
        while True:
            time.sleep(1)
            if interfaz_ya_conectada and len(CLIENTES_CONECTADOS) == 0:
                print("\n[OMEGA] Interfaz desconectada. Esperando reconexión (60s)...")
                time.sleep(60)
                if len(CLIENTES_CONECTADOS) == 0:
                    print("[OMEGA] No hay reconexión. Apagado automático...")
                    break
                else:
                    print("[OMEGA] Reconexión detectada. Continuando.")
    except KeyboardInterrupt:
        print("\n[OMEGA] Apagado manual.")

    if proceso_frontend:
        print("[OMEGA] Deteniendo servidor Web...")
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proceso_frontend.pid)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

builtins.pedir_ia_vision = pedir_ia_vision
if __name__ == "__main__":
    main()