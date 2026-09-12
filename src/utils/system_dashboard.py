#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JARVIS OS - Panel de control flotante
Inspirado en los wallpapers de JARVIS
Versión 1.2.5
"""

import sys
import os
import json
import time
import subprocess
import webbrowser
from datetime import datetime
import psutil
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QSystemTrayIcon, QMenu,
                             QAction, QFrame, QProgressBar, QDialog, QTextEdit,
                             QMessageBox, QGroupBox, QCheckBox, QSpinBox)
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QVariantAnimation
from PyQt5.QtGui import (QPainter, QBrush, QPen, QColor, QFont, QPixmap,
                         QIcon, QRadialGradient)

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

CONFIG_PATH = os.path.expanduser("~/.jarvis_panel_config.json")
DEFAULT_CONFIG = {
    "window_width": 420,
    "window_height": 600,
    "opacity": 0.92,
    "always_on_top": True,
    "show_cpu_cores": 8,
    "theme": "dark"
}

class ConfigManager:
    def __init__(self):
        self.config = {}
        self.load()

    def load(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    self.config = json.load(f)
            except:
                self.config = DEFAULT_CONFIG.copy()
        else:
            self.config = DEFAULT_CONFIG.copy()
            self.save()

    def save(self):
        with open(CONFIG_PATH, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()

# ============================================================================
# WIDGET DE BARRA DE PROGRESO ESTILO JARVIS
# ============================================================================

class JarvisProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QProgressBar {
                background-color: rgba(30, 30, 50, 180);
                border: 1px solid rgba(0, 255, 204, 80);
                border-radius: 4px;
                text-align: center;
                color: #00FFCC;
                font-size: 9px;
                font-weight: bold;
                height: 16px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                  stop:0 #00FFCC, stop:1 #00AA88);
                border-radius: 3px;
            }
        """)
        self.setRange(0, 100)
        self.setTextVisible(True)

    def setValue(self, value):
        super().setValue(int(value))

# ============================================================================
# PANEL PRINCIPAL
# ============================================================================

class JarvisPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.drag_pos = None
        self.start_time = time.time()
        self.cpu_cores = psutil.cpu_count(logical=True)
        self.show_cores = min(self.config.get("show_cpu_cores", 8), self.cpu_cores)

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(
            self.config.get("window_width", 420),
            self.config.get("window_height", 600)
        )
        self.setWindowOpacity(self.config.get("opacity", 0.92))

        # Layout principal
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(5)

        # Contenedor con efecto glassmorphism
        self.container = QFrame()
        self.container.setObjectName("container")
        self.container.setStyleSheet("""
            QFrame#container {
                background-color: rgba(10, 10, 25, 0.85);
                border-radius: 15px;
                border: 1px solid rgba(0, 255, 204, 40);
            }
        """)
        self.main_layout.addWidget(self.container)

        # Layout interno
        self.inner_layout = QVBoxLayout(self.container)
        self.inner_layout.setContentsMargins(15, 10, 15, 10)
        self.inner_layout.setSpacing(6)

        # ===== BARRA DE TÍTULO =====
        self.title_bar = QFrame()
        self.title_bar.setFixedHeight(30)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel("⚡ JARVIS OS  v1.2.5")
        self.title_label.setStyleSheet("color: #00FFCC; font-size: 14px; font-weight: bold;")
        title_layout.addWidget(self.title_label)

        title_layout.addStretch()

        # Botones de control
        self.btn_collapse = self._create_title_button("━", self.toggle_collapse)
        self.btn_close = self._create_title_button("✕", self.close_app)
        title_layout.addWidget(self.btn_collapse)
        title_layout.addWidget(self.btn_close)

        self.inner_layout.addWidget(self.title_bar)

        # ===== CONTENIDO =====
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(4)

        # ---- Usuario ----
        user_label = QLabel(f"User: {os.getlogin()}")
        user_label.setStyleSheet("color: #88CCFF; font-size: 11px;")
        self.content_layout.addWidget(user_label)

        # ---- Fecha/Hora ----
        self.time_label = QLabel(datetime.now().strftime("%H:%M:%S"))
        self.time_label.setStyleSheet("color: #00FFCC; font-size: 18px; font-weight: bold;")
        self.content_layout.addWidget(self.time_label)

        self.date_label = QLabel(datetime.now().strftime("%A, %d %B %Y"))
        self.date_label.setStyleSheet("color: #6688AA; font-size: 11px;")
        self.content_layout.addWidget(self.date_label)

        # ---- Uptime ----
        self.uptime_label = QLabel("Uptime: 0h 0m")
        self.uptime_label.setStyleSheet("color: #88CCFF; font-size: 11px;")
        self.content_layout.addWidget(self.uptime_label)

        # ---- CPU Global ----
        cpu_frame = QFrame()
        cpu_layout = QHBoxLayout(cpu_frame)
        cpu_layout.setContentsMargins(0, 5, 0, 5)

        cpu_label = QLabel("CPU")
        cpu_label.setStyleSheet("color: #00FFCC; font-size: 12px; font-weight: bold;")
        cpu_layout.addWidget(cpu_label)

        self.cpu_bar = JarvisProgressBar()
        self.cpu_bar.setFixedHeight(18)
        cpu_layout.addWidget(self.cpu_bar)

        self.cpu_percent_label = QLabel("0%")
        self.cpu_percent_label.setStyleSheet("color: #FFFFFF; font-size: 11px;")
        cpu_layout.addWidget(self.cpu_percent_label)

        self.content_layout.addWidget(cpu_frame)

        # ---- CPU por núcleo (scrollable) ----
        core_group = QGroupBox("Núcleos")
        core_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid rgba(0, 255, 204, 30);
                border-radius: 6px;
                margin-top: 8px;
                color: #88CCFF;
                font-size: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        core_layout = QVBoxLayout(core_group)

        self.core_bars = []
        self.core_labels = []
        for i in range(self.show_cores):
            core_frame = QFrame()
            core_h_layout = QHBoxLayout(core_frame)
            core_h_layout.setContentsMargins(0, 0, 0, 0)

            label = QLabel(f"CPU {i+1}")
            label.setStyleSheet("color: #88CCFF; font-size: 9px;")
            core_h_layout.addWidget(label)

            bar = JarvisProgressBar()
            bar.setFixedHeight(12)
            core_h_layout.addWidget(bar)

            perc_label = QLabel("0%")
            perc_label.setStyleSheet("color: #FFFFFF; font-size: 9px;")
            core_h_layout.addWidget(perc_label)

            core_layout.addWidget(core_frame)
            self.core_bars.append(bar)
            self.core_labels.append(perc_label)

        # Si hay más núcleos de los mostrados, añadir botón para ver más
        if self.cpu_cores > self.show_cores:
            more_btn = QPushButton(f"Mostrar {self.cpu_cores - self.show_cores} núcleos más")
            more_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 255, 204, 20);
                    color: #00FFCC;
                    border: 1px solid #00FFCC;
                    border-radius: 4px;
                    font-size: 9px;
                    padding: 2px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 255, 204, 40);
                }
            """)
            more_btn.clicked.connect(self.show_all_cores)
            core_layout.addWidget(more_btn)

        self.content_layout.addWidget(core_group)

        # ---- RAM y SWAP ----
        ram_frame = QFrame()
        ram_layout = QVBoxLayout(ram_frame)
        ram_layout.setContentsMargins(0, 5, 0, 5)

        # RAM
        ram_row = QHBoxLayout()
        ram_label = QLabel("RAM")
        ram_label.setStyleSheet("color: #4FC3F7; font-size: 12px; font-weight: bold;")
        ram_row.addWidget(ram_label)
        self.ram_bar = JarvisProgressBar()
        self.ram_bar.setFixedHeight(16)
        ram_row.addWidget(self.ram_bar)
        self.ram_percent_label = QLabel("0%")
        self.ram_percent_label.setStyleSheet("color: #FFFFFF; font-size: 11px;")
        ram_row.addWidget(self.ram_percent_label)
        ram_layout.addLayout(ram_row)

        # SWAP
        swap_row = QHBoxLayout()
        swap_label = QLabel("SWAP")
        swap_label.setStyleSheet("color: #FFD54F; font-size: 12px; font-weight: bold;")
        swap_row.addWidget(swap_label)
        self.swap_bar = JarvisProgressBar()
        self.swap_bar.setFixedHeight(16)
        swap_row.addWidget(self.swap_bar)
        self.swap_percent_label = QLabel("0%")
        self.swap_percent_label.setStyleSheet("color: #FFFFFF; font-size: 11px;")
        swap_row.addWidget(self.swap_percent_label)
        ram_layout.addLayout(swap_row)

        self.content_layout.addWidget(ram_frame)

        # ---- Tráfico de red ----
        net_frame = QFrame()
        net_layout = QHBoxLayout(net_frame)
        net_layout.setContentsMargins(0, 5, 0, 5)

        self.net_label = QLabel("⬇ 0 KB/s  ⬆ 0 KB/s")
        self.net_label.setStyleSheet("color: #88CCFF; font-size: 11px;")
        net_layout.addWidget(self.net_label)

        self.content_layout.addWidget(net_frame)

        # ---- Botones de utilidades ----
        util_frame = QFrame()
        util_layout = QHBoxLayout(util_frame)
        util_layout.setSpacing(6)

        utilities = [
            ("🌐", "Web", lambda: webbrowser.open("https://google.com")),
            ("🧮", "Calc", self.open_calculator),
            ("⬛", "Terminal", self.open_terminal),
            ("📝", "Notas", self.open_notes),
            ("📂", "Archivos", self.open_file_explorer),
            ("📸", "Captura", self.take_screenshot),
            ("🔒", "Bloquear", self.lock_screen),
            ("⚙️", "Config", self.open_settings),
        ]

        for icon, tip, callback in utilities:
            btn = QPushButton(icon)
            btn.setToolTip(tip)
            btn.setFixedSize(36, 36)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(20, 20, 30, 180);
                    color: #00FFCC;
                    border: 1px solid rgba(0, 255, 204, 60);
                    border-radius: 18px;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 255, 204, 30);
                    border: 1px solid #00FFCC;
                }
            """)
            btn.clicked.connect(callback)
            util_layout.addWidget(btn)

        self.content_layout.addWidget(util_frame)

        # ---- Barra de estado ----
        self.status_label = QLabel("Sistema listo")
        self.status_label.setStyleSheet("color: #666688; font-size: 9px;")
        self.content_layout.addWidget(self.status_label)

        self.inner_layout.addWidget(self.content_widget)

        # ---- Timers ----
        self.init_timers()

        # ---- Bandeja del sistema ----
        self.init_tray()

        # Cargar datos iniciales
        QTimer.singleShot(100, self.update_all_data)

    def _create_title_button(self, text, callback):
        btn = QPushButton(text)
        btn.setFixedSize(25, 25)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8888AA;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.1);
                color: #FFFFFF;
            }
        """)
        btn.clicked.connect(callback)
        return btn

    def init_timers(self):
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_all_data)
        self.update_timer.start(1000)

        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)

        self.uptime_timer = QTimer()
        self.uptime_timer.timeout.connect(self.update_uptime)
        self.uptime_timer.start(60000)

    # ========================================================================
    # ACTUALIZACIÓN DE DATOS
    # ========================================================================

    def update_all_data(self):
        try:
            # CPU global
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.cpu_bar.setValue(cpu_percent)
            self.cpu_percent_label.setText(f"{int(cpu_percent)}%")

            # CPU por núcleo
            core_percents = psutil.cpu_percent(interval=0.1, percpu=True)
            for i, bar in enumerate(self.core_bars):
                if i < len(core_percents):
                    val = core_percents[i]
                    bar.setValue(val)
                    self.core_labels[i].setText(f"{int(val)}%")

            # RAM
            mem = psutil.virtual_memory()
            self.ram_bar.setValue(mem.percent)
            self.ram_percent_label.setText(f"{int(mem.percent)}%")

            # SWAP
            swap = psutil.swap_memory()
            self.swap_bar.setValue(swap.percent)
            self.swap_percent_label.setText(f"{int(swap.percent)}%")

            # Red
            net = psutil.net_io_counters()
            self.net_label.setText(
                f"⬇ {self._format_bytes(net.bytes_recv)}/s  ⬆ {self._format_bytes(net.bytes_sent)}/s"
            )

            self.status_label.setText(f"CPU: {int(cpu_percent)}%  RAM: {int(mem.percent)}%")
        except Exception as e:
            print(f"Error actualizando datos: {e}")

    def _format_bytes(self, b):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if b < 1024.0:
                return f"{b:.1f}{unit}"
            b /= 1024.0
        return f"{b:.1f}TB"

    def update_clock(self):
        self.time_label.setText(datetime.now().strftime("%H:%M:%S"))
        self.date_label.setText(datetime.now().strftime("%A, %d %B %Y"))

    def update_uptime(self):
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        self.uptime_label.setText(f"Uptime: {hours}h {minutes}m")

    # ========================================================================
    # ACCIONES DE LOS BOTONES
    # ========================================================================

    def open_calculator(self):
        if sys.platform == "win32":
            os.system("calc")
        elif sys.platform == "linux":
            os.system("gnome-calculator &")
        elif sys.platform == "darwin":
            os.system("open -a Calculator")

    def open_terminal(self):
        if sys.platform == "win32":
            os.system("start cmd")
        elif sys.platform == "linux":
            os.system("gnome-terminal &")
        elif sys.platform == "darwin":
            os.system("open -a Terminal")

    def open_notes(self):
        dialog = NotesDialog(self)
        dialog.exec_()

    def open_file_explorer(self):
        if sys.platform == "win32":
            os.system("explorer")
        elif sys.platform == "linux":
            os.system("nautilus &")
        elif sys.platform == "darwin":
            os.system("open .")

    def take_screenshot(self):
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            screenshot.save(filename)
            self.status_label.setText(f"📸 Captura: {filename}")
        except ImportError:
            self.status_label.setText("❌ pip install pyautogui")
        except Exception as e:
            self.status_label.setText(f"❌ Error: {e}")

    def lock_screen(self):
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.LockWorkStation()
        elif sys.platform == "linux":
            os.system("xdg-screensaver lock")
        elif sys.platform == "darwin":
            os.system("pmset displaysleepnow")
        self.status_label.setText("🔒 Pantalla bloqueada")

    def open_settings(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_() == QDialog.Accepted:
            self.apply_config()

    def apply_config(self):
        self.setFixedSize(
            self.config.get("window_width", 420),
            self.config.get("window_height", 600)
        )
        self.setWindowOpacity(self.config.get("opacity", 0.92))
        if self.config.get("always_on_top", True):
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show_cores = min(self.config.get("show_cpu_cores", 8), self.cpu_cores)
        QMessageBox.information(self, "Configuración", "Reinicia la aplicación para aplicar cambios completos.")

    def show_all_cores(self):
        self.show_cores = self.cpu_cores
        self.config.set("show_cpu_cores", self.cpu_cores)
        QMessageBox.information(self, "Núcleos", "Se mostrarán todos los núcleos al reiniciar la aplicación.")

    def toggle_collapse(self):
        if self.height() > 60:
            self.setFixedHeight(55)
            self.content_widget.hide()
            self.btn_collapse.setText("▣")
        else:
            self.setFixedHeight(self.config.get("window_height", 600))
            self.content_widget.show()
            self.btn_collapse.setText("━")

    def close_app(self):
        self.tray_icon.hide()
        QApplication.quit()

    # ========================================================================
    # BANDEJA DEL SISTEMA
    # ========================================================================

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.create_tray_icon())

        tray_menu = QMenu()
        show_action = QAction("Mostrar/Ocultar", self)
        show_action.triggered.connect(self.toggle_visibility)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()
        settings_action = QAction("Configuración", self)
        settings_action.triggered.connect(self.open_settings)
        tray_menu.addAction(settings_action)

        tray_menu.addSeparator()
        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(self.close_app)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()

    def create_tray_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        gradient = QRadialGradient(32, 32, 28)
        gradient.setColorAt(0, QColor(0, 255, 204, 200))
        gradient.setColorAt(1, QColor(0, 100, 80, 200))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(0, 255, 204), 2))
        painter.drawEllipse(4, 4, 56, 56)

        painter.setPen(QPen(QColor(255, 255, 255)))
        font = QFont("Arial", 24, QFont.Bold)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, 64, 64), Qt.AlignCenter, "J")
        painter.end()
        return QIcon(pixmap)

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.toggle_visibility()

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()

    # ========================================================================
    # EVENTOS DE RATÓN
    # ========================================================================

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.title_bar.geometry().contains(event.pos()):
            self.drag_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos is not None:
            self.move(self.pos() + event.globalPos() - self.drag_pos)
            self.drag_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        show_action = QAction("Mostrar/Ocultar", self)
        show_action.triggered.connect(self.toggle_visibility)
        menu.addAction(show_action)

        menu.addSeparator()
        settings_action = QAction("Configuración", self)
        settings_action.triggered.connect(self.open_settings)
        menu.addAction(settings_action)

        menu.addSeparator()
        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(self.close_app)
        menu.addAction(exit_action)

        menu.exec_(event.globalPos())

# ============================================================================
# DIÁLOGO DE NOTAS
# ============================================================================

class NotesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📝 Notas Rápidas")
        self.setFixedSize(400, 350)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                color: #ffffff;
            }
            QTextEdit {
                background-color: #0a0a1a;
                border: 1px solid #00FFCC;
                border-radius: 8px;
                color: #ffffff;
                font-size: 12px;
            }
            QPushButton {
                background-color: #00FFCC;
                color: #1a1a2e;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #33FFDD;
            }
        """)
        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Escribe tus notas aquí...")
        layout.addWidget(self.text_edit)

        btn_layout = QHBoxLayout()
        btn_save = QPushButton("💾 Guardar")
        btn_save.clicked.connect(self.save_note)
        btn_layout.addWidget(btn_save)
        btn_layout.addStretch()
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        self.load_notes()

    def load_notes(self):
        notes_file = os.path.expanduser("~/notes.txt")
        if os.path.exists(notes_file):
            try:
                with open(notes_file, 'r', encoding='utf-8') as f:
                    self.text_edit.setText(f.read())
            except:
                pass

    def save_note(self):
        notes_file = os.path.expanduser("~/notes.txt")
        try:
            with open(notes_file, 'w', encoding='utf-8') as f:
                f.write(self.text_edit.toPlainText())
            QMessageBox.information(self, "Éxito", "Notas guardadas correctamente.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar: {e}")

# ============================================================================
# DIÁLOGO DE CONFIGURACIÓN
# ============================================================================

class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("⚙️ Configuración")
        self.setFixedSize(400, 300)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                color: #ffffff;
            }
            QLabel {
                color: #aaaaaa;
            }
            QSlider {
                background-color: #2a2a3e;
                border: none;
                border-radius: 4px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #333355;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #00FFCC;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QPushButton {
                background-color: #00FFCC;
                color: #1a1a2e;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #33FFDD;
            }
            QPushButton#cancel {
                background-color: #444466;
                color: #ffffff;
            }
            QPushButton#cancel:hover {
                background-color: #555577;
            }
            QSpinBox {
                background-color: #2a2a3e;
                border: 1px solid #333355;
                border-radius: 4px;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self)

        # Ancho
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Ancho:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(300, 600)
        self.width_spin.setValue(self.config.get("window_width", 420))
        width_layout.addWidget(self.width_spin)
        width_layout.addStretch()
        layout.addLayout(width_layout)

        # Alto
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Alto:"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(400, 800)
        self.height_spin.setValue(self.config.get("window_height", 600))
        height_layout.addWidget(self.height_spin)
        height_layout.addStretch()
        layout.addLayout(height_layout)

        # Opacidad
        op_layout = QHBoxLayout()
        op_layout.addWidget(QLabel("Opacidad:"))
        self.op_slider = QSlider(Qt.Horizontal)
        self.op_slider.setRange(50, 100)
        self.op_slider.setValue(int(self.config.get("opacity", 0.92) * 100))
        self.op_slider.setFixedWidth(150)
        op_layout.addWidget(self.op_slider)
        self.op_label = QLabel(f"{self.op_slider.value()}%")
        op_layout.addWidget(self.op_label)
        self.op_slider.valueChanged.connect(lambda v: self.op_label.setText(f"{v}%"))
        op_layout.addStretch()
        layout.addLayout(op_layout)

        # Siempre encima
        self.top_check = QCheckBox("Siempre encima")
        self.top_check.setChecked(self.config.get("always_on_top", True))
        self.top_check.setStyleSheet("color: #aaaaaa;")
        layout.addWidget(self.top_check)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton("Guardar")
        save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(save_btn)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def save_settings(self):
        self.config.set("window_width", self.width_spin.value())
        self.config.set("window_height", self.height_spin.value())
        self.config.set("opacity", self.op_slider.value() / 100.0)
        self.config.set("always_on_top", self.top_check.isChecked())
        self.accept()

# ============================================================================
# APLICACIÓN PRINCIPAL
# ============================================================================

class JarvisApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.panel = JarvisPanel()
        self.panel.show()

    def run(self):
        return self.app.exec_()

if __name__ == "__main__":
    try:
        import psutil
    except ImportError:
        print("Error: psutil no instalado. Ejecuta: pip install psutil PyQt5")
        sys.exit(1)
    app = JarvisApp()
    sys.exit(app.run())