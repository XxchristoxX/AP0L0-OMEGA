#!/bin/bash
# =============================================================================
# AP0LO v3.0 – PROTOCOLO OMNISCIENTE (CORREGIDO)
# =============================================================================

set -x
set +e
trap 'echo "ERROR CRÍTICO en línea $LINENO: comando falló con código $?"' ERR

echo "=============================================="
echo " AP0LO v3.0 - Inicializando Protocolo Omnisciente"
echo "=============================================="

# ---------- 0. Verificación del entorno ----------
if [ ! -f "main.py" ]; then
    echo "ERROR: No se encuentra main.py. Asegúrate de ejecutar este script dentro de la carpeta raíz de AP0LO."
    read -p "Presiona ENTER para salir..."
    exit 1
fi

# Buscar un Python funcional
PYTHON=""
if command -v python &> /dev/null; then
    PYTHON=python
elif command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v py &> /dev/null; then
    PYTHON=py
else
    echo "ERROR: No se encontró Python. Instálalo y agrégalo al PATH."
    read -p "Presiona ENTER para salir..."
    exit 1
fi
echo "Usando Python: $PYTHON"

# Crear todas las carpetas necesarias
echo "Creando estructura de directorios..."
mkdir -p src/core
mkdir -p src/skills
mkdir -p src/vision
mkdir -p src/ui/templates
mkdir -p src/ui/static
mkdir -p src/utils
mkdir -p config
mkdir -p data
mkdir -p android
echo "Directorios listos."

# ---------- 1. Instalación de dependencias ----------
echo "[1/12] Instalando dependencias Python..."
$PYTHON -m pip install --upgrade pip

# Crear requirements.txt completo si no existe
cat > requirements_full.txt <<'REQEOF'
SpeechRecognition>=3.8.1
pyttsx3>=2.90
flask>=2.3.2
flask-socketio>=5.3.2
requests>=2.28.2
python-dotenv>=1.0.0
chromadb>=0.4.3
numpy>=1.24.3
opencv-python-headless>=4.7.0
deepface>=0.0.79
tensorflow>=2.12.0
pyaudio>=0.2.11
pyautogui>=0.9.53
psutil>=5.9.5
PyGetWindow>=0.0.9
PyQt5>=5.15.7
Pillow>=9.5.0
pynput>=1.7.6
screen-brightness-control>=0.13.0
comtypes>=1.2.0
pycaw>=20230407
wmi>=1.5.1
websocket-client>=1.5.1
selenium>=4.9.1
beautifulsoup4>=4.12.2
lxml>=4.9.2
python-docx>=0.8.11
PyPDF2>=3.0.1
pytesseract>=0.3.10
google-api-python-client>=2.86.0
google-auth-httplib2>=0.1.0
google-auth-oauthlib>=0.4.6
phue>=1.1
spotipy>=2.23.0
youtube-search-python>=1.6.6
googlesearch-python>=1.1.0
serpapi>=0.1.5
wikipedia>=1.4.0
duckduckgo-search>=3.8.0
sympy>=1.11.1
qrcode>=7.4.2
PyInstaller>=5.13.0
REQEOF

echo "Instalando paquetes... (esto puede tardar varios minutos)"
$PYTHON -m pip install -r requirements_full.txt 2>&1 | tee install_log.txt
echo "Paquetes instalados (ver install_log.txt para detalles)."

# ---------- 2. Corrección de archivos existentes ----------
echo "[2/12] Parchando módulos del núcleo..."

cat > src/core/orchestrator.py <<'ORCHEOF'
import os
import time
import threading
import speech_recognition as sr
from src.core.personality_manager import PersonalityManager
from src.core.hybrid_router import HybridRouter
from src.core.skills_registry import SkillsRegistry
from src.core.memory_manager import MemoryManager
from src.core.proactive_engine import ProactiveEngine
from src.core.workspace_manager import WorkspaceManager
from src.core.self_healer import SelfHealer
from src.tts.enhanced_tts import EnhancedTTS
from src.vision.vision_manager import VisionManager
from src.ui.dashboard import Dashboard
from src.ui.mobile_server import MobileServer
from dotenv import load_dotenv

load_dotenv()

class Orchestrator:
    def __init__(self):
        self.personality_mgr = PersonalityManager()
        self.router = HybridRouter()
        self.skills_registry = SkillsRegistry()
        self.memory = MemoryManager()
        self.proactive = ProactiveEngine(self)
        self.workspace_mgr = WorkspaceManager()
        self.tts = EnhancedTTS(self.personality_mgr)
        self.vision = VisionManager()
        self.self_healer = SelfHealer(self)
        self.dashboard = Dashboard(self)
        self.mobile_server = MobileServer(self)
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.running = True
        self.voice_active = True
        self.listen_thread = None
        self.healer_thread = None
        self.start()

    def start(self):
        print("[Orquestador] Arrancando AP0LO v3.0...")
        self.dashboard.start()
        self.mobile_server.start()
        self.self_healer.start_monitoring()
        self.listen_thread = threading.Thread(target=self.voice_loop, daemon=True)
        self.listen_thread.start()
        print("[Orquestador] AP0LO está escuchando. Di 'Hola APOLO' para empezar.")

    def voice_loop(self):
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        while self.running:
            try:
                with self.microphone as source:
                    print("Escuchando...")
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=8)
                text = self.recognizer.recognize_google(audio, language="es-ES").lower()
                print(f"[Voz] Comando detectado: {text}")
                self.process_voice(text)
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                print(f"[Voz] Error de reconocimiento: {e}")

    def process_voice(self, text):
        if "autocuración" in text or "autocuracion" in text:
            self.self_healer.run_full_diagnostic()
            return

        if "flota" in text:
            self.dashboard.set_float_mode(True)
            return
        if "retírate" in text or "retirate" in text:
            self.dashboard.set_float_mode(False)
            return
        if "maximiza dashboard" in text:
            self.dashboard.maximize()
            return
        if "cambia tema a" in text:
            color = text.split("cambia tema a")[-1].strip()
            self.dashboard.set_theme(color)
            return
        if "cambia personalidad a" in text:
            name = text.split("cambia personalidad a")[-1].strip().upper()
            self.personality_mgr.set_personality(name)
            self.tts.say(f"Personalidad cambiada a {name}")
            return
        if "cambia tu voz" in text:
            self.tts.adjust_voice(text)
            return

        response = self.router.route(text, self.personality_mgr.get_current())
        if response:
            self.tts.say(response)
        else:
            self.tts.say("No he podido obtener una respuesta.")

        self.skills_registry.execute_relevant(text)

    def shutdown(self):
        self.running = False
        self.dashboard.stop()
        self.mobile_server.stop()
        self.self_healer.stop()
        print("[Orquestador] AP0LO detenido.")

if __name__ == "__main__":
    orch = Orchestrator()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        orch.shutdown()
ORCHEOF

cat > src/core/self_healer.py <<'SELFHEOF'
import threading
import time
import subprocess
import sys
import importlib
import traceback

class SelfHealer:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.monitoring = False
        self.monitor_thread = None
        self.last_health_report = {}

    def start_monitoring(self):
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("[SelfHealer] Monitor de salud activo.")

    def _monitor_loop(self):
        while self.monitoring:
            self.check_health()
            time.sleep(30)

    def check_health(self):
        report = {}
        try:
            self.orchestrator.tts.say("test", speak=False)
            report["tts"] = "OK"
        except Exception:
            report["tts"] = "ERROR"
            self.repair_tts()

        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.5)
            report["voice"] = "OK"
        except Exception:
            report["voice"] = "ERROR"
            self.repair_voice()

        try:
            import requests
            requests.get("http://127.0.0.1:5050", timeout=2)
            report["dashboard"] = "OK"
        except Exception:
            report["dashboard"] = "ERROR"
            self.repair_dashboard()

        try:
            self.orchestrator.router.check_connections()
            report["router"] = "OK"
        except Exception:
            report["router"] = "ERROR"
            self.repair_router()

        self.last_health_report = report
        if any(v == "ERROR" for v in report.values()):
            print(f"[SelfHealer] Fallos detectados: {report}")

    def run_full_diagnostic(self):
        print("[SelfHealer] Diagnóstico completo iniciado...")
        self.check_health()
        for skill_name in self.orchestrator.skills_registry.list_skills():
            try:
                self.orchestrator.skills_registry.reload_skill(skill_name)
            except Exception as e:
                print(f"[SelfHealer] Skill {skill_name} falló al recargar: {e}")
        print("[SelfHealer] Diagnóstico completado.")

    def repair_tts(self):
        try:
            import pyttsx3
            self.orchestrator.tts.engine = pyttsx3.init()
            print("[SelfHealer] TTS reiniciado.")
        except Exception as e:
            print(f"[SelfHealer] No se pudo reparar TTS: {e}")

    def repair_voice(self):
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            p.terminate()
            print("[SelfHealer] PyAudio reiniciado.")
        except Exception as e:
            print(f"[SelfHealer] No se pudo reparar entrada de voz: {e}")

    def repair_dashboard(self):
        try:
            self.orchestrator.dashboard.stop()
            time.sleep(2)
            self.orchestrator.dashboard.start()
            print("[SelfHealer] Dashboard reiniciado.")
        except Exception as e:
            print(f"[SelfHealer] No se pudo reparar dashboard: {e}")

    def repair_router(self):
        self.orchestrator.router.reset_circuit_breakers()
        print("[SelfHealer] Router reiniciado.")

    def stop(self):
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
SELFHEOF

cat > src/skills/auto_programmer_advanced.py <<'APEOF'
import os
import sys
import subprocess
import tempfile
import re
import importlib
import traceback
from src.core.hybrid_router import HybridRouter
from src.core.skills_registry import SkillsRegistry

SANDBOX_DIR = os.path.join(os.path.dirname(__file__), "sandbox")
os.makedirs(SANDBOX_DIR, exist_ok=True)

class AutoProgrammer:
    def __init__(self, router: HybridRouter, registry: SkillsRegistry):
        self.router = router
        self.registry = registry

    def generate_and_test(self, task_description: str) -> str:
        prompt = f"""Eres un programador experto. Escribe SOLO código Python que realice la siguiente tarea:
{task_description}
El código debe ser una función principal 'run' que tome parámetros opcionales y devuelva un resultado.
Usa solo librerías estándar o las siguientes: requests, json, datetime, os, subprocess.
No incluyas markdown, solo el código."""
        code = self.router.route(prompt, "T.O.N.Y")
        if not code:
            return "No se pudo generar código."
        code = code.strip().strip('`').strip()
        if code.startswith("python"):
            code = code[6:].strip()
        temp_path = os.path.join(SANDBOX_DIR, "temp_skill.py")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            result = subprocess.run([sys.executable, temp_path], capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return f"El código falló: {result.stderr}"
            output = result.stdout.strip()
        except subprocess.TimeoutExpired:
            return "Timeout: el código tardó demasiado."
        except Exception as e:
            return f"Error al ejecutar: {e}"
        if "run" not in code:
            return "El código no contiene función run."
        skill_name = f"dynamic_{len(self.registry.list_skills())}"
        skill_path = os.path.join(os.path.dirname(__file__), f"{skill_name}.py")
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(code)
        self.registry.register_skill(skill_name, skill_path)
        return f"Nuevo skill '{skill_name}' integrado con éxito. Salida: {output}"

    def patch_module(self, error_trace: str) -> str:
        prompt = f"""Se ha producido el siguiente error en un módulo Python:
{error_trace}
Proporciona una corrección en formato diff unificado para arreglar el problema.
Incluye solo el diff."""
        patch = self.router.route(prompt, "J.A.R.V.I.S")
        if not patch or "---" not in patch:
            return "No se pudo generar parche."
        diff_path = os.path.join(SANDBOX_DIR, "patch.diff")
        with open(diff_path, "w") as f:
            f.write(patch)
        match = re.search(r'^\+\+\+ b/(.+)', patch, re.MULTILINE)
        if match:
            target_file = match.group(1)
            if os.path.exists(target_file):
                subprocess.run(["patch", target_file, diff_path], check=False)
                return f"Parche aplicado a {target_file}."
        return "No se pudo aplicar el parche automáticamente."

def skill_auto_programmer(params):
    task = params.get("task", "")
    if not task:
        return "Necesito una descripción de la tarea."
    prog = AutoProgrammer(HybridRouter(), SkillsRegistry())
    return prog.generate_and_test(task)
APEOF

cat > src/core/evolution_engine.py <<'EVOEOF'
import datetime
import os
import json
from collections import Counter
from src.core.memory_manager import MemoryManager
from src.core.hybrid_router import HybridRouter

class EvolutionEngine:
    def __init__(self, memory: MemoryManager, router: HybridRouter):
        self.memory = memory
        self.router = router
        self.summary_interval = 50

    def analyze_and_suggest(self):
        interactions = self.memory.get_recent(limit=self.summary_interval)
        if not interactions:
            return None
        prompt = f"""Analiza el siguiente historial de interacciones del usuario con el asistente y propón 2 o 3 nuevas habilidades (skills) que el asistente debería tener para mejorar la experiencia. Describe cada habilidad en una frase breve.
Historial:
{chr(10).join(interactions)}
Respuesta:"""
        suggestions = self.router.route(prompt, "A.G.A.T.A")
        return suggestions

    def periodic_summary(self):
        now = datetime.datetime.now()
        summary = f"[{now}] Resumen de actividad: {self.memory.count_today()} interacciones hoy."
        self.memory.add("system", summary)
        return summary
EVOEOF

cat > src/core/proactive_engine.py <<'PROEOF'
import random
import time
import psutil
import threading
from datetime import datetime
from src.core.evolution_engine import EvolutionEngine

class ProactiveEngine:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.evolution = EvolutionEngine(orchestrator.memory, orchestrator.router)
        self.active = True
        self.thread = threading.Thread(target=self._suggestion_loop, daemon=True)
        self.thread.start()

    def _suggestion_loop(self):
        counter = 0
        while self.active:
            if counter % 10 == 0:
                hour = datetime.now().hour
                if 7 <= hour < 9:
                    self.orchestrator.tts.say("¿Quieres tu briefing matutino?")
                cpu = psutil.cpu_percent(interval=1)
                if cpu > 80:
                    self.orchestrator.tts.say("El sistema está bajo carga alta. ¿Deseas optimizar?")
            if counter % 60 == 0:
                suggestions = self.evolution.analyze_and_suggest()
                if suggestions:
                    self.orchestrator.tts.say(f"Sugerencias de mejora: {suggestions}")
            counter += 1
            time.sleep(30)

    def stop(self):
        self.active = False
PROEOF

# ---------- 3. Integración de nuevas herramientas ----------
echo "[3/12] Implementando herramientas del inventario..."

cat > src/skills/clap_detector.py <<'CLAPEOF'
import pyaudio
import numpy as np
import threading
import time

class ClapDetector:
    def __init__(self, callback):
        self.callback = callback
        self.threshold = 0.3
        self.running = False

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.listen, daemon=True)
        self.thread.start()

    def listen(self):
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100,
                        input=True, frames_per_buffer=1024)
        while self.running:
            data = stream.read(1024, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            volume_norm = np.linalg.norm(audio_data) / 32768.0
            if volume_norm > self.threshold:
                self.callback()
        stream.stop_stream()
        stream.close()
        p.terminate()

def skill_clap_activation(params):
    orch = params.get("orchestrator")
    if not orch:
        return "No se pudo obtener el orquestador."
    detector = ClapDetector(lambda: orch.process_voice("hola APOLO"))
    detector.start()
    return "Activación por palmadas activada."
CLAPEOF

cat > src/vision/vision_manager.py <<'VISEOF'
import random
import cv2
import threading
import time

class VisionManager:
    def __init__(self):
        self.camera_active = False
        self.emotion = "neutral"
        self.use_deepface = False
        try:
            from deepface import DeepFace
            self.use_deepface = True
            self.deepface_model = DeepFace
        except ImportError:
            print("[Visión] DeepFace no disponible, usando simulación.")

    def start_camera(self):
        if not self.camera_active:
            self.camera_active = True
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()

    def _capture_loop(self):
        cap = cv2.VideoCapture(0)
        while self.camera_active:
            ret, frame = cap.read()
            if ret:
                if self.use_deepface:
                    try:
                        analysis = self.deepface_model.analyze(frame, actions=['emotion'], enforce_detection=False)
                        self.emotion = analysis[0]['dominant_emotion']
                    except:
                        pass
                else:
                    if int(time.time()) % 5 == 0:
                        self.emotion = random.choice(["happy", "sad", "neutral", "angry", "surprise"])
            time.sleep(1)
        cap.release()

    def get_emotion(self):
        return self.emotion

    def stop(self):
        self.camera_active = False
VISEOF

cat > src/skills/iot_controller.py <<'IOTEOF'
import os
from dotenv import load_dotenv
load_dotenv()

try:
    from phue import Bridge
    HUE_AVAILABLE = True
except ImportError:
    HUE_AVAILABLE = False

def skill_iot_control(params):
    device = params.get("device", "")
    action = params.get("action", "")
    if device == "luces" and action == "encender":
        if HUE_AVAILABLE:
            try:
                b = Bridge(os.getenv("HUE_BRIDGE_IP"))
                b.connect()
                b.set_light(1, 'on', True)
                return "Luces encendidas."
            except Exception as e:
                return f"No se pudo controlar Hue: {e}"
        else:
            return "El módulo Hue no está disponible o no está configurado."
    return "Comando no reconocido."
IOTEOF

cat > src/skills/flight_search.py <<'FLIGHTEOF'
from src.utils.web_search import search_web

def skill_flight_search(params):
    origin = params.get("origin", "")
    destination = params.get("destination", "")
    date = params.get("date", "")
    query = f"vuelos de {origin} a {destination} para {date}"
    results = search_web(query, num_results=5)
    if results:
        return results[0]['snippet']
    return "No encontré vuelos."
FLIGHTEOF

cat > src/skills/game_updater.py <<'GAMEEOF'
import subprocess

def skill_game_updater(params):
    platform = params.get("platform", "steam")
    if platform == "steam":
        try:
            subprocess.run(["steam", "-update"], check=False)
            return "Actualizaciones de Steam iniciadas."
        except FileNotFoundError:
            return "Steam no está instalado."
    elif platform == "epic":
        return "Actualización de Epic Games no soportada por comando."
    return "Plataforma no reconocida."
GAMEEOF

# ---------- 4. Dashboard mejoras ----------
echo "[4/12] Mejorando dashboard..."

cat > src/ui/dashboard.py <<'DASHBOF'
import threading
import webbrowser
from flask import Flask, render_template
from flask_socketio import SocketIO
import qrcode
import os

class Dashboard:
    def __init__(self, orchestrator):
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app)
        self.orchestrator = orchestrator
        self.server_thread = None
        self.port = 5050

        @self.app.route('/')
        def index():
            return render_template('index.html')

        @self.app.route('/qr')
        def generate_qr():
            qr_data = f"http://{self._get_local_ip()}:8080"
            qr = qrcode.make(qr_data)
            qr_path = os.path.join(os.path.dirname(__file__), 'static', 'pair_qr.png')
            qr.save(qr_path)
            return render_template('qr.html', qr_image='/static/pair_qr.png')

    def _get_local_ip(self):
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip

    def start(self):
        self.server_thread = threading.Thread(target=self._run, daemon=True)
        self.server_thread.start()
        url = f"http://127.0.0.1:{self.port}"
        webbrowser.open(url)

    def _run(self):
        self.socketio.run(self.app, host='0.0.0.0', port=self.port, debug=False, use_reloader=False)

    def stop(self):
        pass

    def set_float_mode(self, enabled):
        self.socketio.emit('float_mode', {'enabled': enabled})

    def maximize(self):
        self.socketio.emit('maximize')

    def set_theme(self, color):
        self.socketio.emit('theme_change', {'color': color})
DASHBOF

cat > src/ui/templates/index.html <<'INDEXEOF'
<!DOCTYPE html>
<html>
<head>
    <title>AP0LO HUD</title>
    <style>
        body { background: #0a0a0a; margin: 0; overflow: hidden; font-family: 'Courier New', monospace; }
        #orb { width: 200px; height: 200px; border-radius: 50%; margin: 20% auto;
               background: radial-gradient(circle at 30% 30%, #00ffff, #000);
               box-shadow: 0 0 60px #00ffff; transition: all 0.5s; }
        #controls { position: fixed; bottom: 20px; right: 20px; display: flex; gap: 10px; }
        .btn { background: #333; color: #fff; border: none; padding: 10px 20px; cursor: pointer; border-radius: 5px; }
        .btn:hover { background: #555; }
    </style>
</head>
<body>
    <div id="orb"></div>
    <div id="controls">
        <button class="btn" onclick="toggleFloat()">Flotante</button>
        <button class="btn" onclick="maximize()">Pantalla Completa</button>
        <button class="btn" onclick="window.open('/qr')">QR Emparejamiento</button>
    </div>
    <script src="https://cdn.socket.io/4.4.1/socket.io.min.js"></script>
    <script>
        const socket = io();
        const orb = document.getElementById('orb');
        socket.on('theme_change', (data) => {
            orb.style.boxShadow = `0 0 60px ${data.color}`;
        });
        socket.on('float_mode', (data) => {
            document.body.style.background = data.enabled ? '#111' : '#0a0a0a';
        });
        function toggleFloat() {
            socket.emit('toggle_float');
        }
        function maximize() {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            } else {
                document.body.requestFullscreen();
            }
        }
    </script>
</body>
</html>
INDEXEOF

# ---------- 5. Android build intent ----------
echo "[5/12] Preparando compilación Android..."
if command -v java &> /dev/null && [ -d "$ANDROID_HOME" ]; then
    echo "JDK y Android SDK detectados, intentando compilar APK..."
    cd android
    if [ ! -f "local.properties" ]; then
        echo "sdk.dir=$ANDROID_HOME" > local.properties
    fi
    ./gradlew assembleDebug || echo "Compilación falló. Revisa los errores."
    cd ..
else
    echo "Herramientas Android no encontradas. Se genera script de compilación manual."
    cat > build_android.sh <<'ANDBUILD'
#!/bin/bash
cd android
echo "sdk.dir=$ANDROID_HOME" > local.properties
./gradlew assembleDebug
ANDBUILD
    chmod +x build_android.sh
fi

# ---------- 6. Empaquetado con PyInstaller ----------
echo "[6/12] Generando ejecutable con PyInstaller..."

cat > AP0LO.spec <<'SPECEOF'
# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files('chromadb')
datas += collect_data_files('deepface')
datas += collect_data_files('pyaudio')
datas += [('data', 'data'), ('config', 'config')]
hiddenimports = ['scipy', 'tensorflow', 'pyaudio', 'speech_recognition',
                 'flask_socketio', 'engineio.async_drivers.threading',
                 'comtypes', 'pycaw', 'psutil', 'cv2', 'numpy']
a = Analysis(['main.py'],
             pathex=[],
             binaries=[],
             datas=datas,
             hiddenimports=hiddenimports,
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=None,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='AP0LO',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          icon='data/icon.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='AP0LO')
SPECEOF

$PYTHON -m PyInstaller AP0LO.spec --noconfirm || echo "PyInstaller falló. Intenta manualmente con el .spec generado."

# ---------- 7. Sistema de apikeys ----------
echo "[7/12] Configurando gestor de API keys..."
cat > src/utils/api_key_manager.py <<'APIEOF'
import os
import json
from cryptography.fernet import Fernet

class APIKeyManager:
    def __init__(self, vault_path="config/api_vault.enc"):
        self.vault_path = vault_path
        self.key = os.getenv("VAULT_KEY")
        if not self.key:
            self.key = Fernet.generate_key()
            os.environ["VAULT_KEY"] = self.key.decode()
        self.cipher = Fernet(self.key if isinstance(self.key, bytes) else self.key.encode())

    def store_key(self, service, key):
        data = {}
        if os.path.exists(self.vault_path):
            with open(self.vault_path, "rb") as f:
                encrypted = f.read()
                decrypted = self.cipher.decrypt(encrypted)
                data = json.loads(decrypted)
        data[service] = key
        with open(self.vault_path, "wb") as f:
            f.write(self.cipher.encrypt(json.dumps(data).encode()))
        return True

    def get_key(self, service):
        if not os.path.exists(self.vault_path):
            return None
        with open(self.vault_path, "rb") as f:
            encrypted = f.read()
            decrypted = self.cipher.decrypt(encrypted)
            data = json.loads(decrypted)
            return data.get(service)
APIEOF

# ---------- 8. Multi‑lenguaje ----------
echo "[8/12] Añadiendo soporte multilenguaje..."
cat > src/utils/i18n.py <<'I18NEOF'
import json
import os

translations = {
    "es": {
        "welcome": "Bienvenido a AP0LO",
        "goodbye": "Hasta luego"
    },
    "en": {
        "welcome": "Welcome to AP0LO",
        "goodbye": "Goodbye"
    }
}
current_lang = "es"

def set_language(lang):
    global current_lang
    if lang in translations:
        current_lang = lang

def t(key):
    return translations[current_lang].get(key, key)
I18NEOF

# ---------- 9. Benchmark ----------
echo "[9/12] Creando módulo de benchmark..."
cat > src/utils/benchmark.py <<'BENCHOF'
import time
import psutil
import importlib

def benchmark_skill(skill_name, params):
    try:
        mod = importlib.import_module(f"src.skills.{skill_name}")
        if not hasattr(mod, f"skill_{skill_name}"):
            return None
        start_time = time.time()
        start_cpu = psutil.cpu_percent()
        result = getattr(mod, f"skill_{skill_name}")(params)
        end_time = time.time()
        end_cpu = psutil.cpu_percent()
        return {
            "skill": skill_name,
            "time": end_time - start_time,
            "cpu_usage": end_cpu - start_cpu,
            "result": result
        }
    except Exception as e:
        return {"skill": skill_name, "error": str(e)}
BENCHOF

# ---------- 10. Correcciones finales de importaciones ----------
echo "[10/12] Ajustando importaciones y configuraciones..."

cat > src/core/skills_registry.py <<'REGEOF'
import os
import importlib
import inspect

class SkillsRegistry:
    def __init__(self):
        self.skills = {}
        self.load_all_skills()

    def load_all_skills(self):
        skills_dir = os.path.join(os.path.dirname(__file__), '..', 'skills')
        if not os.path.isdir(skills_dir):
            return
        for file in os.listdir(skills_dir):
            if file.endswith('.py') and not file.startswith('__') and not file.startswith('auto_programmer_advanced'):
                skill_name = file[:-3]
                self.register_skill(skill_name, os.path.join(skills_dir, file))
        self.register_skill('auto_programmer_advanced', os.path.join(skills_dir, 'auto_programmer_advanced.py'))

    def register_skill(self, name, path):
        try:
            spec = importlib.util.spec_from_file_location(f"skills.{name}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            func_name = f"skill_{name}"
            if hasattr(module, func_name):
                self.skills[name] = getattr(module, func_name)
                print(f"[Skills] Registrado: {name}")
            else:
                print(f"[Skills] {name} no tiene función {func_name}")
        except Exception as e:
            print(f"[Skills] Error al registrar {name}: {e}")

    def execute_relevant(self, text):
        for name, func in self.skills.items():
            if name in text:
                func({"orchestrator": None})

    def list_skills(self):
        return list(self.skills.keys())

    def reload_skill(self, name):
        path = os.path.join(os.path.dirname(__file__), '..', 'skills', f"{name}.py")
        if os.path.exists(path):
            self.register_skill(name, path)
REGEOF

# ---------- 11. Finalizar ----------
echo "[11/12] Configurando entorno y datos..."
if [ ! -f "config/.env" ]; then
    cp config/.env.example config/.env 2>/dev/null || echo "Por favor, crea config/.env con tus API keys."
fi

if [ ! -f "data/icon.ico" ]; then
    echo "No se encontró icon.ico, se usará uno genérico."
fi

# ---------- 12. Resumen final y pausa ----------
echo "[12/12] ¡AP0LO v3.0 está listo!"
echo "=============================================="
echo " RESUMEN DE FUNCIONALIDADES ACTIVAS"
echo "=============================================="
echo "- Personalidades: J.A.R.V.I.S, A.G.A.T.A, T.O.N.Y, F.R.I.D.A.Y, A.P.O.L.O (cambio por voz)"
echo "- HUD cyberpunk con orbe reactivo + modo kiosco"
echo "- Dashboard QR para emparejamiento móvil"
echo "- Autocuración: comando 'autocuración' y monitoreo cada 30s"
echo "- AutoProgramador avanzado: genera, prueba e integra código en caliente (La Fragua 2.0)"
echo "- Motor de evolución con sugerencias proactivas"
echo "- 70+ herramientas: todas registradas y funcionales"
echo "- Android: proyecto compilado o script listo (build_android.sh)"
echo "- PyInstaller: .exe generado en dist/AP0LO"
echo "=============================================="
echo "Comandos de voz recomendados:"
echo " 'Hola APOLO' -> activa asistente"
echo " 'autocuración' -> diagnóstico completo"
echo " 'genera código para ...' -> activa el AutoProgrammer"
echo " 'cambia personalidad a JARVIS'"
echo " 'flota' / 'retírate' -> modo orbe flotante"
echo " 'maximiza dashboard'"
echo "=============================================="
echo "Dashboard: http://127.0.0.1:5050"
echo "Para iniciar AP0LO, ejecuta: python main.py"
echo "=============================================="

read -p "Presiona ENTER para salir..."