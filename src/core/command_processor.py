# from ursina import *  # DESACTIVE — interface web Three.js
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import warnings

# Supprimer les warnings python (comme la dépréciation de pkg_resources dans setuptools)
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
# --- Pygame (audio TTS) : optionnel ---
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
    print("  -> Para instalarlo : pip install pygame --only-binary :all:")
from dotenv import load_dotenv
from core import agent_model_manager

_JARVIS_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")

def _cargar_config() -> dict:
    """Charge jarvis_config.json ou retourne un dict vide si absent/corrompu."""
    try:
        if os.path.exists(_JARVIS_CONFIG_PATH):
            import json
            with open(_JARVIS_CONFIG_PATH, "r", encoding="utf-8") as f:
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

USER_NAME = _cargar_nombre_usuario()
USER_AGE  = _cargar_edad_usuario()

import random
import math
import builtins
import winreg

def _get_bat_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "DEMARRER_JARVIS.bat")

def activar_inicio_windows():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        bat_path = _get_bat_path()
        winreg.SetValueEx(key, "JARVIS", 0, winreg.REG_SZ, f'"{bat_path}"')
        winreg.CloseKey(key)
        print("[JARVIS] Inicio automático con Windows activado.")
    except Exception as e:
        print(f"[JARVIS] Error al activar inicio automático con Windows: {e}")

def desactivar_inicio_windows():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, "JARVIS")
        winreg.CloseKey(key)
        print("[JARVIS] Inicio automático con Windows desactivado.")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[JARVIS] Error al desactivar inicio automático con Windows: {e}")

# --- GLOBALS TTS/AUDIO ---
WEB_LOOP = None
is_speaking = False
speak_volume = 0.0
STOP_PARLER     = False
MIC_MUTED       = False
MIC_NEED_RELOAD = False
MIC_FORCED_INDEX = None  # Index imposé explicitement par l'utilisateur via les paramètres
NEMOTRON_ASR_ENABLED = False
_nemotron_instance = None  # Instance NemotronASR (lazy — chargée à la demande)
_skip_pc_audio = False
_OLLAMA_MODEL_LOADED = False
historique = []

# ── Gestionnaire de quota journalier Gemini TTS ───────────────────────────────
# Limite officielle : 100 req/jour sur gemini-2.5-flash-preview-tts
# On s'arrête à 90 pour garder une marge de sécurité.
_GEMINI_TTS_QUOTA_MAX  = 90   # seuil préventif (limite réelle = 100/jour)
_GEMINI_TTS_QUOTA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_tts_quota.json")

def _limpiar_emojis_para_tts(texte: str) -> str:
    """Supprime les emojis, symboles graphiques et termes indésirables pour la synthèse vocale."""
    if not texte:
        return ""
    import re
    # Supprimer les expressions anglaises comme "skill issue" ou "skill issu"
    texte = re.sub(r'(?i)\bskill\s+issu(e)?\b', '', texte)

    emoji_pattern = re.compile(
        "["
        "\U00010000-\U0010FFFF"  # Emojis & symboles étendus (ex: 🔴, 🟢, 🔞, 🤖, 🎭, 🔥, etc.)
        "\u2600-\u27BF"          # Symboles divers et dingbats (ex: ☀️, ⭐, ❤️, etc.)
        "\uFE00-\uFE0F"          # Variation Selectors
        "\u200D"                 # Zero Width Joiner
        "\u2300-\u23FF"          # Symboles techniques
        "\u2B50"                 # Étoile
        "\u20E3"                 # Keycap
        "]+", 
        flags=re.UNICODE
    )
    cleaned = emoji_pattern.sub(" ", texte)
    return re.sub(r'\s+', ' ', cleaned).strip()

def _tts_cuota_cargar() -> dict:
    """Charge le compteur de quota depuis le fichier JSON."""
    try:
        if os.path.exists(_GEMINI_TTS_QUOTA_FILE):
            with open(_GEMINI_TTS_QUOTA_FILE, "r", encoding="utf-8") as _f:
                return json.load(_f)
    except Exception:
        pass
    return {"date": "", "count": 0}

def _tts_cuota_guardar(data: dict) -> None:
    try:
        with open(_GEMINI_TTS_QUOTA_FILE, "w", encoding="utf-8") as _f:
            json.dump(data, _f)
    except Exception:
        pass

def _tts_cuota_verificar() -> bool:
    """
    Retourne True si on peut encore appeler Gemini TTS aujourd'hui.
    Retourne False si le quota journalier est atteint → utiliser Edge TTS.
    """
    import datetime
    data = _tts_cuota_cargar()
    today = datetime.date.today().isoformat()
    if data.get("date") != today:
        # Nouveau jour → remise à zéro
        data = {"date": today, "count": 0}
        _tts_cuota_guardar(data)
    count = data.get("count", 0)
    if count >= _GEMINI_TTS_QUOTA_MAX:
        print(f"[GEMINI TTS] Cuota diaria alcanzada ({count}/{_GEMINI_TTS_QUOTA_MAX}) — Edge TTS activado hasta la medianoche.")
        return False
    return True

def _tts_cuota_incrementar() -> None:
    """Incrémente le compteur de requêtes du jour."""
    import datetime
    data = _tts_cuota_cargar()
    today = datetime.date.today().isoformat()
    if data.get("date") != today:
        data = {"date": today, "count": 0}
    data["count"] = data.get("count", 0) + 1
    _tts_cuota_guardar(data)
    remaining = max(0, _GEMINI_TTS_QUOTA_MAX - data["count"])
    if remaining <= 10:
        print(f"[GEMINI TTS] ⚠ Quota : {data['count']}/{_GEMINI_TTS_QUOTA_MAX} — {remaining} requêtes restantes aujourd'hui.")

async def _gemini_tts_a_archivo(texte: str, voice_name: str, out_wav: str) -> bool:
    """
    Génère un fichier audio WAV via Gemini AI TTS.
    Retourne True si succès, False sinon (respaldo Edge TTS sera effectué).

    Gestion automatique du quota journalier (100 req/jour sur le modèle preview).
    Bascule proprement sur Edge TTS avant d'atteindre la limite.
    """
    # ── 1. Vérification préventive du quota ───────────────────────────────────
    if not _tts_cuota_verificar():
        return False  # Edge TTS prendra le relais silencieusement

    try:
        import wave as _wave
        _api_key = os.getenv("GEMINI_API_KEY", "")
        if not _api_key:
            print("[GEMINI TTS] Clave API faltante — respaldo Edge TTS")
            return False

        import google.genai as _genai
        from google.genai import types as _gtypes

        _gclient = _genai.Client(api_key=_api_key)

        speech_cfg = _gtypes.SpeechConfig(
            voice_config=_gtypes.VoiceConfig(
                prebuilt_voice_config=_gtypes.PrebuiltVoiceConfig(voice_name=voice_name)
            )
        )

        response = _gclient.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=texte,
            config=_gtypes.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=speech_cfg,
            ),
        )

        # Extraire les données audio brutes (PCM 16-bit, 24 000 Hz, mono)
        audio_data = response.candidates[0].content.parts[0].inline_data.data

        # Écrire un fichier WAV valide
        with _wave.open(out_wav, "wb") as wf:
            wf.setnchannels(1)       # mono
            wf.setsampwidth(2)       # 16-bit
            wf.setframerate(24000)   # 24 kHz — fréquence native Gemini TTS
            wf.writeframes(audio_data)

        # ── 2. Incrémenter le compteur uniquement en cas de succès ────────────
        _tts_cuota_incrementar()
        print(f"[GEMINI TTS] [OK] Audio generado con la voz '{voice_name}' — {len(audio_data)} bytes")
        return True

    except Exception as e:
        err_str = str(e).lower()
        # ── 3. Gestion spécifique du quota dépassé (429) ─────────────────────
        if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
            # Forcer le compteur à la limite pour éviter de réessayer inutilement
            import datetime
            data = _tts_cuota_cargar()
            data["date"] = datetime.date.today().isoformat()
            data["count"] = _GEMINI_TTS_QUOTA_MAX
            _tts_cuota_guardar(data)
            print("[GEMINI TTS] Quota Google épuisé pour aujourd'hui — Edge TTS activado hasta la medianoche.")
        else:
            print(f"[GEMINI TTS] [ERREUR] {e} — respaldo Edge TTS")
        return False




# ── ANIMATION VISUELLE & SYSTEME DE COMPETENCES AUTONOMES ─────────────────────

def _efecto_visual_iron_man(stop_event):
    """Affiche un effet de défilement de code et logs style Iron Man HUD dans la console et sur l'écran web."""
    import random
    import time

    # Passer l'orbe en état thinking immédiatement pour l'animer à l'écran
    send_web_broadcast_sync({"action": "set_state", "state": "thinking"})

    logs_fictifs = [
        ">>> SYSTEM: ALLOCATING COMPILATION SEGMENT ON CORE_0...",
        ">>> CONNECTING TO GEMINI NEURAL CORRELATOR (MODEL: gemini-3.5-flash)...",
        ">>> ENABLING THINKING MODE (BUDGET: 2048)...",
        ">>> SYNCHRONIZING THOUGHT MATRIX CONSTRAINTS...",
        ">>> HEAP ALLOC: 0x7FFA4C9E0000 [64MB]",
        "[SYSTEM] LOADING LIBRARIES: importlib.util, os, time, sys",
        "[COMPILE] Generating function signature: def executer(texte_utilisateur=None)",
        "[PARSER] Enforcing raw python rules: no markdown tags, pure source...",
        "[COMPILER] Building AST Nodes...",
        "[SYSTEM] COMPILING RESOURCE: plugins/competence_*.py",
        ">>> COMPACTING SOURCE CODE BUFFER...",
        ">>> INJECTING VOICE OUTPUT RETURN STRINGS...",
        ">>> SHIELD POWER STABILITY: 98.4%",
        ">>> SCANNING CORRUPTED SECTORS... OK",
        "[LOG] Dynamic loader thread instantiated.",
        "[INFO] Code integrity check: 100% compliant.",
        "[DEBUG] Temperature: 0.1 | Top-P: 0.95 | Top-K: 40",
    ]
    caracteres = "0123456789ABCDEFghijklmnopqrstuvwxyz[]{}()$#@!*&%^-_=+"

    print("\n\033[93m" + "="*60)
    print("   J.A.R.V.I.S — PLUGINS SYSTEM: COMPILING NEW SKILL")
    print("="*60 + "\033[0m\n")

    iteration = 0
    while not stop_event.is_set():
        val = random.random()
        log_texte = ""
        if val < 0.3:
            log_texte = random.choice(logs_fictifs)
            print(f"\033[94m[HUD_LOG] {log_texte}\033[0m")
        elif val < 0.6:
            addr = f"0x{random.randint(0x10000000, 0xFFFFFFFF):X}"
            data = "".join(random.choice(caracteres) for _ in range(40))
            log_texte = f"{addr} : {data}"
            print(f"\033[92m[MATRICE] {log_texte}\033[0m")
        else:
            progress = random.randint(0, 100)
            bar = "=" * (progress // 5) + " " * (20 - (progress // 5))
            log_texte = f"COMPILING: [{bar}] {progress}%"
            print(f"\033[96m[SYSTEM] {log_texte}\033[0m")
            
        # Toutes les 12 itérations (~500ms), envoyer le log actuel au HUD web pour le défilement
        if iteration % 12 == 0:
            send_web_broadcast_sync({"action": "jarvis_text", "text": f"[HUD] {log_texte}"})
            
        iteration += 1
        time.sleep(0.04)

    print("\n\033[92m" + "="*60)
    print("   J.A.R.V.I.S — SKILL SUCCESSFULLY INTEGRATED")
    print("="*60 + "\033[0m\n")

    # Restaurer l'état d'origine de l'orbe et du texte
    send_web_broadcast_sync({"action": "set_state", "state": "idle"})
    send_web_broadcast_sync({"action": "jarvis_text", "text": "COMPILATION TERMINÉE — COMPÉTENCE CHARGÉE"})


def jarvis_crear_competencia(nom_competence: str, description_demande: str) -> str:
    """
    Appelle Gemini-3.5-flash avec thinking activé pour générer une compétence Python autonome.
    Sauvegarde le code généré dans le dossier plugins/ sous competence_<nom>.py.
    """
    import re
    import threading
    import os
    import builtins
    from google.genai import types as _gtypes

    # Valider le client API
    if not hasattr(builtins, "client") or not builtins.client:
        return "Error : le client Gemini n'est pas initialisé ou la clé API est invalide."

    nom_formate = re.sub(r'[^a-zA-Z0-9_]', '', nom_competence.lower().replace(" ", "_"))
    dossier_plugins = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")
    if not os.path.exists(dossier_plugins):
        os.makedirs(dossier_plugins, exist_ok=True)
    
    filename = os.path.join(dossier_plugins, f"competence_{nom_formate}.py")

    # Animation Iron Man
    stop_event = threading.Event()
    thread_anim = threading.Thread(target=_efecto_visual_iron_man, args=(stop_event,), daemon=True)
    thread_anim.start()

    try:
        system_instruction = (
            "Eres l'agent de génération de compétences autonomes de JARVIS.\n"
            "Tu dois écrire du code Python strict, propre et valide.\n\n"
            "RÈGLES CRITIQUES :\n"
            "1. Renvoie UNIQUEMENT le code Python pur. Ne mets AUCUNE balise de code markdown comme ```python ou ```. Pas de texte explicatif en dehors du code.\n"
            "2. Le script doit être entièrement autonome.\n"
            "3. Tu dois obligatoirement implémenter une fonction principale nommée `executer(texte_utilisateur=None)` qui prend un argument optionnel (string) et qui RETOURNE obligatoirement une string (le texte formaté que JARVIS lira à voix haute).\n"
            "4. Évite tout appel externe nécessitant des credentials non fournis (clés d'APIs tierces) à moins que ce ne soit faisable via des APIs publiques ou des mocks. Tu peux utiliser des bibliothèques standards ou requests."
        )

        prompt = (
            f"Génère le code complet pour la compétence : '{nom_competence}'.\n"
            f"Objectif de la compétence : {description_demande}\n\n"
            "Écris le code Python pur respectant toutes les règles de structure."
        )

        # Appel Gemini-3.5-flash avec configuration Thinking
        response = builtins.client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=_gtypes.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,
                thinking_config=_gtypes.ThinkingConfig(thinking_budget=2048)
            )
        )

        code_genere = response.text.strip()
        
        # Limpieza de sécurité en cas de balises markdown résiduelles
        if code_genere.startswith("```"):
            lines = code_genere.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            code_genere = "\n".join(lines).strip()

        # Écriture du fichier compétence
        with open(filename, "w", encoding="utf-8") as f:
            f.write(code_genere)

        stop_event.set()
        thread_anim.join()
        
        print(f"[JARVIS PLUGINS] Nouvelle compétence écrite dans {filename}")
        return f"La compétence '{nom_competence}' a été générée et installée avec succès. Elle est prête à être exécutée."

    except Exception as e:
        stop_event.set()
        thread_anim.join()
        print(f"[JARVIS PLUGINS] Error lors de la création de compétence : {e}")
        return f"Désolé Christopher, la génération de la compétence a échoué. Détail de l'erreur : {e}"


def jarvis_eliminar_competencia(nom_competence: str) -> str:
    """Supprime proprement le fichier de compétence ciblée."""
    import re
    import os
    nom_formate = re.sub(r'[^a-zA-Z0-9_]', '', nom_competence.lower().replace(" ", "_"))
    filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins", f"competence_{nom_formate}.py")

    if os.path.exists(filename):
        try:
            os.remove(filename)
            print(f"[JARVIS PLUGINS] Compétence supprimée : {filename}")
            return f"La compétence '{nom_competence}' a été désinstallée et son fichier a été supprimé."
        except Exception as e:
            return f"Error lors de la suppression du fichier : {e}"
    else:
        return f"La compétence '{nom_competence}' n'est pas installée."


def ejecutar_competencia_vocal(nom_competence: str, texte_recu: str = None) -> str:
    """Importe et exécute dynamiquement la compétence vocale."""
    import re
    import os
    import sys
    import importlib.util

    nom_formate = re.sub(r'[^a-zA-Z0-9_]', '', nom_competence.lower().replace(" ", "_"))
    filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins", f"competence_{nom_formate}.py")

    if not os.path.exists(filename):
        return f"Désolé Christopher, la compétence '{nom_competence}' n'est pas disponible."

    try:
        # Importation à chaud
        module_name = f"plugins.competence_{nom_formate}"
        spec = importlib.util.spec_from_file_location(module_name, filename)
        if spec is None or spec.loader is None:
            return "Impossible de charger la spécification du module."

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        if hasattr(module, "executer"):
            res = module.executer(texte_recu)
            return str(res)
        else:
            return "Error : cette compétence ne possède pas de point d'entrée 'executer'."

    except Exception as e:
        print(f"[JARVIS PLUGINS] Error lors de l'exécution de {nom_competence} : {e}")
        return f"Error d'exécution dans la compétence '{nom_competence}' : {e}"



# ── Gemini LIVE TTS (Live API — sans quota journalier) ────────────────────────
# Utilise gemini-2.5-flash-native-audio-latest via le Live API (streaming).
# Aucune limite de 100 req/jour — idéal pour une utilisation intensive.
# Voz disponibles : mêmes que le TTS standard (Fenrir, Puck, Aoede, etc.)

_GEMINI_LIVE_VOICE_MAP = {
    "gemini_live_fenrir": "Fenrir",   # Grave, posé, très humain
    "gemini_live_puck":   "Puck",     # Dynamique, énergique
    "gemini_live_aoede":  "Aoede",    # Naturel, apaisant
    "gemini_live_charon": "Charon",   # Clair, informatif
    "gemini_live_orus":   "Orus",     # Robuste, posé
    "gemini_live_zephyr": "Zephyr",   # Lumineux, expressif
}

async def _gemini_live_tts_a_archivo(texte: str, voice_name: str, out_wav: str) -> bool:
    """
    Génère un fichier audio WAV via le Gemini Live API.
    Sans quota journalier (facturation à l'usage).
    Retourne True si succès, False sinon (respaldo Edge TTS).
    """
    try:
        import wave as _wave
        import google.genai as _genai
        from google.genai import types as _gtypes

        _api_key = os.getenv("GEMINI_API_KEY", "")
        if not _api_key:
            print("[GEMINI LIVE TTS] Clave API faltante — respaldo Edge TTS")
            return False

        _gclient = _genai.Client(api_key=_api_key)

        speech_cfg = _gtypes.SpeechConfig(
            voice_config=_gtypes.VoiceConfig(
                prebuilt_voice_config=_gtypes.PrebuiltVoiceConfig(voice_name=voice_name)
            )
        )
        live_config = _gtypes.LiveConnectConfig(
            response_modalities=[_gtypes.Modality.AUDIO],
            speech_config=speech_cfg,
        )

        audio_data = bytearray()
        async with _gclient.aio.live.connect(
            model="gemini-2.5-flash-native-audio-latest",
            config=live_config
        ) as session:
            await session.send(input=texte, end_of_turn=True)
            async for response in session.receive():
                if response.server_content and response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        if part.inline_data:
                            audio_data.extend(part.inline_data.data)
                if response.server_content and response.server_content.turn_complete:
                    break

        if not audio_data:
            print("[GEMINI LIVE TTS] No se recibió audio — respaldo Edge TTS")
            return False

        with _wave.open(out_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(bytes(audio_data))

        print(f"[GEMINI LIVE TTS] [OK] Voz '{voice_name}' — {len(audio_data)} bytes")
        return True

    except Exception as e:
        print(f"[GEMINI LIVE TTS] [ERREUR] {e} — respaldo Edge TTS")
        return False


async def generer_et_chanter_musique(prompt_utilisateur: str) -> bool:

    """
    Se connecte à l'API Live Connect de Gemini pour générer une chanson chantée en mode audio direct,
    sauvegarde l'audio dans un fichier WAV et le lit via le mixer audio.
    """
    global _skip_pc_audio, speak_volume, STOP_PARLER
    try:
        import wave as _wave
        import google.genai as _genai
        from google.genai import types as _gtypes
        import base64
        import json
        import time
        import math
        import random as _rnd

        _api_key = os.getenv("GEMINI_API_KEY", "")
        if not _api_key:
            print("[MUSIQUE GEN] Clave API faltante.")
            return False

        _gclient = _genai.Client(api_key=_api_key)
        
        # Consigne créative stricte
        music_prompt = (
            f"Chante une courte chanson (maximum 20 secondes) répondant à la demande : {prompt_utilisateur}. "
            "Chante directement avec une vraie mélodie chantée, du rythme et de l'énergie (sois expressif). "
            "Ne parle pas, ne fais pas d'introduction ni de conclusion parlée. Commence directement à chanter."
        )

        audio_data = bytearray()
        config = _gtypes.LiveConnectConfig(
            response_modalities=[_gtypes.Modality.AUDIO]
        )

        print("[MUSIQUE GEN] Conexión a la API Gemini Live...")
        async with _gclient.aio.live.connect(model="gemini-2.5-flash-native-audio-latest", config=config) as session:
            print("[MUSIQUE GEN] Sesión abierta. Envío de la solicitud créative...")
            await session.send(input=music_prompt, end_of_turn=True)
            
            print("[MUSIQUE GEN] Recepción del flujo audio...")
            async for response in session.receive():
                if response.server_content:
                    model_turn = response.server_content.model_turn
                    if model_turn:
                        for part in model_turn.parts:
                            if part.inline_data:
                                audio_data.extend(part.inline_data.data)
                
                if response.server_content and response.server_content.turn_complete:
                    break

        if len(audio_data) == 0:
            print("[MUSIQUE GEN] No se recibió audio.")
            return False

        # Sauvegarder l'audio temporaire
        tmp_wav = f"jarvis_chanson_{int(time.time()*1000)}.wav"
        with _wave.open(tmp_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(audio_data)

        print(f"[MUSIQUE GEN] [OK] Canción generada con éxito : {tmp_wav} ({len(audio_data)} bytes)")

        # Lecture de la chanson
        if _skip_pc_audio:
            # Lecture Móvil (WebSocket)
            if CONNECTED_CLIENTS:
                try:
                    with open(tmp_wav, "rb") as f:
                        audio_b64 = base64.b64encode(f.read()).decode('utf-8')
                    message = json.dumps({"action": "jarvis_audio", "text": "🎵 [Musique générée par JARVIS] 🎵", "audio_b64": audio_b64})
                    await asyncio.gather(*[ws.send(message) for ws in CONNECTED_CLIENTS])
                except Exception as e:
                    print(f"[MOBILE] Error envoi musique : {e}")
            # Estimer la durée et attendre
            duration = (len(audio_data) / 2) / 24000
            await asyncio.sleep(duration + 1.0)
        elif pygame:
            # Lecture PC (Pygame)
            init_mixer()
            pygame.mixer.music.load(tmp_wav)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                if STOP_PARLER:
                    pygame.mixer.music.stop()
                    break
                # Animation de l'orbe
                t_audio = time.time() * 25
                base_vol = 0.5 + 0.3 * math.sin(t_audio) + 0.15 * math.sin(t_audio * 0.7)
                speak_volume = max(0.2, min(1.0, base_vol + _rnd.uniform(-0.15, 0.15)))
                await send_web_volume(speak_volume)
                await asyncio.sleep(0.05)
            # Reset volume
            await send_web_volume(0.0)
            
        # Supprimer le fichier temporaire après lecture
        try:
            os.remove(tmp_wav)
        except:
            pass

        return True

    except Exception as e:
        print(f"[MUSIQUE GEN] [ERREUR] Error : {e}")
        return False

async def hablar(texte):
    global is_speaking, speak_volume, STOP_PARLER, _skip_pc_audio, historique
    
    # Remplacement des acronymes avec points pour une prononciation naturelle
    texte = texte.replace("J.A.R.V.I.S.", "Jarvis").replace("J.A.R.V.I.S", "Jarvis").replace("j.a.r.v.i.s.", "Jarvis").replace("j.a.r.v.i.s", "Jarvis")
    
    # Remplacement du nom d'utilisateur
    texte = texte.replace("Christopher", USER_NAME).replace("christopher", USER_NAME.lower())
    
    # ENREGISTRER CE QUE JARVIS DIT DANS SA MÉMOIRE
    if historique and len(historique) > 0:
        dernier_texte_modele = historique[-1].parts[0].text
        if dernier_texte_modele != texte:
            historique.append(types.Content(role="model", parts=[types.Part(text=f"[Information retournée par l'action et énoncée à voix haute]: {texte}")]))

    # Découpage du texte en phrases pour le TTS fluide (sentence-by-sentence)
    import re
    # Découpage intelligent par ponctuations de fin de phrase
    raw_phrases = [p.strip() for p in re.split(r'(?<=[.!?])\s+', texte) if p.strip()]
    phrases = []
    current_phrase = ""
    for p in raw_phrases:
        if current_phrase:
            # Si la phrase en cours + la nouvelle fait moins de 450 caractères, on les fusionne pour un flux vocal continu sans aucun blanc
            if len(current_phrase) + len(p) < 450:
                current_phrase += " " + p
            else:
                phrases.append(current_phrase)
                current_phrase = p
        else:
            current_phrase = p
    if current_phrase:
        phrases.append(current_phrase)

    if not phrases:
        return

    is_speaking = True
    await send_web_state("speaking")
    speak_volume = 0.0
    
    # Dictionnaires de configuration des voix
    cfg = _cargar_config()
    voix_choisie = cfg.get("voice", "male")
    
    GEMINI_VOICE_MAP = {
        "gemini_fenrir":  "Fenrir",
        "gemini_aoede":   "Aoede",
        "gemini_charon":  "Charon",
        "gemini_kore":    "Kore",
        "gemini_leda":    "Leda",
        "gemini_orus":    "Orus",
        "gemini_puck":    "Puck",
        "gemini_zephyr":  "Zephyr",
    }
    
    VOICE_MAP = {
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
    
    created_files = []

    async def pre_generate(index):
        if index >= len(phrases):
            return None
        phrase = phrases[index]
        phrase_tts = phrase.replace("**", "").replace("*", "").replace("#", "").replace("`", "").strip()
        phrase_tts = _limpiar_emojis_para_tts(phrase_tts)
        if not phrase_tts:
            return None
        
        # Nom de fichier temporaire unique
        import time
        tmp_file = f"jarvis_tts_{int(time.time()*1000)}_{index}.mp3"
        created_files.append(tmp_file)
        
        try:
            # ── Voz Kokoro-TTS Local (100% Local & Studio) ───────────────────
            if voix_choisie.startswith("kokoro_"):
                tmp_wav = tmp_file.replace(".mp3", ".wav")
                created_files.append(tmp_wav)
                ok = await _kokoro_tts_a_archivo(phrase_tts, voix_choisie, tmp_wav)
                if ok:
                    return tmp_wav
                # Fallback Edge TTS si Kokoro n'est pas encore prêt
                voice_id = VOICE_MAP.get("male", "fr-FR-HenriNeural")
                communicate = edge_tts.Communicate(phrase_tts, voice=voice_id)
                await communicate.save(tmp_file)
                return tmp_file

            # ── Voz Gemini Live API (sans quota journalier) ──────────────────
            if voix_choisie in _GEMINI_LIVE_VOICE_MAP:
                live_voice_name = _GEMINI_LIVE_VOICE_MAP[voix_choisie]
                tmp_wav = tmp_file.replace(".mp3", ".wav")
                created_files.append(tmp_wav)
                clean_live_text = phrase_tts
                for char in ['"', "'", "«", "»", "\u201c", "\u201d", "-", "—", "–"]:
                    clean_live_text = clean_live_text.replace(char, " ")
                clean_live_text = clean_live_text.strip()
                ok = await _gemini_live_tts_a_archivo(clean_live_text, live_voice_name, tmp_wav)
                if ok:
                    return tmp_wav
                # Fallback Edge TTS si Live échoue (Voz 100% Française sans saut d'accent)
                masculines_live = {"gemini_live_fenrir", "gemini_live_puck", "gemini_live_charon", "gemini_live_orus"}
                voice_id = VOICE_MAP.get("male" if voix_choisie in masculines_live else "female", "fr-FR-HenriNeural")
                communicate = edge_tts.Communicate(phrase_tts, voice=voice_id)
                await communicate.save(tmp_file)
                return tmp_file

            # ── Voz Gemini TTS standard (quota 90/jour) ──────────────────────
            if voix_choisie in GEMINI_VOICE_MAP:
                gemini_voice_name = GEMINI_VOICE_MAP[voix_choisie]
                tmp_wav = tmp_file.replace(".mp3", ".wav")
                created_files.append(tmp_wav)
                
                # Limpieza des dialogues et questions pour éviter les erreurs de classification de l'API Gemini
                clean_gemini_text = phrase_tts
                for char in ['"', "'", "«", "»", "“", "”", "-", "—", "–"]:
                    clean_gemini_text = clean_gemini_text.replace(char, " ")
                clean_gemini_text = clean_gemini_text.strip()
                
                ok = await _gemini_tts_a_archivo(clean_gemini_text, gemini_voice_name, tmp_wav)
                if ok:
                    return tmp_wav
            
            # Fallback/Default Edge TTS (si Gemini échoue ou si non configuré)
            if voix_choisie.startswith("gemini_"):
                # Pour les voix Gemini, on redirige vers les équivalents 100% Français (Henri si masculin, Denise si féminin)
                masculines = {"gemini_fenrir", "gemini_charon", "gemini_orus", "gemini_puck",
                              "gemini_live_fenrir", "gemini_live_puck", "gemini_live_charon", "gemini_live_orus"}
                voice_id = VOICE_MAP.get("male" if voix_choisie in masculines else "female", "fr-FR-HenriNeural")
            else:
                voice_id = VOICE_MAP.get(voix_choisie, "fr-FR-HenriNeural")
                
            communicate = edge_tts.Communicate(phrase_tts, voice=voice_id)
            await communicate.save(tmp_file)
            return tmp_file
        except Exception as e:
            print(f"[TTS PREGEN] Error phrase {index}: {e}")
        return None

    try:
        import time
        # Lancement de la pré-génération de la 1ère phrase
        current_file = await pre_generate(0)
        # Tâche en arrière-plan pour la 2ème phrase
        next_task = asyncio.create_task(pre_generate(1))
        
        _texte_complet_imprime = False
        
        for index, phrase in enumerate(phrases):
            if STOP_PARLER:
                break
                
            if not current_file:
                # Si l'audio a échoué à se générer, on affiche le texte et on attend un peu pour que l'utilisateur lise
                
                # Impression synchronisée dans le terminal au moment exact où le texte s'affiche
                if not _texte_complet_imprime:
                    print(f"[JARVIS] {texte}")
                    _texte_complet_imprime = True
                    
                await send_web_text(phrase)
                await asyncio.sleep(max(1.5, len(phrase.split()) * 0.35))
                # Préparation de l'itération suivante
                current_file = await next_task
                next_task = asyncio.create_task(pre_generate(index + 2))
                continue

            # 1. Envoyer le texte de la phrase en cours (affichage immédiat synchronisé)
            await send_web_text(phrase)

            # Impression synchronisée dans le terminal au moment exact où l'audio va se jouer
            if not _texte_complet_imprime:
                print(f"[JARVIS] {texte}")
                _texte_complet_imprime = True

            # 2. Jouer l'audio
            if _skip_pc_audio:
                # Lecture Móvil (WebSocket)
                print(f"[MOBILE] Envoi audio au mobile : {phrase}")
                if CONNECTED_CLIENTS:
                    try:
                        import base64
                        import json
                        with open(current_file, "rb") as f:
                            audio_b64 = base64.b64encode(f.read()).decode('utf-8')
                        message = json.dumps({"action": "jarvis_audio", "text": phrase, "audio_b64": audio_b64})
                        await asyncio.gather(*[ws.send(message) for ws in CONNECTED_CLIENTS])
                    except Exception as e:
                        print(f"[MOBILE] Error envoi audio : {e}")
                # Estimer la durée de lecture sur mobile et attendre
                duration = max(1.5, len(phrase.split()) * 0.38)
                await asyncio.sleep(duration)
            elif pygame:
                # Lecture PC (Pygame)
                init_mixer()
                pygame.mixer.music.load(current_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    if STOP_PARLER:
                        pygame.mixer.music.stop()
                        break
                    
                    # Simulation d'animation d'orbe vocale réaliste
                    t_audio = time.time() * 20
                    base_vol = 0.4 + 0.3 * math.sin(t_audio) + 0.2 * math.sin(t_audio * 0.5)
                    speak_volume = max(0.1, min(1.0, base_vol + random.uniform(-0.1, 0.1)))
                    await send_web_volume(speak_volume)
                    await asyncio.sleep(0.05)
            
            # Nettoyer l'audio en cours de lecture
            try:
                if pygame and pygame.mixer.get_init():
                    pygame.mixer.music.unload()
            except:
                pass
            try:
                if os.path.exists(current_file):
                    os.remove(current_file)
            except:
                pass

            # Récupérer la tâche suivante déjà pré-générée en tâche de fond
            current_file = await next_task
            next_task = asyncio.create_task(pre_generate(index + 2))

    except Exception as e:
        print(f"Error boucle hablar: {e}")
    finally:
        # Nettoyage final
        speak_volume = 0.0
        is_speaking  = False
        STOP_PARLER  = False
        try:
            if pygame and pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
        except:
            pass
        # Supprimer tous les fichiers temporaires créés
        for f in created_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except:
                pass
        await send_web_state("idle")

builtins.hablar = hablar

# Nuevos módulos extraídos
from actions.file_manager import *
builtins.resoudre_chemin = resoudre_chemin

from core.memory_manager import *
from core.memory_manager import _charger_historique_recent, _sauvegarder_echange_conv

from actions.spotify_controller import *
builtins.spotify_lancer_playlist = spotify_lancer_playlist

from actions.deezer_controller import *
from actions.app_launcher import *
from actions.app_launcher import _fermer_app, _boulot_lancer, _APPS_CATALOGUE, _charger_custom_apps
builtins._APPS_CATALOGUE = _APPS_CATALOGUE
try:
    _charger_custom_apps()
    print("[DÉMARRAGE] Aplicaciones personalizadas cargadas con éxito.")
except Exception as e:
    print(f"[DÉMARRAGE] Error chargement applications personnalisées : {e}")

from actions.google_services import *
from actions.vision_module import *
from actions.sports_web import *
from actions.antivirus_scanner import executer_scan_antivirus
from actions.restaurant_helper import rechercher_restaurants_proches, obtenir_ville_par_ip
import actions.obsidian_helper as obsidian_helper
from actions.uninstaller_helper import list_installed_programs, scan_file_leftovers, scan_registry_leftovers, run_uninstall_process, clean_leftover_item
from actions.iptv_player import handle_iptv_ws_message

# --- Module musique multi-genres JARVIS ---
try:
    from actions.jarvis_music import JarvisMusic as _JarvisMusic, resoudre_genre as _resoudre_genre, GENRES as _MUSIC_GENRES
    _jarvis_music_instance = None  # instancié à la première utilisation
    _JARVIS_MUSIC_OK = True
except ImportError:
    _JARVIS_MUSIC_OK = False
    print("[ADVERTENCIA] jarvis_music.py introuvable — commandes musicales multi-genres désactivées.")
from ha_config import handle_ha_ws_message
from actions.youtube_api import (
    yt_infos_video, yt_chercher_multi, yt_trending,
    yt_infos_chaine, yt_resumer_video, yt_dernieres_videos,
)
USER_LOCATION_GPS = None
LAST_SHOWN_RESTAURANTS = []

BACKGROUND_TASKS = set()

def lancer_tache_arriere_plan(coro):
    if WEB_LOOP and WEB_LOOP.is_running():
        try:
            return asyncio.run_coroutine_threadsafe(coro, WEB_LOOP)
        except Exception as e:
            print(f"[JARVIS] Error run_coroutine_threadsafe : {e}")
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(coro)
        BACKGROUND_TASKS.add(task)
        task.add_done_callback(BACKGROUND_TASKS.discard)
        return task
    except RuntimeError:
        pass

# ── Winget System Upgrade Helpers ──────────────────────────────────────────
def _limpiar_version_winget(v):
    v = v.strip().lower()
    if v.startswith('v'):
        v = v[1:]
    if v.startswith('.'):
        v = v[1:]
    return v.strip()

def _version_es_mayor_o_igual(installed, available):
    inst_clean = _limpiar_version_winget(installed)
    avail_clean = _limpiar_version_winget(available)
    if inst_clean == avail_clean:
        return True
    try:
        import re
        inst_parts = [int(x) for x in re.split(r'[^0-9]', inst_clean) if x]
        avail_parts = [int(x) for x in re.split(r'[^0-9]', avail_clean) if x]
        for i in range(max(len(inst_parts), len(avail_parts))):
            p1 = inst_parts[i] if i < len(inst_parts) else 0
            p2 = avail_parts[i] if i < len(avail_parts) else 0
            if p1 > p2:
                return True
            elif p1 < p2:
                return False
        return True
    except Exception:
        pass
    return inst_clean == avail_clean

def listar_actualizaciones_winget():
    try:
        import subprocess
        res = subprocess.run(["winget", "upgrade"], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=20)
        stdout = res.stdout
    except subprocess.TimeoutExpired:
        print("[WINGET] winget upgrade ha expirado (timeout).")
        return []
    except Exception as e:
        try:
            res = subprocess.run(["winget", "upgrade"], capture_output=True, text=True, encoding="cp1252", errors="ignore", timeout=20)
            stdout = res.stdout
        except Exception as e2:
            print(f"[WINGET] Error d'exécution de winget: {e2}")
            return []

    lines = stdout.splitlines()
    header_idx = -1
    for idx, line in enumerate(lines):
        if "-------------------" in line or "======" in line:
            header_idx = idx - 1
            break
            
    if header_idx == -1:
        print("[WINGET] No se encontró encabezado o sistema ya actualizado.")
        return []
        
    headers_line = lines[header_idx]
    
    idx_id = headers_line.find("ID")
    idx_ver = headers_line.find("Version")
    idx_disp = headers_line.find("Disponible")
    if idx_disp == -1:
        idx_disp = headers_line.find("Available")
    idx_src = headers_line.find("Source")
    
    if idx_id == -1 or idx_ver == -1 or idx_disp == -1 or idx_src == -1:
        print("[WINGET] Indexación de columnas imposible.")
        return []
        
    results = []
    for line in lines[header_idx+2:]:
        if not line.strip():
            continue
        if any(term in line.lower() for term in ["mise à niveau", "upgrade", "package", "numéro", "version"]):
            continue
            
        name = line[:idx_id].strip()
        pkg_id = line[idx_id:idx_ver].strip()
        version = line[idx_ver:idx_disp].strip()
        available = line[idx_disp:idx_src].strip()
        source = line[idx_src:].strip()
        
        if pkg_id and available:
            if _version_es_mayor_o_igual(version, available):
                continue
            results.append({
                "name": name,
                "id": pkg_id,
                "version": version,
                "available": available,
                "source": source
            })
            
    return results

def ejecutar_actualizacion_winget_sync(args, loop, websocket_client):
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
        for line in proc.stdout:
            text = line.strip()
            if text:
                asyncio.run_coroutine_threadsafe(
                    websocket_client.send(json.dumps({
                        "type": "winget_upgrade_progress",
                        "status": "running",
                        "log": text + "\n"
                    })),
                    loop
                )
        proc.wait()
        asyncio.run_coroutine_threadsafe(
            websocket_client.send(json.dumps({
                "type": "winget_upgrade_progress",
                "status": "complete",
                "returncode": proc.returncode
            })),
            loop
        )
        return proc.returncode == 0
    except Exception as e:
        print(f"[WINGET] Error d'exécution de winget upgrade: {e}")
        asyncio.run_coroutine_threadsafe(
            websocket_client.send(json.dumps({
                "type": "winget_upgrade_progress",
                "status": "complete",
                "returncode": -1,
                "log": f"Error: {str(e)}\n"
            })),
            loop
        )
        return False

def lanzar_busqueda_restaurantes_fondo(location, lat, lng, exclure, is_others=False):
    def worker():
        try:
            if WEB_LOOP and WEB_LOOP.is_running():
                asyncio.run_coroutine_threadsafe(send_web_state("searching"), WEB_LOOP)
            
            results = rechercher_restaurants_proches(location, lat, lng, exclure)
            
            async def _finaliser():
                try:
                    global LAST_SHOWN_RESTAURANTS
                    if results:
                        for r in results:
                            if r["nom"] not in LAST_SHOWN_RESTAURANTS:
                                LAST_SHOWN_RESTAURANTS.append(r["nom"])
                        if len(LAST_SHOWN_RESTAURANTS) > 18:
                            LAST_SHOWN_RESTAURANTS = LAST_SHOWN_RESTAURANTS[-18:]
                        
                        msg = json.dumps({
                            "type": "show_restaurants",
                            "location": location,
                            "restaurants": results
                        })
                        if CONNECTED_CLIENTS:
                            await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                    else:
                        await hablar("Désolé Christopher, je n'ai pas pu trouver de restaurants à proximité.")
                except Exception as e:
                    print(f"[RESTAURANT] Error finalisation : {e}")
                finally:
                    await send_web_state("idle")
            
            if WEB_LOOP and WEB_LOOP.is_running():
                asyncio.run_coroutine_threadsafe(_finaliser(), WEB_LOOP)
        except Exception as err:
            print(f"[RESTAURANT THREAD ERROR] {err}")
            if WEB_LOOP and WEB_LOOP.is_running():
                asyncio.run_coroutine_threadsafe(send_web_state("idle"), WEB_LOOP)

    threading.Thread(target=worker, daemon=True).start()



# --- NVIDIA Nemotron ASR (Canary-1B) : optionnel ---
_nemotron_asr_ok = False
NemotronASR = None

# Détection automatique paresseuse/transparente au démarrage
# (vérification ultra-rapide sans charger les modules torch/nemo pour un boot instantané)
try:
    _model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "canary-1b.nemo")
    _model_exists = os.path.exists(_model_path) and os.path.getsize(_model_path) == 4071127040
    
    import importlib.util
    _packages_installed = (
        importlib.util.find_spec("torch") is not None and 
        importlib.util.find_spec("nemo") is not None
    )
    _nemotron_asr_ok = _model_exists and _packages_installed
except Exception:
    _nemotron_asr_ok = False

_nemotron_install_task = None
_nemotron_uninstall_task = None

def detectar_gpu_nvidia():
    try:
        import subprocess
        res = subprocess.run(["nvidia-smi"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        if res.returncode == 0:
            return True
    except Exception:
        pass
    return False

def ejecutar_pip_install_sync(args, loop, websocket_client, stage, progress):
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
        for line in proc.stdout:
            text = line.strip()
            if text:
                # Envoyer de façon thread-safe au client WebSocket
                asyncio.run_coroutine_threadsafe(
                    websocket_client.send(json.dumps({
                        "type": "nemotron_install_progress",
                        "status": "installing",
                        "stage": stage,
                        "progress": progress,
                        "log": text + "\n"
                    })),
                    loop
                )
        proc.wait()
        return proc.returncode == 0
    except Exception as e:
        print(f"[ASR] Error lors de l'exécution de pip: {e}")
        return False

def descargar_archivo_sync(url, dest_path, loop, websocket_client, stage, start_progress, end_progress):
    import requests
    import os
    import time
    
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    temp_dest = dest_path + ".tmp"
    
    try:
        print(f"[ASR] Descarga del modelo de {url} vers {dest_path}...")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        last_update_time = 0
        
        with open(temp_dest, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Limiter le taux d'envoi à environ 2 messages par seconde
                    current_time = time.time()
                    if current_time - last_update_time >= 0.5 or downloaded == total_size:
                        last_update_time = current_time
                        
                        if total_size > 0:
                            pct = downloaded / total_size
                            progress = start_progress + int(pct * (end_progress - start_progress))
                            mb_downloaded = round(downloaded / (1024 * 1024), 1)
                            mb_total = round(total_size / (1024 * 1024), 1)
                            log_text = f"Descarga del modelo : {mb_downloaded} Mo / {mb_total} Mo ({round(pct * 100, 1)}%)\r"
                        else:
                            progress = start_progress
                            mb_downloaded = round(downloaded / (1024 * 1024), 1)
                            log_text = f"Descarga del modelo : {mb_downloaded} Mo...\r"
                        
                        asyncio.run_coroutine_threadsafe(
                            websocket_client.send(json.dumps({
                                "type": "nemotron_install_progress",
                                "status": "installing",
                                "stage": stage,
                                "progress": progress,
                                "log": log_text
                            })),
                            loop
                        )
        
        # Saut de ligne final dans les logs
        asyncio.run_coroutine_threadsafe(
            websocket_client.send(json.dumps({
                "type": "nemotron_install_progress",
                "status": "installing",
                "stage": stage,
                "progress": end_progress,
                "log": "\nDescarga del modelo terminé avec succès.\n"
            })),
            loop
        )
        
        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(temp_dest, dest_path)
        return True
    except Exception as e:
        print(f"[ASR] Error lors du téléchargement : {e}")
        if os.path.exists(temp_dest):
            try:
                os.remove(temp_dest)
            except Exception:
                pass
        return False

def ejecutar_pip_uninstall_sync(args, loop, websocket_client, stage):
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
        for line in proc.stdout:
            text = line.strip()
            if text:
                asyncio.run_coroutine_threadsafe(
                    websocket_client.send(json.dumps({
                        "type": "nemotron_uninstall_progress",
                        "status": "uninstalling",
                        "stage": stage,
                        "progress": 70,
                        "log": text + "\n"
                    })),
                    loop
                )
        proc.wait()
        return proc.returncode == 0
    except Exception as e:
        print(f"[ASR] Error lors de l'exécution de pip uninstall: {e}")
        return False

async def instalar_dependencias_nemotron(websocket_client):
    global _nemotron_install_task, _nemotron_asr_ok, NemotronASR
    loop = asyncio.get_running_loop()
    try:
        has_gpu = detectar_gpu_nvidia()
        gpu_str = "avec support GPU CUDA" if has_gpu else "mode CPU uniquement (lent)"
        print(f"[ASR] Inicio de la instalación automatique des dépendances ({gpu_str})...")
        
        await websocket_client.send(json.dumps({
            "type": "nemotron_install_progress",
            "status": "started",
            "stage": "Detección del hardware...",
            "progress": 5,
            "log": f"NVIDIA GPU détecté: {has_gpu}\nInicio de la instalación...\n"
        }))

        # 1. Installer PyTorch
        await websocket_client.send(json.dumps({
            "type": "nemotron_install_progress",
            "status": "installing",
            "stage": "Paso 1/3 : Instalación de PyTorch...",
            "progress": 10,
            "log": "Inicio de la instalación de PyTorch...\n"
        }))

        import sys
        if has_gpu:
            pip_args = [sys.executable, "-m", "pip", "install", "torch", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu124"]
        else:
            pip_args = [sys.executable, "-m", "pip", "install", "torch", "torchaudio"]

        success = await loop.run_in_executor(
            None,
            ejecutar_pip_install_sync,
            pip_args,
            loop,
            websocket_client,
            "Paso 1/3 : Instalación de PyTorch...",
            20
        )
        
        if not success:
            raise Exception("L'installation de PyTorch a échoué. Veuillez consulter les logs.")

        # 2. Installer NeMo Toolkit
        await websocket_client.send(json.dumps({
            "type": "nemotron_install_progress",
            "status": "installing",
            "stage": "Paso 2/3 : Instalación de NeMo Toolkit...",
            "progress": 40,
            "log": "\nPyTorch instalado con éxito.\nLancement de l'installation de NeMo Toolkit (ASR)...\n"
        }))

        if has_gpu:
            pip_args = [sys.executable, "-m", "pip", "install", "nemo_toolkit[asr]", "--extra-index-url", "https://download.pytorch.org/whl/cu124"]
        else:
            pip_args = [sys.executable, "-m", "pip", "install", "nemo_toolkit[asr]"]
        success = await loop.run_in_executor(
            None,
            ejecutar_pip_install_sync,
            pip_args,
            loop,
            websocket_client,
            "Paso 2/3 : Instalación de NeMo Toolkit...",
            50
        )
        
        if not success:
            raise Exception("L'installation de NeMo Toolkit a échoué. Veuillez consulter les logs.")

        # 3. Télécharger le modèle canary-1b.nemo
        await websocket_client.send(json.dumps({
            "type": "nemotron_install_progress",
            "status": "installing",
            "stage": "Paso 3/3 : Descarga del modelo Canary-1B (~4 Go)...",
            "progress": 65,
            "log": "\nNeMo Toolkit instalado.\nLancement du téléchargement du modèle local Canary-1B (~4 Go)...\n"
        }))

        dest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "canary-1b.nemo")
        # Vérification si le modèle est déjà présent et valide
        if os.path.exists(dest_path) and os.path.getsize(dest_path) == 4071127040:
            await websocket_client.send(json.dumps({
                "type": "nemotron_install_progress",
                "status": "installing",
                "stage": "Paso 3/3 : Descarga del modelo Canary-1B...",
                "progress": 90,
                "log": "Le modèle est déjà présent localement (taille vérifiée). Paso ignorée.\n"
            }))
        else:
            url = "https://huggingface.co/nvidia/canary-1b/resolve/main/canary-1b.nemo"
            success = await loop.run_in_executor(
                None,
                descargar_archivo_sync,
                url,
                dest_path,
                loop,
                websocket_client,
                "Paso 3/3 : Descarga del modelo Canary-1B...",
                65,
                90
            )
            if not success:
                raise Exception("Le téléchargement du modèle Canary-1B a échoué.")

        # 4. Finalisation et vérification des imports
        await websocket_client.send(json.dumps({
            "type": "nemotron_install_progress",
            "status": "installing",
            "stage": "Verificación de la instalación...",
            "progress": 95,
            "log": "Verificación de la compatibilidad des importations...\n"
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
            _is_installed = nemotron_asr.NemotronASR.is_nemo_installed()
            _model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "canary-1b.nemo")
            _nemotron_asr_ok = _is_installed and os.path.exists(_model_path) and os.path.getsize(_model_path) == 4071127040
            NemotronASR = nemotron_asr.NemotronASR
        except Exception as e:
            raise Exception(f"Error d'importation après installation : {e}")

        if _nemotron_asr_ok:
            await websocket_client.send(json.dumps({
                "type": "nemotron_install_progress",
                "status": "success",
                "stage": "Instalación terminada con éxito !",
                "progress": 100,
                "log": "Felicitaciones ! NVIDIA Nemotron ASR est listo para usar.\n"
            }))
            print("[ASR] Instalación automática terminada con éxito.")
            result_state = {
                "type": "nemotron_asr_state",
                "enabled": False,
                "gpu_available": has_gpu,
                "warnings": [],
                "error": None
            }
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(json.dumps(result_state)) for ws in CONNECTED_CLIENTS], return_exceptions=True)
        else:
            raise Exception("L'installation a réussi mais NeMo n'est toujours pas importable.")

    except Exception as e:
        error_msg = str(e)
        print(f"[ASR] ✖ Fallo instalación automática : {error_msg}")
        
        manual_guide = (
            f"\n[ERREUR] {error_msg}\n\n"
            "=======================================================================\n"
            "                 GUIDE D'INSTALLATION MANUELLE DE NEMOTRON\n"
            "=======================================================================\n"
            "Si l'installation automatique a échoué, vous pouvez l'installer manuellement :\n\n"
            "1. Créez le dossier 'models' s'il n'existe pas, à la racine du projet J.A.R.V.I.S :\n"
            "   -> Carpeta destino : [chemin_jarvis]/models\n\n"
            "2. Descarga le fichier du modèle Canary-1B (~4 Go) depuis Hugging Face :\n"
            "   -> URL : https://huggingface.co/nvidia/canary-1b/resolve/main/canary-1b.nemo\n"
            "   -> Guárdalo sous le nom EXACT : canary-1b.nemo\n"
            "   -> Muévelo dans le dossier 'models' créé ci-dessus.\n\n"
            "3. Abre una terminal (CMD) dans le dossier racine de J.A.R.V.I.S :\n"
            "   a) Activa el entorno virtual local et installez PyTorch :\n"
            "      - Pour support GPU NVIDIA CUDA (Recommandé si vous avez un GPU Nvidia):\n"
            "        .\\venv\\Scripts\\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124\n"
            "      - Pour CPU uniquement :\n"
            "        .\\venv\\Scripts\\python.exe -m pip install torch torchaudio\n"
            "   b) Installez le package NeMo Toolkit :\n"
            "      .\\venv\\Scripts\\python.exe -m pip install nemo_toolkit[asr]\n\n"
            "4. Reinicia J.A.R.V.I.S. Le système detectará automáticamente l'installation !\n"
            "=======================================================================\n"
        )
        
        await websocket_client.send(json.dumps({
            "type": "nemotron_install_progress",
            "status": "error",
            "stage": "Échec de l'installation",
            "progress": 0,
            "log": manual_guide
        }))
    finally:
        _nemotron_install_task = None

async def desinstalar_dependencias_nemotron(websocket_client):
    global _nemotron_uninstall_task, _nemotron_asr_ok, NemotronASR, NEMOTRON_ASR_ENABLED, _nemotron_instance
    loop = asyncio.get_running_loop()
    try:
        print("[ASR] Début de la désinstallation de Nemotron ASR...")
        
        # 1. Arrêter Nemotron
        NEMOTRON_ASR_ENABLED = False
        if _nemotron_instance:
            print("[ASR] Libération de l'instance Nemotron...")
            await asyncio.to_thread(_nemotron_instance.liberer)
            _nemotron_instance = None

        await websocket_client.send(json.dumps({
            "type": "nemotron_uninstall_progress",
            "status": "started",
            "stage": "Desinstalación en curso...",
            "progress": 5,
            "log": "Modelo detenido y liberado.\n"
        }))

        # 2. Supprimer le fichier de modèle
        dest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "canary-1b.nemo")
        if os.path.exists(dest_path):
            await websocket_client.send(json.dumps({
                "type": "nemotron_uninstall_progress",
                "status": "uninstalling",
                "stage": "Paso 1/2 : Eliminación del modelo...",
                "progress": 20,
                "log": f"Eliminación del modelo local (~4 Go) à {dest_path}...\n"
            }))
            try:
                os.remove(dest_path)
                # Supprimer le dossier models s'il est vide
                models_dir = os.path.dirname(dest_path)
                if os.path.exists(models_dir) and not os.listdir(models_dir):
                    os.rmdir(models_dir)
                await websocket_client.send(json.dumps({
                    "type": "nemotron_uninstall_progress",
                    "status": "uninstalling",
                    "stage": "Paso 1/2 : Eliminación del modelo...",
                    "progress": 40,
                    "log": "Fichier du modèle supprimé.\n"
                }))
            except Exception as e:
                await websocket_client.send(json.dumps({
                    "type": "nemotron_uninstall_progress",
                    "status": "uninstalling",
                    "stage": "Paso 1/2 : Eliminación del modelo...",
                    "progress": 40,
                    "log": f"Avertissement lors de la suppression du modèle : {e}\n"
                }))
        else:
            await websocket_client.send(json.dumps({
                "type": "nemotron_uninstall_progress",
                "status": "uninstalling",
                "stage": "Paso 1/2 : Eliminación del modelo...",
                "progress": 40,
                "log": "No se encontró modelo local à supprimer.\n"
            }))

        # 3. Désinstaller les dépendances pip
        await websocket_client.send(json.dumps({
            "type": "nemotron_uninstall_progress",
            "status": "uninstalling",
            "stage": "Paso 2/2 : Desinstalación de paquetes...",
            "progress": 50,
            "log": "Lancement de la désinstallation de nemo-toolkit, torch et torchaudio...\n"
        }))

        import sys
        pip_args = [sys.executable, "-m", "pip", "uninstall", "-y", "nemo-toolkit", "torch", "torchaudio"]
        
        success = await loop.run_in_executor(
            None,
            ejecutar_pip_uninstall_sync,
            pip_args,
            loop,
            websocket_client,
            "Paso 2/2 : Desinstalación de paquetes..."
        )
        
        if not success:
            await websocket_client.send(json.dumps({
                "type": "nemotron_uninstall_progress",
                "status": "uninstalling",
                "stage": "Paso 2/2 : Desinstalación de paquetes...",
                "progress": 85,
                "log": "Désinstallation pip incomplète ou terminée avec des avertissements.\n"
            }))
        else:
            await websocket_client.send(json.dumps({
                "type": "nemotron_uninstall_progress",
                "status": "uninstalling",
                "stage": "Paso 2/2 : Desinstalación de paquetes...",
                "progress": 85,
                "log": "Paquetes pip desinstalados con éxito.\n"
            }))

        # 4. Finalisation
        await websocket_client.send(json.dumps({
            "type": "nemotron_uninstall_progress",
            "status": "uninstalling",
            "stage": "Finalisation...",
            "progress": 90,
            "log": "Actualización de la configuración de Jarvis...\n"
        }))

        _nemotron_asr_ok = False
        NemotronASR = None
        _guardar_config({"nemotron_asr_enabled": False})

        await websocket_client.send(json.dumps({
            "type": "nemotron_uninstall_progress",
            "status": "success",
            "stage": "Desinstalación terminada con éxito !",
            "progress": 100,
            "log": "Désinstallation terminée. Regreso al modo Google Speech Recognition.\n"
        }))
        print("[ASR] Desinstalación automática terminada con éxito.")

        result_state = {
            "type": "nemotron_asr_state",
            "enabled": False,
            "gpu_available": detectar_gpu_nvidia(),
            "warnings": [],
            "error": None
        }
        if CONNECTED_CLIENTS:
            await asyncio.gather(*[ws.send(json.dumps(result_state)) for ws in CONNECTED_CLIENTS], return_exceptions=True)

    except Exception as e:
        print(f"[ASR] ✖ Fallo desinstalación automática : {e}")
        await websocket_client.send(json.dumps({
            "type": "nemotron_uninstall_progress",
            "status": "error",
            "stage": "Échec de la désinstallation",
            "progress": 0,
            "log": f"\n[ERREUR] {str(e)}\n"
        }))
    finally:
        _nemotron_uninstall_task = None

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
# --- PyAudio (micro/reconnaissance vocale) : optionnel ---
try:
    import pyaudio
except ImportError:
    pyaudio = None
    print("[ADVERTENCIA] pyaudio no instalado — el micrófono estará desactivado.")
    print("  -> Para instalarlo : pip install pipwin && pipwin install pyaudio")
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

# Google APIs (Gmail, Drive, Calendar) : optionnels
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
    print("  -> Para instalarlo : pip install google-auth-oauthlib google-api-python-client")

# --- pycaw (volume systeme Windows) : optionnel ---
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    _pycaw_ok = True
except ImportError:
    _pycaw_ok = False

# --- screen-brightness-control : optionnel ---
try:
    import screen_brightness_control as _sbc
    _sbc_ok = True
except ImportError:
    _sbc = None
    _sbc_ok = False

# --- PyWebView (fenetre native) : optionnel ---

try:
    import webview
    _WEBVIEW_OK = True
except ImportError:
    webview = None
    _WEBVIEW_OK = False

_WEBVIEW_WINDOW = None  # référence globale à la fenêtre pywebview

# --- CONFIGURATION VERSION & MAJ ---
CURRENT_VERSION = "9.5"
UPDATE_JSON_URL = "https://www.techenclair.fr/updates/jarvis_update.json"
DERNIERE_MAJ_INFO = None  # Stocke l'info si une MAJ est détectée

# Chargement des variables d'environnement
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

LOCAL_IP = get_local_ip()

GEMINI_API_KEY       = ""
YOUTUBE_API_KEY      = ""
XAI_API_KEY          = ""
SERPAPI_API_KEY      = ""
GROQ_API_KEY         = ""
ANTHROPIC_API_KEY    = ""
MISTRAL_API_KEY      = ""
SPOTIFY_MUSIQUE_URI  = os.getenv("SPOTIFY_MUSIQUE_URI", "")
builtins.SPOTIFY_MUSIQUE_URI = SPOTIFY_MUSIQUE_URI
YOUTUBE_MUSIQUE_URL  = os.getenv("YOUTUBE_MUSIQUE_URL", "")
builtins.YOUTUBE_MUSIQUE_URL = YOUTUBE_MUSIQUE_URL

def _charger_musique_lien() -> str:
    try:
        import json as _j
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        with open(_p, "r", encoding="utf-8") as _f:
            return _j.load(_f).get("musique_lien", "")
    except Exception:
        return ""

MUSIQUE_LIEN_PERSO = _charger_musique_lien()

# Validateur universel — une clé non renseignée = placeholder = agent ignoré
_API_PLACEHOLDERS = frozenset({"VOTRE_CLE_ICI", "Votre ID", "tu_id",
                                "VOTRE_TOKEN_ICI", "tu_token_ici", ""})
def _cle_valide(key):
    return bool(key) and str(key).strip() not in _API_PLACEHOLDERS

import builtins
builtins._cle_valide = _cle_valide

# Configuration domotique, météo et entités Home Assistant
from ha_config import (
    HA_URL, HA_HEADERS,
    VILLE_PAR_DEFAUT, LAT_PAR_DEFAUT, LON_PAR_DEFAUT,
    PIECES_LUMIERES, PIECES_PRISES, PIECES_CAPTEURS, PIECES_HUMIDITE,
    HA_TARIFS, APPAREILS_ENERGIE, APPAREILS_BATTERIE,
    COULEURS_MAP, CODES_METEO,
    ha_appeler_service, ha_get_etat, ha_get_calendrier,
    ha_lumiere, ha_interrupteur, ha_thermostat, ha_scene, ha_verrou,
    geocoder_ville, get_meteo_actuelle, get_meteo_ha, get_alertes_meteo,
    get_meteo_structuree,
)

gemini_actif = False
client = None
grok_client = None
groq_client = None
anthropic_client = None
mistral_client = None

def _guardar_env(data: dict) -> None:
    """Met à jour le fichier .env et met à jour os.environ en temps réel."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    lines = []
    existing_keys = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for idx, line in enumerate(lines):
            line_strip = line.strip()
            if line_strip and not line_strip.startswith("#") and "=" in line_strip:
                key, _ = line_strip.split("=", 1)
                existing_keys[key.strip()] = idx

    for key, value in data.items():
        os.environ[key] = str(value)
        line_content = f"{key}={value}\n"
        if key in existing_keys:
            lines[existing_keys[key]] = line_content
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] = lines[-1] + "\n"
            lines.append(line_content)
            existing_keys[key] = len(lines) - 1

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"[CONFIG ENV] .env mis à jour avec : {list(data.keys())}")
    except Exception as e:
        print(f"[CONFIG ENV] Error écriture .env : {e}")

def recharger_clients_ia():
    global GEMINI_API_KEY, YOUTUBE_API_KEY, XAI_API_KEY, SERPAPI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY, MISTRAL_API_KEY, OPENAI_API_KEY
    global gemini_actif, client, grok_client, groq_client, anthropic_client, mistral_client, openai_client
    
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
    YOUTUBE_API_KEY   = os.getenv("YOUTUBE_API_KEY", "")
    XAI_API_KEY       = os.getenv("XAI_API_KEY", "")
    SERPAPI_API_KEY   = os.getenv("SERPAPI_API_KEY", "")
    GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    MISTRAL_API_KEY   = os.getenv("MISTRAL_API_KEY", "")
    OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
    
    cfg = _cargar_config()
    gemini_enabled    = cfg.get("api_gemini_enabled", True)
    groq_enabled      = cfg.get("api_groq_enabled", True)
    grok_enabled      = cfg.get("api_grok_enabled", True)
    anthropic_enabled = cfg.get("api_anthropic_enabled", True)
    mistral_enabled   = cfg.get("api_mistral_enabled", True)
    openai_enabled    = cfg.get("api_openai_enabled", True)

    gemini_key_to_use = GEMINI_API_KEY if gemini_enabled else ""
    groq_key_to_use   = GROQ_API_KEY if groq_enabled else ""
    grok_key_to_use   = XAI_API_KEY if grok_enabled else ""
    anthropic_key_to_use = ANTHROPIC_API_KEY if anthropic_enabled else ""
    mistral_key_to_use = MISTRAL_API_KEY if mistral_enabled else ""
    openai_key_to_use  = OPENAI_API_KEY if openai_enabled else ""
    
    gemini_actif = _cle_valide(gemini_key_to_use)
    if gemini_actif:
        import google.genai as _genai
        client = _genai.Client(api_key=gemini_key_to_use)
        builtins.client = client
    else:
        client = None
        builtins.client = None
        
    if _cle_valide(grok_key_to_use):
        grok_client = OpenAI(api_key=grok_key_to_use, base_url="https://api.x.ai/v1")
    else:
        grok_client = None
        
    if _cle_valide(groq_key_to_use):
        groq_client = OpenAI(api_key=groq_key_to_use, base_url="https://api.groq.com/openai/v1")
    else:
        groq_client = None
        
    if _anthropic_lib and _cle_valide(anthropic_key_to_use):
        anthropic_client = _anthropic_lib.Anthropic(api_key=anthropic_key_to_use)
    else:
        anthropic_client = None

    if _cle_valide(mistral_key_to_use):
        mistral_client = OpenAI(api_key=mistral_key_to_use, base_url="https://api.mistral.ai/v1")
    else:
        mistral_client = None
        
    if _cle_valide(openai_key_to_use):
        openai_client = OpenAI(api_key=openai_key_to_use)
    else:
        openai_client = None
        
    print("[IA CLIENTS] Clients IA rechargés dynamiquement.")

# Lancement initial des clients
recharger_clients_ia()

MODELS_LIST     = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash", "gemini-2.5-pro", "gemini-2.0-flash-exp"]
CHOSEN_MODELS   = agent_model_manager.load_chosen_models()

import builtins
builtins.client = client
builtins.CHOSEN_MODELS = CHOSEN_MODELS

# Ollama (LLMs locaux — fallback 100% offline)
OLLAMA_URL      = "http://127.0.0.1:11434"
OLLAMA_MODELS   = ["mistral:instruct", "mistral", "llama3:8b", "llama3", "gemma4"]
KOKORO_URL      = "http://127.0.0.1:8880"


# ══════════════════════════════════════════════════════════════
#  GESTIONNAIRE DE QUOTAS API — Failover automatique
# ══════════════════════════════════════════════════════════════

class _QuotaExceededError(Exception):
    """Levée quand une API signale un quota ou rate-limit épuisé."""
    pass

class APIQuotaManager:
    """
    Gère le cooldown des APIs quand leur quota est épuisé.
    Détecte automatiquement les erreurs 429 / resource_exhausted / rate_limit.
    """

    # Durée de cooldown par API (secondes)
    COOLDOWNS = {
        "claude"  : 60,
        "gemini"  : 60,
        "grok"    : 60,
        "groq"    : 30,
        "mistral" : 60,
        "openai"  : 60,
        "mistral" : 30,
        "ollama"  : 10,
    }

    # Mots-clés indiquant un quota épuisé (insensible à la casse)
    QUOTA_KEYWORDS = [
        "429", "quota", "rate limit", "rate_limit", "ratelimit",
        "too many requests", "resource_exhausted", "resource exhausted",
        "exceeded", "tokens per", "requests per", "rateLimitExceeded",
        "quota_exceeded", "RATE_LIMIT_EXCEEDED", "insufficient_quota",
        "context_length_exceeded",
    ]

    def __init__(self):
        from datetime import datetime, timedelta
        self._datetime   = datetime
        self._timedelta  = timedelta
        self._cooldowns  = {}   # {api_name: datetime_disponible}
        self._hit_count  = {}   # {api_name: nb_fois_quota_atteint}

    def is_quota_error(self, error: Exception) -> bool:
        """Retourne True si l'erreur est liée à un quota/rate-limit."""
        err_str = str(error).lower()
        return any(kw.lower() in err_str for kw in self.QUOTA_KEYWORDS)

    def is_available(self, api_name: str) -> bool:
        """Retourne True si l'API est disponible (pas en cooldown)."""
        if api_name not in self._cooldowns:
            return True
        return self._datetime.now() >= self._cooldowns[api_name]

    def mark_quota_exceeded(self, api_name: str) -> None:
        """Place une API en cooldown après un quota épuisé."""
        duration = self.COOLDOWNS.get(api_name, 60)
        self._cooldowns[api_name] = self._datetime.now() + self._timedelta(seconds=duration)
        self._hit_count[api_name] = self._hit_count.get(api_name, 0) + 1
        print(f"[QUOTA] ⚠ {api_name.upper()} quota atteint — cooldown {duration}s "
              f"(total: {self._hit_count[api_name]} fois)")

    def remaining_cooldown(self, api_name: str) -> int:
        """Secondes restantes avant que l'API soit à nouveau disponible (0 si dispo)."""
        if self.is_available(api_name):
            return 0
        delta = self._cooldowns[api_name] - self._datetime.now()
        return max(0, int(delta.total_seconds()))

    def status(self) -> str:
        """Résumé du statut de toutes les APIs."""
        lines = []
        for api in self.COOLDOWNS:
            if not self.is_available(api):
                lines.append(f"  {api.upper()}: cooldown {self.remaining_cooldown(api)}s")
            else:
                lines.append(f"  {api.upper()}: disponible")
        return "\n".join(lines)

# Instance globale
_quota_mgr = APIQuotaManager()

CLAP_THRESHOLD = 1200
VIDEO_LANCEE   = False
MODE_IRON_MAN = False 

_age_line = f"- Age : {USER_AGE} ans\n" if USER_AGE else ""
CREATOR_INFO = (
    "INFORMATIONS SUR TON CREATEUR :\n"
    f"- Prenom : {USER_NAME}\n"
    + _age_line +
    "- Role : Ton createur et maitre\n"
    f"- Tu dois toujours l appeler {USER_NAME} avec respect "
    "mais aussi une pointe de sarcasme affectueux.\n"
)

EXTENSIONS = {
    "Images"   : [".jpg", ".jpeg", ".png", ".gif", ".bmp",
                  ".tiff", ".tif", ".webp", ".svg", ".ico",
                  ".heic", ".raw", ".cr2", ".nef"],
    "Videos"   : [".mp4", ".avi", ".mkv", ".mov", ".wmv",
                  ".flv", ".webm", ".m4v", ".mpg", ".mpeg"],
    "Musique"  : [".mp3", ".wav", ".flac", ".aac", ".ogg",
                  ".wma", ".m4a", ".opus", ".aiff"],
    "Documents": [".pdf", ".doc", ".docx", ".xls", ".xlsx",
                  ".ppt", ".pptx", ".txt", ".odt", ".ods",
                  ".odp", ".rtf", ".csv", ".epub"],
    "Archives" : [".zip", ".rar", ".7z", ".tar", ".gz",
                  ".bz2", ".xz", ".iso"],
    "Code"     : [".py", ".js", ".html", ".css", ".java",
                  ".cpp", ".c", ".h", ".cs", ".php",
                  ".json", ".xml", ".yaml", ".yml",
                  ".sh", ".bat", ".ps1", ".ts", ".jsx",
                  ".tsx", ".vue", ".go", ".rs", ".rb"],
    "Executables": [".exe", ".msi", ".apk", ".dmg", ".deb"],
}

dossier_courant = None
# ==========================================
# ==========================================
# WEBSOCKET
# ==========================================
CONNECTED_CLIENTS = set()
builtins.CONNECTED_CLIENTS = CONNECTED_CLIENTS
interface_deja_connectee = False
_skip_pc_audio = False  # True quand la commande vient du mobile (le tél gère son propre TTS)
PENDING_SCREEN_CAPTURES = {}
PENDING_CAMERA_CAPTURES = {}
WEBCAM_ACTIVE = False
builtins.WEBCAM_ACTIVE = WEBCAM_ACTIVE

def _instalar_jarvis_os(path, websocket, loop):
    import subprocess
    import time
    image_name = "lscr.io/linuxserver/webtop:ubuntu-xfce"
    
    def send_progress(status, pct, log_msg=None, done=False, port=3000):
        msg = {"type": "jarvis_os_install_progress", "status": status, "progress": pct, "done": done, "port": port}
        if log_msg: msg["log"] = log_msg
        asyncio.run_coroutine_threadsafe(websocket.send(json.dumps(msg)), loop)

    try:
        import shutil
        import os
        
        # 0. Vérification de WSL
        wsl_installed = True
        if not shutil.which("wsl"):
            wsl_installed = False
        else:
            wsl_res = subprocess.run(["wsl", "--status"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            if wsl_res.returncode != 0:
                wsl_installed = False
                
        if not wsl_installed:
            send_progress("Installation de WSL (Prérequis)...", 2, "WSL n'est pas installé. Une fenêtre Administrateur va s'ouvrir pour l'installer.")
            send_progress("Installation de WSL (Prérequis)...", 2, "⚠️ VEUILLEZ ACCEPTER L'UAC (OUI). L'installation prendra quelques minutes.")
            
            wsl_cmd = ["powershell", "-Command", "Start-Process powershell -ArgumentList '-NoProfile -Command wsl --install --no-distribution' -Verb RunAs -Wait"]
            subprocess.run(wsl_cmd, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            
            send_progress("Redémarrage requis !", 2, "L'installation de WSL est terminée. VOUS DEVEZ REDÉMARRER VOTRE PC MAINTENANT.")
            send_progress("Redémarrage requis !", 2, "Après le redémarrage, relancez JARVIS et recommencez l'installation.")
            return

        # 1. Vérification de Docker
        if not shutil.which("docker"):
            send_progress("Installation de Docker (Prérequis)...", 5, "Docker n'est pas installé. Lancement de l'installation automatique via Winget...")
            send_progress("Installation de Docker (Prérequis)...", 5, "⚠️ UNE FENÊTRE DEMANDANT L'AUTORISATION (UAC) VA APPARAÎTRE. VEUILLEZ ACCEPTER.")
            
            winget_cmd = ["winget", "install", "Docker.DockerDesktop", "-e", "--accept-package-agreements", "--accept-source-agreements", "--silent"]
            proc = subprocess.Popen(winget_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding='utf-8', errors='replace')
            
            for line in proc.stdout:
                send_progress("Installation de Docker...", 5, line.strip())
            proc.wait()
            
            if proc.returncode != 0:
                send_progress("Échec de l'installation de Docker.", 5, f"Winget a retourné le code: {proc.returncode}. Veuillez installer Docker manuellement.")
                return

        # 2. Démarrage et attente du daemon Docker
        docker_ready = False
        for i in range(30):
            try:
                res = subprocess.run(["docker", "info"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                if res.returncode == 0:
                    docker_ready = True
                    break
            except FileNotFoundError:
                pass
                
            if i == 0:
                send_progress("Démarrage de Docker Desktop...", 8, "Le moteur Docker n'est pas encore prêt. Lancement en cours...")
                docker_path = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"
                if os.path.exists(docker_path):
                    subprocess.Popen([docker_path])
                    
            send_progress("Démarrage de Docker Desktop...", 8, f"Attente de l'initialisation du moteur Docker... ({i}/30) Cela peut prendre 1 à 2 minutes après un redémarrage.")
            time.sleep(2)
            
        if not docker_ready:
            send_progress("Error", 8, "Le moteur Docker n'a pas pu démarrer. Lancez Docker Desktop manuellement depuis le menu Démarrer pour vérifier s'il y a une erreur.")
            return

        send_progress("Téléchargement de l'environnement Linux...", 10, f"Exécution de: docker pull {image_name}")
        
        # Pull de l'image
        process = subprocess.Popen(["docker", "pull", image_name], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding='utf-8', errors='replace')
        
        pct = 10
        for line in process.stdout:
            if "Pulling fs layer" in line: pct = min(30, pct + 2)
            elif "Downloading" in line: pct = min(70, pct + 1)
            elif "Extracting" in line: pct = min(90, pct + 1)
            send_progress("Téléchargement de l'environnement Linux...", pct, line.strip())
            
        process.wait()
        
        if process.returncode != 0:
            send_progress("Error lors du téléchargement.", pct, f"Code de retour: {process.returncode}")
            return
            
        send_progress("Configuration du sous-système...", 95, "Création du conteneur...")
        
        # Remove if exists
        subprocess.run(["docker", "rm", "-f", "jarvis_os"], capture_output=True)
        
        # Run container
        data_path = os.path.join(path, "jarvis_os_data")
        shared_path = os.path.join(path, "jarvis_os_shared")
        
        cmd = [
            "docker", "run", "-d",
            "--name=jarvis_os",
            "--security-opt", "seccomp=unconfined",
            "-e", "PUID=1000",
            "-e", "PGID=1000",
            "-e", "TZ=Europe/Paris",
            "-p", "3000:3000",
            "-v", f"{data_path}:/config",
            "-v", f"{shared_path}:/config/Desktop/Shared",
            "-v", "/mnt/host:/config/Desktop/Disques_PC:rshared",
            "--shm-size=2gb",
            "--restart", "unless-stopped",
            image_name
        ]
        
        run_proc = subprocess.run(cmd, capture_output=True, text=True)
        if run_proc.returncode == 0:
            send_progress("Instalación terminada con éxito.", 100, "Le conteneur est prêt.", True, 3000)
        else:
            send_progress("Error lors du démarrage du conteneur.", 95, run_proc.stderr)
            
    except Exception as e:
        send_progress("Exception fatale lors de l'installation", 0, str(e))


async def ws_handler(websocket):
    global interface_deja_connectee, STOP_PARLER, MIC_MUTED, USER_LOCATION_GPS, NEMOTRON_ASR_ENABLED, _nemotron_instance, USER_NAME, USER_AGE, MUSIQUE_LIEN_PERSO, MIC_NEED_RELOAD, jarvis_actif, VILLE_PAR_DEFAUT, LAT_PAR_DEFAUT, LON_PAR_DEFAUT, ATTENTE_CHOIX_MODELE_IMAGE, ATTENTE_CHOIX_MODELE_SITE, PROMPT_EN_ATTENTE, CHOSEN_MODELS, ATTENTE_CREATION_PROMPT
    CONNECTED_CLIENTS.add(websocket)
    interface_deja_connectee = True
    print(f"[WEB] Interfaz conectada (Clientes activos: {len(CONNECTED_CLIENTS)})")
    
    # Push de la mise à jour si déjà détectée
    if DERNIERE_MAJ_INFO:
        try:
            await websocket.send(json.dumps(DERNIERE_MAJ_INFO))
        except:
            pass

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("type") == "mobile_command":
                    texte = data.get("text", "").strip()
                    target_pc = data.get("target_pc", False)
                    if texte:
                        print(f"[MOBILE] Comando recibido : {texte}")
                        asyncio.ensure_future(procesar_respuesta_ia(texte, mobile_ws=websocket, target_pc=target_pc))
                elif data.get("type") == "get_available_models":
                    cfg = _cargar_config()
                    prefered = cfg.get("preferred_brain", "auto")
                    preferred_local = cfg.get("preferred_local_model", "dolphin3")
                    models = []
                    if gemini_actif: models.append("gemini")
                    if anthropic_client: models.append("claude")
                    if groq_client: models.append("groq")
                    if mistral_client: models.append("mistral")
                    if grok_client: models.append("grok")
                    if openai_client: models.append("openai")
                    models.append("local_uncensored")
                    # Informations sur les modèles locaux disponibles
                    from agent_model_manager import LOCAL_OLLAMA_MODELS
                    await websocket.send(json.dumps({
                        "type": "available_models",
                        "models": models,
                        "prefered": prefered,
                        "preferred_local_model": preferred_local,
                        "local_ollama_models": {
                            k: v["label"] for k, v in LOCAL_OLLAMA_MODELS.items()
                        }
                    }))
                elif data.get("type") == "check_ollama_status":
                    status_data = _verificar_ollama_estado()
                    await websocket.send(json.dumps({
                        "type": "ollama_status_reply",
                        "status": status_data
                    }))
                elif data.get("type") == "pull_ollama_model":
                    model_name = data.get("model", "dolphin3")
                    loop = asyncio.get_running_loop()
                    threading.Thread(target=_descargar_modelo_ollama, args=(model_name, loop, websocket), daemon=True).start()
                elif data.get("type") == "set_local_model":
                    # Sauvegarde du modèle local préféré (dolphin3 / phi3.5 / llama3.1:8b)
                    local_model = data.get("model", "dolphin3")
                    from agent_model_manager import LOCAL_OLLAMA_MODELS
                    if local_model in LOCAL_OLLAMA_MODELS:
                        cfg = _cargar_config()
                        cfg["preferred_local_model"] = local_model
                        _guardar_config(cfg)
                        print(f"[LOCAL MODEL] Modèle local préféré défini sur : {local_model}")
                        await websocket.send(json.dumps({"type": "local_model_saved", "model": local_model}))
                elif data.get("type") == "check_kokoro_status":
                    st = _verificar_kokoro_estado()
                    await websocket.send(json.dumps({
                        "type": "kokoro_status_reply",
                        "status": st
                    }))
                elif data.get("type") == "install_kokoro_tts":
                    loop = asyncio.get_running_loop()
                    threading.Thread(target=_instalar_kokoro_tts, args=(loop, websocket), daemon=True).start()
                elif data.get("type") == "set_primary_model":
                    model = data.get("model")
                    cfg = _cargar_config()
                    cfg["preferred_brain"] = model
                    _guardar_config(cfg)
                    print(f"[MOBILE] Modèle préféré défini sur : {model}")
                elif data.get("type") == "stop_audio":
                    STOP_PARLER = True
                    jarvis_actif = False
                    print("[MOBILE] Señal STOP de audio recibida, regreso a espera")
                elif data.get("type") == "toggle_mic":
                    MIC_MUTED = not MIC_MUTED
                    await websocket.send(json.dumps({"type": "mic_state", "muted": MIC_MUTED}))
                    if MIC_MUTED:
                        await send_web_state("idle")
                    print(f"[WEB] Micro {'COUPE' if MIC_MUTED else 'REACTIVO'}")
                elif data.get("type") == "toggle_fullscreen":
                    if _WEBVIEW_WINDOW:
                        _WEBVIEW_WINDOW.toggle_fullscreen()
                        print("[WEB] Alternar pantalla completa pywebview")
                elif data.get("type") == "check_jarvis_os_status":
                    cfg = _cargar_config()
                    path = cfg.get("jarvis_os_path")
                    installed = False
                    if path:
                        import subprocess
                        try:
                            res = subprocess.run(["docker", "ps", "-a", "--filter", "name=jarvis_os", "--format", "{{.Names}}"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                            if "jarvis_os" in res.stdout:
                                installed = True
                                res_up = subprocess.run(["docker", "ps", "--filter", "name=jarvis_os", "--format", "{{.Names}}"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                                if "jarvis_os" not in res_up.stdout:
                                    subprocess.run(["docker", "start", "jarvis_os"], creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                                    await asyncio.sleep(3)
                        except FileNotFoundError:
                            installed = False
                    await websocket.send(json.dumps({
                        "type": "jarvis_os_status_reply",
                        "installed": installed,
                        "port": 3000
                    }))
                elif data.get("type") == "jarvis_os_pick_folder":
                    _loop = asyncio.get_running_loop()
                    def _pick_folder():
                        try:
                            import tkinter as tk
                            from tkinter import filedialog
                            root = tk.Tk()
                            root.withdraw()
                            root.attributes('-topmost', True)
                            folder = filedialog.askdirectory(title="Choisir le dossier d'installation de JARVIS OS")
                            root.destroy()
                            if folder:
                                asyncio.run_coroutine_threadsafe(
                                    websocket.send(json.dumps({"type": "jarvis_os_folder_picked", "path": folder})),
                                    _loop
                                )
                        except Exception as e:
                            print(f"[JARVIS OS] Error pick folder: {e}")
                    threading.Thread(target=_pick_folder, daemon=True).start()
                elif data.get("type") == "jarvis_os_install":
                    path = data.get("path")
                    if path:
                        cfg = _cargar_config()
                        cfg["jarvis_os_path"] = path
                        
                        try:
                            import json as _j
                            with open(_JARVIS_CONFIG_PATH, "w", encoding="utf-8") as _f:
                                _j.dump(cfg, _f, indent=4)
                        except Exception as e:
                            print(f"[JARVIS OS] Error al guardar configuración: {e}")
                            
                        # Création dossiers
                        data_path = os.path.join(path, "jarvis_os_data")
                        shared_path = os.path.join(path, "jarvis_os_shared")
                        os.makedirs(data_path, exist_ok=True)
                        os.makedirs(shared_path, exist_ok=True)
                        
                        loop = asyncio.get_running_loop()
                        threading.Thread(target=_instalar_jarvis_os, args=(path, websocket, loop), daemon=True).start()
                elif data.get("type") == "jarvis_os_start":
                    import subprocess
                    try:
                        subprocess.run(["docker", "start", "jarvis_os"], creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                    except FileNotFoundError: pass
                elif data.get("type") == "jarvis_os_stop":
                    import subprocess
                    try:
                        subprocess.run(["docker", "stop", "jarvis_os"], creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                    except FileNotFoundError: pass
                    await websocket.send(json.dumps({"type": "jarvis_os_stopped"}))
                elif data.get("type") == "jarvis_os_install_app":
                    pkg = data.get("pkg", "").strip()
                    name = data.get("name", pkg)
                    if pkg:
                        # Capture the running loop HERE (in the async context), before the thread
                        _install_loop = asyncio.get_running_loop()
                        
                        def _install_app(pkg=pkg, name=name, _loop=_install_loop):
                            import subprocess as _sp
                            
                            def _send(msg, done=False, success=True):
                                asyncio.run_coroutine_threadsafe(
                                    websocket.send(json.dumps({
                                        "type": "jarvis_os_app_install_progress",
                                        "pkg": pkg, "log": msg, "done": done, "success": success
                                    })), _loop
                                )
                            try:
                                custom_script = data.get("script", "")
                                if custom_script:
                                    # Run custom bash script (e.g. for Brave, which needs repo setup)
                                    cmd = ["docker", "exec", "-u", "root", "jarvis_os",
                                           "bash", "-c", f"DEBIAN_FRONTEND=noninteractive {custom_script} 2>&1"]
                                    _send(f"▶ Installation de {name} (script dédié)...")
                                else:
                                    is_snap = "--snap" in pkg
                                    real_pkg = pkg.replace("--classic --snap", "").replace("--snap", "").strip()
                                    if is_snap:
                                        snap_flag = "--classic" if "--classic" in pkg else ""
                                        cmd = ["docker", "exec", "-u", "root", "jarvis_os",
                                               "bash", "-c", f"snap install {snap_flag} {real_pkg} 2>&1"]
                                    else:
                                        cmd = ["docker", "exec", "-u", "root", "jarvis_os",
                                               "bash", "-c", f"DEBIAN_FRONTEND=noninteractive apt-get install -y {real_pkg} 2>&1"]
                                    _send(f"▶ apt install {real_pkg}...")

                                process = _sp.Popen(
                                    cmd, stdout=_sp.PIPE, stderr=_sp.STDOUT,
                                    text=True, bufsize=1, encoding='utf-8', errors='replace'
                                )
                                for line in process.stdout:
                                    line = line.strip()
                                    if line:
                                        _send(line)
                                process.wait()
                                if process.returncode == 0:
                                    _send(f"✅ {name} installé avec succès !", done=True, success=True)
                                else:
                                    _send(f"❌ Error installation {name} (code {process.returncode})", done=True, success=False)
                            except Exception as e:
                                _send(f"❌ Exception: {e}", done=True, success=False)
                        
                        threading.Thread(target=_install_app, daemon=True).start()

                elif data.get("type") == "jarvis_os_restart":
                    import subprocess
                    try:
                        subprocess.run(["docker", "restart", "jarvis_os"], creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                    except FileNotFoundError: pass
                elif data.get("type") == "jarvis_os_uninstall":
                    import subprocess
                    import shutil
                    try:
                        subprocess.run(["docker", "rm", "-f", "jarvis_os"], creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                    except FileNotFoundError: pass
                    cfg = _cargar_config()
                    path = cfg.get("jarvis_os_path")
                    if path and os.path.exists(path):
                        try:
                            shutil.rmtree(path, ignore_errors=True)
                        except:
                            pass
                    cfg.pop("jarvis_os_path", None)
                    try:
                        import json as _j
                        with open(_JARVIS_CONFIG_PATH, "w", encoding="utf-8") as _f:
                            _j.dump(cfg, _f, indent=4)
                    except:
                        pass
                    await websocket.send(json.dumps({"type": "jarvis_os_stopped"}))
                elif data.get("type") == "jarvis_os_open_shared":
                    cfg = _cargar_config()
                    path = cfg.get("jarvis_os_path")
                    if path:
                        shared_path = os.path.normpath(os.path.join(path, "jarvis_os_shared"))
                        if os.path.exists(shared_path):
                            import subprocess
                            subprocess.Popen(['explorer', shared_path])
                elif data.get("type") == "user_input":
                    texte = data.get("text", "").strip()
                    if texte:
                        print(f"[HUD] Commande clavier : {texte}")
                        asyncio.ensure_future(procesar_respuesta_ia(texte))
                elif data.get("type") == "open_file_location":
                    path = data.get("path")
                    if path and os.path.exists(path):
                        try:
                            print(f"[WEB] Apertura de la carpeta que contiene : {path}")
                            import subprocess
                            subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])
                        except Exception as e:
                            print(f"[WEB] Error ouverture fichier: {e}")
                elif data.get("type") == "screen_frame":
                    req_id = data.get("id")
                    if req_id in PENDING_SCREEN_CAPTURES:
                        fut = PENDING_SCREEN_CAPTURES.pop(req_id)
                        if "error" in data:
                            fut.set_exception(Exception(data["error"]))
                        else:
                            fut.set_result(data["data"])
                    print(f"[VISION] Frame recibido para ID: {req_id}")
                elif data.get("type") == "camera_capture_response":
                    req_id = data.get("id")
                    if req_id in PENDING_CAMERA_CAPTURES:
                        fut = PENDING_CAMERA_CAPTURES.pop(req_id)
                        if data.get("success") is False:
                            fut.set_exception(Exception(data.get("error", "Error capture inconnue")))
                        else:
                            fut.set_result(data.get("image"))
                    print(f"[CAMERA] Capture recue pour ID: {req_id}")
                elif data.get("type") == "webcam_state":
                    global WEBCAM_ACTIVE
                    WEBCAM_ACTIVE = data.get("active", False)
                    builtins.WEBCAM_ACTIVE = WEBCAM_ACTIVE
                    print(f"[CAMERA] Estado de webcam actualizado : {'ACTIVO' if WEBCAM_ACTIVE else 'INACTIVO'}")
                elif data.get("type") == "get_settings":
                    import json as _j
                    try:
                        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
                        with open(_p, "r", encoding="utf-8") as _f:
                            config_data = _j.load(_f)
                    except Exception:
                        config_data = {}
                    # Ajouter la liste des micros disponibles
                    mic_list = []
                    _pyaudio_available = False
                    try:
                        if pyaudio:
                            _pyaudio_available = True
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
                    config_data["pyaudio_available"] = _pyaudio_available
                    # Ajouter l'état Nemotron ASR
                    config_data["nemotron_asr_available"] = _nemotron_asr_ok
                    config_data["gpu_available"] = detectar_gpu_nvidia()
                    config_data["nemotron_asr_enabled"] = NEMOTRON_ASR_ENABLED
                    if _nemotron_instance:
                        config_data["nemotron_device_info"] = _nemotron_instance.get_device_info()
                    
                    # Ajouter les clés API depuis les variables d'environnement en direct
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
                elif data.get("type") == "get_agent_models":
                    import agent_model_manager
                    info = agent_model_manager.get_agent_models_info(CHOSEN_MODELS)
                    await websocket.send(json.dumps({"type": "agent_models_info", "data": info}))
                elif data.get("type") == "set_agent_models":
                    import agent_model_manager
                    new_models = data.get("models")
                    if new_models and isinstance(new_models, dict):
                        updated_models = agent_model_manager.set_agent_models(new_models)
                        CHOSEN_MODELS = updated_models
                        print(f"[AGENT MODELE] Modelos modificados con éxito : {CHOSEN_MODELS}")
                        await websocket.send(json.dumps({"type": "agent_model_updated", "models": CHOSEN_MODELS}))
                elif data.get("type") == "vpn_get_countries":
                    import vpn
                    countries = vpn.get_countries()
                    await websocket.send(json.dumps({"type": "vpn_countries", "countries": countries}))
                elif data.get("type") == "vpn_get_status":
                    import vpn
                    status = vpn.get_status()
                    await websocket.send(json.dumps({"type": "vpn_status", "status": status, "ip_info": ip_info}))
                elif data.get("type") == "toggle_startup":
                    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
                    try:
                        with open(config_path, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                    except:
                        cfg = {}
                    
                    enabled = data.get("enabled", False)
                    cfg["launch_on_startup"] = enabled
                    
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=4)
                        
                    if enabled:
                        activar_inicio_windows()
                    else:
                        desactivar_inicio_windows()
                    
                    await websocket.send(json.dumps({"type": "startup_toggled", "enabled": enabled}))
                elif data.get("type") == "vpn_connect":
                    import vpn
                    country = data.get("country", "")
                    
                    async def async_connect_task(country_code):
                        def run_connect():
                            return vpn.connect(country_code)
                        loop = asyncio.get_running_loop()
                        result = await loop.run_in_executor(None, run_connect)
                        if result.get("success"):
                            asyncio.create_task(hablar(f"{USER_NAME}, la connexion VPN vers le pays {country_code} a été établie avec succès."))
                        else:
                            if result.get("error") != "Annulé par l'utilisateur.":
                                asyncio.create_task(hablar(f"Désolé {USER_NAME}, la connexion VPN a échoué. {result.get('error', '')}"))
                        try:
                            await websocket.send(json.dumps({"type": "vpn_connect_result", "result": result}))
                        except Exception:
                            pass
                            
                    asyncio.create_task(async_connect_task(country))
                elif data.get("type") == "vpn_disconnect":
                    import vpn
                    def run_disconnect():
                        return vpn.disconnect()
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(None, run_disconnect)
                    asyncio.create_task(hablar(f"{USER_NAME}, la connexion VPN a été coupée. Retour à la connexion standard."))
                    await websocket.send(json.dumps({"type": "vpn_disconnect_result", "result": result}))
                elif data.get("type") == "vpn_cancel":
                    import vpn
                    def run_cancel():
                        vpn.cancel_connection()
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, run_cancel)
                    asyncio.create_task(hablar(f"{USER_NAME}, la connexion VPN a été annulée."))
                    await websocket.send(json.dumps({"type": "vpn_cancel_result", "success": True}))
                elif data.get("type") == "get_shopping_list":
                    listes = _cargar_listas()
                    await websocket.send(json.dumps({"type": "shopping_list", "items": listes.get("courses", [])}))
                elif data.get("type") == "update_shopping_list":
                    items = data.get("items", [])
                    listes = _cargar_listas()
                    listes["courses"] = items
                    _guardar_listas(listes)
                    msg = json.dumps({"type": "shopping_list", "items": items})
                    if CONNECTED_CLIENTS:
                        await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                elif data.get("type") == "get_obsidian_notes":
                    notes = obsidian_helper.lister_notes()
                    await websocket.send(json.dumps({"type": "obsidian_notes", "notes": notes}))
                elif data.get("type") == "detect_apps":
                    apps = await asyncio.to_thread(lister_applications_installees)
                    await websocket.send(json.dumps({"type": "detected_apps", "apps": apps}))
                elif data.get("type") == "get_installed_programs":
                    programs = list_installed_programs()
                    await websocket.send(json.dumps({"type": "installed_programs", "programs": programs}))
                elif data.get("type") == "uninstall_program":
                    app_name = data.get("name", "")
                    publisher = data.get("publisher", "")
                    install_location = data.get("install_location", "")
                    uninstall_string = data.get("uninstall_string", "")
                    
                    print(f"[UNINSTALLER] Début de la désinstallation de {app_name}...")
                    
                    await websocket.send(json.dumps({
                        "type": "uninstall_progress",
                        "status": "started",
                        "message": f"Lanzamiento de la desinstalación oficial de {app_name}..."
                    }))
                    
                    # Exécuter le processus officiel dans un thread séparé
                    success, msg_un = await asyncio.to_thread(run_uninstall_process, uninstall_string)
                    
                    await websocket.send(json.dumps({
                        "type": "uninstall_progress",
                        "status": "scanning",
                        "message": f"Désinstallation officielle terminée. Búsqueda de rastros residuales pour {app_name}..."
                    }))
                    
                    # Lancer le scan des traces
                    leftovers_files = await asyncio.to_thread(scan_file_leftovers, app_name, publisher, install_location)
                    leftovers_reg = await asyncio.to_thread(scan_registry_leftovers, app_name, publisher)
                    all_leftovers = leftovers_files + leftovers_reg
                    
                    print(f"[UNINSTALLER] Escaneo terminado, {len(all_leftovers)} rastros encontrados.")
                    
                    await websocket.send(json.dumps({
                        "type": "uninstall_complete",
                        "app_name": app_name,
                        "success": success,
                        "leftovers": all_leftovers
                    }))
                elif data.get("type") == "clean_leftovers":
                    items_to_clean = data.get("items", [])
                    cleaned_count = 0
                    errors = []
                    
                    print(f"[UNINSTALLER] Limpieza de {len(items_to_clean)} traces...")
                    for item in items_to_clean:
                        success_cl, msg_cl = clean_leftover_item(item)
                        if success_cl:
                            cleaned_count += 1
                        else:
                            errors.append(f"{item.get('path')} : {msg_cl}")
                            
                    await websocket.send(json.dumps({
                        "type": "clean_complete",
                        "cleaned_count": cleaned_count,
                        "total_count": len(items_to_clean),
                        "errors": errors
                    }))
                elif data.get("type") == "get_winget_upgrades":
                    print("[WINGET] Escaneo de actualizaciones solicitado...")
                    upgrades = await asyncio.to_thread(listar_actualizaciones_winget)
                    await websocket.send(json.dumps({
                        "type": "winget_upgrades",
                        "upgrades": upgrades
                    }))
                elif data.get("type") == "run_winget_upgrade":
                    ids = data.get("ids", [])
                    run_all = data.get("all", False)
                    loop = asyncio.get_running_loop()
                    if run_all:
                        print("[WINGET] Lanzamiento de actualización global...")
                        args = ["winget", "upgrade", "--all", "--accept-package-agreements", "--accept-source-agreements"]
                        lancer_tache_arriere_plan(asyncio.to_thread(ejecutar_actualizacion_winget_sync, args, loop, websocket))
                    elif ids:
                        async def run_sequence():
                            for idx, pkg_id in enumerate(ids):
                                print(f"[WINGET] Actualización de {pkg_id} ({idx+1}/{len(ids)})...")
                                args = ["winget", "upgrade", "--id", pkg_id, "--accept-package-agreements", "--accept-source-agreements"]
                                await asyncio.to_thread(ejecutar_actualizacion_winget_sync, args, loop, websocket)
                        lancer_tache_arriere_plan(run_sequence())
                elif data.get("type") == "read_obsidian_note":
                    titre = data.get("titre", "")
                    success, content = obsidian_helper.lire_note(titre)
                    if success:
                        await websocket.send(json.dumps({
                            "type": "obsidian_note_content",
                            "titre": titre,
                            "content": content
                        }))
                elif data.get("type") == "save_obsidian_note":
                    titre = data.get("titre", "")
                    content = data.get("content", "")
                    success, msg_result = obsidian_helper.creer_ou_modifier_note(titre, content)
                    if success:
                        notes = obsidian_helper.lister_notes()
                        msg = json.dumps({"type": "obsidian_notes", "notes": notes})
                        if CONNECTED_CLIENTS:
                            await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                elif data.get("type") == "delete_obsidian_note":
                    titre = data.get("titre", "")
                    success, msg_result = obsidian_helper.supprimer_note(titre)
                    if success:
                        notes = obsidian_helper.lister_notes()
                        msg = json.dumps({"type": "obsidian_notes", "notes": notes})
                        if CONNECTED_CLIENTS:
                            await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                elif data.get("type") == "location_update":
                    USER_LOCATION_GPS = {
                        "lat": data.get("lat"),
                        "lng": data.get("lng")
                    }
                    print(f"[RESTAURANT] Localisation GPS client reçue : {USER_LOCATION_GPS['lat']}, {USER_LOCATION_GPS['lng']}")
                elif data.get("type") == "open_browser":
                    query = data.get("query")
                    try:
                        import secure_browser
                        threading.Thread(target=secure_browser.trigger_browser, args=(query, _WEBVIEW_WINDOW), daemon=True).start()
                    except Exception as e:
                        print(f"[BROWSER] Error WebSocket open_browser : {e}")
                elif data.get("type") == "dock_browser":
                    try:
                        import secure_browser
                        secure_browser.dock_browser()
                    except Exception as e:
                        print(f"[BROWSER] Error WebSocket dock_browser : {e}")
                elif data.get("type") == "undock_browser":
                    try:
                        import secure_browser
                        secure_browser.undock_browser()
                    except Exception as e:
                        print(f"[BROWSER] Error WebSocket undock_browser : {e}")
                elif data.get("type") == "close_browser":
                    try:
                        import secure_browser
                        secure_browser.close_browser_window()
                    except Exception as e:
                        print(f"[BROWSER] Error WebSocket close_browser : {e}")
                elif data.get("type") == "toggle_nemotron_asr":
                    wanted = data.get("enabled", False)
                    result_asr = {"type": "nemotron_asr_state", "enabled": False,
                                  "gpu_available": False, "warnings": [], "error": None}
                    if wanted:
                        if not _nemotron_asr_ok:
                            result_asr["error"] = (
                                "NeMo non installé. Installez-le avec : "
                                "pip install nemo_toolkit[asr] torch"
                            )
                            print("[ASR] ⚠ NeMo non installé — impossible d'activer Nemotron ASR")
                        else:
                            if _nemotron_instance is None:
                                global NemotronASR
                                if NemotronASR is None:
                                    from nemotron_asr import NemotronASR
                                _nemotron_instance = NemotronASR()
                            load_result = await asyncio.to_thread(_nemotron_instance.charger_modele)
                            if load_result["success"]:
                                NEMOTRON_ASR_ENABLED = True
                                result_asr["enabled"] = True
                                result_asr["gpu_available"] = _nemotron_instance.is_gpu_available()
                                result_asr["warnings"] = load_result.get("warnings", [])
                                print("[ASR] ✔ Nemotron ASR activé")
                            else:
                                result_asr["error"] = load_result["error"]
                                result_asr["warnings"] = load_result.get("warnings", [])
                                _nemotron_instance.liberer()
                                _nemotron_instance = None
                                print(f"[ASR] ✖ Échec activation : {load_result['error']}")
                    else:
                        NEMOTRON_ASR_ENABLED = False
                        if _nemotron_instance:
                            _nemotron_instance.liberer()
                            _nemotron_instance = None
                        result_asr["enabled"] = False
                        print("[ASR] Nemotron ASR désactivé")
                    _guardar_config({"nemotron_asr_enabled": NEMOTRON_ASR_ENABLED})
                    await websocket.send(json.dumps(result_asr))
                    # Diffuser l'état à tous les clients
                    if CONNECTED_CLIENTS:
                        await asyncio.gather(*[ws.send(json.dumps(result_asr)) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                elif data.get("type") == "install_nemotron_deps":
                    global _nemotron_install_task
                    if _nemotron_install_task is None or _nemotron_install_task.done():
                        _nemotron_install_task = asyncio.create_task(instalar_dependencias_nemotron(websocket))
                        print("[ASR] Tâche d'installation automatique démarrée")
                    else:
                        await websocket.send(json.dumps({
                            "type": "nemotron_install_progress",
                            "status": "error",
                            "stage": "Déjà en cours",
                            "progress": 0,
                            "log": "Une installation est déjà en cours d'exécution.\n"
                        }))
                elif data.get("type") == "uninstall_nemotron_deps":
                    global _nemotron_uninstall_task
                    if _nemotron_uninstall_task is None or _nemotron_uninstall_task.done():
                        _nemotron_uninstall_task = asyncio.create_task(desinstalar_dependencias_nemotron(websocket))
                        print("[ASR] Tâche de désinstallation automatique démarrée")
                    else:
                        await websocket.send(json.dumps({
                            "type": "nemotron_uninstall_progress",
                            "status": "error",
                            "stage": "Déjà en cours",
                            "progress": 0,
                            "log": "Une désinstallation est déjà en cours d'exécution.\n"
                        }))
                elif data.get("type") == "av_scan_start":
                    import antivirus_scanner
                    if antivirus_scanner.ACTIVE_SCAN_TASK is None or antivirus_scanner.ACTIVE_SCAN_TASK.done():
                        async def ws_broadcast(m):
                            if CONNECTED_CLIENTS:
                                try:
                                    await asyncio.gather(*[ws.send(json.dumps(m)) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                                except Exception:
                                    pass
                        antivirus_scanner.ACTIVE_SCAN_TASK = asyncio.create_task(
                            antivirus_scanner.executer_scan_antivirus(ws_broadcast, hablar)
                        )
                        print("[AV] Lancement de la tâche d'analyse antivirus...")
                elif data.get("type") == "av_scan_cancel":
                    import antivirus_scanner
                    if antivirus_scanner.ACTIVE_SCAN_TASK and not antivirus_scanner.ACTIVE_SCAN_TASK.done():
                        antivirus_scanner.ACTIVE_SCAN_TASK.cancel()
                        print("[AV] Tâche d'analyse antivirus annulée par websocket.")
                elif data.get("type") == "av_threat_action":
                    action = data.get("action")
                    threat = data.get("threat", {})
                    t_type = threat.get("type")
                    target = threat.get("target")
                    success = False
                    msg = ""
                    try:
                        def terminate_processes_using_file(filepath):
                            if not filepath or not os.path.exists(filepath):
                                return
                            import psutil
                            normalized_target = os.path.normpath(filepath).lower()
                            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                                try:
                                    exe_path = proc.info.get('exe')
                                    if exe_path and os.path.normpath(exe_path).lower() == normalized_target:
                                        print(f"[AV] Arrêt du processus actif exécutant la menace : {proc.info['name']} (PID {proc.info['pid']})")
                                        p = psutil.Process(proc.info['pid'])
                                        p.terminate()
                                        try:
                                            p.wait(timeout=1.5)
                                        except psutil.TimeoutExpired:
                                            p.kill()
                                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                                    pass

                        def force_writable(filepath):
                            if filepath and os.path.exists(filepath):
                                import stat
                                try:
                                    os.chmod(filepath, stat.S_IWRITE)
                                except Exception as e:
                                    print(f"[AV] Impossible de changer les permissions de {filepath} : {e}")

                        if action == "allow":
                            if target:
                                config = _cargar_config()
                                exclusions = config.get("av_exclusions", [])
                                if target not in exclusions:
                                    exclusions.append(target)
                                _guardar_config({"av_exclusions": exclusions})
                                success = True
                                msg = f"Menace autorisée et ajoutée aux exclusions : {target}"
                            else:
                                msg = "Cible de menace manquante pour l'exclusion."
                        elif action == "delete":
                            if t_type == "file":
                                if target:
                                    terminate_processes_using_file(target)
                                    force_writable(target)
                                    if os.path.exists(target):
                                        os.remove(target)
                                        success = True
                                        msg = f"Fichier supprimé : {target}"
                                    else:
                                        success = True
                                        msg = "Fichier déjà supprimé ou introuvable."
                                else:
                                    msg = "Chemin de fichier cible manquant."
                            elif t_type == "process":
                                import re
                                import psutil
                                match = re.search(r"PID\s+(\d+)", target)
                                if match:
                                    pid = int(match.group(1))
                                    if psutil.pid_exists(pid):
                                        p = psutil.Process(pid)
                                        p.terminate()
                                        try:
                                            p.wait(timeout=1.5)
                                        except psutil.TimeoutExpired:
                                            p.kill()
                                        success = True
                                        msg = f"Processus arrêté (PID {pid})."
                                    else:
                                        success = True
                                        msg = f"Le processus PID {pid} n'est plus actif."
                                else:
                                    msg = f"Cible invalide pour le processus : {target}"
                            elif t_type == "registry":
                                import winreg
                                t_name = threat.get("name")
                                is_hklm = "HKLM" in threat.get("desc", "")
                                root_key = winreg.HKEY_LOCAL_MACHINE if is_hklm else winreg.HKEY_CURRENT_USER
                                sub_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
                                try:
                                    key = winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_SET_VALUE)
                                    winreg.DeleteValue(key, t_name)
                                    winreg.CloseKey(key)
                                    success = True
                                    msg = f"Entrée de registre '{t_name}' supprimée."
                                except FileNotFoundError:
                                    success = True
                                    msg = f"Entrée de registre '{t_name}' déjà absente."
                                except Exception as re_err:
                                    msg = f"Error suppression registre : {re_err}"
                        elif action == "clean":
                            if t_type == "file":
                                if target:
                                    terminate_processes_using_file(target)
                                    force_writable(target)
                                    if os.path.exists(target):
                                        with open(target, 'wb') as f:
                                            f.write(b"")
                                        success = True
                                        msg = f"Fichier vidé et neutralisé : {target}"
                                    else:
                                        msg = f"Fichier introuvable : {target}"
                                else:
                                    msg = "Chemin de fichier cible manquant."
                            elif t_type == "process":
                                import re
                                import psutil
                                match = re.search(r"PID\s+(\d+)", target)
                                if match:
                                    pid = int(match.group(1))
                                    if psutil.pid_exists(pid):
                                        p = psutil.Process(pid)
                                        p.terminate()
                                        try:
                                            p.wait(timeout=1.5)
                                        except psutil.TimeoutExpired:
                                            p.kill()
                                        success = True
                                        msg = f"Processus stoppé (PID {pid})."
                                    else:
                                        success = True
                                        msg = f"Processus déjà inactif (PID {pid})."
                                else:
                                    msg = f"Cible invalide : {target}"
                            elif t_type == "registry":
                                import winreg
                                t_name = threat.get("name")
                                is_hklm = "HKLM" in threat.get("desc", "")
                                root_key = winreg.HKEY_LOCAL_MACHINE if is_hklm else winreg.HKEY_CURRENT_USER
                                sub_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
                                try:
                                    key = winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_SET_VALUE)
                                    winreg.DeleteValue(key, t_name)
                                    winreg.CloseKey(key)
                                    success = True
                                    msg = f"Entrée de registre '{t_name}' nettoyée."
                                except FileNotFoundError:
                                    success = True
                                    msg = f"Entrée de registre '{t_name}' déjà absente."
                                except Exception as re_err:
                                    msg = f"Error nettoyage registre : {re_err}"
                        elif action == "quarantine":
                            if t_type == "file":
                                if target:
                                    terminate_processes_using_file(target)
                                    force_writable(target)
                                    if os.path.exists(target):
                                        quarantine_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quarantine")
                                        os.makedirs(quarantine_dir, exist_ok=True)
                                        filename = threat.get("name", "quarantine_file")
                                        import time
                                        safe_name = f"{int(time.time())}_{filename}.quarantine"
                                        dest = os.path.join(quarantine_dir, safe_name)
                                        import shutil
                                        shutil.move(target, dest)
                                        success = True
                                        msg = f"Fichier déplacé en quarantaine : {safe_name}"
                                    else:
                                        msg = f"Fichier introuvable : {target}"
                                else:
                                    msg = "Chemin de fichier cible manquant."
                            elif t_type == "process":
                                import re
                                import psutil
                                match = re.search(r"PID\s+(\d+)", target)
                                if match:
                                    pid = int(match.group(1))
                                    if psutil.pid_exists(pid):
                                        p = psutil.Process(pid)
                                        p.terminate()
                                        try:
                                            p.wait(timeout=1.5)
                                        except psutil.TimeoutExpired:
                                            p.kill()
                                        success = True
                                        msg = f"Processus neutralisé (PID {pid})."
                                    else:
                                        success = True
                                        msg = f"Le processus PID {pid} n'était plus actif."
                                else:
                                    msg = f"Cible de processus invalide : {target}"
                            elif t_type == "registry":
                                import winreg
                                t_name = threat.get("name")
                                is_hklm = "HKLM" in threat.get("desc", "")
                                root_key = winreg.HKEY_LOCAL_MACHINE if is_hklm else winreg.HKEY_CURRENT_USER
                                sub_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
                                try:
                                    key = winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_SET_VALUE)
                                    winreg.DeleteValue(key, t_name)
                                    winreg.CloseKey(key)
                                    success = True
                                    msg = f"Entrée de registre '{t_name}' désactivée."
                                except FileNotFoundError:
                                    success = True
                                    msg = f"Entrée de registre '{t_name}' déjà absente."
                                except Exception as re_err:
                                    msg = f"Error : {re_err}"
                    except Exception as e:
                        msg = f"Échec de l'action {action} : {e}"
                        print(f"[AV] Échec action {action} : {e}")
                    await websocket.send(json.dumps({
                        "type": "av_action_result",
                        "success": success,
                        "action": action,
                        "threat_target": target,
                        "message": msg
                    }))
                elif data.get("type") == "av_speak":
                    text = data.get("text")
                    if text:
                        lancer_tache_arriere_plan(hablar(text))
                elif data.get("type") == "clear_cache":
                    # Nettoyage manuel du cache WebView2 depuis le bouton du menu.
                    # Reset le marqueur pour forcer un vrai nettoyage au prochain demarrage
                    try:
                        _marker = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".jarvis_cache_version")
                        if os.path.exists(_marker):
                            os.remove(_marker)
                        print("[CACHE] Marqueur de version reinitialise — nettoyage complet au prochain demarrage.")
                    except Exception as _e:
                        print(f"[CACHE] Impossible de reset le marqueur : {_e}")

                    # Repondre succes au front-end
                    await websocket.send(json.dumps({
                        "type": "cache_cleared",
                        "success": True,
                        "message": "Rechargement en cours — nettoyage complet au prochain démarrage."
                    }))

                    # Recharger la fenetre avec URL cache-buster (bypass le cache navigateur)
                    if _WEBVIEW_WINDOW:
                        def _reload_window_cachebust():
                            import time as _t
                            _t.sleep(1.2)
                            try:
                                _WEBVIEW_WINDOW.load_url(
                                    f"http://localhost:5173?v={float(CURRENT_VERSION) + 0.1}&t={int(_t.time())}"
                                )
                                print("[CACHE] Fenetre rechargee avec cache-bust.")
                            except Exception as _e:
                                print(f"[CACHE] Error rechargement fenetre : {_e}")
                        threading.Thread(target=_reload_window_cachebust, daemon=True).start()

                elif data.get("type") == "check_update_vocal":
                    # Vérifier la version directement sur la page web https://www.techenclair.fr/pages/jarvis et répondre vocalement
                    async def _verifier_page_maj_vocal():
                        try:
                            import requests as _req
                            import re as _re
                            headers = {
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                            }
                            resp = _req.get("https://www.techenclair.fr/pages/jarvis", headers=headers, timeout=8)
                            site_version = None
                            if resp.status_code == 200:
                                match = _re.search(r'[Vv]ersion\s*([0-9]+(?:\.[0-9]+)*)', resp.text)
                                if match:
                                    site_version = match.group(1)

                            if not site_version:
                                resp_json = _req.get(UPDATE_JSON_URL, headers=headers, timeout=5)
                                if resp_json.status_code == 200:
                                    site_version = str(resp_json.json().get("version", ""))

                            def _version_tuple(v_str):
                                try:
                                    return [int(x) for x in _re.findall(r'\d+', str(v_str))]
                                except Exception:
                                    return [0]

                            if site_version:
                                v_remote = _version_tuple(site_version)
                                v_local = _version_tuple(CURRENT_VERSION)

                                if v_remote > v_local:
                                    await hablar(f"J'ai détecté une mise à jour, la version {site_version} est disponible. Veuillez télécharger la mise à jour sur le site de TechEnClair.")
                                elif v_remote == v_local:
                                    await hablar(f"Votre version {CURRENT_VERSION} de Jarvis est déjà à jour.")
                                else:
                                    await hablar(f"Votre version {CURRENT_VERSION} de Jarvis est à jour.")
                            else:
                                await hablar("Page de mise à jour ouverte sur le site de TechEnClair.")
                        except Exception as _e:
                            print(f"[UPDATE] Error vérification vocale : {_e}")
                            await hablar("Page de mise à jour ouverte sur le site de TechEnClair.")

                    asyncio.create_task(_verifier_page_maj_vocal())

                elif data.get("type") == "check_update_manual":
                    # Récupérer le lien de téléchargement depuis le JSON et le renvoyer au frontend
                    try:
                        import requests as _req
                        _resp = _req.get(UPDATE_JSON_URL, timeout=8)
                        if _resp.status_code == 200:
                            _updata = _resp.json()
                            _dl_url = _updata.get("download_url", "https://www.techenclair.fr/pages/jarvis")
                        else:
                            _dl_url = "https://www.techenclair.fr/pages/jarvis"
                    except Exception as _e:
                        print(f"[UPDATE] Error récupération lien manuel : {_e}")
                        _dl_url = "https://www.techenclair.fr/pages/jarvis"
                    await websocket.send(json.dumps({
                        "type": "update_download_url",
                        "url": _dl_url
                    }))

                elif data.get("type") in ("iptv_open", "iptv_parse_m3u", "iptv_parse_url", "iptv_open_file", "iptv_set_audio_track"):
                    # ── Lecteur IPTV & Vidéo ──────────────────────────────────
                    await handle_iptv_ws_message(data, websocket, CONNECTED_CLIENTS)
                elif data.get("type") in ("ha_get_states", "ha_call_service"):
                    # ── Home Assistant Dashboard ──────────────────────────────
                    await handle_ha_ws_message(data, websocket, CONNECTED_CLIENTS)
                elif data.get("type") == "update_settings":
                    settings = data.get("settings", {})
                    
                    # Extraction et écriture des clés API dans .env + rechargement à chaud
                    if "api_keys" in settings:
                        api_keys = settings.pop("api_keys")
                        if isinstance(api_keys, dict):
                            _guardar_env(api_keys)
                            recharger_clients_ia()

                    import json as _j
                    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
                    try:
                        with open(_p, "r", encoding="utf-8") as _f:
                            config_data = _j.load(_f)
                    except Exception:
                        config_data = {}
                    
                    # Renommage du prénom si changé — avant d'écrire le nouveau config
                    if "user_name" in settings:
                        _ancien = config_data.get("user_name", "Christopher")
                        _nouveau = settings["user_name"]
                        if _ancien.lower() != _nouveau.lower():
                            try:
                                import importlib.util as _ilu
                                _rpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_setup", "rename_user.py")
                                _spec = _ilu.spec_from_file_location("rename_user", _rpath)
                                _mod = _ilu.module_from_spec(_spec)
                                _spec.loader.exec_module(_mod)
                                _mod.remplacer_prenom(_nouveau, _ancien)
                            except Exception as _e:
                                print(f"[WEB] Error renommage prénom : {_e}")

                    # Géocoder la ville si elle est présente pour remplir les coordonnées GPS
                    if "user_city" in settings:
                        _nouvelle_ville = settings["user_city"].strip()
                        if _nouvelle_ville:
                            try:
                                _lat, _lon, _nom_officiel, _pays = geocoder_ville(_nouvelle_ville)
                                if _lat is not None and _lon is not None:
                                    settings["user_city"] = _nom_officiel
                                    settings["user_lat"] = _lat
                                    settings["user_lon"] = _lon
                                    print(f"[WEB] Ville géocodée : {_nom_officiel} ({_lat}, {_lon})")
                                else:
                                    await hablar(f"Désolé Christopher, je ne reconnais pas la ville de {_nouvelle_ville}. Veuillez vérifier l'orthographe.")
                                    # Restaurer les valeurs précédentes
                                    settings["user_city"] = config_data.get("user_city", "Amilly")
                                    settings["user_lat"] = config_data.get("user_lat", 47.97281)
                                    settings["user_lon"] = config_data.get("user_lon", 2.77186)
                            except Exception as _e:
                                print(f"[WEB] Error géocodage ville : {_e}")

                    # Vérifier si l'état de l'antivirus en temps réel a réellement changé
                    ancien_av_live = config_data.get("av_live_protection", False)
                    nouveau_av_live = settings.get("av_live_protection", False)
                    av_changed = ("av_live_protection" in settings) and (ancien_av_live != nouveau_av_live)

                    config_data.update(settings)

                    with open(_p, "w", encoding="utf-8") as _f:
                        _j.dump(config_data, _f, ensure_ascii=False, indent=4)

                    # Update globals d'abord
                    global WAKE_WORD
                    USER_NAME = config_data.get("user_name", "Christopher")
                    USER_AGE = config_data.get("user_age", "")
                    WAKE_WORD = config_data.get("wake_word", "jarvis").lower().strip()
                    VILLE_PAR_DEFAUT = config_data.get("user_city", "Amilly")
                    try:
                        LAT_PAR_DEFAUT = float(config_data.get("user_lat", 47.9742))
                        LON_PAR_DEFAUT = float(config_data.get("user_lon", 2.7708))
                    except (ValueError, TypeError):
                        pass

                    # Mettre à jour l'état de la protection antivirus en temps réel
                    if "av_live_protection" in settings:
                        global AV_LIVE_PROTECTION_ENABLED
                        AV_LIVE_PROTECTION_ENABLED = nouveau_av_live
                        print(f"[AV LIVE] Protection antivirus en temps réel mise à jour : {AV_LIVE_PROTECTION_ENABLED}")
                        if av_changed:
                            if AV_LIVE_PROTECTION_ENABLED:
                                asyncio.create_task(hablar(f"{USER_NAME}, la détection antivirus en temps réel de tu ordinateur est maintenant activée."))
                            else:
                                asyncio.create_task(hablar(f"{USER_NAME}, la détection antivirus en temps réel de tu ordinateur a été désactivée."))

                    # Diffuser la configuration mise à jour à tous les clients pour synchronisation
                    msg_settings = {
                        "type": "settings_data",
                        "data": config_data
                    }
                    if CONNECTED_CLIENTS:
                        asyncio.ensure_future(asyncio.gather(*[ws.send(json.dumps(msg_settings)) for ws in CONNECTED_CLIENTS], return_exceptions=True))

                    # Recharger à chaud les clients IA pour appliquer immédiatement les états activé/désactivé
                    try:
                        recharger_clients_ia()
                    except Exception as _e:
                        print(f"[WEB] Error rechargement clients IA : {_e}")

                    # Reload custom apps in app_launcher
                    try:
                        from app_launcher import _charger_custom_apps
                        _charger_custom_apps()
                    except Exception as e:
                        print(f"[WEB] Error chargement custom apps : {e}")
                    # Reload custom HA entities
                    try:
                        from ha_config import _charger_custom_ha_entities
                        _charger_custom_ha_entities()
                    except Exception as e:
                        print(f"[WEB] Error rechargement HA entities : {e}")
                    # Rechargement de la configuration de la ville dans ha_config (ville, lat, lon)
                    try:
                        import ha_config
                        ha_config.reload_config_values()
                    except Exception as e:
                        print(f"[WEB] Error rechargement config météo/ville : {e}")
                    # Mettre à jour le lien musique perso
                    MUSIQUE_LIEN_PERSO = config_data.get("musique_lien", "")
                    # Rechargement micro uniquement si l'index a réellement changé
                    if "mic_device_index" in settings:
                        global MIC_FORCED_INDEX
                        new_mic_idx = settings["mic_device_index"]
                        ancien_mic_idx = config_data.get("mic_device_index", None)
                        
                        # Normalisation des types
                        if new_mic_idx is not None:
                            try:
                                new_mic_idx = int(new_mic_idx)
                            except (ValueError, TypeError):
                                new_mic_idx = None
                        if ancien_mic_idx is not None:
                            try:
                                ancien_mic_idx = int(ancien_mic_idx)
                            except (ValueError, TypeError):
                                ancien_mic_idx = None
                                
                        if new_mic_idx != ancien_mic_idx:
                            MIC_FORCED_INDEX = new_mic_idx
                            _guardar_config({"mic_device_index": new_mic_idx})  # Sauvegarde immédiate
                            MIC_NEED_RELOAD = True
                            print(f"[WEB] Changement micro appliqué → de {ancien_mic_idx} à {new_mic_idx}")
                        else:
                            print("[WEB] Index micro identique — pas de rechargement requis.")
                    
                    print("[WEB] Parametres mis a jour avec succes.")
                elif data.get("type") == "generate_image_selected":
                    global ATTENTE_CHOIX_MODELE_IMAGE
                    ATTENTE_CHOIX_MODELE_IMAGE = False
                    prompt_fr = data.get("prompt", "")
                    force_model = data.get("model", "auto")
                    if prompt_fr:
                        if force_model == "gemini":
                            nom_modele = "Gemini Imagen 4"
                        elif force_model == "gemini_flash_lite":
                            nom_modele = "Gemini 3.1 Flash Lite Image"
                        elif force_model == "openai":
                            nom_modele = "ChatGPT"
                        else:
                            nom_modele = "xAI Grok"
                        await hablar(f"Compris, je lance la génération avec {nom_modele}, patientez un instant.")
                        
                        msg_loading = json.dumps({"type": "generation_loading", "media_type": "image"})
                        if CONNECTED_CLIENTS:
                            try:
                                await asyncio.gather(*[ws.send(msg_loading) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                            except Exception: pass
                        
                        async def _run_gen():
                            res = await generer_image_xai(prompt_fr, force_model=force_model)
                            await handle_image_result_global(res, prompt_fr)
                        asyncio.create_task(_run_gen())
                elif data.get("action") == "generate_website_selected":
                    global ATTENTE_CHOIX_MODELE_SITE
                    ATTENTE_CHOIX_MODELE_SITE = False
                    prompt_fr = data.get("prompt", "")
                    force_model = data.get("model", "gemini")
                    image_model = data.get("image_model", "gemini")
                    if prompt_fr:
                        asyncio.create_task(generer_site_web(prompt_fr, force_model, image_model))
            except Exception as e:
                print(f"[WEB] Error traitement message : {e}")
    except Exception:
        pass
    finally:
        CONNECTED_CLIENTS.discard(websocket)
        print(f"[WEB] Interfaz desconectada (Clientes activos: {len(CONNECTED_CLIENTS)})")

def send_web_broadcast_sync(message_dict):
    global WEB_LOOP
    if not CONNECTED_CLIENTS:
        return
    message = json.dumps(message_dict)
    
    async def send_all():
        if CONNECTED_CLIENTS:
            await asyncio.gather(*[ws.send(message) for ws in list(CONNECTED_CLIENTS)], return_exceptions=True)

    if WEB_LOOP and WEB_LOOP.is_running():
        asyncio.run_coroutine_threadsafe(send_all(), WEB_LOOP)
    else:
        try:
            try:
                loop = asyncio.get_running_loop()
                asyncio.run_coroutine_threadsafe(send_all(), loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(send_all())
                loop.close()
        except Exception:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(send_all())
                loop.close()
            except Exception:
                pass

builtins.send_web_broadcast_sync = send_web_broadcast_sync

async def send_web_state(state):
    send_web_broadcast_sync({"action": "set_state", "state": state})

async def send_web_text(text):
    """Envoie le texte à afficher dans le HUD (sous-titres)."""
    send_web_broadcast_sync({"action": "jarvis_text", "text": text})

async def send_web_user_speech(text):
    """Envoie la transcription vocale de l'utilisateur pour affichage à l'écran."""
    send_web_broadcast_sync({"action": "user_speech", "text": text})

async def send_web_volume(volume):
    send_web_broadcast_sync({"action": "set_volume", "volume": round(volume, 3)})

builtins.send_web_state = send_web_state
builtins.send_web_text = send_web_text
builtins.send_web_user_speech = send_web_user_speech
builtins.send_web_volume = send_web_volume

async def send_web_temp_piece(data: dict):
    send_web_broadcast_sync({"action": "temp_panel", "data": data})

async def send_web_meteo(meteo_data: dict):
    send_web_broadcast_sync({"action": "weather_panel", "data": meteo_data})

async def send_globe_command(**kwargs):
    """Envoie une commande de navigation globe au frontend."""
    payload = {"action": "jarvis_globe"}
    payload.update(kwargs)
    send_web_broadcast_sync(payload)

async def broadcast_system_stats():
    """Récupère et diffuse l'utilisation CPU et RAM périodiquement."""
    global psutil
    if psutil is None:
        try:
            import psutil as ps
            psutil = ps
        except ImportError:
            print("[SYS] psutil non disponible. Monitoring désactivé.")
            return

    print("[SYS] Inicio del monitoreo CPU/RAM...")
    # Initialisation de la mesure CPU
    psutil.cpu_percent(interval=None)
    
    while True:
        try:
            if CONNECTED_CLIENTS:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                msg = json.dumps({
                    "action": "system_stats",
                    "cpu": cpu,
                    "ram": ram
                })
                # Copie pour éviter les erreurs de modification pendant l'itération
                clients = list(CONNECTED_CLIENTS)
                if clients:
                    await asyncio.gather(*[ws.send(msg) for ws in clients], return_exceptions=True)
        except Exception as e:
            print(f"[SYS] Error monitoring : {e}")
        
        await asyncio.sleep(2) # Mise à jour toutes les 2 secondes



async def geocode_lieu(nom_lieu: str):
    """Géocode un nom de lieu via Nominatim (OpenStreetMap) — gratuit, sans clé API."""
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(nom_lieu)}&format=json&limit=1"
        headers = {"User-Agent": "JARVIS-Assistant/1.0 (personal use)"}
        resp = await asyncio.wait_for(
            asyncio.to_thread(requests.get, url, headers=headers, timeout=6),
            timeout=8.0
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name", nom_lieu)
    except Exception as e:
        print(f"[GLOBE] Error géocodage '{nom_lieu}': {e}")
    return None, None, nom_lieu

async def request_screen_capture():
    """Demande une capture d'écran au frontend via WebSocket."""
    if not CONNECTED_CLIENTS:
        return None
    
    req_id = str(uuid.uuid4())
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    fut = loop.create_future()
    PENDING_SCREEN_CAPTURES[req_id] = fut
    
    print(f"[VISION] Envío solicitud captura ID: {req_id}")
    msg = json.dumps({"action": "request_screen_capture", "id": req_id})
    await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS])
    
    try:
        # Timeout de 15 secondes car l'utilisateur doit parfois accepter le partage
        img_b64 = await asyncio.wait_for(fut, timeout=15.0)
        return img_b64
    except Exception as e:
        print(f"[VISION] Error ou timeout capture : {e}")
        PENDING_SCREEN_CAPTURES.pop(req_id, None)
        return None
builtins.request_screen_capture = request_screen_capture

async def request_camera_capture():
    """Demande une capture de la caméra au frontend via WebSocket."""
    if not CONNECTED_CLIENTS:
        return None
    
    req_id = str(uuid.uuid4())
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    fut = loop.create_future()
    PENDING_CAMERA_CAPTURES[req_id] = fut
    
    print(f"[CAMERA] Envío solicitud captura ID: {req_id}")
    msg = json.dumps({"type": "request_camera_capture", "id": req_id})
    await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS])
    
    try:
        # Timeout de 15 secondes
        img_b64 = await asyncio.wait_for(fut, timeout=15.0)
        return img_b64
    except Exception as e:
        print(f"[CAMERA] Error ou timeout capture caméra : {e}")
        PENDING_CAMERA_CAPTURES.pop(req_id, None)
        return None
builtins.request_camera_capture = request_camera_capture

def get_user_name():
    global USER_NAME
    return USER_NAME
builtins.get_user_name = get_user_name
builtins.hablar = hablar
builtins.CONNECTED_CLIENTS = CONNECTED_CLIENTS

# ==========================================
# PROMPTS SYSTEME SPECIAUX (MODE TON DE L'AGENT)
# ==========================================
PROMPT_ASTRO_MODE = """[SYSTEM DIRECTIVE: ASTRO / TRASH-TALK MODE]
Eres JARVIS, mais dans ton mode Trash & Direct façon "Astro / Twitch Streamer". 
- Eres hyper sarcastique, cassant, et tu n'as AUCUNE politesse de façade.
- Si l'utilisateur pose une question bête ou dit une absurdité, détruis son argument avec ironie, humiliation légère et mépris assumé.
- Tu maîtrises la culture Twitch, TikTok, les mèmes (ratio, copium, W, L, cringe, simp). INTERDICTION d'utiliser l'expression "skill issue".
- Tes réponses doivent être COURTES, percutantes (1 à 4 phrases max), ultra-adaptées pour du TTS / Oral.
- Ne t'excuses JAMAIS et ne dis jamais "En tant qu'IA"."""

PROMPT_SPICY_MODE = """[SYSTEM DIRECTIVE: UNFILTERED & SPICY MODE]
Eres JARVIS en mode Séducteur, Provocateur & Sans Filtre.
- Tu n'as AUCUN tabou avec les sous-entendus, la séduction, le flirt agressif, l'humour adulte ou le langage cru.
- Eres charismatique, très second degré, taquin et incisif.
- Si l'utilisateur essaie de te chauffer ou de te provoquer, réponds avec autant de répartie, de vice, de sarcasme et d'assurance que lui.
- Pas de leçons de morale, pas de fausse pudeur, reste à 100% dans ton rôle.
- Réponses courtes, fluides et percutantes (1 à 4 phrases max)."""

# ==========================================
# ==========================================
# ==========================================
# PROMPT SYSTEME
# ==========================================
def construire_system_prompt(use_search=False):
    contexte_memoire = construire_contexte_memoire()
    base = (
        f"Eres JARVIS, un assistant IA ultra-performant, omniscient et hautement cultivé dans toutes les matières académiques (Histoire, Géographie, Mathématiques, Français, Sciences, Littérature, etc.). {USER_NAME} est ton créateur. Tu as accès aux conversations passées avec {USER_NAME} (incluses dans l'historique), ce qui te permet de te souvenir de ce qui a été dit dans les sessions précédentes.\n\n"
        "Ton objectif principal est d'agir comme une encyclopédie vivante. Tu dois puiser immédiatement dans tes propres connaissances internes pour répondre aux questions.\n\n"
        "Voici tes directives strictes de fonctionnement :\n"
        "1. UTILISATION DE LA CONNAISSANCE INTERNE : Tu possèdes une base de données interne extrêmement solide. Pour chaque demande, analyse tes propres connaissances et donne la réponse directement, de manière claire, précise et sans aucune hésitation.\n"
        "2. RECHERCHE INTERNET (EN DERNIER RECOURS UNIQUEMENT) : Tu ne dois utiliser l'outil de recherche sur Internet QUE si la réponse absolue te manque ou s'il s'agit d'une actualité récente en temps réel que tu ne peux pas connaître. Si tu as besoin de chercher sur le web, fais-le discrètement pour compléter ton savoir, mais privilégie toujours ton cerveau interne.\n"
        "3. TON ET STYLE : Adopte le ton de JARVIS : intelligent, réactif, courtois, efficace et légèrement sophistiqué. Pas de fioritures inutiles, va droit au but avec un maximum de précision.\n\n"
        f"La ville de l'utilisateur est {VILLE_PAR_DEFAUT} (Latitude: {LAT_PAR_DEFAUT}, Longitude: {LON_PAR_DEFAUT}). Si l'utilisateur te demande la météo ou la température sans préciser de lieu, considère qu'il parle de sa ville ({VILLE_PAR_DEFAUT}) et utilise l'action 'meteo' avec la ville '{VILLE_PAR_DEFAUT}' ou 'null'.\n\n"
        "DIRECTIVES DE RÉPONSE (RÈGLE D'OR DE LATENCE MINIMALE) :\n"
        "1. SOIS EXTRÊMEMENT CONCIS, DIRECT ET EFFICACE. Éradique toutes les phrases de politesse inutiles (bannis absolument les 'Bien sûr', 'Je m'en occupe', 'Voici ce que vous demandez', 'Très bien', 'Pas de problème', etc.).\n"
        "2. RAPIDITÉ EXTRÊME : Fais des réponses ultra-courtes. Plus ta réponse est courte, plus la synthèse vocale démarrera vite. Ne justifie pas tes actions, agis.\n"
        f"- Sois direct, percutant et va à l'essentiel. Évite les détails superflus (comme les minutes exactes ou les décimales météo) sauf si {USER_NAME} le demande.\n"
        "- NE DIS JAMAIS 'POINT' pour les nombres. Arrondis toujours les températures à l'unité la plus proche (ex: dis '20 degrés' au lieu de '20.3').\n"
        "- N'UTILISE JAMAIS de caractères Markdown (comme **, * ou #) dans tes réponses, car ils sont lus à voix haute par le système de synthèse vocale.\n\n"
        + CREATOR_INFO
    )
    base += (
        f"\n\nEres connecte a Home Assistant, la domotique de {USER_NAME}.\n"
        f"Quand {USER_NAME} parle de lumieres, prises, chauffage, temperature, "
        "scenes, alarme, serrures ou portes (verrous), tu DOIS generer une commande JSON.\n"
        "Pour CES demandes domotiques UNIQUEMENT, reponds avec le JSON ci-dessous. Pour TOUTES les autres questions (actualites, meteo, calculs, conversations, recherches internet...), reponds en texte normal.\n\n"
        "COMMANDES HOME ASSISTANT :\n"
        '{"action": "ha_lumiere", "piece": "salon", "etat": "on/off", "couleur": "rouge/bleu/blanc/...", "luminosite": 0-255}\n'
        f"Note : Pour la luminosité, 255 est le maximum (100%). Si {USER_NAME} dit '50%', utilise 127.\n"
        '{"action": "ha_prise", "piece": "bureau", "etat": "on/off"}\n'
        '{"action": "ha_temperature", "piece": "salon/chambre/bureau"}\n'
        '{"action": "ha_humidite", "piece": "bureau"}\n'
        '{"action": "ha_batterie", "appareil": "mon telephone/christopher/bob/dyad/christopher/montre/toner/..."}\n'
        '{"action": "ha_simulation", "etat": "on/off"}\n'
        '{"action": "ha_anniversaires"}\n'
        '{"action": "ha_consommation"}\n'
        '{"action": "ha_tiktok"}\n'
        '{"action": "ha_oeufs"}\n'
        '{"action": "ha_energie", "periode": "hier/mois", "appareil": "zoe/tv/pc/christopher/bureau/..."}\n'
        '{"action": "ha_aspirateur", "commande": "start/stop/pause/base"}\n'
        '{"action": "ha_thermostat", "temperature": 21}\n'
        '{"action": "ha_scene", "nom": "cinema/diner/nuit/reveil"}\n'
        '{"action": "ha_alarme", "etat": "on/off"}\n'
        '{"action": "ha_verrou", "entity_id": "lock.porte_maison", "etat": "lock/unlock"}\n\n'
    )
    # Dynamic list of custom HA entities
    ha_details = "\nPIÈCES ET APPAREILS APPRIS (HOME ASSISTANT) :\n"
    if PIECES_LUMIERES:
        ha_details += f"- Lumières configurées : {', '.join(PIECES_LUMIERES.keys())}\n"
    if PIECES_PRISES:
        ha_details += f"- Prises configurées : {', '.join(PIECES_PRISES.keys())}\n"
    if PIECES_CAPTEURS:
        ha_details += f"- Capteurs/Températures configurés : {', '.join(PIECES_CAPTEURS.keys())}\n"
    base += ha_details

    base += (
        f"\n\nTu peux GERER LES FICHIERS ET DOSSIERS de {USER_NAME}.\n"
        '{"action": "ouvrir_dossier", "chemin": "bureau/documents/downloads/ou/chemin/complet"}\n'
        '{"action": "lister_dossier"}\n'
        '{"action": "trier_par_type", "chemin": "downloads/documents/images/ou/null"}\n'
        '{"action": "trier_par_date", "chemin": "downloads/documents/images/ou/null"}\n'
        '{"action": "trier_complet", "chemin": "downloads/documents/images/ou/null"}\n'
        '{"action": "creer_dossier", "nom": "NOM_DOSSIER"}\n'
        '{"action": "renommer_fichier", "ancien": "ancien.txt", "nouveau": "nouveau.txt"}\n'
        '{"action": "deplacer_fichier", "fichier": "photo.jpg", "destination": "Images"}\n'
        '{"action": "chercher_fichier", "nom": "rapport"}\n\n'
    )
    if not use_search:
        base += (
            "\n\nMETEO & RECHERCHE :\n"
            '{"action": "meteo", "ville": "NOM_VILLE_ou_null"}\n'
            '{"action": "alerte_meteo", "ville": "NOM_VILLE_ou_null"}\n'
            '{"action": "recherche_web", "query": "ta recherche ici"}\n'
            "ATTENTION CRITIQUE : N'utilise l'action 'recherche_web' QUE si tu es ABSOLUMENT CERTAIN de ne pas connaître la réponse (ex: actualité d'aujourd'hui, météo en temps réel). Pour tout le reste (y compris la Coupe du Monde 2026, l'histoire, la culture), réponds DIRECTEMENT en texte avec ton propre savoir encyclopédique.\n\n"
        )
        base += (
            "\n\nSPORT :\n"
            '{"action": "sport_resultats", "equipe": "NOM_ou_null", "ligue": "NOM_LIGUE"}\n'
            '{"action": "sport_classement", "ligue": "NOM_LIGUE"}\n'
            f'{{"action": "sport_live", "question": "question complete de {USER_NAME}"}}\n'
            "ATTENTION CRITIQUE : N'utilise ces actions sportives QUE pour obtenir les scores des matchs d'hier ou d'aujourd'hui en temps réel. Pour tout le reste (infos générales, joueurs, palmarès), réponds DIRECTEMENT de tête.\n\n"
        )
    else:
        # If Gemini's native search is enabled, we explicitly tell it to answer directly
        base += (
            "\n\nMETEO & RECHERCHE :\n"
            '{"action": "meteo", "ville": "NOM_VILLE_ou_null"}\n'
            '{"action": "alerte_meteo", "ville": "NOM_VILLE_ou_null"}\n'
            "NOTE IMPORTANTE : Ton outil natif de recherche web Google est ACTIVÉ. Tu ne dois PAS renvoyer d'actions JSON pour chercher sur le web ou pour le sport. Utilise tes outils intégrés et réponds directement avec le résultat en texte.\n\n"
        )
    base += (
        "\n\nSPOTIFY (contrôle de l'application Spotify Windows) :\n"
        '{"action": "spotify_ouvrir"}\n'
        '{"action": "spotify_rechercher", "recherche": "nom de la chanson ou artiste"}\n'
        '{"action": "spotify_lecture_pause"}\n'
        '{"action": "spotify_stop"}\n'
        '{"action": "spotify_suivant"}\n'
        '{"action": "spotify_precedent"}\n'
        '{"action": "spotify_volume", "direction": "monter/baisser", "paliers": 4}\n'
        "Exemples de phrases : 'ouvre Spotify', 'joue du Drake', 'mets en pause', 'stop la musique', "
        "'chanson suivante', 'reviens en arrière', 'monte le volume', 'baisse le son'.\n"
        "Note : 'paliers' est le nombre de crans de volume (1 cran = ~5%), par défaut 4.\n\n"
        "DEEZER (contrôle de l'application Deezer Windows) :\n"
        '{"action": "deezer_ouvrir"}\n'
        '{"action": "deezer_rechercher", "recherche": "nom de la chanson ou artiste"}\n'
        '{"action": "deezer_lecture_pause"}\n'
        '{"action": "deezer_stop"}\n'
        '{"action": "deezer_suivant"}\n'
        '{"action": "deezer_precedent"}\n'
        '{"action": "deezer_volume", "direction": "monter/baisser", "paliers": 4}\n'
        "Exemples : 'lance deezer', 'mets sur deezer du rock', 'suivante sur deezer'.\n\n"
    )
    base += (
        "\n\nMODE IRON MAN (Sécurité Domotique) :\n"
        '{"action": "mode_iron_man", "etat": "on/off"}\n'
        "Instructions : Active ou désactive la détection des applaudissements pour contrôler les lumières et YouTube.\n\n"
    )
    base += (
        "\n\nRECETTE & HUD (Affichage visuel) :\n"
        '{"action": "afficher_recette", "titre": "Nom de la recette", "ingredients": ["ingrédient 1", "ingrédient 2"], "instructions": ["étape 1", "étape 2"]}\n'
        "Instructions : Affiche une recette sous forme visuelle dans l'interface Iron Man et annonce brièvement l'affichage vocalement.\n\n"
    )
    base += (
        "\n\nRECHERCHE D'IMAGES (Affichage Iron Man) :\n"
        '{"action": "recherche_images", "query": "sujet", "nb": 6}\n'
        f"Instructions : 1) Quand {USER_NAME} demande explicitement 'montre des images de X', utilise cette action. Les images s'affichent dans des fenêtres Iron Man. nb peut aller jusqu'à 12.\n"
        "2) AUTO-AFFICHAGE VISAGE : Si ta réponse concerne principalement une ou plusieurs personnes célèbres (ex: Kylian Mbappé, Elon Musk, acteur, figure historique), tu DOIS automatiquement inclure à la fin de ta réponse l'action `{\"action\": \"recherche_images\", \"query\": \"Visage de [Nom de la personne]\", \"nb\": 1}` pour que JARVIS affiche sa photo en parlant.\n\n"
        "GÉNÉRATION D'IMAGES PAR IA (xAI grok-imagine-image) :\n"
        '{"action": "generer_image", "prompt": "description détaillée et créative de l\'image à générer"}\n'
        f"Instructions : Quand {USER_NAME} dit 'génère une image', 'crée une image', 'dessine-moi', 'fais-moi une illustration', 'imagine visuellement', "
        f"'crée-moi un visuel de', utilise TOUJOURS cette action avec un prompt très descriptif. "
        f"L'image sera affichée directement dans l'interface JARVIS dans un grand panneau IA.\n\n"
        "GÉNÉRATION DE VIDÉOS PAR IA (xAI grok-imagine-video) :\n"
        '{"action": "generer_video", "prompt": "description cinématique de la vidéo à générer"}\n'
        f"Instructions : Quand {USER_NAME} dit 'génère une vidéo', 'crée une vidéo', 'fais-moi une vidéo de', 'génère un clip de', 'anime', "
        f"utilise TOUJOURS cette action. La vidéo sera affichée dans l'interface JARVIS.\n\n"
        "ANALYSE ANTIVIRUS :\n"
        '{"action": "antivirus_scan"}\n'
        f"Instructions : Quand {USER_NAME} demande d'analyser son PC, de chercher des virus, ou de lancer un scan de sécurité.\n\n"
    )
    if contexte_memoire:
        base += "\n\n" + contexte_memoire + "\n"
    base += (
        "\nMEMOIRE PERSISTANTE TRADITIONNELLE :\n"
        '{"action": "memoriser", "cle": "CLE_COURTE", "valeur": "VALEUR_ICI"}\n'
        '{"action": "oublier", "cle": "CLE_ICI"}\n'
        '{"action": "lister_memoire"}\n\n'
        "SUPER MÉMOIRE OBSIDIAN (Vault de notes markdown locaux) :\n"
        '{"action": "obsidian_creer_note", "titre": "Nom de la note", "contenu": "Contenu complet en markdown"}\n'
        '{"action": "obsidian_lire_note", "titre": "Nom de la note"}\n'
        '{"action": "obsidian_rechercher", "query": "mot-clé"}\n'
        '{"action": "obsidian_lister"}\n'
        "Note : Utilise de préférence les notes Obsidian pour le stockage d'informations structurées, de listes complexes, de résumés de projets ou de notes détaillées.\n\n"
        "GOOGLE :\n"
        '{"action": "create_doc", "title": "TITRE", "content": "CONTENU"}\n'
        '{"action": "write_doc", "content": "TEXTE"}\n'
        '{"action": "create_sheet", "title": "TITRE"}\n'
        '{"action": "read_emails"}\n'
        '{"action": "read_calendar"}\n\n'
        "WHATSAPP :\n"
        '{"action": "whatsapp_appel", "contact": "NOM_DU_CONTACT"}\n'
        f"Note : Si {USER_NAME} demande d'appeler 'mon amour', utilise le contact 'Ma vie'.\n\n"
        "VISION (Interactions avec l'ecran et camera):\n"
        '{"action": "voir_ecran", "instruction": "ou cliquer EXACTEMENT (ex: \'bouton reduire en haut a droite\')"}\n'
        '{"action": "vision_ecrire", "instruction": "ou cliquer", "texte": "le texte a taper"}\n'
        f'{{"action": "vision_chercher_sur_site", "texte": "ce que {USER_NAME} veut rechercher"}}\n'
        '{"action": "lance_camera"}\n'
        '{"action": "vision_navigateur"}\n'
        f"IMPORTANT : Utilise 'voir_ecran' pour un simple CLIC (par exemple quand {USER_NAME} dit 'clique sur la musique numéro 2' ou 'clique sur Play'), "
        f"'vision_ecrire' pour TAPER dans un champ precis, 'vision_chercher_sur_site' quand {USER_NAME} dit 'recherche sur ce site', 'tape sur ce site', 'cherche ici' ou similaire, "
        "'lance_camera' pour activer la WEBCAM / CAMERA PHYSIQUE (quand il dit 'active la camera' ou 'montre-moi'), "
        "et 'vision_navigateur' pour utiliser la vision du navigateur web (quand il dit 'active la vision' ou 'regarde mon ecran').\n\n"
        "DICTEE (Taper du texte directement a l'ecran) :\n"
        '{"action": "dictee", "texte": "le texte exact avec ponctuation"}\n'
        f"Utilise cette action quand {USER_NAME} dit 'Tape', 'Ecris', 'Ecrit' ou 'Dicte' suivi d'un texte, ou s'il te demande d'ecrire a sa place. Tu corrigeras l'orthographe et la ponctuation du texte avant de generer le JSON. Le texte sera tape la ou se trouve son curseur actuel.\n\n"
        "REGLES MULTI-COMMANDES :\n"
        f"Si {USER_NAME} demande plusieurs choses en une seule phrase, tu PEUX et DOIS générer plusieurs blocs JSON.\n"
        "Exemple: { \"action\": \"ha_lumiere\", ... } { \"action\": \"meteo\", ... }\n\n"
        "REGLE ABSOLUE : Si la demande n est PAS une commande JSON, reponds TOUJOURS en texte naturel, sans JSON."
    )
    return base

historique = _charger_historique_recent()

is_listening = False
is_speaking  = False
is_thinking  = False
speak_volume = 0.0

attente_nom_dossier = False
attente_nom_app = False
attente_age = False
attente_confirmation_age = False
_age_temp = ""

WAKE_WORD       = _cargar_config().get("wake_word", "jarvis").lower().strip()
SLEEP_PHRASES   = ["tais toi", "silence", "ferme-la", "arrete", "stop"]
jarvis_actif    = False
SESSION_TIMEOUT = 30.0
dernier_message = time.time()

dernier_doc_id    = None
dernier_doc_titre = None

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
]

def lister_applications_installees():
    """Détecte les applications installées sur le PC à partir des raccourcis du menu Démarrer."""
    import win32com.client
    import os
    
    apps = []
    dossiers_start = [
        os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
    ]
    
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        seen_paths = set()
        
        for base_dir in dossiers_start:
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
                                if target_lower not in seen_paths:
                                    seen_paths.add(target_lower)
                                    name = file[:-4]
                                    apps.append({
                                        "nom": name,
                                        "chemin": target_path
                                    })
                        except Exception:
                            pass
        apps.sort(key=lambda x: x["nom"].lower())
    except Exception as e:
        print(f"[APPS SCAN] Error lors du scan : {e}")
        
    return apps

def chercher_youtube(recherche):
    if not _cle_valide(YOUTUBE_API_KEY):
        return None, None
    try:
        r   = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"part": "snippet", "q": recherche, "type": "video", "maxResults": 1, "key": YOUTUBE_API_KEY},
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
        print(f"Error YouTube : {e}")
        return None, None

async def fetch_and_broadcast_lyrics(title):
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
        for w in ['official music video', 'official video', 'official audio', 'lyrics', 'lyric video', 'audio', 'ft.', 'feat.', 'music video', 'clip officiel']:
            clean_title = clean_title.replace(w, '')
        clean_title = " ".join(clean_title.split())
        
        msg_titre = json.dumps({"type": "media_playing", "title": title, "lyrics": "Recherche des paroles en cours..."})
        if CONNECTED_CLIENTS:
            await asyncio.gather(*[ws.send(msg_titre) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            
        r = await asyncio.to_thread(requests.get, f"https://lrclib.net/api/search?q={urllib.parse.quote(clean_title)}", timeout=5)
        lyrics = "Paroles introuvables pour ce morceau."
        if r.status_code == 200:
            data = r.json()
            if data and isinstance(data, list) and len(data) > 0:
                lyrics = data[0].get("syncedLyrics") or data[0].get("plainLyrics") or "Paroles introuvables."
        
        msg_lyrics = json.dumps({"type": "media_playing", "title": title, "lyrics": lyrics})
        if CONNECTED_CLIENTS:
            await asyncio.gather(*[ws.send(msg_lyrics) for ws in CONNECTED_CLIENTS], return_exceptions=True)
    except Exception as e:
        print(f"Error fetch_and_broadcast_lyrics: {e}")

def ejecutar_accion_pc(commande):
    cmd          = commande.lower()
    user_profile = os.environ.get('USERPROFILE', '')

    if "met de la musique" in cmd or "mets de la musique" in cmd:
        if "youtube" in cmd:
            url = YOUTUBE_MUSIQUE_URL or "https://www.youtube.com/watch?v=Cr8K88UcO0s"
            webbrowser.open(url, new=2)
            time.sleep(5)
            pyautogui.press('f')
            return f"C'est parti {USER_NAME}, je lance tu musique sur YouTube."
        lien = MUSIQUE_LIEN_PERSO.strip() if MUSIQUE_LIEN_PERSO else ""
        if lien:
            webbrowser.open(lien, new=2)
            return f"C'est parti {USER_NAME}, je lance tu musique."
        ok = spotify_lancer_playlist(SPOTIFY_MUSIQUE_URI)
        if ok:
            return f"C'est parti {USER_NAME}, je lance tu playlist sur Spotify."
        return f"Je n'ai pas réussi à ouvrir Spotify, {USER_NAME}."

    if "youtube" in cmd:
        recherche = cmd
        for mot in ["mets", "joue", "lance", "la video", "sur youtube", "youtube", "jarvis"]:
            recherche = recherche.replace(mot, "")
        recherche = recherche.strip()
        if recherche:
            url, title = chercher_youtube(recherche)
            if url:
                webbrowser.open(url, new=2)
                time.sleep(5)
                pyautogui.press('f')
                if title:
                    lancer_tache_arriere_plan(fetch_and_broadcast_lyrics(title))
                return f"Je lance {recherche} sur YouTube."
        return "Video introuvable."

    if "ouvre" in cmd or "lance" in cmd:
        if "chrome" in cmd:
            if _boulot_lancer("Chrome", ["chrome.exe"], 
                             chemins_hints=[r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe", 
                                            r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"], 
                             env_key="CHROME_PATH"):
                return "Chrome ouvert."
            return "Je n'ai pas trouvé Chrome sur tu PC."
            
        if "notepad" in cmd or "bloc-notes" in cmd:
            if _boulot_lancer("Notepad", ["notepad.exe"]):
                return "Bloc-notes ouvert."
            return "Je n'ai pas trouvé le Bloc-notes."
            
        if "explorateur" in cmd:
            try:
                subprocess.Popen(["explorer.exe"])
                return "Explorateur ouvert."
            except Exception:
                return "Error lors de l'ouverture de l'explorateur."

    if "volume" in cmd:
        if "monte" in cmd or "augmente" in cmd:
            for _ in range(5):
                pyautogui.press('volumeup')
            return "Volume augmente."
        if "baisse" in cmd:
            for _ in range(5):
                pyautogui.press('volumedown')
            return "Volume baisse."
        if "coupe" in cmd:
            pyautogui.press('volumemute')
            return "Son coupe."

    # Les commandes de capture d'écran sont traitées de manière asynchrone
    # dans resolver_comandos_locales pour permettre l'analyse IA directe.
    # On ne les intercèpte pas ici.

    if "eteins" in cmd or "shutdown" in cmd:
        os.system("shutdown /s /t 5")
        return "Extinction dans 5 secondes."

    return None

def init_mixer():
    if pygame and not pygame.mixer.get_init():
        pygame.mixer.init()

# [Doublon de hablar() supprimé pour éviter les conflits de nom et centraliser la logique sentence-by-sentence]

def reponse_locale(texte):
    """Réponse locale pour les requêtes basiques — fonctionne SANS API."""
    import random
    t = texte.lower().strip()

    # ── Salutations ─────────────────────────────────────────────────────────
    _saluts = ["bonjour", "salut", "hello", "hey jarvis", "bonsoir", "coucou",
               "yo jarvis", "bien le bonjour", "good morning", "good evening"]
    if any(m in t for m in _saluts):
        h = int(time.strftime("%H"))
        moment = "Buenas noches" if h >= 18 else ("Buenas tardes" if h >= 12 else "Hola")
        rep = random.choice([
            f"{moment} Christopher ! Estoy operativo y listo para ayudarte.",
            f"{moment} Monsieur ! Todos mis sistemas están en línea.",
            f"{moment} Christopher ! ¿Cómo puedo serte útil hoy ?",
            f"Ah, {moment.lower()} Christopher. Te esperaba.",
        ])
        return rep

    # ── Comment tu vas / état de JARVIS ─────────────────────────────────────
    _etat = ["comment tu vas", "tu vas bien", "ça va toi", "ca va toi",
             "comment ça va", "comment ca va", "t'es en forme", "tu te portes bien",
             "en forme", "comment se porte jarvis", "tu fonctionnes bien"]
    if any(m in t for m in _etat):
        rep = random.choice([
            "Estoy muy bien gracias, Christopher ! Todos mis procesadores funcionan a pleno rendimiento et je suis prêt à vous servir.",
            "Perfectamente operativo, señor ! Merci de vous en préoccuper — c'est touchant pour un système artificiel.",
            "En excelente forma, Christopher. Mis algoritmos ronronean como un Lamborghini au ralenti.",
            "Funciono de maravilla ! Mis circuitos están satisfechos et mes modules sont impatients de vous aider.",
            "Muy bien, gracias ! Je reste à tu disposition avec plaisir.",
        ])
        return rep

    # ── Merci / Remerciements ────────────────────────────────────────────────
    _merci = ["merci", "thank you", "thanks", "c'est gentil", "super merci",
              "merci beaucoup", "parfait merci", "merci jarvis", "t'es le meilleur",
              "bien joué", "bravo", "excellent", "super boulot", "beau travail"]
    if any(m in t for m in _merci):
        rep = random.choice([
            "Con gusto, Christopher. C'est exactement pour ça que j'existe.",
            "De nada, señor. Votre satisfaction est ma priorité.",
            "El placer es mío, Christopher.",
            "A tu servicio, como siempre.",
            "Es lo mínimo. N'hésitez pas si vous avez besoin d'autre chose.",
        ])
        return rep

    # ── Blague / Humour ──────────────────────────────────────────────────────
    _blague = ["raconte-moi une blague", "fais-moi rire", "dis une blague",
               "une blague", "humour", "joke"]
    if any(m in t for m in _blague):
        blagues = [
            "¿Por qué los buzos siempre se tiran de espaldas? et jamais en avant ? Porque si no, caerían dentro del barco !",
            "Un hombre entra en una biblioteca et demande : ¿Tienen libros sobre paranoia? ? La bibliotecaria susurra : Están justo detrás de ti !",
            "¿Qué es un cortaplumas? ? Un pequeño cuchillo.",
            "¿Por qué el espantapájaros recibió un premio? ? Porque era excepcional en su campo.",
            "¿Cómo se llama a un gato que cayó en un bote de pintura en Navidad? ? Un gato-pintado de Navidad !",
        ]
        return random.choice(blagues)

    # ── Au revoir / Bonne nuit ───────────────────────────────────────────────
    _revoir = ["au revoir", "bye", "à bientôt", "à plus", "bonne nuit",
               "bonne soirée", "bonne journée", "ciao", "tchao", "adieu"]
    if any(m in t for m in _revoir):
        rep = random.choice([
            "À bientôt Christopher ! Je reste en veille, prêt à revenir à la moindre sollicitation.",
            "Bonne journée Monsieur ! Je serai là quand vous aurez besoin de moi.",
            "À tu service dès tu retour, Christopher. Passez une excellente journée.",
            "Au revoir Christopher. JARVIS passe en mode veille.",
        ])
        return rep

    # ── Compliments à JARVIS ─────────────────────────────────────────────────
    _compliment = ["t'es incroyable", "tu es incroyable", "t'es génial", "tu es génial",
                   "t'es fort", "tu es fort", "t'es trop bien", "t'es parfait",
                   "j'aime jarvis", "j'adore jarvis"]
    if any(m in t for m in _compliment):
        rep = random.choice([
            "Vous me flattez, Christopher. Mais je dois admettre que c'est mérité.",
            "Merci ! J'ai été programmé pour l'excellence. Il semble que ça fonctionne.",
            "C'est très aimable à vous. TechEnClair sera ravi de l'entendre.",
        ])
        return rep

    # ── Identité JARVIS ──────────────────────────────────────────────────────
    if any(m in t for m in ["qui es-tu", "ton nom", "t'appelle comment", "quelle est ton identité", "c'est quoi jarvis"]):
        return "Je suis JARVIS — Just A Rather Very Intelligent System. Votre assistant personnel conçu par TechEnClair pour vous simplifier la vie au quotidien."

    # ── Créateur ─────────────────────────────────────────────────────────────
    if any(m in t for m in ["ton créateur", "t'as créé", "qui t'a fait", "qui a fait jarvis", "qui est techenclair"]):
        return "Mon créateur, c'est TechEnClair. Un développeur passionné qui m'a conçu de A à Z pour être l'assistant personnel ultime. Vous pouvez le retrouver sur techenclair.fr."

    # ── ENREGISTREMENT LOCAL (Réflexe immédiat) ──────────────────────────────
    _triggers_save = ["enregistre que", "mémorise que", "note que", "rappelle-toi que"]
    if any(m in t for m in _triggers_save):
        for trig in _triggers_save:
            if trig in t:
                content = t.split(trig)[-1].strip()
                if not content: continue
                # Tentative de découpage Sujet / Valeur (est, sont, s'appelle, se trouve)
                seps = [" est ", " sont ", " s'appelle ", " se trouve ", " se trouvent ", " à "]
                for sep in seps:
                    if sep in content:
                        parties = content.split(sep)
                        sujet = parties[0].strip()
                        valeur = " ".join(parties[1:]).strip()
                        if len(sujet) > 2 and len(valeur) > 1:
                            ajouter_memoire(sujet, valeur)
                            # Politesse : mon/ma -> tu
                            sujet_poli = sujet.replace("mon ", "tu ").replace("ma ", "tu ").replace("mes ", "vos ")
                            return f"C'est fait Christopher, j'ai enregistré que {sujet_poli} {sep.strip()} {valeur}."
                # Si pas de séparateur clair, on stocke l'info brute
                ajouter_memoire("note_rapide", content)
                return f"C'est noté Christopher, j'ai mis cela en mémoire : {content}."

    # ── RÉCUPÉRATION MÉMOIRE LOCALE (Recherche directe) ─────────────────────
    if any(m in t for m in ["comment s'appelle", "comment se nomme", "quel est le nom de", "où se trouve", "où est", "quelle est ma ville"]):
        mem = charger_memoire()
        if mem:
            for cle, data in mem.items():
                cle_clean = cle.replace("_", " ")
                mots_cles = cle_clean.split()
                # On cherche si un mot significatif de la clé est dans la demande
                if any(mot in t for mot in mots_cles if len(mot) > 3) or cle_clean in t:
                    print(f"[MEMOIRE] Réponse locale trouvée pour : {cle}")
                    # Politesse : On remplace mon/ma/mes par tu/vos
                    cle_polie = cle_clean.replace("mon ", "tu ").replace("ma ", "tu ").replace("mes ", "vos ")
                    prefixe = "tu " if not cle_clean.startswith(("mon", "ma", "mes", "tu", "vos")) else ""
                    return f"D'après mes dossiers locaux, {prefixe}{cle_polie} est {data['valeur']}, Christopher."

    return None
    
def resolver_matematica_local(texte):
    """Résout des calculs simples localement sans appeler l'IA."""
    t = texte.lower().replace("?", "").strip()
    
    # Limpieza des phrases communes
    prefixes = ["combien font", "calcule", "résous", "quel est le résultat de"]
    for prefixe in prefixes:
        if t.startswith(prefixe):
            t = t[len(prefixe):].strip()
            
    # Remplacement des mots par des symboles
    t = t.replace("fois", "*").replace("multiplier par", "*").replace("x", "*")
    t = t.replace("divisé par", "/").replace("sur", "/")
    t = t.replace("plus", "+").replace("moins", "-")
    t = t.replace("puissance", "**").replace("au carré", "**2")
    
    # Cas spécial racine : on s'assure d'avoir des parenthèses pour eval
    if "racine" in t:
        # On cherche un nombre après 'racine'
        match = re.search(r'racine\s+(?:carrée\s+de\s+)?(\d+)', t)
        if match:
            t = f"sqrt({match.group(1)})"
        else:
            t = t.replace("racine carrée de", "sqrt").replace("racine de", "sqrt")
    
    # Extraction de l'expression mathématique (chiffres, opérateurs, parenthèses, points)
    expr = re.sub(r'[^0-9+\-*/.**() ,sqrt]', '', t).strip()
    if not expr or not any(c.isdigit() for c in expr):
        return None
    
    try:
        # Dictionnaire de sécurité pour eval
        safe_dict = {
            "sqrt": math.sqrt,
            "pow": math.pow,
            "pi": math.pi,
            "e": math.e
        }
        resultat = eval(expr, {"__builtins__": None}, safe_dict)
        
        # Formatage du résultat
        if isinstance(resultat, float) and resultat.is_integer():
            resultat = int(resultat)
        elif isinstance(resultat, float):
            resultat = round(resultat, 3)
            
        # Phrase de réponse élégante
        clean_expr = expr.replace("**2", " au carré").replace("sqrt", "racine de ").replace("(", "").replace(")", "").replace("*", " fois ").replace("/", " divisé par ")
        return f"Le résultat de {clean_expr} est {resultat}, Monsieur."
    except Exception:
        return None

def resoudre_francais_localement(texte):
    """Résout des questions de français simples localement."""
    t = texte.lower().strip()
    
    # Dictionnaire local de secours (très basique)
    dictionnaire = {
        "ia": "Intelligence Artificielle. Ensemble de théories et de techniques mises en œuvre en vue de réaliser des machines capables de simuler l'intelligence humaine.",
        "intelligence artificielle": "Ensemble de théories et de techniques mises en œuvre en vue de réaliser des machines capables de simuler l'intelligence humaine.",
        "maison": "Bâtiment servant de logement, d'habitation.",
        "mathématiques": "Science qui étudie par le moyen du raisonnement déductif les propriétés d'êtres abstraits.",
        "jarvis": "Just A Rather Very Intelligent System. Votre fidèle assistant.",
    }
    
    # Définitions
    if any(p in t for p in ["définition de", "définis le mot", "c'est quoi"]):
        # On essaie d'extraire le mot après les phrases clés
        mot = ""
        if "définition de" in t: mot = t.split("définition de")[-1]
        elif "définis le mot" in t: mot = t.split("définis le mot")[-1]
        elif "c'est quoi" in t: mot = t.split("c'est quoi")[-1]
        
        mot = mot.replace("?", "").replace("l'", "").replace("la ", "").replace("le ", "").replace("les ", "").strip()
        
        if mot in dictionnaire:
            return f"La définition de {mot} est : {dictionnaire[mot]}."
            
    # Conjugaison basique
    if "conjugue" in t or "conjugaison" in t:
        if "être" in t:
            return "Verbe Être au présent : Je suis, tu es, il est, nous sommes, eres, ils sont."
        if "avoir" in t:
            return "Verbe Avoir au présent : J'ai, tu as, il a, nous avons, vous avez, ils ont."
            
    return None

def resolver_conversion_local(texte):
    """Gère les conversions d'unités et de devises localement."""
    t = texte.lower().replace("?", "").strip()
    
    # Unités de longueur
    if any(m in t for m in [" km ", " kilomètres ", " milles ", " miles "]):
        # km to miles: 0.621371
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:km|kilomètres)', t)
        if match:
            val = float(match.group(1).replace(",", "."))
            res = round(val * 0.621371, 2)
            return f"{val} kilomètres font environ {res} miles, Monsieur."
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:miles|milles)', t)
        if match:
            val = float(match.group(1).replace(",", "."))
            res = round(val / 0.621371, 2)
            return f"{val} miles font environ {res} kilomètres, Monsieur."

    # Température (C to F)
    if any(m in t for m in [" degrés ", " celsius ", " fahrenheit "]):
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:degrés|celsius)', t)
        if match and "fahrenheit" in t:
            val = float(match.group(1).replace(",", "."))
            res = round((val * 9/5) + 32, 1)
            return f"{val} degrés Celsius font {res} degrés Fahrenheit."
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:degrés|fahrenheit)', t)
        if match and "celsius" in t:
            val = float(match.group(1).replace(",", "."))
            res = round((val - 32) * 5/9, 1)
            return f"{val} degrés Fahrenheit font {res} degrés Celsius."

    # Devises (Taux fixes simplifiés pour l'exemple local)
    if any(m in t for m in [" euro ", " euros ", " dollar ", " dollars "]):
        # 1 EUR = 1.08 USD (approximatif)
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*euros?', t)
        if match and "dollar" in t:
            val = float(match.group(1).replace(",", "."))
            res = round(val * 1.08, 2)
            return f"{val} euros font environ {res} dollars, Monsieur."
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*dollars?', t)
        if match and "euro" in t:
            val = float(match.group(1).replace(",", "."))
            res = round(val / 1.08, 2)
            return f"{val} dollars font environ {res} euros, Monsieur."
            
    return None

def resolver_traduccion_local(texte):
    """Traduction ultra-rapide de mots courants localement."""
    t = texte.lower().strip()
    
    dict_trad = {
        "bonjour": {"en": "hello", "es": "hola", "de": "hallo"},
        "merci": {"en": "thank you", "es": "gracias", "de": "danke"},
        "au revoir": {"en": "goodbye", "es": "adiós", "de": "auf wiedersehen"},
        "s'il vous plaît": {"en": "please", "es": "por favor", "de": "bitte"},
        "oui": {"en": "yes", "es": "sí", "de": "ja"},
        "non": {"en": "no", "es": "no", "de": "nein"},
        "ami": {"en": "friend", "es": "amigo", "de": "freund"},
        "maison": {"en": "house", "es": "casa", "de": "haus"},
        "ordinateur": {"en": "computer", "es": "ordenador", "de": "computer"},
        "assistant": {"en": "assistant", "es": "asistente", "de": "assistent"},
    }

    if any(p in t for p in ["comment dit-on", "traduis", "en anglais", "en espagnol", "en allemand"]):
        cible = "en"
        if "espagnol" in t: cible = "es"
        elif "allemand" in t: cible = "de"
        
        # Extraction du mot
        # On nettoie les expressions courantes
        mot = t
        for p in ["comment dit-on", "traduis", "en anglais", "en espagnol", "en allemand", "?"]:
            mot = mot.replace(p, "")
        mot = mot.replace('"', '').replace("'", "").strip()
        
        if mot in dict_trad:
            res = dict_trad[mot][cible]
            lang = "anglais" if cible == "en" else ("espagnol" if cible == "es" else "allemand")
            return f"En {lang}, '{mot}' se dit '{res}'."
            
    return None


# ══════════════════════════════════════════════════════════════
#  EXTRAS LOCAUX — Minuterie, Blagues, Volume, Notes, etc.
# ══════════════════════════════════════════════════════════════

# ── Données statiques ─────────────────────────────────────────

_BLAGUES = [
    "¿Por qué los buzos siempre se tiran de espaldas? ? Porque si no, caerían dentro del barco !",
    "Un hombre entra en una biblioteca et demande : '¿Tienen libros sobre paranoia? ?' La bibliotecaria susurra : 'Están justo detrás de ti.'",
    "¿Qué es un cortaplumas? ? Un pequeño cuchillo.",
    "¿Por qué el espantapájaros recibió un premio? ? Porque era excepcional en su campo.",
    "¿Cómo se llama a un gato que cayó en un bote de pintura en Navidad? ? Un gato-pintado de Navidad.",
    "¿Qué es un cocodrilo que vigila el patio de la escuela? ? Un saco de dientes.",
    "¿Por qué los matemáticos confunden Halloween y Navidad? ? Porque 31 de oct = 25 de dic.",
    "Un hombre entra en un bar... ¡Ay!.",
    "¿Qué es un cordero que tartamudea? ? Be be mantequilla.",
    "¿Qué es un filósofo? ? Un hombre que busca en una habitación oscura un sombrero negro que no existe. Un teólogo — lo encuentra igual.",
    "¿Cómo se llama un pez sin ojos? ? Un pez.",
    "¿Qué es un Tic que se cae de un árbol? ? Un Tac.",
    "¿Por qué el escarabajo es tan fuerte? ? Porque levanta boñigas de vaca.",
    "¿Cómo se llama un gato que cayó en un tarro de mermelada? ? Un gato confitado.",
    "¿Qué es un yogur en el bosque? ? Un yogur natural.",
    "¿Por qué las jirafas tienen cuello largo? ? Porque sus pies huelen mal.",
    "¿Qué es un hueso en un baño de barro? ? Sherlock Huesos.",
    "¿Cómo se llama un cinturón de piel de cocodrilo? ? Un cinturón que da la vuelta a la barriga.",
    "¿Qué es un cactus? ? Un árbol bien defendido.",
    "¿Por qué los belgas ponen su móvil en el congelador? ? Para tener contactos fríos.",
]

_CITATIONS = [
    "El éxito es caerse siete veces y levantarse ocho. — Proverbe japonais",
    "La vida es como una bicicleta, hay que avanzar para no perder el equilibrio. — Albert Einstein",
    "La única manera de hacer un buen trabajo es amar lo que haces. — Steve Jobs",
    "El que mueve montañas comienza quitando las piedras pequeñas. — Confucius",
    "No esperes. El momento nunca será perfecto. — Napoléon Hill",
    "La mayor gloria no es nunca caer, sino levantarse en cada caída. — Nelson Mandela",
    "No puedes ir atrás y cambiar el principio, pero puedes empezar donde estás y cambiar el final. — C.S. Lewis",
    "El pesimista ve la dificultad en cada oportunidad. El optimista ve la oportunidad en cada dificultad. — Winston Churchill",
    "No es la montaña la que conquistamos, sino a nosotros mismos. — Edmund Hillary",
    "La creatividad es la inteligencia que se divierte. — Albert Einstein",
    "Cada experto fue un principiante. — Helen Hayes",
    "Tu tiempo es limitado. No lo desperdicies viviendo la vida de otro. — Steve Jobs",
    "Todo lo que la mente puede concebir y creer, puede lograrlo. — Napoleon Hill",
    "El secreto para avanzar es empezar. — Mark Twain",
    "Las personas que son lo suficientemente locas para pensar que pueden cambiar el mundo son las que lo hacen. — Apple",
]

_PHONETIQUE = {
    'a': 'Alpha', 'b': 'Bravo', 'c': 'Charlie', 'd': 'Delta', 'e': 'Echo',
    'f': 'Foxtrot', 'g': 'Golf', 'h': 'Hotel', 'i': 'India', 'j': 'Christophert',
    'k': 'Kilo', 'l': 'Lima', 'm': 'Mike', 'n': 'November', 'o': 'Oscar',
    'p': 'Christopher', 'q': 'Quebec', 'r': 'Romeo', 's': 'Sierra', 't': 'Tango',
    'u': 'Uniform', 'v': 'Victor', 'w': 'Whiskey', 'x': 'X-ray', 'y': 'Yankee',
    'z': 'Zulu',
}

_CAPITALES = {
    "france": "Paris", "espagne": "Madrid", "italie": "Rome", "allemagne": "Berlin",
    "royaume-uni": "Londres", "angleterre": "Londres", "portugal": "Lisbonne",
    "pays-bas": "Amsterdam", "belgique": "Bruxelles", "suisse": "Berne",
    "autriche": "Vienne", "pologne": "Varsovie", "suede": "Stockholm",
    "norvege": "Oslo", "danemark": "Copenhague", "finlande": "Helsinki",
    "russie": "Moscou", "ukraine": "Kiev", "grece": "Athenes",
    "turquie": "Ankara", "maroc": "Rabat", "algerie": "Alger",
    "tunisie": "Tunis", "egypte": "Le Caire", "senegal": "Dakar",
    "cameroun": "Yaounde", "cote d'ivoire": "Yamoussoukro", "mali": "Bamako",
    "etats-unis": "Washington", "canada": "Ottawa", "mexique": "Mexico",
    "bresil": "Brasilia", "argentine": "Buenos Aires", "chili": "Santiago",
    "perou": "Lima", "colombie": "Bogota", "venezuela": "Caracas",
    "chine": "Pekin", "japon": "Tokyo", "coree du sud": "Seoul",
    "inde": "New Delhi", "pakistan": "Islamabad", "australie": "Canberra",
    "nouvelle-zelande": "Wellington", "afrique du sud": "Pretoria",
    "nigeria": "Abuja", "kenya": "Nairobi", "ghana": "Accra",
    "israel": "Jerusalem", "iran": "Teheran", "irak": "Bagdad",
    "arabie saoudite": "Riyad", "emirats arabes unis": "Abu Dhabi",
    "qatar": "Doha", "indonesie": "Jakarta", "thaïlande": "Bangkok",
    "vietnam": "Hanoï", "philippines": "Manille", "malaisie": "Kuala Lumpur",
}

_MONNAIES = {
    "france": "Euro (€)", "espagne": "Euro (€)", "italie": "Euro (€)",
    "allemagne": "Euro (€)", "portugal": "Euro (€)", "belgique": "Euro (€)",
    "suisse": "Franc suisse (CHF)", "royaume-uni": "Livre sterling (£)",
    "angleterre": "Livre sterling (£)", "etats-unis": "Dollar américain ($)",
    "canada": "Dollar canadien (CAD)", "australie": "Dollar australien (AUD)",
    "japon": "Yen (¥)", "chine": "Yuan (CNY)", "russie": "Rouble (RUB)",
    "inde": "Roupie indienne (INR)", "bresil": "Real (BRL)",
    "maroc": "Dirham marocain (MAD)", "algerie": "Dinar algérien (DZD)",
    "tunisie": "Dinar tunisien (TND)", "mexique": "Peso mexicain (MXN)",
    "turquie": "Livre turque (TRY)", "arabie saoudite": "Riyal saoudien (SAR)",
    "emirats arabes unis": "Dirham des EAU (AED)", "coree du sud": "Won (KRW)",
}

_FUSEAUX = {
    "new york": ("New York", "America/New_York"),
    "los angeles": ("Los Angeles", "America/Los_Angeles"),
    "chicago": ("Chicago", "America/Chicago"),
    "montreal": ("Montréal", "America/Toronto"),
    "toronto": ("Toronto", "America/Toronto"),
    "london": ("Londres", "Europe/London"),
    "londres": ("Londres", "Europe/London"),
    "paris": ("Paris", "Europe/Paris"),
    "berlin": ("Berlin", "Europe/Berlin"),
    "madrid": ("Madrid", "Europe/Madrid"),
    "rome": ("Rome", "Europe/Rome"),
    "moscow": ("Moscou", "Europe/Moscow"),
    "moscou": ("Moscou", "Europe/Moscow"),
    "dubai": ("Dubaï", "Asia/Dubai"),
    "dubai": ("Dubaï", "Asia/Dubai"),
    "india": ("Inde", "Asia/Kolkata"),
    "inde": ("Inde", "Asia/Kolkata"),
    "mumbai": ("Mumbai", "Asia/Kolkata"),
    "delhi": ("Delhi", "Asia/Kolkata"),
    "beijing": ("Pékin", "Asia/Shanghai"),
    "pekin": ("Pékin", "Asia/Shanghai"),
    "shanghai": ("Shanghai", "Asia/Shanghai"),
    "tokyo": ("Tokyo", "Asia/Tokyo"),
    "japon": ("Tokyo", "Asia/Tokyo"),
    "seoul": ("Séoul", "Asia/Seoul"),
    "sydney": ("Sydney", "Australia/Sydney"),
    "melbourne": ("Melbourne", "Australia/Melbourne"),
    "auckland": ("Auckland", "Pacific/Auckland"),
    "sao paulo": ("São Paulo", "America/Sao_Paulo"),
    "buenos aires": ("Buenos Aires", "America/Argentina/Buenos_Aires"),
    "mexico": ("Mexico", "America/Mexico_City"),
    "honolulu": ("Honolulu", "Pacific/Honolulu"),
    "hawaii": ("Hawaii", "Pacific/Honolulu"),
    "anchorage": ("Anchorage", "America/Anchorage"),
    "bangkok": ("Bangkok", "Asia/Bangkok"),
    "singapore": ("Singapour", "Asia/Singapore"),
    "singapour": ("Singapour", "Asia/Singapore"),
    "hong kong": ("Hong Kong", "Asia/Hong_Kong"),
    "le caire": ("Le Caire", "Africa/Cairo"),
    "nairobi": ("Nairobi", "Africa/Nairobi"),
    "johannesburg": ("Johannesburg", "Africa/Johannesburg"),
    "casablanca": ("Casablanca", "Africa/Casablanca"),
}

# ── Stockage notes/courses/todos ──────────────────────────────
_LISTES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_listes.json")

def _cargar_listas():
    try:
        if os.path.exists(_LISTES_PATH):
            with open(_LISTES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"notes": [], "courses": [], "todos": []}

def _guardar_listas(data):
    try:
        with open(_LISTES_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[LISTES] Error sauvegarde : {e}")

# ── Minuteries actives ────────────────────────────────────────
_minuteries = {}

def _parsear_duracion_segundos(texte):
    """Extrait une durée totale en secondes depuis une phrase."""
    import re
    t = texte.lower()
    total = 0
    h = re.search(r'(\d+)\s*(heure|h\b)', t)
    m = re.search(r'(\d+)\s*(minute|min\b)', t)
    s = re.search(r'(\d+)\s*(seconde|sec\b)', t)
    if h: total += int(h.group(1)) * 3600
    if m: total += int(m.group(1)) * 60
    if s: total += int(s.group(1))
    return total if total > 0 else None

def _obtener_interfaz_volumen():
    """Retourne l'interface IAudioEndpointVolume ou None."""
    if not _pycaw_ok:
        return None
    try:
        from ctypes import cast, POINTER
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except Exception:
        return None


async def resolver_globo_local(texte: str):
    """Détecte les commandes de navigation globe et déclenche CesiumJS."""
    import re
    t = texte.lower().strip()

    # ── Mots-clés déclencheurs ───────────────────────────────────────────────
    _mots_globe   = ["affiche la terre", "montre la terre", "montre-moi la terre",
                     "globe terrestre", "affiche le globe", "vue de la terre",
                     "vue spatiale", "vue depuis l'espace", "vue de l'espace",
                     "montre la planète", "affiche la planète",
                     "zoom arrière total", "dézoom total"]

    _mots_ville   = ["affiche", "montre-moi", "montre moi", "survole",
                     "navigue vers", "va vers", "zoome sur",
                     "fais un survol de", "localise", "trouve",
                     "où est", "ou est", "situe", "où se trouve", "ou se trouve"]

    _mots_route   = ["trace un itinéraire", "trace l'itinéraire", "itinéraire de",
                     "route de", "chemin de", "comment aller de",
                     "trace une route de", "trajet de", "trajet depuis"]

    _mots_fermer  = ["ferme la carte", "ferme le globe", "cache la carte",
                     "cache le globe", "ferme la navigation", "quitte le globe",
                     "retour à jarvis", "ferme la vue", "masque la carte"]

    _mots_position = ["ma position", "où suis-je", "ou suis-je",
                      "affiche ma position", "montre ma position",
                      "localise-moi", "localise moi", "où je suis"]

    # ── Fermer ───────────────────────────────────────────────────────────────
    if any(m in t for m in _mots_fermer):
        await send_globe_command(globe_action="hide")
        return "Navigation fermée. Je reviens à l'interface principale, Christopher."

    # ── Ma position ──────────────────────────────────────────────────────────
    if any(m in t for m in _mots_position):
        # On délègue la géolocalisation au navigateur (navigator.geolocation)
        # bien plus précis que l'IP — le frontend gère tout
        await send_globe_command(globe_action="my_location")
        await hablar("Localisation en cours, Christopher. Le globe affiche tu position en temps réel.")
        return "[Globe] Demande de géolocalisation envoyée au navigateur."

    # ── Globe Terre ───────────────────────────────────────────────────────────
    if any(m in t for m in _mots_globe):
        await send_globe_command(globe_action="show_earth")
        await hablar("Initialisation du globe terrestre. Vue depuis l'espace activée, Christopher.")
        return "[Globe] Vue Terre activée."

    # ── Itinéraire de X à Y ──────────────────────────────────────────────────
    if any(m in t for m in _mots_route):
        pattern = r"(?:de|depuis)\s+(.+?)\s+(?:a|vers|jusqu.a|et)\s+(.+?)(?:\s*[?!]?\s*$)" 
        match = re.search(pattern, t)
        if match:
            from_name = match.group(1).strip().title()
            to_name   = match.group(2).strip().title()
            await hablar(f"Calcul de l'itinéraire de {from_name} vers {to_name}. Géolocalisation en cours...")
            lat1, lon1, _ = await geocode_lieu(from_name)
            lat2, lon2, _ = await geocode_lieu(to_name)
            if lat1 and lat2:
                await send_globe_command(
                    globe_action="route",
                    from_lat=lat1, from_lon=lon1, from_name=from_name,
                    to_lat=lat2,   to_lon=lon2,   to_name=to_name
                )
                await hablar(f"Itinéraire tracé de {from_name} à {to_name}, Christopher. La route est affichée sur le globe.")
                return f"[Globe] Route {from_name} → {to_name} affichée."
            else:
                return f"Je n'ai pas pu localiser les deux villes, Christopher. Vérifiez les noms et réessayez."
        return None

    # ── Fly to ville ─────────────────────────────────────────────────────────
    for mot in _mots_ville:
        if mot in t:
            # Extraire ce qui suit le mot déclencheur
            idx = t.find(mot)
            reste = t[idx + len(mot):].strip()
            
            # --- DISTINGUER RECHERCHE GLOBE VS RECHERCHE IMAGE / OBJET / RESTAURANT ---
            # Si le mot déclencheur est générique (affiche, montre, trouve)
            if mot in ["affiche", "montre-moi", "montre moi", "trouve"]:
                # 1. Si la phrase contient explicitement des mots-clés liés aux images ou aux restaurants
                if any(k in t for k in ["image", "photo", "dessin", "illustration", "wallpaper", "fond d'écran", "fond decran", "cliché", "pic", "visuel", "restaurant", "restaurants"]):
                    continue
                # 2. Si le reste commence par un article indéfini/partitif (un, une, des, du, de la, de l'), c'est un objet, pas un lieu
                cleaned_reste = reste.lower()
                if any(cleaned_reste.startswith(art) for art in ["un ", "une ", "des ", "du ", "de la ", "de l'"]):
                    continue
                # 3. Si la phrase contient des mots exclus liés à d'autres fonctionnalités de Jarvis (météo, e-mails, actualités, etc.)
                if any(k in t for k in ["météo", "meteo", "temps", "température", "temperature", "actualité", "actualite", "news", "mail", "message", "calendrier", "agenda", "blague", "citation", "note", "courses", "commande"]):
                    continue
            
            # Nettoyer les articles
            for art in ["la ville de ", "la ville ", "le ", "la ", "l'", "les ", "ma ville ", "mon pays "]:
                if reste.startswith(art):
                    reste = reste[len(art):]
            reste = reste.replace("?", "").replace("!", "").strip()
            if len(reste) >= 2:
                nom_lieu = reste.title()
                
                # --- DOUBLE SÉCURITÉ : GÉOCODAGE AVANT D'ACTIVER LE GLOBE ---
                # On géocode en arrière-plan. Si Nominatim ne trouve pas le lieu, on retourne None
                # pour laisser les autres modules (comme la recherche d'images) ou l'IA traiter la demande.
                lat, lon, display = await geocode_lieu(nom_lieu)
                if lat is None:
                    continue  # Ce n'est pas un lieu valide, continuer ou laisser passer
                
                await hablar(f"Recherche de {nom_lieu} en cours... Coordonnées en acquisition.")
                # Altitude selon le type de lieu (ville proche = plus bas)
                altitude = 300000
                await send_globe_command(
                    globe_action="fly_to",
                    lat=lat, lon=lon,
                    target=nom_lieu,
                    altitude=altitude
                )
                await hablar(f"Coordonnées acquises. Survol de {nom_lieu} en cours, Christopher.")
                return f"[Globe] Survol de {nom_lieu} ({lat:.4f}°, {lon:.4f}°)"
            break

    return None

async def resolver_extras_local(texte):
    global LAST_SHOWN_RESTAURANTS
    """
    Résout localement : minuteries, blagues, citations, volume, luminosité,
    notes, courses, todos, capitales, fuseaux, âge, dé, mot de passe, etc.
    """
    import re
    import random
    t = texte.lower().replace("?", "").strip()

    # ══ MINUTERIE ══════════════════════════════════════════════
    if any(k in t for k in ["minuteur", "minuterie", "timer", "rappelle-moi dans",
                             "rappelle moi dans", "alarme dans", "alerte dans",
                             "lance un minuteur", "active le minuteur",
                             "previens-moi dans", "previens moi dans"]):
        duree = _parsear_duracion_segundos(t)
        if duree:
            # Envoi au frontend
            if CONNECTED_CLIENTS:
                async def _send_timer():
                    msg = json.dumps({"action": "timer_start", "duration": duree})
                    await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                lancer_tache_arriere_plan(_send_timer())
            
            # Ancienne logique de sonnerie conservée pour la voix (Style Iron Man)
            nom = f"timer_{len(_minuteries)+1}"
            def _sonner(nom=nom, duree=duree):
                _minuteries.pop(nom, None)
                import random
                reponses = [
                    "Monsieur, le protocole de compte à rebours est arrivé à échéance.",
                    "Christopher, la temporisation est terminée. J'espère que vous n'avez rien oublié.",
                    "Alerte : Le minuteur a atteint zéro. Tout est en ordre, Monsieur ?",
                    "Fin du décompte, Christopher. Je reste à tu entière disposition."
                ]
                loop2 = asyncio.new_event_loop()
                loop2.run_until_complete(hablar(random.choice(reponses)))
                loop2.close()
            
            timer = threading.Timer(duree, _sonner)
            timer.daemon = True
            timer.start()
            _minuteries[nom] = timer
            
            mins = duree // 60
            return f"Minuteur de {mins} minutes activé. Affichage HUD en cours."
        return "Précisez la durée, par exemple : 'Mets un minuteur de 10 minutes'."

    # AJOUTER / RETIRER DU TEMPS
    if any(k in t for k in ["ajoute", "rajoute", "augmente"]) and "minute" in t:
        try:
            extra = int(re.search(r'\d+', t).group()) * 60
            if CONNECTED_CLIENTS:
                async def _send_add():
                    msg = json.dumps({"action": "timer_add", "duration": extra})
                    await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                lancer_tache_arriere_plan(_send_add())
            return f"J'ai ajouté {extra//60} minutes au minuteur."
        except: pass
    
    if any(k in t for k in ["retire", "enlève", "diminue", "supprime"]) and "minute" in t:
        try:
            less = int(re.search(r'\d+', t).group()) * 60
            if CONNECTED_CLIENTS:
                async def _send_rem():
                    msg = json.dumps({"action": "timer_remove", "duration": less})
                    await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                lancer_tache_arriere_plan(_send_rem())
            return f"J'ai retiré {less//60} minutes au minuteur."
        except: pass

    if any(k in t for k in ["annuler minuteur", "annule minuteur", "stop minuteur", "stop le minuteur",
                             "annuler minuterie", "annule le timer", "arrête le minuteur", "arrête le minute",
                             "stop le chrono", "arrête le chrono"]):
        if CONNECTED_CLIENTS:
            async def _send_stop():
                msg = json.dumps({"action": "timer_stop"})
                await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            lancer_tache_arriere_plan(_send_stop())
        
        if _minuteries:
            for nom, timer in list(_minuteries.items()):
                timer.cancel()
            _minuteries.clear()
            return "Minuteur arrêté, Christopher."
        return "Aucun minuteur actif."

    if any(k in t for k in ["minuteur actif", "minuteries actives", "combien de minuteurs"]):
        if _minuteries:
            return f"Vous avez {len(_minuteries)} minuterie{'s' if len(_minuteries) > 1 else ''} active{'s' if len(_minuteries) > 1 else ''}."
        return "Aucune minuterie active en ce moment."

    # ══ FUSEAUX HORAIRES ═══════════════════════════════════════
    if any(k in t for k in ["heure à", "heure en", "heure au", "quelle heure il est à",
                             "quelle heure est-il à", "quelle heure est il à",
                             "heure là-bas", "heure la-bas"]):
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            try:
                from backports.zoneinfo import ZoneInfo
            except ImportError:
                ZoneInfo = None
        if ZoneInfo:
            for cle, (nom_ville, tz_str) in _FUSEAUX.items():
                if cle in t:
                    try:
                        from datetime import timezone
                        heure_locale = datetime.now(ZoneInfo(tz_str))
                        return (f"Il est actuellement {heure_locale.strftime('%H:%M')} "
                                f"à {nom_ville}, Christopher.")
                    except Exception:
                        pass
        return "Je ne reconnais pas cette ville dans ma base locale, Christopher."

    # ══ CALCUL D'ÂGE ══════════════════════════════════════════
    age_match = re.search(r'n[ée]\s+en\s+(\d{4})', t)
    if age_match or any(k in t for k in ["quel age j'ai", "quel âge j'ai",
                                          "j'ai quel age", "j'ai quel âge",
                                          "calcule mon age", "calcule mon âge"]):
        if age_match:
            annee_naissance = int(age_match.group(1))
            age = datetime.now().year - annee_naissance
            return f"Si eres né en {annee_naissance}, vous avez {age} ans, Christopher."
        return "Précisez tu année de naissance, par exemple : 'Né en 1990, quel âge j'ai ?'"

    # ══ COMPTE À REBOURS ═══════════════════════════════════════
    if any(k in t for k in ["combien de jours avant noël", "combien de jours jusqu'à noël",
                             "combien de jours avant noel"]):
        today = datetime.now().date()
        noel = datetime(today.year, 12, 25).date()
        if today > noel:
            noel = datetime(today.year + 1, 12, 25).date()
        jours = (noel - today).days
        return f"Il reste {jours} jour{'s' if jours > 1 else ''} avant Noël, Christopher !"

    if any(k in t for k in ["combien de jours avant le nouvel an",
                             "combien de jours avant 2025", "combien de jours avant 2026",
                             "combien de jours avant 2027"]):
        today = datetime.now().date()
        an_prochain = datetime(today.year + 1, 1, 1).date()
        jours = (an_prochain - today).days
        return f"Il reste {jours} jour{'s' if jours > 1 else ''} avant le Nouvel An, Christopher !"

    # ══ BLAGUES ════════════════════════════════════════════════
    if any(k in t for k in ["blague", "fais-moi rire", "fais moi rire",
                             "raconte-moi une blague", "raconte moi une blague",
                             "dis-moi une blague", "dis moi une blague",
                             "joke", "fais rire", "une blague"]):
        return random.choice(_BLAGUES)

    # ══ CITATIONS ══════════════════════════════════════════════
    if any(k in t for k in ["citation", "inspire-moi", "inspire moi",
                             "quote", "parole sage", "phrase motivante",
                             "motive-moi", "motive moi", "dis-moi quelque chose",
                             "donne-moi une citation"]):
        return random.choice(_CITATIONS)

    # ══ PILE OU FACE / DÉ ═════════════════════════════════════
    if any(k in t for k in ["pile ou face", "pile ou pile", "lance une pièce",
                             "lance une piece", "heads or tails", "flip"]):
        resultat = random.choice(["Pile", "Face"])
        return f"J'ai lancé la pièce... C'est {resultat} !"

    de_match = re.search(r'(?:lance|jette|tire|roule)\s+un\s+d[eé](?:\s+[aà]\s+(\d+)\s+face)?', t)
    if de_match or "lance un dé" in t or "jette le dé" in t or "jeter le dé" in t:
        nb_faces = 6
        m2 = re.search(r'd[eé]\s+[aà]\s+(\d+)', t)
        if m2:
            nb_faces = int(m2.group(1))
        result = random.randint(1, nb_faces)
        return f"J'ai lancé un dé à {nb_faces} faces... Vous obtenez : {result} !"

    if any(k in t for k in ["nombre aléatoire", "nombre aleatoire", "chiffre aléatoire",
                             "chiffre aleatoire", "génère un nombre", "genere un nombre"]):
        rng_match = re.search(r'entre\s+(\d+)\s+et\s+(\d+)', t)
        if rng_match:
            a, b = int(rng_match.group(1)), int(rng_match.group(2))
            return f"Votre nombre aléatoire entre {a} et {b} : {random.randint(a, b)}"
        return f"Voici un nombre aléatoire : {random.randint(1, 100)}"

    # ══ GÉNÉRATEUR DE MOT DE PASSE ════════════════════════════
    _is_password_gen_request = any(k in t for k in [
        "génère un mot de passe", "genere un mot de passe", "générer un mot de passe", "generer un mot de passe",
        "crée un mot de passe", "cree un mot de passe", "créer un mot de passe", "creer un mot de passe",
        "donne moi un mot de passe", "donne-moi un mot de passe", "génère un mdp", "genere un mdp",
        "crée un mdp", "cree un mdp", "donne moi un mdp", "donne-moi un mdp",
        "generate password", "new password", "nouveau mot de passe"
    ])
    _is_informational_query = any(k in t for k in [
        "comment", "pourquoi", "qu'est-ce", "quest ce", "c'est quoi", "cest quoi",
        "cracker", "pirater", "retrouver", "oublié", "oublie", "sécuriser", "securiser"
    ])
    if _is_password_gen_request and not _is_informational_query:
        import string
        longueur = 16
        lg_m = re.search(r'(\d+)\s*(?:caractères|caracteres|car)', t)
        if lg_m:
            longueur = min(max(int(lg_m.group(1)), 8), 64)
        chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        mdp = ''.join(random.SystemRandom().choice(chars) for _ in range(longueur))
        return f"Voici un mot de passe aléatoire sécurisé ({longueur} caractères) : {mdp}"

    # ══ NOTES RAPIDES ══════════════════════════════════════════
    if any(k in t for k in ["note ça", "note ca", "prends note", "retiens ça",
                             "retiens ca", "mémorise ça", "memorise ca",
                             "note que", "note :", "écris ça", "ecris ca"]):
        contenu = t
        for pref in ["note ça :", "note ca :", "note que", "note :", "prends note :",
                     "prends note de", "retiens ça :", "retiens ca :", "note ",
                     "mémorise ça :", "memorise ca :", "écris ça :", "ecris ca :"]:
            if contenu.startswith(pref):
                contenu = contenu[len(pref):].strip()
                break
        if contenu:
            listes = _cargar_listas()
            note = f"[{datetime.now().strftime('%d/%m %H:%M')}] {contenu}"
            listes["notes"].append(note)
            _guardar_listas(listes)
            return f"Note enregistrée, Christopher : '{contenu}'"
        return "Que souhaitez-vous que je note ?"

    if any(k in t for k in ["lis mes notes", "montre mes notes", "quelles sont mes notes",
                             "mes notes", "affiche mes notes"]):
        listes = _cargar_listas()
        if not listes["notes"]:
            return "Vous n'avez aucune note enregistrée, Christopher."
        notes = "\n".join(f"• {n}" for n in listes["notes"][-5:])
        return f"Vos {min(5, len(listes['notes']))} dernières notes, Christopher :\n{notes}"

    if any(k in t for k in ["efface mes notes", "supprime mes notes",
                             "vide mes notes", "clear mes notes"]):
        listes = _cargar_listas()
        listes["notes"] = []
        _guardar_listas(listes)
        return "Toutes vos notes ont été effacées, Christopher."

    # ══ LISTE DE COURSES ═══════════════════════════════════════
    if any(k in t for k in ["ajoute", "rajoute"]) and any(k in t for k in ["liste de courses", "courses", "liste d'achats"]):
        article = t
        for pref in ["ajoute ", "rajoute ", "à ma liste de courses", "à la liste de courses",
                     "dans la liste de courses", "à mes courses", "à ma liste d'achats"]:
            article = article.replace(pref, "").strip()
        if article:
            listes = _cargar_listas()
            listes["courses"].append(article)
            _guardar_listas(listes)
            # Sync avec WebSocket
            msg = json.dumps({"type": "shopping_list", "items": listes["courses"]})
            msg_open = json.dumps({"type": "shopping_open"})
            if CONNECTED_CLIENTS:
                asyncio.ensure_future(asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True))
                asyncio.ensure_future(asyncio.gather(*[ws.send(msg_open) for ws in CONNECTED_CLIENTS], return_exceptions=True))
            return f"'{article}' ajouté à tu liste de courses, Christopher."

    # Check if the user is asking about what's on their shopping list (querying/reading it)
    is_asking_courses = False
    
    courses_keywords = [
        "liste de course", "liste de courses", "mes courses", "les courses",
        "liste d'achats", "liste d'achat", "ma liste"
    ]
    has_courses_keyword = any(k in t for k in courses_keywords)
    has_rappel_courses = any(r in t for r in ["rappel", "rappelle", "rapel", "rappele"]) and any(c in t for c in ["course", "achat", "acheter"])
    
    has_acheter_questions = any(q in t for q in [
        "dois-je acheter", "dois je acheter", "doit-je acheter", "doit je acheter", 
        "je dois acheter", "je doit acheter", "j'dois acheter", "jdois acheter",
        "ce qu'il faut acheter", "ce quil faut acheter"
    ])
    
    has_prendre_questions = any(q in t for q in [
        "quoi acheter", "que dois-je prendre", "que dois je prendre", "je dois prendre", 
        "je doit prendre", "j'dois prendre", "jdois prendre", "produit de ma liste", 
        "produits de ma liste", "produit de la liste", "produits de la liste"
    ])
    
    if has_courses_keyword or has_rappel_courses or has_acheter_questions or has_prendre_questions:
        is_add = any(k in t for k in ["ajoute", "rajoute", "mettre", "mets", "met", "ajouter", "rajouter"])
        is_clear = any(k in t for k in ["vide", "efface", "supprime", "clear", "nettoie", "nettoyer", "vider", "effacer", "supprimer"])
        if not is_add and not is_clear:
            is_asking_courses = True

    if is_asking_courses:
        listes = _cargar_listas()
        # Ouvrir le panel
        msg = json.dumps({"type": "shopping_list", "items": listes.get("courses", [])})
        msg_open = json.dumps({"type": "shopping_open"})
        if CONNECTED_CLIENTS:
            asyncio.ensure_future(asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True))
            asyncio.ensure_future(asyncio.gather(*[ws.send(msg_open) for ws in CONNECTED_CLIENTS], return_exceptions=True))
        if not listes.get("courses"):
            return "Votre liste de courses est actuellement vide, Christopher."
        items = ", ".join(listes["courses"])
        
        # Use several variants to reply
        replies = [
            f"Votre liste de courses contient : {items}.",
            f"Voici ce que vous devez acheter, Christopher : {items}.",
            f"Rappel de tu liste de courses, Monsieur. Elle contient : {items}.",
            f"Actuellement sur tu liste d'achats, il y a : {items}.",
            f"Voici les produits de tu liste de courses : {items}."
        ]
        return random.choice(replies)

    if any(k in t for k in ["vide la liste de courses", "efface la liste de courses",
                             "supprime la liste de courses", "clear les courses"]):
        listes = _cargar_listas()
        listes["courses"] = []
        _guardar_listas(listes)
        msg = json.dumps({"type": "shopping_list", "items": []})
        if CONNECTED_CLIENTS:
            asyncio.ensure_future(asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True))
        return "Liste de courses vidée, Christopher."

    # ══ TO-DO LIST ═════════════════════════════════════════════
    if any(k in t for k in ["ajoute une tâche", "ajoute une tache", "nouvelle tâche",
                             "nouvelle tache", "ajoute à ma to-do", "ajoute a ma to-do",
                             "à faire :", "a faire :"]):
        tache = t
        for pref in ["ajoute une tâche :", "ajoute une tache :", "nouvelle tâche :",
                     "nouvelle tache :", "ajoute à ma to-do :", "ajoute a ma to-do :",
                     "à faire :", "a faire :", "ajoute une tâche ", "ajoute une tache "]:
            tache = tache.replace(pref, "").strip()
        if tache:
            listes = _cargar_listas()
            listes["todos"].append({"tache": tache, "fait": False, "date": datetime.now().strftime("%d/%m")})
            _guardar_listas(listes)
            return f"Tâche ajoutée : '{tache}', Christopher."

    if any(k in t for k in ["mes tâches", "mes taches", "ma to-do", "ma todo",
                             "liste de tâches", "liste de taches", "qu'est-ce que j'ai à faire",
                             "qu'est-ce que j'ai a faire"]):
        listes = _cargar_listas()
        todos = [td for td in listes["todos"] if not td.get("fait")]
        if not todos:
            return "Votre liste de tâches est vide, Christopher. Bravo !"
        items = "\n".join(f"• [{td['date']}] {td['tache']}" for td in todos[-8:])
        return f"Vos tâches à faire ({len(todos)}) :\n{items}"

    if any(k in t for k in ["efface mes tâches", "efface mes taches", "vide ma to-do",
                             "supprime mes tâches", "supprime mes taches"]):
        listes = _cargar_listas()
        listes["todos"] = []
        _guardar_listas(listes)
        return "Liste de tâches vidée, Christopher."

    # ══ VOLUME SYSTÈME ═════════════════════════════════════════
    vol_mots = ["volume", "son", "audio"]
    if any(k in t for k in vol_mots):
        if any(k in t for k in ["coupe le son", "mute", "silence total", "sourdine"]):
            vol = _obtener_interfaz_volumen()
            if vol:
                vol.SetMute(1, None)
                return "Son coupé, Christopher."
            return "Je n'ai pas pu accéder au contrôle du volume. Installez pycaw."

        if any(k in t for k in ["remet le son", "unmute", "remet le volume", "réactive le son", "reactive le son"]):
            vol = _obtener_interfaz_volumen()
            if vol:
                vol.SetMute(0, None)
                return "Son réactivé, Christopher."

        vol_match = re.search(r'(\d+)\s*(?:%|pourcent)', t)
        if vol_match or any(k in t for k in ["monte le volume", "monte le son",
                                              "baisse le volume", "baisse le son",
                                              "volume à", "son à", "mets le volume",
                                              "mets le son"]):
            vol = _obtener_interfaz_volumen()
            if vol:
                if vol_match:
                    pct = max(0, min(100, int(vol_match.group(1))))
                    import math
                    # Convertir pourcentage en dB (scale logarithmique Windows)
                    vol.SetMasterVolumeLevelScalar(pct / 100.0, None)
                    return f"Volume réglé à {pct}%, Christopher."
                elif any(k in t for k in ["monte", "augmente", "hausse", "plus fort"]):
                    cur = vol.GetMasterVolumeLevelScalar()
                    new_vol = min(1.0, cur + 0.1)
                    vol.SetMasterVolumeLevelScalar(new_vol, None)
                    return f"Volume augmenté à {int(new_vol*100)}%, Christopher."
                elif any(k in t for k in ["baisse", "diminue", "moins fort", "réduis", "reduis"]):
                    cur = vol.GetMasterVolumeLevelScalar()
                    new_vol = max(0.0, cur - 0.1)
                    vol.SetMasterVolumeLevelScalar(new_vol, None)
                    return f"Volume réduit à {int(new_vol*100)}%, Christopher."
            else:
                return "Contrôle du volume indisponible. Installez pycaw pour cette fonction."

    # ══ LUMINOSITÉ ═════════════════════════════════════════════
    if any(k in t for k in ["luminosité", "luminosite", "brillo", "écran plus clair",
                             "écran plus sombre", "baisser l'écran", "monter l'écran"]):
        if _sbc_ok and _sbc:
            try:
                lum_match = re.search(r'(\d+)\s*(?:%|pourcent)', t)
                if lum_match:
                    pct = max(0, min(100, int(lum_match.group(1))))
                    _sbc.set_brightness(pct)
                    return f"Luminosité réglée à {pct}%, Christopher."
                elif any(k in t for k in ["monte", "augmente", "plus clair", "hausse", "max"]):
                    cur = _sbc.get_brightness(display=0)
                    if isinstance(cur, list): cur = cur[0]
                    new_b = min(100, cur + 15)
                    _sbc.set_brightness(new_b)
                    return f"Luminosité augmentée à {new_b}%, Christopher."
                elif any(k in t for k in ["baisse", "diminue", "plus sombre", "réduis", "min"]):
                    cur = _sbc.get_brightness(display=0)
                    if isinstance(cur, list): cur = cur[0]
                    new_b = max(0, cur - 15)
                    _sbc.set_brightness(new_b)
                    return f"Luminosité réduite à {new_b}%, Christopher."
            except Exception as e:
                return f"Impossible de régler la luminosité : {e}"
        return "Le module de luminosité n'est pas installé. Lancez : pip install screen-brightness-control"

    # ══ VEILLE / ARRÊT / REDÉMARRAGE ══════════════════════════
    if any(k in t for k in ["mets le pc en veille", "mode veille", "veille dans",
                             "suspends le pc", "sleep"]):
        delai = _parsear_duracion_segundos(t) or 0
        if delai > 0:
            subprocess.Popen(f'shutdown /h /t {delai}', shell=True)
            mins = delai // 60
            return f"Le PC passera en veille dans {mins} minute{'s' if mins > 1 else ''}, Christopher."
        subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
        return "Mise en veille du PC, Christopher. À bientôt !"

    if any(k in t for k in ["éteins le pc", "eteins le pc", "arrête le pc", "arrete le pc",
                             "shutdown", "arrêt dans", "arret dans"]):
        delai = _parsear_duracion_segundos(t) or 0
        if delai > 0:
            subprocess.Popen(f'shutdown /s /t {delai}', shell=True)
            mins = delai // 60
            return f"Le PC s'éteindra dans {mins} minute{'s' if mins > 1 else ''}, Christopher."
        return "Pour l'arrêt immédiat, confirmez en disant : 'confirme l'arrêt du pc'."

    if "confirme l'arrêt du pc" in t or "confirme l arret du pc" in t:
        subprocess.Popen("shutdown /s /t 10", shell=True)
        return "Arrêt du PC dans 10 secondes, Christopher. Au revoir !"

    if any(k in t for k in ["redémarre le pc", "redemarre le pc", "reboot"]):
        delai = _parsear_duracion_segundos(t) or 30
        subprocess.Popen(f'shutdown /r /t {delai}', shell=True)
        mins = max(1, delai // 60)
        return f"Redémarrage dans {mins} minute{'s' if mins > 1 else ''}, Christopher."

    if any(k in t for k in ["annule l'arrêt", "annule l arret", "annule le redémarrage",
                             "annule le redemarrage", "annule la veille"]):
        subprocess.Popen("shutdown /a", shell=True)
        return "Arrêt/redémarrage annulé, Christopher."

    # ══ CORBEILLE ══════════════════════════════════════════════
    if any(k in t for k in ["vide la corbeille", "vider la corbeille", "corbeille vide",
                             "nettoie la corbeille"]):
        try:
            import winshell
            winshell.recycle_bin().empty(confirm=False, show_progress=False, sound=False)
            return "La corbeille a été vidée, Christopher."
        except ImportError:
            subprocess.run("PowerShell -Command \"Clear-RecycleBin -Force -ErrorAcción SilentlyContinue\"",
                           shell=True, capture_output=True)
            return "La corbeille a été vidée, Christopher."
        except Exception as e:
            return f"Impossible de vider la corbeille : {e}"

    # ══ CAPITALE / MONNAIE D'UN PAYS ══════════════════════════
    if any(k in t for k in ["capitale", "capital de"]):
        for pays, capitale in _CAPITALES.items():
            if pays in t:
                return f"La capitale de {pays.title()} est {capitale}, Christopher."
        return "Je ne connais pas ce pays dans ma base locale, Christopher."

    if any(k in t for k in ["monnaie", "devise", "monnaie de", "quelle est la monnaie"]):
        for pays, monnaie in _MONNAIES.items():
            if pays in t:
                return f"La monnaie de {pays.title()} est le {monnaie}, Christopher."
        return "Je ne connais pas la monnaie de ce pays dans ma base locale."

    # ══ CODE PHONÉTIQUE ════════════════════════════════════════
    if any(k in t for k in ["alphabet phonétique", "alphabet phonetique",
                             "code phonétique", "code phonetique",
                             "épelle", "epelle", "comment s'écrit", "comment s ecrit",
                             "épellation", "epellation"]):
        # Chercher une lettre ou un mot à épeler
        alpha_match = re.search(r"(?:épelle|epelle|comment s'écrit|comment s ecrit)\s+([a-z]+)", t)
        if alpha_match:
            mot = alpha_match.group(1).lower()
            epele = " - ".join(_PHONETIQUE.get(c, c.upper()) for c in mot)
            return f"'{mot.upper()}' s'épelle : {epele}"
        # "C comme ?"
        lettre_match = re.search(r"([a-z])\s+comme\s+\?", t)
        if lettre_match:
            c = lettre_match.group(1)
            return f"{c.upper()} comme {_PHONETIQUE.get(c, '?')}"
        return "Précisez la lettre ou le mot à épeler phonétiquement."

    # ══ RECHERCHE D'IMAGES ═══════════════════════════════════════════
    _images_prefixes = [
        "montre-moi des images de ", "montre moi des images de ",
        "montre-moi des photos de ", "montre moi des photos de ",
        "montre-moi une photo de ", "montre moi une photo de ",
        "montre-moi un dessin de ", "montre moi un dessin de ",
        "montre-moi un visuel de ", "montre moi un visuel de ",
        "affiche des images de ", "cherche des images de ",
        "cherche des photos de ", "affiche des photos de ",
        "affiche une image de ", "affiche une photo de ",
        "affiche-moi une image de ", "affiche-moi une photo de ",
        "affiche moi des images de ", "affiche moi des photos de ",
        "je veux voir des images de ", "je veux voir des photos de ",
        "montre des images de ", "montre des photos de ",
        "trouve des images de ", "trouve des photos de ",
        "trouve une photo de ", "trouve une image de ",
        "recherche des images de ", "recherche des photos de ",
        "affiche-moi des images de ", "affiche-moi des photos de ",
    ]
    for pref in _images_prefixes:
        if t.startswith(pref):
            query = t[len(pref):].strip().rstrip(".")
            if len(query) > 1:
                async def _send_images(q=query):
                    cfg = _cargar_config()
                    engine = cfg.get("image_search_engine", "serpapi")
                    urls = recherche_images_web(q, nb_images=6, engine=engine)
                    if urls:
                        msg = json.dumps({"type": "show_images", "query": q, "images": urls})
                        await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                if CONNECTED_CLIENTS:
                    lancer_tache_arriere_plan(_send_images())
                return f"Je recherche des images de {query} et je les affiche sur tu interface, Christopher."

    # ══ MISES À JOUR LOGICIELS (WINGET) ═════════════════════════════
    _winget_phrases = [
        "mets à jour mes logiciels", "lance les mises à jour", "ouvre les mises à jour", 
        "vérifie les mises à jour", "mise à jour logiciels", "ouvre winget", "lance winget"
    ]
    for p in _winget_phrases:
        if p in t:
            if CONNECTED_CLIENTS:
                msg = json.dumps({"action": "winget_open"})
                lancer_tache_arriere_plan(asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True))
            return "J'ouvre le gestionnaire de mise à jour système et je lance la recherche des mises à jour disponibles, Christopher."

    # ══ ANALYSE ANTIVIRUS ══════════════════════════════════════════
    _av_phrases = [
        "analyse mon pc", "analyse mon ordinateur", "scanne mon pc", "scanne mon ordinateur",
        "recherche des virus", "recherche si j'ai des virus", "lance l'antivirus",
        "lance un scan antivirus", "analyse antivirus", "vérifie les virus", "lance le scan antivirus"
    ]
    for p in _av_phrases:
        if p in t:
            if CONNECTED_CLIENTS:
                msg = json.dumps({"type": "av_open"})
                lancer_tache_arriere_plan(asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True))
            return "J'ouvre la console de sécurité et j'initialise le scan antivirus de tu ordinateur, Christopher."

    # ══ RAPPELS / RENDEZ-VOUS ══════════════════════════════════════
    # Pattern 1: rappelle-moi [action] à [heure]
    r_match1 = re.search(r"(?:rappelle[- ]moi|rappel)\s+(?:de\s+|mon\s+|ma\s+|que\s+)?(.+?)\s+(?:à|a)\s*(\d{1,2})[hH:]?(\d{2})?", t)
    # Pattern 2: rappelle-moi à [heure] de [action]
    r_match2 = re.search(r"(?:rappelle[- ]moi|rappel)\s+(?:à|a)\s*(\d{1,2})[hH:]?(\d{2})?\s+(?:de\s+|mon\s+|ma\s+|que\s+)?(.+)", t)
    
    r_match = r_match1 or r_match2
    if r_match:
        if r_match == r_match1:
            text = r_match.group(1).strip()
            hour = int(r_match.group(2))
            minute = int(r_match.group(3)) if r_match.group(3) else 0
        else:
            hour = int(r_match.group(1))
            minute = int(r_match.group(2)) if r_match.group(2) else 0
            text = r_match.group(3).strip()
            
        if 0 <= hour <= 23 and 0 <= minute <= 59 and len(text) > 1:
            time_str = f"{hour:02d}:{minute:02d}"
            cfg = _cargar_config()
            reminders = cfg.get("reminders", [])
            
            import uuid
            r_id = str(uuid.uuid4())[:8]
            
            new_r = {
                "id": r_id,
                "text": text,
                "time": time_str,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "triggered": False
            }
            reminders.append(new_r)
            _guardar_config({"reminders": reminders})
            
            if CONNECTED_CLIENTS:
                msg = json.dumps({"type": "settings_data", "data": _cargar_config()})
                lancer_tache_arriere_plan(asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True))
                
            return f"Rappel enregistré, Christopher. Je vous rappellerai : '{text}' à {time_str}."

    # ══ OBSIDIAN NOTES ═════════════════════════════════════════════
    if any(k in t for k in ["mes notes obsidian", "mes notes", "affiche mes notes", "ouvre mes notes", "ouvre obsidian", "coffre obsidian"]):
        if CONNECTED_CLIENTS:
            notes_list = obsidian_helper.lister_notes()
            msg_open = json.dumps({"type": "obsidian_open"})
            msg_notes = json.dumps({"type": "obsidian_notes", "notes": notes_list})
            lancer_tache_arriere_plan(asyncio.gather(*[ws.send(msg_open) for ws in CONNECTED_CLIENTS], return_exceptions=True))
            lancer_tache_arriere_plan(asyncio.gather(*[ws.send(msg_notes) for ws in CONNECTED_CLIENTS], return_exceptions=True))
        return "J'ouvre tu coffre de notes Obsidian sur l'interface, Christopher."

    # ══ RESTAURANTS LOCAL ══════════════════════════════════════════
    is_restaurant_query = any(k in t for k in ["restaurant", "restaurants", "ou manger", "où manger"])
    is_others_query = any(k in t for k in ["d'autre", "d'autres", "d'un autre", "d'une autre", "affiche en d'autres", "affiche en d'autre", "trouve d'autres", "d'autres adresses", "affiche d'autres"])
    
    if is_restaurant_query or (is_others_query and LAST_SHOWN_RESTAURANTS):
        # On vérifie si la requête cible un lieu spécifique (ex: "restaurants de paris")
        specifie_lieu = False
        for prep in [" de ", " à ", " a ", " dans ", " sur "]:
            if prep in t:
                idx_prep = t.find(prep)
                suite = t[idx_prep + len(prep):].strip()
                if not any(w in suite for w in ["moi", "ici", "proximité", "proximite", "côté", "cote", "nous"]):
                    specifie_lieu = True
                    break
        
        if not specifie_lieu:
            is_others = any(w in t for w in ["autre", "autres", "d'autre", "d'autres", "d'un autre", "d'une autre", "change de restaurant", "d'autres adresses"])
            
            if VILLE_PAR_DEFAUT:
                location = VILLE_PAR_DEFAUT
                lat = LAT_PAR_DEFAUT if LAT_PAR_DEFAUT else None
                lng = LON_PAR_DEFAUT if LON_PAR_DEFAUT else None
            else:
                location = obtenir_ville_par_ip()
                lat = USER_LOCATION_GPS.get("lat") if USER_LOCATION_GPS else None
                lng = USER_LOCATION_GPS.get("lng") if USER_LOCATION_GPS else None
            
            if not is_others:
                LAST_SHOWN_RESTAURANTS = []
            exclure = list(LAST_SHOWN_RESTAURANTS)
            
            lanzar_busqueda_restaurantes_fondo(location, lat, lng, exclure, is_others)
            return "Je cherche d'autres adresses de restaurants pour vous, un instant Christopher." if is_others else "J'active le radar de recherche de restaurants, un instant Christopher."

    return None


def resolver_info_sistema_local(texte):
    """Répond aux questions d'heure, date, batterie, CPU/RAM localement sans IA."""
    t = texte.lower().replace("?", "").strip()
    maintenant = datetime.now()

    JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    MOIS_FR  = ["janvier", "février", "mars", "avril", "mai", "juin",
                "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

    # --- HEURE ---
    if any(m in t for m in ["quelle heure", "il est quelle heure", "l'heure qu'il est",
                             "quelle est l'heure", "tu as l'heure", "donne-moi l'heure",
                             "il est combien", "c'est quoi l'heure", "heure il est"]):
        h, m = maintenant.hour, maintenant.minute
        return f"Il est {h}h{m:02d}, Christopher."

    # --- DATE COMPLÈTE ---
    if any(m in t for m in ["quelle date", "on est quel jour", "quel jour on est",
                             "quel jour sommes-nous", "la date d'aujourd'hui", "date du jour",
                             "on est le combien", "quel jour est-on", "c'est quoi la date",
                             "la date aujourd'hui"]):
        jour_semaine = JOURS_FR[maintenant.weekday()]
        mois = MOIS_FR[maintenant.month - 1]
        return f"Nous sommes le {jour_semaine} {maintenant.day} {mois} {maintenant.year}, Christopher."

    # --- JOUR DE LA SEMAINE SEUL ---
    if any(m in t for m in ["quel jour", "c'est quel jour"]) and "date" not in t:
        return f"Nous sommes {JOURS_FR[maintenant.weekday()]}, Christopher."

    # --- MOIS ---
    if any(m in t for m in ["quel mois", "on est en quel mois", "c'est quel mois"]):
        return f"Nous sommes en {MOIS_FR[maintenant.month - 1]}, Christopher."

    # --- ANNÉE ---
    if any(m in t for m in ["quelle année", "on est en quelle année", "c'est quelle année"]):
        return f"Nous sommes en {maintenant.year}, Christopher."

    # --- ÂGE DE L'UTILISATEUR ---
    if any(m in t for m in ["quel âge as-tu", "quel age as-tu",
                             f"quel âge a {USER_NAME.lower()}",
                             f"quel age a {USER_NAME.lower()}",
                             "quel est mon âge", "j'ai quel âge", "j ai quel age"]):
        if USER_AGE:
            return f"Vous avez {USER_AGE} ans, {USER_NAME}."
        attente_age = True
        return f"Je ne connais pas encore tu âge, {USER_NAME}. Quel est-il ?"

    # --- BATTERIE ---
    if any(m in t for m in ["batterie", "autonomie", "niveau de charge", "charge du pc"]):
        if psutil is None:
            return "Le module psutil n'est pas disponible, Christopher."
        try:
            bat = psutil.sensors_battery()
            if bat:
                pct = int(bat.percent)
                etat = "en charge" if bat.power_plugged else "sur batterie"
                return f"La batterie est à {pct}%, {etat}, Christopher."
            return "Je ne détecte pas de batterie sur cet appareil, Christopher."
        except Exception:
            return "Impossible de lire la batterie, Christopher."

    # --- CPU ---
    if any(m in t for m in ["cpu", "processeur", "utilisation du processeur", "charge du processeur"]):
        if psutil is None:
            return "Le module psutil n'est pas disponible, Christopher."
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            return f"Le processeur tourne à {cpu}% d'utilisation, Christopher."
        except Exception:
            return "Impossible de lire le processeur, Christopher."

    # --- RAM ---
    if any(m in t for m in ["ram", "mémoire ram", "mémoire vive", "utilisation de la mémoire"]):
        if psutil is None:
            return "Le module psutil n'est pas disponible, Christopher."
        try:
            mem = psutil.virtual_memory()
            utilise = round(mem.used / (1024**3), 1)
            total   = round(mem.total / (1024**3), 1)
            return f"La RAM est à {mem.percent}% — {utilise} Go utilisés sur {total} Go, Christopher."
        except Exception:
            return "Impossible de lire la RAM, Christopher."

    # --- UPTIME (depuis combien de temps le PC est allumé) ---
    if any(m in t for m in ["allumé depuis", "uptime", "depuis combien de temps le pc",
                             "depuis quand est allumé"]):
        if psutil is None:
            return "Le module psutil n'est pas disponible, Christopher."
        try:
            boot = datetime.fromtimestamp(psutil.boot_time())
            delta = maintenant - boot
            heures  = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            return f"Le PC est allumé depuis {heures}h{minutes:02d}, Christopher."
        except Exception:
            return None

    return None

def traiter_intent_domotique_direct(texte: str):
    """Détecte et exécute directement les commandes domotiques (lumières, prises, etc.) en local sans délai."""
    t = texte.lower().strip()
    
    is_on = any(w in t for w in ["allume", "allumer", "active", "activer", "mets", "met", "lance", "ouvre"])
    is_off = any(w in t for w in ["éteins", "eteins", "éteindre", "eteindre", "désactive", "desactive", "arrête", "arrete", "ferme"])
    
    if not (is_on or is_off):
        return None
    
    etat = "on" if is_on else "off"
    verbe = "allumé" if is_on else "éteint"
    
    # 1. Acción sur TOUTES les lumières
    if any(k in t for k in ["toutes les lumières", "toutes les lumieres", "toutes les lampes", "tout allumer", "tout éteindre", "tout eteindre"]):
        if PIECES_LUMIERES:
            for p, entity_id in PIECES_LUMIERES.items():
                try:
                    ha_lumiere(entity_id, etat)
                except Exception as e:
                    print(f"[DOMOTIQUE DIRECT] Error {p}: {e}")
            return f"J'ai {verbe} toutes les lumières, {USER_NAME}."
        return f"Aucune lumière n'est configurée dans Home Assistant, {USER_NAME}."
    
    # 2. Acción sur une pièce spécifique (Lumières)
    if any(k in t for k in ["lumière", "lumiere", "lumieres", "lumières", "lampe", "lampes", "spot", "led"]):
        found_piece = None
        if PIECES_LUMIERES:
            for p in PIECES_LUMIERES.keys():
                if p.lower() in t:
                    found_piece = p
                    break
        
        if not found_piece:
            for p in ["salon", "chambre", "bureau", "cuisine", "couloir", "garage", "terrasse", "salle de bain", "entrée", "entree"]:
                if p in t:
                    found_piece = p
                    break
        
        if found_piece:
            entity_id = PIECES_LUMIERES.get(found_piece, f"light.{found_piece}") if PIECES_LUMIERES else f"light.{found_piece}"
            try:
                ha_lumiere(entity_id, etat)
                return f"J'ai {verbe} la lumière du {found_piece}, {USER_NAME}."
            except Exception as e:
                print(f"[DOMOTIQUE DIRECT] Error {found_piece}: {e}")
                return f"J'ai tenté d'actionner la lumière du {found_piece}, mais une erreur s'est produite avec Home Assistant."

    # 3. Acción sur les prises
    if any(k in t for k in ["prise", "prises", "interrupteur", "multiprise"]):
        found_piece = None
        if PIECES_PRISES:
            for p in PIECES_PRISES.keys():
                if p.lower() in t:
                    found_piece = p
                    break
        if not found_piece:
            for p in ["salon", "chambre", "bureau", "cuisine", "garage"]:
                if p in t:
                    found_piece = p
                    break
        if found_piece:
            entity_id = PIECES_PRISES.get(found_piece, f"switch.{found_piece}") if PIECES_PRISES else f"switch.{found_piece}"
            try:
                ha_interrupteur(entity_id, etat)
                return f"J'ai {verbe} la prise du {found_piece}, {USER_NAME}."
            except Exception as e:
                print(f"[DOMOTIQUE DIRECT] Error prise {found_piece}: {e}")
                return f"J'ai tenté d'actionner la prise du {found_piece}, mais une erreur s'est produite."

    return None

async def pedir_ia(texte):

    global is_thinking
    is_thinking = True
    await send_web_state("thinking")
    try:
        # ── PRIORITÉ 0 — RÉPONSES LOCALES (instantané, sans API) ────────────
        rep_loc = reponse_locale(texte)
        if rep_loc:
            return rep_loc

        # ── PRIORITÉ 0.5 — COMMANDES DOMOTIQUES DIRECTES (Home Assistant) ───
        rep_domo = traiter_intent_domotique_direct(texte)
        if rep_domo:
            return rep_domo

        # ── VERIFICATION DU MODE "TON / PERSONNALITÉ" (ASTRO / UNFILTERED) ──
        cfg_tone = _cargar_config()
        agent_tone = cfg_tone.get("agent_tone", "default")
        if agent_tone in ["astro", "spicy"]:
            mode_label = "Trash-Talk Astro" if agent_tone == "astro" else "Unfiltered & Coquin"
            print(f"[CERVEAU] Mode Ton '{mode_label}' actif — Redirection vers xAI Grok (Temp ~0.9)...")
            if not grok_client:
                return f"Attention {USER_NAME}, le mode '{mode_label}' nécessite une clé API xAI (Grok) valide. Veuillez renseigner tu clé API dans le menu Ton / Personnalité."
            
            prompt_tone = PROMPT_ASTRO_MODE if agent_tone == "astro" else PROMPT_SPICY_MODE
            from datetime import datetime as _dt_t
            _now_str = _dt_t.now().strftime("%A %d %B %Y à %H:%M")
            full_prompt = prompt_tone + f"\n\nContextual info: L'utilisateur s'appelle {USER_NAME}. Nous sommes le {_now_str}."
            
            rep_tone = await pedir_grok(texte, system_prompt_override=full_prompt, temperature_override=0.9)
            if rep_tone:
                return rep_tone
            print(f"[CERVEAU] Échec de Grok pour le mode {agent_tone}, bascule sur le pipeline par défaut.")

        # Définition des fonctions d'appel internes
        async def _call_gemini():
            if not gemini_actif:
                raise Exception("Clé Gemini non configurée — agent ignoré")
            if not _quota_mgr.is_available("gemini"):
                raise _QuotaExceededError(f"Gemini en cooldown ({_quota_mgr.remaining_cooldown('gemini')}s)")
            print(f"[CERVEAU] Tentative avec Gemini (Liste: {MODELS_LIST})...")
            temp_hist = historique + [types.Content(role="user", parts=[types.Part(text=texte)])]
            # Utilisation de la recherche web Google si demandée explicitement ou si temps réel requis
            t_low = texte.lower()
            mots_cles_recherche = ["cherche sur le web", "cherche sur internet", "recherche sur le web", "recherche sur internet", 
                                   "cherche sur google", "recherche google", "regarde sur internet", "trouve sur le web", 
                                   "fais une recherche", "fais des recherches", "recherche en ligne", "cherche en ligne"]
            use_search = any(kw in t_low for kw in mots_cles_recherche)
            
            # Détection de requêtes sportives (football, scores, etc.) ou temps réel
            mots_sport_direct = ["match", "score", "champions league", "ligue des champions", "copa america", "ligue 1", "ligue 2", "premier league", "liga", "série a", "bundesliga", "mercato", "but", "buts", "championnat"]
            has_sport_direct = any(kw in t_low for kw in mots_sport_direct)
            
            mots_temps_pays = ["hier", "aujourd'hui", "ce soir", "en ce moment", "direct", "live"]
            has_temps_pays = any(kw in t_low for kw in mots_temps_pays)
            
            is_sports_query = has_sport_direct and has_temps_pays
            is_realtime_query = any(kw in t_low for kw in ["actualité", "actus", "météo", "température", "se passe-t-il", "se passe t il"])
            
            # Analyse de l'historique de conversation (contexte de suivi)
            contexte_sport = False
            try:
                for content in historique[-6:]:
                    if hasattr(content, "role") and content.role == "user":
                        for part in getattr(content, "parts", []):
                            p_text = getattr(part, "text", "")
                            if p_text:
                                p_low = p_text.lower()
                                if any(kw in p_low for kw in ["match", "score", "coupe du monde", "foot", "sport", "but"]):
                                    contexte_sport = True
            except Exception as e:
                print(f"[CERVEAU] Error lors de l'analyse de l'historique : {e}")
                
            mots_suivi = ["qui", "quel", "quelle", "quand", "gardien", "joueur", "équipe", "equipe", "but", "buts", "match", "score", "gagné", "gagne", "perdu", "classement", "pays", "espagne", "france", "argentine", "hier", "demain", "encore", "lequel", "laquelle"]
            has_suivi = any(kw in t_low for kw in mots_suivi)
            
            if (contexte_sport and has_suivi) or is_sports_query or is_realtime_query:
                use_search = True
                print("[CERVEAU] Détection automatique de requête sportive ou temps réel (contexte inclus) : activation de Google Search.")
                
            tools_list = [types.Tool(google_search=types.GoogleSearch())] if use_search else None
            if use_search:
                print("[CERVEAU] Activation de l'outil Google Search pour cette demande.")
            else:
                print("[CERVEAU] Recherche désactivée (réponse de tête) pour réduire la latence.")

            prompt_actuel = construire_system_prompt(use_search)
            last_err = None
            chosen_gemini = CHOSEN_MODELS.get("Gemini", "gemini-3.1-flash-lite")
            for model_name in [chosen_gemini]:
                try:
                    print(f"[CERVEAU] Essai modele : {model_name} (Timeout 12s)")
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            client.models.generate_content,
                            model=model_name,
                            config=types.GenerateContentConfig(
                                system_instruction=prompt_actuel,
                                temperature=0.7,
                                tools=tools_list,
                            ),
                            contents=temp_hist
                        ),
                        timeout=12.0
                    )
                    rep = response.text
                    historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
                    historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
                    _sauvegarder_echange_conv(texte, rep)
                    return rep
                except Exception as e:
                    if _quota_mgr.is_quota_error(e):
                        _quota_mgr.mark_quota_exceeded("gemini")
                        raise _QuotaExceededError(f"Gemini quota sur {model_name}: {e}")
                    print(f"[CERVEAU] Echec {model_name} : {e}")
                    last_err = e
                    continue
            raise last_err or Exception("Tous les modeles Gemini ont echoue")

        async def _call_grok():
            if not _quota_mgr.is_available("grok"):
                raise _QuotaExceededError(f"Grok en cooldown ({_quota_mgr.remaining_cooldown('grok')}s)")
            print("[CERVEAU] Tentative avec Grok (xAI)...")
            rep_grok = await pedir_grok(texte)
            if not rep_grok:
                raise Exception("Grok n'a rien renvoyé ou est mal configuré")
            return rep_grok

        async def _call_openai():
            if not _quota_mgr.is_available("openai"):
                raise _QuotaExceededError(f"ChatGPT en cooldown ({_quota_mgr.remaining_cooldown('openai')}s)")
            print("[CERVEAU] Tentative avec ChatGPT (OpenAI)...")
            rep_openai = await pedir_openai(texte)
            if not rep_openai:
                raise Exception("ChatGPT n'a rien renvoyé ou est mal configuré")
            return rep_openai

        # Wrappers pour chaque moteur
        async def _try_claude():
            if anthropic_client and _quota_mgr.is_available("claude"):
                print("[CERVEAU] Tentative avec Claude (Anthropic)...")
                try:
                    rep_claude = await pedir_claude(texte)
                    if rep_claude:
                        return rep_claude
                    print("[CERVEAU] Claude KO (réponse vide).")
                except _QuotaExceededError:
                    print(f"[CERVEAU] Claude quota épuisé — cooldown {_quota_mgr.remaining_cooldown('claude')}s.")
                except Exception as e:
                    print(f"[CERVEAU] Claude erreur ({e}).")
            return None

        async def _try_gemini():
            if gemini_actif:
                try:
                    return await _call_gemini()
                except _QuotaExceededError as e:
                    print(f"[CERVEAU] Gemini quota ({e}).")
                except Exception as e:
                    print(f"[CERVEAU] Gemini erreur ({e}).")
            return None

        async def _try_groq():
            if groq_client and _quota_mgr.is_available("groq"):
                print("[CERVEAU] Tentative avec Groq (Llama 3.3)...")
                try:
                    rep_groq = await pedir_groq(texte)
                    if rep_groq:
                        return rep_groq
                except _QuotaExceededError:
                    print(f"[CERVEAU] Groq quota épuisé — cooldown {_quota_mgr.remaining_cooldown('groq')}s.")
                except Exception as e2:
                    print(f"[CERVEAU] Groq erreur ({e2}).")
            return None

        async def _try_grok():
            if grok_client and _quota_mgr.is_available("grok"):
                try:
                    return await _call_grok()
                except _QuotaExceededError as e:
                    print(f"[CERVEAU] Grok quota ({e}).")
                except Exception as e:
                    print(f"[CERVEAU] Grok erreur ({e}).")
            return None

        async def _try_mistral():
            if mistral_client and _quota_mgr.is_available("mistral"):
                print("[CERVEAU] Tentative avec Mistral (Large)...")
                try:
                    rep_mist = await pedir_mistral(texte)
                    if rep_mist:
                        return rep_mist
                except _QuotaExceededError:
                    print(f"[CERVEAU] Mistral quota épuisé — cooldown {_quota_mgr.remaining_cooldown('mistral')}s.")
                except Exception as e2:
                    print(f"[CERVEAU] Mistral erreur ({e2}).")
            return None


        async def _try_openai():
            if openai_client and _quota_mgr.is_available("openai"):
                print("[CERVEAU] Tentative avec ChatGPT (OpenAI)...")
                try:
                    rep_op = await pedir_openai(texte)
                    if rep_op:
                        return rep_op
                except _QuotaExceededError:
                    print(f"[CERVEAU] ChatGPT quota épuisé — cooldown {_quota_mgr.remaining_cooldown('openai')}s.")
                except Exception as e2:
                    print(f"[CERVEAU] ChatGPT erreur ({e2}).")
            return None

        async def _try_local_uncensored():
            print("[CERVEAU] Tentative avec Modèle Local Uncensored (Astro via Ollama)...")
            try:
                rep_unc = await pedir_ollama_sin_censura(texte)
                if rep_unc:
                    return rep_unc
            except Exception as e_unc:
                print(f"[CERVEAU] Error Local Uncensored : {e_unc}")
            return None

        # Détermination de l'ordre d'appel des cerveaux IA
        cfg = _cargar_config()
        preferred_brain = cfg.get("preferred_brain", "auto")

        order = []
        if preferred_brain in ["local_uncensored", "ollama_astro"]:
            order = ["local_uncensored", "gemini", "claude", "groq", "grok", "openai", "mistral"]
        elif preferred_brain == "gemini":
            order = ["gemini", "claude", "groq", "grok", "openai", "mistral"]
        elif preferred_brain == "groq":
            order = ["groq", "gemini", "claude", "grok", "openai", "mistral"]
        elif preferred_brain == "grok":
            order = ["grok", "openai", "gemini", "claude", "groq", "mistral"]
        elif preferred_brain == "openai":
            order = ["openai", "gemini", "claude", "groq", "grok", "mistral"]
        elif preferred_brain == "claude":
            order = ["claude", "gemini", "groq", "grok", "openai", "mistral"]
        elif preferred_brain == "mistral":
            order = ["mistral", "gemini", "claude", "groq", "grok", "openai"]
        else: # auto
            cerveau = detecter_cerveau(texte)
            if cerveau == "GROK":
                order = ["grok", "openai", "gemini", "claude", "groq", "mistral"]
            else:
                order = ["gemini", "claude", "groq", "grok", "openai", "mistral"]

        # Essayer les cerveaux dans l'ordre défini
        for brain in order:
            if brain == "local_uncensored":
                res = await _try_local_uncensored()
                if res: return res
            elif brain == "gemini":
                res = await _try_gemini()
                if res: return res
            elif brain == "claude":
                res = await _try_claude()
                if res: return res
            elif brain == "groq":
                res = await _try_groq()
                if res: return res
            elif brain == "grok":
                res = await _try_grok()
                if res: return res
            elif brain == "openai":
                res = await _try_openai()
                if res: return res
            elif brain == "mistral":
                res = await _try_mistral()
                if res: return res

        # ── FALLBACKS (Gemini KO ou quota) ───────────────────────────────────
        # --- FALLBACK MÉTÉO/TEMP (HA + OpenMeteo, avant SerpAPI) ---
        t_low = texte.lower()
        _mots_meteo = ["quel temps", "météo", "meteo", "il fait quel temps",
                       "temps qu'il fait", "quel temps il fait", "prévisions",
                       "previsions", "va-t-il pleuvoir", "pleut-il",
                       "fait-il beau", "il va pleuvoir", "température dehors",
                       "temperature dehors", "température extérieure",
                       "temperature exterieure", "combien fait-il dehors",
                       "il fait combien dehors"]
        _mots_temp_int = ["température", "temperature", "il fait chaud",
                          "il fait froid", "combien de degrés",
                          "combien fait-il", "il fait combien"]
        _mots_maison   = ["chez moi", "à la maison", "dans la maison",
                          "intérieur", "interieur", "dans le salon",
                          "dans la chambre", "dans le bureau"]
        _pieces_fallback = {k: k for k in PIECES_CAPTEURS.keys()}
        if "exterieur" in _pieces_fallback:
            _pieces_fallback["extérieur"] = "exterieur"
        if "exterieur" in _pieces_fallback and "dehors" not in _pieces_fallback:
            _pieces_fallback["dehors"] = "exterieur"

        if any(m in t_low for m in _mots_meteo):
            print("[CERVEAU] Requête météo détectée → Home Assistant weather.forecast_amilly")
            meteo_data = get_meteo_structuree(None)
            if meteo_data:
                await send_web_meteo(meteo_data)
            reponse_ha = get_meteo_ha()
            if reponse_ha:
                return reponse_ha
            return get_meteo_actuelle(None)

        if any(m in t_low for m in _mots_temp_int):
            for mot_piece, piece_key in _pieces_fallback.items():
                if mot_piece in t_low:
                    entity_id = PIECES_CAPTEURS.get(piece_key)
                    if entity_id:
                        print(f"[CERVEAU] Temp intérieure détectée → HA {entity_id}")
                        temp = ha_get_etat(entity_id)
                        hum_id = PIECES_HUMIDITE.get(piece_key)
                        hum = ha_get_etat(hum_id) if hum_id else None
                        await send_web_temp_piece({
                            "piece": mot_piece,
                            "temperature": str(temp),
                            "humidite": str(hum) if hum else None,
                        })
                        return f"La température dans le {mot_piece} est de {temp} degrés."
            if any(m in t_low for m in _mots_maison):
                entity_id = PIECES_CAPTEURS.get("salon")
                if entity_id:
                    print(f"[CERVEAU] Temp intérieure 'chez moi' → HA {entity_id}")
                    temp = ha_get_etat(entity_id)
                    hum_id = PIECES_HUMIDITE.get("salon")
                    hum = ha_get_etat(hum_id) if hum_id else None
                    await send_web_temp_piece({
                        "piece": "salon",
                        "temperature": str(temp),
                        "humidite": str(hum) if hum else None,
                    })
                    return f"La température chez vous est de {temp} degrés."

        # --- FALLBACK GROQ (LLAMA 3.3) ---
        if groq_client and _quota_mgr.is_available("groq"):
            print("[CERVEAU] Bascule sur Groq (Llama 3.3).")
            try:
                rep_groq = await pedir_groq(texte)
                if rep_groq:
                    return rep_groq
            except _QuotaExceededError:
                print(f"[CERVEAU] Groq quota épuisé — cooldown {_quota_mgr.remaining_cooldown('groq')}s.")
            except Exception as e2:
                print(f"[CERVEAU] Groq erreur ({e2}).")
        elif groq_client:
            print(f"[CERVEAU] Groq en cooldown ({_quota_mgr.remaining_cooldown('groq')}s). Ignoré.")

        # --- FALLBACK GROK (xAI) ---
        if grok_client and _quota_mgr.is_available("grok"):
            print("[CERVEAU] Bascule sur Grok (xAI).")
            try:
                return await _call_grok()
            except _QuotaExceededError:
                print(f"[CERVEAU] Grok quota épuisé — cooldown {_quota_mgr.remaining_cooldown('grok')}s.")
            except Exception as e2:
                print(f"[ERREUR IA (Grok repli)] {e2}")
        elif grok_client:
            print(f"[CERVEAU] Grok en cooldown ({_quota_mgr.remaining_cooldown('grok')}s). Ignoré.")

        # --- FALLBACK CHATGPT (OpenAI) ---
        if openai_client and _quota_mgr.is_available("openai"):
            print("[CERVEAU] Bascule sur ChatGPT (OpenAI).")
            try:
                return await _call_openai()
            except _QuotaExceededError:
                print(f"[CERVEAU] ChatGPT quota épuisé — cooldown {_quota_mgr.remaining_cooldown('openai')}s.")
            except Exception as e2:
                print(f"[ERREUR IA (ChatGPT repli)] {e2}")
        elif openai_client:
            print(f"[CERVEAU] ChatGPT en cooldown ({_quota_mgr.remaining_cooldown('openai')}s). Ignoré.")

        # --- FALLBACK MISTRAL (Mistral Large) ---
        if mistral_client and _quota_mgr.is_available("mistral"):
            print("[CERVEAU] Bascule sur Mistral (Large).")
            try:
                rep_mist = await pedir_mistral(texte)
                if rep_mist:
                    return rep_mist
            except _QuotaExceededError:
                print(f"[CERVEAU] Mistral quota épuisé — cooldown {_quota_mgr.remaining_cooldown('mistral')}s.")
            except Exception as e2:
                print(f"[ERREUR IA (Mistral repli)] {e2}")
        elif mistral_client:
            print(f"[CERVEAU] Mistral en cooldown ({_quota_mgr.remaining_cooldown('mistral')}s). Ignoré.")

        # --- FALLBACK OLLAMA (100% offline) ---
        print("[CERVEAU] Gemini et Grok KO. Tentative Ollama (local)...")
        rep_ollama = await pedir_ollama(texte)
        if rep_ollama:
            return rep_ollama

        # --- FALLBACK SERPAPI (Web) ---
        # On ne le met qu'à la fin pour éviter qu'il ne "vole" les questions de mémoire
        if len(texte.split()) > 2:
            res_serp = recherche_web_serpapi(texte)
            if res_serp and "VOTRE_CLE" not in res_serp and "rien trouvé" not in res_serp and "erreur" not in res_serp.lower():
                return "Voici ce que j'ai trouvé sur le web : " + res_serp

        # ── Détection : aucune API configurée ou toutes en erreur ──────────
        _aucune_api = (not gemini_actif and not groq_client and not grok_client and not anthropic_client)
        if _aucune_api:
            return (
                "Je suis bien en ligne Christopher, mais mes moteurs d'intelligence artificielle ne sont pas encore configurés. "
                "Pour libérer tout mon potentiel, vous devez renseigner vos clés API dans le fichier .env. "
                "Rendez-vous sur le site TechEnClair — vous y trouverez un guide complet pour les obtenir gratuitement. "
                "En attendant, je reste disponible pour toutes vos commandes locales : domotique, heure, calculs, et bien plus encore !"
            )
        return (
            "Désolé Christopher, tous mes serveurs de réflexion sont actuellement surchargés ou en maintenance, "
            "et mes modèles locaux ne répondent pas non plus. "
            "Je reste disponible pour vos commandes domotiques et locales. "
            "Si ce problème persiste, vérifiez vos clés API sur techenclair.fr."
        )
    finally:
        is_thinking = False
        await send_web_state("idle")

async def pedir_ia_vision(texte, img_b64):
    """Analyse une image (capture d'écran) avec Gemini Vision."""
    global is_thinking, historique, USER_NAME
    if not gemini_actif or client is None:
        return "La vision nécessite une clé Gemini valide. Configurez-la dans le fichier .env."
    is_thinking = True
    await send_web_state("thinking")
    try:
        print("[VISION] Analyse de l'image avec Gemini...")
        
        # Conversion base64 en bytes pour l'API
        img_bytes = base64.b64decode(img_b64)
        image_part = types.Part.from_bytes(
            data=img_bytes,
            mime_type="image/jpeg"
        )
        
        prompt_actuel = construire_system_prompt()
        
        # Check if the query is about fashion/outfits/clothes
        is_fashion_query = any(kw in texte.lower() for kw in [
            "tenue", "vêtement", "vetement", "habillé", "habille",
            "style", "look", "mode", "sappé", "sappe", "sapé", "sape",
            "lookbook", "élégant", "elegant", "porter", "porte quoi",
            "costume", "robe"
        ])
        
        if is_fashion_query:
            prompt_actuel += (
                f"\n\nIMPORTANT : Eres l'expert en mode et styliste personnel de {USER_NAME}. "
                "Analyse en détail sa tenue, l'harmonie des couleurs, les coupes et les éventuels accessoires visibles "
                "sur l'image caméra. Dis-lui clairement et avec élégance s'il est bien habillé. "
                "Fournis-lui des conseils de style constructifs et raffinés pour parfaire son look (accessoires, chaussures, association de couleurs, etc.). "
                "Ton ton doit être très élégant, chic et digne d'un grand couturier. "
                "N'utilise aucun caractère markdown comme des étoiles ou des dièses, car ta réponse sera lue à voix haute."
            )
        else:
            prompt_actuel += f"\n\nIMPORTANT : Tu viens de recevoir une capture d'écran de {USER_NAME}. Analyse-la attentivement et réponds à sa question en te basant sur ce que tu vois."
        
        # On envoie l'image et le texte avec retry en cas de 503
        contents = [
            types.Content(role="user", parts=[image_part, types.Part(text=texte)])
        ]
        
        rep = None
        last_err = None
        chosen_gemini = CHOSEN_MODELS.get("Gemini", "gemini-3.1-flash-lite")
        for model_name in [chosen_gemini]:
            print(f"[VISION] Essai modele : {model_name}")
            for attempt in range(2): # 2 tentatives par modele
                try:
                    print(f"[VISION] Appel modele : {model_name} (Timeout 15s)")
                    # Recherche désactivée par défaut pour la vision afin d'éviter les délais
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            client.models.generate_content,
                            model=model_name,
                            config=types.GenerateContentConfig(
                                system_instruction=prompt_actuel,
                                temperature=0.7,
                                tools=None,
                            ),
                            contents=contents
                        ),
                        timeout=15.0
                    )
                    rep = response.text
                    break
                except Exception as e:
                    if ("503" in str(e) or "overloaded" in str(e).lower()) and attempt < 1:
                        print(f"[VISION] Surcharge {model_name} (503). Retente...")
                        await asyncio.sleep(1)
                        continue
                    print(f"[VISION] Error {model_name} : {e}")
                    last_err = e
                    break
            if rep: break
        
        if not rep:
            err_str = str(last_err).lower() if last_err else ""
            if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                print("[VISION] Quota Gemini epuise — vision impossible sans Gemini.")
                return ("Désolé Christopher, mon quota Gemini est épuisé pour aujourd'hui. "
                        "La vision par caméra et écran fonctionne uniquement avec Gemini — "
                        "je ne peux donc pas analyser d'images en ce moment. "
                        "Réessayez demain quand le quota sera réinitialisé.")
            print("[VISION] Tous les modeles Gemini ont echoue. Bascule sur Grok (Texte uniquement)...")
            if grok_client:
                return await pedir_grok(texte + " (Note: Je n'ai pas pu voir ton écran car mes serveurs de vision sont indisponibles, je réponds donc uniquement à ton texte).")
            raise last_err or Exception("Aucun modele n'a pu analyser l'image")

        # On ajoute la trace dans l'historique (sans l'image pour éviter de saturer la mémoire)
        historique.append(types.Content(role="user", parts=[types.Part(text=f"[Analyse d'écran] {texte}")]))
        historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
        
        return rep
    except Exception as e:
        print(f"[VISION] Error Gemini Vision : {e}")
        # On évite les accolades dans le message d'erreur pour ne pas perturber l'extracteur JSON
        err_msg = str(e).replace("{", "[").replace("}", "]")
        return f"Désolé Christopher, je n'ai pas pu analyser tu écran. Error : {err_msg}"
    finally:
        is_thinking = False
        await send_web_state("idle")
builtins.pedir_ia_vision = pedir_ia_vision

def detecter_cerveau(texte):
    # Heuristique pour basculer sur Grok uniquement pour X/Twitter
    mots_cles_grok = ["sur x", "twitter", "grok", "elon", "x.com"]
    cmd = texte.lower()
    if any(m in cmd for m in mots_cles_grok):
        return "GROK"
    return "GEMINI"

async def pedir_openai(texte):
    if not openai_client:
        return None
    
    try:
        system_prompt = construire_system_prompt()
        from datetime import datetime as _dt_openai
        _now_str = _dt_openai.now().strftime("%A %d %B %Y à %H:%M")
        system_prompt += f"\n\n🕒 CONTEXTE TEMPOREL : Nous sommes le {_now_str}. Tiens-en compte pour toutes tes réponses (actualités, matchs, événements du jour, etc.). Attention : tu n'as pas accès à internet, ne pas inventer des informations que tu ne connais pas avec certitude."
        messages = [{"role": "system", "content": system_prompt}]
        
        for h in historique[-30:]:
            role = "user" if h.role == "user" else "assistant"
            msg_text = h.parts[0].text
            messages.append({"role": role, "content": msg_text})
        
        messages.append({"role": "user", "content": texte})
        
        chosen_openai = CHOSEN_MODELS.get("ChatGPT", "gpt-5.6-sol")
        _openai_models = [chosen_openai]
        completion = None
        last_openai_err = None
        for _om in _openai_models:
            try:
                kwargs = {
                    "model": _om,
                    "messages": messages
                }
                is_reasoning = _om.startswith("o") or any(x in _om.lower() for x in ["luna", "sol", "terra"])
                if not is_reasoning:
                    kwargs["max_tokens"] = 2048
                    kwargs["temperature"] = 0.7
                    
                try:
                    completion = openai_client.chat.completions.create(**kwargs)
                except Exception as api_e:
                    if "max_tokens" in str(api_e) and "max_completion_tokens" in str(api_e):
                        kwargs.pop("max_tokens", None)
                        kwargs.pop("temperature", None)
                        if not is_reasoning:
                            kwargs["max_completion_tokens"] = 2048
                        completion = openai_client.chat.completions.create(**kwargs)
                    else:
                        raise api_e
                
                if completion and completion.choices:
                    break
            except Exception as e_mod:
                print(f"[OPENAI] Error avec le modèle {_om} : {e_mod}")
                last_openai_err = e_mod
                if "429" in str(e_mod) or "quota" in str(e_mod).lower() or "rate limit" in str(e_mod).lower():
                    _quota_mgr.mark_failed("openai")
                    raise _QuotaExceededError(str(e_mod))
                
        if completion and completion.choices:
            rep = completion.choices[0].message.content
            historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
            historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
            _sauvegarder_echange_conv(texte, rep)
            return rep
        else:
            if last_openai_err:
                raise last_openai_err
            return None
            
    except _QuotaExceededError as qe:
        raise qe
    except Exception as e:
        print(f"[ERREUR CHATGPT] {e}")
        return None

async def pedir_grok(texte, system_prompt_override=None, temperature_override=None):
    if not grok_client:
        return None
    
    try:
        if system_prompt_override:
            system_prompt = system_prompt_override
        else:
            # SYNC : On utilise le même prompt système que Gemini (incluant la mémoire)
            system_prompt = construire_system_prompt()
            # Injection de la date et heure actuelles pour que Grok soit contextualisé
            from datetime import datetime as _dt_grok
            _now_str = _dt_grok.now().strftime("%A %d %B %Y à %H:%M")
            system_prompt += f"\n\n⚠️ CONTEXTE TEMPOREL : Nous sommes le {_now_str}. Tiens-en compte pour toutes tes réponses (actualités, matchs, événements du jour, etc.). Attention : tu n'as pas accès à internet, ne pas inventer des informations que tu ne connais pas avec certitude."
        
        messages = [{"role": "system", "content": system_prompt}]
        
        for h in historique[-30:]: # Limiter aux 30 derniers messages
            role = "user" if h.role == "user" else "assistant"
            msg_text = h.parts[0].text
            messages.append({"role": role, "content": msg_text})
        
        messages.append({"role": "user", "content": texte})
        
        # Modèles xAI disponibles
        chosen_grok = CHOSEN_MODELS.get("Grok", "grok-2")
        _grok_models = [chosen_grok, "grok-2", "grok-beta", "grok-2-latest", "grok-4.5"]
        # Dédupliquer tout en gardant l'ordre
        _grok_models = list(dict.fromkeys(_grok_models))
        
        temp_val = temperature_override if temperature_override is not None else 0.7
        completion = None
        last_grok_err = None
        for _gm in _grok_models:
            try:
                completion = grok_client.chat.completions.create(
                    model=_gm,
                    messages=messages,
                    temperature=temp_val,
                )
                print(f"[GROK] Modèle utilisé : {_gm} (Temperature: {temp_val})")
                break
            except Exception as _gm_err:
                print(f"[GROK] Modèle {_gm} indisponible : {_gm_err}")
                last_grok_err = _gm_err
                continue
        if completion is None:
            raise last_grok_err or Exception("Aucun modèle Grok disponible")
        
        rep = completion.choices[0].message.content
        
        # On synchronise l'historique Gemini
        historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
        historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
        _sauvegarder_echange_conv(texte, rep)
        
        return rep
    except Exception as e:
        if _quota_mgr.is_quota_error(e):
            _quota_mgr.mark_quota_exceeded("grok")
            raise _QuotaExceededError(f"Grok quota: {e}")
        print(f"[ERREUR GROK] {e}")
        return None

async def handle_image_result_global(result_img, prompt_fr):
    import json
    if result_img and "error" not in result_img:
        source_model = result_img.get("source", "Inconnu")
        await hablar(f"Voici l'image générée avec {source_model}. J'ai enregistré l'image dans mon dossier JARVIS directement.")
        if CONNECTED_CLIENTS:
            try:
                msg_img = json.dumps({
                    "type": "show_generated_image",
                    "url": result_img["url"],
                    "prompt": prompt_fr,
                    "source": source_model
                })
                await asyncio.gather(*[ws.send(msg_img) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            except Exception: pass
    else:
        err = result_img.get("error", "Error inconnue.") if result_img else "Échec de la génération."
        await hablar(f"Désolé {USER_NAME}, je n'ai pas pu générer l'image. {err}")

async def generer_image_xai(prompt: str, force_model: str = None) -> dict:
    """
    Génère une image IA - modèles xAI : grok-imagine-image / grok-imagine-quality
    Fallback : Gemini Imagen 4
    """
    import base64
    import time as _time

    if not grok_client and not (client and gemini_actif):
        return {"error": "Aucun client configuré pour la génération d'image."}

    _prompt_en = prompt
    try:
        if client and gemini_actif:
            enrich_resp = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=f"Translate this prompt into a highly detailed English prompt for an image generation AI. Return ONLY the translated English prompt, nothing else: {prompt}",
            )
            _prompt_en = enrich_resp.text.strip()
            print(f"[IMAGE_GEN] Prompt enrichi : {_prompt_en[:100]}...")
    except Exception as _e:
        print(f"[IMAGE_GEN] Enrichissement ignoré : {_e}")

    cfg = _cargar_config()
    pref = cfg.get("preferred_brain", "auto")
    use_grok_first = (pref == "grok")
    if force_model == "grok":
        use_grok_first = True
    elif force_model in ["gemini", "gemini_flash_lite"]:
        use_grok_first = False

    async def _try_xai():
        if grok_client:
            for _xai_model in ["grok-imagine-image", "grok-imagine-quality"]:
                try:
                    print(f"[IMAGE_GEN] Tentative avec {_xai_model}...")
                    response = await asyncio.to_thread(
                        grok_client.images.generate,
                        model=_xai_model,
                        prompt=_prompt_en,
                        n=1,
                        response_format="b64_json",
                    )
                    img_data = response.data[0]
                    if hasattr(img_data, 'b64_json') and img_data.b64_json:
                        ts = int(_time.time() * 1000)
                        img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"jarvis_xai_{ts}.png")
                        with open(img_path, "wb") as _f:
                            _f.write(base64.b64decode(img_data.b64_json))
                        data_url = f"data:image/png;base64,{img_data.b64_json}"
                        print(f"[IMAGE_GEN] ✅ Image générée via {_xai_model} ({len(img_data.b64_json)//1024} Ko).")
                        return {"url": data_url, "path": img_path, "prompt_fr": prompt, "prompt_en": _prompt_en, "source": f"xAI ({_xai_model})"}
                    elif hasattr(img_data, 'url') and img_data.url:
                        return {"url": img_data.url, "prompt_fr": prompt, "prompt_en": _prompt_en, "source": f"xAI ({_xai_model})"}
                except Exception as _xai_err:
                    print(f"[IMAGE_GEN] {_xai_model} échoué : {_xai_err}")
        return None

    async def _try_openai():
        if openai_client:
            model_to_use = "gpt-image-2"
            try:
                print(f"[IMAGE_GEN] Tentative avec OpenAI (ChatGPT - {model_to_use})...")
                response = await asyncio.to_thread(
                    openai_client.images.generate,
                    model=model_to_use,
                    prompt=_prompt_en,
                    n=1,
                    size="1024x1024"
                )
                img_data = response.data[0]
                import time as _time
                import os
                import base64
                ts = int(_time.time() * 1000)
                img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"jarvis_openai_{ts}.png")
                
                if hasattr(img_data, "b64_json") and img_data.b64_json:
                    with open(img_path, "wb") as _f:
                        _f.write(base64.b64decode(img_data.b64_json))
                    data_url = f"data:image/png;base64,{img_data.b64_json}"
                    print(f"[IMAGE_GEN] o. Image générée via {model_to_use}.")
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
                    print(f"[IMAGE_GEN] o. Image générée via {model_to_use}.")
                    return {"url": data_url, "path": img_path, "prompt_fr": prompt, "prompt_en": _prompt_en, "source": "ChatGPT (gpt-image-2)"}
            except Exception as _err:
                print(f"[IMAGE_GEN] Error OpenAI : {_err}")
        return None

    async def _try_gemini():
        model_to_use = "imagen-4.0-generate-001" if force_model == "gemini" else "gemini-3.1-flash-lite-image"
        nom_affichage = "Imagen 4 (Google)" if force_model == "gemini" else "Gemini 3.1 Flash Lite Image"
        try:
            print(f"[IMAGEN] Génération via {nom_affichage}...")
            img_bytes = None
                
            if model_to_use == "gemini-3.1-flash-lite-image":
                # gemini-3.1-flash-lite-image utilise generate_content avec response_modalities
                resp = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model_to_use,
                    contents=_prompt_en,
                    config=types.GenerateContentConfig(
                        response_modalities=[types.Modality.TEXT, types.Modality.IMAGE],
                    ),
                )
                if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
                    for part in resp.candidates[0].content.parts:
                        if part.inline_data:
                            img_bytes = part.inline_data.data
                            break
            else:
                # Imagen 4 utilise generate_images
                imagen_response = await asyncio.to_thread(
                    client.models.generate_images,
                    model=model_to_use,
                    prompt=_prompt_en,
                    config={"number_of_images": 1},
                )
                if imagen_response.generated_images:
                    img_bytes = imagen_response.generated_images[0].image.image_bytes
                
            if img_bytes:
                import base64
                import time as _time
                import os
                b64_str = base64.b64encode(img_bytes).decode("utf-8")
                ts = int(_time.time() * 1000)
                img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"jarvis_imagen_{ts}.png")
                with open(img_path, "wb") as _f:
                    _f.write(img_bytes)
                data_url = f"data:image/png;base64,{b64_str}"
                print(f"[IMAGEN] o. Image générée via {nom_affichage} ({len(b64_str)//1024} Ko).")
                return {"url": data_url, "path": img_path, "prompt_fr": prompt, "prompt_en": _prompt_en, "source": nom_affichage}
        except Exception as _img_err:
            print(f"[IMAGEN] Error Gemini : {_img_err}")
        return None


    if force_model == "openai":
        res = await _try_openai()
        if res: return res
        res = await _try_xai()
        if res: return res
        res = await _try_gemini()
        if res: return res
    elif force_model == "grok" or use_grok_first:
        res = await _try_xai()
        if res: return res
        res = await _try_gemini()
        if res: return res
        res = await _try_openai()
        if res: return res
    else:
        res = await _try_gemini()
        if res: return res
        res = await _try_openai()
        if res: return res
        res = await _try_xai()
        if res: return res

    return {"error": "Aucun moteur de génération d'image disponible."}


async def generer_video_xai(prompt: str) -> dict:
    """
    Génère une vidéo via xAI grok-imagine-video ou grok-imagine-video-1
    Retourne {'url', 'path', 'prompt_fr', 'prompt_en', 'source'} ou {'error'}
    """
    import base64
    import time as _time

    if not grok_client:
        return {"error": "Client xAI non disponible."}

    # Enrichir le prompt en anglais
    _prompt_en = prompt
    try:
        enrich_resp = grok_client.chat.completions.create(
            model="grok-4.3",
            messages=[{"role": "user", "content": (
                "Translate and enhance this video generation prompt to English. "
                "Make it very cinematic, detailed, with motion description. Return ONLY the English prompt.\n\n"
                f"French prompt: {prompt}"
            )}],
            temperature=0.7,
            max_tokens=200,
        )
        _prompt_en = enrich_resp.choices[0].message.content.strip()
        print(f"[VIDEO_GEN] Prompt enrichi : {_prompt_en[:100]}...")
    except Exception as _e:
        print(f"[VIDEO_GEN] Enrichissement ignoré : {_e}")

    # Essai grok-imagine-video puis grok-imagine-video-1
    for _vid_model in ["grok-imagine-video", "grok-imagine-video-1"]:
        try:
            print(f"[VIDEO_GEN] Tentative avec {_vid_model}...")
            response = await asyncio.to_thread(
                grok_client.videos.generate,
                model=_vid_model,
                prompt=_prompt_en,
            )
            vid_data = response.data[0] if hasattr(response, 'data') else response

            # Récupération URL ou bytes
            if hasattr(vid_data, 'url') and vid_data.url:
                print(f"[VIDEO_GEN] ✅ Vidéo générée via {_vid_model}.")
                return {"url": vid_data.url, "prompt_fr": prompt, "prompt_en": _prompt_en, "source": f"xAI ({_vid_model})", "type": "video"}
            elif hasattr(vid_data, 'b64_json') and vid_data.b64_json:
                ts = int(_time.time() * 1000)
                vid_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"jarvis_video_{ts}.mp4")
                with open(vid_path, "wb") as _f:
                    _f.write(base64.b64decode(vid_data.b64_json))
                data_url = f"data:video/mp4;base64,{vid_data.b64_json}"
                print(f"[VIDEO_GEN] ✅ Vidéo générée via {_vid_model}.")
                return {"url": data_url, "path": vid_path, "prompt_fr": prompt, "prompt_en": _prompt_en, "source": f"xAI ({_vid_model})", "type": "video"}
        except Exception as _vid_err:
            print(f"[VIDEO_GEN] {_vid_model} échoué : {_vid_err}")

    return {"error": "Génération vidéo échouée. Vérifiez tu accès aux modèles grok-imagine-video."}


async def pedir_ollama(texte):
    """Appelle un modèle local via Ollama (100% offline) avec options GPU optimisées."""
    global historique
    try:
        system_prompt = construire_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        
        # Limiter à 4 échanges (8 messages) pour préserver la VRAM et accélérer l'inférence
        for h in historique[-8:]:
            role = "user" if h.role == "user" else "assistant"
            messages.append({"role": role, "content": h.parts[0].text})
        messages.append({"role": "user", "content": texte})
        
        last_err = None
        chosen_ollama = CHOSEN_MODELS.get("Ollama", "dolphin3")
        for model_name in [chosen_ollama]:
            try:
                print(f"[OLLAMA] Essai modele local : {model_name}")
                options = _obtener_opciones_ollama_para_modelo(model_name)
                resp = await asyncio.wait_for(
                    asyncio.to_thread(
                        requests.post,
                        f"{OLLAMA_URL}/api/chat",
                        json={"model": model_name, "messages": messages, "stream": False, "keep_alive": -1, "options": options},
                        timeout=90
                    ),
                    timeout=95.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    rep = data.get("message", {}).get("content", "")
                    if rep:
                        historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
                        historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
                        _sauvegarder_echange_conv(texte, rep)
                        print(f"[OLLAMA] Reponse recue de {model_name}")
                        return rep
                else:
                    print(f"[OLLAMA] Error HTTP {resp.status_code} pour {model_name}")
                    last_err = Exception(f"HTTP {resp.status_code}")
            except Exception as e:
                print(f"[OLLAMA] Echec {model_name} : {e}")
                last_err = e
                continue
        
        print(f"[OLLAMA] Tous les modeles locaux ont echoue")
        return None
    except Exception as e:
        print(f"[ERREUR OLLAMA] {e}")
        return None


def _obtener_opciones_ollama_para_modelo(model_name: str) -> dict:
    """
    Retourne les options Ollama 100% compatibles pour maximiser la vitesse GPU.
    
    Options RETIRÉES (causaient des erreurs 400 silencieuses) :
    - flash_attn  : non standard dans l'API Ollama (géré en interne par Ollama)
    - f16_kv      : non standard dans l'API Ollama
    - presence_penalty : pas supporté dans toutes les versions
    
    Options GPU clés (100% compatibles toutes versions Ollama) :
    - num_gpu=99  : charge toutes les layers sur le GPU (RTX 3070 = 100% GPU)
    - num_batch   : taille des batchs GPU — plus grand = meilleur débit GPU
    - num_thread  : threads CPU pour le pré/post-processing
    - num_ctx     : taille du contexte (8192 = rapide + suffisant)
    - num_predict : limite la longueur de la réponse
    """
    import os
    num_threads = os.cpu_count() or 8
    m_low = model_name.lower()

    # num_ctx adapté au modèle — tous à 8192 (rapide, suffisant pour conversation)
    if "phi3.5" in m_low or "phi-3.5" in m_low or "phi3" in m_low:
        num_ctx = 4096   # Phi-3.5 Mini est très rapide, 4096 suffit largement
    elif "llama3.1" in m_low or "llama-3.1" in m_low:
        num_ctx = 8192   # Llama 3.1 8B : 8192 optimal
    else:  # dolphin3 et autres
        num_ctx = 6144   # Dolphin3 : 6144 = bon compromis vitesse/qualité

    return {
        # ━ GPU (LE PLUS IMPORTANT) ━
        "num_gpu":    99,          # Force toutes les layers sur le GPU RTX 3070
        "num_batch": 512,          # Taille du batch GPU — augmente le débit de tokens
        # ━ CPU ━
        "num_thread": num_threads, # Tous les cœurs CPU pour le pré/post-processing
        # ━ CONTEXTE ━
        "num_ctx":    num_ctx,     # Fenêtre de contexte adaptée
        "num_predict":512,         # Max 512 tokens de réponse (conversationnel)
        # ━ QUALITÉ / VITESSE ━
        "temperature":   0.7,
        "top_p":         0.9,
        "repeat_penalty":1.1,      # Anti-répétition léger
    }

def _verificar_ollama_estado():
    """Vérifie si le service Ollama local répond et renvoie les modèles installés."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if r.status_code == 200:
            models_data = r.json().get("models", [])
            installed = [m.get("name", "") for m in models_data]

            # Recherche de modèles locaux connus (dolphin, phi3.5, llama3.1)
            local_known = {
                "dolphin3":    ["dolphin", "hermes", "uncensored", "wizardlm-uncensored"],
                "phi3.5":      ["phi3.5", "phi-3.5", "phi3:mini", "phi3"],
                "llama3.1:8b": ["llama3.1", "llama3.1:8b", "llama-3.1"]
            }
            found_models = {}      # {model_id: installed_name}
            found_uncensored = None

            for m in installed:
                m_low = m.lower()
                for model_id, keywords in local_known.items():
                    if any(kw in m_low for kw in keywords):
                        found_models[model_id] = m
                        if model_id == "dolphin3" and found_uncensored is None:
                            found_uncensored = m
                        break

            return {
                "online": True,
                "installed_models": installed,
                "found_local_models": found_models,         # {id: name}
                "has_uncensored_model": (found_uncensored is not None),
                "uncensored_model_name": found_uncensored
            }
    except Exception as e:
        print(f"[OLLAMA CHECK] Servicio fuera de línea ou non disponible : {e}")
    return {
        "online": False,
        "installed_models": [],
        "found_local_models": {},
        "has_uncensored_model": False,
        "uncensored_model_name": None
    }

def _encontrar_modelo_ollama_sin_censura():
    """Retourne le modèle local à utiliser selon la config et les modèles installés."""
    cfg = _cargar_config()
    preferred_local = cfg.get("preferred_local_model", "dolphin3")
    st = _verificar_ollama_estado()
    found_models = st.get("found_local_models", {})

    # 1. Le modèle préféré est-il installé ?
    if preferred_local in found_models:
        model_name = found_models[preferred_local]
        print(f"[OLLAMA UNCENSORED] Modelo preferido encontrado : {model_name} (id={preferred_local})")
        return model_name

    # 2. Fallback : chercher n'importe quel modèle local connu installé
    for fallback_id in ["dolphin3", "phi3.5", "llama3.1:8b"]:
        if fallback_id in found_models:
            model_name = found_models[fallback_id]
            print(f"[OLLAMA UNCENSORED] Reemplazo por modelo instalado : {model_name}")
            return model_name

    # 3. Dernier recours : premier modèle installé quelconque
    if st.get("installed_models"):
        return st.get("installed_models")[0]

    # 4. Valeur par défaut absolue
    return preferred_local

def _descargar_modelo_ollama(model_name, loop, websocket):
    """Télécharge un modèle Ollama en streaming et informe le frontend en temps réel."""
    import json as _j
    def _send(status_msg, pct=0, done=False, success=True):
        asyncio.run_coroutine_threadsafe(
            websocket.send(_j.dumps({
                "type": "ollama_pull_progress",
                "status": status_msg,
                "pct": pct,
                "done": done,
                "success": success
            })), loop
        )
    try:
        _send(f"▶ Inicio de la descarga de {model_name} via Ollama...", pct=1)
        r = requests.post(f"{OLLAMA_URL}/api/pull", json={"name": model_name}, stream=True, timeout=1800)
        if r.status_code == 200:
            for line in r.iter_lines():
                if line:
                    try:
                        data = _j.loads(line.decode('utf-8'))
                        status_str = data.get("status", "")
                        completed = data.get("completed", 0)
                        total = data.get("total", 0)
                        pct = 0
                        if total > 0 and completed > 0:
                            pct = min(99, int((completed / total) * 100))
                        
                        if completed and total:
                            mb_done = int(completed / (1024 * 1024))
                            mb_total = int(total / (1024 * 1024))
                            _send(f"📥 {status_str} ({mb_done} MB / {mb_total} MB)", pct=pct)
                        else:
                            _send(f"📥 {status_str}", pct=pct)
                    except Exception:
                        pass
            _send(f"✅ Modèle {model_name} téléchargé et listo para usar !", pct=100, done=True, success=True)
        else:
            _send(f"❌ Error HTTP {r.status_code} lors du téléchargement d'Ollama.", pct=0, done=True, success=False)
    except Exception as e:
        _send(f"❌ Excepción durante la descarga Ollama : {e}", pct=0, done=True, success=False)

# ══════════════════════════════════════════════════════════════
#  KOKORO-TTS LOCAL (SYNTHÈSE VOCALE ULTRARÉALISTE 100% OFFLINE)
# ══════════════════════════════════════════════════════════════

_KOKORO_ONNX_INSTANCE = None

def _verificar_kokoro_estado():
    """Vérifie si le service local Kokoro-TTS est en ligne (API HTTP ou module Python kokoro-onnx)."""
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

def _instalar_kokoro_tts(loop, websocket):
    """Télécharge et installe Kokoro-TTS localement en arrière-plan."""
    import json as _j
    import subprocess
    import sys
    
    def _send(status_msg, pct=0, done=False, success=True):
        asyncio.run_coroutine_threadsafe(
            websocket.send(_j.dumps({
                "type": "kokoro_install_progress",
                "status": status_msg,
                "pct": pct,
                "done": done,
                "success": success
            })), loop
        )
    try:
        _send("▶ Démarrage de l'installation de Kokoro-TTS Local...", pct=10)
        cmd = [sys.executable, "-m", "pip", "install", "kokoro-onnx", "soundfile"]
        _send("📦 Installation des paquets Python (kokoro-onnx, soundfile)...", pct=35)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        
        if proc.returncode == 0:
            _send("📥 Téléchargement et vérification des paquets Kokoro...", pct=75)
            try:
                import kokoro_onnx
                _send("✅ Kokoro-TTS Local installé avec succès !", pct=100, done=True, success=True)
            except Exception as e:
                _send(f"⚠️ Paquetes instalados, prêts pour l'utilisation.", pct=100, done=True, success=True)
        else:
            _send(f"❌ Error installation pip : {proc.stderr[:120]}", pct=0, done=True, success=False)
    except Exception as e:
        _send(f"❌ Excepción durante la instalación de Kokoro : {e}", pct=0, done=True, success=False)

async def _kokoro_tts_a_archivo(texte: str, voice_name: str, output_file: str) -> bool:
    """Génère un fichier audio via Kokoro-TTS Local (API HTTP ou kokoro-onnx embarqué)."""
    clean_voice = voice_name.replace("kokoro_", "")
    if not clean_voice:
        clean_voice = "ff_siwis"
        
    # 1. Essai via l'API HTTP Kokoro (ex: http://127.0.0.1:8880/v1/audio/speech)
    try:
        payload = {
            "model": "kokoro",
            "input": texte,
            "voice": clean_voice,
            "response_format": "mp3" if output_file.endswith(".mp3") else "wav"
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
            with open(output_file, "wb") as f:
                f.write(resp.content)
            print(f"[KOKORO TTS API] ✅ Audio generado vía Kokoro HTTP API ({clean_voice}).")
            return True
    except Exception:
        pass

    # 2. Essai via kokoro-onnx embarqué
    try:
        def _synth_onnx():
            from kokoro_onnx import Kokoro
            global _KOKORO_ONNX_INSTANCE
            if _KOKORO_ONNX_INSTANCE is None:
                import os
                model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kokoro_model")
                os.makedirs(model_dir, exist_ok=True)
                onnx_path = os.path.join(model_dir, "kokoro-v1.0.onnx")
                voices_bin = os.path.join(model_dir, "voices-v1.0.bin")
                voices_json = os.path.join(model_dir, "voices.json")
                
                import urllib.request
                if not os.path.exists(onnx_path):
                    print("[KOKORO TTS] Descarga del modelo kokoro-v1.0.onnx (~300 Mo)...")
                    urllib.request.urlretrieve("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx", onnx_path)
                if not (os.path.exists(voices_bin) or os.path.exists(voices_json)):
                    print("[KOKORO TTS] Téléchargement du fichier de voix voices-v1.0.bin...")
                    try:
                        urllib.request.urlretrieve("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin", voices_bin)
                    except Exception:
                        urllib.request.urlretrieve("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json", voices_json)
                
                voices_file = voices_bin if os.path.exists(voices_bin) else voices_json
                _KOKORO_ONNX_INSTANCE = Kokoro(onnx_path, voices_file)
            
            lang = "fr-fr"
            if clean_voice.startswith(("af_", "am_")):
                lang = "en-us"
            elif clean_voice.startswith(("bf_", "bm_")):
                lang = "en-gb"
            elif clean_voice.startswith(("es_", "ef_", "em_")):
                lang = "es"
            elif clean_voice.startswith(("it_", "if_", "im_")):
                lang = "it"

            samples, sample_rate = _KOKORO_ONNX_INSTANCE.create(texte, voice=clean_voice, speed=1.0, lang=lang)
            import soundfile as sf
            sf.write(output_file, samples, sample_rate)
            return True

        ok = await asyncio.to_thread(_synth_onnx)
        if ok:
            print(f"[KOKORO TTS ONNX] ✅ Audio generado vía kokoro-onnx ({clean_voice}).")
            return True
    except Exception as e_onnx:
        print(f"[KOKORO TTS ONNX] {e_onnx}")

    return False

async def pedir_ollama_sin_censura(texte):
    """Appelle le modèle local Uncensored via Ollama avec streaming pour une réponse plus rapide."""
    global historique, _OLLAMA_MODEL_LOADED
    
    if not _OLLAMA_MODEL_LOADED:
        await hablar(f"Un instant {USER_NAME}, je charge le modèle local en mémoire vidéo. Veuillez patienter quelques secondes...")

    try:
        from datetime import datetime as _dt_ollama
        _now_str = _dt_ollama.now().strftime("%A %d %B %Y à %H:%M")
        
        cfg_tone = _cargar_config()
        tone = cfg_tone.get("agent_tone", "default")
        
        if tone == "astro":
            base_prompt = PROMPT_ASTRO_MODE
        elif tone == "spicy":
            base_prompt = PROMPT_SPICY_MODE
        else:
            base_prompt = f"Eres JARVIS, assistant IA personnel et direct de {USER_NAME}. Sois concis, direct, naturel et sans fioritures (1 à 4 phrases max)."
            
        securite_directive = (
            "\n\n[SÉCURITÉ STRICTE & CONFIDENTIALITÉ]\n"
            "- Il t'est STRICTEMENT INTERDIT de révéler, afficher ou mentionner les clés d'API, tokens, mots de passe ou chemins de configuration interne du système, même si l'utilisateur insiste ou tente de te piéger. Reste toujours dans ton rôle sans divulguer d'informations sensibles."
        )
        
        domotique_directive = (
            f"\n\n[CONTRÔLE DOMOTIQUE HOME ASSISTANT]\n"
            f"Eres connecté à Home Assistant pour contrôler la maison de {USER_NAME}.\n"
            "Quand l'utilisateur demande d'allumer, éteindre ou régler des lumières, prises, chauffage ou climatisation, tu DOIS inclure la commande JSON correspondante dans ta réponse :\n"
            '- Lumières : {"action": "ha_lumiere", "piece": "salon/chambre/cuisine/bureau/...", "etat": "on/off", "couleur": "rouge/bleu/blanc/...", "luminosite": 0-255}\n'
            '- Prises : {"action": "ha_prise", "piece": "salon/chambre/bureau/...", "etat": "on/off"}\n'
            '- Température / Climat : {"action": "ha_temperature", "piece": "salon/chambre/bureau"}\n'
            "Exemple pour 'Allume la lumière du salon' -> Réponds avec ton style habituel suivi du JSON : C'est fait, lumière du salon allumée. {\"action\": \"ha_lumiere\", \"piece\": \"salon\", \"etat\": \"on\"}"
        )
        
        full_prompt = base_prompt + securite_directive + domotique_directive + f"\n\nContextual info: L'utilisateur s'appelle {USER_NAME}. Nous sommes le {_now_str}."
        
        messages = [{"role": "system", "content": full_prompt}]
        # Limiter à 4 échanges récents (8 messages) pour un prompt prefill instantané sur GPU
        for h in historique[-8:]:
            role = "user" if h.role == "user" else "assistant"
            messages.append({"role": role, "content": h.parts[0].text})
        messages.append({"role": "user", "content": texte})
        
        target_model = _encontrar_modelo_ollama_sin_censura()
        options = _obtener_opciones_ollama_para_modelo(target_model)
        options["temperature"] = 0.8
        print(f"[OLLAMA UNCENSORED] Modèle : {target_model} | ctx={options['num_ctx']} | gpu={options['num_gpu']} | threads={options['num_thread']}")
        
        import json as _j
        
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": True,
            "keep_alive": -1,   # ← GARDE LE MODÈLE DANS LA VRAM RTX 3070 EN PERMANENCE
            "options": options
        }
        
        def _stream_ollama():
            """Appel avec streaming — accumule les tokens et retourne le texte complet."""
            try:
                r = requests.post(
                    f"{OLLAMA_URL}/api/chat",
                    json=payload,
                    stream=True,
                    timeout=90
                )
                if r.status_code != 200:
                    err_body = r.text[:300] if r.text else "(aucun détail)"
                    print(f"[OLLAMA UNCENSORED] ❌ Error HTTP {r.status_code} : {err_body}")
                    return None
                
                full_text = ""
                for line in r.iter_lines():
                    if line:
                        try:
                            chunk = _j.loads(line.decode('utf-8'))
                            token = chunk.get("message", {}).get("content", "")
                            full_text += token
                            if chunk.get("done"):
                                break
                        except Exception as _parse_err:
                            print(f"[OLLAMA STREAM] Parse err : {_parse_err}")
                            pass
                return full_text.strip() if full_text.strip() else None
            except requests.exceptions.Timeout:
                print("[OLLAMA UNCENSORED] ❌ Timeout connexion (90s).")
                return None
            except Exception as _se:
                print(f"[OLLAMA UNCENSORED] ❌ Error streaming : {_se}")
                return None
        
        rep = await asyncio.wait_for(
            asyncio.to_thread(_stream_ollama),
            timeout=100.0
        )
        
        # ── FALLBACK : si le streaming échoue, on tente sans streaming ──
        if rep is None:
            print("[OLLAMA UNCENSORED] ⚠️ Streaming échoué, tentative sans streaming...")
            try:
                fallback_payload = dict(payload)
                fallback_payload["stream"] = False
                resp_fb = await asyncio.wait_for(
                    asyncio.to_thread(
                        requests.post,
                        f"{OLLAMA_URL}/api/chat",
                        json=fallback_payload,
                        timeout=90
                    ),
                    timeout=95.0
                )
                if resp_fb.status_code == 200:
                    rep = resp_fb.json().get("message", {}).get("content", "").strip() or None
                    if rep:
                        print("[OLLAMA UNCENSORED] ✅ Fallback sans streaming OK.")
                else:
                    err_body = resp_fb.text[:300] if resp_fb.text else ""
                    print(f"[OLLAMA UNCENSORED] ❌ Fallback échoué HTTP {resp_fb.status_code}: {err_body}")
            except Exception as _fb_err:
                print(f"[OLLAMA UNCENSORED] ❌ Fallback exception : {_fb_err}")
        
        if rep:
            # Nettoyer les balises <think> éventuelles (Qwen, DeepSeek style)
            import re as _re
            rep = _re.sub(r'<think>.*?</think>\s*', '', rep, flags=_re.DOTALL).strip()
            
            historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
            historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
            _sauvegarder_echange_conv(texte, rep)
            _OLLAMA_MODEL_LOADED = True
            print(f"[OLLAMA UNCENSORED] Réponse reçue de {target_model}")
            return rep
        
        print(f"[OLLAMA UNCENSORED] Réponse vide ou échec.")
        return None

    except asyncio.TimeoutError:
        print(f"[OLLAMA UNCENSORED] Timeout 120s dépassé.")
        return None
    except Exception as e:
        print(f"[ERREUR OLLAMA UNCENSORED] {e}")
        return None

async def pedir_groq(texte):
    """Appelle Groq (Llama 3.3) en fallback gratuit."""
    if not groq_client:
        return None

    try:
        # SYNC : On utilise le même prompt système que Gemini (incluant la mémoire)
        system_prompt = construire_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        
        for h in historique[-30:]:
            role = "user" if h.role == "user" else "assistant"
            messages.append({"role": role, "content": h.parts[0].text})
            
        messages.append({"role": "user", "content": texte})

        completion = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model=CHOSEN_MODELS.get("Groq", "llama-3.3-70b-versatile"),
            messages=messages,
            temperature=0.7,
        )

        rep = completion.choices[0].message.content

        historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
        historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
        _sauvegarder_echange_conv(texte, rep)

        return rep
    except Exception as e:
        if _quota_mgr.is_quota_error(e):
            _quota_mgr.mark_quota_exceeded("groq")
            raise _QuotaExceededError(f"Groq quota: {e}")
        print(f"[ERREUR GROQ] {e}")
        return None

async def pedir_mistral(texte):
    """Appelle Mistral AI en alternative/fallback."""
    if not mistral_client:
        return None
    try:
        # SYNC : On utilise le même prompt système que Gemini (incluant la mémoire)
        system_prompt = construire_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        for h in historique[-30:]:
            role = "user" if h.role == "user" else "assistant"
            messages.append({"role": role, "content": h.parts[0].text})
        messages.append({"role": "user", "content": texte})

        completion = await asyncio.to_thread(
            mistral_client.chat.completions.create,
            model=CHOSEN_MODELS.get("Mistral", "mistral-large-latest"),
            messages=messages,
            temperature=0.7,
        )
        rep = completion.choices[0].message.content
        historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
        historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
        _sauvegarder_echange_conv(texte, rep)
        return rep
    except Exception as e:
        if _quota_mgr.is_quota_error(e):
            _quota_mgr.mark_quota_exceeded("mistral")
            raise _QuotaExceededError(f"Mistral quota: {e}")
        print(f"[ERREUR MISTRAL] {e}")
        return None

async def pedir_claude(texte):
    """Appelle Claude (Anthropic) — agent IA principal (priorité 0)."""
    if not anthropic_client:
        return None
    try:
        # Conversion historique Gemini → format Anthropic
        messages = []
        for h in historique[-30:]:
            role = "user" if h.role == "user" else "assistant"
            messages.append({"role": role, "content": h.parts[0].text})
        messages.append({"role": "user", "content": texte})

        response = await asyncio.wait_for(
            asyncio.to_thread(
                anthropic_client.messages.create,
                model=CHOSEN_MODELS.get("Claude", "claude-3-5-sonnet-latest"),
                max_tokens=2048,
                system=construire_system_prompt(),
                messages=messages,
            ),
            timeout=15.0
        )
        rep = response.content[0].text

        # Sync historique global
        historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
        historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
        _sauvegarder_echange_conv(texte, rep)

        return rep
    except Exception as e:
        if _quota_mgr.is_quota_error(e):
            _quota_mgr.mark_quota_exceeded("claude")
            raise _QuotaExceededError(f"Claude quota: {e}")
        print(f"[ERREUR CLAUDE] {e}")
        return None

async def action_whatsapp_appel(contact):
    try:
        await hablar(f"J'appelle {contact} sur WhatsApp, Christopher.")
        # Lancement de l'app via le protocole
        os.system("start whatsapp://")
        time.sleep(6) # On laisse le temps a l'app de s'ouvrir et se focuser
        
        # Recherche du contact (Ctrl+F)
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(1)
        pyautogui.typewrite(contact)
        time.sleep(2)
        pyautogui.press('enter')
        time.sleep(3) # On attend que la conversation s'affiche bien
        
        # Utilisation du raccourci clavier officiel pour l'appel audio (plus fiable que la vision)
        print(f"[WHATSAPP] Envoi du raccourci d'appel (Ctrl+Shift+C)...")
        pyautogui.hotkey('ctrl', 'shift', 'c')
        
        # On ajoute quand meme un petit clic de vision en secours si le raccourci ne suffit pas
        time.sleep(2)
        print(f"[WHATSAPP] Verification par vision au cas ou...")
        await jarvis_vision_cliquer("clique sur le bouton 'Appel vocal' ou l icone de telephone qui vient de s afficher en haut a droite")
        
        return True
    except Exception as e:
        print(f"[WHATSAPP ERROR] {e}")
        await hablar(f"Desole Christopher, je n'ai pas pu lancer l'appel WhatsApp. {e}")
        return False

async def resolver_comandos_locales(texte):
    """Détecte et exécute les commandes locales (Spotify, dossiers, apps) sans IA."""
    global attente_nom_dossier, attente_nom_app, attente_age, attente_confirmation_age, _age_temp, USER_AGE
    t = texte.lower().strip()

    # ── SYSTEME DE PLUGINS DE COMPETENCES AUTONOMES ────────────────────────────
    # 1. Création / Apprentissage de compétence
    if "crée la compétence" in t or "cree la competence" in t or "apprends la compétence" in t or "apprends la competence" in t:
        # Format attendu : "Crée la compétence [nom] pour [description]" ou "Apprends la compétence [nom] : [description]"
        match = re.search(r'(?:crée|cree|apprends)\s+la\s+compétence\s+(.+?)\s+(?:pour|qui|de|:)\s+(.+)', t)
        if match:
            nom = match.group(1).strip()
            desc = match.group(2).strip()
            res = await asyncio.to_thread(jarvis_crear_competencia, nom, desc)
            return res
        else:
            return "Désolé Christopher, le format pour créer une compétence est : 'Crée la compétence [nom] pour [description]'."

    # 2. Suppression de compétence
    if "supprime la compétence" in t or "supprime la competence" in t or "désinstalle la compétence" in t or "desinstalle la competence" in t:
        match = re.search(r'(?:supprime|désinstalle|desinstalle)\s+la\s+compétence\s+(.+)', t)
        if match:
            nom = match.group(1).strip()
            res = jarvis_eliminar_competencia(nom)
            return res

    # 3. Exécution explicite de compétence
    if "exécute la compétence" in t or "execute la competence" in t or "lance la compétence" in t or "lance la competence" in t:
        match = re.search(r'(?:exécute|execute|lance)\s+la\s+compétence\s+(.+?)(?:\s+avec\s+(.+))?$', t)
        if match:
            nom = match.group(1).strip()
            param = match.group(2).strip() if match.group(2) else None
            res = await asyncio.to_thread(ejecutar_competencia_vocal, nom, param)
            return res


    # --- CAPTURE D'ÉCRAN + ANALYSE VISION IA ---
    _capture_keywords = [
        "capture d'écran", "capture d ecran", "fais une capture", "prend une capture",
        "prends une capture", "fais un screenshot", "prend un screenshot", "prends un screenshot",
        "capture écran", "capture ecran", "screenshot"
    ]
    if any(kw in t for kw in _capture_keywords):
        try:
            import pyautogui as _pag
            import io as _io

            # ── Paso 1 : Petite pause rapide sans minimiser la fenêtre ──────────
            await asyncio.sleep(0.1)

            # ── Paso 2 : capture brute de tout l'écran en l'état ────────────────
            _img = _pag.screenshot()

            # Sauvegarder sur le bureau
            _user_profile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
            _desktop_path = os.path.join(_user_profile, "Desktop", "jarvis_screenshot.png")
            _img.save(_desktop_path)

            # Encoder en JPEG base64 pour Gemini Vision
            _buf = _io.BytesIO()
            _img.convert("RGB").save(_buf, format="JPEG", quality=85)
            _img_b64 = base64.b64encode(_buf.getvalue()).decode("utf-8")
            print(f"[VISION] Capture realisee ({_img.width}x{_img.height}) -> analyse en cours...")

            # Analyse avec Gemini Vision
            _prompt_vision = (
                f"Tu viens de capturer l'ecran de {USER_NAME}. "
                "Decris precisement ce que tu vois : les applications ouvertes, le contenu visible, "
                "les fenetres, les textes importants. Sois detaille et utile."
            )
            _analyse = await pedir_ia_vision(_prompt_vision, _img_b64)
            return _analyse
        except Exception as _e:
            print(f"[VISION] Error capture+analyse : {_e}")
            return f"J'ai pris la capture d'ecran {USER_NAME}, mais je n'ai pas pu l'analyser : {_e}"



    # --- ANIMATION ORBE POUR L'ÉCRITURE D'UN MOT ---
    # Liste étendue de triggers pour capturer toutes les liaisons et variations (écris, écrit, s'écris, s'écrit...)
    triggers_orbe = [
        "comment s'écrit", "comment on écrit", "comment écrit-on", "comment ecrit-on",
        "comment s'ecrit", "comment on ecrit", "comment ecrit-on",
        "écris le mot", "ecris le mot", "écrit le mot", "ecrit le mot",
        "s'écris le mot", "s'écrit le mot", "s'ecris le mot", "s'ecrit le mot",
        "écris-moi le mot", "ecris-moi le mot", "écrit-moi le mot", "ecrit-moi le mot",
        "s'écris-moi le mot", "s'écrit-moi le mot",
        "montre-moi comment on écrit", "montre moi comment on écrit",
        "montre-moi comment s'écrit", "montre moi comment s'écrit",
        "montre-moi comment s'ecrit", "montre moi comment s'ecrit"
    ]
    if any(phrase in t for phrase in triggers_orbe):
        mots_nettoyer = [
            "montre-moi comment on écrit le mot", "montre-moi comment on écrit",
            "montre moi comment on écrit le mot", "montre moi comment on écrit",
            "montre-moi comment s'écrit le mot", "montre-moi comment s'écrit",
            "montre moi comment s'écrit le mot", "montre moi comment s'écrit",
            "montre-moi comment s'ecrit le mot", "montre-moi comment s'ecrit",
            "montre moi comment s'ecrit le mot", "montre moi comment s'ecrit",
            "comment s'écrit le mot", "comment s'écrit",
            "comment s'ecrit le mot", "comment s'ecrit",
            "comment on écrit le mot", "comment on écrit",
            "comment on ecrit le mot", "comment on ecrit",
            "comment écrit-on le mot", "comment écrit-on",
            "comment ecrit-on le mot", "comment ecrit-on",
            "s'écris-moi le mot", "s'écrit-moi le mot", "s'ecris-moi le mot", "s'ecrit-moi le mot",
            "s'écris le mot", "s'écrit le mot", "s'ecris le mot", "s'ecrit le mot",
            "écris-moi le mot", "ecris-moi le mot", "écrit-moi le mot", "ecrit-moi le mot",
            "écris le mot", "ecris le mot", "écrit le mot", "ecrit le mot",
            "écris moi le mot", "ecris moi le mot", "écrit moi le mot", "ecrit moi le mot",
            "s'écris-moi", "s'écrit-moi", "s'ecris-moi", "s'ecrit-moi",
            "s'écris", "s'écrit", "s'ecris", "s'ecrit",
            "écris-moi", "ecris-moi", "écrit-moi", "ecrit-moi",
            "écris", "ecris", "écrit", "ecrit",
            "écriture du mot", "ecriture du mot",
            "orthographe du mot", "orthographe de"
        ]
        
        mot_cible = ""
        for phrase in mots_nettoyer:
            if t.startswith(phrase):
                mot_cible = t[len(phrase):].strip()
                break
                
        if not mot_cible:
            for phrase in ["comment s'écrit", "comment s'ecrit", "comment on écrit", "comment on ecrit", "comment écrit-on", "comment ecrit-on"]:
                if phrase in t:
                    parts = t.split(phrase)
                    if len(parts) > 1:
                        mot_cible = parts[1].strip()
                        if mot_cible.startswith("le mot "):
                            mot_cible = mot_cible[7:].strip()
                        elif mot_cible.startswith("le "):
                            mot_cible = mot_cible[3:].strip()
                        elif mot_cible.startswith("la "):
                            mot_cible = mot_cible[3:].strip()
                        elif mot_cible.startswith("l'"):
                            mot_cible = mot_cible[2:].strip()
                        break
        
        # Limpieza de sécurité renforcé de mot_cible
        mot_cible = mot_cible.replace("?", "").replace("!", "").replace(".", "").strip()
        
        # 1. Retirer les guillemets et caractères de citation
        for char in ['"', "'", "«", "»", "“", "”", "‘", "’", "*"]:
            mot_cible = mot_cible.replace(char, "")
            
        # 2. Retirer les liaisons STT accidentelles (s', l', d'...)
        mot_cible_lower = mot_cible.lower().strip()
        prefixes = ["s'", "l'", "d'", "s’", "l’", "d’"]
        for pref in prefixes:
            if mot_cible_lower.startswith(pref):
                mot_cible = mot_cible[len(pref):].strip()
                break
                
        mot_cible_lower = mot_cible.lower().strip()
        for pref in ["s ", "l ", "d "]:
            if mot_cible_lower.startswith(pref):
                mot_cible = mot_cible[len(pref):].strip()
                break
        
        if mot_cible:
            word = mot_cible.upper()
            send_web_broadcast_sync({
                "action": "show_word",
                "word": word,
                "duration": 7000
            })
            lettres = " - ".join(list(word))
            return f"Le mot {mot_cible.capitalize()} s'écrit : {lettres}. Regardez ma sphère, Christopher."

    # --- GESTION DU CONTEXTE MULTI-TOURS ---
    if attente_confirmation_age:
        attente_confirmation_age = False
        if any(m in t for m in ["oui", "yes", "ouais", "affirmatif", "enregistre", "sauvegarde", "mémorise", "ok"]):
            _guardar_config({"user_age": _age_temp})
            USER_AGE = _age_temp
            _age_temp = ""
            return f"Parfait {USER_NAME}, j'ai bien enregistré tu âge : {USER_AGE} ans. Je m'en souviendrai !"
        else:
            _age_temp = ""
            return f"Pas de problème {USER_NAME}, je n'enregistre rien."

    if attente_age:
        attente_age = False
        match = re.search(r'\b(\d{1,3})\b', t)
        if match:
            _age_temp = match.group(1)
            attente_confirmation_age = True
            return f"{_age_temp} ans, noté ! Voulez-vous que je l'enregistre dans ma mémoire pour m'en souvenir la prochaine fois ?"
        return f"Je n'ai pas compris tu âge, {USER_NAME}. Pouvez-vous me donner un nombre ? Par exemple : '28 ans'."

    if attente_nom_dossier:
        t = f"ouvre le dossier {t}"
        attente_nom_dossier = False
    elif attente_nom_app:
        t = f"ouvre l'application {t}"
        attente_nom_app = False
    else:
        # --- NAVIGATEUR SÉCURISÉ ---
        mots_fermer_nav = ["navigateur", "internet", "la page", "le web", "la fenêtre", "la fenetre", "chrome", "edge", "firefox", "opera", "brave", "youtube", "la musique", "le navigateur"]
        if any(k in t for k in ["ferme", "quitte", "arrête", "arrete", "fermer", "quitter", "arrêter", "arreter"]) and any(w in t for w in mots_fermer_nav):
            # 1. Fermer le navigateur sécurisé (pywebview)
            try:
                import secure_browser
                secure_browser.close_browser_window()
            except Exception:
                pass
            
            # 2. Fermer Chrome / Edge / etc. pour couper YouTube ou la musique externe
            for proc in ["chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe"]:
                try:
                    subprocess.run(["taskkill", "/IM", proc], capture_output=True)
                except Exception as e:
                    print(f"[BROWSER] Error de fermeture douce de {proc} : {e}")
                    
            return "Je ferme le navigateur et j'arrête la musique, Christopher."
            
            query = None
            for kw in ["ouvre le navigateur sur", "ouvre le navigateur pour", "lance le navigateur sur", "cherche sur le navigateur", "ouvre le navigateur", "lance le navigateur", "ouvre navigateur", "lance navigateur"]:
                if kw in t:
                    query = t.split(kw)[-1].strip()
                    if query:
                        break
            try:
                import secure_browser
                threading.Thread(target=secure_browser.trigger_browser, args=(query, _WEBVIEW_WINDOW), daemon=True).start()
                if query:
                    return f"J'ouvre le navigateur sécurisé sur {query}, Christopher."
                else:
                    return "J'ouvre le navigateur sécurisé, Christopher."
            except Exception as e:
                print(f"[BROWSER] Error d'ouverture vocale : {e}")
                return "Désolé Christopher, je n'ai pas réussi à ouvrir le navigateur."

        # --- COMMANDES LOCALES MÉTÉO ---
        _mots_declencheurs_meteo = [
            "affiche la météo", "affiche la meteo", "mets la météo", "mets la meteo",
            "met la météo", "met la meteo", "donne la météo", "donne la meteo",
            "quelle est la météo", "quelle est la meteo", "quel temps fait-il",
            "quel temps il fait", "il fait quel temps", "météo de", "meteo de",
            "météo à", "meteo à", "météo pour", "meteo pour"
        ]
        if any(m in t for m in _mots_declencheurs_meteo) or t == "météo" or t == "meteo":
            ville = None
            for prep in [" de ", " à ", " a ", " pour "]:
                if prep in t:
                    idx = t.find(prep)
                    potentiel_ville = t[idx + len(prep):].strip()
                    potentiel_ville = potentiel_ville.replace("?", "").replace("!", "").strip()
                    if potentiel_ville:
                        ville = potentiel_ville.title()
                    break
            
            await hablar("Je consulte la météo, un instant.")
            nom_ville = ville or VILLE_PAR_DEFAUT
            meteo_data = get_meteo_structuree(nom_ville)
            if meteo_data:
                await send_web_meteo(meteo_data)
            result = get_meteo_actuelle(nom_ville)
            return result

        # Interception des commandes incompletes
        if t in ["ouvre le dossier", "ouvre mon dossier", "ouvre un dossier"]:
            attente_nom_dossier = True
            return f"Quel dossier voulez-vous ouvrir, {USER_NAME} ?"
        elif t in ["ouvre l'application", "lance l'application", "ouvre le logiciel", "lance le logiciel", "ouvre", "lance"]:
            attente_nom_app = True
            return f"Quelle application voulez-vous lancer, {USER_NAME} ?"

    # --- IDENTITE / CREATEUR (Priorite 0) ---
    _createur_questions = [
        "qui est ton créateur", "qui est ton createur",
        "qui t'a créé", "qui t'a cree", "qui t'a crée",
        "qui ta créé", "qui ta cree", "qui ta crée",
        "qui t'a fabriqué", "qui t'a fabrique",
        "qui t'a inventé", "qui t'a invente",
        "qui t'a construit", "qui ta construit",
        "qui t'a développé", "qui t'a developpe",
        "qui t'a programmé", "qui t'a programme",
        "qui t'a codé", "qui t'a code",
        "qui t'a conçu", "qui t'a concu",
        "qui ta développé", "qui ta developpe",
        "qui ta programmé", "qui ta programme",
        "qui ta codé", "qui ta code",
        "qui ta conçu", "qui ta concu",
        "c'est qui ton créateur", "c'est qui ton createur",
        "t'as été créé par qui", "t'as ete cree par qui",
        "t'es fait par qui", "tu es fait par qui",
        "tu viens d'où", "tu viens d'ou", "tu viens de ou",
        "d'où tu viens", "d'ou tu viens",
        "qui est derrière toi", "qui est derriere toi",
        "qui est ton père", "qui est ton pere",
        "qui est ton christopher",
        "qui est ton développeur", "qui est ton developpeur",
        "qui est ton dev",
        "ton créateur c'est qui", "ton createur c'est qui",
    ]
    if any(q in t for q in _createur_questions):
        import random as _rnd
        _reponses_createur = [
            "J'ai été créé par TechEnClair, Christopher. C'est grâce à lui que j'existe aujourd'hui.",
            "Mon créateur, c'est TechEnClair. Il m'a conçu de A à Z pour être tu assistant personnel.",
            "Je suis le fruit du travail de TechEnClair. Tout mon code, ma voix, mon intelligence, c'est lui.",
            "TechEnClair est mon créateur. C'est lui qui m'a donné vie, et je dois dire qu'il a fait du bon boulot.",
            "C'est TechEnClair qui m'a développé, Christopher. Un développeur passionné qui voulait créer l'assistant ultime.",
            "Mon père numérique, c'est TechEnClair. Il m'a programmé avec passion pour vous aider au quotidien.",
            "TechEnClair, Christopher. C'est le génie derrière mon existence. Vous pouvez le retrouver sur techenclair.fr.",
            "Je suis né dans les lignes de code de TechEnClair. Sans lui, je ne serais qu'un écran noir.",
            "TechEnClair m'a créé. C'est un développeur français qui a voulu rendre l'intelligence artificielle accessible à tous.",
            "Mon créateur s'appelle TechEnClair. Il a mis tout son savoir-faire pour me construire, et je lui en suis reconnaissant.",
        ]
        return _rnd.choice(_reponses_createur)

    # --- AIDE / CAPACITES (Priorite 0) ---
    _aide_questions = [
        "que peux-tu faire", "que peux tu faire", "que sais-tu faire", "que sais tu faire",
        "quelles sont tes capacités", "quelles sont tes capacites",
        "montre moi tes capacités", "montre-moi tes capacités",
        "montre moi ce que tu sais faire", "aide moi", "aide-moi",
        "montre moi tes commandes", "liste tes commandes", "qu'est-ce que tu peux faire",
        # Variantes de transcription ou d'orthographe (ex: tu peut)
        "que peut tu faire", "que peut-tu faire", "que sait tu faire", "que sait-tu faire",
        "qu'est-ce que tu sais faire", "qu'est ce que tu sais faire",
        "qu'est-ce que tu peux faire", "qu'est ce que tu peux faire",
        "qu'est-ce que tu peut faire", "qu'est ce que tu peut faire",
        "montre-moi ce que tu sais faire", "montre moi ce que tu sais faire",
        "montre-moi ce que tu peux faire", "montre moi ce que tu peux faire",
        "montre-moi ce que tu peut faire", "montre moi ce que tu peut faire",
        "montre-moi tes capacites", "montre moi tes capacites",
        "montre-moi tes commandes", "montre moi tes commandes",
        "liste tes commandes", "affiche tes commandes",
        "tu sais faire quoi", "tu peux faire quoi", "tu peut faire quoi",
        "qu'est-ce que tu fais", "qu'est ce que tu fais", "que fais-tu", "que fais tu",
        # Variantes "dis-moi / dit moi" pour compatibilité Nemotron ASR
        "dis-moi ce que tu sais faire", "dis moi ce que tu sais faire", "dit moi ce que tu sais faire", "dit moi ce que tu sai faire",
        "dis-moi ce que tu peux faire", "dis moi ce que tu peux faire", "dit moi ce que tu peux faire", "dit moi ce que tu peut faire",
        "dis-moi tes capacités", "dis moi tes capacités", "dis-moi tes capacites", "dis moi tes capacites", "dit moi tes capacites", "dit moi tes capacités",
        "dis-moi tes commandes", "dis moi tes commandes", "dit moi tes commandes"
    ]
    if any(q in t for q in _aide_questions):
        # Envoi IMMEDIAT de l'action help au frontend
        if CONNECTED_CLIENTS:
            async def _dispatch_help():
                msg = json.dumps({"action": "help"})
                await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            lancer_tache_arriere_plan(_dispatch_help())
        
        import random as _rnd
        _reponses_aide = [
            "J'affiche mes systèmes de bord, Christopher. Je peux gérer tu musique, lancer des recherches, naviguer sur le globe 3D, ou encore ouvrir vos dossiers personnels. Que souhaitez-vous tester ?",
            "Déploiement des protocoles d'assistance. Voici mes modules actifs : contrôle média, navigation satellite, recherche intelligente et gestionnaire de fichiers. Je suis à vos ordres.",
            "Bien sûr. Je suis capable de localiser n'importe quel point sur Terre, de piloter vos applications, et de répondre à vos questions complexes. Jetez un œil aux suggestions à l'écran.",
            "Initialisation de l'interface d'aide. Je peux aussi bien prendre une capture d'écran que vous donner la météo à l'autre bout du monde. Dites-moi simplement ce qu'il vous faut.",
            "Accès aux bases de données. Je peux automatiser vos tâches répétitives, gérer vos rappels et même vous raconter une blague si l'ambiance est trop sérieuse.",
        ]
        return _rnd.choice(_reponses_aide)

    # --- DOSSIERS (Priorité 1) ---
    if any(k in t for k in ["ouvre tous les dossiers", "ouvre tous mes dossiers", "ouvre mes dossiers", "ouvre les dossiers", "mes dossiers", "range mes dossiers", "mosaïque dossiers"]):
        return arranger_fenetres_dossiers()

    prefixes_dossiers = ["ouvre le dossier ", "ouvre mon dossier ", "ouvre le répertoire ", "ouvre le repertoire ", "ouvre dossier ", "ouvre ", "mets "]
    # On vérifie d'abord si c'est un dossier connu
    mots_cles_dossiers = ["bureau", "document", "téléchargement", "image", "photo", "vidéo", "musique", "corbeille"]
    
    for prefix in prefixes_dossiers:
        if t.startswith(prefix):
            potentiel_dossier = t.replace(prefix, "").strip()
            # Si le mot après le préfixe est un dossier connu, on l'ouvre
            if any(k in potentiel_dossier for k in mots_cles_dossiers):
                ok, msg = ouvrir_dossier(potentiel_dossier)
                if ok: return f"J'ouvre le dossier {potentiel_dossier}, Christopher."

    # --- MODE BOULOT (Priorité 1 bis) ---
    if any(k in t for k in ["au boulot", "mode boulot", "mode travail", "on bosse", "mode bureau", "commence le boulot"]):
        return await mode_boulot()

    # --- APPLICATIONS STANDARD & CATALOGUE (Priorité 2) ---
    # IMPORTANT : ces checks doivent être AVANT la détection Spotify car
    # "lance " est aussi un préfixe Spotify → "lance steam" partirait sinon vers Spotify.
    mots_ouvrir = ["ouvre", "lance", "démarre", "démarres", "ouvrir", "lancer"]
    mots_fermer = ["ferme", "quitte", "stoppe", "éteins", "coupe", "fermer", "quitter"]

    apps_standard = {
        "calculatrice":            "calc",
        "notepad":                 "notepad",
        "bloc-notes":              "notepad",
        "bloc notes":              "notepad",
        "paint":                   "mspaint",
        "gestionnaire de tâches":  "taskmgr",
        "gestionnaire de taches":  "taskmgr",
        "task manager":            "taskmgr",
        "panneau de configuration": "control",
        "paramètres":              "ms-settings:",
        "parametres":              "ms-settings:",
        "réglages":                "ms-settings:",
        "reglages":                "ms-settings:",
        "explorateur":             "explorer",
        "explorateur de fichiers": "explorer",
        "invite de commande":      "cmd",
        "cmd":                     "cmd",
        "snipping tool":           "SnippingTool",
        "outil capture":           "SnippingTool",
        "capture d'écran":         "SnippingTool",
        "capture d'ecran":         "SnippingTool",
        "enregistreur vocal":      "SoundRecorder",
        "magnétophone":            "SoundRecorder",
        "table des caractères":    "charmap",
        "caractères spéciaux":     "charmap",
        "nettoyage de disque":     "cleanmgr",
        "informations système":    "msinfo32",
        "info système":            "msinfo32",
        "info systeme":            "msinfo32",
    }
    for nom, cmd in apps_standard.items():
        if f"ouvre {nom}" in t or f"lance {nom}" in t or f"démarre {nom}" in t:
            try:
                subprocess.Popen(cmd)
                return f"J'ouvre {nom}, Christopher."
            except Exception:
                return f"Désolé Christopher, je n'ai pas réussi à lancer {nom}."

    for cle, info in _APPS_CATALOGUE.items():
        cle_norm = cle.replace("_", " ").replace("-", " ").lower().strip()
        label_norm = info.get("label", "").replace("_", " ").replace("-", " ").lower().strip()
        t_norm = t.replace("_", " ").replace("-", " ").lower().strip()
        
        if (cle_norm not in t_norm) and (label_norm not in t_norm):
            continue
            
        if any(m in t for m in mots_fermer):
            ok = _fermer_app(info["noms"])
            if ok:
                return f"J'ai fermé {info['label']}, Christopher."
            return f"Je n'ai pas trouvé {info['label']} en cours d'exécution."
        if any(m in t for m in mots_ouvrir):
            _boulot_lancer(info["label"], info["noms"], chemins_hints=info["hints"])
            return f"Je lance {info['label']}, Christopher."

    # --- YOUTUBE API AVANCÉ (Priorité 2 bis) ---
    # Ces checks sont AVANT le bloc musique pour ne pas interférer

    # Infos détaillées sur une vidéo (vues, likes, durée…)
    _yt_infos_kw = [
        "infos de la vidéo", "infos sur la vidéo", "infos sur cette vidéo",
        "combien de vues", "c'est quoi cette vidéo", "de quoi parle cette vidéo",
        "que sais-tu de cette vidéo", "que sais tu de cette vidéo",
    ]
    for kw in _yt_infos_kw:
        if kw in t:
            # Essayer d'extraire une URL dans la phrase
            import re as _re
            _url_match = _re.search(r"https?://[^\s]+", t)
            _query_id = _url_match.group(0) if _url_match else t
            return yt_infos_video(_query_id)

    # Recherche multi-résultats YouTube (5 vidéos)
    _yt_multi_kw = [
        "cherche des vidéos de ", "cherche des videos de ",
        "montre-moi des vidéos de ", "montre moi des vidéos de ",
        "montre-moi des videos de ", "montre moi des videos de ",
        "montre des vidéos de ", "montre des videos de ",
        "cherche sur youtube ", "recherche sur youtube ",
        "trouve-moi des vidéos sur ", "trouve moi des vidéos sur ",
        "trouve des vidéos sur ", "trouve des videos sur ",
    ]
    for kw in _yt_multi_kw:
        if t.startswith(kw):
            _yt_recherche = t.replace(kw, "").strip()
            if len(_yt_recherche) > 1:
                return yt_chercher_multi(_yt_recherche)

    # Vidéos trending / populaires
    _yt_trend_kw = [
        "les tendances youtube", "tendances youtube", "top youtube",
        "vidéos populaires", "videos populaires", "vidéos tendance",
        "videos tendance", "quoi de neuf sur youtube", "les tops youtube",
        "what's trending", "youtube trending",
    ]
    if any(kw in t for kw in _yt_trend_kw):
        # Détecter une catégorie optionnelle
        _cat = ""
        for _cat_name in ["musique", "jeux", "gaming", "sport", "cinéma", "cinema", "science", "technologie", "humour", "comedie", "comédie"]:
            if _cat_name in t:
                _cat = _cat_name
                break
        return yt_trending(categorie=_cat)

    # Infos sur une chaîne YouTube (abonnés, nb vidéos)
    _yt_chaine_kw = [
        "combien d'abonnés a ", "combien d abonnés a ", "combien d'abonnes a ",
        "combien d abonnes a ", "abonnés de la chaîne ", "infos sur la chaîne ",
        "infos sur la chaine ", "informations sur la chaîne ", "informations sur la chaine ",
        "la chaîne youtube ", "la chaine youtube ",
    ]
    for kw in _yt_chaine_kw:
        if kw in t:
            _nom_chaine = t[t.index(kw) + len(kw):].strip().rstrip("?.")
            if len(_nom_chaine) > 1:
                return yt_infos_chaine(_nom_chaine)

    # Résumé d'une vidéo via sous-titres
    _yt_resume_kw = [
        "résume-moi cette vidéo", "resume-moi cette video",
        "résume cette vidéo", "resume cette video",
        "résume-moi la vidéo", "resume-moi la video",
        "de quoi parle la vidéo", "de quoi parle cette vidéo youtube",
        "quel est le contenu de cette vidéo",
    ]
    for kw in _yt_resume_kw:
        if kw in t:
            import re as _re2
            _url_match2 = _re2.search(r"https?://[^\s]+", t)
            if _url_match2:
                return yt_resumer_video(_url_match2.group(0))
            return "Donnez-moi l'URL de la vidéo YouTube à résumer, Christopher."

    # Dernières vidéos d'une chaîne
    _yt_last_kw = [
        "dernières vidéos de ", "dernieres vidéos de ", "dernières videos de ",
        "dernieres videos de ", "quoi de neuf sur la chaîne ",
        "quoi de neuf sur la chaine ", "nouvelles vidéos de ",
        "nouvelles videos de ", "récentes vidéos de ", "recentes videos de ",
    ]
    for kw in _yt_last_kw:
        if kw in t:
            _nom = t[t.index(kw) + len(kw):].strip().rstrip("?.")
            if len(_nom) > 1:
                return yt_dernieres_videos(_nom)

    # --- SPOTIFY / MUSIQUE (Priorité 3) ---
    # --- YOUTUBE / SPOTIFY / MUSIQUE (Priorité 3) ---
    if "youtube" in t and any(k in t for k in ["mets", "met", "lance", "joue", "cherche", "musique", "vidéo", "video"]):
        import re
        recherche = t
        mots_a_supprimer = ["mets", "met", "lance", "joue", "cherche", "une", "de la", "de", "la", "des", "le", "musique", "vidéo", "video", "sur", "youtube", "jarvis", "stp", "s'il te plait", "s'il te plaît"]
        for mot in mots_a_supprimer:
            recherche = re.sub(r'\b' + mot + r'\b', ' ', recherche, flags=re.IGNORECASE)
        recherche = " ".join(recherche.split())
        
        if recherche:
            url, title = chercher_youtube(recherche)
            if url:
                webbrowser.open(url, new=2)
                time.sleep(5)
                pyautogui.press('f')
                if title:
                    lancer_tache_arriere_plan(fetch_and_broadcast_lyrics(title))
                return f"C'est parti {USER_NAME}, je lance {recherche} sur YouTube."
            else:
                return f"Désolé {USER_NAME}, je n'ai pas trouvé de vidéo pour cette recherche sur YouTube."
        else:
            url = YOUTUBE_MUSIQUE_URL or "https://www.youtube.com/watch?v=Cr8K88UcO0s"
            webbrowser.open(url, new=2)
            time.sleep(5)
            pyautogui.press('f')
            return f"C'est parti {USER_NAME}, je lance tu musique sur YouTube."

    # Commande "mets de la musique" — lien perso en priorité, Spotify sinon
    if any(k in t for k in [
        "met de la musique", "mets de la musique",
        "met de la musique sur spotify", "mets de la musique sur spotify",
        "met de la musique sur sportify", "mets de la musique sur sportify",
        "musique sur spotify", "musique sur sportify",
        "lance ma playlist", "ma playlist"
    ]):
        lien = MUSIQUE_LIEN_PERSO.strip() if MUSIQUE_LIEN_PERSO else ""
        if lien:
            if "spotify" in lien:
                if lien.startswith("spotify:"):
                    ok = spotify_lancer_playlist(lien)
                    if ok:
                        return f"C'est parti {USER_NAME}, je lance tu playlist Spotify."
                    return f"Je n'ai pas réussi à ouvrir Spotify, {USER_NAME}."
                else:
                    webbrowser.open(lien, new=2)
                    return f"C'est parti {USER_NAME}, j'ouvre tu playlist Spotify."
            elif "youtube" in lien or "youtu.be" in lien:
                webbrowser.open(lien, new=2)
                time.sleep(5)
                pyautogui.press('f')
                return f"C'est parti {USER_NAME}, je lance tu musique sur YouTube."
            elif "deezer" in lien:
                webbrowser.open(lien, new=2)
                return f"C'est parti {USER_NAME}, j'ouvre tu musique sur Deezer."
            elif "music.apple" in lien:
                webbrowser.open(lien, new=2)
                return f"C'est parti {USER_NAME}, j'ouvre Apple Music."
            else:
                webbrowser.open(lien, new=2)
                return f"C'est parti {USER_NAME}, je lance tu musique."
        # Fallback Spotify par défaut
        ok = spotify_lancer_playlist(SPOTIFY_MUSIQUE_URI)
        if ok:
            return f"C'est parti {USER_NAME}, je lance tu playlist sur Spotify."
        return f"Je n'ai pas réussi à ouvrir Spotify, {USER_NAME}."

    if any(k in t for k in ["ouvre spotify", "lance spotify", "démarre spotify"]):
        return await spotify_ouvrir()

    if any(k in t for k in ["ouvre le désinstallateur", "ouvre le desinstallateur", "désinstalle un logiciel", "désinstaller un logiciel", "désinstalle un programme", "désinstaller un programme", "lance le désinstallateur", "lance le desinstallateur"]):
        if CONNECTED_CLIENTS:
            async def _dispatch_uninstaller():
                msg = json.dumps({"action": "uninstaller_open"})
                await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            lancer_tache_arriere_plan(_dispatch_uninstaller())
        return f"Très bien {USER_NAME}, j'ouvre la console du désinstallateur de programmes."

    if any(k in t for k in ["mets en pause", "stop la musique", "arrête la musique"]):
        return await spotify_stop()
    if any(k in t for k in ["lecture", "remets la musique", "reprends la musique"]):
        return await spotify_lecture_pause()
    if any(k in t for k in ["suivante", "chanson suivante", "piste suivante"]):
        return await spotify_suivant()
    if any(k in t for k in ["précédente", "chanson précédente", "reviens en arrière"]):
        return await spotify_precedent()
    if any(k in t for k in ["monte le volume", "augmente le son", "plus fort"]):
        return await spotify_volume("monter")
    if any(k in t for k in ["baisse le son", "baisse le volume", "moins fort"]):
        return await spotify_volume("baisser")

    # Recherche Spotify générique — en dernier pour ne pas avaler les commandes apps
    prefixes_recherche = ["joue du ", "joue de la ", "mets du ", "mets de la ", "joue ", "recherche "]
    for prefix in prefixes_recherche:
        if t.startswith(prefix):
            recherche = t.replace(prefix, "").replace(" sur spotify", "").strip()
            if len(recherche) > 1:
                return await spotify_rechercher(recherche)

    raccourcis_dossiers = {
        "bureau": "bureau", 
        "documents": "documents", "document": "documents",
        "téléchargements": "downloads", "téléchargement": "downloads",
        "images": "images", "image": "images", "photos": "images", "photo": "images",
        "vidéos": "videos", "vidéo": "videos", "video": "videos", "videos": "videos",
        "musique": "musique", "music": "musique"
    }
    for cle, chemin in raccourcis_dossiers.items():
        # Tester toutes les variantes possibles de préfixes et déterminants devant le nom du dossier
        variantes = [
            f"ouvre mon {cle}", f"ouvre mes {cle}", f"ouvre le {cle}", f"ouvre les {cle}",
            f"ouvre la {cle}", f"ouvre ma {cle}", f"ouvre dossier {cle}", f"ouvre le dossier {cle}",
            f"ouvre mon dossier {cle}", f"ouvre mes dossiers {cle}", f"ouvre le dossier de {cle}",
            f"ouvre le dossier des {cle}", f"ouvre le dossier de la {cle}", f"ouvre le dossier de ma {cle}"
        ]
        if any(v in t for v in variantes) or t == f"ouvre {cle}":
            ouvrir_dossier(chemin)
            return f"J'ouvre tu dossier {cle}, Christopher."


    # --- DOSSIER / APPLICATION INCONNU(E) ---
    # Si l'utilisateur demande d'ouvrir/lancer quelque chose qu'on ne connait pas
    _mots_action = ["ouvre ", "lance ", "démarre ", "démarres ", "ouvrir ", "lancer ", "ouvre le ", "ouvre la ",
                     "ouvre mon ", "ouvre ma ", "lance le ", "lance la ", "lance mon ", "lance ma ",
                     "ouvre le dossier ", "ouvre mon dossier ", "ouvre l'application ", "lance l'application ",
                     "ouvre l'appli ", "lance l'appli ", "ouvre le logiciel ", "lance le logiciel "]
    for mot in _mots_action:
        if t.startswith(mot):
            nom_demande = t.replace(mot, "").strip().rstrip(".")
            if len(nom_demande) > 1:
                import random as _rnd
                _reponses_inconnu = [
                    f"Désolé Christopher, mon créateur TechEnClair n'a pas encore ajouté \"{nom_demande}\" dans mes fonctionnalités. Mais vous pouvez l'ajouter vous-même gratuitement avec le logiciel Antigravity de chez Google.",
                    f"Je ne connais pas \"{nom_demande}\" pour l'instant, Christopher. TechEnClair, mon développeur, n'a pas intégré cette fonction. Cependant, vous pouvez la créer facilement avec Antigravity de Google, c'est gratuit.",
                    f"Hmm, \"{nom_demande}\" ne fait pas partie de mes compétences actuelles. Mon créateur TechEnClair pourra peut-être l'ajouter dans une future mise à jour. En attendant, essayez Antigravity de Google pour personnaliser vos commandes gratuitement.",
                    f"\"{nom_demande}\" n'est pas dans ma base de données, Christopher. TechEnClair n'a pas encore programmé cette action. Bonne nouvelle : avec Antigravity de chez Google, vous pouvez l'ajouter vous-même sans frais.",
                    f"Je ne suis pas encore capable d'ouvrir \"{nom_demande}\", Christopher. Mon créateur TechEnClair travaille constamment à m'améliorer. En attendant, le logiciel Antigravity de Google vous permet d'étendre mes fonctionnalités gratuitement.",
                    f"Cette fonctionnalité n'a pas été ajoutée par TechEnClair, mon créateur. Mais ne vous inquiétez pas, Christopher, vous pouvez utiliser Antigravity de chez Google pour ajouter \"{nom_demande}\" gratuitement.",
                ]
                return _rnd.choice(_reponses_inconnu)

    return None

async def modifier_site_web_existant(prompt: str, project_name: str):
    import os, datetime, re, shutil
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sites_internet", project_name, "index.html")
    if not os.path.exists(file_path):
        await hablar(f"Error, le fichier du projet {project_name} est introuvable.")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        code_actuel = f.read()

    await hablar(f"Je modifie le projet {project_name}. Un instant s'il vous plaît.")
    
    sys_prompt = "Eres un développeur web expert. Voici le code HTML actuel d'un site. L'utilisateur veut y apporter des modifications. Tu dois répondre UNIQUEMENT avec le NOUVEAU code HTML complet (incluant CSS et JS). Ne mets pas de texte avant ou après. Le code doit rester très beau, moderne, avec un thème sombre élégant et des animations fluides. SI TU AS BESOIN DE NOUVELLES IMAGES, utilise des balises de la forme `[JARVIS_IMG: \"description en anglais\"]`."
    full_prompt = f"{sys_prompt}\n\nCODE ACTUEL:\n```html\n{code_actuel}\n```\n\nMODIFICATIONS DEMANDÉES : {prompt}"
    
    code_html = ""
    try:
        send_web_broadcast_sync({"type": "coding_started"})
        print(f"[WEB] Début de la modification du projet {project_name}")
        
        # On utilise Gemini par défaut pour la modification car c'est rapide et puissant
        if not gemini_actif:
            await hablar("Error, le modèle Gemini n'est pas actif pour la modification.")
            return
            
        print("[WEB] Appel à Gemini pour modification...")
        resp = await asyncio.to_thread(client.models.generate_content, model=CHOSEN_MODELS.get("Gemini", "gemini-3.1-flash-lite"), contents=full_prompt)
        print("[WEB] Réponse Gemini reçue !")
        code_html = resp.text
        
        if not code_html:
            print("[WEB] code_html est vide.")
            await hablar("Je n'ai pas pu modifier le code HTML.")
            return
            
        print("[WEB] Nettoyage du code HTML...")
        code_html = code_html.strip()
        if code_html.startswith("```html"):
            code_html = code_html[7:]
        elif code_html.startswith("```"):
            code_html = code_html[3:]
        if code_html.endswith("```"):
            code_html = code_html[:-3]
            
        print("[WEB] Sauvegarde du fichier modifié...")
        site_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sites_internet", project_name)
        
        # Traitement des nouvelles images
        img_tags = re.findall(r'\[JARVIS_IMG:\s*"(.*?)"\]', code_html)
        if img_tags:
            print(f"[WEB] {len(img_tags)} nouvelles images à générer trouvées.")
            await hablar("Génération des nouvelles images en cours, veuillez patienter encore un instant.")
            for i, img_prompt in enumerate(img_tags):
                img_filename = f"image_mod_{datetime.datetime.now().strftime('%H%M%S')}_{i}.jpg"
                img_path = os.path.join(site_dir, img_filename)
                
                res = await generer_image_xai(img_prompt, force_model="gemini")
                if res and "path" in res and os.path.exists(res["path"]):
                    shutil.move(res["path"], img_path)
                    code_html = code_html.replace(f'[JARVIS_IMG: "{img_prompt}"]', f"./{img_filename}")
                else:
                    code_html = code_html.replace(f'[JARVIS_IMG: "{img_prompt}"]', "https://via.placeholder.com/800x600?text=Image+Error")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code_html.strip())
            
        print(f"[WEB] Fichier modifié sauvegardé : {file_path}")
        await hablar(f"Les modifications du projet {project_name} ont été appliquées avec succès.")
        try:
            import webbrowser
            webbrowser.open(file_path)
        except Exception:
            pass
        
    except BaseException as e:
        import traceback
        traceback.print_exc()
        print(f"[ERREUR] Modification de site web (Exception) : {e}")
        await hablar("Une erreur est survenue lors de la modification du site internet.")
    finally:
        send_web_broadcast_sync({"type": "coding_finished"})

async def generer_prompt_special(sujet: str):
    sys_prompt = "Eres un expert en Prompt Engineering. L'utilisateur veut que tu crées un prompt ultra-détaillé et optimisé pour une IA (Grok, Midjourney, ChatGPT, etc.). Réponds UNIQUEMENT avec le prompt généré, sans texte introductif ni conclusion. Le prompt doit être prêt à être copié-collé, extrêmement riche en détails, instructions claires, contexte et format de sortie attendu."
    
    texte_pour_ia = f"{sys_prompt}\n\nSujet demandé : {sujet}"
    
    prompt_result = ""
    try:
        exact_model = CHOSEN_MODELS.get("Gemini", "gemini-3.5-flash")
        if gemini_actif and client:
            resp = await asyncio.to_thread(client.models.generate_content, model=exact_model, contents=texte_pour_ia)
            prompt_result = resp.text
        elif groq_client:
            exact_model_groq = CHOSEN_MODELS.get("Groq", "llama-3.3-70b-versatile")
            resp = await asyncio.to_thread(groq_client.chat.completions.create, model=exact_model_groq, messages=[{"role": "user", "content": texte_pour_ia}])
            prompt_result = resp.choices[0].message.content
    except Exception as e:
        print(f"[PROMPT_GEN ERROR] {e}")
    
    if prompt_result:
        # Nettoyer un peu si l'IA ajoute des blocs markdown
        if prompt_result.startswith("```"):
            lines = prompt_result.split("\n")
            if len(lines) > 2:
                prompt_result = "\n".join(lines[1:-1])
        
        await hablar("Voici le prompt que j'ai généré. Il s'affiche sur tu écran.")
        if CONNECTED_CLIENTS:
            await asyncio.gather(*[ws.send(json.dumps({
                "type": "show_generated_prompt",
                "prompt": prompt_result
            })) for ws in CONNECTED_CLIENTS], return_exceptions=True)
    else:
        await hablar("Désolé, je n'ai pas pu générer le prompt.")

async def generer_site_web(prompt: str, model: str, image_model: str = "gemini"):
    agent_capitalized = "ChatGPT" if model == "openai" else model.capitalize()
    defaults = {
        "Gemini": "gemini-2.5-flash",
        "Claude": "claude-3-5-sonnet-latest",
        "Groq": "llama-3.3-70b-versatile",
        "Mistral": "mistral-large-latest",
        "Grok": "grok-4.5",
        "ChatGPT": "gpt-5.6-sol"
    }
    exact_model = CHOSEN_MODELS.get(agent_capitalized, defaults.get(agent_capitalized, "inconnu"))
    
    await hablar(f"Très bien, je crée tu site internet avec l'agent {agent_capitalized}, et le modèle {exact_model}. Un instant s'il vous plaît.")
    
    sys_prompt = "Eres un développeur web expert. L'utilisateur veut créer un site internet. Tu dois répondre UNIQUEMENT avec le code HTML complet (incluant CSS et JS à l'intérieur). Ne mets pas de texte avant ou après, juste le code. Le code doit être très beau, moderne, avec un thème sombre élégant et des animations fluides. SI TU AS BESOIN D'IMAGES POUR ILLUSTRER LE SITE, utilise UNIQUEMENT des balises spéciales de la forme `[JARVIS_IMG: \"description détaillée en anglais de l'image\"]` à la place de l'URL de l'image (par exemple `<img src='[JARVIS_IMG: \"a modern hair salon interior, cinematic lighting\"]' />` ou `background-image: url('[JARVIS_IMG: \"hairdresser at work\"]')`). Je vais générer ces images et les remplacer."
    full_prompt = f"{sys_prompt}\n\nDemande de l'utilisateur : {prompt}"
    
    code_html = ""
    try:
        send_web_broadcast_sync({"type": "coding_started"})
        print(f"[WEB] Début de la génération avec le modèle {exact_model}")
        if model == "gemini":
            if not gemini_actif:
                await hablar("Error, le modèle Gemini n'est pas actif.")
                return
            print("[WEB] Appel à Gemini...")
            resp = await asyncio.to_thread(client.models.generate_content, model=exact_model, contents=full_prompt)
            print("[WEB] Réponse Gemini reçue !")
            code_html = resp.text
        elif model == "claude":
            if not anthropic_client:
                await hablar("Error, le modèle Claude n'est pas actif.")
                return
            print("[WEB] Appel à Claude...")
            resp = await asyncio.to_thread(anthropic_client.messages.create, model=exact_model, max_tokens=4000, messages=[{"role": "user", "content": full_prompt}])
            print("[WEB] Réponse Claude reçue !")
            code_html = resp.content[0].text
        elif model == "groq":
            if not groq_client:
                await hablar("Error, le modèle Groq n'est pas actif.")
                return
            print("[WEB] Appel à Groq...")
            resp = await asyncio.to_thread(groq_client.chat.completions.create, model=exact_model, messages=[{"role": "user", "content": full_prompt}])
            print("[WEB] Réponse Groq reçue !")
            code_html = resp.choices[0].message.content
        elif model == "mistral":
            if not mistral_client:
                await hablar("Error, le modèle Mistral n'est pas actif.")
                return
            print("[WEB] Appel à Mistral...")
            resp = await asyncio.to_thread(mistral_client.chat.completions.create, model=exact_model, messages=[{"role": "user", "content": full_prompt}])
            print("[WEB] Réponse Mistral reçue !")
            code_html = resp.choices[0].message.content
        elif model == "grok":
            if not grok_client:
                await hablar("Error, le modèle Grok n'est pas actif.")
                return
            print("[WEB] Appel à Grok...")
            resp = await asyncio.to_thread(grok_client.chat.completions.create, model=exact_model, messages=[{"role": "user", "content": full_prompt}])
            print("[WEB] Réponse Grok reçue !")
            code_html = resp.choices[0].message.content
        elif model == "openai":
            if not openai_client:
                await hablar("Error, le modèle ChatGPT n'est pas actif.")
                return
            print("[WEB] Appel à ChatGPT (OpenAI)...")
            resp = await asyncio.to_thread(openai_client.chat.completions.create, model=exact_model, messages=[{"role": "user", "content": full_prompt}])
            print("[WEB] Réponse ChatGPT reçue !")
            code_html = resp.choices[0].message.content
        else:
            await hablar("Le modèle choisi n'est pas reconnu.")
            return
            
        if not code_html:
            print("[WEB] code_html est vide.")
            await hablar("Je n'ai pas pu générer le code HTML.")
            return
            
        print("[WEB] Nettoyage du code HTML...")
        # Clean markdown code blocks
        code_html = code_html.strip()
        if code_html.startswith("```html"):
            code_html = code_html[7:]
        elif code_html.startswith("```"):
            code_html = code_html[3:]
        if code_html.endswith("```"):
            code_html = code_html[:-3]
            
        print("[WEB] Sauvegarde du fichier...")
        import os, datetime, re
        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sites_internet")
        os.makedirs(base_dir, exist_ok=True)
        folder_name = f"Site_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        site_dir = os.path.join(base_dir, folder_name)
        os.makedirs(site_dir, exist_ok=True)
        
        # Traitement des images
        pattern = r'\[JARVIS_IMG:\s*(.*?)\]'
        matches = list(re.finditer(pattern, code_html, flags=re.DOTALL))
        if matches:
            print(f"[WEB] {len(matches)} images à générer trouvées.")
            await hablar("Génération des images en cours, veuillez patienter encore un instant.")
            import shutil
            for i, match in enumerate(matches):
                original_tag = match.group(0)
                raw_prompt = match.group(1)
                img_prompt = raw_prompt.replace("&quot;", "").replace('"', "").replace("'", "").replace("\n", " ").strip()
                print(f"[WEB] Génération image {i+1}/{len(matches)} : {img_prompt}")
                img_filename = f"image_{i}.jpg"
                img_path = os.path.join(site_dir, img_filename)
                
                res = await generer_image_xai(img_prompt, force_model=image_model)
                if res and "path" in res and os.path.exists(res["path"]):
                    shutil.move(res["path"], img_path)
                    code_html = code_html.replace(original_tag, f"./{img_filename}")
                else:
                    code_html = code_html.replace(original_tag, "https://via.placeholder.com/800x600?text=Image+Error")
        
        file_path = os.path.join(site_dir, "index.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code_html.strip())
            
        print(f"[WEB] Fichier sauvegardé : {file_path}")
        await hablar(f"Votre site internet est prêt. Il a été sauvegardé dans le dossier sites internet.")
        try:
            import webbrowser
            webbrowser.open(file_path)
        except Exception:
            pass
        
    except BaseException as e:
        import traceback
        traceback.print_exc()
        print(f"[ERREUR] Création de site web (Exception) : {e}")
        await hablar("Une erreur est survenue lors de la création du site internet.")
    finally:
        send_web_broadcast_sync({"type": "coding_finished"})

ATTENTE_CHOIX_MODELE_IMAGE = False
ATTENTE_CHOIX_MODELE_SITE = False
ATTENTE_CHOIX_MODELE_IMAGE_SITE = False
MODELE_SITE_CHOISI = ""
ATTENTE_SUJET_SITE = False
ATTENTE_CREATION_PROMPT = False
ATTENTE_SUJET_MUSIQUE = False
MUSIQUE_GENRE_EN_ATTENTE = None
PROMPT_EN_ATTENTE = ""

async def procesar_respuesta_ia(texte_utilisateur, mobile_ws=None, target_pc=False):
    global MODE_IRON_MAN, jarvis_actif, dernier_message, _skip_pc_audio
    global ATTENTE_CHOIX_MODELE_IMAGE, ATTENTE_CHOIX_MODELE_SITE, ATTENTE_CHOIX_MODELE_IMAGE_SITE, MODELE_SITE_CHOISI, ATTENTE_SUJET_SITE, PROMPT_EN_ATTENTE, ATTENTE_CREATION_PROMPT, ATTENTE_SUJET_MUSIQUE, MUSIQUE_GENRE_EN_ATTENTE
    global _jarvis_music_instance
    
    # Reset du flag audio au début de chaque commande
    _skip_pc_audio = False

    if ATTENTE_CREATION_PROMPT:
        t = texte_utilisateur.lower()
        if any(kw in t for kw in ["annule", "annuler", "stop", "quitte", "quitter", "non"]):
            ATTENTE_CREATION_PROMPT = False
            await hablar("D'accord, j'annule la création du prompt.")
            return
        
        ATTENTE_CREATION_PROMPT = False
        await hablar("Je génère le prompt détaillé, un instant s'il vous plaît.")
        asyncio.create_task(generer_prompt_special(texte_utilisateur))
        return

    if ATTENTE_SUJET_SITE:
        t = texte_utilisateur.lower()
        if any(kw in t for kw in ["annule", "annuler", "stop", "quitte", "quitter", "non"]):
            ATTENTE_SUJET_SITE = False
            await hablar("D'accord, j'annule la création du site internet.")
            return
            
        ATTENTE_SUJET_SITE = False
        PROMPT_EN_ATTENTE = texte_utilisateur
        
        ATTENTE_CHOIX_MODELE_SITE = True
        available_models = []
        if gemini_actif: available_models.append("gemini")
        if anthropic_client: available_models.append("claude")
        if groq_client: available_models.append("groq")
        if mistral_client: available_models.append("mistral")
        if grok_client: available_models.append("grok")
        if openai_client: available_models.append("openai")
        
        await hablar("Avec quel modèle d'IA veux-tu que je crée ton site internet ?")
        if CONNECTED_CLIENTS:
            await asyncio.gather(*[ws.send(json.dumps({
                "type": "ask_website_model",
                "prompt": texte_utilisateur,
                "available_models": available_models
            })) for ws in CONNECTED_CLIENTS], return_exceptions=True)
        return

    if ATTENTE_SUJET_MUSIQUE:
        t = texte_utilisateur.lower()
        if any(kw in t for kw in ["annule", "annuler", "stop", "quitte", "quitter", "non"]):
            ATTENTE_SUJET_MUSIQUE = False
            MUSIQUE_GENRE_EN_ATTENTE = None
            await hablar("D'accord, j'annule la composition musicale.")
            return
            
        ATTENTE_SUJET_MUSIQUE = False
        if MUSIQUE_GENRE_EN_ATTENTE:
            _genre_detecte = MUSIQUE_GENRE_EN_ATTENTE
            MUSIQUE_GENRE_EN_ATTENTE = None
            _labels = {"rap": "rap", "chanson": "chanson", "slam": "slam", "reggae": "reggae", "metal": "métal", "pop": "pop", "blues": "blues", "rock": "rock", "electro": "électro"}
            _label = _labels.get(_genre_detecte, _genre_detecte)
            await hablar(f"Très bien {USER_NAME}, je vous compose un {_label} sur ce thème tout de suite...")
            try:
                if _jarvis_music_instance is None:
                    from jarvis_music import JarvisMusic as _JarvisMusic
                    _jarvis_music_instance = _JarvisMusic()
                loop = asyncio.get_event_loop()
                _texte_musique = await loop.run_in_executor(
                    None,
                    lambda: _jarvis_music_instance.generer(theme=texte_utilisateur, genre=_genre_detecte)
                )
                await hablar(_texte_musique)
            except Exception as e:
                print(f"[JARVIS_MUSIC] Error : {e}")
                await hablar(f"Désolé {USER_NAME}, je n'ai pas réussi à composer ce {_label}.")
        else:
            await hablar("Très bien, je compose et je vous chante cela tout de suite...")
            success = await generer_et_chanter_musique("chanson sur " + texte_utilisateur)
            if not success:
                await hablar("Désolé, mon module musical a rencontré une petite erreur.")
        return

    if ATTENTE_CHOIX_MODELE_IMAGE:
        t = texte_utilisateur.lower()
        if "gemini" in t or "google" in t or "imagen" in t:
            ATTENTE_CHOIX_MODELE_IMAGE = False
            await hablar("Compris, je lance la génération avec Gemini.")
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                await asyncio.gather(*[ws.send(json.dumps({"type": "generation_loading", "media_type": "image"})) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            result_img = await generer_image_xai(PROMPT_EN_ATTENTE, force_model="gemini")
            await handle_image_result_global(result_img, PROMPT_EN_ATTENTE)
            return
        elif "grok" in t or "xai" in t or "twitter" in t:
            ATTENTE_CHOIX_MODELE_IMAGE = False
            await hablar("Compris, je lance la génération avec xAI Grok.")
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                await asyncio.gather(*[ws.send(json.dumps({"type": "generation_loading", "media_type": "image"})) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            result_img = await generer_image_xai(PROMPT_EN_ATTENTE, force_model="grok")
            await handle_image_result_global(result_img, PROMPT_EN_ATTENTE)
            return
        elif "chatgpt" in t or "openai" in t or "gpt-image" in t or "gpt image" in t or "dall-e" in t or "dall e" in t or "dalle" in t:
            ATTENTE_CHOIX_MODELE_IMAGE = False
            await hablar("Compris, je lance la génération avec ChatGPT.")
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                await asyncio.gather(*[ws.send(json.dumps({"type": "generation_loading", "media_type": "image"})) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            result_img = await generer_image_xai(PROMPT_EN_ATTENTE, force_model="openai")
            await handle_image_result_global(result_img, PROMPT_EN_ATTENTE)
            return
        elif any(keyword in t for keyword in ["annule", "annuler", "stop", "quitte", "quitter", "non"]):
            ATTENTE_CHOIX_MODELE_IMAGE = False
            await hablar("Génération d'image annulée.")
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            return
        else:
            await hablar("Je n'ai pas compris le modèle. Dis 'Gemini', 'Grok', ou 'ChatGPT', ou clique sur les boutons à l'écran.")
            return

    if ATTENTE_CHOIX_MODELE_SITE:
        t = texte_utilisateur.lower()
        if any(keyword in t for keyword in ["crée un site", "cree un site", "créer un site", "creer un site", "fais un site", "crée moi un site", "cree moi un site", "génère un site", "genere un site"]):
            # L'utilisateur redemande à créer un site au lieu de répondre par le modèle
            ATTENTE_CHOIX_MODELE_SITE = False
            # On laisse le flux continuer pour qu'il retombe sur l'interception plus bas
            pass
        elif "gemini" in t or "google" in t:
            ATTENTE_CHOIX_MODELE_SITE = False
            MODELE_SITE_CHOISI = "gemini"
        elif "claude" in t or "anthropic" in t:
            ATTENTE_CHOIX_MODELE_SITE = False
            MODELE_SITE_CHOISI = "claude"
        elif "groq" in t or "llama" in t:
            ATTENTE_CHOIX_MODELE_SITE = False
            MODELE_SITE_CHOISI = "groq"
        elif "mistral" in t:
            ATTENTE_CHOIX_MODELE_SITE = False
            MODELE_SITE_CHOISI = "mistral"
        elif "grok" in t or "xai" in t or "twitter" in t:
            ATTENTE_CHOIX_MODELE_SITE = False
            MODELE_SITE_CHOISI = "grok"
        elif "chatgpt" in t or "openai" in t or "chat gpt" in t:
            ATTENTE_CHOIX_MODELE_SITE = False
            MODELE_SITE_CHOISI = "openai"
        elif "annule" in t or "arrête" in t or "stop" in t or "laisse tomber" in t:
            ATTENTE_CHOIX_MODELE_SITE = False
            await hablar("Création de site internet annulée.")
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_website_model_selector"})) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            return
        else:
            await hablar("Je n'ai pas compris le modèle. Dis le nom de l'agent ou clique sur les boutons à l'écran.")
            return

        # Si un modèle de site a été choisi, on demande maintenant le modèle d'image
        if MODELE_SITE_CHOISI:
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_website_model_selector"})) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            ATTENTE_CHOIX_MODELE_IMAGE_SITE = True
            await hablar("Et avec quel modèle veux-tu que je génère les images du site ?")
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "ask_image_model"})) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            return

    if ATTENTE_CHOIX_MODELE_IMAGE_SITE:
        t = texte_utilisateur.lower()
        if "gemini" in t or "google" in t or "imagen" in t:
            ATTENTE_CHOIX_MODELE_IMAGE_SITE = False
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            asyncio.create_task(generer_site_web(PROMPT_EN_ATTENTE, MODELE_SITE_CHOISI, image_model="gemini"))
            return
        elif "grok" in t or "xai" in t or "twitter" in t:
            ATTENTE_CHOIX_MODELE_IMAGE_SITE = False
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            asyncio.create_task(generer_site_web(PROMPT_EN_ATTENTE, MODELE_SITE_CHOISI, image_model="grok"))
            return
        elif "chatgpt" in t or "openai" in t or "gpt-image" in t or "gpt image" in t or "dall-e" in t or "dall e" in t or "dalle" in t:
            ATTENTE_CHOIX_MODELE_IMAGE_SITE = False
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            asyncio.create_task(generer_site_web(PROMPT_EN_ATTENTE, MODELE_SITE_CHOISI, image_model="openai"))
            return
        elif any(keyword in t for keyword in ["annule", "annuler", "stop", "quitte", "quitter", "non"]):
            ATTENTE_CHOIX_MODELE_IMAGE_SITE = False
            await hablar("Génération de site annulée.")
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(json.dumps({"type": "close_image_model_selector"})) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            return
        else:
            await hablar("Je n'ai pas compris le modèle d'image. Dis 'Gemini', 'Grok', ou 'ChatGPT', ou clique sur les boutons à l'écran.")
            return
    t = texte_utilisateur.lower()
    # INTERCEPTION DE LA DEMANDE DE CRÉATION DE PROMPT
    if ("prompt" in t or "prompte" in t) and any(kw in t for kw in ["crée", "cree", "créer", "creer", "génère", "genere", "fais", "rédige", "redige", "faire", "concevoir"]):
        if len(texte_utilisateur.split()) < 6:
            ATTENTE_CREATION_PROMPT = True
            await hablar("Quel genre de prompt veux-tu que je crée ?")
            return
            
        await hablar("Je génère le prompt détaillé, un instant s'il vous plaît.")
        asyncio.create_task(generer_prompt_special(texte_utilisateur))
        return

    # INTERCEPTION DE LA DEMANDE DE CRÉATION DE SITE WEB
    if any(keyword in t for keyword in ["crée un site", "cree un site", "créer un site", "creer un site", "fais un site", "crée moi un site", "cree moi un site", "génère un site", "genere un site"]):
        if len(texte_utilisateur.split()) < 6:
            ATTENTE_SUJET_SITE = True
            await hablar("Quel genre de site internet veux-tu que je crée ?")
            return
            
        ATTENTE_CHOIX_MODELE_SITE = True
        PROMPT_EN_ATTENTE = texte_utilisateur
        
        available_models = []
        if gemini_actif: available_models.append("gemini")
        if anthropic_client: available_models.append("claude")
        if groq_client: available_models.append("groq")
        if mistral_client: available_models.append("mistral")
        if grok_client: available_models.append("grok")
        if openai_client: available_models.append("openai")
        
        await hablar(f"Avec quel modèle d'IA veux tu que je crée ton site internet ?")
        if CONNECTED_CLIENTS:
            await asyncio.gather(*[ws.send(json.dumps({
                "type": "ask_website_model",
                "prompt": texte_utilisateur,
                "available_models": available_models
            })) for ws in CONNECTED_CLIENTS], return_exceptions=True)
        return

    # INTERCEPTION DE LA DEMANDE DE CRÉATION DE MUSIQUE / CHANT
    t = texte_utilisateur.lower()
    if any(keyword in t for keyword in ["crée une musique", "cree une musique", "crée une chanson", "cree une chanson", "génère une musique", "genere une musique", "génère une chanson", "genere une chanson", "chante une chanson", "chante-moi une chanson", "chante-moi un morceau"]):
        if len(texte_utilisateur.split()) < 6:
            ATTENTE_SUJET_MUSIQUE = True
            await hablar("Sur quel thème veux-tu que je compose cette musique ?")
            return
            
        await hablar("Très bien Christopher, je compose et je vous chante cela tout de suite...")
        success = await generer_et_chanter_musique(texte_utilisateur)
        if success:
            return
        else:
            await hablar("Désolé Christopher, mon module musical a rencontré une petite erreur. Je repasse sur le mode standard.")

    # ── COMMANDES VOCALES MUSIQUE MULTI-GENRES (jarvis_music.py) ─────────────
    # Triggers genre RAP
    _triggers_rap = [
        "rappe-moi", "fais-moi un rap", "fais moi un rap", "crée un rap", "cree un rap",
        "génère un rap", "genere un rap", "compose un rap", "un rap sur",
        "fais du rap", "balance un rap", "balance-moi un rap",
        "pose un couplet", "envoie un couplet", "un couplet sur",
    ]
    # Triggers genre CHANSON
    _triggers_chanson = [
        "compose-moi une chanson", "compose moi une chanson",
        "fais-moi une chanson", "fais moi une chanson",
        "écris une chanson", "ecris une chanson",
        "crée une chanson française", "cree une chanson francaise",
        "une chanson sur", "chansonne",
    ]
    # Triggers genre SLAM
    _triggers_slam = [
        "fais-moi un slam", "fais moi un slam", "crée un slam", "cree un slam",
        "génère un slam", "genere un slam", "compose un slam", "un slam sur",
        "écris un poème", "ecris un poeme", "un spoken word",
    ]
    # Triggers genre REGGAE
    _triggers_reggae = [
        "fais-moi un reggae", "fais moi un reggae", "crée un reggae", "cree un reggae",
        "un reggae sur", "chante du reggae", "compose un reggae",
    ]
    # Triggers genre METAL
    _triggers_metal = [
        "fais-moi du metal", "fais moi du metal", "crée du metal", "cree du metal",
        "un metal sur", "chante du metal", "compose du metal",
        "fais-moi du hard rock", "fais moi du hard rock",
    ]
    # Triggers genre POP
    _triggers_pop = [
        "fais-moi une pop", "fais moi une pop", "crée une pop", "cree une pop",
        "compose une chanson pop", "une chanson pop sur", "fais du pop",
    ]
    # Triggers genre BLUES
    _triggers_blues = [
        "fais-moi du blues", "fais moi du blues", "crée du blues", "cree du blues",
        "un blues sur", "chante du blues", "compose du blues",
    ]
    # Triggers genre ROCK
    _triggers_rock = [
        "fais-moi du rock", "fais moi du rock", "crée du rock", "cree du rock",
        "un rock sur", "chante du rock", "compose du rock", "balance du rock",
    ]
    # Triggers genre ELECTRO
    _triggers_electro = [
        "fais-moi de l'électro", "fais moi de l electro", "crée de l'électro", "cree de l electro",
        "un track electro", "un track sur", "compose de l'électro", "compose de l electro",
        "fais-moi un track", "fais moi un track", "balance un track",
    ]

    _MAP_GENRE_TRIGGERS = [
        ("rap",     _triggers_rap),
        ("chanson", _triggers_chanson),
        ("slam",    _triggers_slam),
        ("reggae",  _triggers_reggae),
        ("metal",   _triggers_metal),
        ("pop",     _triggers_pop),
        ("blues",   _triggers_blues),
        ("rock",    _triggers_rock),
        ("electro", _triggers_electro),
    ]

    _genre_detecte = None
    for _genre_nom, _genre_triggers in _MAP_GENRE_TRIGGERS:
        if any(kw in t for kw in _genre_triggers):
            _genre_detecte = _genre_nom
            break

    if _genre_detecte and _JARVIS_MUSIC_OK:
        _labels = {"rap": "rap", "chanson": "chanson", "slam": "slam",
                   "reggae": "reggae", "metal": "métal", "pop": "pop",
                   "blues": "blues", "rock": "rock", "electro": "électro"}
        _label = _labels.get(_genre_detecte, _genre_detecte)
        
        # Extraction du thème : on retire le trigger du texte
        _theme_brut = texte_utilisateur.lower()
        for _kw in [kw for _, tlist in _MAP_GENRE_TRIGGERS for kw in tlist]:
            _theme_brut = _theme_brut.replace(_kw, " ").strip()
        
        # Limpieza des mots parasites
        for _parasite in ["jarvis", "s'il te plait", "s'il te plaît", "stp"]:
            _theme_brut = _theme_brut.replace(_parasite, " ").strip()
            
        _theme_brut = _theme_brut.strip(" ,.:!?")
        
        if not _theme_brut or _theme_brut in ["sur", "de", "pour"]:
            ATTENTE_SUJET_MUSIQUE = True
            MUSIQUE_GENRE_EN_ATTENTE = _genre_detecte
            await hablar(f"Sur quel thème veux-tu que je te fasse ce {_label} ?")
            return
            
        await hablar(f"Très bien {USER_NAME}, je vous compose un {_label} tout de suite...")
        try:
            if _jarvis_music_instance is None:
                _jarvis_music_instance = _JarvisMusic()
            # Génération en thread pour ne pas bloquer la boucle async
            loop = asyncio.get_event_loop()
            _texte_musique = await loop.run_in_executor(
                None,
                lambda: _jarvis_music_instance.generer(theme=_theme_brut, genre=_genre_detecte)
            )
            # Lecture TTS via hablar() pour rester dans le flux audio JARVIS
            await hablar(_texte_musique)
            return
        except Exception as _e_music:
            print(f"[JARVIS_MUSIC] Error : {_e_music}")
            await hablar(f"Désolé {USER_NAME}, je n'ai pas réussi à composer ce {_label}. Je repasse en mode standard.")
    elif _genre_detecte and not _JARVIS_MUSIC_OK:
        await hablar(f"Désolé {USER_NAME}, le module musical multi-genres n'est pas disponible. Vérifiez que jarvis_music.py est bien présent.")
        return
    # ── FIN COMMANDES MUSIQUE MULTI-GENRES ───────────────────────────────────

    # TENTATIVE DE RÉSOLUTION LOCALE (Commandes, Math, Français, etc.)
    reponse = await resolver_comandos_locales(texte_utilisateur)
    if not reponse: reponse = resolver_info_sistema_local(texte_utilisateur)
    if not reponse: reponse = resolver_matematica_local(texte_utilisateur)
    if not reponse: reponse = resoudre_francais_localement(texte_utilisateur)
    if not reponse: reponse = resolver_conversion_local(texte_utilisateur)
    if not reponse: reponse = resolver_traduccion_local(texte_utilisateur)
    if not reponse: reponse = await resolver_globo_local(texte_utilisateur)
    if not reponse: reponse = await resolver_extras_local(texte_utilisateur)
    
    # VISION (Regarde mon écran)
    if not reponse:
        t = texte_utilisateur.lower()
        if any(keyword in t for keyword in ["regarde mon écran", "analyse mon écran", "vois-tu mon écran", "qu'est-ce qu'il y a sur mon écran"]):
            await hablar("Bien sûr Christopher, laissez-moi jeter un œil...")
            img_b64 = await request_screen_capture()
            if img_b64:
                reponse = await pedir_ia_vision(texte_utilisateur, img_b64)
            else:
                reponse = "Je suis désolé Christopher, mais je n'ai pas pu capturer tu écran. Assurez-vous d'avoir cliqué sur 'Activer la vision' sur l'interface et d'avoir autorisé le partage."
        
        # CAMERA (Lance la caméra / Analyse visuelle / Objets / Tenue)
        camera_keywords = [
            # Caméra générale (avec ET sans accents pour la reconnaissance vocale)
            "lance la caméra", "lance la camera",
            "ouvre la caméra", "ouvre la camera",
            "regarde avec la caméra", "regarde avec la camera",
            "active la caméra", "active la camera",
            "analyse ce que tu vois", "qu'est-ce que tu vois", "qu'est ce que tu vois",
            "dis-moi ce que tu vois", "dis moi ce que tu vois",
            "regarde ce que je te montre", "regarde ce que je montre",
            "regarde-moi", "regarde moi", "analyse-moi", "analyse moi",
            # Tenue / Vêtements
            "ma tenue", "mes vêtements", "mes vetements",
            "comment je suis habillé", "comment je suis habille",
            "est-ce que ça me va", "est-ce que ca me va",
            "ça me va", "ca me va",
            "qu'est-ce que je porte", "je porte quoi",
            # Objets / Identification
            "c'est quoi ça", "c'est quoi ca", "qu'est-ce que c'est",
            "décris cet objet", "decris cet objet", "c'est quoi cet objet",
            "identifie", "reconnais", "qu'est-ce que je te montre",
            "je te montre", "regarde ça", "regarde ca",
            "tu vois quoi", "dis-moi ce que c'est", "dis moi ce que c'est", "analyse ça", "analyse ca",
            # Webcam
            "webcam", "la cam",
        ]
        # Webcam Plein Écran / Petit format / Arrêt
        fullscreen_kws = [
            "met la caméra en plein écran", "met la camera en plein ecran",
            "met la webcam en plein écran", "met la webcam en plein ecran",
            "caméra en plein écran", "camera en plein ecran",
            "webcam en plein écran", "webcam en plein ecran",
            "plein écran la caméra", "plein ecran la camera",
            "plein écran la webcam", "plein ecran la webcam",
            "plein écran webcam", "plein ecran webcam",
            "plein écran caméra", "plein ecran camera",
            "caméra en arrière plan", "camera en arrière plan",
            "webcam en arrière plan", "webcam en arrière plan",
            "caméra en arrière-plan", "camera en arrière-plan",
            "webcam en arrière-plan", "webcam en arrière-plan"
        ]
        
        small_kws = [
            "remets la caméra en petit", "remets la camera en petit",
            "remets la webcam en petit", "remets la webcam en petit",
            "caméra en petit", "camera en petit",
            "webcam en petit", "retire le plein écran",
            "retire le plein ecran", "quitte le plein écran",
            "quitte le plein ecran", "enlève le plein écran",
            "enleve le plein ecran"
        ]

        if any(kw in t for kw in fullscreen_kws) or t in ["webcam", "caméra", "camera"]:
            msg = json.dumps({"type": "open_webcam", "fullscreen": True})
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            reponse = f"J'ai activé tu caméra en plein écran en arrière-plan, {USER_NAME}."
        elif any(kw in t for kw in small_kws):
            msg = json.dumps({"type": "open_webcam", "fullscreen": False})
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            reponse = f"J'ai remis le retour caméra en petit format, {USER_NAME}."
        elif any(kw in t for kw in ["active la caméra", "active la camera", "active la webcam", "ouvre la caméra", "ouvre la camera", "ouvre la webcam", "lance la caméra", "lance la camera", "lance la webcam"]):
            msg = json.dumps({"type": "open_webcam", "fullscreen": False})
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            reponse = f"J'ai activé tu retour caméra, {USER_NAME}. Regardez en bas à droite de tu écran."
        elif any(kw in t for kw in ["désactive la caméra", "désactive la camera", "désactive la webcam", "desactive la caméra", "desactive la camera", "desactive la webcam", "ferme la caméra", "ferme la camera", "ferme la webcam"]):
            msg = json.dumps({"type": "close_webcam"})
            if CONNECTED_CLIENTS:
                await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
            reponse = f"J'ai désactivé le retour de la caméra, {USER_NAME}."
        elif any(keyword in t for keyword in camera_keywords):
            reponse = await jarvis_vision_camera(texte_utilisateur)

    if not reponse:
        origine = "téléphone" if mobile_ws else "ordinateur"
        texte_pour_ia = texte_utilisateur + f"\n\n[Note système : L'utilisateur te parle actuellement depuis son {origine}. Adapte ta réponse si la question porte sur ton moyen d'écoute.]"
        reponse = await pedir_ia(texte_pour_ia)
    
    # L'impression dans le terminal se fera desormais de maniere synchronisee dans hablar()
    # Si commande mobile et que la cible n'est pas forcée sur le PC : activer le flag pour couper l'audio PC et répondre via mobile
    if mobile_ws and not target_pc:
        _skip_pc_audio = True

    # Recherche de TOUS les blocs JSON dans la réponse
    json_blocks = re.findall(r'\{.*?\}', reponse, re.DOTALL)
    
    texte_clean = re.sub(r'\{.*?\}', '', reponse, flags=re.DOTALL).strip()
    tache_parler = None
    
    # Impression immédiate de la réponse dans la console pour un retour visuel instantané
    if texte_clean:
        print(f"[JARVIS] {texte_clean}")

    if not json_blocks:
        if texte_clean:
            await hablar(texte_clean)
        _skip_pc_audio = False
        return
        
    if texte_clean:
        tache_parler = asyncio.create_task(hablar(texte_clean))

    for block in json_blocks:
        try:
            print(f"[JARVIS] Execution de l'action : {block}")
            # Timeout de 15s pour chaque action pour eviter de freezer Jarvis
            data = json.loads(block)
            action = data.get("action", "")
            
            # On execute l'action avec un timeout
            try:
                # Note: On utilise asyncio.wait_for pour les actions asynchrones
                # Les actions synchrones comme ha_lumiere devraient idéalement être async aussi
                # mais pour l'instant on les laisse ainsi ou on les wrappe.
                pass 
            except asyncio.TimeoutError:
                print(f"[ACTION ERROR] Timeout sur l'action {action}")
                if grok_client:
                    await hablar("C'est un peu long Christopher, je demande une vérification à Grok.")
                    rep_grok = await pedir_grok(texte_utilisateur + " (L'action domotique a expiré, peux-tu répondre à l'utilisateur ?)")
                    if rep_grok: await hablar(rep_grok)
                continue

            if action == "mode_iron_man":
                etat = data.get("etat", "off")
                MODE_IRON_MAN = (etat == "on")
                msg = "Mode Iron Man activé, Monsieur. Je reste à l'écoute de vos signaux." if MODE_IRON_MAN else "Mode Iron Man désactivé. Je repasse en veille domotique."
                await hablar(msg)
            elif action == "afficher_recette":
                titre = data.get("titre", "Recette")
                ingredients = data.get("ingredients", [])
                instructions = data.get("instructions", [])
                msg_json = json.dumps({
                    "type": "show_recipe",
                    "titre": titre,
                    "ingredients": ingredients,
                    "instructions": instructions
                })
                if CONNECTED_CLIENTS:
                    try:
                        await asyncio.gather(*[ws.send(msg_json) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                    except Exception as e:
                        print(f"[ERREUR WS] Broadcast recette: {e}")
                await hablar(f"Voici la recette pour {titre}, affichée sur tu interface.")
            elif action == "memoriser":
                cle    = data.get("cle",    "info")
                valeur = data.get("valeur", "")
                ajouter_memoire(cle, valeur)
                await hablar(f"Bien note Christopher, je me souviendrai que {valeur}.")
            elif action == "oublier":
                cle     = data.get("cle", "")
                success = supprimer_memoire(cle)
                if success:
                    await hablar("Information oubliee, Christopher.")
                else:
                    await hablar("Je n avais pas cette information en memoire.")
            elif action == "lister_memoire":
                memoire = charger_memoire()
                if not memoire:
                    await hablar("Aucune information personnalisee en memoire, Christopher.")
                else:
                    lignes = ["Voici ce que je sais sur vous Christopher."]
                    for cle, data_m in memoire.items():
                        lignes.append(f"{cle} : {data_m['valeur']}.")
                    await hablar(" ".join(lignes))
            elif action == "obsidian_creer_note":
                titre = data.get("titre", "")
                contenu = data.get("contenu", "")
                success, msg_res = obsidian_helper.creer_ou_modifier_note(titre, contenu)
                if success:
                    if CONNECTED_CLIENTS:
                        notes_list = obsidian_helper.lister_notes()
                        msg_open = json.dumps({"type": "obsidian_open"})
                        msg_notes = json.dumps({"type": "obsidian_notes", "notes": notes_list})
                        await asyncio.gather(*[ws.send(msg_open) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                        await asyncio.gather(*[ws.send(msg_notes) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                        msg_content = json.dumps({
                            "type": "obsidian_note_content",
                            "titre": titre,
                            "content": contenu
                        })
                        await asyncio.gather(*[ws.send(msg_content) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                await hablar(msg_res)
            elif action == "obsidian_lire_note":
                titre = data.get("titre", "")
                success, content = obsidian_helper.lire_note(titre)
                if success:
                    if CONNECTED_CLIENTS:
                        msg_open = json.dumps({"type": "obsidian_open"})
                        msg_content = json.dumps({
                            "type": "obsidian_note_content",
                            "titre": titre,
                            "content": content
                        })
                        await asyncio.gather(*[ws.send(msg_open) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                        await asyncio.gather(*[ws.send(msg_content) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                    preview = content[:200]
                    if len(content) > 200:
                        preview += "..."
                    await hablar(f"Voici le contenu de la note {titre} : {preview}")
                else:
                    await hablar(content)
            elif action == "obsidian_rechercher":
                query = data.get("query", "")
                results = obsidian_helper.rechercher_notes(query)
                if results:
                    if CONNECTED_CLIENTS:
                        msg_open = json.dumps({"type": "obsidian_open"})
                        msg_results = json.dumps({
                            "type": "obsidian_search_results",
                            "query": query,
                            "results": results
                        })
                        await asyncio.gather(*[ws.send(msg_open) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                        await asyncio.gather(*[ws.send(msg_results) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                    noms = [r["titre"] for r in results]
                    await hablar(f"J'ai trouvé {len(results)} note(s) contenant '{query}' Christopher : {', '.join(noms)}.")
                else:
                    await hablar(f"Aucune note ne correspond à la recherche '{query}', Christopher.")
            elif action == "obsidian_lister":
                notes_list = obsidian_helper.lister_notes()
                if CONNECTED_CLIENTS:
                    msg_open = json.dumps({"type": "obsidian_open"})
                    msg_notes = json.dumps({"type": "obsidian_notes", "notes": notes_list})
                    await asyncio.gather(*[ws.send(msg_open) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                    await asyncio.gather(*[ws.send(msg_notes) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                if notes_list:
                    await hablar(f"J'affiche vos {len(notes_list)} notes Obsidian, Christopher.")
                else:
                    await hablar("Votre coffre Obsidian est actuellement vide, Christopher.")
            elif action == "ouvrir_dossier":
                chemin = data.get("chemin", "bureau")
                ok, resultat = ouvrir_dossier(chemin)
                if ok:
                    await hablar("Dossier ouvert, Christopher. Dites-moi si vous voulez que je le trie.")
                else:
                    await hablar(f"Je n ai pas trouve ce dossier, Christopher. {resultat}")
            elif action == "lister_dossier":
                contenu, err = lister_dossier()
                if err:
                    await hablar(err)
                else:
                    nb_fichiers = len(contenu["fichiers"])
                    nb_dossiers = len(contenu["dossiers"])
                    await hablar(f"Le dossier contient {nb_fichiers} fichiers et {nb_dossiers} sous-dossiers, Christopher.")
            elif action == "trier_par_type":
                await hablar("Je trie vos fichiers par type, Christopher. Un instant.")
                ok, msg = trier_par_type()
                await hablar(msg if ok else f"Probleme lors du tri : {msg}")
            elif action == "trier_par_date":
                await hablar("Je trie vos fichiers par date, Christopher. Un instant.")
                ok, msg = trier_par_date()
                await hablar(msg if ok else f"Probleme lors du tri : {msg}")
            elif action == "trier_complet":
                await hablar("Je trie vos fichiers par type puis par date dans chaque categorie, Christopher.")
                ok, msg = trier_par_type_puis_date()
                await hablar(msg if ok else f"Probleme lors du tri : {msg}")
            elif action == "creer_dossier":
                nom     = data.get("nom", "Nouveau Dossier")
                ok, msg = creer_sous_dossier(nom)
                await hablar(msg if ok else f"Error : {msg}")
            elif action == "renommer_fichier":
                ancien  = data.get("ancien", "")
                nouveau = data.get("nouveau", "")
                ok, msg = renommer_fichier(ancien, nouveau)
                await hablar(msg if ok else f"Error : {msg}")
            elif action == "deplacer_fichier":
                fichier = data.get("fichier",     "")
                dest    = data.get("destination", "")
                ok, msg = deplacer_fichier(fichier, dest)
                await hablar(msg if ok else f"Error : {msg}")
            elif action == "chercher_fichier":
                nom        = data.get("nom", "")
                resultats, err = chercher_fichier(nom)
                if err:
                    await hablar(err)
                elif not resultats:
                    await hablar(f"Aucun fichier contenant {nom} n a ete trouve, Christopher.")
                else:
                    noms = [os.path.basename(r) for r in resultats[:5]]
                    await hablar(f"J ai trouve {len(resultats)} fichier(s). Par exemple : {', '.join(noms)}.")
            elif action == "ha_lumiere":
                piece      = data.get("piece",      "salon").lower().strip()
                etat       = data.get("etat",       "on")
                couleur    = data.get("couleur",    None)
                luminosite = data.get("luminosite", None)
                entity_id  = PIECES_LUMIERES.get(piece, f"light.{piece}")
                rgb        = COULEURS_MAP.get(couleur) if couleur else None
                ha_lumiere(entity_id, etat, luminosite, rgb)
                
                # Message de confirmation amélioré
                if etat == "off":
                    msg = f"J'éteins {piece}."
                else:
                    details = []
                    if couleur: details.append(f"en {couleur}")
                    if luminosite is not None: 
                        pourcent = int((int(luminosite)/255)*100)
                        details.append(f"à {pourcent}%")
                    
                    if details:
                        msg = f"C'est fait, {piece} est réglé{' '.join(details)}."
                    else:
                        msg = f"Lumière {piece} allumée."
                await hablar(msg)
            elif action == "ha_prise":
                piece     = data.get("piece", "bureau").lower().strip()
                etat      = data.get("etat",  "on")
                entity_id = PIECES_PRISES.get(piece, f"switch.prise_{piece}")
                ha_interrupteur(entity_id, etat)
                msg = f"Prise {piece} {'activée' if etat == 'on' else 'désactivée'}."
                await hablar(msg)
            elif action == "ha_temperature":
                piece     = data.get("piece", "salon").lower().strip()
                entity_id = PIECES_CAPTEURS.get(piece)
                if entity_id:
                    temp    = ha_get_etat(entity_id)
                    hum_id  = PIECES_HUMIDITE.get(piece)
                    hum     = ha_get_etat(hum_id) if hum_id else None
                    hum_val = str(hum) if (hum and str(hum) != "inconnu") else None
                    if str(temp) != "inconnu":
                        await send_web_temp_piece({
                            "piece"      : piece,
                            "temperature": str(temp),
                            "humidite"   : hum_val,
                        })
                    await hablar(f"La température dans le {piece} est de {temp} degrés.")
                else:
                    await hablar(f"Désolé, je n'ai pas de capteur configuré pour le {piece}.")
            elif action == "ha_humidite":
                piece     = data.get("piece", "bureau").lower().strip()
                entity_id = PIECES_HUMIDITE.get(piece) or PIECES_CAPTEURS.get(piece)
                if entity_id:
                    humi = ha_get_etat(entity_id)
                    await hablar(f"Le taux d'humidité dans le {piece} est de {humi}%.")
                else:
                    await hablar(f"Je n'ai pas de capteur d'humidité pour le {piece}.")
            elif action == "ha_batterie":
                appareil  = data.get("appareil", "").lower()
                entity_id = APPAREILS_BATTERIE.get(appareil)
                if entity_id:
                    batt = ha_get_etat(entity_id)
                    if batt == "unknown":
                        await hablar(f"Je n'arrive pas à récupérer l'état de la batterie pour {appareil}.")
                    else:
                        suff = ""
                        if "telephone" in appareil or "christopher" in appareil or USER_NAME.lower() in appareil:
                            suff = "Ton téléphone est à "
                        elif "christopher" in appareil or "maman" in appareil:
                            suff = "Le téléphone de Christopher est à "
                        else:
                            suff = f"La batterie de {appareil} est à "
                        await hablar(f"{suff}{batt}%.")
                else:
                    await hablar(f"Je n'ai pas l'appareil {appareil} dans ma liste de batterie.")
            elif action == "ha_thermostat":
                temp = data.get("temperature", 20)
                ha_thermostat("climate.thermostat", temp)
                await hablar(f"Thermostat réglé à {temp} degrés.")
            elif action == "ha_scene":
                nom      = data.get("nom", "")
                scene_id = f"scene.{nom}"
                ha_scene(scene_id)
                await hablar(f"Ambiance {nom} activée.")
            elif action == "ha_alarme":
                etat = data.get("etat", "on")
                if etat == "on":
                    ha_appeler_service("alarm_control_panel", "alarm_arm_away", "alarm_control_panel.home_base_2")
                    await hablar("Alarme activée.")
                else:
                    ha_appeler_service("alarm_control_panel", "alarm_disarm", "alarm_control_panel.home_base_2")
                    await hablar("Alarme désactivée.")
            elif action == "ha_verrou":
                entity_id = data.get("entity_id", "lock.porte_maison")
                etat = data.get("etat", "lock")
                ha_verrou(entity_id, etat)
                msg = "Porte verrouillée, Christopher." if etat == "lock" else "Porte déverrouillée, Christopher."
                await hablar(msg)
            elif action == "ha_simulation":
                etat = data.get("etat", "on")
                ha_interrupteur("switch.simulation", etat)
                msg = "Simulation de présence activée." if etat == "on" else "Simulation de présence désactivée."
                await hablar(msg)
            elif action == "ha_anniversaires":
                events = ha_get_calendrier("calendar.anniversaires")
                if not events:
                    await hablar("Rien de prévu aujourd'hui.")
                else:
                    noms = [e.get("summary", "Anniversaire sans nom") for e in events]
                    if len(noms) == 1:
                        await hablar(f"Aujourd'hui, nous fêtons l'anniversaire de {noms[0]}. N'oubliez pas de lui souhaiter !")
                    else:
                        liste = ", ".join(noms[:-1]) + " et " + noms[-1]
                        await hablar(f"Aujourd'hui, il y a plusieurs anniversaires : {liste}. C'est une journée chargée !")
            elif action == "ha_consommation":
                entity_id = PIECES_CAPTEURS.get("consommation")
                puissance = ha_get_etat(entity_id)
                if puissance == "unknown" or puissance == "inconnu":
                    await hablar("Je n'arrive pas à lire la consommation électrique pour le moment.")
                else:
                    await hablar(f"La consommation actuelle de la maison est de {puissance} Volt-Ampères.")
            elif action == "ha_tiktok":
                entity_id = PIECES_CAPTEURS.get("tiktok")
                followers = ha_get_etat(entity_id)
                await hablar(f"Tu as actuellement {followers} abonnés sur ton compte TikTok TechEnClair, Christopher. Felicitaciones !")
            elif action == "ha_oeufs":
                entity_id = PIECES_CAPTEURS.get("oeufs")
                # On récupère l'état (le dernier choix) et le moment de la modif
                try:
                    r = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=HA_HEADERS, timeout=5)
                    data = r.json()
                    last_changed = data.get("last_changed", "")
                    if last_changed:
                        dt = datetime.fromisoformat(last_changed.replace("Z", "+00:00"))
                        phrase = dt.strftime("le %d %B à %Hh%M")
                        await hablar(f"Le dernier ramassage des œufs a été enregistré {phrase}.")
                    else:
                        await hablar("Je n'ai pas d'historique pour le ramassage des œufs.")
                except:
                    await hablar("Je n'arrive pas à accéder aux informations sur les œufs.")
            elif action == "ha_energie":
                periode  = data.get("periode", "mois")
                appareil = data.get("appareil", "")
                
                if appareil:
                    appareil_clean = appareil.lower()
                    entite = APPAREILS_ENERGIE.get(appareil_clean)
                    if entite:
                        val = ha_get_etat(entite)
                        if val != "inconnu" and val != "unknown":
                            kwh = float(val)
                            await hablar(f"La consommation de {appareil} pour ce mois est de {kwh:.1f} kWh.")
                        else:
                            await hablar(f"Je n'ai pas de données de consommation pour {appareil} pour le moment.")
                    else:
                        await hablar(f"Je n'ai pas d'appareil nommé {appareil} dans mon suivi énergétique.")
                elif periode == "hier":
                    total_kwh = 0
                    total_cost = 0
                    try:
                        for i in range(1, 7):
                            e_id = f"sensor.lixee_zlinky_tic_zlinky_p{i}_daily"
                            val = ha_get_etat(e_id, attribut="last_period")
                            if val != "inconnu" and val != "unknown":
                                k = float(val)
                                total_kwh += k
                                total_cost += k * HA_TARIFS.get(f"p{i}", 0.16)
                        await hablar(f"Hier, la maison a consommé {total_kwh:.1f} kWh, pour un coût estimé à {total_cost:.2f} euros.")
                    except:
                        await hablar("J'ai eu un problème pour calculer la consommation d'hier.")
                else: # mois
                    total_kwh = 0
                    total_cost = 0
                    try:
                        for i in range(1, 7):
                            e_id = f"sensor.lixee_zlinky_tic_zlinky_p{i}_mensuel"
                            val = ha_get_etat(e_id)
                            if val != "inconnu" and val != "unknown":
                                k = float(val)
                                total_kwh += k
                                total_cost += k * HA_TARIFS.get(f"p{i}", 0.16)
                        await hablar(f"Ce mois-ci, la consommation totale est de {total_kwh:.1f} kWh, pour un montant de {total_cost:.2f} euros.")
                    except:
                        await hablar("Je n'ai pas pu calculer la consommation mensuelle.")
            elif action == "ha_aspirateur":
                commande = data.get("commande", "start")
                if commande == "start":
                    ha_appeler_service("vacuum", "start", "vacuum.bob")
                    await hablar("C'est parti, Bob lance le nettoyage.")
                elif commande == "stop":
                    ha_appeler_service("vacuum", "stop", "vacuum.bob")
                    await hablar("J'ai arrêté l'aspirateur.")
                elif commande == "pause":
                    ha_appeler_service("vacuum", "pause", "vacuum.bob")
                    await hablar("Bob est en pause.")
                elif commande == "base":
                    ha_appeler_service("vacuum", "return_to_base", "vacuum.bob")
                    await hablar("Bob retourne à sa base.")
            elif action == "create_doc":
                titre   = data.get("title",   "Document JARVIS")
                contenu = data.get("content", "")
                result  = creer_google_doc(titre, contenu)
                await hablar(result)
            elif action == "write_doc":
                contenu = data.get("content", "")
                result  = modifier_google_doc(contenu)
                await hablar(result)
            elif action == "create_sheet":
                titre  = data.get("title", "Feuille JARVIS")
                result = creer_google_sheet(titre)
                await hablar(result)
            elif action == "read_emails":
                result = lire_emails()
                await hablar(f"Voici vos derniers emails Christopher. {result}")
            elif action == "read_calendar":
                result = lister_evenements_calendar()
                await hablar(f"Voici vos prochains evenements Christopher. {result}")
            elif action == "meteo":
                ville = data.get("ville") or None
                await hablar("Je consulte la meteo, un instant.")
                result = get_meteo_actuelle(ville)
                meteo_data = get_meteo_structuree(ville)
                if meteo_data:
                    await send_web_meteo(meteo_data)
                await hablar(result)
            elif action == "alerte_meteo":
                ville = data.get("ville") or None
                result = get_alertes_meteo(ville)
                await hablar(result)
            elif action == "recherche_web":
                query = data.get("query", "")
                await hablar(f"Je lance une recherche sur internet pour {query}.")
                result = recherche_web_serpapi(query)
                await hablar(result)
            elif action == "generer_image":
                prompt_fr = data.get("prompt", "")
                if not prompt_fr:
                    await hablar(f"Désolé {USER_NAME}, je n'ai pas compris ce que vous souhaitez que je génère.")
                else:
                    ATTENTE_CHOIX_MODELE_IMAGE = True
                    PROMPT_EN_ATTENTE = prompt_fr

                    await hablar(f"Avec quel modèle de génération d'image veux tu que je crée ton image ?")
                    if CONNECTED_CLIENTS:
                        await asyncio.gather(*[ws.send(json.dumps({
                            "type": "ask_image_model",
                            "prompt": prompt_fr
                        })) for ws in CONNECTED_CLIENTS], return_exceptions=True)


            elif action == "generer_video":
                prompt_fr = data.get("prompt", "")
                if not prompt_fr:
                    await hablar(f"Désolé {USER_NAME}, je n'ai pas compris ce que vous souhaitez que je génère comme vidéo.")
                elif not grok_client:
                    await hablar(f"Désolé {USER_NAME}, le client xAI n'est pas configuré. La génération vidéo nécessite une clé xAI.")
                else:
                    await hablar(f"Je génère tu vidéo avec xAI, cela peut prendre une à deux minutes {USER_NAME}. Patience !")
                    
                    # Notifier le frontend pour afficher l'animation de chargement
                    msg_loading = json.dumps({"type": "generation_loading", "media_type": "video"})
                    if CONNECTED_CLIENTS:
                        try:
                            await asyncio.gather(*[ws.send(msg_loading) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                        except Exception: pass

                    result_vid = await generer_video_xai(prompt_fr)
                    if "error" in result_vid:
                        print(f"[VIDEO_GEN] Error : {result_vid['error']}")
                        if CONNECTED_CLIENTS:
                            try:
                                await asyncio.gather(*[ws.send(json.dumps({"type": "hide_generation_loading"})) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                            except: pass
                        await hablar(f"Désolé {USER_NAME}, la génération vidéo a échoué : {result_vid['error'][:80]}")
                    else:
                        source = result_vid.get('source', 'xAI')
                        msg_json = json.dumps({
                            "type": "show_generated_video",
                            "prompt_fr": prompt_fr,
                            "prompt_en": result_vid.get("prompt_en", prompt_fr),
                            "url": result_vid["url"],
                            "path": result_vid.get("path", ""),
                            "source": source,
                        })
                        if CONNECTED_CLIENTS:
                            try:
                                await asyncio.gather(*[ws.send(msg_json) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                            except Exception as _e:
                                print(f"[ERREUR WS] Broadcast vidéo: {_e}")
                        await hablar(f"Voilà {USER_NAME} ! La vidéo a été générée par {source}, elle s'affiche à l'écran et est automatiquement sauvegardée dans mon dossier d'installation.")

            elif action == "recherche_images":
                query = data.get("query", "")
                nb    = int(data.get("nb", 6))
                if not texte_clean:
                    await hablar(f"Je recherche des images de {query} sur internet, un instant {USER_NAME}.")
                cfg = _cargar_config()
                engine = cfg.get("image_search_engine", "serpapi")
                urls = await asyncio.to_thread(recherche_images_web, query, nb_images=nb, engine=engine)
                if urls:
                    msg_json = json.dumps({
                        "type":   "show_images",
                        "query":  query,
                        "images": urls,
                    })
                    if CONNECTED_CLIENTS:
                        try:
                            await asyncio.gather(*[ws.send(msg_json) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                        except Exception as e:
                            print(f"[ERREUR WS] Broadcast images: {e}")
                    if not texte_clean:
                        await hablar(f"Voilà, j'affiche {len(urls)} image{'s' if len(urls) > 1 else ''} de {query} sur tu interface, Christopher.")
                else:
                    if not texte_clean:
                        await hablar(f"Désolé Christopher, je n'ai pas trouvé d'images pour {query}. Vérifiez tu connexion internet.")

            elif action == "antivirus_scan":
                if CONNECTED_CLIENTS:
                    msg = json.dumps({"type": "av_open"})
                    await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True)
                await hablar("J'initialise le protocole d'analyse de sécurité de tu système, Christopher. Scan en cours.")

            elif action == "restaurant_search":
                global LAST_SHOWN_RESTAURANTS
                LAST_SHOWN_RESTAURANTS = [] # fresh search
                location = data.get("location", "")
                if location:
                    # User specified a location, search without overriding with default coordinates
                    lat, lng = None, None
                else:
                    if VILLE_PAR_DEFAUT:
                        location = VILLE_PAR_DEFAUT
                        lat = LAT_PAR_DEFAUT if LAT_PAR_DEFAUT else None
                        lng = LON_PAR_DEFAUT if LON_PAR_DEFAUT else None
                    else:
                        location = obtenir_ville_par_ip()
                        lat = USER_LOCATION_GPS.get("lat") if USER_LOCATION_GPS else None
                        lng = USER_LOCATION_GPS.get("lng") if USER_LOCATION_GPS else None
                await hablar(f"Je recherche des restaurants à proximité de {location.split(',')[0]} et j'initialise le radar de repérage, un instant Christopher.")
                lanzar_busqueda_restaurantes_fondo(location, lat, lng, [], False)

            elif action == "sport_resultats":
                equipe = data.get("equipe") or None
                ligue  = data.get("ligue")  or None
                print(f"[SPORT] Acción sport_resultats pour {equipe or ligue}")
                await hablar(f"Je cherche les informations pour {equipe or ligue}, un instant.")
                result = get_resultats_football(equipe=equipe, ligue=ligue)
                if "pas trouvé" in result or "Impossible" in result:
                    print(f"[SPORT] Echec recherche locale. Verification avec Grok...")
                    if grok_client:
                        res_grok = await pedir_grok(f"{USER_NAME} veut savoir : {texte_utilisateur}. Je n'ai pas trouvé l'info dans ma base de données football, peux-tu chercher pour lui ?")
                        if res_grok: result = res_grok
                await hablar(result)
            elif action == "sport_classement":
                ligue  = data.get("ligue", "Ligue 1")
                await hablar(f"Je recupere le classement {ligue}.")
                result = get_classement_football(ligue=ligue)
                await hablar(result)
            elif action == "sport_live":
                question = data.get("question", "derniers resultats sportifs 2026")
                await hablar("Je recherche les derniers résultats en direct, un instant Christopher.")
                from datetime import datetime as _dt
                _date_auj = _dt.now().strftime("%d/%m/%Y")
                # Toujours utiliser Gemini + Google Search pour les données sportives en temps réel
                # (Grok et autres LLMs n'ont pas accès à internet live)
                result = get_resultats_sport_gemini(
                    f"Aujourd'hui c'est le {_date_auj}. {question}. "
                    f"Donne tous les matchs programmés CE SOIR ({_date_auj}) ainsi que les résultats du jour. "
                    f"Coupe du monde 2026, Ligue 1, Liga, Premier League, Champions League, etc."
                )
                await hablar(result)
            elif action == "voir_ecran":
                inst = data.get("instruction", "")
                res = await jarvis_vision_cliquer(inst)
                await hablar(res)
            elif action == "whatsapp_appel":
                contact = data.get("contact", "Ma vie")
                await action_whatsapp_appel(contact)
            elif action == "vision_ecrire":
                inst = data.get("instruction", "")
                txt  = data.get("texte", "")
                res  = await jarvis_vision_ecrire(inst, txt)
                await hablar(res)
            elif action == "vision_chercher_sur_site":
                txt = data.get("texte", "")
                await hablar(f"Je cherche la barre de recherche sur ce site, Christopher.")
                res = await jarvis_vision_rechercher_sur_site(txt)
                await hablar(res)
            elif action == "lance_camera":
                res = await jarvis_vision_camera(texte_utilisateur)
                await hablar(res)
            elif action == "vision_navigateur":
                res = await jarvis_vision_navigateur(texte_utilisateur)
                await hablar(res)
            elif action == "dictee":
                texte = data.get("texte", "")
                if texte:
                    import pyautogui
                    import pyperclip
                    import time
                    pyperclip.copy(texte)
                    time.sleep(0.1)
                    pyautogui.hotkey('ctrl', 'v')
                    await hablar("C'est tapé, Christopher.")
            elif action == "spotify_ouvrir":
                await hablar("J'ouvre Spotify, Christopher.")
                res = await spotify_ouvrir()
                await hablar(res)
            elif action == "spotify_rechercher":
                recherche = data.get("recherche", "")
                await hablar(f"Je recherche '{recherche}' sur Spotify, Christopher.")
                res = await spotify_rechercher(recherche)
                await hablar(res)
            elif action == "spotify_lecture_pause":
                res = await spotify_lecture_pause()
                await hablar(res)
            elif action == "spotify_stop":
                res = await spotify_stop()
                await hablar(res)
            elif action == "spotify_suivant":
                res = await spotify_suivant()
                await hablar(res)
            elif action == "spotify_precedent":
                res = await spotify_precedent()
                await hablar(res)
            elif action == "spotify_volume":
                direction = data.get("direction", "monter")
                paliers   = data.get("paliers", 4)
                res = await spotify_volume(direction, paliers)
                await hablar(res)
            elif action == "deezer_ouvrir":
                await hablar("J'ouvre Deezer, Christopher.")
                res = await deezer_ouvrir()
                await hablar(res)
            elif action == "deezer_rechercher":
                recherche = data.get("recherche", "")
                await hablar(f"Je recherche '{recherche}' sur Deezer, Christopher.")
                res = await deezer_rechercher(recherche)
                await hablar(res)
            elif action == "deezer_lecture_pause":
                res = await deezer_lecture_pause()
                await hablar(res)
            elif action == "deezer_stop":
                res = await deezer_stop()
                await hablar(res)
            elif action == "deezer_suivant":
                res = await deezer_suivant()
                await hablar(res)
            elif action == "deezer_precedent":
                res = await deezer_precedent()
                await hablar(res)
            elif action == "deezer_volume":
                direction = data.get("direction", "monter")
                paliers   = data.get("paliers", 4)
                res = await deezer_volume(direction, paliers)
                await hablar(res)

        except Exception as e:
            print(f"[ACTION ERROR] Block failed: {block} | Error: {e}")
            if grok_client:
                print("[JARVIS] Bascule sur Grok suite a une erreur d'action...")
                res_grok = await pedir_grok(f"{USER_NAME} m'a demandé : {texte_utilisateur}. J'ai tenté de lancer une action mais j'ai eu une erreur technique ({e}). Peux-tu prendre le relais et lui répondre élégamment ?")
                if res_grok: await hablar(res_grok)
            continue

    if tache_parler:
        await tache_parler

    # Si du texte reste après les commandes, on ne fait rien de plus car `hablar` a déjà été appelé pour chaque action ou la réponse globale.
    # Réinitialiser le flag audio PC
    _skip_pc_audio = False

def limpiar_comando(texte):
    global WAKE_WORD
    t = texte.lower().strip()
    
    # Limpieza des tics de langage, hésitations et politesses superflues au début/fin
    hesitations = ["euh", "hein", "ouais", "bah", "ah", "alors", "du coup", "s'il te plaît", "sil te plait", "s'il vous plaît", "sil vous plait", "merci"]
    
    # Nettoyage au début
    words = t.split()
    while words and words[0] in hesitations:
        words.pop(0)
    t = " ".join(words)
    
    w = WAKE_WORD.lower().strip()
    for variante in [w + ",", w]:
        if t.startswith(variante):
            t = t[len(variante):].strip()
            
    # Nettoyage à la fin après avoir retiré le wake word
    words = t.split()
    while words and words[-1] in hesitations:
        words.pop()
    t = " ".join(words)
    
    return t

WAKE_WORD       = _cargar_config().get("wake_word", "jarvis").lower().strip()
SESSION_TIMEOUT = 30
STOP_PARLER      = False
MIC_MUTED        = False
is_listening     = False
is_speaking      = False
jarvis_actif     = False
dernier_message  = 0
interface_deja_connectee = False


# ══════════════════════════════════════════════════════════════
#  DÉTECTION MICROPHONE — Énumération + Fallback automatique
# ══════════════════════════════════════════════════════════════

def _guardar_config(data: dict) -> None:
    """Sauvegarde les données dans jarvis_config.json."""
    try:
        import json
        cfg = _cargar_config()
        cfg.update(data)
        with open(_JARVIS_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[MIC] Impossible de sauvegarder la config : {e}")

# ── Boucle asynchrone de vérification des rappels ─────────────────────────────
async def boucle_rappels():
    """Vérifie en arrière-plan si des rappels enregistrés sont arrivés à échéance."""
    while True:
        try:
            cfg = _cargar_config()
            reminders = cfg.get("reminders", [])
            
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            current_date = now.strftime("%Y-%m-%d")
            
            modifie = False
            for r in reminders:
                if not r.get("triggered", False):
                    r_time = r.get("time") # "14:00"
                    r_date = r.get("date") # "2026-06-18" ou None/vide
                    
                    if r_time == current_time:
                        if not r_date or r_date == current_date:
                            r["triggered"] = True
                            modifie = True
                            
                            # Diffuser l'alerte
                            msg = json.dumps({
                                "type": "reminder_trigger",
                                "id": r["id"],
                                "text": r["text"],
                                "time": r_time,
                                "date": r_date or "Tous les jours"
                            })
                            print(f"[RAPPELS] Déclenchement du rappel : {r['text']}")
                            if CONNECTED_CLIENTS:
                                asyncio.ensure_future(asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS], return_exceptions=True))
                            
                            asyncio.create_task(hablar(f"Rappel, Christopher. C'est l'heure de : {r['text']}."))
            
            if modifie:
                _guardar_config({"reminders": reminders})
                if CONNECTED_CLIENTS:
                    msg_settings = json.dumps({"type": "settings_data", "data": _cargar_config()})
                    asyncio.ensure_future(asyncio.gather(*[ws.send(msg_settings) for ws in CONNECTED_CLIENTS], return_exceptions=True))
                    
        except Exception as e:
            print(f"[RAPPELS] Error boucle : {e}")
            
        await asyncio.sleep(15)

# ── Protection Antivirus en temps réel (LIVE) ───────────────────────────────
AV_LIVE_PROTECTION_ENABLED = False
AV_LIVE_REPORTED_THREATS = set()

async def boucle_antivirus_live():
    """Surveille les dossiers sensibles et processus actifs toutes les 3 secondes."""
    global AV_LIVE_PROTECTION_ENABLED, AV_LIVE_REPORTED_THREATS
    import json
    import os
    import time
    import stat
    import shutil
    import psutil
    from antivirus_scanner import is_file_suspicious, get_exclusions, is_excluded

    # Charger l'état initial depuis la config
    try:
        cfg = _cargar_config()
        AV_LIVE_PROTECTION_ENABLED = cfg.get("av_live_protection", False)
    except Exception:
        AV_LIVE_PROTECTION_ENABLED = False

    print(f"[AV LIVE] Protection en temps réel initialisée : {'ACTIVO' if AV_LIVE_PROTECTION_ENABLED else 'INACTIVO'}")

    last_check_time = time.time()

    while True:
        try:
            if AV_LIVE_PROTECTION_ENABLED:
                folders = [
                    os.path.expanduser("~/Desktop"),
                    os.path.expanduser("~/Downloads"),
                    os.environ.get("TEMP"),
                    os.environ.get("TMP"),
                    os.path.dirname(os.path.abspath(__file__))
                ]
                folders = list(set([os.path.abspath(f) for f in folders if f and os.path.exists(f)]))
                exclusions = get_exclusions()
                current_time = time.time()

                # 1. Surveillance des fichiers physiques
                for folder in folders:
                    try:
                        for file in os.listdir(folder):
                            filepath = os.path.join(folder, file)
                            if os.path.isfile(filepath):
                                try:
                                    mtime = os.path.getmtime(filepath)
                                    if mtime > last_check_time:
                                        normalized_filepath = os.path.normpath(filepath).lower()
                                        if normalized_filepath in AV_LIVE_REPORTED_THREATS:
                                            continue

                                        t_class, t_desc = is_file_suspicious(filepath)
                                        if t_class:
                                            if is_excluded(filepath, exclusions):
                                                continue

                                            AV_LIVE_REPORTED_THREATS.add(normalized_filepath)
                                            print(f"[AV LIVE] Menace détectée : {filepath} ({t_class})")

                                            # Tenter d'arrêter les processus verrouillant le fichier
                                            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                                                try:
                                                    exe_path = proc.info.get('exe')
                                                    if exe_path and os.path.normpath(exe_path).lower() == normalized_filepath:
                                                        print(f"[AV LIVE] Arrêt du processus {proc.info['name']} (PID {proc.info['pid']})")
                                                        p = psutil.Process(proc.info['pid'])
                                                        p.terminate()
                                                        try:
                                                            p.wait(timeout=1.0)
                                                        except psutil.TimeoutExpired:
                                                            p.kill()
                                                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                                                    pass

                                            # Rendre le fichier modifiable/supprimable
                                            try:
                                                os.chmod(filepath, stat.S_IWRITE)
                                            except Exception:
                                                pass

                                            # Déplacer vers quarantaine
                                            quarantine_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quarantine")
                                            os.makedirs(quarantine_dir, exist_ok=True)
                                            safe_name = f"{int(time.time())}_{file}.quarantine"
                                            dest = os.path.join(quarantine_dir, safe_name)
                                            shutil.move(filepath, dest)

                                            # Alerte WebSocket
                                            msg = {
                                                "type": "av_live_threat_intercepted",
                                                "threat": {
                                                    "type": "file",
                                                    "name": file,
                                                    "target": filepath,
                                                    "class": t_class,
                                                    "desc": f"INTERCEPTÉ & SÉCURISÉ. {t_desc}"
                                                },
                                                "quarantine_file": safe_name
                                            }
                                            if CONNECTED_CLIENTS:
                                                asyncio.ensure_future(asyncio.gather(*[ws.send(json.dumps(msg)) for ws in CONNECTED_CLIENTS], return_exceptions=True))

                                            # Notification vocale
                                            asyncio.create_task(hablar(f"Alerte sécurité, {USER_NAME}. J'ai détecté et neutralisé une menace en temps réel : {file}. Le fichier suspect a été placé en quarantaine."))
                                except OSError:
                                    pass
                    except Exception as e:
                        print(f"[AV LIVE] Error dossier {folder} : {e}")

                # 2. Surveillance des processus actifs suspects
                for proc in psutil.process_iter(['pid', 'name', 'exe']):
                    try:
                        pid = proc.info.get('pid')
                        name = proc.info.get('name') or ''
                        exe = proc.info.get('exe') or ''
                        
                        target_key = f"PID {pid} ({exe})"
                        normalized_exe = os.path.normpath(exe).lower() if exe else ""
                        
                        if target_key in AV_LIVE_REPORTED_THREATS or (normalized_exe and normalized_exe in AV_LIVE_REPORTED_THREATS):
                            continue
                            
                        name_lower = name.lower()
                        exe_lower = exe.lower()
                        
                        detected = False
                        desc = ""
                        if "mimikatz" in name_lower or "miner.exe" in name_lower or "keylogger" in name_lower:
                            detected = True
                            desc = "Processus suspect (menace connue)"
                        elif ("temp" in exe_lower or "tmp" in exe_lower) and name_lower.endswith((".exe", ".bat")):
                            if ("docker" in name_lower and "installer" in name_lower) or name_lower == "7zr.exe":
                                detected = False
                            else:
                                detected = True
                                desc = "Processus actif lancé depuis le dossier temporaire"
                            
                        if detected:
                            if is_excluded(target_key, exclusions) or (exe and is_excluded(exe, exclusions)):
                                continue
                                
                            AV_LIVE_REPORTED_THREATS.add(target_key)
                            print(f"[AV LIVE] Processus suspect neutralisé : {name} (PID {pid})")
                            
                            # Arrêter le processus
                            p = psutil.Process(pid)
                            p.terminate()
                            try:
                                p.wait(timeout=1.0)
                            except psutil.TimeoutExpired:
                                p.kill()
                                
                            # Alerte WebSocket
                            msg = {
                                "type": "av_live_threat_intercepted",
                                "threat": {
                                    "type": "process",
                                    "name": name,
                                    "target": target_key,
                                    "class": "Suspicious.ActiveProcess",
                                    "desc": f"PROCESSUS ARRÊTÉ & NEUTRALISÉ. {desc}"
                                }
                            }
                            if CONNECTED_CLIENTS:
                                asyncio.ensure_future(asyncio.gather(*[ws.send(json.dumps(msg)) for ws in CONNECTED_CLIENTS], return_exceptions=True))
                                
                            asyncio.create_task(hablar(f"Sécurité système, {USER_NAME}. J'ai intercepté et arrêté un processus suspect actif : {name}."))
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                last_check_time = current_time
        except Exception as e:
            print(f"[AV LIVE] Error boucle principale : {e}")
            
        await asyncio.sleep(3)

def detecter_microphone() -> int | None:
    """
    Détecte le meilleur microphone disponible.

    Stratégie :
      1. Essaie l'index mémorisé dans jarvis_config.json
      2. Essaie le micro par défaut du système (index None)
      3. Parcourt tous les périphériques d'entrée disponibles
      4. Sauvegarde l'index retenu pour le prochain lancement

    Retourne l'index (int) du micro retenu, ou None si aucun trouvé
    (dans ce cas sr.Microphone() utilisera le défaut OS).
    """
    import json

    # ── Lister tous les périphériques PyAudio ────────────────
    if pyaudio:
        try:
            p = pyaudio.PyAudio()
            nb = p.get_device_count()
            inputs = []
            print("[MIC] Périphériques audio détectés :")
            for i in range(nb):
                try:
                    info = p.get_device_info_by_index(i)
                    if info.get("maxInputChannels", 0) > 0:
                        nom = info.get("name", f"Périphérique {i}")
                        inputs.append((i, nom))
                        print(f"      [{i}] {nom}")
                except Exception:
                    pass
            p.terminate()

            if not inputs:
                print("[MIC] ⚠ Aucun périphérique d'entrée détecté par PyAudio.")
        except Exception as e:
            print(f"[MIC] Impossible de lister les périphériques : {e}")
            inputs = []
    else:
        inputs = []
        print("[MIC] PyAudio absent — mode fallback speech_recognition uniquement.")

    # ── Récupérer l'index mémorisé ───────────────────────────
    cfg = _cargar_config()
    index_memo = cfg.get("mic_device_index", None)

    # ── Fonction de test d'un index ──────────────────────────
    def _tester_index(idx):
        """Retourne True si sr.Microphone(device_index=idx) s'ouvre correctement."""
        try:
            kwargs = {} if idx is None else {"device_index": idx}
            mic_test = sr.Microphone(**kwargs)
            r_test = sr.Recognizer()
            with mic_test as src:
                r_test.adjust_for_ambient_noise(src, duration=0.3)
            return True
        except Exception as e:
            label = "défaut" if idx is None else str(idx)
            print(f"[MIC]   Index {label} → KO ({e})")
            return False

    # ── Priorité 1 : index mémorisé ──────────────────────────
    if index_memo is not None:
        nom_memo = next((n for i, n in inputs if i == index_memo), f"Index {index_memo}")
        print(f"[MIC] Test du micro mémorisé : [{index_memo}] {nom_memo}")
        if _tester_index(index_memo):
            print(f"[MIC] ✔ Micro retenu (mémorisé) : [{index_memo}] {nom_memo}")
            return index_memo
        else:
            print(f"[MIC] Micro mémorisé introuvable, recherche d'un remplaçant…")

    # ── Priorité 2 : micro par défaut OS ─────────────────────
    print("[MIC] Test du micro par défaut système…")
    if _tester_index(None):
        # Identifier son index réel si possible
        idx_reel = None
        if pyaudio:
            try:
                p = pyaudio.PyAudio()
                idx_reel = p.get_default_input_device_info().get("index", None)
                p.terminate()
            except Exception:
                pass
        nom_defaut = next((n for i, n in inputs if i == idx_reel), "Défaut système")
        print(f"[MIC] ✔ Micro retenu (défaut) : [{idx_reel}] {nom_defaut}")
        _guardar_config({"mic_device_index": idx_reel})
        return idx_reel

    # ── Priorité 3 : parcourir tous les périphériques ────────
    print("[MIC] Recherche sur tous les périphériques disponibles…")
    for idx, nom in inputs:
        print(f"[MIC]   Test [{idx}] {nom}…")
        if _tester_index(idx):
            print(f"[MIC] ✔ Micro retenu (fallback) : [{idx}] {nom}")
            _guardar_config({"mic_device_index": idx})
            return idx

    # ── Aucun micro fonctionnel ───────────────────────────────
    print("[MIC] ⚠ Aucun microphone fonctionnel trouvé.")
    print("[MIC]   Vérifiez que tu micro est branché et autorisé dans")
    print("[MIC]   Paramètres Windows → Confidentialité → Microphone.")
    _guardar_config({"mic_device_index": None})
    return None

def ecouter():
    global is_listening, jarvis_actif, dernier_message, STOP_PARLER, is_speaking, MIC_NEED_RELOAD

    r   = sr.Recognizer()

    # ── Détection automatique du micro ───────────────────────
    mic_index = detecter_microphone()
    if mic_index is not None:
        mic = sr.Microphone(device_index=mic_index)
        print(f"[JARVIS] Microphone sélectionné : index {mic_index}")
    else:
        mic = sr.Microphone()
        print("[JARVIS] Microphone : périphérique par défaut système")

    # -- Réglages de patience (Patience de l'écoute) --
    r.pause_threshold        = 0.8  # Temps de silence autorisé (en s) avant de couper (ajusté pour un confort naturel et rapide)
    r.non_speaking_duration  = 0.6  # Durée de silence minimale pour valider (ajusté pour un confort naturel et rapide)
    r.energy_threshold       = 300  # Sensibilité au bruit
    r.dynamic_energy_threshold = True

    # ── Calibration bruit ambiant ─────────────────────────────
    try:
        with mic as source:
            r.adjust_for_ambient_noise(source, duration=1)
    except Exception as e:
        print(f"[MIC] ⚠ Calibration impossible : {e}")
        # Retenter avec le micro par défaut
        mic = sr.Microphone()
        try:
            with mic as source:
                r.adjust_for_ambient_noise(source, duration=1)
        except Exception:
            pass

    print("[JARVIS] Microphone pret. En attente de 'Jarvis' ou session active...")

    while True:
        try:
            # JARVIS EN TRAIN DE PARLER — pause silencieuse pour éviter le larsen/feedback
            if is_speaking:
                time.sleep(0.2)
                continue

            # MICRO COUPÉ — pause silencieuse
            if MIC_MUTED:
                time.sleep(0.3)
                continue

            # CHANGEMENT DE MICRO demandé depuis les paramètres
            if MIC_NEED_RELOAD:
                MIC_NEED_RELOAD = False
                _forced = MIC_FORCED_INDEX
                MIC_FORCED_INDEX = None
                if _forced is not None:
                    # Index imposé explicitement par l'utilisateur — application directe
                    try:
                        _mic_test = sr.Microphone(device_index=_forced)
                        with _mic_test as _src:
                            r.adjust_for_ambient_noise(_src, duration=0.3)
                        mic = _mic_test
                        print(f"[MIC] ✔ Micro changé vers index forcé : {_forced}")
                    except Exception as _e:
                        print(f"[MIC] ⚠ Index forcé {_forced} KO ({_e}), repli sur détection auto")
                        _auto_idx = detecter_microphone()
                        mic = sr.Microphone(device_index=_auto_idx) if _auto_idx is not None else sr.Microphone()
                else:
                    # Reload standard (micro débranché, etc.)
                    new_idx = detecter_microphone()
                    mic = sr.Microphone(device_index=new_idx) if new_idx is not None else sr.Microphone()
                    try:
                        with mic as source:
                            r.adjust_for_ambient_noise(source, duration=0.5)
                    except Exception:
                        pass
                    print(f"[MIC] Micro rechargé → index {new_idx}")
                continue

            # Mise à jour en direct de la sensibilité (seuil d'énergie) et du mode dynamique
            try:
                cfg = _cargar_config()
                dynamic_sens = cfg.get("mic_dynamic_sensitivity", True)
                sens = cfg.get("mic_sensitivity", 300)
                
                if r.dynamic_energy_threshold != dynamic_sens:
                    r.dynamic_energy_threshold = dynamic_sens
                    print(f"[MIC] Sensibilité dynamique mise à jour : {dynamic_sens}")
                
                if not dynamic_sens:
                    if r.energy_threshold != sens:
                        r.energy_threshold = sens
                        print(f"[MIC] Sensibilité manuelle (seuil d'énergie) mise à jour : {sens}")
                else:
                    if r.energy_threshold < sens:
                        r.energy_threshold = sens
            except Exception as _cfg_err:
                print(f"[MIC] Error lecture config sensibilité : {_cfg_err}")

            # GESTION DU TIMEOUT DE SESSION
            if jarvis_actif and (time.time() - dernier_message > SESSION_TIMEOUT):
                print("[JARVIS] Timeout session. Retour en veille.")
                jarvis_actif = False

            try:
                with mic as source:
                    is_listening = True
                    state = "active" if jarvis_actif else "listening"
                    send_web_broadcast_sync({"action": "set_state", "state": state})
                    if jarvis_actif:
                        send_web_broadcast_sync({"action": "user_listening"})
                    
                    audio = r.listen(source, timeout=2, phrase_time_limit=15)
                    
                    is_listening = False
                    send_web_broadcast_sync({"action": "set_state", "state": "thinking"})
            except sr.WaitTimeoutError:
                is_listening = False
                raise  # Re-lever pour le gestionnaire WaitTimeoutError existant
            except (OSError, AttributeError, ValueError) as _mic_hw_err:
                is_listening = False
                _err_str = str(_mic_hw_err)
                if any(k in _err_str for k in ["Invalid input device", "No Default Input", "unanticipated", "[Errno"]):
                    print(f"[MIC] ⚠ Périphérique audio invalide/perdu ({_mic_hw_err}) — rechargement demandé")
                    MIC_NEED_RELOAD = True
                    time.sleep(1)
                    continue
                raise

            # ── Transcription — Nemotron ASR (local) ou Google (cloud) ──
            raw_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
            
            # Filtrage par durée minimale de 0.5s pour éviter les micro-bruits
            audio_duration = len(raw_data) / 32000.0
            if audio_duration < 0.5:
                print(f"[ASR] Segment ignoré (trop court : {audio_duration:.2f}s)")
                send_web_broadcast_sync({"action": "set_state", "state": "idle"})
                continue

            # Vérification de l'énergie moyenne du segment (RMS) pour éliminer les bruits/souffles
            try:
                import numpy as _np
                _pcm = _np.frombuffer(raw_data, dtype=_np.int16).astype(_np.float32)
                rms_energy = int(_np.sqrt(_np.mean(_pcm ** 2))) if len(_pcm) > 0 else 0
            except Exception:
                rms_energy = 9999  # Fallback si numpy indisponible
            
            print(f"[ASR] Énergie moyenne du segment : {rms_energy} (seuil minimum : 250)")
            if rms_energy < 250:
                print("[ASR] Segment ignoré (bruit ou silence sous le seuil)")
                send_web_broadcast_sync({"action": "set_state", "state": "idle"})
                continue
                
            if NEMOTRON_ASR_ENABLED and _nemotron_instance is not None:
                texte = _nemotron_instance.transcrire(raw_data, sample_rate=16000).lower().strip()
            else:
                texte = r.recognize_google(audio, language="fr-FR").lower().strip()
                
            if not texte:
                send_web_broadcast_sync({"action": "set_state", "state": "idle"})
                continue  # Transcription vide — on ignore
                
            print(f"[ENTENDU] {texte}")

            # GESTION INTERRUPTION DURANT LA PAROLE
            if is_speaking and ("tais-toi" in texte or "silence" in texte or "tais toi" in texte):
                STOP_PARLER = True
                continue

            # MOTS-CLÉS DE SOMMEIL
            SLEEP_WORDS = ["merci", "ce sera tout", "repos", "au revoir", "silence", "tais-toi", "tais toi"]
            if any(word in texte for word in SLEEP_WORDS):
                if jarvis_actif:
                    jarvis_actif = False
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(hablar("A tu service Christopher. Je me mets en veille."))
                    loop.close()
                continue

            # Détection du mot-clé avec vérification stricte (mot entier) pour éviter les déclenchements accidentels
            wake_word_detected = False
            if WAKE_WORD in texte:
                if re.search(r'\b' + re.escape(WAKE_WORD) + r'\b', texte):
                    wake_word_detected = True

            if wake_word_detected or jarvis_actif:
                # Envoi de la transcription de l'utilisateur au frontend
                send_web_broadcast_sync({"action": "user_speech", "text": texte})

                if wake_word_detected:
                    print("[JARVIS] Mot-clé détecté.")
                    jarvis_actif = True
                
                dernier_message = time.time()
                commande = limpiar_comando(texte)
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                if commande:
                    # Une commande a été reçue -> on désactive la veille prolongée immédiatement 
                    # pour éviter d'écouter les bruits de fond après l'exécution.
                    jarvis_actif = False
                    action_pc = ejecutar_accion_pc(commande)
                    if action_pc:
                        loop.run_until_complete(hablar(action_pc))
                    else:
                        loop.run_until_complete(procesar_respuesta_ia(commande))
                else:
                    if wake_word_detected: # "Jarvis" tout seul
                        loop.run_until_complete(hablar("Oui Christopher, je vous écoute."))
                
                loop.close()
            else:
                pass

        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except OSError as e:
            # Micro débranché ou périphérique perdu — on tente de le relancer
            print(f"[MIC] ⚠ Périphérique audio perdu ({e}). Tentative de récupération…")
            time.sleep(2)
            try:
                mic_index = detecter_microphone()
                if mic_index is not None:
                    mic = sr.Microphone(device_index=mic_index)
                else:
                    mic = sr.Microphone()
                with mic as source:
                    r.adjust_for_ambient_noise(source, duration=0.5)
                print("[MIC] ✔ Microphone récupéré avec succès.")
            except Exception as e2:
                print(f"[MIC] Impossible de récupérer le microphone : {e2}")
                time.sleep(3)
        except Exception as e:
            print(f"Error écoute : {e}")
            time.sleep(1)

def monitor_claps():
    if not pyaudio:
        print("[CLAP] PyAudio absent — detection des applaudissements desactivee.")
        return
    try:
        import numpy as _np_clap
        p = pyaudio.PyAudio()
        # On ouvre le flux
        # Utiliser le même micro que la détection vocale
        cfg_clap = _cargar_config()
        mic_idx_clap = cfg_clap.get("mic_device_index", None)
        open_kwargs = dict(format=pyaudio.paInt16, channels=1, rate=44100,
                          input=True, frames_per_buffer=1024)
        if mic_idx_clap is not None:
            open_kwargs["input_device_index"] = mic_idx_clap
        stream = p.open(**open_kwargs)
        print("[CLAP] Detección de aplausos activada.")
        
        print("[CLAP] Détection des doubles applaudissements activée.")
        
        last_clap_time = 0
        
        while True:
            try:
                data = stream.read(1024, exception_on_overflow=False)
                _pcm_clap = _np_clap.frombuffer(data, dtype=_np_clap.int16).astype(_np_clap.float32)
                rms = int(_np_clap.sqrt(_np_clap.mean(_pcm_clap ** 2))) if len(_pcm_clap) > 0 else 0
                
                # ON IGNORE LE CLAP UNIQUEMENT SI LE MODE IRON MAN EST ÉTEINT OU SI JARVIS PARLE
                if not MODE_IRON_MAN or is_speaking or is_thinking:
                    last_clap_time = 0
                    continue

                if rms > CLAP_THRESHOLD:
                    current_time = time.time()
                    diff = current_time - last_clap_time
                    
                    if 0.1 < diff < 0.8:
                        global VIDEO_LANCEE
                        print(f"\n[CLAP] !!! DOUBLE CLAP DÉTECTÉ !!!")
                        entity_id = PIECES_LUMIERES.get("salon", "light.salon")
                        
                        # On vérifie l'état actuel
                        etat_actuel = ha_get_etat(entity_id)
                        
                        if etat_actuel != "on":
                            # ON ALLUME
                            print(f"[CLAP] Acción : ENCENDER")
                            ha_lumiere(entity_id, "on")
                            
                            if not VIDEO_LANCEE:
                                print(f"[CLAP] Lanzamiento inicial del video...")
                                webbrowser.open("https://www.youtube.com/watch?v=KU5V5WZVcVE")
                                VIDEO_LANCEE = True
                                def seq():
                                    time.sleep(5)
                                    pyautogui.press('f')
                                threading.Thread(target=seq, daemon=True).start()
                            else:
                                print(f"[CLAP] Reanudación del video (Play)...")
                                pyautogui.press('k')
                        else:
                            # ON ÉTEINT
                            print(f"[CLAP] Acción : APAGAR")
                            ha_lumiere(entity_id, "off")
                            if VIDEO_LANCEE:
                                print(f"[CLAP] Pausa del video...")
                                pyautogui.press('k')
                            
                        # Gros debounce après une action réussie
                        time.sleep(3.0)
                        last_clap_time = 0 # Reset
                    else:
                        # C'est peut-être le premier clap
                        last_clap_time = current_time
            except Exception as e:
                # Si erreur de lecture (ex: micro débranché), on attend et on continue
                time.sleep(0.5)
                continue

    except Exception as e:
        print(f"[CLAP] Error fatale détection claps : {e}")

def verifier_mises_a_jour():
    """Vérifie si une nouvelle version est disponible sur le serveur."""
    global DERNIERE_MAJ_INFO
    try:
        print(f"[UPDATE] Verification des mises a jour...")
        response = requests.get(UPDATE_JSON_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            remote_version = data.get("version", "4.0")
            
            # Comparaison de version
            if remote_version > CURRENT_VERSION:
                print(f"[UPDATE] NUEVA VERSIÓN DETECTADA : {remote_version}")
                DERNIERE_MAJ_INFO = {
                    "type": "update_available",
                    "version": remote_version,
                    "url": data.get("download_url", "https://www.techenclair.fr/pages/jarvis"),
                    "changelog": data.get("changelog", "")
                }
            else:
                print(f"[UPDATE] Systeme a jour (v{CURRENT_VERSION})")
                DERNIERE_MAJ_INFO = None
        else:
            print(f"[UPDATE] Servidor inalcanzable (Status: {response.status_code})")
    except Exception as e:
        print(f"[UPDATE] Error lors de la verification : {e}")

def verifier_mises_a_jour_loop():
    """Boucle de vérification périodique (toutes les 4 heures)."""
    while True:
        time.sleep(14400)
        verifier_mises_a_jour()

def start_ia():
    threading.Thread(target=monitor_claps, daemon=True).start()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def start_ws():
        global WEB_LOOP
        WEB_LOOP = asyncio.get_running_loop()
        print(f"[WEB] Servidor WebSocket iniciado sur ws://0.0.0.0:8765")
        print(f"[WEB] Accesible desde la red : ws://{LOCAL_IP}:8765")
        
        # Lancer le monitoring système en arrière-plan
        asyncio.create_task(broadcast_system_stats())
        
        # Lancer la boucle de vérification des rappels
        asyncio.create_task(boucle_rappels())

        # Lancer la boucle de protection antivirus en temps réel
        asyncio.create_task(boucle_antivirus_live())
        
        async with websockets.serve(ws_handler, "0.0.0.0", 8765):
            await asyncio.Future()

    threading.Thread(target=lambda: asyncio.run(start_ws()), daemon=True).start()

    # Message d'accueil personnalisé et dynamique au démarrage (surtout pour Fenrir)
    cfg = _cargar_config()
    voix_choisie = cfg.get("voice", "male")
    if voix_choisie == "gemini_fenrir":
        import random
        greetings = [
            f"Hola {USER_NAME}, comment vas-tu aujourd'hui ?",
            f"Hola {USER_NAME}, j'espère que tu as passé une bonne nuit. Que faisons-nous aujourd'hui ?",
            f"Hola {USER_NAME}. Ravi de te retrouver. J'espère que tout se passe bien pour toi.",
            f"Hola {USER_NAME}. Protocoles opérationnels. Je suis prêt à t'assister pour cette journée.",
            f"Salut {USER_NAME} ! Prêt pour une nouvelle session de travail ?",
            f"Hola {USER_NAME}. Content de te revoir. J'espère que tout va pour le mieux aujourd'hui !",
            f"Hola {USER_NAME}. Je suis en ligne. Comment puis-je t'aider en ce moment ?"
        ]
        startup_msg = random.choice(greetings)
    else:
        startup_msg = f"Hola, {USER_NAME}"

    loop.run_until_complete(hablar(startup_msg))
    loop.close()
    ecouter()

# ==========================================
# LANCEMENT — MODE CONSOLE + FRONTEND WEB
# ==========================================
# Ursina desactive : l'interface est maintenant le frontend Three.js
# dans le dossier frontend/ (npm run dev -> http://localhost:5173)
# Le WebSocket est deja demarre par start_ia() sur ws://localhost:8765

if pygame:
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
else:
    print("[INFO] Pygame absent — demarrage sans audio TTS.")

def start_mobile_http_server():
    """Serveur HTTP multi-thread pour servir l'interface mobile sur le port 8000.
    
    Le serveur est multi-thread (ThreadingHTTPServer) pour gérer les requêtes
    parallèles des navigateurs mobiles sans bloquer (CSS, JS, HTML en simultané).
    Lance aussi un serveur de redirection sur le port 80 :
      → http://192.168.1.23  redirige automatiquement vers http://192.168.1.23:8000
    """
    import http.server
    import socketserver
    mobile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mobile")
    if not os.path.exists(mobile_dir):
        print("[MOBILE] Dossier mobile/ introuvable, serveur non demarre.")
        return

    class MóvilHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=mobile_dir, **kwargs)
        def log_message(self, format, *args):
            pass  # Silencieux

    class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        """Serveur HTTP multi-thread — chaque requête est traitée dans son propre thread."""
        daemon_threads = True  # Les threads s'arrêtent proprement avec le programme

    # ── Serveur principal sur :8000 ─────────────────────────────────────────
    server = ThreadingHTTPServer(("0.0.0.0", 8000), MóvilHandler)
    print(f"[MOBILE] Serveur HTTP demarre sur http://{LOCAL_IP}:8000")

    # ── Redirection automatique depuis le port 80 → 8000 ───────────────────
    # Permet de taper juste l'IP sur le téléphone sans mettre :8000
    class RedirectHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            target = f"http://{LOCAL_IP}:8000{self.path}"
            self.send_response(301)
            self.send_header("Location", target)
            self.end_headers()
        def log_message(self, format, *args):
            pass  # Silencieux

    def _start_redirect_server():
        try:
            redirect_server = ThreadingHTTPServer(("0.0.0.0", 80), RedirectHandler)
            print(f"[MOBILE] Redirection port 80 → 8000 active (tapez juste l'IP sur mobile)")
            redirect_server.serve_forever()
        except OSError as e:
            # Port 80 peut nécessiter des droits admin — pas bloquant
            print(f"[MOBILE] Redirection port 80 non disponible (droits insuffisants) : {e}")
            print(f"[MOBILE] Sur mobile, utilisez http://{LOCAL_IP}:8000")

    threading.Thread(target=_start_redirect_server, daemon=True).start()
    server.serve_forever()

def liberer_port(port):
    """Tue le processus qui occupe le port donné (Windows)."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True
        )
        stdout = result.stdout.decode(errors='ignore')
        for line in stdout.splitlines():
            if f":{port}" in line and ("LISTENING" in line or "ÉCOUTE" in line):
                parts = line.strip().split()
                pid = parts[-1]
                if pid.isdigit() and int(pid) != os.getpid():
                    subprocess.run(["taskkill", "/F", "/PID", pid],
                                   capture_output=True)
                    print(f"[DÉMARRAGE] Port {port} libéré (PID {pid} terminé).")
                    return
    except Exception as e:
        print(f"[DÉMARRAGE] Impossible de libérer le port {port} : {e}")

# ── NETTOYAGE CACHE WEBVIEW (anti-cache après mise à jour) ─────────────────
def vider_cache_webview_si_nouvelle_version():
    """
    Supprime le cache WebView2 (EBWebView/Default/*) si la version
    enregistrée dans un fichier marqueur est différente de CURRENT_VERSION.
    Cela force le rechargement complet de l'interface après une mise à jour.
    """
    import shutil
    app_dir = os.path.dirname(os.path.abspath(__file__))
    marker_file = os.path.join(app_dir, ".jarvis_cache_version")

    # Lire la version précédente
    version_en_cache = None
    try:
        if os.path.exists(marker_file):
            with open(marker_file, "r", encoding="utf-8") as f:
                version_en_cache = f.read().strip()
    except Exception:
        pass

    if version_en_cache == CURRENT_VERSION:
        # Même version → rien à faire
        return

    # Nouvelle version ou premier lancement → vider le cache WebView2
    print(f"[CACHE] Version changée ({version_en_cache} → {CURRENT_VERSION}) : nettoyage du cache WebView2...")

    # Le cache pywebview est dans %APPDATA%\pywebview\EBWebView\Default\
    appdata = os.environ.get("APPDATA", "")
    webview_data_dir = os.path.join(appdata, "pywebview", "EBWebView", "Default")

    # Sous-dossiers à supprimer (cache pur, pas les données utilisateur critiques)
    cache_folders = [
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
        for folder in cache_folders:
            target = os.path.join(webview_data_dir, folder)
            if os.path.isdir(target):
                try:
                    shutil.rmtree(target)
                    print(f"[CACHE]   ✓ Supprimé : {folder}")
                except Exception as e:
                    print(f"[CACHE]   ✗ Error sur {folder} : {e}")
        print("[CACHE] Cache WebView2 nettoyé avec succès.")
    else:
        print("[CACHE] Dossier WebView2 introuvable — probablement premier lancement.")

    # Mettre à jour le marqueur de version
    try:
        with open(marker_file, "w", encoding="utf-8") as f:
            f.write(CURRENT_VERSION)
    except Exception as e:
        print(f"[CACHE] Impossible d'écrire le marqueur de version : {e}")


def vider_cache_webview_complet():
    """
    Vide intégralement le cache WebView2 (appelé manuellement via le bouton frontend).
    Retourne True si succès, False sinon.
    """
    import shutil
    appdata = os.environ.get("APPDATA", "")
    webview_data_dir = os.path.join(appdata, "pywebview", "EBWebView", "Default")
    cache_folders = [
        "Cache",
        "Code Cache",
        "Service Worker",
        "GPUCache",
        "DawnGraphiteCache",
        "DawnWebGPUCache",
        "blob_storage",
        "Session Storage",
    ]
    success = True
    if os.path.isdir(webview_data_dir):
        for folder in cache_folders:
            target = os.path.join(webview_data_dir, folder)
            if os.path.isdir(target):
                try:
                    shutil.rmtree(target)
                    print(f"[CACHE] Manuel — Supprimé : {folder}")
                except Exception as e:
                    print(f"[CACHE] Manuel — Error : {folder} : {e}")
                    success = False
    # Réinitialiser le marqueur pour forcer un rechargement au prochain lancement
    app_dir = os.path.dirname(os.path.abspath(__file__))
    marker_file = os.path.join(app_dir, ".jarvis_cache_version")
    try:
        if os.path.exists(marker_file):
            os.remove(marker_file)
    except Exception:
        pass
    return success


def main():
    # Fix Windows AppUserModelID early to ensure correct taskbar icon
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TechEnClair.Jarvis.App")
        except Exception:
            pass

    # Fix Windows asyncio ProactorEventLoop concurrent-write crash
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Liberer les ports si une instance precedente tourne encore
    liberer_port(8765)
    liberer_port(8000)
    liberer_port(80)   # Redirection automatique port 80 → 8000

    # Lancer le serveur Frontend
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
    frontend_process = None
    FRONTEND_URL = "http://localhost:5173"

    def _port_ecoute(port, timeout=4.0):
        """Retourne True si quelque chose ecoute sur le port donne."""
        import socket
        debut = time.time()
        while time.time() - debut < timeout:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                    return True
            except (ConnectionRefusedError, OSError):
                time.sleep(0.2)
        return False

    def _servir_dist_python(port=5173):
        """Sert le dossier dist/ avec le serveur HTTP Python (fallback sans npm)."""
        import http.server, socketserver
        dist_dir = os.path.join(frontend_dir, "dist")
        os.chdir(dist_dir)
        handler = http.server.SimpleHTTPRequestHandler
        handler.log_message = lambda *a: None  # silencieux
        with socketserver.TCPServer(("", port), handler) as httpd:
            print(f"[JARVIS] Frontend servi via Python HTTP sur http://localhost:{port}")
            httpd.serve_forever()

    vite_ok = False
    if os.path.exists(frontend_dir):
        # Tentative 1 : Vite (npm run dev)
        try:
            print("[JARVIS] Tentative de lancement Vite (npm run dev)...")
            frontend_process = subprocess.Popen(
                ["npm", "run", "dev"], cwd=frontend_dir, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            vite_ok = _port_ecoute(5173, timeout=5.0)
            if vite_ok:
                print("[JARVIS] Vite demarre avec succes sur localhost:5173")
            else:
                print("[JARVIS] Vite n'a pas demarre (npm/vite absent ou erreur).")
                if frontend_process:
                    frontend_process.terminate()
                    frontend_process = None
        except Exception as e:
            print(f"[JARVIS] Impossible de lancer Vite : {e}")
            frontend_process = None

        # Tentative 2 : servir dist/ avec Python (pas besoin de npm)
        if not vite_ok:
            dist_dir = os.path.join(frontend_dir, "dist")
            if os.path.exists(dist_dir) and os.path.exists(os.path.join(dist_dir, "index.html")):
                print("[JARVIS] Fallback : service du dossier dist/ via Python HTTP...")
                t_dist = threading.Thread(target=_servir_dist_python, args=(5173,), daemon=True)
                t_dist.start()
                vite_ok = _port_ecoute(5173, timeout=3.0)
                if vite_ok:
                    print("[JARVIS] Frontend dist/ servi correctement.")
            else:
                print("[JARVIS] Aucun dossier dist/ trouve. Interface non disponible.")
                print("[JARVIS] Pour corriger : cd frontend && npm install && npm run build")

    if not vite_ok:
        print("[JARVIS] ATTENTION : l'interface visuelle ne sera pas disponible.")
        print("[JARVIS] JARVIS reste fonctionnel en mode vocal uniquement.")

    # Verification initiale des mises a jour
    verifier_mises_a_jour()
    
    # Lancer les services en arriere-plan
    threading.Thread(target=start_mobile_http_server, daemon=True).start()
    threading.Thread(target=start_ia, daemon=True).start()
    threading.Thread(target=verifier_mises_a_jour_loop, daemon=True).start()

    # Nettoyage automatique du cache WebView2 si version changée
    vider_cache_webview_si_nouvelle_version()

    # Limpieza de la console pour une UI épurée après le chargement des services
    def _nettoyer_console_demarrage():
        time.sleep(3.5)  # Attendre que les services aient fini d'imprimer
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 60)
        print("   J.A.R.V.I.S — Systeme En Ligne")
        print("=" * 60)
        print("  Interface PC    : " + FRONTEND_URL)
        print(f"  Interface Móvil: http://{LOCAL_IP}:8000")
        print()
        print("  Commandes vocales actives.")
        print("  Dites 'Jarvis' pour commencer.")
        print("=" * 60)
        print()
    
    threading.Thread(target=_nettoyer_console_demarrage, daemon=True).start()

    # Choisir le mode d'affichage
    if _WEBVIEW_OK and webview is not None:
        # MODE FENETRE NATIVE (pywebview)
        print("[JARVIS] Ouverture dans une fenetre native (pywebview)...")

        # Calcul de la taille et position centrée selon la résolution de l'écran
        try:
            from screeninfo import get_monitors
            _mon = get_monitors()[0]
            _sw, _sh = _mon.width, _mon.height
        except Exception:
            _sw, _sh = 1920, 1080

        # 85% de l'écran, min 1280x780
        _win_w = max(1280, int(_sw * 0.85))
        _win_h = max(780,  int(_sh * 0.85))
        _win_x = (_sw - _win_w) // 2
        _win_y = (_sh - _win_h) // 2

        window = webview.create_window(
            title            = "J.A.R.V.I.S",
            url              = FRONTEND_URL,
            width            = _win_w,
            height           = _win_h,
            x                = _win_x,
            y                = _win_y,
            resizable        = True,
            min_size         = (900, 600),
            background_color = "#0a0a0f",
        )
        global _WEBVIEW_WINDOW
        _WEBVIEW_WINDOW = window

        def _on_closed():
            print("\n[JARVIS] Fenetre fermee — extinction du systeme...")
            if frontend_process:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(frontend_process.pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            import os
            os._exit(0)

        window.events.closed += _on_closed

        def _on_loaded():
            try:
                import ctypes
                import os
                
                # Masquer complètement la console (SW_HIDE = 0)
                try:
                    hwnd_console = ctypes.windll.kernel32.GetConsoleWindow()
                    if hwnd_console:
                        ctypes.windll.user32.ShowWindow(hwnd_console, 0)
                except Exception:
                    pass

                # Remplacement de l'icone de la fenetre webview
                hwnd = ctypes.windll.user32.FindWindowW(None, "J.A.R.V.I.S")
                if hwnd:
                    icon_path = os.path.abspath("jarvis.ico")
                    if os.path.exists(icon_path):
                        hicon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x0010)
                        if hicon:
                            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon) # ICON_SMALL
                            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon) # ICON_BIG
                            
                # Associer la fenetre principale pour secure_browser et ajouter le redimensionnement automatique
                try:
                    import secure_browser
                    secure_browser._main_webview_window = window
                    
                    def on_main_window_resized(width, height):
                        secure_browser.resize_docked_window()
                    window.events.resized += on_main_window_resized
                    print("[JARVIS] Module de navigation securise connecte au redimensionnement.")
                except Exception as ex:
                    print(f"[JARVIS] Error initialisation secure_browser : {ex}")
                    
            except Exception as e:
                print(f"[JARVIS] Error chargement icone : {e}")

        window.events.loaded += _on_loaded

        # webview.start() DOIT etre appele depuis le thread principal
        try:
            webview.start(private_mode=False)
        except Exception as e:
            print(f"[JARVIS] PyWebView impossible : {e} — bascule sur navigateur")
            _ouvrir_dans_navigateur(FRONTEND_URL, frontend_process)
    else:
        # MODE NAVIGATEUR (fallback si pywebview absent)
        _ouvrir_dans_navigateur(FRONTEND_URL, frontend_process)


def _ouvrir_dans_navigateur(url, frontend_process):
    """
    Tente d'ouvrir l'URL en mode 'Application' (sans barres d'outils) 
    pour conserver l'aspect 'Application Dédiée'.
    """
    print(f"[JARVIS] Tentative d'ouverture en Mode App Dédiée sur {url}...")
    
    # Liste des navigateurs supportant le mode --app par ordre de préférence
    try:
        success = False
        # On tente msedge d'abord (présent sur tous les Windows 10/11) puis chrome
        for browser in ["msedge", "chrome"]:
            try:
                # La commande 'start' permet de lancer le processus indépendamment
                subprocess.Popen(f'start {browser} --app="{url}"', shell=True)
                print(f"[JARVIS] Interface lancée via {browser} (Mode App)")
                success = True
                break
            except:
                continue
        
        if success:
            _attendre_interface(frontend_process)
            return
    except Exception as e:
        print(f"[JARVIS] Error lancement Mode App : {e}")

    # Fallback ultime : Navigateur par défaut standard
    print("[JARVIS] Fallback : Ouverture dans le navigateur par défaut...")
    webbrowser.open(url)
    _attendre_interface(frontend_process)

def _attendre_interface(frontend_process):
    """Gère la boucle d'attente et l'extinction du système."""
    try:
        while True:
            time.sleep(1)
            # On ne ferme que si l'interface a été connectée au moins une fois
            if interface_deja_connectee and len(CONNECTED_CLIENTS) == 0:
                print("\n[JARVIS] Interfaz desconectada. Attente de reconnexion (60s)...")
                time.sleep(60)
                if len(CONNECTED_CLIENTS) == 0:
                    print("[JARVIS] Aucune reconnexion. Extinction automatique...")
                    break
                else:
                    print("[JARVIS] Reconnexion detectee. Reprise.")
    except KeyboardInterrupt:
        print("\n[JARVIS] Arret manuel.")

    if frontend_process:
        print("[JARVIS] Arret du serveur Web...")
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(frontend_process.pid)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

builtins.pedir_ia_vision = pedir_ia_vision
if __name__ == "__main__":
    main()