# =====================================================================
# server.py — AP0L0 OMEGA DASHBOARD v21.2 (completo)
# =====================================================================

import asyncio
import base64
import hashlib
import secrets
import socket
import string
import time
import json
import traceback
import platform as _platform
from pathlib import Path
from typing import Set, Dict, Optional, List, Any
from datetime import datetime, timedelta
import subprocess
import xml.etree.ElementTree as ET
import os
import shutil
import zipfile
import re
import random
import string as str_lib
import io
import sqlite3
import threading
import uuid
import webbrowser
import logging

# ---- Configurar logging ----
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("AP0L0")

# ---- Dependencias web ----
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File as FastAPIFile
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    _FASTAPI_OK = True
except ImportError:
    _FASTAPI_OK = False
    logger.warning("FastAPI/uvicorn no instalado. Ejecuta: pip install fastapi uvicorn")

# ---- Dependencias sistema ----
try:
    import psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

try:
    import feedparser
    _FEEDPARSER_OK = True
except ImportError:
    _FEEDPARSER_OK = False

try:
    import pyperclip
    _PYPERCLIP_OK = True
except ImportError:
    _PYPERCLIP_OK = False

try:
    import ddgs
    _DDGS_OK = True
except ImportError:
    _DDGS_OK = False

try:
    import openai
    _OPENAI_OK = True
except ImportError:
    _OPENAI_OK = False

# ---- google.genai ----
try:
    from google import genai
    from google.genai import types
    _GENAI_OK = True
    logger.info("google.genai importado correctamente.")
except ImportError:
    _GENAI_OK = False
    logger.warning("google.genai no instalado. Ejecuta: pip install google-genai")

try:
    import ollama
    _OLLAMA_OK = True
except ImportError:
    _OLLAMA_OK = False

try:
    import wikipedia
    _WIKIPEDIA_OK = True
except ImportError:
    _WIKIPEDIA_OK = False

try:
    from googlesearch import search
    _GOOGLE_SEARCH_OK = True
except ImportError:
    _GOOGLE_SEARCH_OK = False

# ---- Volumen, brillo, captura ----
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    _PYCAW_OK = True
except ImportError:
    _PYCAW_OK = False

try:
    import screen_brightness_control as sbc
    _SBC_OK = True
except ImportError:
    _SBC_OK = False

try:
    import mss
    _MSS_OK = True
except ImportError:
    _MSS_OK = False

try:
    import pyautogui
    _PYAUTOGUI_OK = True
except ImportError:
    _PYAUTOGUI_OK = False

# ---- Voz (STT / TTS) ----
try:
    import speech_recognition as sr
    _SR_OK = True
except ImportError:
    _SR_OK = False

try:
    from faster_whisper import WhisperModel
    _WHISPER_OK = True
except ImportError:
    _WHISPER_OK = False

try:
    import pyttsx3
    _PYTTSX3_OK = True
except ImportError:
    _PYTTSX3_OK = False

try:
    import edge_tts
    _EDGE_TTS_OK = True
    logger.info("EdgeTTS disponible.")
except ImportError:
    _EDGE_TTS_OK = False
    logger.warning("EdgeTTS no instalado. Ejecuta: pip install edge-tts")

try:
    from gtts import gTTS
    _GTTS_OK = True
except ImportError:
    _GTTS_OK = False

# =====================================================================
# CONFIGURACIÓN
# =====================================================================

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
SRC_DIR = BASE_DIR.parent
CONFIG_DIR = SRC_DIR / "config"
CONFIG_DIR.mkdir(exist_ok=True)

logger.info(f"Directorio de configuración: {CONFIG_DIR}")

PORT = 8000
PERSONALITY_FILE = CONFIG_DIR / "personality.json"
API_KEYS_FILE = CONFIG_DIR / "api_keys.json"
AI_CONFIG_FILE = CONFIG_DIR / "ai_config.json"

KEY_CHARS = [c for c in (string.ascii_uppercase + string.digits) if c not in ('O', 'I', 'L', '0', '1')]
AES_SALT = b'JARVIS-DASHBOARD-v1'
CONVERSATION_HISTORY = []

# Modelo válido (según pruebas)
GEMINI_MODEL = "gemma-4-26b-a4b-it"

# Voces EdgeTTS por personalidad
PERSONALITY_VOICES = {
    "jarvis": "es-ES-ElviraNeural",
    "agata": "es-ES-ElviraNeural",
    "tony": "es-ES-AlvaroNeural",
    "friday": "es-ES-ElviraNeural",
    "apolo": "es-ES-AlvaroNeural",
}
DEFAULT_VOICE = "es-ES-ElviraNeural"

DB_PATH = CONFIG_DIR / "apolo_memory.db"
DB_LOCK = threading.Lock()

def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    with DB_LOCK:
        conn = get_db_connection()
        try:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT,
                category TEXT DEFAULT 'general',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                remind_at TEXT NOT NULL,
                done INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()
            logger.info("Base de datos inicializada correctamente.")
        except Exception as e:
            logger.error(f"Error al inicializar la base de datos: {e}")
        finally:
            conn.close()

init_db()

def db_execute(sql, params=()):
    with DB_LOCK:
        conn = get_db_connection()
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

def db_query(sql, params=()):
    with DB_LOCK:
        conn = get_db_connection()
        try:
            cur = conn.execute(sql, params)
            rows = cur.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

# =====================================================================
# FUNCIONES AUXILIARES
# =====================================================================

def _local_ip() -> str:
    for probe in ("8.8.8.8", "1.1.1.1", "192.168.1.1"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect((probe, 80))
            ip = s.getsockname()[0]
            s.close()
            if not ip.startswith("127."):
                return ip
        except Exception:
            pass
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "127.0.0.1"

def _get_personality() -> str:
    if PERSONALITY_FILE.exists():
        try:
            return json.loads(PERSONALITY_FILE.read_text()).get("personality", "jarvis")
        except:
            pass
    return "jarvis"

def _set_personality(name: str):
    PERSONALITY_FILE.write_text(json.dumps({"personality": name}))

def _get_api_key(service: str) -> Optional[str]:
    if not API_KEYS_FILE.exists():
        return None
    try:
        data = json.loads(API_KEYS_FILE.read_text())
        return data.get(service)
    except:
        return None

def _get_ai_config() -> Dict:
    if AI_CONFIG_FILE.exists():
        try:
            return json.loads(AI_CONFIG_FILE.read_text())
        except:
            pass
    return {"provider": "gemini", "model": GEMINI_MODEL, "temperature": 0.7}

def _set_ai_config(config: Dict):
    AI_CONFIG_FILE.write_text(json.dumps(config, indent=2))

# =====================================================================
# FUNCIONES DE VOZ (STT y TTS)
# =====================================================================

_whisper_model = None
if _WHISPER_OK:
    try:
        _whisper_model = WhisperModel("base", device="auto", compute_type="auto")
        logger.info("Whisper cargado correctamente.")
    except Exception as e:
        logger.warning(f"Whisper falló: {e}")

_sr_recognizer = None
if _SR_OK:
    _sr_recognizer = sr.Recognizer()

def _speech_to_text(audio_bytes: bytes) -> str:
    if not audio_bytes or len(audio_bytes) < 100:
        logger.warning(f"Audio demasiado corto: {len(audio_bytes)} bytes")
        return ""
    tmp_path = f"temp_audio_{uuid.uuid4().hex}.wav"
    try:
        # Si es WebM, intentar convertir con pydub (opcional)
        if audio_bytes[:4] != b"RIFF":
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="webm")
                audio.export(tmp_path, format="wav")
            except:
                # Guardar como está y esperar que Whisper lo entienda
                with open(tmp_path, "wb") as f:
                    f.write(audio_bytes)
        else:
            with open(tmp_path, "wb") as f:
                f.write(audio_bytes)

        if _whisper_model is not None:
            segments, _ = _whisper_model.transcribe(tmp_path, language="es")
            text = " ".join(seg.text.strip() for seg in segments).strip()
            if text:
                logger.info(f"Whisper transcribió: {text[:50]}...")
                return text
            else:
                logger.warning("Whisper no devolvió texto.")

        if _sr_recognizer is not None:
            with sr.AudioFile(tmp_path) as source:
                audio = _sr_recognizer.record(source)
            try:
                text = _sr_recognizer.recognize_google(audio, language="es-ES")
                logger.info(f"Google Speech transcribió: {text[:50]}...")
                return text
            except Exception as e:
                logger.warning(f"Google Speech falló: {e}")

        return ""
    except Exception as e:
        logger.error(f"STT error: {e}")
        return ""
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

_tts_engine = None
if _PYTTSX3_OK:
    try:
        _tts_engine = pyttsx3.init()
        _tts_engine.setProperty("rate", 180)
        try:
            voices = _tts_engine.getProperty('voices')
            for voice in voices:
                if 'spanish' in voice.name.lower() or 'es' in voice.id.lower():
                    _tts_engine.setProperty('voice', voice.id)
                    logger.info("pyttsx3 configurado con voz en español.")
                    break
        except:
            pass
        logger.info("pyttsx3 listo.")
    except Exception as e:
        logger.warning(f"pyttsx3 falló: {e}")

async def _text_to_speech(text: str, personality: str = None) -> bytes:
    if not text:
        return b""
    if not personality:
        personality = _get_personality()
    voice = PERSONALITY_VOICES.get(personality, DEFAULT_VOICE)
    logger.info(f"Usando voz '{voice}' para personalidad '{personality}'")

    # 1. EdgeTTS
    if _EDGE_TTS_OK:
        tmp_path = f"temp_tts_{uuid.uuid4().hex}.mp3"
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(tmp_path)
            with open(tmp_path, "rb") as f:
                audio_data = f.read()
            logger.info(f"EdgeTTS generó {len(audio_data)} bytes")
            return audio_data
        except Exception as e:
            logger.warning(f"EdgeTTS falló: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # 2. gTTS
    if _GTTS_OK:
        try:
            tts = gTTS(text, lang="es")
            with io.BytesIO() as f:
                tts.write_to_fp(f)
                audio_data = f.getvalue()
            logger.info(f"gTTS generó {len(audio_data)} bytes (fallback)")
            return audio_data
        except Exception as e:
            logger.warning(f"gTTS falló: {e}")

    # 3. pyttsx3
    if _tts_engine is not None:
        try:
            import tempfile
            tmp_path = tempfile.mktemp(suffix=".wav")
            _tts_engine.save_to_file(text, tmp_path)
            _tts_engine.runAndWait()
            with open(tmp_path, "rb") as f:
                audio_data = f.read()
            os.remove(tmp_path)
            logger.info(f"pyttsx3 generó {len(audio_data)} bytes (último recurso)")
            return audio_data
        except Exception as e:
            logger.error(f"pyttsx3 falló: {e}")

    logger.error("Todos los TTS fallaron.")
    return b""

# =====================================================================
# ENRUTADOR DE COMANDOS
# =====================================================================

def _process_command(text: str) -> Optional[str]:
    lower = text.lower().strip()

    # Apertura de aplicaciones
    app_patterns = {
        "word": "word",
        "excel": "excel",
        "powerpoint": "powerpoint",
        "calculadora": "calculadora",
        "bloc de notas": "bloc de notas",
        "notepad": "bloc de notas",
        "cmd": "cmd",
        "terminal": "cmd",
        "explorador": "explorador",
        "explorer": "explorador",
        "chrome": "chrome",
        "firefox": "firefox",
        "edge": "edge",
        "spotify": "spotify",
        "youtube": "youtube",
        "google": "google",
        "gmail": "gmail",
        "github": "github",
        "whatsapp": "whatsapp",
        "telegram": "telegram",
    }
    for pattern, app in app_patterns.items():
        if pattern in lower:
            return _open_app(app)

    # URLs
    url_match = re.search(r'(abre|ve a|visita)\s+(https?://[^\s]+)', lower)
    if url_match:
        return _open_website(url_match.group(2))

    # Volumen
    if "sube volumen" in lower or "volumen arriba" in lower:
        _set_volume_os(min(100, _get_volume_os()[0] + 10))
        vol, _ = _get_volume_os()
        return f"Volumen subido al {vol}%"
    if "baja volumen" in lower or "volumen abajo" in lower:
        _set_volume_os(max(0, _get_volume_os()[0] - 10))
        vol, _ = _get_volume_os()
        return f"Volumen bajado al {vol}%"
    if "silencia" in lower or "mute" in lower:
        _toggle_mute_os()
        _, muted = _get_volume_os()
        return "Silencio activado" if muted else "Silencio desactivado"
    if "volumen" in lower:
        match = re.search(r'volumen\s+(\d+)', lower)
        if match:
            vol = int(match.group(1))
            _set_volume_os(vol)
            return f"Volumen ajustado al {vol}%"

    # Brillo
    if "brillo" in lower:
        match = re.search(r'brillo\s+(\d+)', lower)
        if match:
            level = int(match.group(1))
            return _control_brightness(level)

    # Bloquear
    if "bloquear pantalla" in lower or "lock" in lower:
        return _lock_screen()

    # Captura
    if "captura" in lower or "screenshot" in lower:
        result = _take_screenshot()
        if result.startswith("data:image") or len(result) > 100:
            return "Captura de pantalla tomada."
        else:
            return result

    # Media
    if "reproducir" in lower or "play" in lower:
        return _control_media("playpause")
    if "siguiente" in lower or "next" in lower:
        return _control_media("nexttrack")
    if "anterior" in lower or "previous" in lower:
        return _control_media("prevtrack")

    # Sistema
    if "apagar" in lower or "shutdown" in lower:
        return _system_action("shutdown")
    if "reiniciar" in lower or "restart" in lower:
        return _system_action("restart")
    if "suspender" in lower or "sleep" in lower:
        return _system_action("sleep")
    if "hibernar" in lower or "hibernate" in lower:
        return _system_action("hibernate")

    # Recordatorios
    if "recordatorio" in lower:
        match = re.search(r'recordatorio\s+(.+?)\s+en\s+(\d+)\s+minutos?', lower)
        if match:
            text_rem = match.group(1)
            minutes = int(match.group(2))
            return _add_reminder(text_rem, minutes)
        else:
            return "Para añadir un recordatorio, di: 'recordatorio [texto] en [minutos] minutos'"

    # Notas
    if "nota" in lower:
        match = re.search(r'nota\s+(.+?)\s+con\s+contenido\s+(.+)', lower)
        if match:
            title = match.group(1)
            content = match.group(2)
            return _add_note(title, content)
        else:
            return "Para añadir una nota, di: 'nota [título] con contenido [texto]'"

    return None

# =====================================================================
# FUNCIONES DE ACCIONES REALES
# =====================================================================

def _open_app(app_name: str) -> str:
    system = _platform.system()
    try:
        if system == "Windows":
            app_map = {
                "word": "winword",
                "excel": "excel",
                "powerpoint": "powerpnt",
                "calculadora": "calc",
                "bloc de notas": "notepad",
                "notepad": "notepad",
                "cmd": "cmd",
                "terminal": "cmd",
                "explorador": "explorer",
                "explorer": "explorer",
                "chrome": "chrome",
                "firefox": "firefox",
                "edge": "msedge",
                "spotify": "spotify",
                "youtube": "https://youtube.com",
                "google": "https://google.com",
                "gmail": "https://gmail.com",
                "github": "https://github.com",
                "whatsapp": "https://web.whatsapp.com",
                "telegram": "https://web.telegram.org",
            }
            app_key = app_name.lower().strip()
            if app_key in app_map:
                target = app_map[app_key]
                if target.startswith("http"):
                    webbrowser.open(target)
                    return f"Abriendo {app_name} en el navegador."
                else:
                    subprocess.Popen(["start", target], shell=True)
                    return f"Abriendo {app_name}..."
            else:
                subprocess.Popen(["start", app_name], shell=True)
                return f"Intentando abrir {app_name}..."
        else:
            return "Apertura de aplicaciones solo soportada en Windows."
    except Exception as e:
        return f"Error al abrir {app_name}: {str(e)}"

def _open_website(url: str) -> str:
    try:
        webbrowser.open(url)
        return f"Abriendo {url}"
    except Exception as e:
        return f"Error: {str(e)}"

def _lock_screen() -> str:
    try:
        if _platform.system() == "Windows":
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False)
            return "Pantalla bloqueada"
        else:
            return "Bloqueo de pantalla solo soportado en Windows."
    except Exception as e:
        return f"Error: {str(e)}"

def _take_screenshot() -> str:
    if not _MSS_OK:
        return "Captura no disponible (mss no instalado)."
    try:
        with mss.MSS() as sct:
            monitor = sct.monitors[1]
            img = sct.grab(monitor)
            png = mss.tools.to_png(img.rgb, img.size)
            return base64.b64encode(png).decode()
    except Exception as e:
        return f"Error: {str(e)}"

def _control_media(action: str) -> str:
    if not _PYAUTOGUI_OK:
        return "Control de medios no disponible (pyautogui no instalado)."
    try:
        pyautogui.press(action)
        return f"Comando '{action}' enviado"
    except Exception as e:
        return f"Error: {str(e)}"

def _get_volume_os():
    vol = 50
    muted = False
    if _PYCAW_OK:
        try:
            devices = AudioUtilities.GetSpeakers()
            if isinstance(devices, list):
                device = devices[0] if devices else None
            else:
                device = devices
            if device:
                interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                vol_obj = interface.QueryInterface(IAudioEndpointVolume)
                vol = int(vol_obj.GetMasterVolumeLevelScalar() * 100)
                muted = vol_obj.GetMute()
        except Exception as e:
            logger.error(f"Error al leer volumen: {e}")
    return vol, muted

def _set_volume_os(volume: int):
    if _PYCAW_OK:
        try:
            devices = AudioUtilities.GetSpeakers()
            if isinstance(devices, list):
                device = devices[0] if devices else None
            else:
                device = devices
            if device:
                interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                vol_obj = interface.QueryInterface(IAudioEndpointVolume)
                vol_obj.SetMasterVolumeLevelScalar(volume / 100, None)
        except Exception as e:
            logger.error(f"Error al establecer volumen: {e}")

def _toggle_mute_os():
    if _PYCAW_OK:
        try:
            devices = AudioUtilities.GetSpeakers()
            if isinstance(devices, list):
                device = devices[0] if devices else None
            else:
                device = devices
            if device:
                interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                vol_obj = interface.QueryInterface(IAudioEndpointVolume)
                vol_obj.SetMute(not vol_obj.GetMute(), None)
        except Exception as e:
            logger.error(f"Error al alternar mute: {e}")

def _control_brightness(level: int) -> str:
    if not _SBC_OK:
        return "Control de brillo no disponible (screen-brightness-control no instalado)."
    try:
        sbc.set_brightness(level)
        return f"Brillo ajustado a {level}%"
    except Exception as e:
        return f"Error: {str(e)}"

def _get_brightness() -> str:
    if not _SBC_OK:
        return "Control de brillo no disponible."
    try:
        return f"Brillo actual: {sbc.get_brightness()}%"
    except Exception as e:
        return f"Error: {str(e)}"

def _get_wifi_info() -> str:
    try:
        if _platform.system() == "Windows":
            res = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True)
            return res.stdout.strip() or "No hay información WiFi"
        else:
            return "Comando WiFi no disponible en este SO."
    except Exception as e:
        return f"Error: {str(e)}"

def _get_bluetooth_info() -> str:
    try:
        if _platform.system() == "Windows":
            res = subprocess.run(["powershell", "Get-PnpDevice -Class Bluetooth | Select-Object Status, FriendlyName"], capture_output=True, text=True)
            return res.stdout.strip() or "No hay información Bluetooth"
        else:
            return "Comando Bluetooth no disponible en este SO."
    except Exception as e:
        return f"Error: {str(e)}"

def _system_action(action: str) -> str:
    try:
        if _platform.system() == "Windows":
            if action == "shutdown":
                subprocess.run(["shutdown", "/s", "/t", "5"], check=False)
                return "Apagando sistema en 5 segundos..."
            elif action == "restart":
                subprocess.run(["shutdown", "/r", "/t", "5"], check=False)
                return "Reiniciando sistema en 5 segundos..."
            elif action == "sleep":
                subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"], check=False)
                return "Suspendiendo sistema..."
            elif action == "hibernate":
                subprocess.run(["shutdown", "/h"], check=False)
                return "Hibernando sistema..."
        else:
            return "Acciones de sistema solo soportadas en Windows."
    except Exception as e:
        return f"Error: {str(e)}"

# =====================================================================
# FUNCIONES DE UTILIDADES (CLIMA, NOTICIAS, WIKIPEDIA, ETC.)
# =====================================================================

def _get_weather(city: str = "Madrid") -> str:
    try:
        if _REQUESTS_OK:
            resp = requests.get(f"https://wttr.in/{city}?format=%C+%t+%w", timeout=5)
            if resp.status_code == 200:
                return f"Clima en {city}: {resp.text.strip()}"
        return "No se pudo obtener el clima."
    except Exception as e:
        return f"Error: {str(e)}"

def _get_news_rss(category: str = "tecnologia") -> str:
    sources = {
        "tecnologia": ["https://es.wired.com/feed", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/tecnologia/portada"],
        "deportes": ["https://e00-marca.uecdn.es/rss/portada.xml"],
        "politica": ["https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/politica/portada"],
        "economia": ["https://e00-expansion.uecdn.es/rss/portada.xml"],
        "ciencia": ["https://www.agenciasinc.es/rss"],
        "salud": ["https://medlineplus.gov/spanish/rss.xml"],
        "entretenimiento": ["https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/cultura/portada"]
    }
    urls = sources.get(category, sources["tecnologia"])
    all_items = []
    for url in urls:
        try:
            if _FEEDPARSER_OK:
                feed = feedparser.parse(url)
                for entry in feed.entries[:4]:
                    title = entry.get('title', '').strip()
                    if title:
                        all_items.append(f"• {title}")
            else:
                if _REQUESTS_OK:
                    resp = requests.get(url, timeout=8)
                    if resp.status_code == 200:
                        root = ET.fromstring(resp.content)
                        for item in root.findall('.//item')[:4]:
                            title = item.find('title')
                            if title is not None and title.text:
                                all_items.append(f"• {title.text.strip()}")
        except:
            continue
        if len(all_items) >= 8:
            break
    return "\n".join(all_items[:8]) if all_items else "No se encontraron noticias."

def _search_wikipedia(query: str) -> str:
    if not _WIKIPEDIA_OK:
        return "Wikipedia no instalada."
    try:
        wikipedia.set_lang("es")
        page = wikipedia.page(query)
        return f"Título: {page.title}\nResumen: {page.summary[:500]}..."
    except Exception as e:
        return f"No se encontró información: {str(e)}"

def _web_search(query: str) -> str:
    if not _GOOGLE_SEARCH_OK:
        return "Búsqueda web no disponible."
    try:
        results = list(search(query, num_results=5, lang="es"))
        return "\n".join(f"• {r}" for r in results)
    except Exception as e:
        return f"Error: {str(e)}"

def _calculate(expression: str) -> str:
    try:
        allowed = set("0123456789+-*/().%^ ")
        if not all(c in allowed for c in expression):
            return "Expresión no válida"
        expression = expression.replace("^", "**")
        result = eval(expression, {"__builtins__": {}}, {"math": __import__("math")})
        return str(result)
    except Exception as e:
        return f"Error: {str(e)}"

def _get_btc_price() -> str:
    try:
        resp = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            price = data.get('bitcoin', {}).get('usd')
            if price:
                return f"💰 Bitcoin: ${price:.2f} USD"
    except:
        pass
    return "No se pudo obtener precio de Bitcoin."

def _get_crypto_price(crypto: str = "bitcoin") -> str:
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto}&vs_currencies=usd,eur"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if crypto in data:
                prices = data[crypto]
                return f"💰 {crypto.capitalize()}: ${prices.get('usd', 'N/A')} USD"
    except:
        pass
    return f"No se pudo obtener precio de {crypto}."

def _get_random_quote() -> str:
    try:
        resp = requests.get("https://api.quotable.io/random", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return f"📝 '{data.get('content', '')}' — {data.get('author', 'Desconocido')}"
    except:
        pass
    return "No se pudo obtener cita."

def _generate_password(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return ''.join(secrets.choice(chars) for _ in range(length))

def _get_system_info() -> str:
    try:
        cpu = psutil.cpu_percent(interval=0.2)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/')
        return f"CPU: {cpu}%, RAM: {ram}%, Disco: {disk.percent}% usado"
    except:
        return "No se pudo obtener información del sistema."

def _add_reminder(text: str, minutes: int) -> str:
    try:
        remind_at = (datetime.now() + timedelta(minutes=minutes)).isoformat()
        db_execute("INSERT INTO reminders (text, remind_at) VALUES (?, ?)", (text, remind_at))
        return f"Recordatorio '{text}' en {minutes} minutos"
    except Exception as e:
        return f"Error: {str(e)}"

def _list_reminders() -> str:
    rows = db_query("SELECT * FROM reminders WHERE done=0 ORDER BY remind_at")
    if not rows:
        return "No hay recordatorios pendientes."
    return "\n".join(f"• {r['text']} ({r['remind_at']})" for r in rows)

def _add_note(title: str, content: str) -> str:
    try:
        db_execute("INSERT INTO notes (title, content) VALUES (?, ?)", (title, content))
        return f"Nota '{title}' guardada"
    except Exception as e:
        return f"Error: {str(e)}"

def _list_notes() -> str:
    rows = db_query("SELECT * FROM notes ORDER BY id DESC LIMIT 10")
    if not rows:
        return "No hay notas."
    return "\n".join(f"• {r['title']}: {r['content']}" for r in rows)

def _search_recipes(query: str) -> str:
    try:
        if _REQUESTS_OK:
            url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={query.replace(' ', '_')}"
            resp = requests.get(url, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            if data.get("meals"):
                meals = data["meals"][:5]
                output = []
                for meal in meals:
                    name = meal.get("strMeal", "Sin nombre")
                    category = meal.get("strCategory", "")
                    area = meal.get("strArea", "")
                    instructions = meal.get("strInstructions", "")[:100].replace("\n", " ")
                    output.append(f"• {name} ({category} - {area})\n  {instructions}...")
                return "\n".join(output)
            else:
                return f"No se encontraron recetas para '{query}'."
        else:
            return "Recetas no disponibles (requests no instalado)."
    except Exception as e:
        return f"Error al buscar recetas: {str(e)}"

def _search_podcast(query: str) -> str:
    return f"Búsqueda de podcast para '{query}' (simulado)."

# =====================================================================
# FUNCIONES PARA LISTAR MODELOS
# =====================================================================

def _list_available_models() -> List[str]:
    try:
        api_key = _get_api_key("gemini_api_key")
        if not api_key:
            return ["No hay clave API"]
        client = genai.Client(api_key=api_key)
        models = client.models.list()
        available = []
        for model in models:
            if "generateContent" in str(model.supported_actions):
                available.append(model.name.replace("models/", ""))
        return available
    except Exception as e:
        logger.error(f"Error al listar modelos: {e}")
        return [f"Error: {e}"]

# =====================================================================
# FUNCIONES DE IA
# =====================================================================

def _get_ai_response(prompt: str, personality: str = "jarvis") -> str:
    global CONVERSATION_HISTORY
    config = _get_ai_config()
    provider = config.get("provider", "gemini")

    if provider == "gemini" and _GENAI_OK:
        try:
            api_key = _get_api_key("gemini_api_key")
            if api_key:
                client = genai.Client(api_key=api_key)
                full_prompt = f"Eres {personality}, un asistente avanzado. Responde en español de forma clara y concisa.\n\n{prompt}"
                model_name = config.get("model", GEMINI_MODEL)
                response = client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(temperature=0.7)
                )
                if response and response.text:
                    reply = response.text.strip()
                    CONVERSATION_HISTORY.append({"role": "user", "content": prompt})
                    CONVERSATION_HISTORY.append({"role": "assistant", "content": reply})
                    return reply
        except Exception as e:
            logger.error(f"Gemini falló: {e}")

    if provider == "openai" and _OPENAI_OK:
        try:
            key = _get_api_key("openai")
            if key:
                openai.api_key = key
                messages = [{"role": "system", "content": f"Eres {personality}, un asistente útil."}] + CONVERSATION_HISTORY[-5:]
                response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages, max_tokens=200)
                reply = response.choices[0].message.content.strip()
                CONVERSATION_HISTORY.append({"role": "user", "content": prompt})
                CONVERSATION_HISTORY.append({"role": "assistant", "content": reply})
                return reply
        except Exception as e:
            logger.error(f"OpenAI falló: {e}")

    if provider == "ollama" and _OLLAMA_OK:
        try:
            import ollama
            messages = [{"role": "system", "content": f"Eres {personality}, un asistente útil."}] + CONVERSATION_HISTORY[-5:]
            response = ollama.chat(model=config.get("model", "llama3.1"), messages=messages)
            reply = response.get("message", {}).get("content", "").strip()
            CONVERSATION_HISTORY.append({"role": "user", "content": prompt})
            CONVERSATION_HISTORY.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            logger.error(f"Ollama falló: {e}")

    return f"Soy {personality}, tu asistente. No tengo un proveedor de IA configurado o funcionando correctamente."

# =====================================================================
# CLASE PRINCIPAL DEL SERVIDOR (CORREGIDA)
# =====================================================================

class DashboardServer:
    def __init__(self):
        self._ip = _local_ip()
        self._tokens: Set[str] = set()
        self._token_keys: Dict[str, str] = {}
        self._clients: Set[WebSocket] = set()
        self._history: list[dict] = []
        self._command_queue = asyncio.Queue()
        self._phone_audio_queue = asyncio.Queue()   # <--- NUEVO: cola para audio del teléfono
        self._pending_keys: Dict[str, float] = {"XXXXXX": time.time() + 3600}
        self._personality = _get_personality()
        self._connect_callback = None
        self._app = FastAPI(title="AP0L0 OMEGA Dashboard", version="21.2")
        self._setup_routes()
        self._setup_websocket()
        logger.info("Servidor AP0L0 OMEGA iniciado correctamente.")

    # ===== NUEVO: método para establecer el callback =====
    def set_connect_callback(self, callback):
        """Establece la función que se llamará cuando un dispositivo se conecte."""
        self._connect_callback = callback
        logger.info("Callback de conexión establecido.")

    # ===== NUEVO: métodos para generar clave remota =====
    def new_key(self) -> str:
        """Genera una nueva clave temporal para acceso remoto (6 dígitos alfanuméricos)."""
        import secrets, string
        # Caracteres permitidos: mayúsculas y dígitos, excluyendo O, I, L, 0, 1 para evitar confusiones
        chars = [c for c in (string.ascii_uppercase + string.digits) if c not in ('O', 'I', 'L', '0', '1')]
        key = ''.join(secrets.choice(chars) for _ in range(6))
        self._pending_keys[key] = time.time() + 600  # 10 minutos
        return key

    def get_url(self) -> str:
        return f"http://{self._ip}:{PORT}"

    def get_manual_url(self) -> str:
        return self.get_url()

    def _setup_routes(self):
        app = self._app
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

        def _auth(req: Request) -> bool:
            tok = req.headers.get("authorization", "").removeprefix("Bearer ").strip()
            return bool(tok) and tok in self._tokens

        @app.get("/", response_class=HTMLResponse)
        async def index():
            index_path = STATIC_DIR / "index.html"
            if index_path.exists():
                return HTMLResponse(index_path.read_text(encoding="utf-8"))
            return HTMLResponse("<h1>AP0L0</h1><p>index.html no encontrado.</p>")

        @app.post("/login")
        async def login(req: Request):
            body = await req.json()
            entered = str(body.get("pin", "")).strip().upper()
            now = time.time()
            if entered in self._pending_keys and self._pending_keys[entered] > now:
                del self._pending_keys[entered]
                tok = secrets.token_urlsafe(32)
                self._tokens.add(tok)
                self._token_keys[tok] = entered
                return JSONResponse({"ok": True, "token": tok})
            return JSONResponse({"ok": False, "error": "Invalid or expired key"}, status_code=401)

        @app.get("/auto-login")
        async def auto_login(key: str = ""):
            now = time.time()
            if not key or key not in self._pending_keys or self._pending_keys[key] <= now:
                return HTMLResponse("Link expirado", status_code=401)
            del self._pending_keys[key]
            tok = secrets.token_urlsafe(32)
            self._tokens.add(tok)
            self._token_keys[tok] = key
            return HTMLResponse(f"""
            <script>
                sessionStorage.setItem('jarvis_token','{tok}');
                location.href = '/';
            </script>
            """)

        # ---- API de sistema ----
        @app.get("/api/system")
        async def system_status(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            try:
                cpu = psutil.cpu_percent(interval=0.2)
                ram = psutil.virtual_memory().percent
                disk = psutil.disk_usage('/')
                battery = psutil.sensors_battery()
                bat_data = {"percent": battery.percent, "plugged": battery.power_plugged} if battery else None
                return JSONResponse({
                    "cpu": cpu, "ram": ram,
                    "disk": {"used": round(disk.used/disk.total*100,1), "used_gb": round(disk.used/(1024**3),1)},
                    "battery": bat_data,
                    "uptime": f"{int((time.time()-psutil.boot_time())//3600)}h {int(((time.time()-psutil.boot_time())%3600)//60)}m"
                })
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        @app.get("/api/info")
        async def get_info(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            return JSONResponse({
                "hostname": socket.gethostname(),
                "os": _platform.system(),
                "os_version": _platform.release(),
                "python_version": _platform.python_version(),
                "cpu_cores": psutil.cpu_count() if _PSUTIL_OK else 0,
                "process_count": len(psutil.pids()) if _PSUTIL_OK else 0,
                "ip": self._ip
            })

        @app.get("/api/volume")
        async def get_volume(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            vol, muted = _get_volume_os()
            return JSONResponse({"volume": vol, "muted": muted})

        @app.post("/api/volume")
        async def set_volume(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            volume = max(0, min(100, int(data.get("volume", 50))))
            _set_volume_os(volume)
            vol, muted = _get_volume_os()
            return JSONResponse({"status": "ok", "volume": vol, "muted": muted})

        @app.post("/api/volume/toggle")
        async def toggle_mute(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            _toggle_mute_os()
            vol, muted = _get_volume_os()
            return JSONResponse({"status": "ok", "volume": vol, "muted": muted})

        # ---- IA ----
        @app.post("/api/ai")
        async def ai_endpoint(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            prompt = data.get("prompt", "")
            if not prompt:
                return JSONResponse({"error": "Falta prompt"}, status_code=400)
            personality = data.get("personality", self._personality)

            result = _process_command(prompt)
            if result is not None:
                return JSONResponse({"response": result, "command": True})

            response = _get_ai_response(prompt, personality)
            return JSONResponse({"response": response, "command": False})

        @app.post("/api/tts")
        async def tts_endpoint(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            text = data.get("text", "")
            if not text:
                return JSONResponse({"error": "Falta texto"}, status_code=400)
            personality = data.get("personality", self._personality)
            audio_bytes = await _text_to_speech(text, personality)
            if audio_bytes:
                return JSONResponse({
                    "audio_base64": base64.b64encode(audio_bytes).decode(),
                    "mime_type": "audio/mpeg" if _EDGE_TTS_OK else "audio/wav"
                })
            return JSONResponse({"error": "No se pudo generar audio"}, status_code=500)

        # ---- Endpoint de voz ----
        @app.post("/api/voice")
        async def voice_endpoint(req: Request, file: UploadFile = FastAPIFile(...)):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            try:
                audio_bytes = await file.read()
                logger.info(f"Recibido archivo de audio: {len(audio_bytes)} bytes, content-type: {file.content_type}")

                if not audio_bytes or len(audio_bytes) < 100:
                    logger.warning(f"Audio demasiado pequeño: {len(audio_bytes)} bytes")
                    return JSONResponse({"transcript": "", "error": "Audio vacío o demasiado corto"}, status_code=400)

                transcript = _speech_to_text(audio_bytes)
                if not transcript:
                    return JSONResponse({"transcript": "", "error": "No se pudo transcribir el audio"}, status_code=200)

                personality = self._personality
                result = _process_command(transcript)
                if result is not None:
                    response_text = result
                else:
                    response_text = _get_ai_response(transcript, personality)

                audio_output = await _text_to_speech(response_text, personality)
                result_json = {
                    "transcript": transcript,
                    "response": response_text,
                    "audio_base64": base64.b64encode(audio_output).decode() if audio_output else None,
                    "mime_type": "audio/mpeg" if _EDGE_TTS_OK else "audio/wav"
                }
                return JSONResponse(result_json)
            except Exception as e:
                logger.error(f"Error en /api/voice: {e}")
                return JSONResponse({"error": str(e)}, status_code=500)

        # ---- Acciones reales ----
        @app.post("/api/open")
        async def open_app(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            app = data.get("app", "")
            if not app:
                return JSONResponse({"error": "Falta app"}, status_code=400)
            result = _open_app(app)
            return JSONResponse({"result": result})

        @app.post("/api/openurl")
        async def open_url(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            url = data.get("url", "")
            if not url:
                return JSONResponse({"error": "Falta url"}, status_code=400)
            result = _open_website(url)
            return JSONResponse({"result": result})

        @app.post("/api/system/action")
        async def system_action(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            action = data.get("action", "")
            if not action:
                return JSONResponse({"error": "Falta acción"}, status_code=400)
            result = _system_action(action)
            return JSONResponse({"result": result})

        @app.post("/api/lock")
        async def lock(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            result = _lock_screen()
            return JSONResponse({"result": result})

        @app.get("/api/screenshot")
        async def screenshot(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            result = _take_screenshot()
            if result.startswith("Error") or result.startswith("Captura no disponible"):
                return JSONResponse({"error": result}, status_code=500)
            return JSONResponse({"image_base64": result})

        @app.post("/api/media")
        async def media(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            action = data.get("action", "playpause")
            result = _control_media(action)
            return JSONResponse({"result": result})

        @app.post("/api/brightness")
        async def brightness(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            level = int(data.get("level", 50))
            result = _control_brightness(level)
            return JSONResponse({"result": result})

        @app.get("/api/brightness")
        async def get_brightness(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            result = _get_brightness()
            return JSONResponse({"result": result})

        @app.get("/api/wifi")
        async def wifi(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            result = _get_wifi_info()
            return JSONResponse({"result": result})

        @app.get("/api/bluetooth")
        async def bluetooth(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            result = _get_bluetooth_info()
            return JSONResponse({"result": result})

        # ---- Utilidades ----
        @app.get("/api/weather")
        async def weather(req: Request, city: str = "Madrid"):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            return JSONResponse({"result": _get_weather(city)})

        @app.post("/api/news")
        async def news(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            return JSONResponse({"result": _get_news_rss(data.get("category", "tecnologia"))})

        @app.post("/api/wikipedia")
        async def wikipedia_search(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            query = data.get("query", "")
            if not query:
                return JSONResponse({"error": "Falta query"}, status_code=400)
            return JSONResponse({"result": _search_wikipedia(query)})

        @app.post("/api/websearch")
        async def web_search(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            query = data.get("query", "")
            if not query:
                return JSONResponse({"error": "Falta query"}, status_code=400)
            return JSONResponse({"result": _web_search(query)})

        @app.post("/api/calculate")
        async def calculate(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            expr = data.get("expression", "")
            return JSONResponse({"result": _calculate(expr)})

        @app.get("/api/btc")
        async def btc(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            return JSONResponse({"result": _get_btc_price()})

        @app.get("/api/crypto")
        async def crypto(req: Request, coin: str = "bitcoin"):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            return JSONResponse({"result": _get_crypto_price(coin)})

        @app.get("/api/quote")
        async def quote(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            return JSONResponse({"result": _get_random_quote()})

        @app.get("/api/password")
        async def password(req: Request, length: int = 16):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            return JSONResponse({"password": _generate_password(length)})

        @app.get("/api/systeminfo")
        async def systeminfo(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            return JSONResponse({"result": _get_system_info()})

        @app.get("/api/clipboard")
        async def get_clipboard(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            if _PYPERCLIP_OK:
                return JSONResponse({"text": pyperclip.paste()})
            return JSONResponse({"error": "pyperclip no instalado"}, status_code=501)

        @app.post("/api/clipboard")
        async def set_clipboard(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            if _PYPERCLIP_OK:
                pyperclip.copy(data.get("text", ""))
                return JSONResponse({"status": "ok"})
            return JSONResponse({"error": "pyperclip no instalado"}, status_code=501)

        @app.post("/api/recipes")
        async def recipes(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            query = data.get("query", "")
            if not query:
                return JSONResponse({"error": "Falta query"}, status_code=400)
            return JSONResponse({"result": _search_recipes(query)})

        @app.post("/api/podcast")
        async def podcast(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            query = data.get("query", "")
            return JSONResponse({"result": _search_podcast(query)})

        @app.post("/api/reminders")
        async def add_reminder(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            return JSONResponse({"status": "ok", "result": _add_reminder(data.get("text", ""), int(data.get("minutes", 5)))})

        @app.get("/api/reminders")
        async def list_reminders(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            return JSONResponse({"reminders": _list_reminders()})

        @app.post("/api/notes")
        async def add_note(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            return JSONResponse({"status": "ok", "result": _add_note(data.get("title", ""), data.get("content", ""))})

        @app.get("/api/notes")
        async def list_notes(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            return JSONResponse({"notes": _list_notes()})

        @app.post("/api/personality")
        async def set_personality(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            data = await req.json()
            personality = data.get("personality", "jarvis")
            _set_personality(personality)
            self._personality = personality
            return JSONResponse({"status": "ok"})

        @app.get("/api/personality")
        async def get_personality(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            return JSONResponse({"personality": self._personality})

        @app.post("/api/upload")
        async def upload_file(req: Request, file: UploadFile = FastAPIFile(...)):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            upload_dir = Path.home() / "Downloads" / "AP0L0 Uploads"
            upload_dir.mkdir(exist_ok=True)
            dest = upload_dir / file.filename
            counter = 1
            while dest.exists():
                dest = upload_dir / f"{dest.stem}_{counter}{dest.suffix}"
                counter += 1
            content = await file.read()
            dest.write_bytes(content)
            return JSONResponse({"result": f"Archivo guardado como {dest.name}"})

    def _setup_websocket(self):
        @self._app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket, token: str = ""):
            tok = token.strip()
            if not tok or tok not in self._tokens:
                await websocket.close(code=4001)
                return
            await websocket.accept()
            # ===== Llamar al callback cuando un cliente se conecta =====
            if self._connect_callback is not None:
                try:
                    self._connect_callback()
                except Exception as e:
                    logger.error(f"Error en callback de conexión: {e}")

            self._clients.add(websocket)
            try:
                while True:
                    data = await websocket.receive_json()
                    msg_type = data.get("type")
                    if msg_type == "chat":
                        text = data.get("text", "").strip()
                        if text:
                            result = _process_command(text)
                            if result is not None:
                                await websocket.send_json({"type": "response", "text": result})
                            else:
                                response = _get_ai_response(text, self._personality)
                                await websocket.send_json({"type": "response", "text": response})
                    elif msg_type == "voice":
                        audio_b64 = data.get("audio", "")
                        if audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            transcript = _speech_to_text(audio_bytes)
                            if transcript:
                                result = _process_command(transcript)
                                if result is not None:
                                    response_text = result
                                else:
                                    response_text = _get_ai_response(transcript, self._personality)
                                audio_output = await _text_to_speech(response_text, self._personality)
                                await websocket.send_json({
                                    "type": "audio_response",
                                    "text": response_text,
                                    "audio": base64.b64encode(audio_output).decode() if audio_output else None
                                })
                    elif msg_type == "command" and data.get("command") == "change_personality":
                        personality = data.get("personality", "jarvis")
                        _set_personality(personality)
                        self._personality = personality
                        await websocket.send_json({"type": "system", "message": f"Personalidad cambiada a {personality}"})
            except WebSocketDisconnect:
                pass
            finally:
                self._clients.discard(websocket)

    async def broadcast(self, msg: dict):
        for ws in list(self._clients):
            try:
                await ws.send_json(msg)
            except:
                pass

    def get_url(self) -> str:
        return f"http://{self._ip}:{PORT}"

    async def serve(self):
        if not _FASTAPI_OK:
            logger.error("FastAPI no instalado")
            return
        cfg = uvicorn.Config(self._app, host="0.0.0.0", port=PORT, log_level="warning")
        server = uvicorn.Server(cfg)
        logger.info(f"🌐 Servidor disponible en: {self.get_url()}")
        logger.info("📱 PIN por defecto: XXXXXX")
        logger.info(f"🧠 Usando modelo: {_get_ai_config().get('model', GEMINI_MODEL)}")
        logger.info("🗣️ TTS: EdgeTTS con voces según personalidad")
        logger.info("⚡ Comandos: detección automática de acciones")
        await server.serve()

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(DashboardServer().serve())
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario.")