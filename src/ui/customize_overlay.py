# src/ui/customize_overlay.py
"""
Ventana de personalización del asistente (CustomizeOverlay).
Extraída de ui.py para mantener el código modular.
Incluye pestañas avanzadas: Motores, Memoria, Agente, Autenticación.
"""

import json
import os
import platform
import subprocess
import time
import math
import random
import sys
import ctypes
from pathlib import Path

from PyQt6.QtCore import (
    Qt, pyqtSignal, QTimer, Q_ARG, QMetaObject, QRectF, QPointF,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
)
from PyQt6.QtGui import (
    QColor, QFont, QIcon, QPixmap, QBrush, QPainter, QPen,
    QConicalGradient, QRadialGradient, QLinearGradient,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTabWidget, QGroupBox, QFileDialog, QMessageBox, QColorDialog,
    QSlider, QCheckBox, QComboBox, QScrollArea, QDialogButtonBox,
    QFrame, QSizePolicy, QApplication, QSpinBox, QTextEdit, QGridLayout,
)

# Manejo opcional de win32com (para crear accesos directos en Windows)
try:
    from win32com.client import Dispatch
    WIN32COM_AVAILABLE = True
except ImportError:
    WIN32COM_AVAILABLE = False
    Dispatch = None
    print("[CustomizeOverlay] pywin32 no disponible. No se podrán crear accesos directos.")

# ===== IMPORTACIONES CORREGIDAS =====
from src.config.settings import BASE_DIR, CONFIG_DIR, API_FILE, DEFAULT_THEME
from src.config.themes import THEME_MAP, VOICE_MAP, DEFAULT_VOICE
from src.config.personality import PERSONALITY_INFO, DEFAULT_PERSONALITY
from src.utils.i18n import tr, LanguageManager

from src.ui.ui_utils import (
    C,
    apply_ui_accent,
    current_palette,
    retheme_all_widgets,
    _read_full_config,
    _save_config,
    qcol,
)

# =====================================================================
# HUE WHEEL (selector de color circular)
# =====================================================================
class HueWheel(QWidget):
    hue_picked = pyqtSignal(str)
    hue_committed = pyqtSignal(str)

    _RING = 16

    def __init__(self, initial_hex: str = "#00d4ff", parent=None):
        super().__init__(parent)
        self.setFixedSize(148, 148)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hue = 0.53
        self._drag = False
        self.set_color(initial_hex)

    def color(self) -> str:
        return QColor.fromHsvF(self._hue, 1.0, 1.0).name()

    def set_color(self, hex_str: str):
        c = QColor((hex_str or "").strip())
        if c.isValid() and c.hsvHueF() >= 0:
            self._hue = c.hsvHueF()
            self.update()

    def _ring_rect(self) -> QRectF:
        m = self._RING / 2 + 3
        return QRectF(self.rect()).adjusted(m, m, -m, -m)

    def _hue_from_pos(self, pos: QPointF) -> float:
        c = QRectF(self.rect()).center()
        dx = pos.x() - c.x()
        dy = c.y() - pos.y()
        ang = math.atan2(dy, dx)
        return (ang / (2 * math.pi)) % 1.0

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self._ring_rect()
        center = rect.center()

        grad = QConicalGradient(center, 0)
        for i in range(0, 361, 20):
            grad.setColorAt(i / 360.0, QColor.fromHsvF((i % 360) / 360.0, 1.0, 1.0))
        p.setPen(QPen(QBrush(grad), self._RING))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)

        preview = QColor.fromHsvF(self._hue, 1.0, 1.0)
        inner = rect.adjusted(30, 30, -30, -30)
        p.setPen(QPen(qcol(C.BORDER_B), 1))
        p.setBrush(QBrush(preview))
        p.drawEllipse(inner)

        r = rect.width() / 2
        ang = self._hue * 2 * math.pi
        hx = center.x() + r * math.cos(ang)
        hy = center.y() - r * math.sin(ang)
        p.setPen(QPen(QColor("#00060a"), 2))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(QPointF(hx, hy), 7.5, 7.5)

    def mousePressEvent(self, e):
        self._drag = True
        self._hue = self._hue_from_pos(e.position())
        self.update()
        self.hue_picked.emit(self.color())

    def mouseMoveEvent(self, e):
        if self._drag:
            self._hue = self._hue_from_pos(e.position())
            self.update()
            self.hue_picked.emit(self.color())

    def mouseReleaseEvent(self, e):
        if self._drag:
            self._drag = False
            self.hue_committed.emit(self.color())

def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h)
    c.setAlpha(a)
    return c

# =====================================================================
# CUSTOMIZE OVERLAY (COMPLETO, CON REFRESCO DE COLORES Y SLIDER OPACIDAD)
# =====================================================================
class CustomizeOverlay(QWidget):
    saved = pyqtSignal(str, str, str, str, str)  # name, user, color, personality, voice
    language_changed = pyqtSignal(str)
    response_mode_changed = pyqtSignal(str)
    focus_mode_toggled = pyqtSignal(bool)

    _OW, _OH = 1150, 820   # Tamaño amplio, más ancho que alto

    def __init__(self, assistant_name="APOLO", user_name="Christopher",
                 config_dict=None, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self._config = config_dict or {}
        self._temp = self._config.copy()
        self._language = self._temp.get("ui_language", "es")
        self._defaults = _read_full_config()
        self._applying = False
        self._has_unsaved_changes = False

        # Cargar perfiles por personalidad
        self._profiles = self._config.get("personality_profiles", {})
        if not self._profiles:
            self._init_default_profiles()
        else:
            # Completar perfiles faltantes con paletas generadas
            for persona, info in PERSONALITY_INFO.items():
                if persona not in self._profiles:
                    color = THEME_MAP.get(persona, DEFAULT_THEME)
                    self._profiles[persona] = self._generate_palette(color, info["voice"])
                else:
                    # Asegurar que el perfil tenga todas las claves de color
                    base_color = self._profiles[persona].get("ui_color", THEME_MAP.get(persona, DEFAULT_THEME))
                    full_palette = self._generate_palette(base_color, self._profiles[persona].get("voice", info["voice"]))
                    for key, val in full_palette.items():
                        if key not in self._profiles[persona]:
                            self._profiles[persona][key] = val

        self._active_personality = self._temp.get("personality", DEFAULT_PERSONALITY)
        self._current_profile_personality = self._active_personality

        # Asegurar que los nuevos campos existan en _temp
        nuevos_defaults = {
            "ollama_model": "qwen2.5:3b",
            "ollama_url": "http://localhost:11434",
            "vosk_model_path": "models/vosk-model-es",
            "connection_mode": "auto",
            "openrouter_api_key": "",
            "groq_api_key": "",
            "gemini_api_key": "",
            "stt_engine": "Vosk (Offline)",
            "llm_engine": "Gemini (Cloud)",
            "tts_engine": "pyttsx3 (Local)",
            "auto_learn_enabled": True,
            "auto_learn_interval": 600,
            "planner_enabled": True,
            "gesture_control_enabled": False,
            "face_auth_enabled": False,
            "face_auth_confidence": 0.6,
            "face_image_path": "face.png",
            "window_opacity": 0.95,  # NUEVO
        }
        for key, val in nuevos_defaults.items():
            if key not in self._temp:
                self._temp[key] = self._config.get(key, val)

        # Existing keys
        for key in ["ui_font_size", "ui_icon_path", "shortcut_name", "shortcut_icon",
                    "font_size_header", "font_size_left", "font_size_right",
                    "font_size_center", "font_size_footer", "assistant_subtitle",
                    "badge1_text", "badge2_text", "badge3_text", "badge4_text", "badge5_text",
                    "badge1_color", "badge2_color", "badge3_color", "badge4_color", "badge5_color",
                    "wallpaper_path", "personality", "voice", "theme_name", "sync_system_theme",
                    "response_mode", "focus_mode", "vad_enabled", "rag_enabled"]:
            if key not in self._temp:
                self._temp[key] = self._config.get(key, self._get_default(key))

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            CustomizeOverlay {{
                background: rgba(0, 6, 10, 248);
                border: 1px solid {C.BORDER_B};
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        self._title_label = QLabel("⚙  " + tr("PERSONALIZACIÓN"))
        self._title_label.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self._title_label.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        layout.addWidget(self._title_label)

        self.tab_widget = QTabWidget()
        self.tab_widget.setUsesScrollButtons(True)
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                background: {C.PANEL};
                border: 1px solid {C.BORDER};
                border-radius: 6px;
                padding: 6px;
            }}
            QTabBar::tab {{
                background: {C.DARK};
                color: {C.TEXT_MED};
                padding: 6px 12px;
                font-size: 10px;
                font-weight: bold;
                border: 1px solid {C.BORDER};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                min-width: 50px;
            }}
            QTabBar::tab:selected {{
                background: {C.PANEL};
                color: {C.PRI};
                border-color: {C.PRI_DIM};
            }}
            QTabBar::tab:hover {{
                color: {C.TEXT};
            }}
        """)

        # Atributos de widgets
        self._name_input = None
        self._subtitle_input = None
        self._user_input = None
        self._icon_path_label = None
        self._sc_name_input = None
        self._sc_icon_label = None
        self._face_path_label = None
        self._color_buttons = {}
        self._color_widgets = {}
        self._font_sliders = {}
        self._badge_inputs = {}
        self._lang_combo = None
        self._wallpaper_preview = None
        self._personality_combo = None
        self._voice_combo = None
        self._active_voice_label = None
        self._sync_theme_check = None
        self._response_mode_combo = None
        self._focus_mode_check = None
        self._vad_check = None
        self._rag_check = None
        self._theme_combo = None
        self._test_text_input = None
        self._sel_color = None
        self.hue_wheel = None
        self._gemini_key_input = None
        self._openrouter_key_input = None
        self._groq_key_input = None
        self._ollama_model_input = None
        self._ollama_url_input = None
        self._vosk_path_input = None
        self._connection_mode_combo = None
        self._stt_combo = None
        self._llm_combo = None
        self._tts_combo = None
        self._memory_display = None
        self._auto_learn_check = None
        self._learn_interval_spin = None
        self._planner_check = None
        self._gesture_check = None
        self._face_auth_check = None
        self._face_confidence_slider = None
        self._face_confidence_label = None
        self._register_user_btn = None

        # ===== WIDGETS DE OPACIDAD =====
        self._opacity_slider = None
        self._opacity_value_label = None
        self._opacity_group = None

        # Pestañas
        self.tab_widget.addTab(self._build_general_tab(), tr("General"))
        self.tab_widget.addTab(self._build_personality_tab(), tr("Personalidad"))  # AQUÍ SE AÑADE EL SLIDER
        self.tab_widget.addTab(self._build_fonts_tab(), tr("Fuentes"))
        self.tab_widget.addTab(self._build_language_tab(), tr("Idioma"))
        self.tab_widget.addTab(self._build_badges_tab(), tr("Insignias"))
        self.tab_widget.addTab(self._build_wallpaper_tab(), tr("Fondo"))
        self.tab_widget.addTab(self._build_api_tab(), "🔑 API Keys")
        self.tab_widget.addTab(self._build_local_ai_tab(), "🤖 Modo Local")
        self.tab_widget.addTab(self._build_engines_tab(), "🔧 Motores")
        self.tab_widget.addTab(self._build_memory_tab(), "🧠 Memoria")
        self.tab_widget.addTab(self._build_agent_tab(), "🤖 Agente")
        self.tab_widget.addTab(self._build_auth_tab(), "🔐 Autenticación")
        self.tab_widget.addTab(self._build_advanced_tab(), tr("Avanzado"))

        layout.addWidget(self.tab_widget)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self._reset_btn = QPushButton("⟳  " + tr("Restaurar valores predeterminados"))
        self._reset_btn.setFixedHeight(38)
        self._reset_btn.setFont(QFont("Courier New", 9))
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.WARNING};
                border: 1px solid {C.WARNING}; border-radius: 6px;
            }}
            QPushButton:hover {{ background: rgba(255,136,0,0.1); border-color: {C.ACC}; }}
        """)
        self._reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(self._reset_btn)

        btn_row.addStretch()

        self._apply_btn = QPushButton("▸  " + tr("APLICAR"))
        self._apply_btn.setFixedHeight(38)
        self._apply_btn.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        self._apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 2px solid {C.PRI_DIM}; border-radius: 6px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
        """)
        self._apply_btn.clicked.connect(self._save)
        btn_row.addWidget(self._apply_btn)

        self._cancel_btn = QPushButton(tr("CANCELAR"))
        self._cancel_btn.setFixedHeight(38)
        self._cancel_btn.setFont(QFont("Courier New", 10))
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 6px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        self._cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(self._cancel_btn)

        layout.addLayout(btn_row)

        # Asegurar que todos los perfiles tengan todas las claves de color
        self._ensure_profile_completeness()

        # Inicializar colores y voz del perfil activo
        self._apply_current_profile()
        self._refresh_all_tabs()

        # Aplicar estilos con los colores actuales
        self._apply_styles()

    # ---------- Helpers de perfil y paleta ----------
    def _generate_palette(self, base_color: str, voice: str) -> dict:
        base = QColor(base_color)
        if not base.isValid():
            base = QColor("#00d4ff")

        def adjust(hex_color, factor):
            c = QColor(hex_color)
            h, s, v, a = c.getHsv()
            v = max(0, min(255, int(v * factor)))
            c.setHsv(h, s, v, a)
            return c.name()

        return {
            "voice": voice,
            "ui_color": base.name(),
            "ui_main_bg": adjust(base.name(), 0.35),
            "ui_log_bg": adjust(base.name(), 0.25),
            "ui_log_text": adjust(base.name(), 1.4),
            "ui_news_bg": adjust(base.name(), 0.4),
            "ui_news_text": adjust(base.name(), 1.6),
            "ui_input_bg": adjust(base.name(), 0.3),
            "ui_input_text": adjust(base.name(), 1.8),
            "ui_button_bg": adjust(base.name(), 0.6),
            "ui_button_text": adjust(base.name(), 1.5),
            "ui_title_color": adjust(base.name(), 1.4),
            "ui_status_color": "#00ff88",
            "ui_border_color": adjust(base.name(), 0.8),
        }

    def _init_default_profiles(self):
        self._profiles = {}
        for persona, info in PERSONALITY_INFO.items():
            color = THEME_MAP.get(persona, DEFAULT_THEME)
            self._profiles[persona] = self._generate_palette(color, info["voice"])

    def _ensure_profile_completeness(self):
        """Asegura que todos los perfiles tengan todas las claves de color y voz necesarias, con valores válidos."""
        required_color_keys = [
            "ui_color", "voice",
            "ui_main_bg", "ui_log_bg", "ui_log_text", "ui_news_bg", "ui_news_text",
            "ui_input_bg", "ui_input_text", "ui_button_bg", "ui_button_text",
            "ui_title_color", "ui_status_color", "ui_border_color",
        ]
        for persona, profile in self._profiles.items():
            # Asegurar ui_color y voice
            if "ui_color" not in profile or not QColor(profile.get("ui_color", "")).isValid():
                profile["ui_color"] = THEME_MAP.get(persona, DEFAULT_THEME)
            if "voice" not in profile or not profile.get("voice"):
                profile["voice"] = PERSONALITY_INFO.get(persona, {}).get("voice", "Charon")

            base_color = profile.get("ui_color", DEFAULT_THEME)
            for key in required_color_keys:
                # Si falta o es vacío o inválido, generar uno válido
                val = profile.get(key)
                if key == "ui_color" or key == "voice":
                    continue
                if not val or not QColor(val).isValid():
                    c = QColor(base_color)
                    h, s, v, a = c.getHsv()
                    factor = {
                        "ui_main_bg": 0.35, "ui_log_bg": 0.25, "ui_log_text": 1.4,
                        "ui_news_bg": 0.4, "ui_news_text": 1.6, "ui_input_bg": 0.3,
                        "ui_input_text": 1.8, "ui_button_bg": 0.6, "ui_button_text": 1.5,
                        "ui_title_color": 1.4, "ui_status_color": 1.0, "ui_border_color": 0.8
                    }.get(key, 1.0)
                    v = max(0, min(255, int(v * factor)))
                    c.setHsv(h, s, v, a)
                    profile[key] = c.name()
            # status_color debe ser siempre verde o similar
            if not profile.get("ui_status_color") or not QColor(profile.get("ui_status_color", "")).isValid():
                profile["ui_status_color"] = "#00ff88"

    def _get_default(self, key):
        defaults = {
            "ui_font_size": 10,
            "ui_icon_path": "face.png",
            "shortcut_name": "APOLO AI",
            "shortcut_icon": "",
            "font_size_header": 10,
            "font_size_left": 10,
            "font_size_right": 10,
            "font_size_center": 10,
            "font_size_footer": 10,
            "assistant_subtitle": "Autonomous Platform for Orchestration, Learning and Operations",
            "badge1_text": "AI CORE ACTIVE",
            "badge2_text": "SEC CLEARED",
            "badge3_text": "PROTOCOL XLIX",
            "badge4_text": "READY",
            "badge5_text": "ONLINE",
            "badge1_color": "#00ff88",
            "badge2_color": "#00d4ff",
            "badge3_color": "#5ab8cc",
            "badge4_color": "#ffcc00",
            "badge5_color": "#ff6b00",
            "wallpaper_path": "",
            "personality": DEFAULT_PERSONALITY,
            "voice": "Charon",
            "theme_name": "dark",
            "sync_system_theme": False,
            "response_mode": "voice_text",
            "focus_mode": False,
            "vad_enabled": False,
            "rag_enabled": False,
            "ollama_model": "qwen2.5:3b",
            "ollama_url": "http://localhost:11434",
            "vosk_model_path": "models/vosk-model-es",
            "connection_mode": "auto",
            "openrouter_api_key": "",
            "groq_api_key": "",
            "gemini_api_key": "",
            "stt_engine": "Vosk (Offline)",
            "llm_engine": "Gemini (Cloud)",
            "tts_engine": "pyttsx3 (Local)",
            "auto_learn_enabled": True,
            "auto_learn_interval": 600,
            "planner_enabled": True,
            "gesture_control_enabled": False,
            "face_auth_enabled": False,
            "face_auth_confidence": 0.6,
            "face_image_path": "face.png",
            "window_opacity": 0.95,
        }
        return defaults.get(key)

    def _reset_defaults(self):
        reply = self._show_message(
            QMessageBox.Icon.Question,
            tr("Restaurar"),
            tr("¿Estás seguro de que quieres restaurar todos los valores predeterminados?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._temp = self._defaults.copy()
            self._init_default_profiles()
            self._current_profile_personality = DEFAULT_PERSONALITY
            self._active_personality = DEFAULT_PERSONALITY
            self._apply_current_profile()
            self._refresh_all_tabs()
            if self.main_window:
                self.main_window._apply_full_config(self._temp)

    # =================================================================
    # REFRESH DE TODOS LOS CONTROLES (EXCEPTO COLORES Y VOZ)
    # =================================================================
    def _refresh_all_tabs(self):
        """Actualiza todos los controles que NO son de color/voz."""
        # General
        if self._name_input is not None:
            self._name_input.setText(self._temp.get("assistant_name", "APOLO"))
        if self._subtitle_input is not None:
            self._subtitle_input.setText(self._temp.get("assistant_subtitle", ""))
        if self._user_input is not None:
            self._user_input.setText(self._temp.get("user_name", "Christopher"))
        if self._icon_path_label is not None:
            self._icon_path_label.setText(self._temp.get("ui_icon_path", "face.png"))
        if self._sc_name_input is not None:
            self._sc_name_input.setText(self._temp.get("shortcut_name", "APOLO AI"))
        if self._sc_icon_label is not None:
            self._sc_icon_label.setText(self._temp.get("shortcut_icon", "(default)"))
        if self._face_path_label is not None:
            self._face_path_label.setText(self._temp.get("face_image_path", "face.png"))

        # Fuentes
        for key, (slider, label) in self._font_sliders.items():
            val = self._temp.get(key, 10)
            slider.blockSignals(True)
            slider.setValue(val)
            slider.blockSignals(False)
            label.setText(f"{val}px")

        # Idioma
        if self._lang_combo is not None:
            lang = self._temp.get("ui_language", "es")
            idx = self._lang_combo.findData(lang)
            if idx >= 0:
                self._lang_combo.setCurrentIndex(idx)

        # Badges
        for i in range(1, 6):
            if i not in self._badge_inputs:
                continue
            text_key = f"badge{i}_text"
            color_key = f"badge{i}_color"
            text_val = self._temp.get(text_key, f"BADGE {i}")
            color_val = self._temp.get(color_key, "#00d4ff")
            self._badge_inputs[i]["text"].setText(text_val)
            self._badge_inputs[i]["color"].setText(color_val)
            self._badge_inputs[i]["pick_btn"].setStyleSheet(
                f"background: {color_val}; border: 1px solid {C.BORDER}; border-radius: 4px;"
            )

        # Wallpaper
        if self._wallpaper_preview is not None:
            wp = self._temp.get("wallpaper_path", "")
            if wp and Path(wp).exists():
                self._update_wallpaper_preview(wp)
            else:
                self._wallpaper_preview.setText(tr("No wallpaper selected"))

        # Sync theme
        if self._sync_theme_check is not None:
            self._sync_theme_check.setChecked(self._temp.get("sync_system_theme", False))

        # Respuesta, focus, vad, rag
        if self._response_mode_combo is not None:
            modes = ["voice_text", "voice_only", "text_only"]
            current_mode = self._temp.get("response_mode", "voice_text")
            if current_mode in modes:
                idx = modes.index(current_mode)
                self._response_mode_combo.setCurrentIndex(idx)

        if self._focus_mode_check is not None:
            self._focus_mode_check.setChecked(self._temp.get("focus_mode", False))
        if self._vad_check is not None:
            self._vad_check.setChecked(self._temp.get("vad_enabled", False))
        if self._rag_check is not None:
            self._rag_check.setChecked(self._temp.get("rag_enabled", False))

        # API keys y otros
        if self._gemini_key_input is not None:
            self._gemini_key_input.setText(self._temp.get("gemini_api_key", ""))
        if self._openrouter_key_input is not None:
            self._openrouter_key_input.setText(self._temp.get("openrouter_api_key", ""))
        if self._groq_key_input is not None:
            self._groq_key_input.setText(self._temp.get("groq_api_key", ""))
        if self._ollama_model_input is not None:
            self._ollama_model_input.setText(self._temp.get("ollama_model", "qwen2.5:3b"))
        if self._ollama_url_input is not None:
            self._ollama_url_input.setText(self._temp.get("ollama_url", "http://localhost:11434"))
        if self._vosk_path_input is not None:
            self._vosk_path_input.setText(self._temp.get("vosk_model_path", "models/vosk-model-es"))
        if self._connection_mode_combo is not None:
            modes = ["auto", "cloud", "local"]
            current = self._temp.get("connection_mode", "auto")
            idx = modes.index(current) if current in modes else 0
            self._connection_mode_combo.setCurrentIndex(idx)

        # Motores
        if self._stt_combo is not None:
            idx = self._stt_combo.findText(self._temp.get("stt_engine", "Vosk (Offline)"))
            if idx >= 0:
                self._stt_combo.setCurrentIndex(idx)
        if self._llm_combo is not None:
            idx = self._llm_combo.findText(self._temp.get("llm_engine", "Gemini (Cloud)"))
            if idx >= 0:
                self._llm_combo.setCurrentIndex(idx)
        if self._tts_combo is not None:
            idx = self._tts_combo.findText(self._temp.get("tts_engine", "pyttsx3 (Local)"))
            if idx >= 0:
                self._tts_combo.setCurrentIndex(idx)

        # Agente
        if self._auto_learn_check is not None:
            self._auto_learn_check.setChecked(self._temp.get("auto_learn_enabled", True))
        if self._learn_interval_spin is not None:
            self._learn_interval_spin.setValue(self._temp.get("auto_learn_interval", 600))
        if self._planner_check is not None:
            self._planner_check.setChecked(self._temp.get("planner_enabled", True))
        if self._gesture_check is not None:
            self._gesture_check.setChecked(self._temp.get("gesture_control_enabled", False))

        # Autenticación
        if self._face_auth_check is not None:
            self._face_auth_check.setChecked(self._temp.get("face_auth_enabled", False))
        if self._face_confidence_slider is not None:
            conf = self._temp.get("face_auth_confidence", 0.6)
            self._face_confidence_slider.setValue(int(conf * 100))
            if self._face_confidence_label is not None:
                self._face_confidence_label.setText(f"{conf:.2f}")

        # Opacidad
        if self._opacity_slider is not None:
            opacity = self._temp.get("window_opacity", 0.95)
            self._opacity_slider.blockSignals(True)
            self._opacity_slider.setValue(int(opacity * 100))
            self._opacity_slider.blockSignals(False)
            if self._opacity_value_label is not None:
                self._opacity_value_label.setText(f"{int(opacity * 100)}%")

        self._refresh_memory_display()
        self._apply_styles()
        self._update_tab_texts()
        self._has_unsaved_changes = False

    # =================================================================
    # APLICAR PERFIL ACTUAL (COLORES Y VOZ)
    # =================================================================
    def _apply_current_profile(self):
        """Aplica el perfil de la personalidad actual a los widgets de color y voz."""
        profile = self._profiles.get(self._current_profile_personality, {})

        # Voz
        if self._voice_combo is not None:
            voice = profile.get("voice", "Charon")
            idx = self._voice_combo.findText(voice)
            if idx >= 0:
                self._voice_combo.blockSignals(True)
                self._voice_combo.setCurrentIndex(idx)
                self._voice_combo.blockSignals(False)
            if self._active_voice_label is not None:
                self._active_voice_label.setText(tr("Voz activa") + f": {voice}")

        # Rueda de color
        ui_color = profile.get("ui_color", THEME_MAP.get(self._current_profile_personality, DEFAULT_THEME))
        if self.hue_wheel is not None:
            self.hue_wheel.set_color(ui_color)
        self._sel_color = ui_color

        # Botones de color y campos hex usando el nuevo _color_widgets
        for key, (btn, hex_input) in self._color_widgets.items():
            color = profile.get(key, "#00d4ff")
            if btn is not None:
                btn.setStyleSheet(f"background-color: {color}; border: 1px solid {C.BORDER}; border-radius: 6px;")
                btn.setAutoFillBackground(True)
                btn.update()
            if hex_input is not None:
                hex_input.blockSignals(True)
                hex_input.setText(color)
                hex_input.blockSignals(False)

        # Actualizar el estilo de los títulos de las pestañas
        self._apply_styles()

    # =================================================================
    # APLICAR ESTILOS DINÁMICOS (COLORES DE PERSONALIDAD)
    # =================================================================
    def _apply_styles(self):
        """Aplica los colores actuales (C.PRI, C.PANEL, etc.) a todos los elementos del overlay."""
        ui_color = C.PRI
        border_color = C.BORDER
        panel_bg = C.PANEL
        text_color = C.TEXT
        text_med = C.TEXT_MED
        dark_bg = C.DARK

        # Estilo del overlay
        self.setStyleSheet(f"""
            CustomizeOverlay {{
                background: rgba(0, 6, 10, 248);
                border: 1px solid {C.BORDER_B};
                border-radius: 10px;
            }}
        """)

        # Estilo del tab widget
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                background: {panel_bg};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 6px;
            }}
            QTabBar::tab {{
                background: {dark_bg};
                color: {text_med};
                padding: 6px 12px;
                font-size: 10px;
                font-weight: bold;
                border: 1px solid {border_color};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                min-width: 50px;
            }}
            QTabBar::tab:selected {{
                background: {panel_bg};
                color: {ui_color};
                border-color: {ui_color};
            }}
            QTabBar::tab:hover {{
                color: {text_color};
            }}
        """)

        # Botones generales
        for btn in self.findChildren(QPushButton):
            text = btn.text()
            if "APLICAR" in text or "APPLY" in text:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent; color: {ui_color};
                        border: 2px solid {C.PRI_DIM}; border-radius: 6px;
                    }}
                    QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {ui_color}; }}
                """)
            elif "CANCELAR" in text or "CANCEL" in text:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent; color: {text_med};
                        border: 1px solid {border_color}; border-radius: 6px;
                    }}
                    QPushButton:hover {{ color: {text_color}; border-color: {C.BORDER_B}; }}
                """)
            elif "⟳" in text or "Restaurar" in text:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent; color: {C.WARNING};
                        border: 1px solid {C.WARNING}; border-radius: 6px;
                    }}
                    QPushButton:hover {{ background: rgba(255,136,0,0.1); border-color: {C.ACC}; }}
                """)

        # Título
        self._title_label.setStyleSheet(f"color: {ui_color}; background: transparent;")

        # Grupos de pestañas (QGroupBox) dentro de cada tab
        for tab_index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(tab_index)
            if tab:
                for group in tab.findChildren(QGroupBox):
                    group.setStyleSheet(f"""
                        QGroupBox {{
                            color: {ui_color};
                            border: 1px solid {border_color};
                            border-radius: 6px;
                            margin-top: 8px;
                            padding-top: 6px;
                        }}
                        QGroupBox::title {{
                            subcontrol-origin: margin;
                            left: 8px;
                            padding: 0 6px 0 6px;
                            background-color: {panel_bg};
                            color: {ui_color};
                        }}
                    """)

    # =================================================================
    # MANEJADORES DE PERSONALIDAD Y VOZ
    # =================================================================
    def _on_personality_changed(self, index):
        self._save_current_profile_from_widgets()
        new_personality = self._personality_combo.currentText().lower()
        self._current_profile_personality = new_personality
        self._apply_current_profile()
        if self._current_profile_personality == self._active_personality:
            profile = self._profiles.get(self._current_profile_personality, {})
            self._temp["personality"] = self._current_profile_personality
            self._temp["voice"] = profile.get("voice", "Charon")
            self._temp["ui_color"] = profile.get("ui_color", THEME_MAP.get(self._current_profile_personality, DEFAULT_THEME))
            for key in ["ui_main_bg", "ui_log_bg", "ui_log_text", "ui_news_bg", "ui_news_text",
                        "ui_input_bg", "ui_input_text", "ui_button_bg", "ui_button_text",
                        "ui_title_color", "ui_status_color", "ui_border_color"]:
                self._temp[key] = profile.get(key, self._temp.get(key, "#00d4ff"))
            # Aplicar colores a la ventana principal
            if self.main_window:
                self.main_window._apply_ui_colors(self._temp)
                self.main_window.set_personality_info(
                    self._current_profile_personality,
                    self._temp["voice"],
                    self._temp["ui_color"]
                )
                if hasattr(self.main_window, 'on_personality_change'):
                    self.main_window.on_personality_change(
                        self._current_profile_personality,
                        self._temp["voice"]
                    )
            self._apply_styles()  # Refrescar colores del overlay
        self._mark_unsaved()

    def _on_voice_changed(self, index):
        voice = self._voice_combo.currentText()
        profile = self._profiles.setdefault(self._current_profile_personality, {})
        profile["voice"] = voice
        self._active_voice_label.setText(tr("Voz activa") + f": {voice}")
        self._mark_unsaved()
        if self._current_profile_personality == self._active_personality:
            self._temp["voice"] = voice
            _save_config(self._temp)
            if self.main_window:
                self.main_window.set_personality_info(
                    self._current_profile_personality,
                    voice,
                    self._profiles[self._current_profile_personality].get("ui_color", DEFAULT_THEME)
                )
                if hasattr(self.main_window, 'on_personality_change'):
                    self.main_window.on_personality_change(self._current_profile_personality, voice)

    def _save_current_profile_from_widgets(self):
        profile = self._profiles.setdefault(self._current_profile_personality, {})
        if self._voice_combo is not None:
            profile["voice"] = self._voice_combo.currentText()
        if self.hue_wheel is not None:
            profile["ui_color"] = self._sel_color if self._sel_color else self.hue_wheel.color()
        # Usar _color_widgets para leer los valores de los campos hex
        for key, (btn, hex_input) in self._color_widgets.items():
            if hex_input is not None:
                color_text = hex_input.text().strip()
                if QColor(color_text).isValid():
                    profile[key] = color_text
        for color_key in ["ui_main_bg", "ui_log_bg", "ui_log_text", "ui_news_bg", "ui_news_text",
                          "ui_input_bg", "ui_input_text", "ui_button_bg", "ui_button_text",
                          "ui_title_color", "ui_status_color", "ui_border_color"]:
            if color_key not in profile:
                profile[color_key] = self._temp.get(color_key, "#00d4ff")

    # =================================================================
    # MANEJADORES DE CAMBIOS DE COLOR
    # =================================================================
    def _preview_color_from_hue(self, hex_color: str):
        if self._applying:
            return
        self._sel_color = hex_color
        profile = self._profiles.setdefault(self._current_profile_personality, {})
        profile["ui_color"] = hex_color
        self._mark_unsaved()
        if self._current_profile_personality == self._active_personality:
            self._temp["ui_color"] = hex_color
            if self.main_window and not self._applying:
                self._applying = True
                QTimer.singleShot(0, lambda: self.main_window._apply_ui_colors(self._temp))
                QTimer.singleShot(100, lambda: setattr(self, '_applying', False))
            _save_config(self._temp)

    def _pick_color(self, key, button):
        if self._applying:
            return
        current = self._profiles.get(self._current_profile_personality, {}).get(key, '#00d4ff')
        color = QColorDialog.getColor(QColor(current))
        if color.isValid():
            hex_color = color.name()
            profile = self._profiles.setdefault(self._current_profile_personality, {})
            profile[key] = hex_color
            button.setStyleSheet(f"background-color: {hex_color}; border: 1px solid {C.BORDER}; border-radius: 6px;")
            hex_input = self._color_widgets.get(key, (None, None))[1]
            if hex_input is not None:
                hex_input.blockSignals(True)
                hex_input.setText(hex_color)
                hex_input.blockSignals(False)
            self._mark_unsaved()
            if self._current_profile_personality == self._active_personality:
                self._temp[key] = hex_color
                _save_config(self._temp)
                if self.main_window:
                    if key == "ui_color":
                        if not self._applying:
                            self._applying = True
                            QTimer.singleShot(0, lambda: self.main_window._apply_ui_colors(self._temp))
                            QTimer.singleShot(100, lambda: setattr(self, '_applying', False))
                    else:
                        self.main_window._apply_ui_colors(self._temp)

    def _on_hex_changed(self, key, text):
        if self._applying:
            return
        text = text.strip().lower()
        if text.startswith("#") and len(text) == 7:
            try:
                int(text[1:], 16)
                profile = self._profiles.setdefault(self._current_profile_personality, {})
                profile[key] = text
                self._mark_unsaved()
                btn = self._color_widgets.get(key, (None, None))[0]
                if btn is not None:
                    btn.setStyleSheet(f"background-color: {text}; border: 1px solid {C.BORDER}; border-radius: 6px;")
                if self._current_profile_personality == self._active_personality:
                    self._temp[key] = text
                    _save_config(self._temp)
                    if self.main_window:
                        if key == "ui_color":
                            if not self._applying:
                                self._applying = True
                                QTimer.singleShot(0, lambda: self.main_window._apply_ui_colors(self._temp))
                                QTimer.singleShot(100, lambda: setattr(self, '_applying', False))
                        else:
                            self.main_window._apply_ui_colors(self._temp)
            except ValueError:
                pass

    # =================================================================
    # MÉTODOS AUXILIARES Y CONSTRUCCIÓN DE PESTAÑAS
    # =================================================================
    def _show_message(self, icon, title, text, buttons=QMessageBox.StandardButton.Ok):
        """Muestra un QMessageBox con estilo legible sobre fondo oscuro."""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon)
        msg.setStandardButtons(buttons)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #000d14;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #002233;
                color: #e0e0e0;
                border: 1px solid #00d4ff;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #003344;
            }
        """)
        return msg.exec()

    def _mark_unsaved(self):
        self._has_unsaved_changes = True

    # ===== MÉTODO PARA TRADUCCIÓN GENÉRICA =====
    def _set_i18n_property(self, widget, key):
        widget.setProperty("i18n_key", key)

    def _retranslate_ui(self):
        """Actualiza todos los textos estáticos del overlay según el idioma actual."""
        self._title_label.setText("⚙  " + tr("PERSONALIZACIÓN"))
        self._update_tab_texts()

        # Actualizar todos los QLabel, QPushButton, QGroupBox que tengan i18n_key
        for widget in self.findChildren((QLabel, QPushButton, QGroupBox)):
            key = widget.property("i18n_key")
            if key:
                if isinstance(widget, QGroupBox):
                    widget.setTitle(tr(key))
                elif isinstance(widget, QLabel):
                    widget.setText(tr(key))
                elif isinstance(widget, QPushButton):
                    widget.setText(tr(key))

        # Actualizar etiqueta de voz activa
        if self._voice_combo is not None and self._active_voice_label is not None:
            self._active_voice_label.setText(tr("Voz activa") + f": {self._voice_combo.currentText()}")

    # ===== PESTAÑA GENERAL =====
    def _build_general_tab(self):
        tab = QWidget()
        tab.setStyleSheet("background: #000d14;")
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 8, 10, 8)

        self._general_name_label = QLabel(tr("NOMBRE DEL ASISTENTE"))
        self._set_i18n_property(self._general_name_label, "NOMBRE DEL ASISTENTE")
        self._general_name_label.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        self._general_name_label.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(self._general_name_label)
        self._name_input = QLineEdit(self._temp.get("assistant_name", "APOLO"))
        self._name_input.setFont(QFont("Courier New", 11))
        self._name_input.setFixedHeight(36)
        self._name_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 4px; padding: 6px 10px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        self._name_input.textChanged.connect(self._mark_unsaved)
        layout.addWidget(self._name_input)

        self._general_subtitle_label = QLabel(tr("SUBTÍTULO"))
        self._set_i18n_property(self._general_subtitle_label, "SUBTÍTULO")
        self._general_subtitle_label.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        self._general_subtitle_label.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(self._general_subtitle_label)
        self._subtitle_input = QLineEdit(self._temp.get("assistant_subtitle", ""))
        self._subtitle_input.setFont(QFont("Courier New", 10))
        self._subtitle_input.setFixedHeight(36)
        self._subtitle_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 4px; padding: 6px 10px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        self._subtitle_input.textChanged.connect(self._mark_unsaved)
        layout.addWidget(self._subtitle_input)

        # Sincronizar tema
        sync_row = QHBoxLayout()
        self._general_sync_label = QLabel(tr("Sincronizar tema con el sistema"))
        self._set_i18n_property(self._general_sync_label, "Sincronizar tema con el sistema")
        self._general_sync_label.setFont(QFont("Courier New", 9))
        self._general_sync_label.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._sync_theme_check = QCheckBox()
        self._sync_theme_check.setChecked(self._temp.get("sync_system_theme", False))
        self._sync_theme_check.setStyleSheet("background: transparent;")
        self._sync_theme_check.toggled.connect(self._mark_unsaved)
        sync_row.addWidget(self._general_sync_label)
        sync_row.addWidget(self._sync_theme_check)
        sync_row.addStretch()
        layout.addLayout(sync_row)

        self._general_user_label = QLabel(tr("TU NOMBRE"))
        self._set_i18n_property(self._general_user_label, "TU NOMBRE")
        self._general_user_label.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        self._general_user_label.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(self._general_user_label)
        self._user_input = QLineEdit(self._temp.get("user_name", "Christopher"))
        self._user_input.setPlaceholderText("Ej. Christopher")
        self._user_input.setFont(QFont("Courier New", 11))
        self._user_input.setFixedHeight(36)
        self._user_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 4px; padding: 6px 10px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        self._user_input.textChanged.connect(self._mark_unsaved)
        layout.addWidget(self._user_input)

        # Icono del sistema
        icon_group = QGroupBox(tr("ICONO DEL SISTEMA"))
        self._set_i18n_property(icon_group, "ICONO DEL SISTEMA")
        icon_group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 8px; padding: 6px;")
        icon_layout = QHBoxLayout(icon_group)
        self._icon_path_label = QLabel(self._temp.get("ui_icon_path", "face.png"))
        self._icon_path_label.setStyleSheet(f"color: {C.TEXT}; font-size: 10px;")
        icon_layout.addWidget(self._icon_path_label)
        icon_layout.addStretch()
        icon_browse_btn = QPushButton(tr("Examinar…"))
        self._set_i18n_property(icon_browse_btn, "Examinar…")
        icon_browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        icon_browse_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 4px;
                padding: 4px 12px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; }}
        """)
        icon_browse_btn.clicked.connect(self._browse_icon)
        icon_layout.addWidget(icon_browse_btn)
        refresh_icon_btn = QPushButton("⟳")
        refresh_icon_btn.setFixedSize(28,28)
        refresh_icon_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_icon_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 4px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; }}
        """)
        refresh_icon_btn.clicked.connect(self._refresh_icon)
        icon_layout.addWidget(refresh_icon_btn)
        layout.addWidget(icon_group)

        # Cara del sistema
        face_group = QGroupBox(tr("CARA DEL SISTEMA (face.png)"))
        self._set_i18n_property(face_group, "CARA DEL SISTEMA (face.png)")
        face_group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 8px; padding: 6px;")
        face_layout = QHBoxLayout(face_group)
        self._face_path_label = QLabel(self._temp.get("face_image_path", "face.png"))
        self._face_path_label.setStyleSheet(f"color: {C.TEXT}; font-size: 10px;")
        face_layout.addWidget(self._face_path_label)
        face_layout.addStretch()
        face_browse_btn = QPushButton(tr("Examinar…"))
        self._set_i18n_property(face_browse_btn, "Examinar…")
        face_browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        face_browse_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 4px;
                padding: 4px 12px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; }}
        """)
        face_browse_btn.clicked.connect(self._browse_face)
        face_layout.addWidget(face_browse_btn)
        layout.addWidget(face_group)

        # Acceso directo
        shortcut_group = QGroupBox(tr("ACCESO DIRECTO EN ESCRITORIO"))
        self._set_i18n_property(shortcut_group, "ACCESO DIRECTO EN ESCRITORIO")
        shortcut_group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 8px; padding: 6px;")
        sc_layout = QVBoxLayout(shortcut_group)
        name_row = QHBoxLayout()
        name_label = QLabel(tr("Nombre:"))
        self._set_i18n_property(name_label, "Nombre:")
        name_row.addWidget(name_label)
        self._sc_name_input = QLineEdit(self._temp.get("shortcut_name", "APOLO AI"))
        self._sc_name_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px;
            }}
        """)
        self._sc_name_input.setFixedHeight(28)
        self._sc_name_input.textChanged.connect(self._mark_unsaved)
        name_row.addWidget(self._sc_name_input)
        sc_layout.addLayout(name_row)

        icon_row = QHBoxLayout()
        icon_label = QLabel(tr("Icono:"))
        self._set_i18n_property(icon_label, "Icono:")
        icon_row.addWidget(icon_label)
        self._sc_icon_label = QLabel(self._temp.get("shortcut_icon", "(default)"))
        self._sc_icon_label.setStyleSheet(f"color: {C.TEXT_MED};")
        icon_row.addWidget(self._sc_icon_label)
        icon_row.addStretch()
        sc_icon_browse = QPushButton(tr("Examinar…"))
        self._set_i18n_property(sc_icon_browse, "Examinar…")
        sc_icon_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        sc_icon_browse.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 4px;
                padding: 4px 12px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; }}
        """)
        sc_icon_browse.clicked.connect(self._browse_shortcut_icon)
        icon_row.addWidget(sc_icon_browse)
        sc_layout.addLayout(icon_row)

        create_shortcut_btn = QPushButton(tr("Crear acceso directo"))
        self._set_i18n_property(create_shortcut_btn, "Crear acceso directo")
        create_shortcut_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        create_shortcut_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {C.GREEN};
                border: 1px solid {C.GREEN_D}; border-radius: 4px;
                padding: 4px 12px;
            }}
            QPushButton:hover {{ background: #001a0d; }}
        """)
        create_shortcut_btn.clicked.connect(self._create_shortcut)
        sc_layout.addWidget(create_shortcut_btn)
        layout.addWidget(shortcut_group)

        layout.addStretch()
        return tab

    # ===== MÉTODOS DE NAVEGACIÓN =====
    def _browse_icon(self):
        try:
            path, _ = QFileDialog.getOpenFileName(
                self, tr("Seleccionar icono"), str(Path.home()),
                "Images (*.png *.jpg *.jpeg *.ico *.bmp *.gif)"
            )
            if path:
                self._temp["ui_icon_path"] = path
                if self._icon_path_label is not None:
                    self._icon_path_label.setText(path)
                self._mark_unsaved()
                _save_config(self._temp)
                if self.main_window:
                    self.main_window.update_icon(path)
        except Exception as e:
            print(f"[UI] Error browsing icon: {e}")

    def _browse_face(self):
        try:
            path, _ = QFileDialog.getOpenFileName(
                self, tr("Seleccionar imagen para la cara"), str(Path.home()),
                "Images (*.png *.jpg *.jpeg *.ico *.bmp *.gif)"
            )
            if path:
                self._temp["face_image_path"] = path
                if self._face_path_label is not None:
                    self._face_path_label.setText(path)
                self._mark_unsaved()
                _save_config(self._temp)
                if self.main_window and hasattr(self.main_window, 'update_face_image'):
                    self.main_window.update_face_image(path)
        except Exception as e:
            print(f"[UI] Error browsing face image: {e}")

    def _refresh_icon(self):
        if self.main_window and hasattr(self.main_window, 'update_icon'):
            path = self._temp.get("ui_icon_path", "face.png")
            self.main_window.update_icon(path)

    def _browse_shortcut_icon(self):
        try:
            path, _ = QFileDialog.getOpenFileName(
                self, tr("Seleccionar icono para acceso directo"), str(Path.home()),
                "Icons (*.ico *.png *.jpg *.jpeg *.bmp *.gif)"
            )
            if path:
                self._temp["shortcut_icon"] = path
                if self._sc_icon_label is not None:
                    self._sc_icon_label.setText(path)
                self._mark_unsaved()
                _save_config(self._temp)
        except Exception as e:
            print(f"[UI] Error browsing shortcut icon: {e}")

    def _create_shortcut(self):
        if not WIN32COM_AVAILABLE or Dispatch is None:
            self._show_message(QMessageBox.Icon.Warning, tr("Error"), "pywin32 no está instalado.")
            return
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            shortcut_name = self._sc_name_input.text().strip() or "APOLO AI"
            shortcut_path = os.path.join(desktop, f"{shortcut_name}.lnk")
            target = sys.executable
            icon_path = self._temp.get("shortcut_icon", "")
            if not icon_path:
                icon_path = os.path.join(BASE_DIR, "face.png")

            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = target
            shortcut.WorkingDirectory = os.path.dirname(target)
            shortcut.IconLocation = icon_path
            shortcut.save()
            self._show_message(QMessageBox.Icon.Information, tr("Acceso directo"), f"Acceso directo creado en:\n{shortcut_path}")
        except Exception as e:
            self._show_message(QMessageBox.Icon.Warning, tr("Error"), f"No se pudo crear el acceso directo: {e}")

    # ===== PESTAÑA PERSONALIDAD (fusionada con Apariencia) =====
    def _build_personality_tab(self):
        tab = QWidget()
        tab.setStyleSheet("background: #000d14;")
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 8, 10, 8)

        self._personality_title_label = QLabel(tr("PERSONALIDAD Y APARIENCIA"))
        self._set_i18n_property(self._personality_title_label, "PERSONALIDAD Y APARIENCIA")
        self._personality_title_label.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        self._personality_title_label.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(self._personality_title_label)

        # Personalidad
        self._personality_group_label = QGroupBox(tr("PERSONALIDAD"))
        self._set_i18n_property(self._personality_group_label, "PERSONALIDAD")
        self._personality_group_label.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        person_layout = QHBoxLayout(self._personality_group_label)
        self._personality_combo = QComboBox()
        self._personality_combo.addItems(["Jarvis", "Agata", "Tony", "Friday", "Apolo"])
        idx = self._personality_combo.findText(self._current_profile_personality.capitalize())
        if idx >= 0:
            self._personality_combo.setCurrentIndex(idx)
        self._personality_combo.setStyleSheet(f"""
            QComboBox {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 4px;
                padding: 6px 10px;
                font-size: 11px;
            }}
            QComboBox:hover {{ border-color: {C.PRI_DIM}; }}
        """)
        self._personality_combo.currentIndexChanged.connect(self._on_personality_changed)
        person_layout.addWidget(self._personality_combo)
        person_layout.addStretch()
        layout.addWidget(self._personality_group_label)

        # Voz
        self._voice_group_label = QGroupBox(tr("Voz"))
        self._set_i18n_property(self._voice_group_label, "Voz")
        self._voice_group_label.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        voice_layout = QVBoxLayout(self._voice_group_label)
        self._voice_combo = QComboBox()
        voices = ["Charon", "Puck", "Fenrir", "Kore", "Orus", "Leda", "Zephyr"]
        self._voice_combo.addItems(voices)
        current_voice = self._profiles.get(self._current_profile_personality, {}).get("voice", "Charon")
        idx = self._voice_combo.findText(current_voice)
        if idx >= 0:
            self._voice_combo.setCurrentIndex(idx)
        self._voice_combo.setStyleSheet(f"""
            QComboBox {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 4px;
                padding: 6px 10px;
                font-size: 11px;
            }}
            QComboBox:hover {{ border-color: {C.PRI_DIM}; }}
        """)
        self._voice_combo.currentIndexChanged.connect(self._on_voice_changed)
        self._active_voice_label = QLabel(tr("Voz activa") + f": {self._voice_combo.currentText()}")
        self._active_voice_label.setStyleSheet(f"color: {C.PRI}; font-size: 10px;")
        voice_layout.addWidget(self._active_voice_label)
        combo_layout = QHBoxLayout()
        combo_layout.addWidget(self._voice_combo)
        combo_layout.addStretch()
        voice_layout.addLayout(combo_layout)
        layout.addWidget(self._voice_group_label)

        # Colores
        self._colors_title_label = QLabel(tr("PERSONALIZACIÓN DE COLORES"))
        self._set_i18n_property(self._colors_title_label, "PERSONALIZACIÓN DE COLORES")
        self._colors_title_label.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        self._colors_title_label.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(self._colors_title_label)

        self.hue_wheel = HueWheel(self._profiles.get(self._current_profile_personality, {}).get("ui_color", "#00d4ff"))
        self.hue_wheel.hue_picked.connect(self._preview_color_from_hue)
        layout.addWidget(self.hue_wheel, alignment=Qt.AlignmentFlag.AlignCenter)

        color_grid = QGridLayout()
        color_grid.setSpacing(8)
        self._color_buttons = {}
        self._color_widgets = {}
        color_items = [
            ("ui_main_bg", tr("Fondo Principal")),
            ("ui_log_bg", tr("Fondo Log")),
            ("ui_log_text", tr("Texto Log")),
            ("ui_news_bg", tr("Fondo Noticias")),
            ("ui_news_text", tr("Texto Noticias")),
            ("ui_input_bg", tr("Fondo Input")),
            ("ui_input_text", tr("Texto Input")),
            ("ui_button_bg", tr("Fondo Botones")),
            ("ui_button_text", tr("Texto Botones")),
            ("ui_title_color", tr("Título")),
            ("ui_status_color", tr("Estado")),
            ("ui_border_color", tr("Bordes")),
        ]

        row, col = 0, 0
        for key, label_text in color_items:
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(0,0,0,0)
            item_layout.setSpacing(6)

            lbl_w = QLabel(label_text)
            self._set_i18n_property(lbl_w, label_text)
            lbl_w.setFont(QFont("Courier New", 9))
            lbl_w.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
            lbl_w.setFixedWidth(100)
            item_layout.addWidget(lbl_w)

            btn = QPushButton()
            btn.setFixedSize(28, 28)
            color = self._profiles.get(self._current_profile_personality, {}).get(key, '#00d4ff')
            btn.setStyleSheet(f"background-color: {color}; border: 1px solid {C.BORDER}; border-radius: 4px;")
            btn.clicked.connect(lambda _, k=key, b=btn: self._pick_color(k, b))
            self._color_buttons[key] = btn
            item_layout.addWidget(btn)

            hex_input = QLineEdit(color)
            hex_input.setFont(QFont("Courier New", 8))
            hex_input.setFixedWidth(65)
            hex_input.setStyleSheet(f"background: #000d12; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 2px 4px;")
            hex_input.textChanged.connect(lambda t, k=key: self._on_hex_changed(k, t))
            self._color_buttons[key + "_hex"] = hex_input
            item_layout.addWidget(hex_input)

            # Guardar referencia directa en _color_widgets
            self._color_widgets[key] = (btn, hex_input)

            item_layout.addStretch()
            color_grid.addWidget(item_widget, row, col)
            col += 1
            if col >= 2:
                col = 0
                row += 1

        layout.addLayout(color_grid)

        # ===== SLIDER DE OPACIDAD (NUEVO) =====
        self._opacity_group = QGroupBox("OPACIDAD DE LA VENTANA")
        self._opacity_group.setStyleSheet(f"""
            QGroupBox {{
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER};
                border-radius: 6px;
                margin-top: 8px;
                padding: 6px;
            }}
            QGroupBox::title {{
                color: {C.TEXT_MED};
            }}
        """)
        opacity_layout = QHBoxLayout(self._opacity_group)
        opacity_layout.setContentsMargins(6, 2, 6, 6)

        # Etiqueta
        opacity_label = QLabel("Opacidad:")
        opacity_label.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        opacity_layout.addWidget(opacity_label)

        # Slider
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(50, 100)
        current_opacity = self._temp.get("window_opacity", 0.95)
        self._opacity_slider.setValue(int(current_opacity * 100))
        self._opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._opacity_slider.setTickInterval(10)
        self._opacity_slider.setFixedWidth(180)
        self._opacity_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background: {C.BORDER};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {C.PRI};
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
        """)
        # Conectar el evento de liberación para evitar spam en el log
        self._opacity_slider.sliderReleased.connect(self._on_opacity_released)
        self._opacity_slider.valueChanged.connect(self._on_opacity_preview)
        opacity_layout.addWidget(self._opacity_slider)

        # Etiqueta del valor porcentual
        self._opacity_value_label = QLabel(f"{self._opacity_slider.value()}%")
        self._opacity_value_label.setStyleSheet(f"color: {C.PRI}; font-weight: bold; font-size: 12px; background: transparent;")
        opacity_layout.addWidget(self._opacity_value_label)
        opacity_layout.addStretch()

        layout.addWidget(self._opacity_group)

        layout.addStretch()
        return tab

    # ===== MÉTODOS DE OPACIDAD =====
    def _on_opacity_preview(self, value: int):
        """Actualiza la vista previa de la opacidad (sin guardar en log)."""
        self._opacity_value_label.setText(f"{value}%")
        # Aplicar temporalmente la opacidad a la ventana principal
        if self.main_window:
            self.main_window.setWindowOpacity(value / 100.0)

    def _on_opacity_released(self):
        """Cuando se suelta el slider, guarda el valor y escribe en el log una sola vez."""
        value = self._opacity_slider.value()
        opacity = value / 100.0
        self._temp["window_opacity"] = opacity
        _save_config(self._temp)
        if self.main_window:
            # Asegurar que la opacidad quede fijada
            self.main_window.setWindowOpacity(opacity)
            # Escribir en el log solo una vez al soltar el slider
            self.main_window.write_log(f"SYS: Opacidad ajustada a {value}%")

    # ===== PESTAÑA FUENTES =====
    def _build_fonts_tab(self):
        tab = QWidget()
        tab.setStyleSheet("background: #000d14;")
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 8, 10, 8)

        lbl = QLabel(tr("TAMAÑOS DE FUENTE POR ZONA"))
        self._set_i18n_property(lbl, "TAMAÑOS DE FUENTE POR ZONA")
        lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(lbl)

        self._font_sliders = {}
        font_sections = [
            ("font_size_header", tr("Barra Superior")),
            ("font_size_left", tr("Panel Izquierdo")),
            ("font_size_right", tr("Panel Derecho")),
            ("font_size_center", tr("Contenido Central")),
            ("font_size_footer", tr("Barra Inferior")),
        ]
        for key, label_text in font_sections:
            group = QGroupBox(label_text)
            self._set_i18n_property(group, label_text)
            group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 6px; padding: 6px;")
            hbox = QHBoxLayout(group)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(8, 20)
            slider.setValue(int(self._temp.get(key, 10)))
            slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            slider.setTickInterval(1)
            slider.setFixedWidth(120)
            value_label = QLabel(f"{slider.value()}px")
            value_label.setStyleSheet(f"color: {C.PRI}; font-size: 11px; font-weight: bold;")
            slider.valueChanged.connect(lambda v, lbl=value_label: lbl.setText(f"{v}px"))
            slider.valueChanged.connect(lambda v, k=key: self._on_font_changed(k, v))
            hbox.addWidget(slider)
            hbox.addWidget(value_label)
            hbox.addStretch()
            layout.addWidget(group)
            self._font_sliders[key] = (slider, value_label)

        layout.addStretch()
        return tab

    def _on_font_changed(self, key: str, value: int):
        self._temp[key] = value
        self._mark_unsaved()
        _save_config(self._temp)
        if self.main_window:
            font_cfg = {}
            for k in ["font_size_header", "font_size_left", "font_size_right",
                      "font_size_center", "font_size_footer"]:
                font_cfg[k] = self._temp.get(k, 10)
            QTimer.singleShot(0, lambda: self.main_window._apply_font_sizes(font_cfg))

    # ===== PESTAÑA IDIOMA =====
    def _build_language_tab(self):
        tab = QWidget()
        tab.setStyleSheet("background: #000d14;")
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(10, 8, 10, 8)

        lbl = QLabel(tr("IDIOMA DE LA INTERFAZ"))
        self._set_i18n_property(lbl, "IDIOMA DE LA INTERFAZ")
        lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(lbl)

        self._lang_combo = QComboBox()
        self._lang_combo.addItem("Español", "es")
        self._lang_combo.addItem("English", "en")
        self._lang_combo.addItem(tr("Francés"), "fr")
        self._lang_combo.addItem(tr("Alemán"), "de")
        self._lang_combo.addItem(tr("Italiano"), "it")
        self._lang_combo.addItem(tr("Portugués"), "pt")
        self._lang_combo.addItem("Русский", "ru")
        current_lang = self._temp.get("ui_language", "es")
        idx = self._lang_combo.findData(current_lang)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)
        self._lang_combo.setStyleSheet(f"""
            QComboBox {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 4px;
                padding: 6px 10px;
                font-size: 11px;
            }}
            QComboBox:hover {{ border-color: {C.PRI_DIM}; }}
        """)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        layout.addWidget(self._lang_combo)

        info = QLabel(tr("El cambio de idioma afecta a toda la interfaz.\nLos prompts del asistente se actualizarán en la siguiente conversación."))
        self._set_i18n_property(info, "El cambio de idioma afecta a toda la interfaz.\nLos prompts del asistente se actualizarán en la siguiente conversación.")
        info.setFont(QFont("Courier New", 9))
        info.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()
        return tab

    def _on_language_changed(self, index):
        if self._lang_combo is None:
            return
        lang_code = self._lang_combo.itemData(index)
        self._temp["ui_language"] = lang_code
        self._mark_unsaved()
        _save_config(self._temp)
        LanguageManager.set_language(lang_code)
        self.language_changed.emit(lang_code)
        if self.main_window:
            self.main_window._update_ui_texts()
        self._retranslate_ui()

    def _update_tab_texts(self):
        self.tab_widget.setTabText(0, tr("General"))
        self.tab_widget.setTabText(1, tr("Personalidad"))
        self.tab_widget.setTabText(2, tr("Fuentes"))
        self.tab_widget.setTabText(3, tr("Idioma"))
        self.tab_widget.setTabText(4, tr("Insignias"))
        self.tab_widget.setTabText(5, tr("Fondo"))
        self.tab_widget.setTabText(6, "🔑 API Keys")
        self.tab_widget.setTabText(7, "🤖 Modo Local")
        self.tab_widget.setTabText(8, "🔧 Motores")
        self.tab_widget.setTabText(9, "🧠 Memoria")
        self.tab_widget.setTabText(10, "🤖 Agente")
        self.tab_widget.setTabText(11, "🔐 Autenticación")
        self.tab_widget.setTabText(12, tr("Avanzado"))

    # ===== PESTAÑA BADGES =====
    def _build_badges_tab(self):
        tab = QWidget()
        tab.setStyleSheet("background: #000d14;")
        layout = QVBoxLayout(tab)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 8, 10, 8)

        lbl = QLabel(tr("PANEL DE ESTADO (IZQUIERDO)"))
        self._set_i18n_property(lbl, "PANEL DE ESTADO (IZQUIERDO)")
        lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(lbl)

        self._badge_inputs = {}
        for i in range(1, 6):
            g = QGroupBox(tr(f"Badge {i}"))
            self._set_i18n_property(g, f"Badge {i}")
            g.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 4px;")
            g_layout = QVBoxLayout(g)

            row_t = QHBoxLayout()
            lbl_text = QLabel(tr("Texto:"))
            self._set_i18n_property(lbl_text, "Texto:")
            row_t.addWidget(lbl_text)
            text_input = QLineEdit(self._temp.get(f"badge{i}_text", f"BADGE {i}"))
            text_input.setStyleSheet(f"""
                QLineEdit {{
                    background: #000d12; color: {C.TEXT};
                    border: 1px solid {C.BORDER}; border-radius: 4px;
                    padding: 2px 6px;
                }}
            """)
            text_input.textChanged.connect(self._mark_unsaved)
            row_t.addWidget(text_input)
            g_layout.addLayout(row_t)

            row_c = QHBoxLayout()
            lbl_color = QLabel(tr("Color:"))
            self._set_i18n_property(lbl_color, "Color:")
            row_c.addWidget(lbl_color)
            color_input = QLineEdit(self._temp.get(f"badge{i}_color", "#00d4ff"))
            color_input.setStyleSheet(f"""
                QLineEdit {{
                    background: #000d12; color: {C.TEXT};
                    border: 1px solid {C.BORDER}; border-radius: 4px;
                    padding: 2px 6px;
                }}
            """)
            color_input.textChanged.connect(self._mark_unsaved)
            row_c.addWidget(color_input)
            pick_btn = QPushButton("🎨")
            pick_btn.setFixedSize(28, 28)
            pick_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            pick_btn.setStyleSheet(f"background: {color_input.text()}; border: 1px solid {C.BORDER}; border-radius: 4px;")
            pick_btn.clicked.connect(lambda _, k=f"badge{i}_color", inp=color_input, btn=pick_btn: self._pick_badge_color(k, inp, btn))
            row_c.addWidget(pick_btn)
            g_layout.addLayout(row_c)

            apply_btn = QPushButton(tr("Aplicar badge"))
            self._set_i18n_property(apply_btn, "Aplicar badge")
            apply_btn.setFixedHeight(24)
            apply_btn.setFont(QFont("Courier New", 7))
            apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            apply_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.PANEL2}; color: {C.PRI};
                    border: 1px solid {C.PRI_DIM}; border-radius: 3px;
                    padding: 2px 6px;
                }}
                QPushButton:hover {{ background: {C.PRI_GHO}; }}
            """)
            apply_btn.clicked.connect(lambda _, idx=i: self._apply_badge(idx))
            g_layout.addWidget(apply_btn)

            self._badge_inputs[i] = {"text": text_input, "color": color_input, "pick_btn": pick_btn}
            layout.addWidget(g)

        layout.addStretch()
        return tab

    def _pick_badge_color(self, key, input_widget, button):
        current = input_widget.text().strip()
        if not current.startswith("#"):
            current = "#00d4ff"
        color = QColorDialog.getColor(QColor(current))
        if color.isValid():
            hex_color = color.name()
            input_widget.setText(hex_color)
            button.setStyleSheet(f"background: {hex_color}; border: 1px solid {C.BORDER}; border-radius: 4px;")
            self._temp[key] = hex_color
            self._mark_unsaved()
            _save_config(self._temp)

    def _apply_badge(self, index: int):
        if index not in self._badge_inputs:
            return
        text = self._badge_inputs[index]["text"].text().strip() or f"BADGE {index}"
        color = self._badge_inputs[index]["color"].text().strip() or "#00d4ff"
        self._temp[f"badge{index}_text"] = text
        self._temp[f"badge{index}_color"] = color
        _save_config(self._temp)
        if self.main_window:
            self.main_window._update_badges()
        self._mark_unsaved()

    # ===== PESTAÑA WALLPAPER =====
    def _build_wallpaper_tab(self):
        tab = QWidget()
        tab.setStyleSheet("background: #000d14;")
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 8, 10, 8)

        lbl = QLabel(tr("SELECCIONAR WALLPAPER"))
        self._set_i18n_property(lbl, "SELECCIONAR WALLPAPER")
        lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(lbl)

        self._wallpaper_preview = QLabel()
        self._wallpaper_preview.setFixedHeight(160)
        self._wallpaper_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._wallpaper_preview.setStyleSheet(f"""
            background: {C.PANEL2};
            border: 1px solid {C.BORDER};
            border-radius: 6px;
            color: {C.TEXT_DIM};
        """)
        wallpaper_path = self._temp.get("wallpaper_path", "")
        if wallpaper_path and Path(wallpaper_path).exists():
            self._update_wallpaper_preview(wallpaper_path)
        else:
            self._wallpaper_preview.setText(tr("No wallpaper selected"))
        layout.addWidget(self._wallpaper_preview)

        btn_row = QHBoxLayout()
        browse_btn = QPushButton("🖼  " + tr("Cambiar wallpaper"))
        self._set_i18n_property(browse_btn, "Cambiar wallpaper")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 4px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; }}
        """)
        browse_btn.clicked.connect(self._browse_wallpaper)
        btn_row.addWidget(browse_btn)

        reset_btn = QPushButton("⟳  " + tr("Restaurar predeterminado"))
        self._set_i18n_property(reset_btn, "Restaurar predeterminado")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 4px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        reset_btn.clicked.connect(self._reset_wallpaper)
        btn_row.addWidget(reset_btn)

        apply_wp_btn = QPushButton(tr("Aplicar wallpaper"))
        self._set_i18n_property(apply_wp_btn, "Aplicar wallpaper")
        apply_wp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_wp_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {C.GREEN};
                border: 1px solid {C.GREEN_D}; border-radius: 4px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{ background: #001a0d; }}
        """)
        apply_wp_btn.clicked.connect(self._apply_wallpaper_now)
        btn_row.addWidget(apply_wp_btn)

        layout.addLayout(btn_row)
        layout.addStretch()
        return tab

    def _update_wallpaper_preview(self, path: str):
        try:
            px = QPixmap(path)
            if not px.isNull():
                scaled = px.scaled(300, 160, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
                self._wallpaper_preview.setPixmap(scaled)
                self._wallpaper_preview.setText("")
            else:
                self._wallpaper_preview.setText(tr("Cannot preview"))
        except Exception:
            self._wallpaper_preview.setText(tr("Cannot preview"))

    def _browse_wallpaper(self):
        try:
            path, _ = QFileDialog.getOpenFileName(
                self, tr("Select wallpaper image"), str(Path.home()),
                "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.tiff)"
            )
            if path:
                self._temp["wallpaper_path"] = path
                self._mark_unsaved()
                _save_config(self._temp)
                self._update_wallpaper_preview(path)
                if self.main_window:
                    self.main_window._apply_wallpaper(path)
                    self._set_windows_wallpaper(path)
        except Exception as e:
            self._show_message(QMessageBox.Icon.Warning, "Error", f"No se pudo seleccionar la imagen: {e}")

    def _reset_wallpaper(self):
        self._temp["wallpaper_path"] = ""
        self._mark_unsaved()
        _save_config(self._temp)
        if self._wallpaper_preview is not None:
            self._wallpaper_preview.setPixmap(QPixmap())
            self._wallpaper_preview.setText(tr("No wallpaper selected"))
        if self.main_window and hasattr(self.main_window, '_apply_wallpaper'):
            self.main_window._apply_wallpaper("")
        if platform.system() == "Windows":
            try:
                ctypes.windll.user32.SystemParametersInfoW(20, 0, "", 3)
            except Exception:
                pass

    def _apply_wallpaper_now(self):
        if self.main_window:
            path = self._temp.get("wallpaper_path", "")
            if path and Path(path).exists():
                self.main_window._apply_wallpaper(path)
                self.main_window._log.append_log(f"SYS: Wallpaper aplicado: {Path(path).name}")
                self._show_message(QMessageBox.Icon.Information, tr("Wallpaper"), f"Wallpaper aplicado: {Path(path).name}")
                self._set_windows_wallpaper(path)
                _save_config(self._temp)
            else:
                self._show_message(QMessageBox.Icon.Warning, tr("Wallpaper"), "No se ha seleccionado ninguna imagen válida.")

    def _set_windows_wallpaper(self, path):
        if platform.system() == "Windows" and path and Path(path).exists():
            try:
                ctypes.windll.user32.SystemParametersInfoW(20, 0, str(path), 3)
            except Exception as e:
                print(f"[Wallpaper] No se pudo establecer fondo de Windows: {e}")

    # ===== PESTAÑA API KEYS =====
    def _build_api_tab(self):
        tab = QWidget()
        tab.setStyleSheet("background: #000d14;")
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 8, 10, 8)

        lbl = QLabel("🔑 " + tr("CONFIGURACIÓN DE API KEYS"))
        self._set_i18n_property(lbl, "CONFIGURACIÓN DE API KEYS")
        lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(lbl)

        gb = QGroupBox("Gemini")
        gb.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        g_layout = QVBoxLayout(gb)
        self._gemini_key_input = QLineEdit()
        self._gemini_key_input.setPlaceholderText("AIza... o AQ...")
        self._gemini_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._gemini_key_input.setStyleSheet(f"""
            QLineEdit {{ background: #000d12; color: {C.TEXT};
            border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px; }}
        """)
        self._gemini_key_input.textChanged.connect(self._mark_unsaved)
        g_layout.addWidget(self._gemini_key_input)
        layout.addWidget(gb)

        gb2 = QGroupBox("OpenRouter")
        gb2.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        g_layout2 = QVBoxLayout(gb2)
        self._openrouter_key_input = QLineEdit()
        self._openrouter_key_input.setPlaceholderText("sk-or-v1-...")
        self._openrouter_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._openrouter_key_input.setStyleSheet(f"""
            QLineEdit {{ background: #000d12; color: {C.TEXT};
            border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px; }}
        """)
        self._openrouter_key_input.textChanged.connect(self._mark_unsaved)
        g_layout2.addWidget(self._openrouter_key_input)
        layout.addWidget(gb2)

        gb3 = QGroupBox("Groq")
        gb3.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        g_layout3 = QVBoxLayout(gb3)
        self._groq_key_input = QLineEdit()
        self._groq_key_input.setPlaceholderText("gsk_...")
        self._groq_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._groq_key_input.setStyleSheet(f"""
            QLineEdit {{ background: #000d12; color: {C.TEXT};
            border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px; }}
        """)
        self._groq_key_input.textChanged.connect(self._mark_unsaved)
        g_layout3.addWidget(self._groq_key_input)
        layout.addWidget(gb3)

        layout.addStretch()
        return tab

    # ===== PESTAÑA MODO LOCAL =====
    def _build_local_ai_tab(self):
        tab = QWidget()
        tab.setStyleSheet("background: #000d14;")
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 8, 10, 8)

        lbl = QLabel("🤖 " + tr("CONFIGURACIÓN DE IA LOCAL"))
        self._set_i18n_property(lbl, "CONFIGURACIÓN DE IA LOCAL")
        lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(lbl)

        gb = QGroupBox("Ollama")
        gb.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        g_layout = QVBoxLayout(gb)
        lbl_model = QLabel("Modelo:")
        lbl_model.setStyleSheet(f"color: {C.TEXT_MED};")
        g_layout.addWidget(lbl_model)
        self._ollama_model_input = QLineEdit()
        self._ollama_model_input.setPlaceholderText("qwen2.5:3b, deepseek-r1:1.5b, etc.")
        self._ollama_model_input.setStyleSheet(f"""
            QLineEdit {{ background: #000d12; color: {C.TEXT};
            border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px; }}
        """)
        self._ollama_model_input.textChanged.connect(self._mark_unsaved)
        g_layout.addWidget(self._ollama_model_input)
        lbl_url = QLabel("URL de la API:")
        lbl_url.setStyleSheet(f"color: {C.TEXT_MED};")
        g_layout.addWidget(lbl_url)
        self._ollama_url_input = QLineEdit()
        self._ollama_url_input.setPlaceholderText("http://localhost:11434")
        self._ollama_url_input.setStyleSheet(f"""
            QLineEdit {{ background: #000d12; color: {C.TEXT};
            border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px; }}
        """)
        self._ollama_url_input.textChanged.connect(self._mark_unsaved)
        g_layout.addWidget(self._ollama_url_input)
        layout.addWidget(gb)

        gb2 = QGroupBox("Vosk (STT)")
        gb2.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        g_layout2 = QVBoxLayout(gb2)
        lbl_vosk = QLabel("Ruta del modelo:")
        lbl_vosk.setStyleSheet(f"color: {C.TEXT_MED};")
        g_layout2.addWidget(lbl_vosk)
        self._vosk_path_input = QLineEdit()
        self._vosk_path_input.setPlaceholderText("models/vosk-model-es")
        self._vosk_path_input.setStyleSheet(f"""
            QLineEdit {{ background: #000d12; color: {C.TEXT};
            border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px; }}
        """)
        self._vosk_path_input.textChanged.connect(self._mark_unsaved)
        g_layout2.addWidget(self._vosk_path_input)
        layout.addWidget(gb2)

        gb3 = QGroupBox("Modo de conexión")
        gb3.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        g_layout3 = QVBoxLayout(gb3)
        self._connection_mode_combo = QComboBox()
        self._connection_mode_combo.addItems(["Automático (auto)", "Solo Nube (cloud)", "Solo Local (local)"])
        self._connection_mode_combo.setStyleSheet(f"""
            QComboBox {{ background: #000d12; color: {C.TEXT};
            border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px; }}
        """)
        self._connection_mode_combo.currentIndexChanged.connect(self._mark_unsaved)
        g_layout3.addWidget(self._connection_mode_combo)
        info = QLabel("Automático: usa nube si hay internet, local si no.\nSolo Nube: fuerza Gemini.\nSolo Local: fuerza Ollama.")
        info.setFont(QFont("Courier New", 8))
        info.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        info.setWordWrap(True)
        g_layout3.addWidget(info)
        layout.addWidget(gb3)

        layout.addStretch()
        return tab

    # ===== PESTAÑA MOTORES =====
    def _build_engines_tab(self):
        tab = QWidget()
        tab.setStyleSheet("background: #000d14;")
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 8, 10, 8)

        lbl = QLabel("🔧 " + tr("CONFIGURACIÓN DE MOTORES"))
        self._set_i18n_property(lbl, "CONFIGURACIÓN DE MOTORES")
        lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(lbl)

        stt_group = QGroupBox("STT (Speech-to-Text)")
        stt_group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        stt_layout = QVBoxLayout(stt_group)
        self._stt_combo = QComboBox()
        self._stt_combo.addItems(["Vosk (Offline)", "Whisper (Local)", "Google Cloud", "Azure"])
        self._stt_combo.setStyleSheet(f"background: #000d12; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px;")
        self._stt_combo.currentIndexChanged.connect(self._mark_unsaved)
        stt_layout.addWidget(self._stt_combo)
        stt_info = QLabel("El motor STT convierte voz a texto. Reinicia el asistente para aplicar cambios.")
        stt_info.setFont(QFont("Courier New", 7))
        stt_info.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        stt_info.setWordWrap(True)
        stt_layout.addWidget(stt_info)
        layout.addWidget(stt_group)

        llm_group = QGroupBox("LLM (Language Model)")
        llm_group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        llm_layout = QVBoxLayout(llm_group)
        self._llm_combo = QComboBox()
        self._llm_combo.addItems(["Gemini (Cloud)", "Ollama (Local)", "OpenRouter", "Groq"])
        self._llm_combo.setStyleSheet(f"background: #000d12; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px;")
        self._llm_combo.currentIndexChanged.connect(self._mark_unsaved)
        llm_layout.addWidget(self._llm_combo)
        llm_info = QLabel("El motor LLM genera respuestas. Reinicia el asistente para aplicar cambios.")
        llm_info.setFont(QFont("Courier New", 7))
        llm_info.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        llm_info.setWordWrap(True)
        llm_layout.addWidget(llm_info)
        layout.addWidget(llm_group)

        tts_group = QGroupBox("TTS (Text-to-Speech)")
        tts_group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        tts_layout = QVBoxLayout(tts_group)
        self._tts_combo = QComboBox()
        self._tts_combo.addItems(["pyttsx3 (Local)", "EdgeTTS", "ElevenLabs", "Kokoro"])
        self._tts_combo.setStyleSheet(f"background: #000d12; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px;")
        self._tts_combo.currentIndexChanged.connect(self._mark_unsaved)
        tts_layout.addWidget(self._tts_combo)
        tts_info = QLabel("El motor TTS convierte texto a voz. Reinicia el asistente para aplicar cambios.")
        tts_info.setFont(QFont("Courier New", 7))
        tts_info.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        tts_info.setWordWrap(True)
        tts_layout.addWidget(tts_info)
        layout.addWidget(tts_group)

        layout.addStretch()
        return tab

    # ===== PESTAÑA MEMORIA =====
    def _build_memory_tab(self):
        tab = QWidget()
        tab.setStyleSheet("background: #000d14;")
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 8, 10, 8)

        lbl = QLabel("🧠 " + tr("GESTIÓN DE MEMORIA"))
        self._set_i18n_property(lbl, "GESTIÓN DE MEMORIA")
        lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(lbl)

        memory_group = QGroupBox("Memoria almacenada")
        memory_group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        memory_layout = QVBoxLayout(memory_group)
        self._memory_display = QTextEdit()
        self._memory_display.setReadOnly(True)
        self._memory_display.setFont(QFont("Courier New", 9))
        self._memory_display.setStyleSheet(f"background: #000d12; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px;")
        self._memory_display.setMaximumHeight(200)
        memory_layout.addWidget(self._memory_display)
        layout.addWidget(memory_group)

        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 Refrescar")
        refresh_btn.setStyleSheet(f"background: {C.PANEL2}; color: {C.PRI}; border: 1px solid {C.PRI_DIM}; border-radius: 4px; padding: 4px 12px;")
        refresh_btn.clicked.connect(self._refresh_memory_display)
        btn_layout.addWidget(refresh_btn)
        clear_btn = QPushButton("🗑️ Limpiar memoria")
        clear_btn.setStyleSheet(f"background: {C.PANEL2}; color: {C.RED}; border: 1px solid {C.RED}; border-radius: 4px; padding: 4px 12px;")
        clear_btn.clicked.connect(self._clear_memory)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addStretch()
        return tab

    def _refresh_memory_display(self):
        try:
            from src.memory.memory_manager import load_memory
            memory = load_memory()
            if self._memory_display is not None:
                self._memory_display.setText(json.dumps(memory, indent=2, ensure_ascii=False))
        except Exception as e:
            if self._memory_display is not None:
                self._memory_display.setText(f"Error al cargar memoria: {e}")

    def _clear_memory(self):
        reply = self._show_message(
            QMessageBox.Icon.Question,
            "Limpiar memoria",
            "¿Estás seguro de que quieres eliminar toda la memoria?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from src.memory.memory_manager import save_memory, _empty_memory
                save_memory(_empty_memory())
                self._refresh_memory_display()
                self._show_message(QMessageBox.Icon.Information, "Memoria", "Memoria limpiada correctamente.")
            except Exception as e:
                self._show_message(QMessageBox.Icon.Warning, "Error", f"No se pudo limpiar la memoria: {e}")

    # ===== PESTAÑA AGENTE =====
    def _build_agent_tab(self):
        tab = QWidget()
        tab.setStyleSheet("background: #000d14;")
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 8, 10, 8)

        lbl = QLabel("🤖 " + tr("CONFIGURACIÓN DEL AGENTE"))
        self._set_i18n_property(lbl, "CONFIGURACIÓN DEL AGENTE")
        lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(lbl)

        learn_group = QGroupBox("Autoaprendizaje")
        learn_group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        learn_layout = QVBoxLayout(learn_group)
        self._auto_learn_check = QCheckBox("Activar autoaprendizaje")
        self._auto_learn_check.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        self._auto_learn_check.setChecked(self._temp.get("auto_learn_enabled", True))
        self._auto_learn_check.toggled.connect(self._mark_unsaved)
        learn_layout.addWidget(self._auto_learn_check)

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Intervalo (segundos):"))
        self._learn_interval_spin = QSpinBox()
        self._learn_interval_spin.setRange(60, 3600)
        self._learn_interval_spin.setValue(self._temp.get("auto_learn_interval", 600))
        self._learn_interval_spin.setStyleSheet(f"background: #000d12; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px;")
        self._learn_interval_spin.valueChanged.connect(self._mark_unsaved)
        interval_layout.addWidget(self._learn_interval_spin)
        interval_layout.addStretch()
        learn_layout.addLayout(interval_layout)
        layout.addWidget(learn_group)

        planner_group = QGroupBox("Planificador de tareas")
        planner_group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        planner_layout = QVBoxLayout(planner_group)
        self._planner_check = QCheckBox("Activar planificador de tareas")
        self._planner_check.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        self._planner_check.setChecked(self._temp.get("planner_enabled", True))
        self._planner_check.toggled.connect(self._mark_unsaved)
        planner_layout.addWidget(self._planner_check)
        layout.addWidget(planner_group)

        gesture_group = QGroupBox("Control por gestos (Minority Report)")
        gesture_group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        gesture_layout = QVBoxLayout(gesture_group)
        self._gesture_check = QCheckBox("Activar control por gestos")
        self._gesture_check.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        self._gesture_check.setChecked(self._temp.get("gesture_control_enabled", False))
        self._gesture_check.toggled.connect(self._mark_unsaved)
        gesture_layout.addWidget(self._gesture_check)
        gesture_info = QLabel("Permite controlar el asistente con gestos de la mano usando la cámara.")
        gesture_info.setFont(QFont("Courier New", 7))
        gesture_info.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        gesture_info.setWordWrap(True)
        gesture_layout.addWidget(gesture_info)
        layout.addWidget(gesture_group)

        layout.addStretch()
        return tab

    # ===== PESTAÑA AUTENTICACIÓN =====
    def _build_auth_tab(self):
        tab = QWidget()
        tab.setStyleSheet("background: #000d14;")
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 8, 10, 8)

        lbl = QLabel("🔐 " + tr("CONFIGURACIÓN DE AUTENTICACIÓN"))
        self._set_i18n_property(lbl, "CONFIGURACIÓN DE AUTENTICACIÓN")
        lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(lbl)

        face_group = QGroupBox("Autenticación facial")
        face_group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        face_layout = QVBoxLayout(face_group)
        self._face_auth_check = QCheckBox("Activar autenticación facial")
        self._face_auth_check.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        self._face_auth_check.setChecked(self._temp.get("face_auth_enabled", False))
        self._face_auth_check.toggled.connect(self._mark_unsaved)
        face_layout.addWidget(self._face_auth_check)

        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("Confianza:"))
        self._face_confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self._face_confidence_slider.setRange(10, 99)
        self._face_confidence_slider.setValue(int(self._temp.get("face_auth_confidence", 0.6) * 100))
        self._face_confidence_slider.setStyleSheet("background: #000d12;")
        self._face_confidence_slider.valueChanged.connect(self._on_face_confidence_changed)
        conf_layout.addWidget(self._face_confidence_slider)
        self._face_confidence_label = QLabel(f"{self._face_confidence_slider.value()/100:.2f}")
        self._face_confidence_label.setStyleSheet(f"color: {C.PRI};")
        conf_layout.addWidget(self._face_confidence_label)
        face_layout.addLayout(conf_layout)

        self._register_user_btn = QPushButton("📸 Registrar usuario (captura facial)")
        self._register_user_btn.setStyleSheet(f"background: {C.PANEL2}; color: {C.PRI}; border: 1px solid {C.PRI_DIM}; border-radius: 4px; padding: 6px 12px;")
        self._register_user_btn.clicked.connect(self._register_face)
        face_layout.addWidget(self._register_user_btn)

        face_info = QLabel("La autenticación facial usa detección básica. Puedes registrar una imagen de tu rostro.")
        face_info.setFont(QFont("Courier New", 7))
        face_info.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        face_info.setWordWrap(True)
        face_layout.addWidget(face_info)
        layout.addWidget(face_group)

        layout.addStretch()
        return tab

    def _on_face_confidence_changed(self, value):
        if self._face_confidence_label is not None:
            self._face_confidence_label.setText(f"{value/100:.2f}")
        self._temp["face_auth_confidence"] = value / 100.0
        self._mark_unsaved()
        _save_config(self._temp)

    def _register_face(self):
        """Captura una imagen y la guarda en ~/.apolo_faces sin depender de librerías externas."""
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self._show_message(QMessageBox.Icon.Warning, "Error", "No se pudo abrir la cámara.")
                return
            ret, frame = cap.read()
            cap.release()
            if not ret:
                self._show_message(QMessageBox.Icon.Warning, "Error", "No se pudo capturar la imagen.")
                return

            user_id = self._user_input.text().strip() if self._user_input is not None else "default_user"
            faces_dir = Path.home() / '.apolo_faces'
            faces_dir.mkdir(exist_ok=True)
            img_path = faces_dir / f"{user_id}.jpg"
            cv2.imwrite(str(img_path), frame)

            self._temp["face_user_id"] = user_id
            self._temp["face_auth_enabled"] = True
            self._temp["face_image_path"] = str(img_path)
            self._mark_unsaved()
            _save_config(self._temp)

            self._show_message(QMessageBox.Icon.Information, "Registro", f"Usuario '{user_id}' registrado correctamente.")
        except ImportError:
            self._show_message(QMessageBox.Icon.Warning, "Error", "OpenCV no está instalado. Instala: python -m pip install opencv-python")
        except Exception as e:
            self._show_message(QMessageBox.Icon.Warning, "Error", f"Error al registrar usuario: {e}")

    # ===== PESTAÑA AVANZADO =====
    def _build_advanced_tab(self):
        tab = QWidget()
        tab.setStyleSheet("background: #000d14;")
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 8, 10, 8)

        lbl = QLabel(tr("CONFIGURACIONES AVANZADAS"))
        self._set_i18n_property(lbl, "CONFIGURACIONES AVANZADAS")
        lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(lbl)

        mode_group = QGroupBox(tr("Modo de respuesta"))
        self._set_i18n_property(mode_group, "Modo de respuesta")
        mode_group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        mode_layout = QVBoxLayout(mode_group)
        self._response_mode_combo = QComboBox()
        self._response_mode_combo.addItems([tr("Voz + Texto"), tr("Solo Voz"), tr("Solo Texto")])
        self._response_mode_combo.setCurrentIndex(
            ["voice_text", "voice_only", "text_only"].index(self._temp.get("response_mode", "voice_text"))
        )
        self._response_mode_combo.setStyleSheet(f"""
            QComboBox {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 4px;
                padding: 4px 8px;
            }}
            QComboBox:hover {{ border-color: {C.PRI_DIM}; }}
        """)
        self._response_mode_combo.currentIndexChanged.connect(self._on_response_mode_changed)
        mode_layout.addWidget(self._response_mode_combo)
        layout.addWidget(mode_group)

        focus_group = QGroupBox(tr("Modo No Molestar"))
        self._set_i18n_property(focus_group, "Modo No Molestar")
        focus_group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        focus_layout = QHBoxLayout(focus_group)
        self._focus_mode_check = QCheckBox(tr("Activar/Desactivar"))
        self._set_i18n_property(self._focus_mode_check, "Activar/Desactivar")
        self._focus_mode_check.setChecked(self._temp.get("focus_mode", False))
        self._focus_mode_check.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        self._focus_mode_check.toggled.connect(self._on_focus_mode_toggled)
        focus_layout.addWidget(self._focus_mode_check)
        focus_layout.addStretch()
        layout.addWidget(focus_group)

        vad_group = QGroupBox(tr("VAD (Detección de Voz)"))
        self._set_i18n_property(vad_group, "VAD (Detección de Voz)")
        vad_group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        vad_layout = QHBoxLayout(vad_group)
        self._vad_check = QCheckBox(tr("Activar/Desactivar"))
        self._set_i18n_property(self._vad_check, "Activar/Desactivar")
        self._vad_check.setChecked(self._temp.get("vad_enabled", False))
        self._vad_check.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        self._vad_check.toggled.connect(self._on_vad_toggled)
        vad_layout.addWidget(self._vad_check)
        vad_layout.addStretch()
        layout.addWidget(vad_group)

        rag_group = QGroupBox(tr("RAG (Memoria avanzada)"))
        self._set_i18n_property(rag_group, "RAG (Memoria avanzada)")
        rag_group.setStyleSheet(f"color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 4px; padding: 6px;")
        rag_layout = QHBoxLayout(rag_group)
        self._rag_check = QCheckBox(tr("Activar/Desactivar"))
        self._set_i18n_property(self._rag_check, "Activar/Desactivar")
        self._rag_check.setChecked(self._temp.get("rag_enabled", False))
        self._rag_check.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        self._rag_check.toggled.connect(self._on_rag_toggled)
        rag_layout.addWidget(self._rag_check)
        rag_layout.addStretch()
        layout.addWidget(rag_group)

        layout.addStretch()
        return tab

    def _on_response_mode_changed(self, index):
        modes = ["voice_text", "voice_only", "text_only"]
        mode = modes[index]
        self._temp["response_mode"] = mode
        self._mark_unsaved()
        _save_config(self._temp)
        self.response_mode_changed.emit(mode)
        if self.main_window and hasattr(self.main_window, 'on_response_mode_change'):
            self.main_window.on_response_mode_change(mode)

    def _on_focus_mode_toggled(self, checked):
        self._temp["focus_mode"] = checked
        self._mark_unsaved()
        _save_config(self._temp)
        self.focus_mode_toggled.emit(checked)
        if self.main_window and hasattr(self.main_window, 'on_focus_mode_toggle'):
            self.main_window.on_focus_mode_toggle(checked)

    def _on_vad_toggled(self, checked):
        self._temp["vad_enabled"] = checked
        self._mark_unsaved()
        _save_config(self._temp)
        if self.main_window:
            self.main_window.write_log(f"SYS: VAD {'activado' if checked else 'desactivado'}")

    def _on_rag_toggled(self, checked):
        self._temp["rag_enabled"] = checked
        self._mark_unsaved()
        _save_config(self._temp)
        if self.main_window:
            self.main_window.write_log(f"SYS: RAG {'activado' if checked else 'desactivado'}")

    # ===== GUARDAR Y CANCELAR =====
    def _save(self):
        # ===== GUARDAR TODAS LAS API KEYS =====
        # Leer los valores actuales de los campos
        gemini_key = self._gemini_key_input.text().strip() if self._gemini_key_input else ""
        openrouter_key = self._openrouter_key_input.text().strip() if self._openrouter_key_input else ""
        groq_key = self._groq_key_input.text().strip() if self._groq_key_input else ""

        # Guardar en _temp y luego en el archivo
        if gemini_key:
            self._temp["gemini_api_key"] = gemini_key
        if openrouter_key:
            self._temp["openrouter_api_key"] = openrouter_key
        if groq_key:
            self._temp["groq_api_key"] = groq_key

        # También guardar otros campos de configuración
        self._save_current_profile_from_widgets()
        selected_personality = self._current_profile_personality
        profile = self._profiles.get(selected_personality, {})
        self._temp["personality"] = selected_personality
        self._temp["voice"] = profile.get("voice", "Charon")
        self._temp["ui_color"] = profile.get("ui_color", THEME_MAP.get(selected_personality, DEFAULT_THEME))
        for key in ["ui_main_bg", "ui_log_bg", "ui_log_text", "ui_news_bg", "ui_news_text",
                    "ui_input_bg", "ui_input_text", "ui_button_bg", "ui_button_text",
                    "ui_title_color", "ui_status_color", "ui_border_color"]:
            self._temp[key] = profile.get(key, self._temp.get(key, "#00d4ff"))
        self._temp["personality_profiles"] = self._profiles

        # Guardar opacidad
        if self._opacity_slider is not None:
            self._temp["window_opacity"] = self._opacity_slider.value() / 100.0

        # Guardar todo
        _save_config(self._temp)

        ui_color = self._temp["ui_color"]
        self.saved.emit(
            self._temp.get("assistant_name", "APOLO"),
            self._temp.get("user_name", "Christopher"),
            ui_color,
            selected_personality,
            self._temp["voice"]
        )

        if self.main_window:
            self.main_window.set_personality_info(selected_personality, self._temp["voice"], ui_color)
            self.main_window._apply_ui_colors(self._temp)
            if hasattr(self.main_window, 'on_personality_change'):
                self.main_window.on_personality_change(selected_personality, self._temp["voice"])

        self._has_unsaved_changes = False
        self.hide()

    def _cancel(self):
        if self._has_unsaved_changes:
            reply = self._show_message(
                QMessageBox.Icon.Question,
                tr("Cambios sin guardar"),
                "Hay cambios sin aplicar. ¿Deseas guardarlos antes de cerrar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._save()
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        self.hide()

    def closeEvent(self, event):
        self._cancel()
        event.accept()
