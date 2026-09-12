# ui.py (raíz) — VERSIÓN COMPLETA CON MENÚ FLOTANTE REESTRUCTURADO
# =====================================================================
# ui.py — AP0L0 UI (Menú Flotante + Barra Superior Optimizada)
# =====================================================================

from __future__ import annotations

import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
import warnings
import ctypes
from pathlib import Path
from typing import Callable, Dict, Any, Optional

try:
    import psutil  # opcional; las métricas tienen fallback en system_utils
except ImportError:
    psutil = None

from PyQt6.QtCore import (
    QEasingCurve, QMimeData, QObject, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, pyqtSignal, pyqtSlot, QPropertyAnimation, QParallelAnimationGroup,
    QMetaObject, Q_ARG,
)
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QDragEnterEvent, QDropEvent, QFont,
    QFontDatabase, QKeySequence, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient, QShortcut, QIcon, QPalette, QAction,
)
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QSplitter,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget, QProgressBar,
    QSlider, QComboBox, QGroupBox, QTabWidget, QColorDialog,
    QCheckBox, QSpinBox, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QProgressDialog, QDialog, QDialogButtonBox, QTextBrowser, QSystemTrayIcon,
    QGraphicsOpacityEffect,
)

warnings.filterwarnings("ignore", category=FutureWarning, module="pynvml")

# ===== IMPORTS DE MÓDULOS INTERNOS =====
from src.config.settings import (
    BASE_DIR, CONFIG_DIR, API_FILE,
    DEFAULT_W, DEFAULT_H, MIN_W, MIN_H, LEFT_W, RIGHT_W, FLOAT_W, FLOAT_H,
    ENABLE_ADMIN_CHECK
)
from src.config.personality import (
    PERSONALITY_INFO, DEFAULT_PERSONALITY,
    NAME_MAP, SUBTITLE_MAP
)
from src.config.themes import (
    VOICE_MAP, THEME_MAP, DEFAULT_VOICE, DEFAULT_THEME
)
from src.utils.i18n import (
    tr, LanguageManager, set_language, get_language
)
from src.ui.customize_overlay import CustomizeOverlay
from src.ui.ui_utils import (
    C,
    apply_ui_accent,
    current_palette,
    retheme_all_widgets,
    apply_theme,
    qcol,
    _read_full_config,
    _save_config,
)
from src.ui.ui_constants import WALLPAPER_DIR, _DEFAULT_ICON_PATH
from src.ui.hud_canvas import HudCanvas
from src.ui.widgets import (
    MetricBar, LogWidget, FileDropZone, _DropCanvas,
    _CameraPreview, SetupOverlay, ClipboardPanel, RemoteKeyOverlay,
    SystemStatusWidget,
    BatteryWidget, WeatherWidget, CalendarWidget, TimerWidget,
    TemperatureWidget, SwapWidget, NetworkGraphWidget
)
from src.utils.system_utils import (
    IS_WINDOWS, IS_LINUX, IS_MAC, _OS, _WIN_HIDE,
    _metrics, _get_desktop_dir, _build_jarvis_icon, _create_lnk_windows
)
from src.utils.file_utils import (
    _FILE_ICONS, _EXT_TO_CAT, _file_category, _fmt_size
)

# ===== IMPORTS DE HANDLERS =====
from src.ui.camera_handler import CameraHandler
from src.ui.clipboard_handler import ClipboardHandler
from src.ui.float_mode import FloatModeHandler
from src.ui.main_window_parts import UIBuilderMixin
from src.ui.shortcuts import ShortcutsHandler
from src.ui.theme_handler import ThemeHandler
from src.ui.tray_handler import TrayHandler


# =====================================================================
# MAIN WINDOW
# =====================================================================

class MainWindow(QMainWindow, UIBuilderMixin):
    _log_sig = pyqtSignal(str)
    _state_sig = pyqtSignal(str)
    _content_sig = pyqtSignal(str, str)
    _reconfig_sig = pyqtSignal()
    _camera_sig = pyqtSignal(bytes)
    _cam_stream_sig = pyqtSignal(bool)
    _cam_frame_sig = pyqtSignal(bytes)
    _clipboard_sig = pyqtSignal(str)
    _theme_changed = pyqtSignal(str)

    def __init__(self, face_path: str):
        super().__init__()
        self._face_path = face_path
        self._float_mode = False
        self._last_geometry = None
        self._always_on_top = False
        self._dashboard_url = "No conectado"
        self._focus_mode = False

        # Configuración inicial
        cfg = _read_full_config()
        lang = cfg.get("ui_language", "es")
        set_language(lang)

        self._personality = cfg.get("personality", DEFAULT_PERSONALITY)
        info = PERSONALITY_INFO.get(self._personality, PERSONALITY_INFO[DEFAULT_PERSONALITY])
        self._assistant_name = cfg.get("assistant_name") or info["name"]
        self._assistant_subtitle = cfg.get("assistant_subtitle") or info["subtitle"]
        self._voice = cfg.get("voice") or info["voice"]
        self._theme_color = cfg.get("ui_color") or info["color"]

        self._enable_animations = cfg.get("enable_animations", True)
        self._enable_sounds = cfg.get("enable_sounds", True)
        self._show_timestamps = cfg.get("show_timestamps", True)
        self._auto_scroll_log = cfg.get("auto_scroll_log", True)
        self._sync_system_theme = cfg.get("sync_system_theme", False)

        self._response_mode = cfg.get("response_mode", "voice_text")
        self._focus_mode = cfg.get("focus_mode", False)
        self._vad_enabled = cfg.get("vad_enabled", False)
        self._rag_enabled = cfg.get("rag_enabled", False)

        self.panel = None
        self.floating_mode_active = False

        apply_theme(self._personality)
        apply_ui_accent(self._theme_color)

        self.setWindowTitle(f"{self._assistant_name} — XxchristoxX")
        self.setMinimumSize(MIN_W, MIN_H)
        self.resize(DEFAULT_W, DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - DEFAULT_W) // 2,
            (screen.height() - DEFAULT_H) // 2,
        )

        self.on_text_command = None
        self.on_remote_clicked = None
        self.on_interrupt = None
        self.on_personality_change = None
        self.on_restart_assistant = None
        self.on_response_mode_change = None
        self.on_focus_mode_toggle = None
        self._muted = False
        self._current_file = None
        self._remote_overlay = None
        self._customize_overlay = None
        self._brief_enabled = True
        self._applying_theme = False
        self._theme_index = 0

        self._badge_labels = []
        self._action_buttons = {}

        # ===== MENÚ FLOTANTE =====
        self._float_menu = None
        self._float_menu_visible = False
        self._float_menu_title = None  # Referencia al título del menú

        # Construir la UI
        central = QWidget()
        central.setStyleSheet(f"background: {C.BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Cabecera con botón de menú y controles
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._left_panel = self._build_left_panel()
        body.addWidget(self._left_panel, stretch=0)

        custom_face = cfg.get("face_image_path", face_path)
        self.hud = HudCanvas(custom_face, self._assistant_name, personality=self._personality)
        self.hud.set_animations_enabled(self._enable_animations)
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hud.persona = self._personality
        self.hud._assistant_name = self._assistant_name
        self.hud.update()

        if cfg.get("ui_icon_path"):
            self.update_icon(cfg["ui_icon_path"])

        self._content_panel = self._build_content_panel()

        _cam_cont = QWidget()
        _cam_cont.setStyleSheet("background: #000308;")
        _cam_v = QVBoxLayout(_cam_cont)
        _cam_v.setContentsMargins(0, 0, 0, 0)
        _cam_v.setSpacing(0)
        _cam_hdr = QHBoxLayout()
        _cam_hdr.setContentsMargins(8, 5, 8, 5)
        _cam_title = QLabel("◈  CAMERA FEED")
        _cam_title.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        _cam_title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        _cam_hdr.addWidget(_cam_title)
        _cam_hdr.addStretch()
        _cam_x = QPushButton("✕  CLOSE")
        _cam_x.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        _cam_x.setCursor(Qt.CursorShape.PointingHandCursor)
        _cam_x.setStyleSheet(f"""
            QPushButton {{
                color: {C.TEXT_DIM}; background: transparent;
                border: none; padding: 2px 6px;
            }}
            QPushButton:hover {{ color: {C.PRI}; }}
        """)
        _cam_x.clicked.connect(self._stop_camera_stream)
        _cam_hdr.addWidget(_cam_x)
        _cam_v.addLayout(_cam_hdr)
        self._cam_live_lbl = QLabel()
        self._cam_live_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cam_live_lbl.setStyleSheet("background: transparent;")
        self._cam_live_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        _cam_v.addWidget(self._cam_live_lbl, stretch=1)

        self._hud_cam_stack = QStackedWidget()
        self._hud_cam_stack.addWidget(self.hud)
        self._hud_cam_stack.addWidget(_cam_cont)

        self._center_split = QSplitter(Qt.Orientation.Vertical)
        self._center_split.setStyleSheet(f"""
            QSplitter::handle {{
                background: {C.BORDER};
                height: 4px;
            }}
            QSplitter::handle:hover {{
                background: {C.PRI_DIM};
            }}
        """)
        self._center_split.addWidget(self._hud_cam_stack)
        self._center_split.addWidget(self._content_panel)
        self._center_split.setStretchFactor(0, 3)
        self._center_split.setStretchFactor(1, 0)
        self._center_split.setCollapsible(0, False)
        body.addWidget(self._center_split, stretch=5)

        self._right_panel = self._build_right_panel()
        body.addWidget(self._right_panel, stretch=0)

        root.addLayout(body, stretch=1)
        self._footer_widget = self._build_footer()
        root.addWidget(self._footer_widget)

        self._quick_drawer = None

        self._update_autostart_state()
        from src.memory.config_manager import get_brief_enabled as _gbe
        self._brief_enabled = _gbe()
        self._update_brief_state()

        self._clipboard_panel = ClipboardPanel(self.centralWidget())

        self.theme_handler = ThemeHandler(self)
        self.tray_handler = TrayHandler(self)
        self.camera_handler = CameraHandler(self)
        self.clipboard_handler = ClipboardHandler(self)
        self.float_handler = FloatModeHandler(self)
        self.shortcuts_handler = ShortcutsHandler(self)

        self._cam_stream_sig.connect(self.camera_handler.on_stream_toggle)
        self._cam_frame_sig.connect(self.camera_handler.on_frame)
        self._clipboard_sig.connect(self.clipboard_handler.show_clipboard_panel)
        self._theme_changed.connect(self.theme_handler.on_theme_changed)

        self.shortcuts_handler.setup_shortcuts()
        self.tray_handler.create_icon()

        LanguageManager.register_callback(self._on_language_changed_global)

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        self._log_sig.connect(self._log.append_log)
        self._state_sig.connect(self._apply_state)
        self._content_sig.connect(self._show_content)
        self._reconfig_sig.connect(self._show_setup)
        self._camera_sig.connect(self._show_camera_frame)

        self._cam_stop = threading.Event()
        self._cam_preview = _CameraPreview(self.centralWidget())

        self._overlay = None
        self._ready = self._check_config()
        if not self._ready:
            self._show_setup()

        self._apply_full_config(cfg)

        QTimer.singleShot(100, self._update_all_toggle_states)

        self._create_float_menu()
        # Aplicar de nuevo el perfil persistido después de crear todos los
        # widgets, HUD y menú; así el reinicio no vuelve a la paleta anterior.
        self.set_personality_info(self._personality, self._voice, self._theme_color)

    # =====================================================================
    # CABECERA CON MENÚ FLOTANTE + CONTROLES OPTIMIZADOS
    # =====================================================================

    def _build_header(self) -> QWidget:
        """Construye la barra modular completa de acciones del sistema.

        La implementación mantenida en ``src.ui.main_window_parts`` contiene
        el registro completo de acciones, controles multimedia y toggles. Se
        usa aquí como única implementación para evitar que una versión local
        reducida oculte opciones de la interfaz.
        """
        return UIBuilderMixin._build_header(self)

        # Código histórico conservado debajo para facilitar revisión de
        # compatibilidad; no se ejecuta y no se elimina durante esta fase.
        header_widget = QWidget()
        header_widget.setStyleSheet(f"background: {C.DARK}; border-bottom: 1px solid {C.BORDER_B};")
        layout = QVBoxLayout(header_widget)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(0)

        # ---------- FILA 1: TÍTULO Y BOTÓN DE MENÚ ----------
        row1 = QWidget()
        row1.setFixedHeight(48)
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(8, 0, 8, 0)
        row1_layout.setSpacing(8)

        # Botón de menú (Hamburguesa) con icono de dibujo
        self._menu_btn = QPushButton("☰")
        self._menu_btn.setFixedSize(38, 38)
        self._menu_btn.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self._menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._menu_btn.setToolTip("Abrir menú de control")
        self._menu_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C.PRI};
                border: 1px solid {C.PRI_DIM};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO};
                border-color: {C.PRI};
            }}
        """)
        self._menu_btn.clicked.connect(self._toggle_float_menu)
        row1_layout.addWidget(self._menu_btn)

        row1_layout.addWidget(self._make_badge("XxchristoxX", C.PRI_DIM))

        # Título
        mid = QVBoxLayout()
        mid.setSpacing(1)
        self._title_lbl = QLabel(self._assistant_name)
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_lbl.setFont(QFont("Courier New", 16, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        mid.addWidget(self._title_lbl)

        self._sub_lbl = QLabel(self._assistant_subtitle)
        self._sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_lbl.setFont(QFont("Courier New", 7))
        self._sub_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        mid.addWidget(self._sub_lbl)
        row1_layout.addLayout(mid, stretch=1)

        # Reloj
        right_col = QVBoxLayout()
        right_col.setSpacing(1)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)

        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont("Courier New", 7))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        row1_layout.addLayout(right_col)

        layout.addWidget(row1)

        # ---------- FILA 2: CONTROLES (SIN LÍNEA DE SEPARACIÓN) ----------
        row2 = QWidget()
        row2.setFixedHeight(34)
        row2.setStyleSheet(f"background: {C.PANEL2};")
        row2_layout = QHBoxLayout(row2)
        row2_layout.setContentsMargins(4, 0, 4, 0)
        row2_layout.setSpacing(3)

        # Estilo para botones (tamaño más pequeño)
        action_style = f"""
            QPushButton {{
                background: transparent;
                color: {C.TEXT_MED};
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 8pt;
                font-family: 'Segoe UI', 'Courier New', monospace;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO};
                color: {C.PRI};
            }}
        """
        toggle_style_off = f"""
            QPushButton {{
                background: transparent;
                color: {C.MUTED_C};
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 8pt;
                font-family: 'Segoe UI', 'Courier New', monospace;
            }}
            QPushButton:hover {{
                background: #3d0f0f;
                color: {C.MUTED_C};
            }}
        """
        toggle_style_on = f"""
            QPushButton {{
                background: transparent;
                color: {C.GREEN};
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 8pt;
                font-family: 'Segoe UI', 'Courier New', monospace;
            }}
            QPushButton:hover {{
                background: #003d26;
                color: {C.GREEN};
            }}
        """

        row2_layout.addStretch(1)

        # --- Solo 3 botones de acción en la barra (los menos usados) ---
        self._btn_remote = QPushButton("📡  Control Remoto")
        self._btn_remote.setStyleSheet(action_style)
        self._btn_remote.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_remote.clicked.connect(self._open_remote)
        row2_layout.addWidget(self._btn_remote)

        self._btn_shortcut = QPushButton("⚡  Acceso Directo")
        self._btn_shortcut.setStyleSheet(action_style)
        self._btn_shortcut.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_shortcut.clicked.connect(self._create_desktop_shortcut)
        row2_layout.addWidget(self._btn_shortcut)

        # --- Controles multimedia (con iconos de dibujo) ---
        self._btn_media_prev = QPushButton("⏮  Anterior")
        self._btn_media_prev.setStyleSheet(action_style)
        self._btn_media_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_media_prev.clicked.connect(self._media_prev)
        row2_layout.addWidget(self._btn_media_prev)

        self._btn_media_play = QPushButton("▶  Reproducir")
        self._btn_media_play.setStyleSheet(action_style)
        self._btn_media_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_media_play.clicked.connect(self._media_play_pause)
        row2_layout.addWidget(self._btn_media_play)

        self._btn_media_next = QPushButton("⏭  Siguiente")
        self._btn_media_next.setStyleSheet(action_style)
        self._btn_media_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_media_next.clicked.connect(self._media_next)
        row2_layout.addWidget(self._btn_media_next)

        # --- Separador visual ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"background: {C.BORDER}; width: 1px; max-height: 24px;")
        row2_layout.addWidget(sep)

        # --- Toggles principales con iconos de dibujo ---
        self._btn_clap = QPushButton("👏  Aplausos: OFF")
        self._btn_clap.setCheckable(True)
        self._btn_clap.setStyleSheet(toggle_style_off)
        self._btn_clap.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clap.toggled.connect(self._on_clap_toggled)
        row2_layout.addWidget(self._btn_clap)

        self._btn_continuous = QPushButton("👂  Escucha Continua: OFF")
        self._btn_continuous.setCheckable(True)
        self._btn_continuous.setStyleSheet(toggle_style_off)
        self._btn_continuous.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_continuous.toggled.connect(self._on_continuous_toggled)
        row2_layout.addWidget(self._btn_continuous)

        self._btn_autostart = QPushButton("🚀  Inicio Auto: OFF")
        self._btn_autostart.setCheckable(True)
        self._btn_autostart.setStyleSheet(toggle_style_off)
        self._btn_autostart.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_autostart.toggled.connect(self._on_autostart_toggled)
        row2_layout.addWidget(self._btn_autostart)

        self._btn_brief = QPushButton("🌅  Resumen Matutino: OFF")
        self._btn_brief.setCheckable(True)
        self._btn_brief.setStyleSheet(toggle_style_off)
        self._btn_brief.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_brief.toggled.connect(self._on_brief_toggled)
        row2_layout.addWidget(self._btn_brief)

        row2_layout.addStretch(1)

        layout.addWidget(row2)

        # Guardar referencias
        self._action_buttons = {
            'clap': self._btn_clap,
            'continuous': self._btn_continuous,
            'autostart': self._btn_autostart,
            'brief': self._btn_brief,
        }

        return header_widget

    # =====================================================================
    # MENÚ FLOTANTE COMPLETO CON TODAS LAS OPCIONES
    # =====================================================================

    def _create_float_menu(self):
        """Crea el menú flotante con todas las opciones del sistema (versión completa)."""
        if self._float_menu is not None:
            return

        self._float_menu = QFrame(self.centralWidget())
        self._float_menu.setStyleSheet(f"""
            QFrame {{
                background: rgba(0, 6, 12, 248);
                border: 1px solid {C.BORDER_B};
                border-radius: 10px;
            }}
        """)
        self._float_menu.setFixedWidth(360)
        self._float_menu.setVisible(False)

        layout = QVBoxLayout(self._float_menu)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        # Título con icono de dibujo (se guarda referencia para actualizar)
        title = QLabel(f"⚙️  CONTROLES_SISTEMA // {self._assistant_name}")
        title.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; border-bottom: 1px solid {C.BORDER}; padding-bottom: 6px;")
        layout.addWidget(title)
        self._float_menu_title = title  # Guardar referencia

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 4, 0, 4)
        content_layout.setSpacing(2)

        btn_style = f"""
            QPushButton {{
                background: transparent;
                color: {C.TEXT};
                border: none;
                border-radius: 4px;
                padding: 6px 10px;
                text-align: left;
                font-size: 9pt;
                font-family: 'Segoe UI', 'Courier New', monospace;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO};
                color: {C.PRI};
            }}
        """

        # ===== SECCIÓN 1: IA Y VOZ =====
        sec2 = QLabel("🧠  IA Y VOZ")
        sec2.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        sec2.setStyleSheet(f"color: {C.TEXT_MED}; border-bottom: 1px solid {C.BORDER_A}; padding-top: 6px; padding-bottom: 2px;")
        content_layout.addWidget(sec2)

        menu_options = [
            ("🎙️  Nemotron ASR", self._toggle_nemotron_asr),
            ("👁️  Activar Visión", self._toggle_vision),
            ("🖥️  Procesar Pantalla", self._process_screen),
            ("📷  Analizar Cámara / Mano", self._analyze_camera),
            ("🎭  Modo Aura", self._toggle_aura_mode),
            ("👂  Escucha Continua", self._toggle_continuous_listening),
            ("🎤  Seleccionar Micrófono", self._select_microphone),
            ("🔊  Seleccionar Altavoces", self._select_speakers),
        ]
        for label, cb in menu_options:
            btn = QPushButton(label)
            btn.setFont(QFont("Segoe UI", 9))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(cb)
            content_layout.addWidget(btn)

        # ===== SECCIÓN 2: MULTIMEDIA (UN ÚNICO ACCESO) =====
        sec_media = QLabel("🎵  MULTIMEDIA")
        sec_media.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        sec_media.setStyleSheet(f"color: {C.TEXT_MED}; border-bottom: 1px solid {C.BORDER_A}; padding-top: 6px; padding-bottom: 2px;")
        content_layout.addWidget(sec_media)
        media_btn = QPushButton("⏯  Reproducir / Pausar")
        media_btn.setFont(QFont("Segoe UI", 9))
        media_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        media_btn.setStyleSheet(btn_style)
        media_btn.clicked.connect(self._media_play_pause)
        content_layout.addWidget(media_btn)

        # ===== SECCIÓN 3: HARDWARE Y RENDIMIENTO =====
        sec3 = QLabel("⚡  HARDWARE Y RENDIMIENTO")
        sec3.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        sec3.setStyleSheet(f"color: {C.TEXT_MED}; border-bottom: 1px solid {C.BORDER_A}; padding-top: 6px; padding-bottom: 2px;")
        content_layout.addWidget(sec3)

        menu_options = [
            ("⚡  GPU Boost", self._toggle_gpu_boost),
            ("⌨️  Teclado Visual", self._toggle_keyboard),
            ("📹  Webcam Física", self._toggle_webcam),
            ("⬡  Holograma", self._toggle_holo_mode),
            ("💻  Monitor de Rendimiento", self._open_performance_monitor),
            ("🌡️  Temperatura CPU", self._show_cpu_temperature),
        ]
        for label, cb in menu_options:
            btn = QPushButton(label)
            btn.setFont(QFont("Segoe UI", 9))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(cb)
            content_layout.addWidget(btn)

        # ===== SECCIÓN 4: HERRAMIENTAS =====
        sec4 = QLabel("🛠️  HERRAMIENTAS")
        sec4.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        sec4.setStyleSheet(f"color: {C.TEXT_MED}; border-bottom: 1px solid {C.BORDER_A}; padding-top: 6px; padding-bottom: 2px;")
        content_layout.addWidget(sec4)

        menu_options = [
            ("🛒  Lista de Compras", self._toggle_shopping_list),
            ("📺  Reproductor IPTV", self._toggle_iptv_player),
            ("🗑️  Desinstalador", self._toggle_uninstaller),
            ("🚀  Actualizar Software", self._toggle_winget_updater),
            ("🛡️  Antivirus", self._toggle_antivirus),
            ("🛡️  Protección en Tiempo Real", self._toggle_realtime_protection),
            ("🌐  Cliente VPN", self._toggle_vpn_client),
            ("📋  Lista de Comandos", self._toggle_commands_list),
            ("📋  Portapapeles Proactivo", self._start_clipboard_proactive),
            ("📝  Crear Nota Rápida", self._create_quick_note),
            ("📊  Generar Informe", self._generate_report),
        ]
        for label, cb in menu_options:
            btn = QPushButton(label)
            btn.setFont(QFont("Segoe UI", 9))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(cb)
            content_layout.addWidget(btn)

        # ===== SECCIÓN 5: CONFIGURACIÓN =====
        sec5 = QLabel("⚙️  CONFIGURACIÓN")
        sec5.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        sec5.setStyleSheet(f"color: {C.TEXT_MED}; border-bottom: 1px solid {C.BORDER_A}; padding-top: 6px; padding-bottom: 2px;")
        content_layout.addWidget(sec5)

        menu_options = [
            ("🔑  Configuración API", self._open_api_config),
            ("🤖  Agente Modelo", self._open_agent_model),
            ("⬆️  Actualizar AP0L0", self._check_for_updates),
            ("🔗  Navegador Seguro", self._launch_secure_browser),
            ("🔄  Vaciar Caché", self._clear_cache),
            ("🐧  JARVIS OS", self._launch_jarvis_os),
        ]
        for label, cb in menu_options:
            btn = QPushButton(label)
            btn.setFont(QFont("Segoe UI", 9))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(cb)
            content_layout.addWidget(btn)

        # ===== SECCIÓN 6: APAGADO =====
        sec6 = QLabel("⏻  APAGADO")
        sec6.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        sec6.setStyleSheet(f"color: {C.TEXT_MED}; border-bottom: 1px solid {C.BORDER_A}; padding-top: 6px; padding-bottom: 2px;")
        content_layout.addWidget(sec6)

        menu_options = [
            ("⏻  Apagar Sistema", self._shutdown_system),
            ("⟳  Reiniciar Sistema", self._restart_system),
            ("☾  Suspender Sistema", self._suspend_system),
            ("🔒  Bloquear Pantalla", self._lock_screen),
        ]
        for label, cb in menu_options:
            btn = QPushButton(label)
            btn.setFont(QFont("Segoe UI", 9))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(cb)
            content_layout.addWidget(btn)

        # Versión
        version_label = QLabel("PROTOCOLO C  |  XxchristoxX")
        version_label.setFont(QFont("Courier New", 8))
        version_label.setStyleSheet(f"color: {C.TEXT_DIM}; text-align: center; padding-top: 8px;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(version_label)

        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

        # Posicionar el menú a la izquierda debajo del botón
        self._float_menu.setGeometry(8, 55, 360, 560)

    def _update_float_menu_title(self):
        """Actualiza el título del menú flotante con el nombre actual del asistente."""
        if self._float_menu_title is not None:
            self._float_menu_title.setText(f"⚙️  CONTROLES_SISTEMA // {self._assistant_name}")

    def _toggle_float_menu(self):
        """Muestra u oculta el menú flotante con altura ajustable."""
        if self._float_menu is None:
            self._create_float_menu()

        if self._float_menu_visible:
            self._float_menu.hide()
            self._float_menu_visible = False
        else:
            # Usar altura dinámica: 85% de la ventana
            altura_max = int(self.height() * 0.85)
            # Asegurar que no sea menor a 600
            altura_max = max(600, altura_max)
            self._float_menu.setGeometry(8, 55, 360, altura_max)
            self._float_menu.show()
            self._float_menu.raise_()
            self._float_menu_visible = True

    # =====================================================================
    # FUNCIONES DEL MENÚ FLOTANTE
    # =====================================================================

    def _toggle_nemotron_asr(self):
        self._log.append_log("SYS: 🎙️ Nemotron ASR toggled")
        if self.on_text_command:
            self.on_text_command("toggle_nemotron_asr toggle")

    def _toggle_vision(self):
        self._log.append_log("SYS: 👁️ Visión toggled")
        if self.on_text_command:
            self.on_text_command("toggle_vision toggle")

    def _process_screen(self):
        """Solicita análisis de la pantalla usando el procesador de visión activo."""
        self._log.append_log("SYS: 🖥️ Procesando pantalla")
        def _run():
            try:
                from src.actions.screen_processor import screen_process
                ok = screen_process(
                    {"angle": "screen", "text": "Analiza lo que aparece en mi pantalla."},
                    player=self,
                )
                self._log.append_log("SYS: ✅ Pantalla enviada a visión" if ok else "SYS: ⚠️ Visión no disponible")
            except Exception as exc:
                self._log.append_log(f"SYS: ⚠️ Screen Processor: {exc}")
        threading.Thread(target=_run, daemon=True, name="ScreenProcessorMenu").start()

    def _analyze_camera(self):
        """Captura la cámara y solicita identificar objetos y movimientos visibles."""
        self._log.append_log("SYS: 📷 Analizando cámara y objeto en mano")
        def _run():
            try:
                from src.actions.screen_processor import screen_process
                ok = screen_process(
                    {"angle": "camera", "text": "Analiza la cámara. Identifica mis manos, los movimientos y describe con precisión qué objeto sostengo."},
                    player=self,
                )
                self._log.append_log("SYS: ✅ Cámara enviada a visión" if ok else "SYS: ⚠️ Cámara/visión no disponible")
            except Exception as exc:
                self._log.append_log(f"SYS: ⚠️ Análisis de cámara: {exc}")
        threading.Thread(target=_run, daemon=True, name="CameraVisionMenu").start()

    def _toggle_gpu_boost(self):
        self._log.append_log("SYS: ⚡ GPU Boost toggled")
        if self.on_text_command:
            self.on_text_command("toggle_gpu_boost toggle")

    def _toggle_keyboard(self):
        self._log.append_log("SYS: ⌨️ Teclado visual toggled")
        if self.on_text_command:
            self.on_text_command("toggle_keyboard toggle")

    def _toggle_holo_mode(self):
        self._log.append_log("SYS: ⬡ Holograma toggled")
        if self.on_text_command:
            self.on_text_command("toggle_holo_mode toggle")

    def _toggle_shopping_list(self):
        self._log.append_log("SYS: 🛒 Lista de compras toggled")
        if self.on_text_command:
            self.on_text_command("toggle_shopping_list toggle")

    def _toggle_iptv_player(self):
        self._log.append_log("SYS: 📺 IPTV toggled")
        if self.on_text_command:
            self.on_text_command("toggle_iptv_player toggle")

    def _toggle_uninstaller(self):
        self._log.append_log("SYS: 🗑️ Desinstalador toggled")
        if self.on_text_command:
            self.on_text_command("toggle_uninstaller toggle")

    def _toggle_winget_updater(self):
        self._log.append_log("SYS: 🚀 Actualizador winget toggled")
        if self.on_text_command:
            self.on_text_command("toggle_winget_updater toggle")

    def _toggle_antivirus(self):
        self._log.append_log("SYS: 🛡️ Antivirus toggled")
        if self.on_text_command:
            self.on_text_command("toggle_antivirus toggle")

    def _toggle_realtime_protection(self):
        self._log.append_log("SYS: 🛡️ Protección en tiempo real toggled")
        if self.on_text_command:
            self.on_text_command("toggle_realtime_protection toggle")

    def _toggle_vpn_client(self):
        self._log.append_log("SYS: 🌐 VPN toggled")
        if self.on_text_command:
            self.on_text_command("toggle_vpn_client toggle")

    def _toggle_smart_home(self):
        self._log.append_log("SYS: 🏠 Domótica toggled")
        if self.on_text_command:
            self.on_text_command("toggle_smart_home toggle")

    def _toggle_webcam(self):
        self._log.append_log("SYS: 📹 Webcam toggled")
        if self.on_text_command:
            self.on_text_command("toggle_webcam toggle")

    def _toggle_commands_list(self):
        self._log.append_log("SYS: 📋 Lista de comandos toggled")
        if self.on_text_command:
            self.on_text_command("toggle_commands_list toggle")

    def _toggle_android(self):
        self._log.append_log("SYS: 📱 Android toggled")
        if self.on_text_command:
            self.on_text_command("android_connect toggle")

    def _open_contacts(self):
        self._log.append_log("SYS: 👤 Abriendo contactos")
        if self.on_text_command:
            self.on_text_command("manage_contacts list")

    def _open_smarthome(self):
        """Abre el panel de domótica mediante el mismo canal de comandos del agente."""
        self._log.append_log("SYS: 🏠 Abriendo Smart Home")
        if self.on_text_command:
            self.on_text_command("smart_home open")

    def _start_clipboard_proactive(self):
        self._log.append_log("SYS: 📋 Portapapeles proactivo activado")
        if self.on_text_command:
            self.on_text_command("clipboard_proactive")

    def _create_quick_note(self):
        self._log.append_log("SYS: 📝 Creando nota rápida")
        if self.on_text_command:
            self.on_text_command("create_note")

    def _generate_report(self):
        self._log.append_log("SYS: 📊 Generando informe")
        if self.on_text_command:
            self.on_text_command("generate_report")

    def _open_performance_monitor(self):
        self._log.append_log("SYS: 💻 Abriendo monitor de rendimiento")
        if self.on_text_command:
            self.on_text_command("open_performance_monitor")

    def _show_cpu_temperature(self):
        self._log.append_log("SYS: 🌡️ Mostrando temperatura CPU")
        if self.on_text_command:
            self.on_text_command("show_cpu_temperature")

    def _select_microphone(self):
        self._log.append_log("SYS: 🎤 Abriendo selector de micrófono")
        if self.on_text_command:
            self.on_text_command("select_microphone")

    def _select_speakers(self):
        self._log.append_log("SYS: 🔊 Abriendo selector de altavoces")
        if self.on_text_command:
            self.on_text_command("select_speakers")

    def _open_api_config(self):
        self._log.append_log("SYS: 🔑 Abriendo configuración de APIs")
        if self.on_text_command:
            self.on_text_command("open_api_config")

    def _open_agent_model(self):
        self._log.append_log("SYS: 🤖 Abriendo selector de modelos")
        if self.on_text_command:
            self.on_text_command("open_agent_model")

    def _open_agent_tone(self):
        self._log.append_log("SYS: 🎭 Abriendo selector de tono")
        if self.on_text_command:
            self.on_text_command("open_agent_tone")

    def _check_for_updates(self):
        self._log.append_log("SYS: ⬆️ Buscando actualizaciones")
        if self.on_text_command:
            self.on_text_command("check_for_updates")

    def _launch_secure_browser(self):
        self._log.append_log("SYS: 🌐 Abriendo navegador seguro")
        if self.on_text_command:
            self.on_text_command("launch_secure_browser")

    def _launch_jarvis_os(self):
        self._log.append_log("SYS: 🐧 Iniciando JARVIS OS")
        if self.on_text_command:
            self.on_text_command("launch_jarvis_os")

    def _clear_cache(self):
        self._log.append_log("SYS: 🔄 Limpiando caché")
        if self.on_text_command:
            self.on_text_command("clear_cache")
        QMessageBox.information(self, "Caché", "La caché ha sido limpiada. Reinicia para aplicar cambios.")

    def _lock_screen(self):
        if IS_WINDOWS:
            try:
                ctypes.windll.user32.LockWorkStation()
            except Exception:
                pass
        elif IS_MAC:
            subprocess.run(["pmset", "displaysleepnow"])
        else:
            subprocess.run(["xdg-screensaver", "lock"])
        self._log.append_log("SYS: 🔒 Pantalla bloqueada")

    # =====================================================================
    # MÉTODOS DE CONTROL MULTIMEDIA
    # =====================================================================

    def _media_prev(self):
        try:
            import pyautogui
            pyautogui.press('prevtrack')
            self._log.append_log("SYS: ⏮ Canción anterior")
        except Exception:
            self._log.append_log("SYS: Control multimedia no disponible")

    def _media_play_pause(self):
        try:
            import pyautogui
            pyautogui.press('playpause')
            self._log.append_log("SYS: ⏯ Play/Pause")
        except Exception:
            self._log.append_log("SYS: Control multimedia no disponible")

    def _media_next(self):
        try:
            import pyautogui
            pyautogui.press('nexttrack')
            self._log.append_log("SYS: ⏭ Siguiente canción")
        except Exception:
            self._log.append_log("SYS: Control multimedia no disponible")

    # =====================================================================
    # MÉTODOS DE TOGGLES
    # =====================================================================

    def _on_clap_toggled(self, checked: bool):
        if self.on_text_command:
            self.on_text_command("toggle_clap_detection " + ("on" if checked else "off"))
        self._update_toggle_style(self._btn_clap, checked, "Aplausos")

    def _on_continuous_toggled(self, checked: bool):
        if self.on_text_command:
            self.on_text_command("toggle_continuous_listening " + ("on" if checked else "off"))
        self._update_toggle_style(self._btn_continuous, checked, "Escucha Continua")

    def _on_autostart_toggled(self, checked: bool):
        self._toggle_autostart()
        QTimer.singleShot(50, self._update_autostart_state)

    def _on_brief_toggled(self, checked: bool):
        self._toggle_brief()
        QTimer.singleShot(50, self._update_brief_state)

    def _update_toggle_style(self, btn: QPushButton, checked: bool, label: str):
        if checked:
            btn.setText(f"🟢  {label}: ON")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {C.GREEN};
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 8pt;
                    font-family: 'Segoe UI', 'Courier New', monospace;
                }}
                QPushButton:hover {{
                    background: #003d26;
                    color: {C.GREEN};
                }}
            """)
        else:
            btn.setText(f"🔴  {label}: OFF")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {C.MUTED_C};
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 8pt;
                    font-family: 'Segoe UI', 'Courier New', monospace;
                }}
                QPushButton:hover {{
                    background: #3d0f0f;
                    color: {C.MUTED_C};
                }}
            """)

    def _update_autostart_state(self):
        enabled = self._check_autostart()
        if hasattr(self, '_btn_autostart'):
            self._btn_autostart.blockSignals(True)
            self._btn_autostart.setChecked(enabled)
            self._update_toggle_style(self._btn_autostart, enabled, "Inicio Auto")
            self._btn_autostart.blockSignals(False)

    def _update_brief_state(self):
        from src.memory.config_manager import get_brief_enabled
        enabled = get_brief_enabled()
        if hasattr(self, '_btn_brief'):
            self._btn_brief.blockSignals(True)
            self._btn_brief.setChecked(enabled)
            self._update_toggle_style(self._btn_brief, enabled, "Resumen Matutino")
            self._btn_brief.blockSignals(False)

    def _update_all_toggle_states(self):
        self._update_autostart_state()
        self._update_brief_state()
        for key in ['clap', 'continuous']:
            btn = self._action_buttons.get(key)
            if btn:
                btn.blockSignals(True)
                btn.setChecked(False)
                self._update_toggle_style(btn, False, key.capitalize())
                btn.blockSignals(False)

    # =====================================================================
    # MÉTODOS ORIGINALES (CONSERVADOS)
    # =====================================================================

    def _toggle_aura_mode(self):
        if hasattr(self, '_btn_aura') and self._btn_aura.isChecked():
            self.on_text_command("activar modo aura")
        else:
            self.on_text_command("desactivar modo aura")

    def _toggle_continuous_listening(self):
        if hasattr(self, '_btn_continuous') and self._btn_continuous.isChecked():
            self.on_text_command("activar escucha continua")
        else:
            self.on_text_command("desactivar escucha continua")

    def _toggle_float_mode(self):
        self.float_handler.toggle_float_mode()

    def deactivate_floating_mode(self):
        self.float_handler.deactivate_float_mode()

    def start_camera_stream(self):
        self.camera_handler.start_stream()

    def _stop_camera_stream(self):
        self.camera_handler.stop_stream()

    def stop_camera_stream(self):
        self.camera_handler.stop_stream()

    def set_theme(self, accent_hex: str):
        self.theme_handler.set_theme(accent_hex)

    def _apply_ui_colors(self, cfg: dict = None):
        self.theme_handler.apply_ui_colors(cfg)

    def _apply_font_sizes(self, font_cfg: dict):
        self.theme_handler.apply_font_sizes(font_cfg)

    def _apply_wallpaper(self, path: str):
        self.theme_handler.apply_wallpaper(path)

    def _on_theme_changed(self, theme_hex: str):
        self.theme_handler.on_theme_changed(theme_hex)

    def _cleanup_timers(self):
        for timer_name in ['_metric_tmr', '_clock_tmr', '_cam_preview._timer', '_ctimer']:
            timer = getattr(self, timer_name, None)
            if timer and timer.isActive():
                timer.stop()

    def _shutdown_system(self):
        if IS_WINDOWS:
            reply = QMessageBox.question(
                self, "Apagar sistema",
                "¿Estás seguro de que quieres apagar el sistema?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                subprocess.run(["shutdown", "/s", "/t", "5"])
        else:
            QMessageBox.information(self, "Info", "Esta función solo está disponible en Windows.")

    def _restart_system(self):
        if IS_WINDOWS:
            reply = QMessageBox.question(
                self, "Reiniciar sistema",
                "¿Estás seguro de que quieres reiniciar el sistema?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                subprocess.run(["shutdown", "/r", "/t", "5"])
        else:
            QMessageBox.information(self, "Info", "Esta función solo está disponible en Windows.")

    def _suspend_system(self):
        if IS_WINDOWS:
            subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"])
        elif IS_MAC:
            subprocess.run(["pmset", "sleepnow"])
        else:
            subprocess.run(["systemctl", "suspend"])

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(28)
        w.setStyleSheet(f"background: {C.DARK}; border-top: 1px solid {C.BORDER};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 0, 14, 0)

        def _fl(txt, color=C.TEXT_MED):
            l = QLabel(txt)
            l.setFont(QFont("Courier New", 8))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_fl("[F4] Mute  ·  [F11] Fullscreen"))
        lay.addStretch()

        self._footer_dashboard_lbl = QLabel(f"{tr('Panel de control activo en')}: {self._dashboard_url}")
        self._footer_dashboard_lbl.setFont(QFont("Courier New", 8))
        self._footer_dashboard_lbl.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        lay.addWidget(self._footer_dashboard_lbl)

        lay.addStretch()
        lay.addWidget(_fl("By XxchristoxX", C.PRI_DIM))

        self._footer_clock_lbl = QLabel()
        self._footer_clock_lbl.setFont(QFont("Courier New", 8))
        self._footer_clock_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addWidget(self._footer_clock_lbl)

        return w

    def _on_file_selected(self, path: str):
        self._current_file = path
        p = Path(path)
        cat = _file_category(p)
        icon, _ = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size = _fmt_size(p.stat().st_size)
        self._file_hint.setText(f"{icon}  {p.name}  ·  {size}  ·  Tell {self._assistant_name} what to do with it")
        self._log.append_log(f"FILE: {p.name} ({size}) loaded")
        if self.on_text_command:
            msg = (
                f"[FILE_UPLOADED] path={path} | name={p.name} | "
                f"type={p.suffix.lstrip('.')} | size={size} | "
                f"Briefly tell the user you can see the file '{p.name}' "
                f"({size}) has been uploaded and ask what they'd like to do with it."
            )
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def _open_remote(self):
        if not self.on_remote_clicked:
            self._log.append_log("SYS: Dashboard not running — remote unavailable.")
            return
        result = self.on_remote_clicked()
        if not result:
            self._log.append_log("SYS: Could not generate remote key.")
            return
        url = result[0]
        key = result[1]
        auto = result[2] if len(result) >= 3 else ""
        manual = result[3] if len(result) >= 4 else url
        self.set_dashboard_url(url)

        if self._remote_overlay:
            self._remote_overlay._do_close()
        cw = self.centralWidget()
        ow, oh = RemoteKeyOverlay._OW, RemoteKeyOverlay._OH
        ov = RemoteKeyOverlay(url, key, auto_login_url=auto, manual_url=manual, expiry_secs=600, parent=cw)
        ov.set_new_key_callback(self.on_remote_clicked)
        ov.setGeometry((cw.width() - ow) // 2, (cw.height() - oh) // 2, ow, oh)
        ov.closed.connect(lambda: setattr(self, '_remote_overlay', None))
        ov.show()
        self._remote_overlay = ov
        self._log.append_log(f"SYS: Remote key generated — manual: {manual or url}")

    def _check_autostart(self) -> bool:
        try:
            if IS_WINDOWS:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
                try:
                    winreg.QueryValueEx(key, "AP0L0_AI")
                    return True
                except FileNotFoundError:
                    return False
                finally:
                    winreg.CloseKey(key)
            elif IS_MAC:
                return (Path.home() / "Library" / "LaunchAgents" / "com.apolo.assistant.plist").exists()
            else:
                return (Path.home() / ".config" / "autostart" / "apolo.desktop").exists()
        except Exception:
            return False

    def _toggle_autostart(self):
        currently_on = self._check_autostart()
        try:
            script = str(Path(__file__).resolve().parent / "main.py")
            if IS_WINDOWS:
                import winreg
                reg = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
                if currently_on:
                    winreg.DeleteValue(reg, "AP0L0_AI")
                else:
                    pythonw = Path(sys.executable).parent / "pythonw.exe"
                    exe = str(pythonw if pythonw.exists() else sys.executable)
                    winreg.SetValueEx(reg, "AP0L0_AI", 0, winreg.REG_SZ, f'"{exe}" "{script}"')
                winreg.CloseKey(reg)
            elif IS_MAC:
                plist_dir = Path.home() / "Library" / "LaunchAgents"
                plist_dir.mkdir(parents=True, exist_ok=True)
                plist = plist_dir / "com.apolo.assistant.plist"
                if currently_on:
                    plist.unlink(missing_ok=True)
                else:
                    plist.write_text(
                        '<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                        '<plist version="1.0"><dict>\n'
                        '  <key>Label</key><string>com.apolo.assistant</string>\n'
                        '  <key>ProgramArguments</key><array>\n'
                        f'    <string>{sys.executable}</string>\n'
                        f'    <string>{script}</string>\n'
                        '  </array>\n'
                        '  <key>RunAtLoad</key><true/>\n'
                        '</dict></plist>\n'
                    )
            else:
                desk_dir = Path.home() / ".config" / "autostart"
                desk_dir.mkdir(parents=True, exist_ok=True)
                desk = desk_dir / "apolo.desktop"
                if currently_on:
                    desk.unlink(missing_ok=True)
                else:
                    desk.write_text(
                        "[Desktop Entry]\n"
                        f"Name={self._assistant_name}\n"
                        f"Exec={sys.executable} {script}\n"
                        "Type=Application\nTerminal=false\n"
                        "X-GNOME-Autostart-enabled=true\n"
                    )
            enabled = not currently_on
            self._update_autostart_state()
            self._log.append_log(f"SYS: Auto-start {'enabled' if enabled else 'disabled'}.")
        except Exception as e:
            self._log.append_log(f"ERR: Auto-start failed — {e}")

    def _toggle_brief(self):
        from src.memory.config_manager import get_brief_enabled, save_brief_enabled
        self._brief_enabled = not get_brief_enabled()
        save_brief_enabled(self._brief_enabled)
        self._update_brief_state()

    def _open_customize(self):
        cfg = _read_full_config()
        if self._customize_overlay:
            self._customize_overlay.hide()
        cw = self.centralWidget()
        ov = CustomizeOverlay(
            cfg.get("assistant_name", "APOLO"),
            cfg.get("user_name", "Christopher"),
            cfg,
            parent=cw,
            main_window=self
        )
        ow, oh = CustomizeOverlay._OW, CustomizeOverlay._OH
        oh = min(oh, cw.height() - 16)
        ov.setGeometry((cw.width() - ow) // 2, (cw.height() - oh) // 2, ow, oh)
        ov.saved.connect(self._apply_customization)
        ov.language_changed.connect(self._on_language_changed_global)
        ov.response_mode_changed.connect(self._on_response_mode_changed)
        ov.focus_mode_toggled.connect(self._on_focus_mode_toggled)
        ov.show()
        self._customize_overlay = ov

    def _on_response_mode_changed(self, mode: str):
        self._response_mode = mode
        if self.on_response_mode_change:
            self.on_response_mode_change(mode)
        self._log.append_log(f"SYS: Modo de respuesta: {mode}")

    def _on_focus_mode_toggled(self, enabled: bool):
        self._focus_mode = enabled
        if self.on_focus_mode_toggle:
            self.on_focus_mode_toggle(enabled)
        self._log.append_log(f"SYS: Modo No Molestar {'activado' if enabled else 'desactivado'}")

    @pyqtSlot(str, str, str, str, str)
    def _apply_customization(self, name: str, user_name: str, ui_color: str, personality: str, voice: str):
        subtitles = {
            "jarvis": "Just A Rather Very Intelligent System",
            "agata": "Advanced Generative Assistant for Technology & Art",
            "tony": "Technology Oriented Network Yield",
            "friday": "Female Replacement Intelligent Digital Assistant Youth",
            "apolo": "Autonomous Platform for Orchestration, Learning and Operations"
        }
        subtitle = subtitles.get(personality, "Autonomous Platform for Orchestration, Learning and Operations")

        self.update_title_and_subtitle(name, subtitle)
        self._personality = personality
        self._voice = voice
        self._theme_color = ui_color

        self._log._ai_name_lc = name.lower()
        self.hud._assistant_name = name.upper()
        self.hud.persona = personality

        self.set_personality_info(personality, voice, ui_color)

        try:
            cfg = _read_full_config()
            cfg["assistant_name"] = name
            cfg["assistant_subtitle"] = subtitle
            cfg["user_name"] = user_name
            cfg["personality"] = personality
            cfg["voice"] = voice
            cfg["ui_color"] = ui_color
            _save_config(cfg)

            QTimer.singleShot(0, lambda: self._apply_ui_colors(cfg))
            font_cfg = {}
            for k in ["font_size_header", "font_size_left", "font_size_right", "font_size_center", "font_size_footer"]:
                font_cfg[k] = cfg.get(k, 10)
            QTimer.singleShot(50, lambda: self._apply_font_sizes(font_cfg))
            QTimer.singleShot(100, lambda: self._update_badges())
            QTimer.singleShot(150, lambda: self._update_ui_texts())

            wallpaper_path = cfg.get("wallpaper_path", "")
            if wallpaper_path and Path(wallpaper_path).exists():
                QTimer.singleShot(150, lambda: self._apply_wallpaper(wallpaper_path))
                self._set_windows_wallpaper(wallpaper_path)
            else:
                self._set_windows_wallpaper("")

            if cfg.get("ui_icon_path"):
                QTimer.singleShot(0, lambda: self.update_icon(cfg["ui_icon_path"]))
            if cfg.get("face_image_path"):
                QTimer.singleShot(0, lambda: self.update_face_image(cfg["face_image_path"]))

            if self.on_personality_change:
                self.on_personality_change(personality, voice)
            if self.on_response_mode_change:
                self.on_response_mode_change(self._response_mode)
            if self.on_focus_mode_toggle:
                self.on_focus_mode_toggle(self._focus_mode)

            self._log.append_log(f"SYS: Personalización aplicada. Personalidad: {personality.capitalize()}")
            self._log.append_log(f"SYS: Modo de respuesta: {self._response_mode}")

        except Exception as e:
            self._log.append_log(f"ERR: Guardado falló — {e}")

    @pyqtSlot(str, str)
    def update_title_and_subtitle(self, name: str, subtitle: str):
        self._assistant_name = name
        self._assistant_subtitle = subtitle
        self._title_lbl.setText(name.upper())
        self._sub_lbl.setText(subtitle)
        self.setWindowTitle(f"{name.upper()} — XxchristoxX")
        self.hud._assistant_name = name.upper()
        self._update_badges()
        self._update_ui_texts()
        self._update_float_menu_title()  # Actualizar título del menú flotante

    @pyqtSlot(str, str, str)
    def set_personality_info(self, personality: str, voice: str, theme_color: str):
        """Sincroniza personalidad, voz, tema, HUD y panel en una sola operación."""
        from src.config.personality import PERSONALITY_INFO, DEFAULT_PERSONALITY
        from src.config.themes import THEME_MAP, VOICE_MAP

        key = (personality or DEFAULT_PERSONALITY).strip().lower()
        if key not in PERSONALITY_INFO:
            key = DEFAULT_PERSONALITY
        profile = PERSONALITY_INFO[key]
        selected_voice = (voice or VOICE_MAP.get(key) or profile["voice"]).strip()
        selected_color = (theme_color or THEME_MAP.get(key) or profile["color"]).strip()

        self._personality = key
        self._voice = selected_voice
        self._theme_color = selected_color
        apply_theme(key)
        # El perfil personalizado tiene prioridad sobre el acento base del tema.
        apply_ui_accent(selected_color)
        self._apply_ui_colors()
        self.hud.persona = key
        self.hud._assistant_name = self._assistant_name.upper()
        self.hud.update()
        if self.panel:
            self.panel.set_theme_color(selected_color)
        self._update_badges()
        self._update_ui_texts()
        self._update_float_menu_title()  # Actualizar título del menú flotante

    @pyqtSlot(str, str, str, str)
    def apply_full_theme(self, personality: str, name: str, subtitle: str, theme_color: str):
        old_palette = current_palette()
        apply_theme(personality)
        self._assistant_name = name
        self._assistant_subtitle = subtitle
        self._title_lbl.setText(name.upper())
        self._sub_lbl.setText(subtitle)
        self.setWindowTitle(f"{name.upper()} — XxchristoxX")
        self.hud.persona = personality.lower()
        self.hud._assistant_name = name.upper()
        self.hud.update()
        self._apply_ui_colors()
        if self.panel:
            self.panel.set_theme_color(theme_color)
        self._update_badges()
        self._update_ui_texts()
        self._update_float_menu_title()  # Actualizar título del menú flotante

    def update_icon(self, path: str):
        try:
            if Path(path).exists():
                self.setWindowIcon(QIcon(path))
        except Exception as e:
            print(f"[UI] Error actualizando icono: {e}")

    def update_face_image(self, path: str):
        try:
            if Path(path).exists():
                self.hud.reload_face(path)
        except Exception as e:
            print(f"[UI] Error actualizando cara: {e}")

    def _set_windows_wallpaper(self, path: str):
        if platform.system() == "Windows":
            try:
                if path and Path(path).exists():
                    ctypes.windll.user32.SystemParametersInfoW(20, 0, str(path), 3)
                else:
                    ctypes.windll.user32.SystemParametersInfoW(20, 0, "", 3)
            except Exception as e:
                print(f"[Wallpaper] No se pudo establecer fondo de Windows: {e}")

    def _apply_full_config(self, cfg: dict):
        try:
            self._apply_ui_colors(cfg)
            font_cfg = {}
            for k in ["font_size_header", "font_size_left", "font_size_right", "font_size_center", "font_size_footer"]:
                font_cfg[k] = cfg.get(k, 10)
            self._apply_font_sizes(font_cfg)

            wallpaper_path = cfg.get("wallpaper_path", "")
            if wallpaper_path and Path(wallpaper_path).exists():
                self._apply_wallpaper(wallpaper_path)
                self._set_windows_wallpaper(wallpaper_path)
            else:
                self._set_windows_wallpaper("")

            if cfg.get("ui_icon_path"):
                self.update_icon(cfg["ui_icon_path"])
            if cfg.get("face_image_path"):
                self.update_face_image(cfg["face_image_path"])

            self._update_badges()
            self._update_ui_texts()
            self._update_autostart_state()
            self._update_brief_state()

        except Exception as e:
            print(f"[UI] Error aplicando configuración: {e}")

    def _show_content(self, title: str, text: str):
        import time as _time
        self._content_title_lbl.setText(title.upper()[:48])
        self._content_ts_lbl.setText(_time.strftime("%H:%M:%S"))
        self._content_display.setPlainText(text)
        self._content_display.moveCursor(
            self._content_display.textCursor().MoveOperation.Start
        )
        first_show = not self._content_panel.isVisible()
        self._content_panel.show()
        if first_show:
            total = self._center_split.height()
            self._center_split.setSizes([max(total - 220, 120), 220])

    def _show_camera_frame(self, img_bytes: bytes):
        self._cam_preview.show_frame(img_bytes)

    def _toggle_always_on_top(self):
        self._always_on_top = not self._always_on_top
        if self._always_on_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            self._top_btn.setChecked(True)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
            self._top_btn.setChecked(False)
        self.show()

    def _clear_logs(self):
        self._log.clear_log()
        self._log.append_log("SYS: Registro limpiado")

    def _export_logs(self):
        self._log.export_log()

    def set_focus_mode(self, enabled: bool):
        self._focus_mode = enabled
        self._log.append_log(f"SYS: Modo No Molestar {'activado' if enabled else 'desactivado'}")

    def write_log(self, text: str):
        self._log.append_log(text)

    def _send(self):
        txt = self._input.text().strip()
        if not txt:
            return
        self._input.clear()
        self._log.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _do_interrupt(self):
        if self.on_interrupt:
            self.on_interrupt()

    def _toggle_mute(self):
        self._muted = not self._muted
        self.hud.muted = self._muted
        self._style_mute_btn()
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Microphone active.")
        if self.panel:
            self.panel.set_mic_state(self._muted)

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setText(" " + tr("MICROPHONE MUTED"))
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #140006; color: {C.MUTED_C};
                    border: 1px solid {C.MUTED_C}; border-radius: 4px;
                }}
            """)
        else:
            self._mute_btn.setText(" " + tr("MICROPHONE ACTIVE"))
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #00140a; color: {C.GREEN};
                    border: 1px solid {C.GREEN}; border-radius: 4px;
                }}
                QPushButton:hover {{ background: #001f10; }}
            """)

    def _apply_state(self, state: str):
        self.hud.state = state
        self.hud.speaking = (state == "SPEAKING")

    def _check_config(self) -> bool:
        if not API_FILE.exists():
            return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key")) and bool(d.get("os_system"))
        except Exception:
            return False

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        cw = self.centralWidget()
        ow, oh = 460, 390
        ov.setGeometry((cw.width() - ow) // 2, (cw.height() - oh) // 2, ow, oh)
        ov.done.connect(self._on_setup_done)
        ov.show()
        self._overlay = ov

    def _on_setup_done(self, key: str, os_name: str):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        API_FILE.write_text(json.dumps({"gemini_api_key": key, "os_system": os_name}, indent=4), encoding="utf-8")
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        self._apply_state("LISTENING")
        self._assistant_name = _read_full_config().get("assistant_name", "APOLO")
        self._log.append_log(f"SYS: Initialised. OS={os_name.upper()}. {self._assistant_name} online.")
        self._update_float_menu_title()

    def _tick_clock(self):
        now = time.localtime()
        if hasattr(self, '_clock_lbl'):
            self._clock_lbl.setText(time.strftime("%H:%M:%S", now))
        if hasattr(self, '_date_lbl'):
            self._date_lbl.setText(time.strftime("%A, %d %B %Y", now))
        if hasattr(self, '_footer_clock_lbl'):
            self._footer_clock_lbl.setText(time.strftime("%H:%M  %d/%m/%Y", now))

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _toggle_drawer(self):
        self._log.append_log("SYS: El menú deslizante ha sido reemplazado por el menú flotante.")
        return

    def _create_desktop_shortcut(self):
        script = Path(__file__).resolve().parent / "main.py"
        python = Path(sys.executable)
        desktop = _get_desktop_dir()

        cfg = _read_full_config()
        shortcut_name = cfg.get("shortcut_name", "AP0L0")
        custom_icon = cfg.get("shortcut_icon", "")

        if custom_icon and Path(custom_icon).exists():
            ico_path = Path(custom_icon)
        else:
            ico_path = Path(__file__).resolve().parent / "config" / "apolo.ico"
            if not ico_path.exists():
                _build_jarvis_icon(ico_path)

        try:
            if IS_WINDOWS:
                pythonw = python.parent / "pythonw.exe"
                target = str(pythonw if pythonw.exists() else python)
                lnk = str(desktop / f"{shortcut_name}.lnk")
                icon_loc = str(ico_path) if ico_path.exists() else f"{target},0"
                _create_lnk_windows(lnk, target, str(script), str(script.parent), icon_loc)

            elif IS_MAC:
                app = desktop / f"{shortcut_name}.app"
                mac_dir = app / "Contents" / "MacOS"
                res_dir = app / "Contents" / "Resources"
                mac_dir.mkdir(parents=True, exist_ok=True)
                res_dir.mkdir(exist_ok=True)

                launcher = mac_dir / f"{shortcut_name}"
                launcher.write_text(
                    "#!/usr/bin/env bash\n"
                    f'cd "{script.parent}"\n'
                    f'exec "{python}" "{script}"\n'
                )
                launcher.chmod(launcher.stat().st_mode | 0o755)

                (app / "Contents" / "Info.plist").write_text(
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                    '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                    '<plist version="1.0"><dict>\n'
                    f'  <key>CFBundleExecutable</key><string>{shortcut_name}</string>\n'
                    f'  <key>CFBundleName</key><string>{shortcut_name}</string>\n'
                    '  <key>CFBundlePackageType</key><string>APPL</string>\n'
                    '  <key>CFBundleVersion</key><string>1.0</string>\n'
                    '</dict></plist>\n'
                )

                try:
                    if ico_path.exists():
                        import PIL.Image
                        icns = res_dir / "AppIcon.icns"
                        PIL.Image.open(ico_path).save(icns, format="ICNS")
                        plist = app / "Contents" / "Info.plist"
                        txt = plist.read_text()
                        plist.write_text(
                            txt.replace(
                                '</dict></plist>',
                                '  <key>CFBundleIconFile</key>'
                                '<string>AppIcon</string>\n</dict></plist>\n',
                            )
                        )
                except Exception:
                    pass

            else:
                png_path = ico_path.with_suffix(".png")
                if not png_path.exists() and ico_path.exists():
                    try:
                        import PIL.Image
                        PIL.Image.open(ico_path).resize(
                            (256, 256), PIL.Image.LANCZOS
                        ).save(png_path, format="PNG")
                    except Exception:
                        png_path = ico_path
                icon_line = f"Icon={png_path}\n" if png_path.exists() else ""
                desk = desktop / f"{shortcut_name}.desktop"
                desk.write_text(
                    "[Desktop Entry]\n"
                    f"Name={shortcut_name}\n"
                    f"Exec={python} {script}\n"
                    f"Path={script.parent}\n"
                    "Type=Application\n"
                    "Terminal=false\n"
                    "Categories=Utility;\n"
                    + icon_line
                )
                desk.chmod(desk.stat().st_mode | 0o755)

            self._log.append_log("SYS: Desktop shortcut created.")
        except Exception as e:
            self._log.append_log(f"ERR: Shortcut failed — {e}")

    def _open_dashboard(self):
        try:
            import webbrowser
            if self._dashboard_url != "No conectado":
                webbrowser.open(self._dashboard_url)
            else:
                self._log.append_log("SYS: Dashboard no disponible. Espera a que el servidor se inicie.")
        except Exception as e:
            self._log.append_log(f"ERR: No se pudo abrir el dashboard: {e}")

    def _restart_assistant(self):
        if self.on_restart_assistant:
            self.on_restart_assistant()
        else:
            self._log.append_log("SYS: Restart requested but callback not set.")

    def _show_about(self):
        about_text = f"""
        <b>AP0L0 — Autonomous Platform for Orchestration, Learning and Operations</b><br>
        <br>
        <b>Versión:</b> 9.5<br>
        <b>Autor:</b> XxchristoxX<br>
        <b>Sistema:</b> {_OS}<br>
        <br>
        <i>Powered by Gemini Live API</i>
        """
        QMessageBox.about(self, tr("ACERCA DE"), about_text)

    def _on_language_changed_global(self, lang_code: str):
        self._update_ui_texts()

    def _update_ui_texts(self):
        self.setWindowTitle(f"{self._assistant_name} — XxchristoxX")
        if hasattr(self, '_left_panel_title'):
            self._left_panel_title.setText(tr("SYS MONITOR"))
        if hasattr(self, '_right_panel_title'):
            self._right_panel_title.setText(tr("ACTIVITY LOG"))
        if hasattr(self, '_file_upload_label'):
            self._file_upload_label.setText(tr("FILE UPLOAD"))
        if hasattr(self, '_command_input_label'):
            self._command_input_label.setText(tr("COMMAND INPUT"))
        self._interrupt_btn.setText(tr("INTERRUPT  [ESC]"))
        self._mute_btn.setText(tr("MICROPHONE ACTIVE") if not self._muted else tr("MICROPHONE MUTED"))
        if hasattr(self, '_btn_autostart'):
            self._btn_autostart.setText(tr("AUTO-START: ON") if self._check_autostart() else tr("AUTO-START: OFF"))
        if hasattr(self, '_btn_brief'):
            self._btn_brief.setText(tr("MORNING BRIEF: ON") if self._brief_enabled else tr("MORNING BRIEF: OFF"))
        # Los botones del encabezado se construyen desde el módulo modular y
        # deben actualizarse sin reiniciar la aplicación.
        header_labels = {
            "_btn_remote": "REMOTE", "_btn_shortcut": "SHORTCUT",
            "_btn_customize": "CUSTOMISE", "_btn_restart": "RESTART",
            "_btn_about": "ABOUT", "_btn_float": "FLOAT",
            "_btn_dashboard": "DASHBOARD", "_btn_clear": "CLEAR LOG",
            "_btn_export": "EXPORT LOG", "_btn_contacts": "CONTACTS",
            "_btn_smarthome": "SMARTHOME", "_btn_android": "ANDROID",
        }
        for attr, key in header_labels.items():
            button = getattr(self, attr, None)
            if button is not None:
                icon = button.text().split("  ", 1)[0]
                button.setText(f"{icon}  {tr(key)}")
        self._update_badges()
        self._update_footer_texts()
        self._update_float_menu_title()

    def _update_footer_texts(self):
        if hasattr(self, '_footer_dashboard_lbl'):
            self._footer_dashboard_lbl.setText(f"{tr('Panel de control activo en')}: {self._dashboard_url}")

    def _update_badges(self):
        if not hasattr(self, '_badge_labels') or not isinstance(self._badge_labels, list):
            return
        cfg = _read_full_config()
        badge_texts = [
            cfg.get("badge1_text", "AI CORE ACTIVE"),
            cfg.get("badge2_text", "SEC CLEARED"),
            cfg.get("badge3_text", "PROTOCOL XLIX"),
            cfg.get("badge4_text", "READY"),
            cfg.get("badge5_text", "ONLINE"),
        ]
        badge_colors = [
            cfg.get("badge1_color", "#00ff88"),
            cfg.get("badge2_color", "#00d4ff"),
            cfg.get("badge3_color", "#5ab8cc"),
            cfg.get("badge4_color", "#ffcc00"),
            cfg.get("badge5_color", "#ff6b00"),
        ]
        for i, lbl in enumerate(self._badge_labels):
            if i < len(badge_texts):
                lbl.setText(tr(badge_texts[i]))
                lbl.setStyleSheet(
                    f"color: {badge_colors[i]}; background: {C.PANEL2};"
                    f"border: 1px solid {C.BORDER_A}; border-radius: 3px; padding: 4px;"
                )

    def set_dashboard_url(self, url: str):
        self._dashboard_url = url
        self._update_footer_texts()

    def notify_phone_connected(self) -> None:
        if self._remote_overlay and self._remote_overlay.isVisible():
            self._remote_overlay.mark_connected()

    def refresh_customize_overlay(self):
        if self._customize_overlay and self._customize_overlay.isVisible():
            self._customize_overlay._refresh_all_tabs()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cw = self.centralWidget()
        if self._overlay and self._overlay.isVisible():
            ow, oh = 460, 390
            self._overlay.setGeometry(
                (cw.width() - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        if self._remote_overlay and self._remote_overlay.isVisible():
            ow, oh = RemoteKeyOverlay._OW, RemoteKeyOverlay._OH
            self._remote_overlay.setGeometry(
                (cw.width() - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        if self._customize_overlay and self._customize_overlay.isVisible():
            ow, oh = CustomizeOverlay._OW, CustomizeOverlay._OH
            self._customize_overlay.setGeometry(
                (cw.width() - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        pw = _CameraPreview._W
        ph = self._cam_preview.height() or _CameraPreview._H
        self._cam_preview.setGeometry(
            cw.width() - RIGHT_W - pw - 12,
            cw.height() - ph - 28,
            pw, ph,
        )
        if hasattr(self, '_clipboard_panel') and self._clipboard_panel.isVisible():
            self._position_clipboard_panel()
        if self._float_menu and self._float_menu.isVisible():
            self._float_menu.setGeometry(8, 55, 360, min(560, cw.height() - 80))

    def _position_clipboard_panel(self):
        self.clipboard_handler._position_clipboard_panel()

    def closeEvent(self, event):
        self.tray_handler.close_event(event)

    # =====================================================================
    # MÉTODOS DE CONSTRUCCIÓN DE PANELES (SIN CAMBIOS)
    # =====================================================================

    def _make_badge(self, txt, color):
        l = QLabel(txt)
        l.setFont(QFont("Courier New", 8))
        l.setStyleSheet(f"color: {color}; background: transparent;")
        return l

    def _build_left_panel(self) -> QWidget:
        from src.ui.widgets import (
            SystemStatusWidget, BatteryWidget, WeatherWidget,
            CalendarWidget, TimerWidget,
            TemperatureWidget, SwapWidget, NetworkGraphWidget
        )

        panel = QWidget()
        panel.setFixedWidth(LEFT_W)
        panel.setStyleSheet(f"background: {C.PANEL}; border-right: 1px solid {C.BORDER};")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._left_panel_title = QLabel(tr("SYS MONITOR"))
        self._left_panel_title.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        self._left_panel_title.setStyleSheet(
            f"color: {C.PRI}; background: transparent; "
            f"border-bottom: 1px solid {C.BORDER}; padding: 6px 8px;"
        )
        layout.addWidget(self._left_panel_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setStyleSheet(f"background: {C.PANEL};")
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 2, 2, 2)
        content_layout.setSpacing(4)

        def get_group_style():
            return f"""
                QGroupBox {{
                    color: {C.PRI};
                    border: 1px solid {C.BORDER_A};
                    border-radius: 4px;
                    margin-top: 12px;
                    padding-top: 8px;
                    font-weight: bold;
                    font-size: 8pt;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 8px;
                    padding: 0 6px 0 6px;
                    background-color: {C.PANEL};
                    color: {C.PRI};
                }}
            """

        self.sys_group = QGroupBox("🖥️  SISTEMA")
        self.sys_group.setStyleSheet(get_group_style())
        sys_layout = QVBoxLayout(self.sys_group)
        sys_layout.setContentsMargins(4, 4, 4, 4)
        self.system_widget = SystemStatusWidget()
        self.system_widget.setMaximumHeight(1800)
        sys_layout.addWidget(self.system_widget)
        content_layout.addWidget(self.sys_group)

        self.batt_group = QGroupBox("🔋  BATERÍA")
        self.batt_group.setStyleSheet(get_group_style())
        batt_layout = QVBoxLayout(self.batt_group)
        batt_layout.setContentsMargins(4, 4, 4, 4)
        self.battery_widget = BatteryWidget()
        self.battery_widget.setFixedHeight(70)
        batt_layout.addWidget(self.battery_widget)
        content_layout.addWidget(self.batt_group)

        self.net_group = QGroupBox("📶  TRÁFICO DE RED")
        self.net_group.setStyleSheet(get_group_style())
        net_layout = QVBoxLayout(self.net_group)
        net_layout.setContentsMargins(4, 4, 4, 4)
        self.network_widget = NetworkGraphWidget()
        self.network_widget.setFixedHeight(80)
        net_layout.addWidget(self.network_widget)
        content_layout.addWidget(self.net_group)

        self.weather_group = QGroupBox("🌤️  CLIMA")
        self.weather_group.setStyleSheet(get_group_style())
        weather_layout = QVBoxLayout(self.weather_group)
        weather_layout.setContentsMargins(4, 4, 4, 4)
        self.weather_widget = WeatherWidget()
        self.weather_widget.setFixedHeight(80)
        weather_layout.addWidget(self.weather_widget)
        content_layout.addWidget(self.weather_group)

        self.swap_group = QGroupBox("💾  MEMORIA SWAP")
        self.swap_group.setStyleSheet(get_group_style())
        swap_layout = QVBoxLayout(self.swap_group)
        swap_layout.setContentsMargins(4, 4, 4, 4)
        self.swap_widget = SwapWidget()
        self.swap_widget.setFixedHeight(30)
        swap_layout.addWidget(self.swap_widget)
        content_layout.addWidget(self.swap_group)

        self.control_group = QGroupBox("⚙  CONTROL")
        self.control_group.setStyleSheet(get_group_style())
        control_layout = QHBoxLayout(self.control_group)
        control_layout.setContentsMargins(4, 4, 4, 4)
        control_layout.setSpacing(4)

        btn_base_style = """
            QPushButton {
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 2px;
                font-weight: bold;
                font-size: 7pt;
                font-family: 'Segoe UI', 'Courier New', monospace;
            }
            QPushButton:hover { opacity: 0.85; }
            QPushButton:pressed { opacity: 0.70; }
        """

        self.shutdown_btn = QPushButton("⏻  Apagar")
        self.shutdown_btn.setStyleSheet(btn_base_style + "background: #d32f2f !important;")
        self.shutdown_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.shutdown_btn.clicked.connect(self._shutdown_system)
        control_layout.addWidget(self.shutdown_btn)

        self.restart_btn = QPushButton("⟳  Reiniciar")
        self.restart_btn.setStyleSheet(btn_base_style + "background: #f57c00 !important;")
        self.restart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restart_btn.clicked.connect(self._restart_system)
        control_layout.addWidget(self.restart_btn)

        self.sleep_btn = QPushButton("☾  Suspender")
        self.sleep_btn.setStyleSheet(btn_base_style + "background: #1976d2 !important;")
        self.sleep_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sleep_btn.clicked.connect(self._suspend_system)
        control_layout.addWidget(self.sleep_btn)

        content_layout.addWidget(self.control_group)
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

        cfg = _read_full_config()
        badge_texts = [
            cfg.get("badge1_text", "AI CORE ACTIVE"),
            cfg.get("badge2_text", "SEC CLEARED"),
            cfg.get("badge3_text", "PROTOCOL XLIX"),
            cfg.get("badge4_text", "READY"),
            cfg.get("badge5_text", "ONLINE"),
        ]
        badge_colors = [
            cfg.get("badge1_color", "#00ff88"),
            cfg.get("badge2_color", "#00d4ff"),
            cfg.get("badge3_color", "#5ab8cc"),
            cfg.get("badge4_color", "#ffcc00"),
            cfg.get("badge5_color", "#ff6b00"),
        ]
        self._badge_labels = []
        for txt, col in zip(badge_texts, badge_colors):
            lbl = QLabel(tr(txt))
            lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {col}; background: {C.PANEL2};"
                f"border: 1px solid {C.BORDER_A}; border-radius: 3px; "
                f"padding: 4px; margin: 2px 6px;"
            )
            layout.addWidget(lbl)
            self._badge_labels.append(lbl)

        layout.addStretch()
        return panel

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(RIGHT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-left: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        self._right_panel_title = QLabel(tr("ACTIVITY LOG"))
        self._right_panel_title.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._right_panel_title.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(self._right_panel_title)

        self._log = LogWidget()
        lay.addWidget(self._log, stretch=1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        self._file_upload_label = QLabel(tr("FILE UPLOAD"))
        self._file_upload_label.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._file_upload_label.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(self._file_upload_label)

        self._drop_zone = FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._drop_zone)

        self._file_hint = QLabel("No file loaded — drop or click above to upload")
        self._file_hint.setFont(QFont("Courier New", 7))
        self._file_hint.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._file_hint.setWordWrap(True)
        lay.addWidget(self._file_hint)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep2)

        self._command_input_label = QLabel(tr("COMMAND INPUT"))
        self._command_input_label.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._command_input_label.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(self._command_input_label)

        lay.addLayout(self._build_input_row())

        self._interrupt_btn = QPushButton(tr("✋ INTERRUPT  [ESC]"))
        self._interrupt_btn.setFixedHeight(36)
        self._interrupt_btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        self._interrupt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._interrupt_btn.setStyleSheet(f"""
            QPushButton {{
                background: #140008; color: {C.MUTED_C};
                border: 1px solid {C.MUTED_C}; border-radius: 4px;
            }}
            QPushButton:hover {{ background: #200010; border: 1px solid #ff6688; }}
            QPushButton:pressed {{ background: #300018; }}
        """)
        self._interrupt_btn.clicked.connect(self._do_interrupt)
        lay.addWidget(self._interrupt_btn)

        self._mute_btn = QPushButton(tr("🎙 MICROPHONE ACTIVE"))
        self._mute_btn.setFixedHeight(32)
        self._mute_btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._style_mute_btn()
        lay.addWidget(self._mute_btn)

        return w

    def _build_input_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(5)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command or question…")
        self._input.setFont(QFont("Courier New", 10))
        self._input.setFixedHeight(32)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d14; color: {C.WHITE};
                border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input)

        self._send_btn = QPushButton("▸")
        self._send_btn.setFixedSize(32, 32)
        self._send_btn.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 4px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        self._send_btn.clicked.connect(self._send)
        row.addWidget(self._send_btn)

        return row

    def _build_content_panel(self) -> QWidget:
        w = QWidget()
        w.setObjectName("ContentPanel")
        w.setStyleSheet(f"""
            QWidget#ContentPanel {{
                background: {C.PANEL};
                border-top: 1px solid {C.BORDER_B};
            }}
        """)
        w.hide()

        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 8, 14, 10)
        lay.setSpacing(5)

        hdr = QHBoxLayout()
        hdr.setSpacing(6)

        self._content_dot = QLabel("◈")
        self._content_dot.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        self._content_dot.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(self._content_dot)

        self._content_title_lbl = QLabel("BRIEFING")
        self._content_title_lbl.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        self._content_title_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 1px;")
        hdr.addWidget(self._content_title_lbl)
        hdr.addStretch()

        self._content_ts_lbl = QLabel("")
        self._content_ts_lbl.setFont(QFont("Courier New", 7))
        self._content_ts_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        hdr.addWidget(self._content_ts_lbl)

        dismiss = QPushButton("DISMISS  ✕")
        dismiss.setFont(QFont("Courier New", 7))
        dismiss.setFixedHeight(20)
        dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 0 8px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        dismiss.clicked.connect(w.hide)
        hdr.addWidget(dismiss)
        lay.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};")
        lay.addWidget(sep)

        self._content_display = QTextEdit()
        self._content_display.setReadOnly(True)
        self._content_display.setFont(QFont("Courier New", 9))
        self._content_display.setMinimumHeight(70)
        self._content_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._content_display.setStyleSheet(f"""
            QTextEdit {{
                background: {C.DARK};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 6px 8px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: {C.BG}; width: 6px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B}; border-radius: 3px; min-height: 16px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0; border: none;
            }}
        """)
        lay.addWidget(self._content_display)

        return w


# =====================================================================
# ROOT SHIM Y JARVIS UI WRAPPER
# =====================================================================

class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app

    def mainloop(self):
        self._app.exec()

    def protocol(self, *_):
        pass


class JarvisUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        self._win.showFullScreen()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._drop_zone.current_file()

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    @property
    def on_remote_clicked(self):
        return self._win.on_remote_clicked

    @on_remote_clicked.setter
    def on_remote_clicked(self, cb):
        self._win.on_remote_clicked = cb

    @property
    def on_interrupt(self):
        return self._win.on_interrupt

    @on_interrupt.setter
    def on_interrupt(self, cb):
        self._win.on_interrupt = cb

    @property
    def on_personality_change(self):
        return self._win.on_personality_change

    @on_personality_change.setter
    def on_personality_change(self, cb):
        self._win.on_personality_change = cb

    @property
    def on_restart_assistant(self):
        return self._win.on_restart_assistant

    @on_restart_assistant.setter
    def on_restart_assistant(self, cb):
        self._win.on_restart_assistant = cb

    @property
    def on_response_mode_change(self):
        return self._win.on_response_mode_change

    @on_response_mode_change.setter
    def on_response_mode_change(self, cb):
        self._win.on_response_mode_change = cb

    @property
    def on_focus_mode_toggle(self):
        return self._win.on_focus_mode_toggle

    @on_focus_mode_toggle.setter
    def on_focus_mode_toggle(self, cb):
        self._win.on_focus_mode_toggle = cb

    @property
    def panel(self):
        return self._win.panel

    @panel.setter
    def panel(self, value):
        self._win.panel = value

    def set_dashboard_url(self, url: str):
        self._win.set_dashboard_url(url)

    def notify_phone_connected(self) -> None:
        self._win.notify_phone_connected()

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def show_content(self, title: str, text: str):
        self._win._content_sig.emit(title[:48], text[:4000])

    def prompt_reconfig(self):
        self._win._ready = False
        self._win._reconfig_sig.emit()

    def show_camera_frame(self, img_bytes: bytes):
        self._win._camera_sig.emit(img_bytes)

    def start_camera_stream(self) -> None:
        self._win.start_camera_stream()

    def stop_camera_stream(self) -> None:
        self._win.stop_camera_stream()

    def set_theme(self, accent_hex: str):
        self._win.set_theme(accent_hex)

    def update_assistant_info(self, name: str, subtitle: str):
        if threading.current_thread() is threading.main_thread():
            self._win.update_title_and_subtitle(name, subtitle)
        else:
            QMetaObject.invokeMethod(
                self._win,
                "update_title_and_subtitle",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, name),
                Q_ARG(str, subtitle)
            )

    def set_personality(self, personality: str, voice: str, theme_color: str):
        if threading.current_thread() is threading.main_thread():
            self._win.set_personality_info(personality, voice, theme_color)
        else:
            QMetaObject.invokeMethod(
                self._win,
                "set_personality_info",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, personality),
                Q_ARG(str, voice),
                Q_ARG(str, theme_color)
            )

    @property
    def assistant_name(self) -> str:
        return self._win._assistant_name

    @property
    def personality(self) -> str:
        return self._win._personality

    @property
    def voice(self) -> str:
        return self._win._voice

    @property
    def response_mode(self) -> str:
        return self._win._response_mode

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")

    def set_modo(self, mode: str):
        if mode == "local":
            self.write_log("🌐 Modo LOCAL activado")
        else:
            self.write_log("🌐 Modo NUBE activado")


# =====================================================================
# MAIN
# =====================================================================

if __name__ == "__main__":
    ui = JarvisUI("face.png")
    ui.root.mainloop()
