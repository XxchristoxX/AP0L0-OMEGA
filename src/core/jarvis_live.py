# src/core/jarvis_live.py
# ============================================================================
# CORE DEL ASISTENTE EN VIVO (JARVIS LIVE) - VERSIÓN DEFINITIVA CORREGIDA
# CON RECONEXIÓN FORZADA MEDIANTE EVENTO (SIN EXCEPCIONES PERDIDAS)
# ============================================================================

import os
import sys
import warnings
import ctypes
import platform as _platform
import subprocess as _subprocess
import json
import traceback
import asyncio
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
import math
import random
import logging
import socket
import webbrowser
import shutil
import base64
import io
try:
    import sounddevice as sd
    _SOUNDDEVICE_AVAILABLE = True
except ImportError:
    _SOUNDDEVICE_AVAILABLE = False

    class _SoundDeviceUnavailable:
        def __getattr__(self, name):
            raise RuntimeError(
                "sounddevice no está instalado; instala requirements.txt para usar audio."
            )
    sd = _SoundDeviceUnavailable()

# ===== NUEVAS IMPORTACIONES PARA HERRAMIENTAS INTEGRADAS =====
from src.actions.app_launcher import app_launcher
from src.actions.spotify_controller import spotify_control
from src.actions.deezer_controller import deezer_control
from src.actions.antivirus_scanner import antivirus_scan, ejecutar_scan_antivirus
from src.actions.vpn import vpn_control
from src.actions.iptv_player import iptv_play
from src.actions.file_manager import file_manager
from src.actions.google_services import google_services
from src.actions.ha_config import ha_control
from src.core.jarvis_agent import jarvis_agent
from src.actions.jarvis_music import jarvis_music
from src.actions.jarvis_rap import jarvis_rap
from src.core.local_agent_manager import local_agent
from src.core.memory_manager import memory_operations
from src.actions.nemotron_asr import nemotron_asr
from src.actions.obsidian_helper import obsidian_control
from src.actions.project_builder import project_builder
from src.actions.restaurant_helper import restaurant_search
from src.actions.secure_browser import secure_browser
from src.actions.sports_web import sports_web
from src.actions.uninstaller_helper import uninstaller
from src.actions.youtube_api import youtube_advanced
from src.actions.vision_module import (
    vision_click,
    vision_type,
    vision_search_on_site,
    vision_camera,
    vision_browser
)

# ===== NUEVA IMPORTACIÓN =====
try:
    import websockets
    _WEBSOCKETS_AVAILABLE = True
except ImportError:
    _WEBSOCKETS_AVAILABLE = False
    class _WebSocketsUnavailable:
        class ConnectionClosed(Exception):
            pass
        class ConnectionClosedOK(ConnectionClosed):
            pass
        def __getattr__(self, name):
            raise RuntimeError("websockets no está instalado; dashboard remoto desactivado.")
    websockets = _WebSocketsUnavailable()

# ===== SILENCIAR LOGS DE TERCEROS =====
logging.basicConfig(level=logging.WARNING)
for lib in ['google', 'httpx', 'urllib3', 'transformers', 'tensorflow', 'faster_whisper', 'PIL']:
    logging.getLogger(lib).setLevel(logging.WARNING)

# ===== IMPORTS DE PYTQT =====
from PyQt6.QtCore import QTimer, QMetaObject, Qt, Q_ARG, pyqtSignal
from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QMessageBox

# ===== AÑADIR CARPETA src AL PYTHONPATH =====
BASE_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ===== IMPORTS DE MÓDULOS PROPIOS =====
from src.core.config import (
    LIVE_MODEL, CHANNELS, SEND_SAMPLE_RATE, RECEIVE_SAMPLE_RATE, CHUNK_SIZE,
    VOICE_MAP, DEFAULT_VOICE, THEME_MAP, DEFAULT_THEME,
    _get_api_key, _validate_api_key, _get_config, _save_config, _load_system_prompt,
    _clean_transcript, ReconnectException, get_live_model_list,
    get_selected_live_model, get_selected_text_model, is_gemini_live_available,
    gemini_generate, PERSONALITY_INFO
)
from src.core.tools import TOOL_DECLARATIONS
from src.memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
    save_session_summary, pop_last_session, get_last_session_summary,
    save_user_language, get_user_language
)
from src.memory.config_manager import get_brief_enabled

# ===== IMPORTAR CONSTANTES DE SISTEMA =====
from src.utils.system_utils import IS_WINDOWS, IS_MAC, IS_LINUX

# ===== IMPORTACIÓN OPCIONAL DE google.genai =====
# El modo local no debe depender del SDK de Gemini instalado.
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    _GEMINI_SDK_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    class APIError(Exception):
        pass
    _GEMINI_SDK_AVAILABLE = False

# ===== IMPORT CORREGIDO: jarvis_ui.py está en la raíz =====
from ui import JarvisUI

# ===== FUNCIONES DE FUNC_INTEGRATION (FALLBACK) =====
try:
    from src.core.func_integration import (
        resolver_comandos_locales as _resolver_comandos_locales,
        resolver_info_sistema_local as _resolver_info_sistema_local,
        resolver_matematica_local as _resolver_matematica_local,
        resolver_extras_local as _resolver_extras_local,
        resolver_globo_local as _resolver_globo_local,
        resolver_traduccion_local as _resolver_traduccion_local,
        resolver_conversion_local as _resolver_conversion_local,
        ejecutar_accion_pc as _ejecutar_accion_pc,
    )
    _FUNC_INTEGRATION_AVAILABLE = True
    print("[JARVIS] ✅ func_integration.py cargado.")
except ImportError as e:
    _FUNC_INTEGRATION_AVAILABLE = False
    print(f"[JARVIS] ⚠️ func_integration.py no encontrado: {e}")
    # Stubs
    def _resolver_comandos_locales(text): return None
    def _resolver_info_sistema_local(text): return None
    def _resolver_matematica_local(text): return None
    async def _resolver_extras_local(text): return None
    async def _resolver_globo_local(text): return None
    def _resolver_traduccion_local(text): return None
    def _resolver_conversion_local(text): return None
    def _ejecutar_accion_pc(text): return None

# ===== INTENTAR IMPORTAR COMMAND_PROCESSOR =====
_COMMAND_PROCESSOR_AVAILABLE = False
try:
    from src.core.command_processor import (
        resolver_comandos_locales as cp_resolver_comandos_locales,
        ejecutar_accion_pc as cp_ejecutar_accion_pc,
    )
    _COMMAND_PROCESSOR_AVAILABLE = True
    print("[JARVIS] ✅ command_processor.py cargado.")
except ImportError as e:
    print(f"[ADVERTENCIA] command_processor.py no encontrado o falló al importar: {e}")
    cp_resolver_comandos_locales = None
    cp_ejecutar_accion_pc = None

# ===== INTENTAR IMPORTAR func.py (obsoleto) =====
_FUNC_AVAILABLE = False
try:
    import func
    _FUNC_AVAILABLE = True
    print("[JARVIS] ✅ func.py cargado (obsoleto, usar command_processor).")
except Exception as e:
    func = None

# ===== PERSONALIDAD DUAL =====
try:
    from src.core.prompt_loader import load_prompt
    _PERSONALITY_AVAILABLE = True
except ImportError:
    _PERSONALITY_AVAILABLE = False

# ===== AGENTE AUTÓNOMO =====
try:
    from src.agent.planner import AgentPlanner
    from src.agent.executor import AgentExecutor
    _AGENT_AVAILABLE = True
except ImportError:
    _AGENT_AVAILABLE = False

# ===== ACCIONES BASE =====
from src.actions.file_processor import file_processor
from src.actions.flight_finder import flight_finder
from src.actions.weather_report import weather_action
from src.actions.send_message import send_message
from src.actions.reminder import reminder
from src.actions.computer_settings import computer_settings
from src.actions.youtube_video import youtube_video
from src.actions.desktop import desktop_control
from src.actions.browser_control import browser_control
from src.actions.file_controller import file_controller
from src.actions.code_helper import code_helper
from src.actions.dev_agent import dev_agent
from src.actions.web_search import web_search as web_search_action
from src.actions.web_search import _news as _fetch_news_sync
from src.actions.computer_control import computer_control
from src.actions.game_updater import game_updater
from src.actions.system_monitor import SystemMonitor, get_system_status
from src.actions.proactive import ProactiveEngine
from src.actions.background_monitor import (
    add_monitor, remove_monitor, list_monitors, check_all as monitor_check_all,
)

# ===== CAPTURA (FALLBACKS) =====
try:
    from src.actions.screen_processor import _capture_camera, _capture_screen
    print("[CAPTURE] ✅ Módulo de captura cargado.")
except ImportError:
    import io
    try:
        import pyautogui
        _PYAutoGUI_AVAILABLE = True
    except ImportError:
        pyautogui = None
        _PYAutoGUI_AVAILABLE = False
    try:
        import cv2
        import numpy as np
        _CAPTURE_AVAILABLE = True
    except ImportError:
        cv2 = None
        np = None
        _CAPTURE_AVAILABLE = False
    def _capture_screen():
        if not pyautogui:
            return b"", "image/png"
        screenshot = pyautogui.screenshot()
        img_bytes = io.BytesIO()
        screenshot.save(img_bytes, format='PNG')
        return img_bytes.getvalue(), 'image/png'
    def _capture_camera():
        if not _CAPTURE_AVAILABLE:
            return b"", "image/png"
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
        if not cap.isOpened():
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "No camera found", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
            _, img_encoded = cv2.imencode('.png', frame)
            return img_encoded.tobytes(), 'image/png'
        ret, frame = cap.read()
        if not ret:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "Camera error", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
        cap.release()
        _, img_encoded = cv2.imencode('.png', frame)
        return img_encoded.tobytes(), 'image/png'
    print("[CAPTURE] Usando funciones de respaldo para captura.")

# ===== MÓDULOS OPCIONALES =====
try:
    from src.actions.ocr import OCRService
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False

try:
    from src.actions.face_recognition import FaceRecognitionService
    _FACE_AVAILABLE = True
except ImportError:
    _FACE_AVAILABLE = False

try:
    from src.actions.news_report import NewsReporter
    _NEWS_REPORT_AVAILABLE = True
except ImportError:
    _NEWS_REPORT_AVAILABLE = False

try:
    from src.actions.todo_list import TodoListGenerator
    _TODO_AVAILABLE = True
except ImportError:
    _TODO_AVAILABLE = False

try:
    from src.actions.youtube_downloader import YouTubeDownloader
    _YTDL_AVAILABLE = True
except ImportError:
    _YTDL_AVAILABLE = False

try:
    from src.actions.rhythmbox import RhythmboxController
    _RHYTHMBOX_AVAILABLE = True
except ImportError:
    _RHYTHMBOX_AVAILABLE = False

try:
    from src.actions.wallpaper import WallpaperChanger
    _WALLPAPER_AVAILABLE = True
except ImportError:
    _WALLPAPER_AVAILABLE = False

try:
    from src.skills.catalog import SkillsCatalog
    _SKILLS_CATALOG_AVAILABLE = True
except ImportError:
    _SKILLS_CATALOG_AVAILABLE = False

try:
    from src.skills.agents import BuiltInAgents
    _SKILLS_AGENTS_AVAILABLE = True
except ImportError:
    _SKILLS_AGENTS_AVAILABLE = False

try:
    from src.actions.gdrive_integration import GDriveIntegration
    _GDRIVE_AVAILABLE = True
except ImportError:
    _GDRIVE_AVAILABLE = False

try:
    from src.actions.clipboard_intelligence import ClipboardIntelligence
    _CLIPBOARD_AVAILABLE = True
except ImportError:
    _CLIPBOARD_AVAILABLE = False

try:
    from openai import OpenAI
    _OPENROUTER_AVAILABLE = True
except ImportError:
    _OPENROUTER_AVAILABLE = False

try:
    from src.utils.panel_circular_IA import JarvisCircularPanel
    _PANEL_AVAILABLE = True
except ImportError:
    _PANEL_AVAILABLE = False

# ===== NUEVAS HERRAMIENTAS =====
from src.actions.emotion_detector import detect_emotion
from src.actions.aura_mode import toggle_aura_mode, get_aura_prompt
from src.actions.contact_manager import contact_manager
from src.actions.iot_control import iot_control
from src.agent.multi_agent import multi_agent_tool
from src.core.reflection_engine import ReflectionEngine

from src.actions.project_builder import ProjectBuilder
from src.actions.file_manager import (
    lister_dossier, trier_par_type, trier_par_date,
    creer_sous_dossier, renommer_fichier, deplacer_fichier, chercher_fichier,
    ouvrir_dossier, arranger_fenetres_dossiers
)
from src.actions.vpn import connect as vpn_connect, disconnect as vpn_disconnect, get_status as vpn_get_status, get_countries
from src.actions.secure_browser import trigger_browser, close_browser_window
from src.actions.jarvis_music import JarvisMusic
from src.actions.google_services import creer_google_doc, modifier_google_doc, lire_emails
from src.actions.youtube_api import (
    yt_infos_video, yt_chercher_multi, yt_trending,
    yt_infos_chaine, yt_resumer_video, yt_dernieres_videos
)
from src.actions.app_launcher import open_app_compat as open_app, lanzar_app, modo_boulot, listar_apps
from src.actions.iptv_player import parse_playlist_file, parse_playlist_url, get_video_stream_url, start_video_server
from src.actions.antivirus_scanner import ejecutar_scan_antivirus

# ===== MÓDULO DE VISIÓN (INTEGRADO) =====
from src.actions.vision_module import (
    set_vision_context,
    jarvis_vision_cliquer,
    jarvis_vision_ecrire,
    jarvis_vision_rechercher_sur_site,
    jarvis_vision_camera,
    jarvis_vision_navigateur
)

# =====================================================================
# CLASE PRINCIPAL JarvisLive
# =====================================================================
class JarvisLive:
    def __init__(self, ui, router=None, skills_registry=None, auto_programmer=None,
                 healer=None, learner=None, boot_screen=None):
        self.ui = ui
        self.boot_screen = boot_screen
        self._asst_name = "APOLO"
        self._asst_subtitle = "Autonomous Platform for Orchestration, Learning and Operations"
        self.session = None
        self.audio_in_queue = None
        self.out_queue = None
        self._loop = None
        self._is_speaking = False
        self._speaking_lock = threading.Lock()
        self._phone_active = False
        self._pending_vision = None
        self._vision_cam_active = False
        self._vision_close_pending = False
        self._vision_last_time = 0.0
        self._vision_busy = False
        self._interrupted = False
        self._turn_done_event = None
        self._dashboard = None
        self._briefing_sent = False
        self._sys_monitor = SystemMonitor()
        self._proactive = ProactiveEngine()
        self._last_user_speech = time.monotonic()
        self._session_log = []
        self._task_reminders = []
        self._reconnect_attempts = 0
        self._reconnect_immediate = False
        self._current_model = LIVE_MODEL
        self._session_resumption_handle = None
        self._reconnecting = False
        self._should_restart = False
        self._personality_change_requested = False

        # ===== SISTEMA DE DESHACER =====
        self._undo_stack = []
        self._undo_enabled = True

        # EVENTO DE RECONEXIÓN
        self._reconnect_event = asyncio.Event()

        # REFERENCIA AL PANEL
        self.panel = None

        # ===== USAR DEPENDENCIAS COMPARTIDAS =====
        from src.core.hybrid_router import HybridRouter
        from src.core.skills_registry import SkillsRegistry
        from src.core.persistence import Persistence
        from src.skills.auto_programmer_advanced import AutoProgrammer
        from src.autonomous.self_healer import SelfHealer
        from src.autonomous.auto_learn import AutonomousLearner

        self.router = router if router is not None else HybridRouter()
        self.skills_registry = skills_registry if skills_registry is not None else SkillsRegistry()
        self.persistence = Persistence()
        self.auto_programmer = auto_programmer if auto_programmer is not None else AutoProgrammer(self.router, self.skills_registry, self.persistence)
        self.self_healer = healer if healer is not None else SelfHealer(self.auto_programmer, self.persistence)
        self.autonomous_learner = learner if learner is not None else AutonomousLearner(
            router=self.router,
            skills_registry=self.skills_registry,
            self_healer=self.self_healer,
            auto_programmer=self.auto_programmer,
            persistence=self.persistence,
            daily_limit=50
        )

        self.modo_local = False
        self.asistente_local = None
        self.ultima_prueba_internet = 0
        self.intervalo_prueba = 30

        self.personality_prompts = {}
        _cfg = _get_config()

        # LEER LA PERSONALIDAD DESDE EL ARCHIVO, PERO LA SOBREESCRIBIREMOS SI HAY UNA RECONEXIÓN
        self.current_personality = _cfg.get("personality", "apolo").lower()
        self._pending_reconnect = False
        self._reconnect_personality = self.current_personality
        self._reconnect_theme = THEME_MAP.get(self.current_personality, DEFAULT_THEME)
        self._reconnect_voice = VOICE_MAP.get(self.current_personality, DEFAULT_VOICE)

        self._user_name = _cfg.get("user_name", "Christopher")
        self._user_language = get_user_language() or "es"
        self._user_language_detected = bool(get_user_language())

        self.continuous_listening = False
        self.aura_enabled = False
        self._iron_man_active = False

        self.gesture = None
        self.face_auth = None
        self.proactive_v2 = None
        self.reflection = None

        # ===== INICIALIZACIÓN DEL CLIENTE DE VISIÓN =====
        self._vision_client = None
        api_key = _get_api_key()
        if _validate_api_key(api_key):
            try:
                self._vision_client = genai.Client(api_key=api_key)
                print("[JARVIS] ✅ Cliente de visión inicializado.")
            except Exception as e:
                print(f"[JARVIS] ⚠️ Error al crear cliente de visión: {e}")
        else:
            print("[JARVIS] ⚠️ API key inválida, la visión no estará disponible.")

        # ===== INYECCIÓN DE CONTEXTO PARA VISIÓN =====
        self._init_vision_context()

        # Cargar prompts de personalidad
        if _PERSONALITY_AVAILABLE:
            try:
                self.personality_prompts = {
                    "jarvis": load_prompt("prompt_jarvis.txt"),
                    "agata": load_prompt("prompt_agata.txt"),
                    "tony": load_prompt("prompt_tony.txt") or load_prompt("prompt_jarvis.txt"),
                    "friday": load_prompt("prompt_friday.txt") or load_prompt("prompt_agata.txt"),
                    "apolo": load_prompt("prompt_apolo.txt") or load_prompt("prompt_jarvis.txt")
                }
            except Exception:
                pass

        self._agent_executor = None
        if _AGENT_AVAILABLE:
            try:
                self._agent_executor = AgentExecutor()
            except Exception:
                self._agent_executor = None

        self.ui.on_text_command = self._on_text_command
        self.ui.on_remote_clicked = self._make_remote_key
        self.ui.on_interrupt = self.interrupt

        self._init_services()

        try:
            self.skills_registry.register_skill("auto_programmer_advanced", "src/skills/auto_programmer_advanced.py")
        except Exception:
            pass

        print("[MAIN] ✅ Módulos de autocuración y vida propia iniciados.")
        self._apply_personality_to_ui(self.current_personality)

    # =====================================================================
    # INICIALIZACIÓN DEL CONTEXTO DE VISIÓN
    # =====================================================================
    def _init_vision_context(self):
        """Configura el contexto global que usa vision_module.py."""
        async def _speak(text):
            self.hablar(text)

        async def _ask_vision(prompt, img_b64):
            if self._vision_client is None:
                return "El cliente de visión no está disponible."
            try:
                response = self._vision_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        prompt,
                        {"inline_data": {"mime_type": "image/png", "data": img_b64}}
                    ]
                )
                return response.text.strip() if response and response.text else "No se pudo analizar la imagen."
            except Exception as e:
                return f"Error al analizar la imagen: {e}"

        async def _request_camera_capture():
            return None

        async def _request_screen_capture():
            return None

        def _get_user_name():
            return self._user_name

        vision_context = {
            "speak": _speak,
            "ask_vision": _ask_vision,
            "request_camera_capture": _request_camera_capture,
            "request_screen_capture": _request_screen_capture,
            "connected_clients": set(),
            "webcam_active": False,
            "user_name": self._user_name,
            "client": self._vision_client,
            "chosen_model": "gemini-2.5-flash"
        }
        set_vision_context(vision_context)
        print("[JARVIS] ✅ Contexto de visión inyectado.")

    # ===== APLICAR PERSONALIDAD A LA UI (CORREGIDO) =====
    def _apply_personality_to_ui(self, personality: str):
        try:
            from src.ui.ui_utils import apply_theme, apply_ui_accent
            from PyQt6.QtCore import QTimer
            theme = THEME_MAP.get(personality, DEFAULT_THEME)
            voice = VOICE_MAP.get(personality, DEFAULT_VOICE)
            name_map = {"jarvis": "JARVIS", "agata": "AGATA", "tony": "TONY", "friday": "FRIDAY", "apolo": "APOLO"}
            subtitle_map = {
                "jarvis": "Just A Rather Very Intelligent System",
                "agata": "Advanced Generative Assistant for Technology & Art",
                "tony": "Technology Oriented Network Yield",
                "friday": "Female Replacement Intelligent Digital Assistant Youth",
                "apolo": "Autonomous Platform for Orchestration, Learning and Operations",
            }
            new_name = name_map.get(personality, "APOLO")
            new_subtitle = subtitle_map.get(personality, "Autonomous Platform for Orchestration, Learning and Operations")
            self._asst_name = new_name
            self._asst_subtitle = new_subtitle

            def update_ui():
                if self.ui and hasattr(self.ui, '_win'):
                    win = self.ui._win
                    win._theme_changed.emit(theme)
                    apply_theme(personality)
                    apply_ui_accent(theme)
                    win._assistant_name = new_name
                    win._assistant_subtitle = new_subtitle
                    if hasattr(win, '_title_lbl'):
                        win._title_lbl.setText(new_name.upper())
                    if hasattr(win, '_sub_lbl'):
                        win._sub_lbl.setText(new_subtitle)
                    win.setWindowTitle(f"{new_name.upper()} — XxchristoxX")
                    if hasattr(win, 'hud'):
                        win.hud.persona = personality
                        win.hud._assistant_name = new_name
                        win.hud.update()
                    win._apply_ui_colors()
                    win._update_badges()
                    win.update()
                    win.repaint()
                    if self.panel:
                        self.panel.set_theme_color(theme)
                        self.panel.update()
                        self.panel.repaint()
                    if hasattr(win, '_update_float_menu_title'):
                        win._update_float_menu_title()
                    if hasattr(win, '_update_toggle_states'):
                        win._update_all_toggle_states()
                try:
                    cfg = _get_config()
                    cfg["personality"] = personality
                    cfg["assistant_name"] = new_name
                    cfg["assistant_subtitle"] = new_subtitle
                    cfg["ui_color"] = theme
                    cfg["voice"] = voice
                    _save_config(cfg)
                except Exception:
                    pass
                print(f"[{self._asst_name}] ✅ Personalidad aplicada: {personality.capitalize()} | Color: {theme} | Voz: {voice}")

            if threading.current_thread() is threading.main_thread():
                update_ui()
            else:
                QTimer.singleShot(0, update_ui)
        except Exception as e:
            print(f"[{self._asst_name}] ⚠️ Error aplicando personalidad: {e}")

    def set_panel(self, panel):
        self.panel = panel
        if panel:
            panel.set_command_callback(self._on_panel_command)

    def _on_panel_command(self, command):
        if command == "[TOGGLE_MIC]":
            self.ui.muted = not self.ui.muted
            if self.panel:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self.panel.set_mic_state(self.ui.muted))
        else:
            self._on_text_command(command)

    # =====================================================================
    # NUEVO MÉTODO CORREGIDO: _force_switch_personality (CON RECONEXIÓN)
    # =====================================================================
    async def _force_switch_personality(self, params: dict, player=None, speak=None):
        personality = params.get("personality", "jarvis").lower()
        valid = ["jarvis", "agata", "tony", "friday", "apolo"]
        if personality not in valid:
            msg = f"Personalidad '{personality}' no válida. Opciones: {', '.join(valid)}"
            if speak:
                speak(msg)
            return msg

        # Obtener información
        info = PERSONALITY_INFO.get(personality, PERSONALITY_INFO["apolo"])
        name = info["name"]
        subtitle = info["subtitle"]
        theme = info["color"]
        voice = info["voice"]

        # Actualizar estado interno
        self.current_personality = personality
        self._asst_name = name
        self._asst_subtitle = subtitle
        self._reconnect_personality = personality
        self._reconnect_theme = theme
        self._reconnect_voice = voice
        self._pending_reconnect = True
        self._reconnect_immediate = True
        self._reconnect_attempts = 0

        # Aplicar tema completo en la UI
        if self.ui and hasattr(self.ui, 'apply_full_theme'):
            self.ui.apply_full_theme(personality, name, subtitle, theme)
        else:
            if self.ui:
                self.ui.set_theme(theme)
                self.ui.update_assistant_info(name, subtitle)
                self.ui.set_personality(personality, voice, theme)

        if self.panel:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.panel.set_theme_color(theme))

        # Guardar configuración
        try:
            cfg = _get_config()
            cfg["personality"] = personality
            cfg["voice"] = voice
            cfg["ui_color"] = theme
            cfg["assistant_name"] = name
            cfg["assistant_subtitle"] = subtitle
            _save_config(cfg)
        except Exception as e:
            print(f"[MAIN] ⚠️ Error guardando personalidad: {e}")

        # Mensaje de bienvenida
        welcome_msgs = {
            "jarvis": "Señor, Jarvis de vuelta. ¿Cómo está?",
            "agata": "Hola, señor. Soy Agata. Encantada de estar con usted.",
            "tony": "Señor, Tony aquí. ¿Qué necesitamos construir hoy?",
            "friday": "Hola, soy Friday. ¿Cómo puedo ayudarle?",
            "apolo": "Apolo online. ¿Qué necesita?"
        }
        welcome = welcome_msgs.get(personality, welcome_msgs["apolo"])
        if speak:
            speak(welcome)

        if player:
            player.write_log(f"SYS: ✅ Personalidad cambiada a {personality.capitalize()}: {welcome}")

        # Forzar reconexión con un pequeño retraso para que la UI se actualice
        self._reconnect_event.set()
        await asyncio.sleep(0.2)

        return f"Personalidad cambiada a {personality.capitalize()}"

    # =====================================================================
    # MÉTODOS DE CONEXIÓN Y UTILIDADES
    # =====================================================================
    def probar_internet(self) -> bool:
        try:
            import requests
            requests.get("https://www.google.com", timeout=3)
            return True
        except:
            return False

    def verificar_conexion(self) -> bool:
        if str(_get_config().get("connection_mode", "auto")).lower() == "local":
            self.modo_local = True
            return False
        ahora = time.time()
        if ahora - self.ultima_prueba_internet < self.intervalo_prueba:
            return not self.modo_local
        self.ultima_prueba_internet = ahora
        tiene_internet = self.probar_internet()
        if tiene_internet and self.modo_local:
            self.ui.write_log("🌐 Conexión restaurada. Cambiando a modo NUBE (Gemini).")
            self.modo_local = False
            self.ui.set_modo("nube")
            self._pending_reconnect = True
            self._reconnect_event.set()
        elif not tiene_internet and not self.modo_local:
            self.ui.write_log("📡 Sin conexión a Internet. Cambiando a modo LOCAL.")
            self.modo_local = True
            self.ui.set_modo("local")
            if self.asistente_local is None:
                try:
                    from local_ai import LocalAssistant
                    self.asistente_local = LocalAssistant()
                    self.asistente_local.hablar("Modo local activado. Estoy funcionando sin internet.")
                except Exception as exc:
                    self.ui.write_log(f"SYS: Voz local no disponible: {exc}")
        return not self.modo_local

    def procesar_comando_local(self, comando_texto: str = None):
        if self.asistente_local is None:
            from local_ai import LocalAssistant
            self.asistente_local = LocalAssistant()
        if comando_texto:
            respuesta = self.asistente_local.think(comando_texto)
            self.asistente_local.hablar(respuesta)
            return respuesta
        else:
            return self.asistente_local.process_voice_command()

    def _init_services(self):
        self.ocr = None
        self.face = None
        self.news_reporter = None
        self.todo = None
        self.ytdl = None
        self.rhythmbox = None
        self.wallpaper = None
        self.skills = None
        self.agents = None
        self.gdrive = None
        self.clipboard = None
        self.aiml_kernel = None

    def _make_remote_key(self):
        if self._dashboard is None:
            self.ui.write_log("SYS: Dashboard unavailable.")
            return None
        key = self._dashboard.new_key()
        url = self._dashboard.get_url()
        manual = self._dashboard.get_manual_url()
        return url, key, f"{url}/auto-login?key={key}", manual

    # =====================================================================
    # MANEJO DE COMANDOS DE TEXTO - CON COMMAND_PROCESSOR INTEGRADO
    # =====================================================================
    def _on_text_command(self, text: str):
        """Procesa comandos de texto del usuario."""
        if not text or not text.strip():
            return

        text = text.strip()

        # ===== 1. DETECTAR COMANDOS ESPECIALES ANTES DE CUALQUIER OTRA COSA =====
        import re
        personality_patterns = [
            r"cambia\s*(?:a\s*)?(jarvis|agata|tony|friday|apolo)",
            r"cambiar\s*(?:a\s*)?(jarvis|agata|tony|friday|apolo)",
            r"pon\s*(?:personalidad\s*)?(jarvis|agata|tony|friday|apolo)",
            r"set\s*(?:personality\s*)?(jarvis|agata|tony|friday|apolo)"
        ]
        for pattern in personality_patterns:
            match = re.search(pattern, text.lower())
            if match:
                personality = match.group(1)
                self.ui.write_log(f"SYS: Cambiando a personalidad {personality.capitalize()} (comando local)")
                if self._loop is not None and not self._loop.is_closed():
                    asyncio.run_coroutine_threadsafe(
                        self._force_switch_personality({"personality": personality}),
                        self._loop
                    )
                else:
                    def run_force():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        new_loop.run_until_complete(self._force_switch_personality({"personality": personality}))
                        new_loop.close()
                    threading.Thread(target=run_force, daemon=True).start()
                return

        # --- Comandos de deshacer ---
        if text.lower() in ["undo", "deshacer", "revertir", "atrás"]:
            if self._undo_stack:
                action = self._undo_stack.pop()
                try:
                    action["undo"]()
                    self.ui.write_log(f"SYS: Deshecho: {action.get('description', 'Acción')}")
                    self.hablar(f"Acción deshecha, señor.")
                except Exception:
                    self.hablar(f"No pude deshacer la acción, señor.")
            else:
                self.hablar("No hay acciones para deshacer, señor.")
            return

        # --- Comandos de autocuración ---
        if text.lower() in ["autocuración", "autocuracion", "self-heal", "diagnóstico", "diagnostico"]:
            self.ui.write_log("SYS: Activando protocolo de autocuración...")
            if hasattr(self, "self_healer"):
                self.self_healer.diagnose_and_repair()
            self.hablar("Protocolo de autocuración completado.")
            return

        # ===== 2. INTENTAR CON COMMAND_PROCESSOR =====
        if _COMMAND_PROCESSOR_AVAILABLE:
            try:
                result = cp_resolver_comandos_locales(text)
                if result:
                    self.hablar(result)
                    return
                result = cp_ejecutar_accion_pc(text)
                if result:
                    self.hablar(result)
                    return
            except Exception as e:
                self.ui.write_log(f"ERR: command_processor falló: {e}")

        # ===== 3. FALLBACK: FUNC_INTEGRATION =====
        if _FUNC_INTEGRATION_AVAILABLE:
            try:
                result = _resolver_info_sistema_local(text)
                if result:
                    self.hablar(result)
                    return
                result = _resolver_matematica_local(text)
                if result:
                    self.hablar(result)
                    return
                result = _resolver_conversion_local(text)
                if result:
                    self.hablar(result)
                    return
                result = _resolver_traduccion_local(text)
                if result:
                    self.hablar(result)
                    return
                if asyncio.iscoroutinefunction(_resolver_extras_local):
                    future = asyncio.run_coroutine_threadsafe(_resolver_extras_local(text), self._loop)
                    result = future.result(timeout=5)
                    if result:
                        self.hablar(result)
                        return
                if asyncio.iscoroutinefunction(_resolver_globo_local):
                    future = asyncio.run_coroutine_threadsafe(_resolver_globo_local(text), self._loop)
                    result = future.result(timeout=5)
                    if result:
                        self.hablar(result)
                        return
                if asyncio.iscoroutinefunction(_resolver_comandos_locales):
                    future = asyncio.run_coroutine_threadsafe(_resolver_comandos_locales(text), self._loop)
                    result = future.result(timeout=5)
                    if result:
                        self.hablar(result)
                        return
                result = _ejecutar_accion_pc(text)
                if result:
                    self.hablar(result)
                    return
            except Exception as e:
                self.ui.write_log(f"ERR: Comando local falló: {e}")

        # ===== 4. FALLBACK: FUNC.PY =====
        if _FUNC_AVAILABLE and func:
            try:
                if hasattr(func, 'resolver_comandos_locales'):
                    if asyncio.iscoroutinefunction(func.resolver_comandos_locales):
                        future = asyncio.run_coroutine_threadsafe(func.resolver_comandos_locales(text), self._loop)
                        res = future.result(timeout=5)
                    else:
                        res = func.resolver_comandos_locales(text)
                    if res:
                        self.hablar(res)
                        return
                if hasattr(func, 'resolver_info_sistema_local'):
                    res = func.resolver_info_sistema_local(text)
                    if res:
                        self.hablar(res)
                        return
                if hasattr(func, 'resolver_matematica_local'):
                    res = func.resolver_matematica_local(text)
                    if res:
                        self.hablar(res)
                        return
                if hasattr(func, 'resolver_extras_local'):
                    if asyncio.iscoroutinefunction(func.resolver_extras_local):
                        future = asyncio.run_coroutine_threadsafe(func.resolver_extras_local(text), self._loop)
                        res = future.result(timeout=5)
                    else:
                        res = func.resolver_extras_local(text)
                    if res:
                        self.hablar(res)
                        return
                if hasattr(func, 'resolver_globo_local'):
                    if asyncio.iscoroutinefunction(func.resolver_globo_local):
                        future = asyncio.run_coroutine_threadsafe(func.resolver_globo_local(text), self._loop)
                        res = future.result(timeout=5)
                    else:
                        res = func.resolver_globo_local(text)
                    if res:
                        self.hablar(res)
                        return
            except Exception as e:
                self.ui.write_log(f"ERR: func.py falló: {e}")

        # ===== 5. DETECTAR IDIOMA =====
        self._detect_language(text)

        # ===== 6. ENVIAR A IA =====
        if not self._loop or not self.session:
            if self.modo_local:
                # El chat local no debe depender del micrófono Vosk ni de
                # pyttsx3: también debe funcionar desde teclado, Linux, macOS
                # y Android/Termux. Ollama se consume mediante HybridRouter.
                try:
                    answer = self.router.route_local(text, self._asst_name)
                    self.ui.write_log(f"{self._asst_name}: {answer}")
                    self.hablar(answer)
                except Exception as exc:
                    self.ui.write_log(f"ERR: Modo local no disponible: {exc}")
            return

        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    # =====================================================================
    # MÉTODOS DEL MENÚ FLOTANTE (AHORA USAN COMMAND_PROCESSOR)
    # =====================================================================
    def _toggle_nemotron_asr(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🎙️ Nemotron ASR toggled (command_processor)")
        if speak:
            speak("Función Nemotron ASR conmutada.")

    def _toggle_vision(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 👁️ Visión toggled (command_processor)")
        if speak:
            speak("Función de visión conmutada.")

    def _toggle_aura_mode(self, params=None, player=None, speak=None):
        self.aura_enabled = not self.aura_enabled
        ui = player or self.ui
        ui.write_log(f"SYS: Modo Aura {'activado' if self.aura_enabled else 'desactivado'}")
        if speak:
            speak(f"Modo Aura {'activado' if self.aura_enabled else 'desactivado'}, señor.")

    def _toggle_clap_detection(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: Detección de aplausos toggle (command_processor)")
        if speak:
            speak("Detección de aplausos conmutada.")

    def _toggle_continuous_listening(self, params=None, player=None, speak=None):
        self.continuous_listening = not self.continuous_listening
        estado = "activada" if self.continuous_listening else "desactivada"
        ui = player or self.ui
        ui.write_log(f"SYS: Escucha continua {estado}")
        if speak:
            speak(f"Escucha continua {estado}, señor.")

    # ===== MÉTODOS CORREGIDOS PARA DIÁLOGOS EN HILO PRINCIPAL =====
    def _select_microphone(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🎤 Abriendo selector de micrófono...")
        if speak:
            speak("Abriendo selector de micrófono, señor.")
        if hasattr(ui, '_win'):
            QTimer.singleShot(0, lambda: self._show_audio_dialog(ui, "input"))

    def _select_speakers(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🔊 Abriendo selector de altavoces...")
        if speak:
            speak("Abriendo selector de altavoces, señor.")
        if hasattr(ui, '_win'):
            QTimer.singleShot(0, lambda: self._show_audio_dialog(ui, "output"))

    def _show_audio_dialog(self, ui, device_type):
        try:
            from src.ui.audio_devices_dialog import AudioDevicesDialog
            import inspect
            sig = inspect.signature(AudioDevicesDialog.__init__)
            if 'device_type' in sig.parameters:
                dialog = AudioDevicesDialog(parent=ui._win, device_type=device_type)
            else:
                dialog = AudioDevicesDialog(parent=ui._win)
            dialog.exec()
        except Exception as e:
            ui.write_log(f"ERR: No se pudo abrir selector de {device_type}: {e}")

    def _toggle_gpu_boost(self, params=None, player=None, speak=None):
        if not hasattr(self, '_gpu_boost_active'):
            self._gpu_boost_active = False
        self._gpu_boost_active = not self._gpu_boost_active
        ui = player or self.ui
        ui.write_log(f"SYS: GPU Boost {'activado' if self._gpu_boost_active else 'desactivado'}")
        if speak:
            speak(f"GPU Boost {'activado' if self._gpu_boost_active else 'desactivado'}, señor.")

    def _toggle_keyboard(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: ⌨️ Teclado visual toggled")
        if IS_WINDOWS:
            try:
                _subprocess.Popen(["osk.exe"], shell=True)
                ui.write_log("SYS: Teclado visual abierto.")
                if speak:
                    speak("Teclado visual abierto, señor.")
            except Exception as e:
                ui.write_log(f"ERR: No se pudo abrir teclado visual: {e}")
        else:
            if speak:
                speak("Teclado visual disponible en la configuración de accesibilidad del sistema.")

    def _toggle_webcam(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 📹 Webcam toggled")
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                cap.release()
                ui.write_log("SYS: Webcam detectada y funcionando.")
                if speak:
                    speak("Webcam detectada y funcionando, señor.")
            else:
                ui.write_log("SYS: No se detectó webcam.")
                if speak:
                    speak("No se detectó ninguna webcam, señor.")
        except:
            ui.write_log("SYS: Webcam no disponible (OpenCV no instalado).")
            if speak:
                speak("Módulo de webcam no disponible, señor.")

    def _toggle_holo_mode(self, params=None, player=None, speak=None):
        if not hasattr(self, '_holo_active'):
            self._holo_active = False
        self._holo_active = not self._holo_active
        ui = player or self.ui
        ui.write_log(f"SYS: Modo holograma {'activado' if self._holo_active else 'desactivado'}")
        if speak:
            speak(f"Modo holograma {'activado' if self._holo_active else 'desactivado'}, señor.")

    def _toggle_shopping_list(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🛒 Lista de compras toggled")
        if speak:
            speak("Abriendo lista de compras, señor.")

    def _iptv_play(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 📺 IPTV toggled")
        try:
            from src.actions.iptv_player import start_video_server
            start_video_server()
            webbrowser.open("http://127.0.0.1:8766")
            ui.write_log("SYS: IPTV abierto en http://127.0.0.1:8766")
            if speak:
                speak("Abriendo reproductor IPTV, señor.")
        except Exception as e:
            ui.write_log(f"ERR: IPTV no disponible: {e}")
            webbrowser.open("https://www.youtube.com")
            ui.write_log("SYS: Abriendo YouTube como alternativa.")
            if speak:
                speak("No pude abrir IPTV, abriendo YouTube.")

    def _toggle_uninstaller(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🗑️ Desinstalador toggled")
        if speak:
            speak("Abriendo desinstalador de programas, señor.")

    def _toggle_antivirus(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🛡️ Antivirus toggled")
        if speak:
            speak("Iniciando escaneo antivirus, señor.")

    def _toggle_realtime_protection(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🛡️ Protección en tiempo real toggled")
        if speak:
            speak("Protección en tiempo real gestionada desde el panel de seguridad.")

    def _vpn_connect(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🔒 VPN toggled")
        if speak:
            speak("Abriendo cliente VPN, señor.")

    def _toggle_smart_home(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🏠 Domótica toggled")
        if speak:
            speak("Abriendo panel de domótica, señor.")

    def _toggle_commands_list(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 📋 Lista de comandos toggled")
        if speak:
            speak("Mostrando lista de comandos en la interfaz, señor.")

    def _open_api_config(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🔑 Abriendo configuración de APIs")
        if hasattr(ui, '_win') and hasattr(ui._win, '_open_customize'):
            ui._win._open_customize()
        elif hasattr(ui, '_open_customize'):
            ui._open_customize()
        else:
            self._show_simple_dialog("🔑 Configuración de APIs", 
                "Abre la ventana de personalización (Customize) para configurar las APIs.\n"
                "También puedes editar el archivo src/config/api_keys.json directamente.")
        if speak:
            speak("Abriendo configuración de APIs, señor.")

    def _open_agent_model(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🤖 Abriendo selector de modelos")
        try:
            from src.core.agent_model_manager import open_model_selector
            open_model_selector()
        except Exception as e:
            ui.write_log(f"ERR: Selector de modelos no disponible: {e}")
            self._show_agent_models_dialog()
        if speak:
            speak("Abriendo selector de modelos de IA, señor.")

    def _open_agent_tone(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🎭 Abriendo selector de tono")
        if hasattr(ui, '_win') and hasattr(ui._win, '_open_customize'):
            ui._win._open_customize()
        elif hasattr(ui, '_open_customize'):
            ui._open_customize()
        else:
            self._show_simple_dialog("🎭 Selector de Tono", 
                "Abre la ventana de personalización para seleccionar el tono y la personalidad.\n"
                "Puedes elegir entre: Jarvis, Agata, Tony, Friday, Apolo.")
        if speak:
            speak("Abriendo selector de tono y personalidad, señor.")

    def _clear_cache(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🔄 Limpiando caché")
        try:
            import shutil
            cache_dirs = [
                Path.home() / ".cache" / "AP0L0",
                Path.home() / "AppData" / "Local" / "AP0L0" / "cache",
                Path.home() / "cache" / "AP0L0",
            ]
            for d in cache_dirs:
                if d.exists():
                    shutil.rmtree(d)
                    ui.write_log(f"SYS: Eliminado {d}")
            ui.write_log("SYS: Caché limpiada correctamente.")
            if speak:
                speak("Caché limpiada correctamente, señor.")
        except Exception as e:
            ui.write_log(f"ERR: Error limpiando caché: {e}")
            if speak:
                speak("No se pudo limpiar la caché, señor.")

    def _launch_jarvis_os(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🐧 Iniciando JARVIS OS")
        try:
            jarvis_os = Path(__file__).resolve().parent.parent / "jarvis_os" / "main.py"
            if jarvis_os.exists():
                _subprocess.Popen([sys.executable, str(jarvis_os)])
                ui.write_log("SYS: JARVIS OS iniciado.")
                if speak:
                    speak("JARVIS OS iniciado, señor.")
            else:
                ui.write_log("SYS: JARVIS OS no encontrado.")
                self._show_simple_dialog("🐧 JARVIS OS", 
                    "JARVIS OS no se encuentra en el sistema.\n"
                    "Asegúrate de que el directorio 'jarvis_os' existe en la raíz del proyecto.")
                if speak:
                    speak("JARVIS OS no encontrado, señor.")
        except Exception as e:
            ui.write_log(f"ERR: Error iniciando JARVIS OS: {e}")
            if speak:
                speak("Error al iniciar JARVIS OS, señor.")

    def _launch_secure_browser(self, params=None, player=None, speak=None):
        ui = player or self.ui
        url = params.get("url", "https://www.google.com") if params else "https://www.google.com"
        try:
            webbrowser.open(url)
            ui.write_log("SYS: Navegador seguro abierto.")
            if speak:
                speak("Navegador seguro abierto, señor.")
        except Exception as e:
            ui.write_log(f"SYS: Error abriendo navegador: {e}")
            if speak:
                speak("No pude abrir el navegador, señor.")

    def _secure_browser(self, params=None, player=None, speak=None):
        self._launch_secure_browser(params, player, speak)

    def _generate_report(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 📊 Generando informe")
        try:
            import psutil
            import datetime
            import platform
            report = "=== INFORME AP0L0 ===\n\n"
            report += f"Fecha: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            report += f"Sistema: {platform.system()} {platform.release()}\n"
            report += f"CPU: {psutil.cpu_percent(interval=0.5)}%\n"
            report += f"RAM: {psutil.virtual_memory().percent}% ({psutil.virtual_memory().used / (1024**3):.1f} GB / {psutil.virtual_memory().total / (1024**3):.1f} GB)\n"
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    report += f"Disco {part.device}: {usage.percent}% ({usage.free / (1024**3):.1f} GB libres)\n"
                except:
                    pass
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        if entries:
                            report += f"Temperatura {name}: {entries[0].current:.1f}°C\n"
                            break
            except:
                pass
            report += f"\nProcesos activos: {len(psutil.pids())}"
            if hasattr(ui, 'show_content'):
                ui.show_content("📊 INFORME DEL SISTEMA", report)
            else:
                ui.write_log(report)
            ui.write_log("SYS: Informe generado.")
            if speak:
                speak("Informe generado, señor. Revise el panel de contenido.")
        except Exception as e:
            ui.write_log(f"ERR: Error generando informe: {e}")
            if speak:
                speak("No pude generar el informe, señor.")

    def _build_project(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 📦 Constructor de proyectos")
        try:
            from src.ui.developer_gui import DeveloperGUI
            dev_gui = DeveloperGUI()
            dev_gui.show()
            ui.write_log("SYS: Constructor de proyectos abierto.")
            if speak:
                speak("Abriendo constructor de proyectos, señor.")
        except Exception as e:
            ui.write_log(f"ERR: Constructor de proyectos no disponible: {e}")
            self._show_simple_dialog("📦 Constructor de Proyectos", 
                "Función en desarrollo.\n"
                "Usa el comando 'build_project description=...' para crear proyectos desde el chat.")
            if speak:
                speak("No pude abrir el constructor de proyectos, señor.")

    def _file_manager(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 📁 Gestor de archivos")
        try:
            if IS_WINDOWS:
                _subprocess.Popen(["explorer.exe"])
            elif IS_LINUX:
                _subprocess.Popen(["nautilus", "."] if shutil.which("nautilus") else ["xdg-open", "."])
            elif IS_MAC:
                _subprocess.Popen(["open", "."])
            ui.write_log("SYS: Gestor de archivos abierto.")
            if speak:
                speak("Abriendo gestor de archivos, señor.")
        except Exception as e:
            ui.write_log(f"ERR: Error abriendo gestor de archivos: {e}")
            if speak:
                speak("No pude abrir el gestor de archivos, señor.")

    def _create_music(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🎵 Creando música")
        try:
            from src.actions.jarvis_music import jarvis_music
            if asyncio.iscoroutinefunction(jarvis_music):
                if self._loop and self._loop.is_running():
                    asyncio.create_task(jarvis_music(params or {}, player=ui, speak=speak))
                else:
                    asyncio.run(jarvis_music(params or {}, player=ui, speak=speak))
            else:
                result = jarvis_music(params or {}, player=ui, speak=speak)
                ui.write_log(f"Music: {result}")
        except Exception as e:
            ui.write_log(f"ERR: Compositor musical no disponible: {e}")
        if speak:
            speak("Abriendo compositor musical, señor.")

    def _home_assistant(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🏠 Home Assistant")
        try:
            from src.actions.ha_config import HA_URL
            if HA_URL:
                webbrowser.open(HA_URL)
                ui.write_log(f"SYS: Abriendo Home Assistant en {HA_URL}")
                if speak:
                    speak("Abriendo panel de Home Assistant, señor.")
            else:
                ui.write_log("SYS: Home Assistant no configurado.")
                self._show_simple_dialog("🏠 Home Assistant", 
                    "Home Assistant no está configurado.\n"
                    "Configura HA_URL en src/actions/ha_config.py")
                if speak:
                    speak("Home Assistant no está configurado, señor.")
        except Exception as e:
            ui.write_log(f"ERR: Home Assistant no disponible: {e}")
            if speak:
                speak("Abriendo panel de Home Assistant, señor.")

    def _google_docs(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 📄 Google Docs")
        webbrowser.open("https://docs.google.com")
        if speak:
            speak("Abriendo Google Docs, señor.")

    def _youtube_advanced(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🎬 YouTube avanzado")
        webbrowser.open("https://www.youtube.com")
        if speak:
            speak("Abriendo YouTube avanzado, señor.")

    def _mode_work(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 💼 Modo trabajo")
        try:
            from src.actions.app_launcher import modo_boulot
            apps = params.get("apps", ["vscode", "chrome", "terminal"]) if params else None
            result = modo_boulot(apps)
            ui.write_log(f"Work mode: {result}")
            if speak:
                speak("Activando modo trabajo, señor.")
        except Exception as e:
            ui.write_log(f"ERR: Modo trabajo no disponible: {e}")
            for app in ["code", "chrome", "cmd"]:
                try:
                    _subprocess.Popen([app], shell=True)
                except:
                    pass
            ui.write_log("SYS: Aplicaciones de trabajo lanzadas (fallback).")
            if speak:
                speak("Activando modo trabajo, señor.")

    def _toggle_winget_updater(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🚀 Actualizador winget toggled")
        if IS_WINDOWS:
            try:
                result = _subprocess.run(["winget", "--version"], capture_output=True, text=True)
                if result.returncode == 0:
                    _subprocess.Popen(["start", "winget", "upgrade", "--all"], shell=True)
                    ui.write_log("SYS: Actualizador winget iniciado.")
                    if speak:
                        speak("Iniciando actualización de software con winget, señor.")
                else:
                    ui.write_log("SYS: winget no está disponible en este sistema.")
                    if speak:
                        speak("winget no está disponible en este sistema, señor.")
            except Exception as e:
                ui.write_log(f"ERR: Winget no disponible: {e}")
                if speak:
                    speak("No se pudo iniciar el actualizador winget, señor.")
        else:
            ui.write_log("SYS: winget solo está disponible en Windows.")
            if speak:
                speak("Actualizador winget solo disponible en Windows, señor.")

    def _list_plugins(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 📋 Listando plugins")
        try:
            from src.core.plugin_system import PluginSystem
            ps = PluginSystem()
            plugins = ps.load_plugins()
            if plugins:
                msg = "Plugins cargados:\n" + "\n".join(f"  • {name}" for name in plugins.keys())
            else:
                msg = "No hay plugins cargados."
            if hasattr(ui, 'show_content'):
                ui.show_content("🧩 PLUGINS", msg)
            else:
                ui.write_log(msg)
            if speak:
                speak("Listando plugins en la interfaz, señor.")
        except Exception as e:
            ui.write_log(f"ERR: No se pudieron listar plugins: {e}")
            if speak:
                speak("No pude listar los plugins, señor.")

    def _reload_plugins(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🔄 Recargando plugins")
        try:
            from src.core.plugin_system import PluginSystem
            ps = PluginSystem()
            ps.load_plugins()
            ui.write_log("SYS: Plugins recargados correctamente.")
            if speak:
                speak("Plugins recargados, señor.")
        except Exception as e:
            ui.write_log(f"ERR: No se pudieron recargar plugins: {e}")
            if speak:
                speak("No pude recargar los plugins, señor.")

    def _toggle_plugin(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🔌 Gestionando plugin")
        try:
            from src.core.plugin_manager import get_plugin_manager
            pm = get_plugin_manager()
            plugins = pm.list_plugins()
            msg = "Gestión de plugins:\n" + "\n".join(f"  • {p['name']} ({'activado' if p['enabled'] else 'desactivado'})" for p in plugins)
            if hasattr(ui, 'show_content'):
                ui.show_content("🔌 GESTIÓN DE PLUGINS", msg)
            else:
                ui.write_log(msg)
            if speak:
                speak("Abriendo gestión de plugins, señor.")
        except Exception as e:
            ui.write_log(f"ERR: Gestión de plugins no disponible: {e}")
            if speak:
                speak("No pude gestionar los plugins, señor.")

    def _app_launcher(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 📱 Lanzador de aplicaciones")
        try:
            from src.actions.app_launcher import listar_apps, lanzar_app
            apps = listar_apps()
            apps_text = "Aplicaciones disponibles:\n" + "\n".join(f"  • {a}" for a in apps[:30])
            if hasattr(ui, 'show_content'):
                ui.show_content("📱 LANZADOR DE APLICACIONES", apps_text)
            else:
                ui.write_log(apps_text)
            if speak:
                speak("Abriendo lanzador de aplicaciones, señor.")
        except Exception as e:
            ui.write_log(f"ERR: Lanzador de aplicaciones no disponible: {e}")
            if speak:
                speak("No pude abrir el lanzador de aplicaciones, señor.")

    def _android_connect(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 📱 Android toggled")
        try:
            from src.livekit.android_bridge import AndroidBridge
            bridge = AndroidBridge()
            if hasattr(bridge, 'connect'):
                bridge.connect()
                ui.write_log("SYS: Android conectado.")
                if speak:
                    speak("Conectando con Android...")
            else:
                ui.write_log("SYS: Android Bridge no tiene método connect.")
                if speak:
                    speak("Conectando con Android... (función no implementada)")
        except Exception as e:
            ui.write_log(f"ERR: Android no disponible: {e}")
            if speak:
                speak("No pude conectar con Android, señor.")

    def _clipboard_proactive(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 📋 Portapapeles proactivo activado")
        try:
            from src.actions.clipboard_intelligence import start_clipboard_monitoring
            start_clipboard_monitoring()
            ui.write_log("SYS: Portapapeles proactivo activado.")
            if speak:
                speak("Portapapeles proactivo activado.")
        except Exception as e:
            ui.write_log(f"ERR: Clipboard proactivo no disponible: {e}")
            if speak:
                speak("No pude activar el portapapeles proactivo, señor.")

    def _manage_contacts(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 👤 Gestión de contactos")
        try:
            from src.actions.contact_manager import open_contact_manager
            open_contact_manager()
            if speak:
                speak("Abriendo gestión de contactos.")
        except Exception as e:
            ui.write_log(f"ERR: Contactos no disponible: {e}")
            self._show_simple_dialog("👤 Contactos", 
                "Gestión de contactos en desarrollo.\n"
                "Puedes usar el comando 'manage_contacts list' en el chat.")
            if speak:
                speak("No pude abrir la gestión de contactos, señor.")

    def _create_quick_note(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 📝 Crear nota rápida")
        try:
            from src.actions.quick_note import create_quick_note
            create_quick_note()
            if speak:
                speak("Creando nota rápida...")
        except Exception as e:
            ui.write_log(f"ERR: Nota rápida no disponible: {e}")
            self._show_simple_dialog("📝 Nota Rápida", 
                "Función de nota rápida en desarrollo.\n"
                "Puedes usar el comando 'create_note title=... content=...' en el chat.")
            if speak:
                speak("No pude crear la nota rápida, señor.")

    def _open_contacts(self, params=None, player=None, speak=None):
        self._manage_contacts(params, player, speak)

    def _show_cpu_temperature(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 🌡️ Mostrando temperatura CPU")
        try:
            import psutil
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        temp = entries[0].current
                        ui.write_log(f"🌡️ Temperatura CPU ({name}): {temp:.1f}°C")
                        if speak:
                            speak(f"La temperatura de la CPU es de {temp:.1f} grados Celsius, señor.")
                        return
            ui.write_log("🌡️ No se pudo obtener la temperatura de la CPU.")
            if speak:
                speak("No pude obtener la temperatura de la CPU, señor.")
        except Exception as e:
            ui.write_log(f"🌡️ Error al obtener temperatura: {e}")
            if speak:
                speak("Ocurrió un error al leer la temperatura de la CPU.")

    def _open_performance_monitor(self, params=None, player=None, speak=None):
        ui = player or self.ui
        ui.write_log("SYS: 💻 Abriendo monitor de rendimiento")
        try:
            if IS_WINDOWS:
                _subprocess.Popen(["taskmgr"])
                ui.write_log("SYS: Administrador de tareas abierto.")
                if speak:
                    speak("Monitor de rendimiento abierto, señor.")
            elif IS_LINUX:
                _subprocess.Popen(["gnome-system-monitor"])
                ui.write_log("SYS: Monitor de sistema abierto.")
                if speak:
                    speak("Monitor de sistema abierto, señor.")
            elif IS_MAC:
                _subprocess.Popen(["open", "-a", "Activity Monitor"])
                ui.write_log("SYS: Activity Monitor abierto.")
                if speak:
                    speak("Activity Monitor abierto, señor.")
        except Exception as e:
            ui.write_log(f"ERR: Error abriendo monitor: {e}")
            if speak:
                speak("No pude abrir el monitor de rendimiento, señor.")

    # ===== MÉTODOS AUXILIARES PARA DIÁLOGOS =====
    def _show_simple_dialog(self, title, message):
        try:
            if hasattr(self.ui, '_win'):
                dialog = QDialog(self.ui._win)
                dialog.setWindowTitle(title)
                dialog.setMinimumSize(400, 200)
                layout = QVBoxLayout(dialog)
                label = QLabel(message)
                label.setWordWrap(True)
                layout.addWidget(label)
                btn = QPushButton("Aceptar")
                btn.clicked.connect(dialog.accept)
                layout.addWidget(btn)
                dialog.exec()
            else:
                self.ui.write_log(f"[Dialog] {title}: {message}")
        except Exception as e:
            self.ui.write_log(f"ERR: No se pudo mostrar diálogo: {e}")

    def _show_agent_models_dialog(self):
        try:
            if hasattr(self.ui, '_win'):
                dialog = QDialog(self.ui._win)
                dialog.setWindowTitle("🤖 Selector de Modelos")
                dialog.setMinimumSize(450, 300)
                layout = QVBoxLayout(dialog)
                label = QLabel("Modelos disponibles:\n\n• Gemini (Cloud)\n• OpenRouter (Cloud)\n• Ollama (Local)\n• Groq (Cloud)\n\nConfigura los modelos en src/config/api_keys.json")
                label.setWordWrap(True)
                layout.addWidget(label)
                btn = QPushButton("Aceptar")
                btn.clicked.connect(dialog.accept)
                layout.addWidget(btn)
                dialog.exec()
            else:
                self.ui.write_log("[Models] Selecciona modelos en src/config/api_keys.json")
        except Exception as e:
            self.ui.write_log(f"ERR: No se pudo mostrar selector de modelos: {e}")

    # =====================================================================
    # MÉTODOS DE AUDIO Y CONEXIÓN
    # =====================================================================
    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def interrupt(self):
        self._interrupted = True
        q = self.audio_in_queue
        if q:
            drained = 0
            while True:
                try:
                    q.get_nowait()
                    drained += 1
                except Exception:
                    break
            if drained:
                print(f"[{self._asst_name}] ✋ Interrupted — {drained} chunks discarded")
        self.set_speaking(False)
        if self._turn_done_event:
            self._turn_done_event.clear()
        self.ui.write_log("SYS: Interrupted — listening...")

    def hablar(self, text: str):
        if not self._loop or not self.session:
            if self.modo_local and self.asistente_local:
                self.asistente_local.hablar(text)
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def hablar_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.hablar(f"Señor, {tool_name} encontró un error. {short}")

    def _detect_language(self, text: str):
        if not text or self._user_language_detected:
            return
        try:
            from langdetect import detect
            lang = detect(text)
            if lang in ['es', 'en', 'fr', 'de', 'it', 'pt']:
                self._user_language = lang
                self._user_language_detected = True
                save_user_language(lang)
                self.ui.write_log(f"SYS: Idioma detectado: {lang}")
        except:
            pass

    def _build_config(self, personality: str = None):
        _cfg = _get_config()
        if personality is None:
            personality = getattr(self, 'current_personality', 'jarvis')
        else:
            self.current_personality = personality

        personality_names = {
            "jarvis": "JARVIS", "agata": "AGATA", "tony": "TONY", "friday": "FRIDAY", "apolo": "APOLO",
        }
        personality_subtitles = {
            "jarvis": "Just A Rather Very Intelligent System",
            "agata": "Advanced Generative Assistant for Technology & Art",
            "tony": "Technology Oriented Network Yield",
            "friday": "Female Replacement Intelligent Digital Assistant Youth",
            "apolo": "Autonomous Platform for Orchestration, Learning and Operations",
        }
        custom_name = _cfg.get("assistant_name", "").strip()
        custom_subtitle = _cfg.get("assistant_subtitle", "").strip()
        self._asst_name = custom_name if custom_name else personality_names.get(personality, "APOLO")
        self._asst_subtitle = custom_subtitle if custom_subtitle else personality_subtitles.get(personality, "Autonomous Platform for Orchestration, Learning and Operations")

        _user_name = (_cfg.get("user_name") or "").strip()
        sys_prompt = _load_system_prompt(self._asst_name, self._asst_subtitle)

        if _PERSONALITY_AVAILABLE and self.personality_prompts:
            personality_prompt = self.personality_prompts.get(personality)
            if personality_prompt:
                personality_prompt = personality_prompt.replace("{assistant_name}", self._asst_name)
                personality_prompt = personality_prompt.replace("{assistant_subtitle}", self._asst_subtitle)
                sys_prompt = personality_prompt

        voice_name = VOICE_MAP.get(personality, DEFAULT_VOICE)
        self._reconnect_voice = voice_name

        memory = load_memory()
        mem_str = format_memory_for_prompt(memory)

        now = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = f"[CURRENT DATE & TIME]\nRight now it is: {time_str}\n\n"

        _addr = (f"ADDRESS: Always call the user '{_user_name}'."
                 if _user_name
                 else "ADDRESS: When speaking Turkish → say 'efendim'. When English → say 'sir'.")
        identity_ctx = (
            f"[IDENTITY]\nYour name is {self._asst_name}.\n"
            f"Always refer to yourself as {self._asst_name}.\n{_addr}\n\n"
        )

        lang_ctx = f"LANGUAGE: Always respond in {self._user_language or 'Spanish'}."

        parts = [time_ctx, identity_ctx, lang_ctx]
        if mem_str:
            parts.append(mem_str)
        parts.append(sys_prompt)

        aura_prompt = self._get_aura_prompt()
        if aura_prompt:
            parts.append(aura_prompt)

        session_config = types.SessionResumptionConfig()
        if self._session_resumption_handle:
            try:
                session_config.handle = self._session_resumption_handle
            except Exception:
                pass

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=session_config,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name
                    )
                )
            ),
        )

    def _get_aura_prompt(self):
        try:
            from src.actions.aura_mode import get_aura_prompt
            return get_aura_prompt()
        except:
            return ""

    def _close_boot_screen(self):
        try:
            if self.boot_screen and self.boot_screen.isVisible():
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._close_boot_screen_impl())
                print("[MAIN] ✅ Cerrando boot screen...")
        except Exception:
            pass

    def _close_boot_screen_impl(self):
        try:
            if self.boot_screen:
                self.boot_screen.boot_closed.emit()
                self.boot_screen.close()
                print("[MAIN] ✅ Boot screen cerrada correctamente")
        except Exception:
            pass

    # =====================================================================
    # EJECUCIÓN DE HERRAMIENTAS (TOOL EXECUTION) - CON HANDLERS CORREGIDOS
    # =====================================================================
    async def _execute_tool(self, fc):
        name = fc.name
        args = dict(fc.args or {})

        print(f"[{self._asst_name}] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")

        handlers = {
            "open_app": app_launcher,
            "app_launcher": app_launcher,
            "mode_work": app_launcher,
            "file_manager": file_manager,
            "build_project": project_builder,
            "secure_browser": self._launch_secure_browser,
            "launch_secure_browser": self._launch_secure_browser,
            "spotify_control": spotify_control,
            "deezer_control": deezer_control,
            "create_music": jarvis_music,
            "jarvis_music": jarvis_music,
            "jarvis_rap": jarvis_rap,
            "antivirus_scan": lambda args, player=None, speak=None: (antivirus_scan(args, player=player, speak=speak) if speak else antivirus_scan(args, player=player, speak=lambda x: None)),
            "toggle_antivirus": lambda args, player=None, speak=None: (antivirus_scan(args, player=player, speak=speak) if speak else antivirus_scan(args, player=player, speak=lambda x: None)),
            "vpn_connect": vpn_control,
            "vpn_control": vpn_control,
            "iptv_play": iptv_play,
            "google_services": google_services,
            "google_docs": google_services,
            "google_doc_create": google_services,
            "google_doc_append": google_services,
            "google_sheet_create": google_services,
            "gmail_read": google_services,
            "calendar_read": google_services,
            "home_assistant": ha_control,
            "ha_light": ha_control,
            "ha_switch": ha_control,
            "ha_temperature": ha_control,
            "ha_humidity": ha_control,
            "ha_battery": ha_control,
            "ha_thermostat": ha_control,
            "ha_scene": ha_control,
            "ha_alarm": ha_control,
            "ha_lock": ha_control,
            "ha_energy": ha_control,
            "ha_vacuum": ha_control,
            "ha_anniversaries": ha_control,
            "ha_power_consumption": ha_control,
            "ha_tiktok": ha_control,
            "ha_eggs": ha_control,
            "ha_simulation": ha_control,
            "obsidian_create_note": obsidian_control,
            "obsidian_read_note": obsidian_control,
            "obsidian_search": obsidian_control,
            "obsidian_list": obsidian_control,
            "memory_store": memory_operations,
            "memory_forget": memory_operations,
            "memory_list": memory_operations,
            "save_memory": memory_operations,
            "jarvis_agent": jarvis_agent,
            "local_ai_chat": local_agent,
            "ollama_uncensored": local_agent,
            "nemotron_asr": nemotron_asr,
            "toggle_nemotron_asr": nemotron_asr,
            "restaurant_search": restaurant_search,
            "sports_results": sports_web,
            "sports_standings": sports_web,
            "sports_live": sports_web,
            "youtube_advanced": youtube_advanced,
            "uninstaller": uninstaller,
            "toggle_uninstaller": uninstaller,
            "vision_click": vision_click,
            "vision_type": vision_type,
            "vision_search_on_site": vision_search_on_site,
            "vision_camera": vision_camera,
            "vision_browser": vision_browser,
            "show_recipe": self._show_recipe,
            "generate_report": self._generate_report,
            "switch_personality": self._force_switch_personality,
            "clear_cache": self._clear_cache,
            "toggle_aura_mode": self._toggle_aura_mode,
            "toggle_continuous_listening": self._toggle_continuous_listening,
            "toggle_clap_detection": self._toggle_clap_detection,
            "toggle_gpu_boost": self._toggle_gpu_boost,
            "toggle_keyboard": self._toggle_keyboard,
            "toggle_webcam": self._toggle_webcam,
            "toggle_holo_mode": self._toggle_holo_mode,
            "toggle_shopping_list": self._toggle_shopping_list,
            "toggle_smart_home": self._toggle_smart_home,
            "toggle_commands_list": self._toggle_commands_list,
            "open_api_config": self._open_api_config,
            "open_agent_model": self._open_agent_model,
            "open_agent_tone": self._open_agent_tone,
            "launch_jarvis_os": self._launch_jarvis_os,
            "open_performance_monitor": self._open_performance_monitor,
            "show_cpu_temperature": self._show_cpu_temperature,
            "select_microphone": self._select_microphone,
            "select_speakers": self._select_speakers,
            "generate_image": self._generate_image,
            "generar_imagen": self._generate_image,
            "generar_video": self._generate_video,
            "generar_sitio": self._generate_site,
            "serpapi_search": self._serpapi_search,
            "competence_create": self._competence_create,
            "competence_run": self._competence_run,
            "competence_delete": self._competence_delete,
            "whatsapp_call": self._whatsapp_call,
            "dictate": self._dictate,
            "iron_man_mode": self._iron_man_mode,
        }

        handler = handlers.get(name)
        if handler is None:
            result = f"Herramienta '{name}' no implementada."
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": result}
            )

        speak_func = self.hablar if self.hablar else lambda x: None

        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(args, player=self.ui, speak=speak_func)
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, handler, args, self.ui, speak_func)

            if not isinstance(result, str):
                result = str(result)
            result = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', result)
            if len(result) > 500:
                result = result[:497] + "..."

        except ReconnectException:
            raise
        except Exception as e:
            result = f"Error ejecutando {name}: {str(e)}"
            self.ui.write_log(f"[ERROR] {name} → {e}")
            traceback.print_exc()

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[{self._asst_name}] 📤 {name} → {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    # ===== STUBS PARA FUNCIONES ASÍNCRONAS =====
    async def _generate_image(self, params, player=None, speak=None):
        prompt = params.get("prompt", "")
        if not prompt:
            return "Falta el prompt para generar la imagen."
        return f"Generando imagen con prompt: {prompt[:50]}... (función en desarrollo)"

    async def _generate_video(self, params, player=None, speak=None):
        prompt = params.get("prompt", "")
        if not prompt:
            return "Falta el prompt para generar el video."
        return f"Generando video con prompt: {prompt[:50]}... (función en desarrollo)"

    async def _generate_site(self, params, player=None, speak=None):
        prompt = params.get("prompt", "")
        model = params.get("model", "gemini")
        if not prompt:
            return "Falta la descripción del sitio web."
        return f"Generando sitio web con {model}: {prompt[:50]}... (función en desarrollo)"

    async def _serpapi_search(self, params, player=None, speak=None):
        query = params.get("query", "")
        if not query:
            return "Falta la consulta de búsqueda."
        return f"Buscando en SerpAPI: {query} (función en desarrollo)"

    async def _competence_create(self, params, player=None, speak=None):
        nom = params.get("nom", "")
        desc = params.get("descripcion", "")
        if not nom or not desc:
            return "Faltan nombre o descripción de la competencia."
        return f"Competencia '{nom}' creada (función en desarrollo)"

    async def _competence_run(self, params, player=None, speak=None):
        nom = params.get("nom", "")
        param = params.get("param", "")
        if not nom:
            return "Falta el nombre de la competencia."
        return f"Ejecutando competencia '{nom}' con parámetro '{param}' (función en desarrollo)"

    async def _competence_delete(self, params, player=None, speak=None):
        nom = params.get("nom", "")
        if not nom:
            return "Falta el nombre de la competencia."
        return f"Competencia '{nom}' eliminada (función en desarrollo)"

    async def _whatsapp_call(self, params, player=None, speak=None):
        contact = params.get("contact", "")
        if not contact:
            return "Falta el contacto."
        return f"Llamando a {contact} por WhatsApp (función en desarrollo)"

    async def _dictate(self, params, player=None, speak=None):
        texte = params.get("texte", "")
        if not texte:
            return "Falta el texto a dictar."
        return f"Texto dictado: {texte[:30]}... (función en desarrollo)"

    def _iron_man_mode(self, params, player=None, speak=None):
        etat = params.get("etat", "on")
        self._iron_man_active = (etat == "on")
        estado = "activado" if self._iron_man_active else "desactivado"
        ui = player or self.ui
        ui.write_log(f"SYS: Modo Iron Man {estado}")
        if speak:
            speak(f"Modo Iron Man {estado}, señor.")
        return f"Modo Iron Man {estado}"

    def _show_recipe(self, params, player=None, speak=None):
        titre = params.get("titre", "Receta")
        ingredients = params.get("ingredients", [])
        instructions = params.get("instructions", [])
        ui = player or self.ui
        if hasattr(ui, 'show_content'):
            ui.show_content(f"📖 {titre}",
                "Ingredientes:\n- " + "\n- ".join(ingredients) + "\n\nInstrucciones:\n" + "\n".join(f"{i+1}. {inst}" for i, inst in enumerate(instructions))
            )
        return f"Receta '{titre}' mostrada en la interfaz."

    # =====================================================================
    # LOOPS DE AUDIO
    # =====================================================================
    async def _send_realtime(self):
        while True:
            try:
                if self._reconnect_event.is_set():
                    print(f"[{self._asst_name}] _send_realtime: evento de reconexión detectado, saliendo.")
                    break
                if self.session is None:
                    await asyncio.sleep(0.1)
                    continue
                msg = await self.out_queue.get()
                if msg is None:
                    print(f"[{self._asst_name}] Centinela en send, saliendo.")
                    break
                await self.session.send_realtime_input(media=msg)
            except asyncio.CancelledError:
                break
            except (AttributeError, RuntimeError, websockets.ConnectionClosed, websockets.ConnectionClosedOK):
                await asyncio.sleep(0.1)
                continue
            except Exception as e:
                print(f"[{self._asst_name}] _send_realtime error: {e}")
                await asyncio.sleep(0.1)
                continue

    async def _listen_audio(self):
        print(f"[{self._asst_name}] 🎤 Mic started")
        loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            if self._reconnect_event.is_set():
                return
            with self._speaking_lock:
                jarvis_speaking = self._is_speaking
            if self.continuous_listening or (not jarvis_speaking and not self.ui.muted and not self._phone_active):
                data = indata.tobytes()
                def safe_put():
                    try:
                        self.out_queue.put_nowait({"data": data, "mime_type": "audio/pcm"})
                    except asyncio.QueueFull:
                        pass
                loop.call_soon_threadsafe(safe_put)

        try:
            with sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                callback=callback,
            ):
                print(f"[{self._asst_name}] 🎤 Mic stream open")
                while True:
                    if self._reconnect_event.is_set():
                        print(f"[{self._asst_name}] _listen_audio: evento de reconexión, saliendo.")
                        break
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[{self._asst_name}] ❌ Mic: {e}")
        finally:
            print(f"[{self._asst_name}] 🎤 Mic stream cerrado.")

    async def _receive_audio(self):
        print(f"[{self._asst_name}] 👂 Recv started")
        out_buf, in_buf = [], []

        try:
            while True:
                if self._reconnect_event.is_set():
                    print(f"[{self._asst_name}] _receive_audio: evento de reconexión, saliendo.")
                    break

                if self.session is None:
                    await asyncio.sleep(0.1)
                    continue

                try:
                    async for response in self.session.receive():
                        if self._reconnect_event.is_set():
                            print(f"[{self._asst_name}] _receive_audio: evento de reconexión durante recepción, saliendo.")
                            return

                        if response.data:
                            if self._interrupted:
                                pass
                            else:
                                if self._turn_done_event and self._turn_done_event.is_set():
                                    self._turn_done_event.clear()
                                _SLICE = 2400
                                for _i in range(0, len(response.data), _SLICE):
                                    self.audio_in_queue.put_nowait(response.data[_i : _i + _SLICE])

                        if response.server_content:
                            sc = response.server_content
                            if sc.output_transcription and sc.output_transcription.text:
                                txt = _clean_transcript(sc.output_transcription.text)
                                if txt and txt != (out_buf[-1] if out_buf else ""):
                                    out_buf.append(txt)

                            if sc.input_transcription and sc.input_transcription.text:
                                txt = _clean_transcript(sc.input_transcription.text)
                                if txt:
                                    self._detect_language(txt)
                                    in_buf.append(txt)
                                    self._last_user_speech = time.monotonic()

                            if sc.turn_complete:
                                if self._turn_done_event:
                                    self._turn_done_event.set()

                                if self._interrupted:
                                    self._interrupted = False
                                    in_buf = []
                                    out_buf = []
                                    continue

                                full_in = " ".join(in_buf).strip()
                                if full_in:
                                    self.ui.write_log(f"Tú: {full_in}")
                                    self._session_log.append(f"Usuario: {full_in}")
                                    if self._dashboard:
                                        asyncio.create_task(self._dashboard.broadcast({
                                            "type": "log", "speaker": "user",
                                            "text": full_in,
                                            "ts": datetime.now().isoformat(),
                                        }))
                                in_buf = []

                                full_out = " ".join(out_buf).strip()
                                if full_out:
                                    self.ui.write_log(f"{self._asst_name}: {full_out}")
                                    self._session_log.append(f"{self._asst_name}: {full_out}")
                                    if self._dashboard:
                                        asyncio.create_task(self._dashboard.broadcast({
                                            "type": "log", "speaker": "jarvis",
                                            "text": full_out,
                                            "ts": datetime.now().isoformat(),
                                        }))
                                    if self.panel:
                                        try:
                                            if hasattr(self.panel, 'show_message'):
                                                QMetaObject.invokeMethod(
                                                    self.panel,
                                                    "show_message",
                                                    Qt.ConnectionType.QueuedConnection,
                                                    Q_ARG(str, full_out),
                                                    Q_ARG(str, self._asst_name)
                                                )
                                            else:
                                                self.ui.show_content(self._asst_name, full_out)
                                        except Exception:
                                            self.ui.show_content(self._asst_name, full_out)

                                out_buf = []

                                if self._pending_vision and self.session:
                                    import base64 as _b64
                                    img_b, mime_t, question, angle = self._pending_vision
                                    self._pending_vision = None
                                    b64 = _b64.b64encode(img_b).decode("ascii")
                                    print(f"[Visión] 📤 {len(img_b):,} bytes → sesión principal")
                                    await self.session.send_client_content(
                                        turns={"parts": [
                                            {"inline_data": {"mime_type": mime_t, "data": b64}},
                                            {"text": question},
                                        ]},
                                        turn_complete=True,
                                    )
                                    if self._vision_cam_active:
                                        self._vision_cam_active = False
                                        self._vision_close_pending = True
                                    else:
                                        self._vision_busy = False
                                elif self._vision_close_pending:
                                    self._vision_close_pending = False
                                    self._vision_busy = False
                                    async def _cam_close():
                                        await asyncio.sleep(2.0)
                                        self.ui.stop_camera_stream()
                                    asyncio.create_task(_cam_close())

                        if response.tool_call:
                            fn_responses = []
                            for fc in response.tool_call.function_calls:
                                print(f"[{self._asst_name}] 📞 {fc.name}")
                                try:
                                    fr = await self._execute_tool(fc)
                                    fn_responses.append(fr)
                                except ReconnectException:
                                    print(f"[{self._asst_name}] 🔄 Reconexión solicitada desde herramienta.")
                                    raise
                            if self.session is not None:
                                await self.session.send_tool_response(
                                    function_responses=fn_responses
                                )
                except asyncio.CancelledError:
                    print(f"[{self._asst_name}] _receive_audio cancelado, saliendo.")
                    break
                except (websockets.ConnectionClosed, websockets.ConnectionClosedOK,
                        asyncio.CancelledError, ConnectionResetError, RuntimeError) as e:
                    print(f"[{self._asst_name}] _receive_audio: cierre normal de sesión ({type(e).__name__}).")
                    self._reconnect_event.set()
                    self._pending_reconnect = True
                    self.session = None
                    raise
                except APIError as e:
                    status_code = getattr(e, 'status_code', 0)
                    if status_code in (1000, 1011) or "1000" in str(e) or "1011" in str(e):
                        print(f"[{self._asst_name}] _receive_audio: cierre de sesión ({status_code}), reconectando...")
                        self._reconnect_event.set()
                        self._pending_reconnect = True
                        self.session = None
                        raise
                    else:
                        print(f"[{self._asst_name}] _receive_audio error API: {e}")
                        traceback.print_exc()
                        self._reconnect_event.set()
                        self._pending_reconnect = True
                        self.session = None
                        raise
                except ReconnectException:
                    raise
                except Exception as e:
                    print(f"[{self._asst_name}] _receive_audio error inesperado: {e}")
                    traceback.print_exc()
                    self._reconnect_event.set()
                    self._pending_reconnect = True
                    self.session = None
                    raise
        except Exception as e:
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print(f"[{self._asst_name}] 🔊 Play iniciado")
        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()

        try:
            while True:
                if self._reconnect_event.is_set():
                    print(f"[{self._asst_name}] _play_audio: evento de reconexión, saliendo.")
                    break

                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(),
                        timeout=0.1
                    )
                    if chunk is None:
                        print(f"[{self._asst_name}] Centinela en play, saliendo.")
                        break
                except asyncio.TimeoutError:
                    if (
                        self._turn_done_event
                        and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()
                    ):
                        self.set_speaking(False)
                        self._turn_done_event.clear()
                    continue

                self.set_speaking(True)

                batch = bytearray(chunk)
                while len(batch) < 9600:
                    try:
                        batch.extend(self.audio_in_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break

                try:
                    await asyncio.to_thread(stream.write, bytes(batch))
                except (RuntimeError, asyncio.CancelledError):
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[{self._asst_name}] ❌ Play: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()
            print(f"[{self._asst_name}] 🔊 Play stream cerrado.")

    # =====================================================================
    # MONITORES Y BUCLE PRINCIPAL
    # =====================================================================
    async def _monitor_connection(self):
        while True:
            try:
                await asyncio.sleep(15)
                if self._loop is None or self._loop.is_closed():
                    break
                online = await asyncio.to_thread(self.probar_internet)
                forced_local = str(_get_config().get("connection_mode", "auto")).lower() == "local"
                if online and self.modo_local and not forced_local:
                    self.ui.write_log("🌐 Internet restaurado. Volviendo a modo nube...")
                    self.modo_local = False
                    self.ui.set_modo("nube")
                    self._pending_reconnect = True
                    self._reconnect_event.set()
                elif not online and not self.modo_local:
                    self.ui.write_log("📡 Sin conexión. Cambiando a modo local.")
                    self.modo_local = True
                    self.ui.set_modo("local")
                    if self.asistente_local is None:
                        try:
                            from local_ai import LocalAssistant
                            self.asistente_local = LocalAssistant()
                            self.asistente_local.hablar("Modo local activado.")
                        except Exception as exc:
                            self.ui.write_log(f"SYS: Voz local no disponible: {exc}")
            except RuntimeError as e:
                if "cannot schedule new futures" in str(e):
                    break
                print(f"[Monitor] Error: {e}")
            except Exception as e:
                print(f"[Monitor] Error inesperado: {e}")

    async def _send_startup_briefing(self) -> None:
        memory = load_memory()
        identity = memory.get("identity", {})
        def _val(k: str) -> str:
            e = identity.get(k, {})
            return (e.get("value", "") if isinstance(e, dict) else str(e)).strip()
        lang = _val("language") or self._user_language or "Spanish"
        name = _val("name")
        time_str = datetime.now().strftime("%H:%M")

        loop = asyncio.get_event_loop()
        news_future = loop.run_in_executor(None, _fetch_news_sync, "top world news today")

        try:
            from src.actions.calendar_manager import _load_events
            events = _load_events()
            today = datetime.now().date()
            today_events = [
                e for e in events
                if datetime.fromisoformat(e.get("datetime", "")).date() == today
            ]
        except Exception:
            today_events = []

        await asyncio.sleep(0.3)
        if not self.session:
            return

        lang_clause = f" Responde en {lang}." if lang else ""
        name_clause = f" Llama al usuario como {name}." if name else ""

        last = await asyncio.to_thread(pop_last_session)
        session_clause = ""
        if last:
            try:
                _delta = (datetime.now() - datetime.strptime(last["date"], "%Y-%m-%d")).days
                _when = "hoy" if _delta == 0 else ("ayer" if _delta == 1 else f"hace {_delta} días")
            except Exception:
                _when = "la última vez"
            session_clause = f" También menciona brevemente que {_when}: {last['summary']}"
        else:
            last_summary = get_last_session_summary()
            if last_summary:
                session_clause = f" Menciona brevemente que la última vez hablamos de: {last_summary}"

        calendar_clause = ""
        if today_events:
            calendar_clause = f" Tienes {len(today_events)} evento(s) hoy: {', '.join(e['title'] for e in today_events)}."

        p1 = (
            f"Saluda al usuario cálidamente, menciona que son las {time_str} y que estás obteniendo las noticias de hoy.{session_clause}{calendar_clause} "
            f"Manténlo en un máximo de 2 frases cortas. No uses herramientas.{lang_clause}{name_clause}"
        )

        if self._turn_done_event:
            self._turn_done_event.clear()

        await self.session.send_client_content(
            turns={"parts": [{"text": p1}]},
            turn_complete=True,
        )
        self.ui.write_log("SYS: Briefing fase 1 (saludo) enviado.")

        async def _deliver_news():
            try:
                lang_str = f" Responde en {lang}." if lang else ""
                news_done = asyncio.wrap_future(news_future)
                turn_waited = False
                if self._turn_done_event:
                    try:
                        await asyncio.wait_for(self._turn_done_event.wait(), timeout=6.0)
                        turn_waited = True
                    except asyncio.TimeoutError:
                        pass

                if turn_waited:
                    await asyncio.sleep(0.8)
                else:
                    await asyncio.sleep(1.0)

                try:
                    news_text = await asyncio.wait_for(news_done, timeout=4.0)
                except Exception:
                    news_text = ""

                if not self.session:
                    return

                if news_text and len(news_text) > 60:
                    self.ui.show_content("NOTICIAS — principales noticias del mundo hoy", news_text)
                    p2 = (
                        f"[BRIEFING] Estos son los titulares de hoy:\n{news_text}\n\n"
                        "Elige UN titular, resúmelo en una frase, luego di que la lista completa "
                        f"se muestra en pantalla. No uses herramientas.{lang_str}"
                    )
                else:
                    p2 = f"No se pudieron obtener los titulares ahora. Hazle saber al usuario brevemente.{lang_str}"

                await self.session.send_client_content(
                    turns={"parts": [{"text": p2}]},
                    turn_complete=True,
                )
                self.ui.write_log("SYS: Briefing fase 2 (noticias) enviado.")
            except Exception as e:
                print(f"[Briefing] Error fase 2: {e}")

        asyncio.create_task(_deliver_news())

    async def _save_session_summary(self) -> None:
        log = self._session_log
        if len(log) < 3:
            return
        self._session_log = []

        memory = load_memory()
        lang_entry = memory.get("identity", {}).get("language", {})
        lang = (lang_entry.get("value", "") if isinstance(lang_entry, dict) else str(lang_entry)).strip()
        lang = lang or "English"

        convo = "\n".join(log[-40:])
        prompt = (
            f"Resume esta conversación en 1-2 frases en {lang}. "
            "Concéntrate en lo que el usuario logró o discutió. "
            "SOLO la salida de texto, nada más:\n\n" + convo
        )
        try:
            from google import genai as _genai
            client = _genai.Client(api_key=_get_api_key())
            resp = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.0-flash",
                contents=prompt,
            )
            summary = (resp.text or "").strip()
            if summary:
                save_session_summary(summary, lang)
                self.ui.write_log("SYS: Resumen de sesión guardado.")
        except Exception as e:
            print(f"[Memoria] ⚠️ Resumen de sesión falló: {e}")

    async def _run_system_monitor(self):
        while not self._reconnect_event.is_set():
            await asyncio.sleep(10)
            try:
                alert = await asyncio.to_thread(self._sys_monitor.check)
            except Exception:
                continue
            if not alert or not self.session:
                continue
            with self._speaking_lock:
                speaking = self._is_speaking
            if speaking or (time.monotonic() - self._last_user_speech) < 10:
                continue
            try:
                await self.session.send_client_content(
                    turns={"parts": [{"text": alert}]},
                    turn_complete=True,
                )
            except Exception:
                pass

    async def _run_background_monitor(self):
        await asyncio.sleep(300)
        while not self._reconnect_event.is_set():
            if self.session:
                with self._speaking_lock:
                    speaking = self._is_speaking
                recent_speech = (time.monotonic() - self._last_user_speech) < 30
                if not speaking and not recent_speech:
                    try:
                        alerts = await asyncio.to_thread(monitor_check_all)
                        memory = load_memory()
                        lang_e = memory.get("identity", {}).get("language", {})
                        lang = (lang_e.get("value", "") if isinstance(lang_e, dict) else str(lang_e)).strip() or "English"
                        for alert in alerts:
                            msg = (
                                f"{alert}\n\n"
                                f"Informa al usuario sobre esto de forma natural en {lang}. "
                                "Solo una frase breve."
                            )
                            await self.session.send_client_content(
                                turns={"parts": [{"text": msg}]},
                                turn_complete=True,
                            )
                            self.ui.write_log(f"SYS: Alerta de monitor enviada.")
                            await asyncio.sleep(6)
                    except Exception:
                        pass
            await asyncio.sleep(1800)

    async def _run_proactive_mode(self):
        while not self._reconnect_event.is_set():
            await asyncio.sleep(60)
            if time.monotonic() - self._last_user_speech > 300 and not self._is_speaking:
                self.ui.write_log("[AutoAprendizaje] Inactividad detectada, iniciando evolución...")
                asyncio.create_task(self.autonomous_learner._autonomous_evolution(self.ui.write_log))
            if not self.session:
                continue
            with self._speaking_lock:
                speaking = self._is_speaking
            if speaking:
                continue
            if self.proactive_v2 is not None:
                if not self.proactive_v2.should_trigger(self._last_user_speech):
                    continue
                self.proactive_v2.mark_triggered()
                try:
                    memory = await asyncio.to_thread(load_memory)
                    monitors = await asyncio.to_thread(list_monitors)
                    recent_turns = self._session_log[-8:] if self._session_log else []
                    from src.actions.calendar_manager import _load_events
                    events = _load_events()
                    from src.actions.weather_report import weather_action
                    weather = weather_action({"city": "Lima, Peru"})
                    prompt = self.proactive_v2.build_prompt(
                        memory=memory,
                        monitors=monitors or None,
                        recent_turns=recent_turns or None,
                        calendar_events=events,
                        weather=weather
                    )
                    await self.session.send_client_content(
                        turns={"parts": [{"text": prompt}]},
                        turn_complete=True,
                    )
                    self.ui.write_log("SYS: Check-in proactivo (v2).")
                except Exception as e:
                    print(f"[Proactivo] ⚠️ {e}")
            else:
                if not self._proactive.should_trigger(self._last_user_speech):
                    continue
                self._proactive.mark_triggered()
                try:
                    memory = await asyncio.to_thread(load_memory)
                    monitors = await asyncio.to_thread(list_monitors)
                    recent_turns = self._session_log[-8:] if self._session_log else []
                    prompt = self._proactive.build_prompt(
                        memory=memory,
                        monitors=monitors or None,
                        recent_turns=recent_turns or None,
                    )
                    await self.session.send_client_content(
                        turns={"parts": [{"text": prompt}]},
                        turn_complete=True,
                    )
                    self.ui.write_log("SYS: Check-in proactivo.")
                except Exception as e:
                    print(f"[Proactivo] ⚠️ {e}")

    async def _run_autonomous_loop(self):
        while not self._reconnect_event.is_set():
            try:
                await self.autonomous_learner.run_loop(self.ui.write_log)
            except Exception as e:
                print(f"[AutoAprendizaje] Error: {e}")
            await asyncio.sleep(1)

    async def _run_self_healer(self):
        while not self._reconnect_event.is_set():
            try:
                await self.self_healer.run_loop(self.ui.write_log)
            except Exception as e:
                print(f"[SelfHealer] Error: {e}")
            await asyncio.sleep(1)

    async def _relay_phone_audio(self):
        if not self._dashboard:
            return
        try:
            q = self._dashboard._phone_audio_queue
        except AttributeError:
            await asyncio.sleep(10)
            return
        while not self._reconnect_event.is_set():
            try:
                chunk = await asyncio.wait_for(q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                self._phone_active = False
                continue
            self._phone_active = True
            with self._speaking_lock:
                speaking = self._is_speaking
            if not speaking and not self.ui.muted:
                try:
                    self.out_queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    pass

    def _on_phone_connected(self):
        self.ui.write_log("SYS: Teléfono conectado vía Dashboard Remoto.")
        self.ui.notify_phone_connected()

    async def _process_dashboard_commands(self):
        while not self._reconnect_event.is_set():
            try:
                text = await asyncio.wait_for(
                    self._dashboard._command_queue.get(), timeout=0.5
                )
                if not text:
                    continue
                for _ in range(80):
                    if self.session:
                        break
                    await asyncio.sleep(0.1)
                if self.session:
                    await self.session.send_client_content(
                        turns={"parts": [{"text": text}]},
                        turn_complete=True,
                    )
                    self.ui.write_log(f"[Web]: {text}")
                else:
                    print(f"[Dashboard] Comando descartado (sin sesión): {text}")
            except asyncio.TimeoutError:
                pass
            except (websockets.ConnectionClosed, RuntimeError) as e:
                print(f"[Dashboard] Conexión cerrada: {e}")
                await asyncio.sleep(1)
            except Exception as e:
                print(f"[Dashboard] Error de comando: {e}")
                await asyncio.sleep(0.5)

    async def _do_shutdown(self):
        print("Apagando AP0LO...")
        self.running = False
        if self.session:
            await self.session.close()
        os._exit(0)

    async def _perform_face_auth(self):
        try:
            from src.auth.face_auth import FaceAuthenticator
        except ImportError:
            self.ui.write_log("ℹ️ Autenticación facial desactivada (MediaPipe no disponible).")
            return
        try:
            _cfg = _get_config()
            if not _cfg.get("face_auth_enabled", False):
                return
            self.ui.write_log("🔐 Autenticación facial activada. Esperando reconocimiento...")
            self.hablar("Por favor, mira a la cámara para autenticarte.")
            import cv2
            cap = cv2.VideoCapture(0)
            ret, frame = cap.read()
            cap.release()
            if ret:
                import tempfile
                tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                cv2.imwrite(tmp.name, frame)
                face_auth = FaceAuthenticator()
                user_id, confidence = face_auth.verify_user(tmp.name)
                os.unlink(tmp.name)
                if user_id:
                    self.ui.write_log(f"✅ Autenticación exitosa: {user_id} (confianza: {confidence:.2f})")
                    self.hablar(f"Bienvenido de nuevo, {user_id}.")
                else:
                    self.ui.write_log("❌ Autenticación fallida. Continuando en modo limitado.")
                    self.hablar("No te reconozco. Algunas funciones estarán restringidas.")
            else:
                self.ui.write_log("⚠️ No se pudo acceder a la cámara. Saltando autenticación.")
        except Exception as e:
            self.ui.write_log(f"⚠️ Error en autenticación facial: {e}")

    # =====================================================================
    # BUCLE PRINCIPAL (CORREGIDO CON MANEJO DE RECONEXIÓN Y LÍMITE DE INTENTOS)
    # =====================================================================
    async def run(self):
        self._loop = asyncio.get_event_loop()

        try:
            from src.dashboard.server import DashboardServer
            self._dashboard = DashboardServer()
            self._dashboard.set_connect_callback(self._on_phone_connected)
            async def _serve_dashboard():
                try:
                    await self._dashboard.serve()
                except Exception as e:
                    print(f"[Dashboard] ❌ Error crítico: {e}")
                    self._dashboard = None
                    self.ui.write_log(f"SYS: Dashboard falló — {e}")
            asyncio.create_task(_serve_dashboard())
            asyncio.create_task(self._process_dashboard_commands())
        except Exception as e:
            print(f"[Dashboard] Desactivado: {e}")
            self._dashboard = None

        try:
            from google import genai
            from google.genai import types
            _gemini_sdk_available = True
        except ImportError:
            genai = None
            types = None
            _gemini_sdk_available = False

        _cfg_start = _get_config()
        _mode_start = str(_cfg_start.get("connection_mode", "auto")).lower()
        api_key = _get_api_key()
        _cloud_ready = _gemini_sdk_available and _validate_api_key(api_key)
        if _mode_start == "local" or not _cloud_ready:
            self.modo_local = True
            self.ui.set_modo("local")
            reason = "modo LOCAL configurado" if _mode_start == "local" else "Gemini no disponible"
            self.ui.write_log(f"SYS: {reason}. Usando proveedor local sin bloquear el arranque.")
        else:
            self.modo_local = False

        await self._perform_face_auth()

        asyncio.create_task(self._monitor_connection())

        if self.modo_local:
            await self._run_local_mode()
            return

        while True:
            try:
                self._reconnect_event.clear()
                self._personality_change_requested = False

                # ===== USAR SIEMPRE LA PERSONALIDAD ACTUAL, NO LA DEL ARCHIVO =====
                personality = getattr(self, 'current_personality', 'jarvis')
                theme = THEME_MAP.get(personality, DEFAULT_THEME)
                if self._pending_reconnect:
                    self._pending_reconnect = False
                    print(f"[{self._asst_name}] Reconectando con personalidad: {personality}")
                    self._apply_personality_to_ui(personality)
                    if self.ui and hasattr(self.ui, '_win'):
                        self.ui._win._theme_changed.emit(theme)

                _cfg = _get_config()
                assistant_name = _cfg.get("assistant_name", "APOLO").upper()

                live_models = get_live_model_list()
                if not live_models:
                    live_models = [LIVE_MODEL]
                print(f"[{self._asst_name}] 📋 Modelos LIVE configurados: {live_models}")

                connected = False
                self._reconnecting = False
                self._should_restart = False

                for live_model in live_models:
                    if connected or self._reconnecting:
                        break
                    try:
                        print(f"[{self._asst_name}] 🔄 Intentando con modelo: {live_model} (personalidad: {personality})")
                        self.ui.set_state("THINKING")
                        config = self._build_config(personality)

                        client = genai.Client(
                            api_key=_get_api_key(),
                            http_options={"api_version": "v1beta"}
                        )

                        # TIMEOUT DE CONEXIÓN
                        async with asyncio.timeout(30):
                            async with client.aio.live.connect(model=live_model, config=config) as session:
                                self.session = session
                                self._reconnecting = False
                                self._should_restart = False
                                self._reconnect_attempts = 0  # Reiniciar contador en éxito
                                try:
                                    if hasattr(session, '_resumption_handle') and session._resumption_handle:
                                        self._session_resumption_handle = session._resumption_handle
                                except Exception:
                                    pass

                                self.audio_in_queue = asyncio.Queue()
                                self.out_queue = asyncio.Queue(maxsize=500)
                                self._turn_done_event = asyncio.Event()
                                self._reconnect_attempts = 0

                                self._pending_vision = None
                                self._vision_cam_active = False
                                self._vision_close_pending = False
                                self._vision_busy = False
                                self._vision_last_time = 0.0
                                self._interrupted = False

                                voice_name = VOICE_MAP.get(personality, DEFAULT_VOICE)
                                print(f"[{self._asst_name}] ✅ Conectado con {live_model}. Personalidad: {personality.capitalize()} | Voz: {voice_name}")
                                self.ui.set_state("LISTENING")
                                self.ui.write_log(f"SYS: {assistant_name} online | Modelo: {live_model} | Personalidad: {personality.capitalize()}")

                                self._current_model = live_model

                                if self._dashboard:
                                    await self._dashboard.broadcast({"type": "status", "state": "active"})

                                if self.boot_screen:
                                    self._close_boot_screen()

                                async def task_wrapper(coro, name):
                                    try:
                                        await coro
                                    except asyncio.CancelledError:
                                        print(f"[{self._asst_name}] {name} cancelado, saliendo.")
                                    except ReconnectException:
                                        print(f"[{self._asst_name}] {name} detectó reconexión, saliendo.")
                                        self._reconnect_event.set()
                                        self._should_restart = True
                                        raise
                                    except Exception as e:
                                        print(f"[{self._asst_name}] {name} error: {e}")

                                async with asyncio.TaskGroup() as tg:
                                    tg.create_task(task_wrapper(self._send_realtime(), "_send_realtime"))
                                    tg.create_task(task_wrapper(self._listen_audio(), "_listen_audio"))
                                    tg.create_task(task_wrapper(self._receive_audio(), "_receive_audio"))
                                    tg.create_task(task_wrapper(self._play_audio(), "_play_audio"))
                                    if self._dashboard:
                                        tg.create_task(task_wrapper(self._relay_phone_audio(), "_relay_phone_audio"))

                                    monitor_tasks = []
                                    for coro, name in [
                                        (self._run_system_monitor(), "_run_system_monitor"),
                                        (self._run_background_monitor(), "_run_background_monitor"),
                                        (self._run_proactive_mode(), "_run_proactive_mode"),
                                        (self._run_autonomous_loop(), "_run_autonomous_loop"),
                                        (self._run_self_healer(), "_run_self_healer"),
                                    ]:
                                        monitor_tasks.append(asyncio.create_task(task_wrapper(coro, name)))

                                    if not self._briefing_sent and get_brief_enabled():
                                        self._briefing_sent = True
                                        tg.create_task(self._send_startup_briefing())

                                for task in monitor_tasks:
                                    task.cancel()
                                await asyncio.gather(*monitor_tasks, return_exceptions=True)

                                connected = True

                    except asyncio.TimeoutError:
                        print(f"[{self._asst_name}] ⏰ Timeout conectando a {live_model}")
                        continue
                    except ReconnectException:
                        print(f"[{self._asst_name}] 🔄 Reiniciando por excepción de reconexión...")
                        self._reconnect_event.clear()
                        connected = False
                        self._reconnecting = True
                        self._should_restart = True
                        self._personality_change_requested = True
                        break
                    except genai.errors.APIError as e:
                        err_str = str(e)
                        if "429" in err_str or "quota" in err_str.lower():
                            print(f"[{self._asst_name}] ⚠️ CUOTA AGOTADA. Cambiando a modo LOCAL.")
                            self.ui.write_log("⚠️ Se ha agotado el crédito de Gemini. Activando modo LOCAL automáticamente.")
                            self.modo_local = True
                            self.ui.set_modo("local")
                            if self.asistente_local is None:
                                from local_ai import LocalAssistant
                                self.asistente_local = LocalAssistant()
                                self.asistente_local.hablar("Modo local activado por falta de crédito.")
                            connected = False
                            break
                        elif "404" in err_str:
                            print(f"[{self._asst_name}] ⚠️ Modelo {live_model} no disponible (404). Probando siguiente...")
                            continue
                        else:
                            print(f"[{self._asst_name}] ❌ Error con {live_model}: {err_str[:200]}")
                            continue
                    except asyncio.CancelledError:
                        connected = False
                        break
                    except Exception as e:
                        err_str = str(e)
                        if "persona_switch" in err_str or "Cambio a personalidad" in err_str:
                            print(f"[{self._asst_name}] 🔄 Cambiando a personalidad {self._reconnect_personality.capitalize()}...")
                            self._reconnect_event.clear()
                            connected = False
                            self._reconnecting = True
                            self._should_restart = True
                            self._personality_change_requested = True
                            break
                        print(f"[{self._asst_name}] ❌ Error con {live_model}: {err_str[:200]}")
                        continue
                    finally:
                        if not connected and not self._reconnecting:
                            await self._save_session_summary()
                            self.session = None
                            self.set_speaking(False)
                            self.ui.set_state("SLEEPING")
                            if self._dashboard:
                                await self._dashboard.broadcast({"type": "status", "state": "sleeping"})

                # ===== VERIFICAR RECONEXIÓN Y LÍMITE DE INTENTOS =====
                if self._personality_change_requested:
                    print(f"[{self._asst_name}] 🔄 Personalidad cambiada, reiniciando bucle...")
                    self._personality_change_requested = False
                    self._should_restart = False
                    self._reconnecting = False
                    self._reconnect_event.clear()
                    self._reconnect_immediate = True
                    self._reconnect_attempts = 0
                    await asyncio.sleep(0.5)
                    continue

                if self._reconnect_event.is_set():
                    print(f"[{self._asst_name}] 🔄 Reconexión solicitada por evento, reiniciando bucle...")
                    self._reconnect_event.clear()
                    self._reconnecting = False
                    self._should_restart = False
                    self._pending_reconnect = True
                    self._reconnect_attempts += 1
                    if self._reconnect_attempts > 3:
                        self.ui.write_log("⚠️ Demasiados intentos de reconexión. Cambiando a modo LOCAL.")
                        self.modo_local = True
                        self.ui.set_modo("local")
                        if self.asistente_local is None:
                            from local_ai import LocalAssistant
                            self.asistente_local = LocalAssistant()
                            self.asistente_local.hablar("Cambio a modo local por fallos de conexión.")
                        self._reconnect_attempts = 0
                        await asyncio.sleep(1)
                        continue
                    await asyncio.sleep(0.5)
                    continue

                # ===== SI NO HAY CONEXIÓN, MODO LOCAL =====
                if not connected and not self.modo_local and not self._reconnecting:
                    self.ui.write_log("⚠️ Todos los modelos LIVE fallaron. Activando modo LOCAL.")
                    self.modo_local = True
                    self.ui.set_modo("local")
                    if self.asistente_local is None:
                        from local_ai import LocalAssistant
                        self.asistente_local = LocalAssistant()
                        self.asistente_local.hablar("Modo local activado por fallo de los modelos en la nube.")

                if self.modo_local:
                    await self._run_local_mode()
                    await asyncio.sleep(5)
                    continue

                # ===== SI LLEGAMOS AQUÍ, CONNECTED ES TRUE =====
                if connected:
                    if self._reconnect_immediate:
                        delay = 0.5
                        self._reconnect_immediate = False
                    else:
                        delay = min(60, 3 + self._reconnect_attempts * 3)
                        self._reconnect_attempts += 1
                    print(f"[{self._asst_name}] Reconectando en {delay}s...")
                    await asyncio.sleep(delay)
                    self._reconnecting = False

            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except BaseExceptionGroup as e:
                excs = getattr(e, "exceptions", [])
                is_persona_switch = any("persona_switch" in str(sub) or "Cambio a personalidad" in str(sub) for sub in excs)
                if is_persona_switch:
                    print(f"[{self._asst_name}] 🔄 Cambiando a personalidad {self._reconnect_personality.capitalize()}...")
                    self._reconnect_event.clear()
                    self._should_restart = True
                    self._personality_change_requested = True
                else:
                    print(f"[{self._asst_name}] Advertencia: {str(e)[:200]}")
                    traceback.print_exc()
                    await asyncio.sleep(3)
            except Exception as e:
                err_str = str(e)
                if "persona_switch" in err_str or "Cambio a personalidad" in err_str:
                    print(f"[{self._asst_name}] 🔄 Cambiando a personalidad {self._reconnect_personality.capitalize()}...")
                    self._reconnect_event.clear()
                    self._should_restart = True
                    self._personality_change_requested = True
                else:
                    print(f"[{self._asst_name}] Error: {e}")
                    traceback.print_exc()
                    await asyncio.sleep(3)
            finally:
                if not self._reconnect_immediate:
                    await self._save_session_summary()
                self.session = None
                self.set_speaking(False)
                self.ui.set_state("SLEEPING")
                if self._dashboard:
                    await self._dashboard.broadcast({"type": "status", "state": "sleeping"})

    # ===== MODO LOCAL =====
    async def _run_local_mode(self):
        self.ui.write_log("🎤 Modo LOCAL: Ollama disponible; entrada por teclado y voz si el dispositivo está configurado.")
        self.ui.set_state("LISTENING")
        if self.asistente_local is None:
            try:
                from local_ai import LocalAssistant
                self.asistente_local = LocalAssistant()
            except Exception as exc:
                # Vosk/pyttsx3 son opcionales. El sistema continúa operativo
                # mediante el campo de texto y HybridRouter.route_local().
                self.asistente_local = None
                self.ui.write_log(f"SYS: Voz local no disponible ({exc}); chat local por texto activo.")

        while self.modo_local:
            try:
                question = self.asistente_local.listen(timeout=5) if self.asistente_local else None
                if question:
                    self.ui.write_log(f"Tú: {question}")
                    answer = self.router.route_local(question, self._asst_name)
                    self.ui.write_log(f"{self._asst_name}: {answer}")
                    if self.asistente_local:
                        self.asistente_local.hablar(answer)
                    if self.panel:
                        try:
                            if hasattr(self.panel, 'show_message'):
                                QMetaObject.invokeMethod(
                                    self.panel,
                                    "show_message",
                                    Qt.ConnectionType.QueuedConnection,
                                    Q_ARG(str, answer),
                                    Q_ARG(str, self._asst_name)
                                )
                            else:
                                self.ui.show_content(self._asst_name, answer)
                        except Exception:
                            self.ui.show_content(self._asst_name, answer)
                if await self._check_should_exit_local():
                    self.modo_local = False
                    self.ui.write_log("🌐 Saliendo del modo LOCAL. Volviendo a modo NUBE.")
                    self.ui.set_modo("nube")
                    break
                await asyncio.sleep(0.5)
            except Exception:
                await asyncio.sleep(1)

    async def _check_should_exit_local(self) -> bool:
        if str(_get_config().get("connection_mode", "auto")).lower() == "local":
            return False
        if not self.probar_internet():
            return False
        try:
            from google import genai
            api_key = _get_api_key()
            if not _validate_api_key(api_key):
                return False
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents="Hola, responde 'OK'",
                config={"max_output_tokens": 5}
            )
            if response and response.text:
                return True
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                print("[ModoLocal] Aún sin crédito. Permanecer en local.")
            else:
                print(f"[ModoLocal] Error probando Gemini: {e}")
        return False
