# src/ui/main_window_parts.py
"""
Partes de la ventana principal (UIBuilderMixin).
Contiene la construcción de la barra superior, paneles laterales, contenido y footer.
Integrado con control por gestos.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QLineEdit,
    QFrame, QSplitter, QStackedWidget, QTextEdit, QSizePolicy, QScrollArea
)
from PyQt6.QtGui import QFont

try:
    from src.config.settings import LEFT_W, RIGHT_W
except ImportError:  # compatibilidad con lanzadores antiguos
    from config.settings import LEFT_W, RIGHT_W
from src.ui.ui_utils import C, qcol, _read_full_config
from src.utils.i18n import tr
from src.ui.widgets import (
    MetricBar, LogWidget, FileDropZone,
    SystemStatusWidget, BatteryWidget, WeatherWidget,
    SwapWidget, NetworkGraphWidget
)
from src.utils.system_utils import _OS


class UIBuilderMixin:
    """Mixin que contiene los métodos de construcción de la interfaz."""

    # ============================================================
    # CABECERA CON BARRA DE ACCIONES (reemplaza al slider)
    # ============================================================
    def _build_header(self) -> QWidget:
        """
        Construye la barra superior con:
        - Fila 1: título, subtítulo, reloj y fecha (igual que antes)
        - Fila 2: todos los botones de acción y toggles (antes en el slider)
        """
        # Contenedor principal (dos filas)
        header_widget = QWidget()
        header_widget.setStyleSheet(f"background: {C.DARK}; border-bottom: 1px solid {C.BORDER_B};")
        layout = QVBoxLayout(header_widget)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        # ---------- FILA 1: CABECERA ORIGINAL ----------
        row1 = QWidget()
        row1.setFixedHeight(52)
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(8, 0, 8, 0)
        row1_layout.setSpacing(8)

        # Botón visible del menú flotante. La versión histórica de ui.py lo
        # construía en un bloque que ya no se ejecutaba tras delegar en este
        # mixin; por eso el menú existía pero no podía abrirse desde la UI.
        self._menu_btn = QPushButton("☰  MENÚ")
        self._menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._menu_btn.setStyleSheet(f"""
            QPushButton {{ background: {C.PANEL}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 5px;
                padding: 5px 9px; font-weight: bold; }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
        """)
        self._menu_btn.clicked.connect(self._toggle_float_menu)
        row1_layout.addWidget(self._menu_btn)

        # Badge izquierdo
        row1_layout.addWidget(self._make_badge("XxchristoxX", C.PRI_DIM))
        row1_layout.addSpacing(8)

        # Título y subtítulo
        mid = QVBoxLayout()
        mid.setSpacing(1)
        self._title_lbl = QLabel(self._assistant_name)
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_lbl.setFont(QFont("Courier New", 18, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        mid.addWidget(self._title_lbl)

        self._sub_lbl = QLabel(self._assistant_subtitle)
        self._sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_lbl.setFont(QFont("Courier New", 8))
        self._sub_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        mid.addWidget(self._sub_lbl)
        row1_layout.addLayout(mid, stretch=1)

        # Reloj y fecha (derecha)
        right_col = QVBoxLayout()
        right_col.setSpacing(2)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(QFont("Courier New", 15, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)

        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont("Courier New", 8))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        row1_layout.addLayout(right_col)

        layout.addWidget(row1)

        # ---------- FILA 2: BARRA DE ACCIONES ----------
        row2 = QWidget()
        row2.setFixedHeight(40)
        row2.setStyleSheet(f"background: {C.PANEL2}; border-top: 1px solid {C.BORDER_A};")
        row2_layout = QHBoxLayout(row2)
        row2_layout.setContentsMargins(6, 2, 6, 2)
        row2_layout.setSpacing(4)

        # Estilos comunes
        action_style = f"""
            QPushButton {{
                background: {C.PANEL};
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 8pt;
                font-family: 'Segoe UI', 'Courier New', monospace;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO};
                border-color: {C.PRI_DIM};
                color: {C.PRI};
            }}
        """
        toggle_style_off = f"""
            QPushButton {{
                background: #2a0a0a;
                color: {C.MUTED_C};
                border: 1px solid {C.MUTED_C};
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 8pt;
                font-family: 'Segoe UI', 'Courier New', monospace;
            }}
            QPushButton:hover {{
                background: #3d0f0f;
                border-color: #ff6688;
            }}
        """

        # Añadir stretch al inicio para centrar el grupo
        row2_layout.addStretch(1)

        # --- Botones de acción ---
        # 1. Control remoto
        self._btn_remote = QPushButton("◉  " + tr("REMOTE"))
        self._btn_remote.setStyleSheet(action_style)
        self._btn_remote.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_remote.clicked.connect(self._open_remote)
        row2_layout.addWidget(self._btn_remote)

        # 2. Crear acceso directo
        self._btn_shortcut = QPushButton("⊞  " + tr("SHORTCUT"))
        self._btn_shortcut.setStyleSheet(action_style)
        self._btn_shortcut.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_shortcut.clicked.connect(self._create_desktop_shortcut)
        row2_layout.addWidget(self._btn_shortcut)

        # 3. Personalizar asistente
        self._btn_customize = QPushButton("⚙  " + tr("CUSTOMISE"))
        self._btn_customize.setStyleSheet(action_style)
        self._btn_customize.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_customize.clicked.connect(self._open_customize)
        row2_layout.addWidget(self._btn_customize)

        # 4. Reiniciar asistente
        self._btn_restart = QPushButton("⟳  " + tr("RESTART"))
        self._btn_restart.setStyleSheet(action_style)
        self._btn_restart.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_restart.clicked.connect(self._restart_assistant)
        row2_layout.addWidget(self._btn_restart)

        # 5. Acerca de
        self._btn_about = QPushButton("ℹ  " + tr("ABOUT"))
        self._btn_about.setStyleSheet(action_style)
        self._btn_about.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_about.clicked.connect(self._show_about)
        row2_layout.addWidget(self._btn_about)

        # 6. Modo flotante
        self._btn_float = QPushButton("◈  " + tr("FLOAT"))
        self._btn_float.setStyleSheet(action_style)
        self._btn_float.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_float.clicked.connect(self._toggle_float_mode)
        row2_layout.addWidget(self._btn_float)

        # 7. Abrir Dashboard
        self._btn_dashboard = QPushButton("📡  " + tr("DASHBOARD"))
        self._btn_dashboard.setStyleSheet(action_style)
        self._btn_dashboard.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_dashboard.clicked.connect(self._open_dashboard)
        row2_layout.addWidget(self._btn_dashboard)

        # 8. Limpiar registro
        self._btn_clear = QPushButton("🗑  " + tr("CLEAR LOG"))
        self._btn_clear.setStyleSheet(action_style)
        self._btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clear.clicked.connect(self._clear_logs)
        row2_layout.addWidget(self._btn_clear)

        # 9. Exportar registro
        self._btn_export = QPushButton("💾  " + tr("EXPORT LOG"))
        self._btn_export.setStyleSheet(action_style)
        self._btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_export.clicked.connect(self._export_logs)
        row2_layout.addWidget(self._btn_export)

        # 10. Contactos
        self._btn_contacts = QPushButton("👤  " + tr("CONTACTS"))
        self._btn_contacts.setStyleSheet(action_style)
        self._btn_contacts.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_contacts.clicked.connect(self._open_contacts)
        row2_layout.addWidget(self._btn_contacts)

        # 11. Smart Home
        self._btn_smarthome = QPushButton("🏠  " + tr("SMARTHOME"))
        self._btn_smarthome.setStyleSheet(action_style)
        self._btn_smarthome.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_smarthome.clicked.connect(self._open_smarthome)
        row2_layout.addWidget(self._btn_smarthome)

        # 12. Android
        self._btn_android = QPushButton("📱  " + tr("ANDROID"))
        self._btn_android.setStyleSheet(action_style)
        self._btn_android.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_android.clicked.connect(self._toggle_android)
        row2_layout.addWidget(self._btn_android)

        # --- Separador visual entre acciones y toggles ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"background: {C.BORDER}; width: 1px;")
        row2_layout.addWidget(sep)

        # --- Botones de control multimedia ---
        self._btn_media_prev = QPushButton("⏮  " + tr("PREV"))
        self._btn_media_prev.setStyleSheet(action_style)
        self._btn_media_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_media_prev.clicked.connect(self._media_prev)
        row2_layout.addWidget(self._btn_media_prev)

        self._btn_media_play = QPushButton("⏯  " + tr("PLAY/PAUSE"))
        self._btn_media_play.setStyleSheet(action_style)
        self._btn_media_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_media_play.clicked.connect(self._media_play_pause)
        row2_layout.addWidget(self._btn_media_play)

        self._btn_media_next = QPushButton("⏭  " + tr("NEXT"))
        self._btn_media_next.setStyleSheet(action_style)
        self._btn_media_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_media_next.clicked.connect(self._media_next)
        row2_layout.addWidget(self._btn_media_next)

        # --- Botones toggle (On/Off) ---
        # 13. Detección de aplausos
        self._btn_clap = QPushButton("👏  " + tr("CLAP: OFF"))
        self._btn_clap.setCheckable(True)
        self._btn_clap.setStyleSheet(toggle_style_off)
        self._btn_clap.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clap.toggled.connect(self._on_clap_toggled)
        row2_layout.addWidget(self._btn_clap)

        # 14. Portapapeles Proactivo
        self._btn_clipboard = QPushButton("📋  " + tr("CLIPBOARD: OFF"))
        self._btn_clipboard.setCheckable(True)
        self._btn_clipboard.setStyleSheet(toggle_style_off)
        self._btn_clipboard.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clipboard.toggled.connect(self._on_clipboard_toggled)
        row2_layout.addWidget(self._btn_clipboard)

        # 15. Modo Aura
        self._btn_aura = QPushButton("🎭  " + tr("AURA: OFF"))
        self._btn_aura.setCheckable(True)
        self._btn_aura.setStyleSheet(toggle_style_off)
        self._btn_aura.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_aura.toggled.connect(self._on_aura_toggled)
        row2_layout.addWidget(self._btn_aura)

        # 16. Escucha Continua
        self._btn_continuous = QPushButton("👂  " + tr("CONTINUOUS: OFF"))
        self._btn_continuous.setCheckable(True)
        self._btn_continuous.setStyleSheet(toggle_style_off)
        self._btn_continuous.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_continuous.toggled.connect(self._on_continuous_toggled)
        row2_layout.addWidget(self._btn_continuous)

        # 17. Inicio automático
        self._btn_autostart = QPushButton("◉  " + tr("AUTO-START: OFF"))
        self._btn_autostart.setCheckable(True)
        self._btn_autostart.setStyleSheet(toggle_style_off)
        self._btn_autostart.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_autostart.toggled.connect(self._on_autostart_toggled)
        row2_layout.addWidget(self._btn_autostart)

        # 18. Resumen Matutino
        self._btn_brief = QPushButton("☀  " + tr("BRIEF: OFF"))
        self._btn_brief.setCheckable(True)
        self._btn_brief.setStyleSheet(toggle_style_off)
        self._btn_brief.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_brief.toggled.connect(self._on_brief_toggled)
        row2_layout.addWidget(self._btn_brief)

        # ===== NUEVO: BOTÓN DE CONTROL POR GESTOS =====
        self._btn_gesture = QPushButton("🖐  " + tr("GESTURE: OFF"))
        self._btn_gesture.setCheckable(True)
        self._btn_gesture.setStyleSheet(toggle_style_off)
        self._btn_gesture.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_gesture.toggled.connect(self._on_gesture_toggled)
        row2_layout.addWidget(self._btn_gesture)

        # Añadir stretch al final para centrar el grupo
        row2_layout.addStretch(1)

        layout.addWidget(row2)

        # Guardar referencias a los botones para actualización de estado
        self._action_buttons = {
            'clap': self._btn_clap,
            'clipboard': self._btn_clipboard,
            'aura': self._btn_aura,
            'continuous': self._btn_continuous,
            'autostart': self._btn_autostart,
            'brief': self._btn_brief,
            'gesture': self._btn_gesture,
        }

        return header_widget

    # ------------------------------------------------------------
    # Slots para los toggles
    # ------------------------------------------------------------
    def _on_clap_toggled(self, checked: bool):
        if self.on_text_command:
            self.on_text_command("toggle_clap_detection " + ("on" if checked else "off"))
        self._update_toggle_style(self._btn_clap, checked, "CLAP")

    def _on_clipboard_toggled(self, checked: bool):
        if self.on_text_command:
            self.on_text_command("clipboard_proactive " + ("on" if checked else "off"))
        self._update_toggle_style(self._btn_clipboard, checked, "CLIPBOARD")

    def _on_aura_toggled(self, checked: bool):
        if self.on_text_command:
            self.on_text_command("toggle_aura_mode " + ("on" if checked else "off"))
        self._update_toggle_style(self._btn_aura, checked, "AURA")

    def _on_continuous_toggled(self, checked: bool):
        if self.on_text_command:
            self.on_text_command("toggle_continuous_listening " + ("on" if checked else "off"))
        self._update_toggle_style(self._btn_continuous, checked, "CONTINUOUS")

    def _on_autostart_toggled(self, checked: bool):
        self._toggle_autostart()
        QTimer.singleShot(50, self._update_autostart_state)

    def _on_brief_toggled(self, checked: bool):
        self._toggle_brief()
        QTimer.singleShot(50, self._update_brief_state)

    def _on_gesture_toggled(self, checked: bool):
        """Maneja el toggle del control por gestos."""
        if self.on_text_command:
            self.on_text_command("gesture_control " + ("start" if checked else "stop"))
        self._update_toggle_style(self._btn_gesture, checked, "GESTURE")

    # ------------------------------------------------------------
    # Actualización de estilos de toggles
    # ------------------------------------------------------------
    def _update_toggle_style(self, btn: QPushButton, checked: bool, label: str):
        if checked:
            btn.setText(f"🟢  {label}: ON")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #002a1a;
                    color: {C.GREEN};
                    border: 1px solid {C.GREEN_D};
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 8pt;
                    font-family: 'Segoe UI', 'Courier New', monospace;
                }}
                QPushButton:hover {{
                    background: #003d26;
                    border-color: {C.GREEN};
                }}
            """)
        else:
            btn.setText(f"🔴  {label}: OFF")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #2a0a0a;
                    color: {C.MUTED_C};
                    border: 1px solid {C.MUTED_C};
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 8pt;
                    font-family: 'Segoe UI', 'Courier New', monospace;
                }}
                QPushButton:hover {{
                    background: #3d0f0f;
                    border-color: #ff6688;
                }}
            """)

    def _update_autostart_state(self):
        """Actualiza el botón de autostart según el estado real."""
        enabled = self._check_autostart()
        if hasattr(self, '_btn_autostart'):
            self._btn_autostart.blockSignals(True)
            self._btn_autostart.setChecked(enabled)
            self._update_toggle_style(self._btn_autostart, enabled, "AUTO-START")
            self._btn_autostart.blockSignals(False)

    def _update_brief_state(self):
        """Actualiza el botón de resumen matutino según el estado real."""
        from src.memory.config_manager import get_brief_enabled
        enabled = get_brief_enabled()
        if hasattr(self, '_btn_brief'):
            self._btn_brief.blockSignals(True)
            self._btn_brief.setChecked(enabled)
            self._update_toggle_style(self._btn_brief, enabled, "BRIEF")
            self._btn_brief.blockSignals(False)

    def _update_gesture_state(self):
        """Actualiza el botón de gestos según el estado real del gestor."""
        try:
            from src.actions.gesture_control import get_gesture_manager
            gm = get_gesture_manager()
            enabled = gm._running if gm else False
            if hasattr(self, '_btn_gesture'):
                self._btn_gesture.blockSignals(True)
                self._btn_gesture.setChecked(enabled)
                self._update_toggle_style(self._btn_gesture, enabled, "GESTURE")
                self._btn_gesture.blockSignals(False)
        except Exception:
            pass

    def _update_all_toggle_states(self):
        """Actualiza todos los toggles."""
        self._update_autostart_state()
        self._update_brief_state()
        self._update_gesture_state()
        # Para los demás, inicializar en OFF (o leer de config si se guarda)
        for key in ['clap', 'clipboard', 'aura', 'continuous']:
            btn = self._action_buttons.get(key)
            if btn:
                btn.blockSignals(True)
                btn.setChecked(False)
                self._update_toggle_style(btn, False, key.upper())
                btn.blockSignals(False)

    # ------------------------------------------------------------
    # MÉTODOS DE CONTROL MULTIMEDIA
    # ------------------------------------------------------------
    def _media_prev(self):
        """Ir a la canción anterior."""
        try:
            import pyautogui
            pyautogui.press('prevtrack')
            self._log.append_log("SYS: Canción anterior.")
        except Exception:
            self._log.append_log("SYS: Control multimedia no disponible (pyautogui).")

    def _media_play_pause(self):
        """Reproducir o pausar."""
        try:
            import pyautogui
            pyautogui.press('playpause')
            self._log.append_log("SYS: Play/Pause.")
        except Exception:
            self._log.append_log("SYS: Control multimedia no disponible (pyautogui).")

    def _media_next(self):
        """Ir a la siguiente canción."""
        try:
            import pyautogui
            pyautogui.press('nexttrack')
            self._log.append_log("SYS: Siguiente canción.")
        except Exception:
            self._log.append_log("SYS: Control multimedia no disponible (pyautogui).")

    # ============================================================
    # MÉTODOS ORIGINALES (sin cambios, solo adaptados)
    # ============================================================

    def _make_badge(self, txt, color):
        l = QLabel(txt)
        l.setFont(QFont("Courier New", 8))
        l.setStyleSheet(f"color: {color}; background: transparent;")
        return l

    # ------------------------------------------------------------
    # PANEL IZQUIERDO
    # ------------------------------------------------------------
    def _build_left_panel(self) -> QWidget:
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

        # ---- 1. SISTEMA ----
        self.sys_group = QGroupBox("🖥️  SISTEMA")
        self.sys_group.setStyleSheet(get_group_style())
        sys_layout = QVBoxLayout(self.sys_group)
        sys_layout.setContentsMargins(4, 4, 4, 4)
        self.system_widget = SystemStatusWidget()
        self.system_widget.setMaximumHeight(1800)
        sys_layout.addWidget(self.system_widget)
        content_layout.addWidget(self.sys_group)

        # ---- 2. BATERÍA ----
        self.batt_group = QGroupBox("🔋  BATERÍA")
        self.batt_group.setStyleSheet(get_group_style())
        batt_layout = QVBoxLayout(self.batt_group)
        batt_layout.setContentsMargins(4, 4, 4, 4)
        self.battery_widget = BatteryWidget()
        self.battery_widget.setFixedHeight(70)
        batt_layout.addWidget(self.battery_widget)
        content_layout.addWidget(self.batt_group)

        # ---- 3. TRÁFICO DE RED ----
        self.net_group = QGroupBox("📶  TRÁFICO DE RED")
        self.net_group.setStyleSheet(get_group_style())
        net_layout = QVBoxLayout(self.net_group)
        net_layout.setContentsMargins(4, 4, 4, 4)
        self.network_widget = NetworkGraphWidget()
        self.network_widget.setFixedHeight(80)
        net_layout.addWidget(self.network_widget)
        content_layout.addWidget(self.net_group)

        # ---- 4. CLIMA ----
        self.weather_group = QGroupBox("🌤️  CLIMA")
        self.weather_group.setStyleSheet(get_group_style())
        weather_layout = QVBoxLayout(self.weather_group)
        weather_layout.setContentsMargins(4, 4, 4, 4)
        self.weather_widget = WeatherWidget()
        self.weather_widget.setFixedHeight(80)
        weather_layout.addWidget(self.weather_widget)
        content_layout.addWidget(self.weather_group)

        # ---- 5. MEMORIA SWAP ----
        self.swap_group = QGroupBox("💾  MEMORIA SWAP")
        self.swap_group.setStyleSheet(get_group_style())
        swap_layout = QVBoxLayout(self.swap_group)
        swap_layout.setContentsMargins(4, 4, 4, 4)
        self.swap_widget = SwapWidget()
        self.swap_widget.setFixedHeight(30)
        swap_layout.addWidget(self.swap_widget)
        content_layout.addWidget(self.swap_group)

        # ---- 6. CONTROL ----
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

        # ---- BADGES ----
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

    # ------------------------------------------------------------
    # PANEL DERECHO
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # INPUT ROW
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # CONTENT PANEL
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # FOOTER
    # ------------------------------------------------------------
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

        lay.addWidget(_fl("[F4] Mute"))
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
