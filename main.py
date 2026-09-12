#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
═══════════════════════════════════════════════════════════════════════════════
AP0L0 — Autonomous Platform for Orchestration, Learning and Operations
Sistema Operativo de Agentes Inteligentes — Versión 3.0 (Auto‑programación segura)
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import warnings
import ctypes
import platform as _platform
import subprocess as _subprocess
import threading
import asyncio
from pathlib import Path
from PyQt6.QtWidgets import QApplication

# ===== CONFIGURACIÓN DE ENTORNO =====
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["ABSL_LOGGING_SEVERITY"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

warnings.filterwarnings("ignore")
warnings.simplefilter("ignore", DeprecationWarning)
warnings.simplefilter("ignore", FutureWarning)
warnings.simplefilter("ignore", RuntimeWarning)
warnings.simplefilter("ignore", UserWarning)

# ===== AÑADIR CARPETA src AL PYTHONPATH =====
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ===== IMPORTS =====
# UI (versión completa con módulos divididos)
from ui import JarvisUI

# Módulos del core y autónomos
from src.core.jarvis_live import JarvisLive
from src.core.config import THEME_MAP, DEFAULT_THEME

# ===== SISTEMA DE PLUGINS =====
try:
    from src.core.plugin_system import PluginSystem
    PLUGIN_SYSTEM_AVAILABLE = True
except ImportError:
    PLUGIN_SYSTEM_AVAILABLE = False

# ===== FORZAR CREATE_NO_WINDOW EN WINDOWS =====
if _platform.system() == "Windows":
    _OrigPopen = _subprocess.Popen
    class _Popen(_OrigPopen):
        def __init__(self, args, **kw):
            kw["creationflags"] = kw.get("creationflags", 0) | _subprocess.CREATE_NO_WINDOW
            kw.pop("startupinfo", None)
            super().__init__(args, **kw)
    _subprocess.Popen = _Popen

# ===== VARIABLE GLOBAL =====
_jarvis_instance = None
_plugin_system = None

def log_callback(message: str):
    print(f"[AUTONOMOUS] {message}")

def main():
    global _jarvis_instance, _plugin_system

    # Restaurar la secuencia visual de arranque. Se crea antes de la UI para
    # que cubra la construcción de los paneles y se cierre de forma natural.
    from src.ui.boot_screen import BootScreen
    app = QApplication.instance() or QApplication(sys.argv)
    boot_screen = BootScreen()

    # ===== INICIALIZAR SISTEMA DE PLUGINS =====
    if PLUGIN_SYSTEM_AVAILABLE:
        _plugin_system = PluginSystem(plugin_dir="plugins")
        _plugin_system.load_plugins()
        print(f"[MAIN] ✅ PluginSystem cargado: {len(_plugin_system.plugins)} plugins")

    ui = JarvisUI("face.png")
    boot_screen.boot_closed.connect(lambda: ui._win.raise_())

    # ===== PANEL CIRCULAR =====
    panel = None
    try:
        from src.utils.panel_circular_IA import JarvisCircularPanel
        panel = JarvisCircularPanel()
        panel.hide()
        def posicionar_panel():
            if ui._win:
                x = ui._win.x() + ui._win.width() + 20
                y = ui._win.y()
                panel.move(x, y)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(200, posicionar_panel)
        ui.panel = panel
        def on_panel_closed():
            if hasattr(ui, '_win') and ui._win:
                ui._win.deactivate_floating_mode()
        panel.set_close_callback(on_panel_closed)
        print("[MAIN] ✅ Panel circular creado (oculto).")
    except Exception as e:
        print(f"[MAIN] ⚠️ Panel circular no disponible: {e}")

    # ===== CALLBACKS PARA CAMBIO DE PERSONALIDAD =====
    def on_personality_change(personality: str, voice: str):
        global _jarvis_instance
        print(f"[MAIN] Cambio a personalidad {personality} con voz {voice}")
        if _jarvis_instance:
            _jarvis_instance._pending_reconnect = True
            _jarvis_instance._reconnect_personality = personality
            _jarvis_instance._reconnect_voice = voice
            theme = THEME_MAP.get(personality, DEFAULT_THEME)
            ui.set_theme(theme)
            if panel:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: panel.set_theme_color(theme))

    def on_restart_assistant():
        global _jarvis_instance
        print("[MAIN] Reiniciando asistente...")
        if _jarvis_instance:
            _jarvis_instance._pending_reconnect = True
            _jarvis_instance._reconnect_personality = _jarvis_instance.current_personality
            _jarvis_instance._reconnect_voice = _jarvis_instance._reconnect_voice

    ui.on_personality_change = on_personality_change
    ui.on_restart_assistant = on_restart_assistant

    # ===== INICIALIZAR COLA DE TAREAS =====
    try:
        from src.agent.task_queue import get_queue
        get_queue()
        print("[MAIN] ✅ Cola de tareas del agente iniciada")
    except Exception as e:
        print(f"[MAIN] ⚠️ Cola de tareas no disponible: {e}")

    # ===== EJECUTAR JARVIS EN UN HILO =====
    def runner():
        global _jarvis_instance
        ui.wait_for_api_key()
        # CORRECCIÓN: JarvisLive SOLO acepta ui (y opcionalmente boot_screen, pero lo omitimos)
        # Las dependencias (router, skills, etc.) se crean internamente en JarvisLive.
        jarvis = JarvisLive(ui)
        _jarvis_instance = jarvis
        if panel:
            jarvis.set_panel(panel)

        async def main_async():
            # jarvis.run() ya lanza internamente los bucles de autocuración y aprendizaje
            await jarvis.run()

        try:
            asyncio.run(main_async())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")
        finally:
            _jarvis_instance = None

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()

if __name__ == "__main__":
    main()
