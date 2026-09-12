#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JARVIS CIRCULAR PANEL - v12.1 (Distribución corregida)
- Eliminados los núcleos CPU.
- Botones de chat y micrófono reposicionados al centro inferior.
- Botones minimizar/cerrar centrados en la barra superior.
- Chat muestra respuestas en texto automáticamente.
- Incluye opciones de apagado/reinicio.
"""

import sys
import os
import json
import time
import webbrowser
import math
import random
from datetime import datetime
import psutil
import subprocess
import urllib.request
import urllib.parse

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSystemTrayIcon, QMenu,
    QFrame, QProgressBar, QDialog, QTextEdit,
    QMessageBox, QGroupBox, QCheckBox, QSpinBox,
    QScrollArea, QSlider, QGridLayout, QLineEdit,
    QListWidget, QListWidgetItem, QCalendarWidget,
    QInputDialog, QDialogButtonBox,
)
from PyQt6.QtGui import (
    QAction, QPainter, QBrush, QPen, QColor, QFont,
    QPixmap, QIcon, QRadialGradient, QPainterPath,
    QLinearGradient, QRegion,
)
from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QRect, QVariantAnimation,
    QEasingCurve, QRectF, QPropertyAnimation, QPointF,
)

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

CONFIG_PATH = os.path.expanduser("~/.jarvis_circular_config.json")
DEFAULT_CONFIG = {
    "window_size": 880,
    "opacity": 0.92,
    "always_on_top": True,
    "x": None,
    "y": None,
    "volume_step": 5,
    "weather_city": "Lima, Peru",
    "brightness_step": 10,
    "battery_alert_threshold": 20,
    "cpu_alert_threshold": 90,
    "light_mode": False,
    "custom_shortcuts": [],
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

        if self.config.get("weather_city", "") == "Madrid":
            self.config["weather_city"] = "Lima, Peru"
            self.save()
        for key, val in DEFAULT_CONFIG.items():
            if key not in self.config:
                self.config[key] = val
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
# VENTANA DE CHAT EMERGENTE
# ============================================================================

class ChatDialog(QDialog):
    def __init__(self, parent=None, on_send_callback=None):
        super().__init__(parent)
        self.on_send_callback = on_send_callback
        self.setWindowTitle("💬 Chat con AP0LO")
        self.setFixedSize(450, 500)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                color: #ffffff;
                border: 1px solid #00FFCC;
                border-radius: 12px;
            }
            QTextEdit {
                background-color: #0a0a1a;
                border: 1px solid rgba(0, 255, 204, 40);
                border-radius: 8px;
                color: #ffffff;
                font-size: 13px;
                padding: 6px;
            }
            QLineEdit {
                background-color: #0a0a1a;
                border: 1px solid rgba(0, 255, 204, 40);
                border-radius: 20px;
                color: #ffffff;
                font-size: 13px;
                padding: 8px 14px;
            }
            QLineEdit:focus {
                border: 1px solid #00FFCC;
            }
            QPushButton {
                background-color: #00FFCC;
                color: #1a1a2e;
                border: none;
                border-radius: 18px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #33FFDD;
            }
            QPushButton#voice {
                background-color: rgba(255, 50, 50, 40);
                color: #FF6666;
                border: 2px solid #FF6666;
                border-radius: 18px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton#voice:checked {
                background-color: rgba(255, 50, 50, 180);
                color: #FFFFFF;
                border: 2px solid #FF0000;
                border-radius: 18px;
                padding: 8px 16px;
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("Inicia la conversación...")
        layout.addWidget(self.chat_history)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Escribe un mensaje...")
        self.input_field.returnPressed.connect(self.send_message)
        controls.addWidget(self.input_field)

        self.send_btn = QPushButton("➤ Enviar")
        self.send_btn.clicked.connect(self.send_message)
        controls.addWidget(self.send_btn)

        self.voice_btn = QPushButton("🎤")
        self.voice_btn.setObjectName("voice")
        self.voice_btn.setFixedSize(40, 40)
        self.voice_btn.setCheckable(True)
        self.voice_btn.clicked.connect(self.toggle_voice)
        controls.addWidget(self.voice_btn)

        layout.addLayout(controls)

    def send_message(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self.add_message("Tú", text)
        if self.on_send_callback:
            self.on_send_callback(text)

    def toggle_voice(self):
        if self.on_send_callback:
            self.on_send_callback("[TOGGLE_MIC]")

    def add_message(self, sender, message):
        if sender.lower() == "tú":
            color = "#88CCFF"
            prefix = "👤 "
        elif sender.lower() == "ap0lo" or sender.lower() == "ia":
            color = "#00FFCC"
            prefix = "🤖 "
        else:
            color = "#FFFFFF"
            prefix = ""

        html = f'<p><span style="color:{color}; font-weight:bold;">{prefix}{sender}:</span> {message}</p>'
        self.chat_history.append(html)
        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.chat_history.setTextCursor(cursor)

    def display_response(self, message, sender="AP0LO"):
        self.add_message(sender, message)

    def set_voice_state(self, recording):
        self.voice_btn.setChecked(recording)
        if recording:
            self.voice_btn.setStyleSheet("""
                QPushButton#voice {
                    background-color: rgba(255, 50, 50, 180);
                    color: #FFFFFF;
                    border: 2px solid #FF0000;
                    border-radius: 18px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
            """)
            self.voice_btn.setText("⏹")
        else:
            self.voice_btn.setStyleSheet("""
                QPushButton#voice {
                    background-color: rgba(255, 50, 50, 40);
                    color: #FF6666;
                    border: 2px solid #FF6666;
                    border-radius: 18px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
            """)
            self.voice_btn.setText("🎤")

# ============================================================================
# MEDIDOR RADIAL COMPACTO
# ============================================================================

class CompactRadialGauge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._label = ""
        self._color = QColor(0, 255, 204)
        self._bg_color = QColor(20, 20, 30, 180)
        self.setMinimumSize(55, 55)

    def setValue(self, value):
        self._value = int(value)
        self.update()

    def setLabel(self, label):
        self._label = label
        self.update()

    def setColor(self, color):
        self._color = QColor(color) if isinstance(color, str) else color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        center = rect.center()
        radius = min(rect.width(), rect.height()) / 2 - 4

        painter.setBrush(QBrush(self._bg_color))
        painter.setPen(QPen(QColor(60, 60, 70, 80), 1))
        painter.drawEllipse(QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2))

        painter.setPen(QPen(QColor(60, 60, 70, 60), 1))
        start_angle = 180 * 16
        span_angle = 180 * 16
        painter.drawArc(
            int(center.x() - radius), int(center.y() - radius),
            int(radius * 2), int(radius * 2),
            start_angle, span_angle
        )

        normalized = self._value / 100.0
        painter.setPen(QPen(self._color, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(
            int(center.x() - radius), int(center.y() - radius),
            int(radius * 2), int(radius * 2),
            start_angle, int(-normalized * 180 * 16)
        )

        painter.setPen(QPen(QColor(255, 255, 255)))
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            int(center.x() - 18), int(center.y() - 4),
            36, 16, Qt.AlignmentFlag.AlignCenter, f"{self._value}"
        )

        painter.setPen(QPen(QColor(150, 150, 170)))
        font.setPointSize(6)
        painter.setFont(font)
        painter.drawText(
            int(center.x() - 18), int(center.y() + 12),
            36, 12, Qt.AlignmentFlag.AlignCenter, self._label
        )

# ============================================================================
# DIÁLOGO DE NOTAS RÁPIDAS (con To-Do)
# ============================================================================

class NotesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📝 Notas y Tareas")
        self.setFixedSize(450, 500)
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
            QLineEdit {
                background-color: #0a0a1a;
                border: 1px solid #00FFCC;
                border-radius: 8px;
                color: #ffffff;
                font-size: 12px;
                padding: 4px;
            }
            QListWidget {
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

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                background-color: #1a1a2e;
                border: none;
            }
            QTabBar::tab {
                background-color: #2a2a3e;
                color: #aaaaaa;
                padding: 6px 12px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: #0a0a1a;
                color: #00FFCC;
            }
        """)

        notes_widget = QWidget()
        notes_layout = QVBoxLayout(notes_widget)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Escribe tus notas aquí...")
        notes_layout.addWidget(self.text_edit)
        self.tabs.addTab(notes_widget, "📝 Notas")

        todo_widget = QWidget()
        todo_layout = QVBoxLayout(todo_widget)
        self.task_list = QListWidget()
        todo_layout.addWidget(self.task_list)
        task_input = QHBoxLayout()
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Nueva tarea...")
        task_input.addWidget(self.task_input)
        add_task_btn = QPushButton("➕")
        add_task_btn.setFixedWidth(40)
        add_task_btn.clicked.connect(self.add_task)
        task_input.addWidget(add_task_btn)
        todo_layout.addLayout(task_input)
        remove_task_btn = QPushButton("🗑️ Eliminar seleccionada")
        remove_task_btn.clicked.connect(self.remove_task)
        todo_layout.addWidget(remove_task_btn)
        self.tabs.addTab(todo_widget, "✅ Tareas")

        layout.addWidget(self.tabs)

        btn_layout = QHBoxLayout()
        btn_save = QPushButton("💾 Guardar")
        btn_save.clicked.connect(self.save_notes)
        btn_layout.addWidget(btn_save)
        btn_layout.addStretch()
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        self.load_notes()
        self.load_tasks()

    def add_task(self):
        text = self.task_input.text().strip()
        if text:
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.task_list.addItem(item)
            self.task_input.clear()

    def remove_task(self):
        row = self.task_list.currentRow()
        if row >= 0:
            self.task_list.takeItem(row)

    def load_notes(self):
        notes_file = os.path.expanduser("~/notes.txt")
        if os.path.exists(notes_file):
            try:
                with open(notes_file, 'r', encoding='utf-8') as f:
                    self.text_edit.setText(f.read())
            except:
                pass

    def save_notes(self):
        notes_file = os.path.expanduser("~/notes.txt")
        try:
            with open(notes_file, 'w', encoding='utf-8') as f:
                f.write(self.text_edit.toPlainText())
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar: {e}")
        self.save_tasks()
        QMessageBox.information(self, "Éxito", "Notas y tareas guardadas correctamente.")

    def save_tasks(self):
        tasks = []
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            tasks.append({"text": item.text(), "done": item.checkState() == Qt.CheckState.Checked})
        tasks_file = os.path.expanduser("~/tasks.json")
        try:
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, indent=2)
        except Exception as e:
            print(f"Error guardando tareas: {e}")

    def load_tasks(self):
        tasks_file = os.path.expanduser("~/tasks.json")
        if os.path.exists(tasks_file):
            try:
                with open(tasks_file, 'r', encoding='utf-8') as f:
                    tasks = json.load(f)
                for task in tasks:
                    item = QListWidgetItem(task.get("text", ""))
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(Qt.CheckState.Checked if task.get("done", False) else Qt.CheckState.Unchecked)
                    self.task_list.addItem(item)
            except:
                pass

# ============================================================================
# DIÁLOGO DE CALENDARIO
# ============================================================================

class CalendarDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📅 Calendario")
        self.setFixedSize(400, 350)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                color: #ffffff;
            }
            QCalendarWidget {
                background-color: #0a0a1a;
                color: #ffffff;
                border: 1px solid #00FFCC;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(self)
        self.calendar = QCalendarWidget()
        layout.addWidget(self.calendar)

# ============================================================================
# DIÁLOGO DE CONFIGURACIÓN
# ============================================================================

class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("⚙️ Configuración")
        self.setFixedSize(500, 600)
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
            QLineEdit {
                background-color: #2a2a3e;
                border: 1px solid #333355;
                border-radius: 4px;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self)

        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Tamaño:"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(700, 950)
        self.size_spin.setValue(self.config.get("window_size", 880))
        size_layout.addWidget(self.size_spin)
        size_layout.addStretch()
        layout.addLayout(size_layout)

        op_layout = QHBoxLayout()
        op_layout.addWidget(QLabel("Opacidad:"))
        self.op_slider = QSlider(Qt.Orientation.Horizontal)
        self.op_slider.setRange(50, 100)
        self.op_slider.setValue(int(self.config.get("opacity", 0.92) * 100))
        self.op_slider.setFixedWidth(150)
        op_layout.addWidget(self.op_slider)
        self.op_label = QLabel(f"{self.op_slider.value()}%")
        op_layout.addWidget(self.op_label)
        self.op_slider.valueChanged.connect(lambda v: self.op_label.setText(f"{v}%"))
        op_layout.addStretch()
        layout.addLayout(op_layout)

        self.top_check = QCheckBox("Siempre encima")
        self.top_check.setChecked(self.config.get("always_on_top", True))
        self.top_check.setStyleSheet("color: #aaaaaa;")
        layout.addWidget(self.top_check)

        city_layout = QHBoxLayout()
        city_layout.addWidget(QLabel("Ciudad (clima):"))
        self.city_input = QLineEdit(self.config.get("weather_city", "Lima, Peru"))
        city_layout.addWidget(self.city_input)
        layout.addLayout(city_layout)

        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("Paso volumen (%):"))
        self.vol_spin = QSpinBox()
        self.vol_spin.setRange(1, 20)
        self.vol_spin.setValue(self.config.get("volume_step", 5))
        vol_layout.addWidget(self.vol_spin)
        vol_layout.addStretch()
        layout.addLayout(vol_layout)

        bright_layout = QHBoxLayout()
        bright_layout.addWidget(QLabel("Paso brillo (%):"))
        self.bright_spin = QSpinBox()
        self.bright_spin.setRange(5, 50)
        self.bright_spin.setValue(self.config.get("brightness_step", 10))
        bright_layout.addWidget(self.bright_spin)
        bright_layout.addStretch()
        layout.addLayout(bright_layout)

        bat_layout = QHBoxLayout()
        bat_layout.addWidget(QLabel("Alerta batería (%):"))
        self.bat_spin = QSpinBox()
        self.bat_spin.setRange(5, 50)
        self.bat_spin.setValue(self.config.get("battery_alert_threshold", 20))
        bat_layout.addWidget(self.bat_spin)
        bat_layout.addStretch()
        layout.addLayout(bat_layout)

        cpu_layout = QHBoxLayout()
        cpu_layout.addWidget(QLabel("Alerta CPU (%):"))
        self.cpu_spin = QSpinBox()
        self.cpu_spin.setRange(50, 100)
        self.cpu_spin.setValue(self.config.get("cpu_alert_threshold", 90))
        cpu_layout.addWidget(self.cpu_spin)
        cpu_layout.addStretch()
        layout.addLayout(cpu_layout)

        # Atajos personalizados
        self.shortcut_widgets = []
        for i in range(4):
            group = QGroupBox(f"Atajo {i+1}")
            group.setStyleSheet("""
                QGroupBox {
                    background-color: #2a2a3e;
                    color: #aaaaaa;
                    border: 1px solid #333355;
                    border-radius: 4px;
                    margin-top: 6px;
                    padding-top: 10px;
                }
            """)
            hbox = QHBoxLayout(group)
            name_edit = QLineEdit()
            name_edit.setPlaceholderText("Nombre")
            cmd_edit = QLineEdit()
            cmd_edit.setPlaceholderText("Comando")
            shortcuts = self.config.get("custom_shortcuts", [])
            if i < len(shortcuts):
                name_edit.setText(shortcuts[i].get("name", ""))
                cmd_edit.setText(shortcuts[i].get("command", ""))
            hbox.addWidget(name_edit)
            hbox.addWidget(cmd_edit)
            layout.addWidget(group)
            self.shortcut_widgets.append((name_edit, cmd_edit))

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
        self.config.set("window_size", self.size_spin.value())
        self.config.set("opacity", self.op_slider.value() / 100.0)
        self.config.set("always_on_top", self.top_check.isChecked())
        self.config.set("weather_city", self.city_input.text().strip() or "Lima, Peru")
        self.config.set("volume_step", self.vol_spin.value())
        self.config.set("brightness_step", self.bright_spin.value())
        self.config.set("battery_alert_threshold", self.bat_spin.value())
        self.config.set("cpu_alert_threshold", self.cpu_spin.value())

        shortcuts = []
        for name_edit, cmd_edit in self.shortcut_widgets:
            name = name_edit.text().strip()
            cmd = cmd_edit.text().strip()
            if name and cmd:
                shortcuts.append({"name": name, "command": cmd})
        self.config.set("custom_shortcuts", shortcuts)
        self.accept()

# ============================================================================
# PANEL CIRCULAR CON DISEÑO GALAXIA
# ============================================================================

class JarvisCircularPanel(QWidget):
    def __init__(self, parent=None, on_command_callback=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.drag_pos = None
        self.start_time = time.time()
        self.cpu_cores = psutil.cpu_count(logical=True)
        self.rotation_angle = 0
        self.is_collapsed = False
        self.on_command_callback = on_command_callback
        self.chat_dialog = None
        self.on_close_callback = None
        self.light_mode = self.config.get("light_mode", False)
        self.battery_alert_shown = False
        self.cpu_alert_shown = False

        self.last_net = psutil.net_io_counters()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        size = self.config.get("window_size", 880)
        self.setFixedSize(size, size)
        self.setWindowOpacity(self.config.get("opacity", 0.92))
        self.setMask(QRegion(0, 0, size, size, QRegion.RegionType.Ellipse))

        x = self.config.get("x")
        y = self.config.get("y")
        if x is not None and y is not None:
            self.move(x, y)

        self.central = QWidget(self)
        self.central.setGeometry(0, 0, size, size)
        self.central.setStyleSheet("background-color: transparent;")

        center_x, center_y = size // 2, size // 2
        self.center_x, self.center_y = center_x, center_y
        self.radius = size // 2 - 25

        self.star_data = []
        self._precompute_stars()

        # ========== BARRA DE TÍTULO (más estrecha y centrada) ==========
        self.title_bar = QFrame(self.central)
        self.title_bar.setGeometry(center_x - 150, center_y - 250, 300, 44)
        self.title_bar.setStyleSheet("""
            QFrame {
                background-color: rgba(0,0,0,0.6);
                border-radius: 12px;
                border: 1px solid rgba(0, 255, 204, 40);
            }
        """)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(12, 0, 12, 0)
        title_layout.setSpacing(6)

        self.btn_collapse = QPushButton("⤵")
        self.btn_collapse.setFixedSize(32, 32)
        self.btn_collapse.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 255, 204, 20);
                color: #00FFCC;
                border: 1px solid #00FFCC;
                border-radius: 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(0, 255, 204, 40);
            }
        """)
        self.btn_collapse.clicked.connect(self.toggle_collapse)
        title_layout.addWidget(self.btn_collapse, 0, Qt.AlignmentFlag.AlignLeft)

        self.title_label = QLabel("✦SISTEMA")
        self.title_label.setStyleSheet("""
            color: #00FFCC;
            font-size: 18px;
            font-weight: bold;
            font-family: 'Segoe UI', 'Courier New', monospace;
            background-color: transparent;
        """)
        title_layout.addWidget(self.title_label, 1, Qt.AlignmentFlag.AlignCenter)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(32, 32)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 50, 50, 20);
                color: #FF6666;
                border: 1px solid #FF6666;
                border-radius: 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 50, 50, 40);
            }
        """)
        self.btn_close.clicked.connect(self.close_app)
        title_layout.addWidget(self.btn_close, 0, Qt.AlignmentFlag.AlignRight)

        # ========== ELEMENTOS CENTRALES ==========
        self.user_label = QLabel(f"User: {os.getlogin()}", self.central)
        self.user_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.user_label.setStyleSheet("color: #88CCFF; font-size: 12px; background-color: rgba(0,0,0,0.3); border-radius: 8px; padding: 2px 12px;")
        self.user_label.setGeometry(center_x - 80, center_y - 190, 160, 24)

        self.time_label = QLabel(datetime.now().strftime("%H:%M:%S"), self.central)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet("color: #FFFFFF; font-size: 22px; font-weight: bold; background-color: rgba(0,0,0,0.3); border-radius: 8px; padding: 2px 12px;")
        self.time_label.setGeometry(center_x - 90, center_y - 150, 180, 32)

        self.date_label = QLabel(datetime.now().strftime("%d %B %Y"), self.central)
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.date_label.setStyleSheet("color: #88CCFF; font-size: 13px; background-color: rgba(0,0,0,0.2); border-radius: 6px; padding: 2px 12px;")
        self.date_label.setGeometry(center_x - 100, center_y - 116, 200, 24)

        # ========== MEDIDORES ==========
        gauge_size = 65
        spacing = 95
        offset_y_medidores = 20
        gauges = [
            (-spacing, "CPU", "#00FFCC", offset_y_medidores),
            (0, "RAM", "#4FC3F7", offset_y_medidores + 10),
            (spacing, "SWAP", "#FFD54F", offset_y_medidores),
        ]

        self.cpu_gauge = CompactRadialGauge(self.central)
        self.cpu_gauge.setLabel("CPU")
        self.cpu_gauge.setColor("#00FFCC")
        self.cpu_gauge.setGeometry(
            center_x + gauges[0][0] - gauge_size//2,
            center_y - 32 - gauge_size//2 + gauges[0][3],
            gauge_size, gauge_size
        )

        self.ram_gauge = CompactRadialGauge(self.central)
        self.ram_gauge.setLabel("RAM")
        self.ram_gauge.setColor("#4FC3F7")
        self.ram_gauge.setGeometry(
            center_x + gauges[1][0] - gauge_size//2,
            center_y - 32 - gauge_size//2 + gauges[1][3],
            gauge_size, gauge_size
        )

        self.swap_gauge = CompactRadialGauge(self.central)
        self.swap_gauge.setLabel("SWAP")
        self.swap_gauge.setColor("#FFD54F")
        self.swap_gauge.setGeometry(
            center_x + gauges[2][0] - gauge_size//2,
            center_y - 32 - gauge_size//2 + gauges[2][3],
            gauge_size, gauge_size
        )

        # ========== UPTIME ==========
        self.uptime_label = QLabel("Uptime: 0h 0m", self.central)
        self.uptime_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.uptime_label.setStyleSheet("color: #6688AA; font-size: 12px; background-color: rgba(0,0,0,0.2); border-radius: 6px; padding: 2px 12px;")
        self.uptime_label.setGeometry(center_x - 80, center_y + 22, 160, 24)

        # ========== ETIQUETAS DE BATERÍA Y GPU ==========
        net_y = center_y + 90  # Posición central inferior (sin núcleos)
        self.battery_label = QLabel("🔋 N/A", self.central)
        self.battery_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.battery_label.setStyleSheet("color: #88CCFF; font-size: 12px; background-color: rgba(0,0,0,0.3); border-radius: 6px; padding: 2px 12px;")
        self.battery_label.setGeometry(center_x - 180, net_y, 100, 24)

        self.gpu_label = QLabel("🌡 GPU: N/A", self.central)
        self.gpu_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gpu_label.setStyleSheet("color: #88CCFF; font-size: 12px; background-color: rgba(0,0,0,0.3); border-radius: 6px; padding: 2px 12px;")
        self.gpu_label.setGeometry(center_x + 80, net_y, 100, 24)

        self.net_label = QLabel("⬇ 0 KB/s  ⬆ 0 KB/s", self.central)
        self.net_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.net_label.setStyleSheet("color: #88CCFF; font-size: 12px; background-color: rgba(0,0,0,0.3); border-radius: 6px; padding: 2px 12px;")
        self.net_label.setGeometry(center_x - 120, net_y + 26, 240, 24)

        # ========== BOTONES RADIALES ==========
        util_buttons = [
            ("🌐", "Web", lambda: webbrowser.open("https://google.com")),
            ("🧮", "Calculadora", self.open_calculator),
            ("⬛", "Terminal", self.open_terminal),
            ("📝", "Notas/Tareas", self.open_notes),
            ("📂", "Explorador", self.open_file_explorer),
            ("📸", "Captura", self.take_screenshot),
            ("🔒", "Bloquear", self.lock_screen),
            ("⚙️", "Config", self.open_settings),
            ("🔊", "Volumen +", self.increase_volume),
            ("🔉", "Volumen -", self.decrease_volume),
            ("🔆", "Brillo +", self.increase_brightness),
            ("🔅", "Brillo -", self.decrease_brightness),
            ("🌤", "Clima", self.show_weather),
            ("📅", "Calendario", self.show_calendar),
            ("⏮", "Anterior", self.media_prev),
            ("⏯", "Reproducir/Pausa", self.media_play_pause),
            ("⏭", "Siguiente", self.media_next),
            ("🌓", "Modo Claro/Oscuro", self.toggle_light_mode),
            ("⌨", "Teclado Retroiluminado", self.toggle_keyboard_backlight),
        ]

        self.radial_buttons = []
        outer_r = self.radius - 8
        num_btns = len(util_buttons)
        for i, (icon, tip, callback) in enumerate(util_buttons):
            angle = 2 * math.pi * i / num_btns - math.pi / 2
            x = center_x + outer_r * math.cos(angle) - 22
            y = center_y + outer_r * math.sin(angle) - 22
            btn = QPushButton(icon, self.central)
            btn.setToolTip(tip)
            btn.setFixedSize(44, 44)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(10, 10, 25, 200);
                    color: #00FFCC;
                    border: 2px solid #00FFCC;
                    border-radius: 22px;
                    font-size: 18px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 255, 204, 30);
                    border: 2px solid #FFFFFF;
                    color: #FFFFFF;
                }
            """)
            btn.clicked.connect(callback)
            btn.setGeometry(int(x), int(y), 44, 44)
            self.radial_buttons.append(btn)

        # Atajos personalizados
        self.custom_buttons = []
        shortcuts = self.config.get("custom_shortcuts", [])
        for idx, shortcut in enumerate(shortcuts[:4]):
            name = shortcut.get("name", f"Atajo {idx+1}")
            cmd = shortcut.get("command", "")
            icon = "🔗"
            btn = QPushButton(icon, self.central)
            btn.setToolTip(name)
            btn.setFixedSize(44, 44)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(10, 10, 25, 200);
                    color: #FFD700;
                    border: 2px solid #FFD700;
                    border-radius: 22px;
                    font-size: 18px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 215, 0, 30);
                    border: 2px solid #FFFFFF;
                    color: #FFFFFF;
                }
            """)
            btn.clicked.connect(lambda _, c=cmd: self.run_custom_shortcut(c))
            angle = 2 * math.pi * (num_btns + idx) / (num_btns + len(shortcuts))
            x = center_x + (outer_r - 30) * math.cos(angle) - 22
            y = center_y + (outer_r - 30) * math.sin(angle) - 22
            btn.setGeometry(int(x), int(y), 44, 44)
            self.custom_buttons.append(btn)

        # ========== BOTONES FLOTANTES: CHAT y MICRÓFONO (centrados y bajos) ==========
        btn_size = 50
        chat_y = center_y + 150  # 440 + 150 = 590 (debajo de etiquetas de red)
        self.chat_btn = QPushButton("💬", self.central)
        self.chat_btn.setToolTip("Abrir chat con IA")
        self.chat_btn.setFixedSize(btn_size, btn_size)
        self.chat_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 200, 255, 100);
                color: white;
                border: 2px solid #00FFCC;
                border-radius: 25px;
                font-size: 22px;
            }
            QPushButton:hover {
                background-color: rgba(0, 200, 255, 180);
                border: 2px solid #FFFFFF;
            }
        """)
        self.chat_btn.setGeometry(center_x - btn_size - 30, chat_y, btn_size, btn_size)
        self.chat_btn.clicked.connect(self.toggle_chat)

        self.mic_btn = QPushButton("🎤", self.central)
        self.mic_btn.setToolTip("Activar/Desactivar micrófono")
        self.mic_btn.setFixedSize(btn_size, btn_size)
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 50, 50, 40);
                color: #FF6666;
                border: 2px solid #FF6666;
                border-radius: 25px;
                font-size: 22px;
            }
            QPushButton:hover {
                background-color: rgba(255, 50, 50, 80);
                border: 2px solid #FFFFFF;
            }
        """)
        self.mic_btn.setGeometry(center_x + 30, chat_y, btn_size, btn_size)
        self.mic_btn.clicked.connect(self.toggle_mic)

        # ========== TIMERS ==========
        self.init_timers()
        self.init_tray()

        QTimer.singleShot(100, self.update_all_data)

    # ========================================================================
    # PRECALCULAR ESTRELLAS
    # ========================================================================
    def _precompute_stars(self):
        radius = self.radius
        center_x, center_y = self.center_x, self.center_y
        for _ in range(80):
            angle = random.uniform(0, 2 * math.pi)
            r = random.uniform(0.2, 0.9) * radius
            x = center_x + r * math.cos(angle)
            y = center_y + r * math.sin(angle)
            size = random.uniform(0.5, 1.8)
            alpha = random.randint(150, 255)
            self.star_data.append((x, y, size, alpha))

    # ========================================================================
    # MÉTODOS DE COMUNICACIÓN CON IA
    # ========================================================================
    def set_command_callback(self, callback):
        self.on_command_callback = callback
        if self.chat_dialog:
            self.chat_dialog.on_send_callback = callback

    def set_close_callback(self, callback):
        self.on_close_callback = callback

    def toggle_chat(self):
        if self.chat_dialog is None or not self.chat_dialog.isVisible():
            self.open_chat()
        else:
            self.chat_dialog.hide()

    def open_chat(self):
        if self.chat_dialog is None:
            self.chat_dialog = ChatDialog(self, self.on_command_callback)
            panel_geo = self.geometry()
            x = panel_geo.x() + panel_geo.width() + 10
            y = panel_geo.y()
            self.chat_dialog.move(x, y)
        self.chat_dialog.show()
        self.chat_dialog.raise_()
        self.chat_dialog.activateWindow()

    def toggle_mic(self):
        if self.on_command_callback:
            self.on_command_callback("[TOGGLE_MIC]")
        else:
            self.net_label.setText("⚠️ Sin callback para micrófono")

    def set_mic_state(self, recording):
        if recording:
            self.mic_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 50, 50, 180);
                    color: #FFFFFF;
                    border: 2px solid #FF0000;
                    border-radius: 25px;
                    font-size: 22px;
                }
            """)
            self.mic_btn.setText("⏹")
        else:
            self.mic_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 50, 50, 40);
                    color: #FF6666;
                    border: 2px solid #FF6666;
                    border-radius: 25px;
                    font-size: 22px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 50, 50, 80);
                    border: 2px solid #FFFFFF;
                }
            """)
            self.mic_btn.setText("🎤")
        if self.chat_dialog and self.chat_dialog.isVisible():
            self.chat_dialog.set_voice_state(recording)

    def display_response(self, message, sender="AP0LO"):
        """Muestra la respuesta en el chat dialog, abriéndolo si es necesario."""
        if self.chat_dialog is None:
            self.chat_dialog = ChatDialog(self, self.on_command_callback)
            panel_geo = self.geometry()
            x = panel_geo.x() + panel_geo.width() + 10
            y = panel_geo.y()
            self.chat_dialog.move(x, y)
        if not self.chat_dialog.isVisible():
            self.chat_dialog.show()
            self.chat_dialog.raise_()
            self.chat_dialog.activateWindow()
        self.chat_dialog.display_response(message, sender)

    def set_theme_color(self, color):
        style = f"""
            QPushButton {{
                background-color: rgba({QColor(color).red()}, {QColor(color).green()}, {QColor(color).blue()}, 100);
                color: white;
                border: 2px solid {color};
                border-radius: 25px;
                font-size: 22px;
            }}
            QPushButton:hover {{
                background-color: rgba({QColor(color).red()}, {QColor(color).green()}, {QColor(color).blue()}, 180);
                border: 2px solid #FFFFFF;
            }}
        """
        self.chat_btn.setStyleSheet(style)
        self.update()

    # ========================================================================
    # CONTROL DE VOLUMEN
    # ========================================================================
    def increase_volume(self):
        self._change_volume(+abs(self.config.get("volume_step", 5)))

    def decrease_volume(self):
        self._change_volume(-abs(self.config.get("volume_step", 5)))

    def _change_volume(self, delta):
        try:
            if sys.platform == "win32":
                import ctypes
                VK_VOLUME_UP = 0xAF
                VK_VOLUME_DOWN = 0xAE
                vk = VK_VOLUME_UP if delta > 0 else VK_VOLUME_DOWN
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                ctypes.windll.user32.keybd_event(vk, 0, 0x0002, 0)
            elif sys.platform == "linux":
                cmd = "pactl set-sink-volume @DEFAULT_SINK@ "
                if delta > 0:
                    cmd += f"+{delta}%"
                else:
                    cmd += f"{delta}%"
                subprocess.run(cmd, shell=True, check=False)
            elif sys.platform == "darwin":
                sign = "+" if delta > 0 else "-"
                subprocess.run(["osascript", "-e", f"set volume output volume (output volume of (get volume settings) {sign} {abs(delta)})"], check=False)
            self.net_label.setText(f"🔊 Volumen {'+' if delta > 0 else '-'}{abs(delta)}%")
        except Exception as e:
            self.net_label.setText(f"❌ Error volumen: {e}")

    # ========================================================================
    # CONTROL DE BRILLO DE PANTALLA
    # ========================================================================
    def increase_brightness(self):
        self._change_brightness(+abs(self.config.get("brightness_step", 10)))

    def decrease_brightness(self):
        self._change_brightness(-abs(self.config.get("brightness_step", 10)))

    def _change_brightness(self, delta):
        try:
            if sys.platform == "win32":
                ps_cmd = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{max(0, min(100, 50 + delta))})"
                subprocess.run(["powershell", "-Command", ps_cmd], check=False)
            elif sys.platform == "linux":
                if delta > 0:
                    subprocess.run(["brightnessctl", "s", f"+{delta}%"], check=False)
                else:
                    subprocess.run(["brightnessctl", "s", f"{delta}%"], check=False)
                subprocess.run(["xrandr", "--output", "eDP-1", "--brightness", str(max(0.2, min(1.5, 1.0 + delta/100.0)))], check=False)
            elif sys.platform == "darwin":
                subprocess.run(["osascript", "-e", f"tell application \"System Events\" to key code 144"], check=False)
            self.net_label.setText(f"🔆 Brillo {'+' if delta > 0 else '-'}{abs(delta)}%")
        except Exception as e:
            self.net_label.setText(f"❌ Error brillo: {e}")

    # ========================================================================
    # CONTROL MULTIMEDIA
    # ========================================================================
    def media_prev(self):
        self._send_media_key(0xB1)

    def media_play_pause(self):
        self._send_media_key(0xB3)

    def media_next(self):
        self._send_media_key(0xB0)

    def _send_media_key(self, vk):
        try:
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                ctypes.windll.user32.keybd_event(vk, 0, 0x0002, 0)
            else:
                subprocess.run(["xdotool", "key", "XF86AudioPrev"], check=False)
        except Exception as e:
            print(f"Error multimedia: {e}")

    # ========================================================================
    # MODO CLARO/OSCURO
    # ========================================================================
    def toggle_light_mode(self):
        self.light_mode = not self.light_mode
        self.config.set("light_mode", self.light_mode)
        self.update()

    # ========================================================================
    # RETROILUMINACIÓN DE TECLADO (Linux)
    # ========================================================================
    def toggle_keyboard_backlight(self):
        try:
            if sys.platform == "linux":
                leds = os.listdir("/sys/class/leds")
                kbd_leds = [l for l in leds if "kbd" in l.lower() or "keyboard" in l.lower()]
                if kbd_leds:
                    led = kbd_leds[0]
                    path = f"/sys/class/leds/{led}/brightness"
                    with open(path, 'r') as f:
                        current = int(f.read().strip())
                    with open(path, 'w') as f:
                        f.write(str(0 if current > 0 else 255))
                    self.net_label.setText("⌨️ Retroiluminación cambiada")
                else:
                    self.net_label.setText("❌ No se encontró LED de teclado")
            else:
                self.net_label.setText("❌ Solo Linux soporta esto")
        except Exception as e:
            self.net_label.setText(f"❌ Error: {e}")

    # ========================================================================
    # CLIMA
    # ========================================================================
    def show_weather(self):
        city = self.config.get("weather_city", "Lima, Peru")
        encoded_city = urllib.parse.quote(city)
        url = f"https://wttr.in/{encoded_city}?format=3"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    weather = response.read().decode('utf-8').strip()
                    self.net_label.setText(f"🌤 {weather}")
                    msg = QMessageBox(self)
                    msg.setWindowTitle(f"Clima en {city}")
                    msg.setText(weather)
                    msg.setIcon(QMessageBox.Icon.Information)
                    msg.setStyleSheet("""
                        QMessageBox {
                            background-color: #0a0a1a;
                            color: #ffffff;
                        }
                        QLabel {
                            color: #ffffff;
                        }
                        QPushButton {
                            background-color: #00FFCC;
                            color: #1a1a2e;
                            border: none;
                            border-radius: 4px;
                            padding: 4px 12px;
                            font-weight: bold;
                        }
                    """)
                    msg.exec()
                else:
                    raise Exception(f"HTTP {response.status}")
        except Exception:
            webbrowser.open(f"https://wttr.in/{encoded_city}")
            self.net_label.setText(f"🌤 Abriendo clima de {city}...")

    # ========================================================================
    # CALENDARIO
    # ========================================================================
    def show_calendar(self):
        dialog = CalendarDialog(self)
        dialog.exec()

    # ========================================================================
    # ATAJOS PERSONALIZADOS
    # ========================================================================
    def run_custom_shortcut(self, command):
        try:
            subprocess.Popen(command, shell=True)
        except Exception as e:
            self.net_label.setText(f"❌ Error atajo: {e}")

    # ========================================================================
    # MONITOREO Y ACTUALIZACIÓN
    # ========================================================================
    def init_timers(self):
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_all_data)
        self.update_timer.setInterval(1000)

        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.setInterval(1000)

        self.uptime_timer = QTimer()
        self.uptime_timer.timeout.connect(self.update_uptime)
        self.uptime_timer.setInterval(60000)

        self.rotation_timer = QTimer()
        self.rotation_timer.timeout.connect(self.rotate_ring)
        self.rotation_timer.setInterval(100)

    def update_all_data(self):
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            self.cpu_gauge.setValue(cpu)
            mem = psutil.virtual_memory()
            self.ram_gauge.setValue(mem.percent)
            swap = psutil.swap_memory()
            self.swap_gauge.setValue(swap.percent)

            net = psutil.net_io_counters()
            delta_recv = max(0, net.bytes_recv - self.last_net.bytes_recv)
            delta_sent = max(0, net.bytes_sent - self.last_net.bytes_sent)
            self.last_net = net
            self.net_label.setText(
                f"⬇ {self._format_bytes(delta_recv)}/s  ⬆ {self._format_bytes(delta_sent)}/s"
            )

            battery = psutil.sensors_battery()
            if battery:
                percent = battery.percent
                charging = "⚡" if battery.power_plugged else "🔋"
                self.battery_label.setText(f"{charging} {percent}%")
                if percent <= self.config.get("battery_alert_threshold", 20) and not battery.power_plugged:
                    if not self.battery_alert_shown:
                        self.tray_icon.showMessage("Batería baja", f"Nivel de batería: {percent}%", QSystemTrayIcon.MessageIcon.Warning, 5000)
                        self.battery_alert_shown = True
                else:
                    self.battery_alert_shown = False
            else:
                self.battery_label.setText("🔋 N/A")

            try:
                import pynvml
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                self.gpu_label.setText(f"🌡 GPU: {temp}°C")
            except:
                try:
                    temps = psutil.sensors_temperatures()
                    if temps:
                        for name, entries in temps.items():
                            if entries:
                                self.gpu_label.setText(f"🌡 {name}: {entries[0].current}°C")
                                break
                    else:
                        self.gpu_label.setText("🌡 GPU: N/A")
                except:
                    self.gpu_label.setText("🌡 GPU: N/A")

            if cpu >= self.config.get("cpu_alert_threshold", 90):
                if not self.cpu_alert_shown:
                    self.tray_icon.showMessage("CPU alta", f"Uso de CPU: {cpu}%", QSystemTrayIcon.MessageIcon.Warning, 5000)
                    self.cpu_alert_shown = True
            else:
                self.cpu_alert_shown = False

        except Exception as e:
            print(f"Error en actualización: {e}")

    def _format_bytes(self, b):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if b < 1024.0:
                return f"{b:.1f}{unit}"
            b /= 1024.0
        return f"{b:.1f}TB"

    def update_clock(self):
        self.time_label.setText(datetime.now().strftime("%H:%M:%S"))
        self.date_label.setText(datetime.now().strftime("%d %B %Y"))

    def update_uptime(self):
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        self.uptime_label.setText(f"Uptime: {hours}h {minutes}m")

    def rotate_ring(self):
        self.rotation_angle = (self.rotation_angle + 1) % 360
        self.update()

    # ========================================================================
    # ACCIONES DE BOTONES DE UTILIDAD
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
        dialog.exec()

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
            self.net_label.setText(f"📸 Captura: {filename}")
            self.tray_icon.showMessage("Captura", f"Guardada como {filename}", QSystemTrayIcon.MessageIcon.Information, 3000)
        except ImportError:
            self.net_label.setText("❌ pip install pyautogui")
        except Exception as e:
            self.net_label.setText(f"❌ Error: {e}")

    def lock_screen(self):
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.LockWorkStation()
        elif sys.platform == "linux":
            os.system("xdg-screensaver lock")
        elif sys.platform == "darwin":
            os.system("pmset displaysleepnow")
        self.net_label.setText("🔒 Pantalla bloqueada")

    def open_settings(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_config()

    def apply_config(self):
        size = self.config.get("window_size", 880)
        self.setFixedSize(size, size)
        self.setMask(QRegion(0, 0, size, size, QRegion.RegionType.Ellipse))
        self.central.setGeometry(0, 0, size, size)
        self.setWindowOpacity(self.config.get("opacity", 0.92))
        if self.config.get("always_on_top", True):
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
        self.light_mode = self.config.get("light_mode", False)
        self.show()
        self._reposition_elements()

    # ========================================================================
    # COLAPSO Y VISIBILIDAD (CORREGIDO)
    # ========================================================================
    def toggle_collapse(self):
        if not self.is_collapsed:
            self._expanded_size = self.size()
            self.setFixedSize(70, 70)
            self.setMask(QRegion(0, 0, 70, 70, QRegion.RegionType.Ellipse))
            self.central.setGeometry(0, 0, 70, 70)
            for child in self.central.children():
                if child not in [self.btn_collapse, self.btn_close]:
                    child.hide()
            self.btn_collapse.move(2, 19)
            self.btn_close.move(36, 19)
            self.btn_collapse.setText("⤴")
            self.is_collapsed = True
            self.update_timer.stop()
        else:
            size = self._expanded_size.width()
            self.setFixedSize(size, size)
            self.setMask(QRegion(0, 0, size, size, QRegion.RegionType.Ellipse))
            self.central.setGeometry(0, 0, size, size)
            for child in self.central.children():
                child.show()
            self.btn_collapse.setText("⤵")
            self.is_collapsed = False
            self._restore_title_bar_layout()
            self._reposition_elements()
            self.update_timer.start()

    def _restore_title_bar_layout(self):
        layout = self.title_bar.layout()
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
        else:
            layout = QHBoxLayout(self.title_bar)

        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(6)
        layout.addWidget(self.btn_collapse, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.title_label, 1, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.btn_close, 0, Qt.AlignmentFlag.AlignRight)
        self.title_label.show()

    def _reposition_elements(self):
        center_x, center_y = self.center_x, self.center_y
        size = self.width()
        gauge_size = 65
        spacing = 95
        offset_y_medidores = 20

        self.title_bar.setGeometry(center_x - 150, center_y - 250, 300, 44)
        self._restore_title_bar_layout()

        self.user_label.setGeometry(center_x - 80, center_y - 190, 160, 24)
        self.time_label.setGeometry(center_x - 90, center_y - 150, 180, 32)
        self.date_label.setGeometry(center_x - 100, center_y - 116, 200, 24)

        gauges = [
            (-spacing, "CPU", "#00FFCC", offset_y_medidores),
            (0, "RAM", "#4FC3F7", offset_y_medidores + 10),
            (spacing, "SWAP", "#FFD54F", offset_y_medidores),
        ]
        for i, (x_offset, label, color, off_y) in enumerate(gauges):
            if i == 0:
                self.cpu_gauge.setGeometry(
                    center_x + x_offset - gauge_size//2,
                    center_y - 32 - gauge_size//2 + off_y,
                    gauge_size, gauge_size
                )
            elif i == 1:
                self.ram_gauge.setGeometry(
                    center_x + x_offset - gauge_size//2,
                    center_y - 32 - gauge_size//2 + off_y,
                    gauge_size, gauge_size
                )
            else:
                self.swap_gauge.setGeometry(
                    center_x + x_offset - gauge_size//2,
                    center_y - 32 - gauge_size//2 + off_y,
                    gauge_size, gauge_size
                )

        self.uptime_label.setGeometry(center_x - 80, center_y + 22, 160, 24)

        net_y = center_y + 90
        self.battery_label.setGeometry(center_x - 180, net_y, 100, 24)
        self.gpu_label.setGeometry(center_x + 80, net_y, 100, 24)
        self.net_label.setGeometry(center_x - 120, net_y + 26, 240, 24)

        btn_size = 50
        chat_y = center_y + 150
        self.chat_btn.setGeometry(center_x - btn_size - 30, chat_y, btn_size, btn_size)
        self.mic_btn.setGeometry(center_x + 30, chat_y, btn_size, btn_size)

        outer_r = self.radius - 8
        num_btns = len(self.radial_buttons)
        for i, btn in enumerate(self.radial_buttons):
            angle = 2 * math.pi * i / num_btns - math.pi / 2
            x = center_x + outer_r * math.cos(angle) - 22
            y = center_y + outer_r * math.sin(angle) - 22
            btn.setGeometry(int(x), int(y), 44, 44)

        shortcuts = self.config.get("custom_shortcuts", [])
        if shortcuts:
            for idx, btn in enumerate(self.custom_buttons):
                angle = 2 * math.pi * (num_btns + idx) / (num_btns + len(shortcuts))
                x = center_x + (outer_r - 30) * math.cos(angle) - 22
                y = center_y + (outer_r - 30) * math.sin(angle) - 22
                btn.setGeometry(int(x), int(y), 44, 44)

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

        shutdown_action = QAction("Apagar sistema", self)
        shutdown_action.triggered.connect(self.shutdown_system)
        tray_menu.addAction(shutdown_action)

        reboot_action = QAction("Reiniciar sistema", self)
        reboot_action.triggered.connect(self.reboot_system)
        tray_menu.addAction(reboot_action)

        tray_menu.addSeparator()
        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(lambda: self.close_app(quit_app=True))
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()

    def create_tray_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setBrush(QBrush(QColor(10, 10, 20, 240)))
        painter.setPen(QPen(QColor(0, 255, 204), 3))
        painter.drawEllipse(4, 4, 56, 56)

        grad = QRadialGradient(32, 32, 28)
        grad.setColorAt(0, QColor(0, 255, 204, 80))
        grad.setColorAt(0.8, QColor(0, 255, 204, 10))
        grad.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(4, 4, 56, 56)

        painter.setPen(QPen(QColor(0, 255, 204), 1))
        font = QFont("Arial", 28, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, 64, 64), Qt.AlignmentFlag.AlignCenter, "J")

        painter.setBrush(QBrush(QColor(0, 255, 204, 180)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(48, 48, 12, 12)

        painter.end()
        return QIcon(pixmap)

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_visibility()

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def close_app(self, quit_app=False):
        self.config.set("x", self.x())
        self.config.set("y", self.y())
        self.config.save()
        self.tray_icon.hide()
        self.hide()
        if self.on_close_callback:
            self.on_close_callback()
        if quit_app:
            QApplication.instance().quit()

    def closeEvent(self, event):
        self.close_app()
        event.accept()

    # ========================================================================
    # FUNCIONES DE APAGADO/REINICIO
    # ========================================================================
    def shutdown_system(self):
        reply = QMessageBox.question(self, "Apagar sistema", "¿Seguro que deseas apagar el sistema?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if sys.platform == "win32":
                    os.system("shutdown /s /t 5")
                elif sys.platform == "linux":
                    os.system("systemctl poweroff")
                elif sys.platform == "darwin":
                    os.system("osascript -e 'tell app \"System Events\" to shut down'")
            except Exception as e:
                print(f"Error apagando: {e}")

    def reboot_system(self):
        reply = QMessageBox.question(self, "Reiniciar sistema", "¿Seguro que deseas reiniciar el sistema?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if sys.platform == "win32":
                    os.system("shutdown /r /t 5")
                elif sys.platform == "linux":
                    os.system("systemctl reboot")
                elif sys.platform == "darwin":
                    os.system("osascript -e 'tell app \"System Events\" to restart'")
            except Exception as e:
                print(f"Error reiniciando: {e}")

    # ========================================================================
    # EVENTOS DE RATÓN
    # ========================================================================
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_pos is not None:
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_collapse()

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
        shutdown_action = QAction("Apagar sistema", self)
        shutdown_action.triggered.connect(self.shutdown_system)
        menu.addAction(shutdown_action)

        reboot_action = QAction("Reiniciar sistema", self)
        reboot_action.triggered.connect(self.reboot_system)
        menu.addAction(reboot_action)

        menu.addSeparator()
        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(lambda: self.close_app(quit_app=True))
        menu.addAction(exit_action)

        menu.exec(event.globalPos())

    # ========================================================================
    # PINTADO DE LA GALAXIA (con estrellas precalculadas y modo claro)
    # ========================================================================
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        center = rect.center()
        center_f = QPointF(center.x(), center.y())
        radius = min(rect.width(), rect.height()) / 2 - 10

        if self.light_mode:
            bg_color1 = QColor(230, 230, 250, 255)
            bg_color2 = QColor(200, 210, 230, 255)
            bg_color3 = QColor(220, 220, 240, 255)
            nebula1_color = QColor(200, 180, 255, 100)
            nebula2_color = QColor(180, 220, 255, 80)
            nebula3_color = QColor(255, 200, 220, 80)
            ring_color = QColor(100, 100, 180, 60)
            arc_color = QColor(100, 100, 200, 200)
            tick_color = QColor(150, 150, 200, 40)
            core_glow_color = QColor(255, 255, 255, 120)
            border_color = QColor(150, 150, 220, 80)
        else:
            bg_color1 = QColor(10, 5, 25, 255)
            bg_color2 = QColor(2, 0, 15, 255)
            bg_color3 = QColor(0, 0, 5, 255)
            nebula1_color = QColor(30, 0, 80, 50)
            nebula2_color = QColor(0, 40, 80, 30)
            nebula3_color = QColor(80, 0, 40, 30)
            ring_color = QColor(0, 255, 204, 30)
            arc_color = QColor(0, 255, 204, 180)
            tick_color = QColor(0, 255, 204, 20)
            core_glow_color = QColor(0, 255, 204, 80)
            border_color = QColor(0, 255, 204, 60)

        bg_grad = QRadialGradient(center_f, radius)
        bg_grad.setColorAt(0.0, bg_color1)
        bg_grad.setColorAt(0.5, bg_color2)
        bg_grad.setColorAt(1.0, bg_color3)
        painter.fillRect(self.rect(), QBrush(bg_grad))

        n1_center = QPointF(center.x() - radius * 0.3, center.y() - radius * 0.2)
        n1 = QRadialGradient(n1_center, radius * 0.8)
        n1.setColorAt(0.0, nebula1_color)
        n1.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(n1))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(center_f.x() - radius, center_f.y() - radius, radius * 2, radius * 2))

        n2_center = QPointF(center.x() + radius * 0.4, center.y() + radius * 0.3)
        n2 = QRadialGradient(n2_center, radius * 0.6)
        n2.setColorAt(0.0, nebula2_color)
        n2.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(n2))
        painter.drawEllipse(QRectF(center_f.x() - radius, center_f.y() - radius, radius * 2, radius * 2))

        n3_center = QPointF(center.x() - radius * 0.1, center.y() + radius * 0.6)
        n3 = QRadialGradient(n3_center, radius * 0.5)
        n3.setColorAt(0.0, nebula3_color)
        n3.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(n3))
        painter.drawEllipse(QRectF(center_f.x() - radius, center_f.y() - radius, radius * 2, radius * 2))

        if not self.light_mode:
            for x, y, size, alpha in self.star_data:
                if (x - center.x())**2 + (y - center.y())**2 < radius**2:
                    painter.setBrush(QBrush(QColor(255, 255, 255, alpha)))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(QPointF(x, y), size, size)

        for ring_i in range(3):
            ring_radius = radius * (0.4 + ring_i * 0.15)
            alpha = 30 - ring_i * 5
            painter.setPen(QPen(ring_color, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(center_f.x() - ring_radius, center_f.y() - ring_radius,
                                       ring_radius * 2, ring_radius * 2))

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(arc_color, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        start_angle = int(self.rotation_angle * 16)
        span_angle = 60 * 16
        painter.drawArc(
            int(center.x() - radius + 4), int(center.y() - radius + 4),
            int((radius - 4) * 2), int((radius - 4) * 2),
            start_angle, span_angle
        )

        painter.setPen(QPen(QColor(arc_color.red(), arc_color.green(), arc_color.blue(), 60), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        start_angle2 = int((self.rotation_angle + 180) * 16)
        span_angle2 = 30 * 16
        painter.drawArc(
            int(center.x() - radius + 4), int(center.y() - radius + 4),
            int((radius - 4) * 2), int((radius - 4) * 2),
            start_angle2, span_angle2
        )

        painter.setPen(QPen(tick_color, 1))
        for i in range(12):
            angle = 2 * math.pi * i / 12
            x1 = center.x() + (radius - 6) * math.cos(angle)
            y1 = center.y() + (radius - 6) * math.sin(angle)
            x2 = center.x() + (radius - 30) * math.cos(angle)
            y2 = center.y() + (radius - 30) * math.sin(angle)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        core_glow = QRadialGradient(center_f, radius * 0.3)
        core_glow.setColorAt(0.0, core_glow_color)
        core_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(core_glow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(center_f.x() - radius * 0.35, center_f.y() - radius * 0.35,
                                   radius * 0.7, radius * 0.7))

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border_color, 2))
        painter.drawEllipse(QRectF(center_f.x() - radius, center_f.y() - radius, radius * 2, radius * 2))

    # ========================================================================
    # SHOW/HIDE EVENT: manejo de timers
    # ========================================================================
    def showEvent(self, event):
        self.update_timer.start()
        self.clock_timer.start()
        self.uptime_timer.start()
        self.rotation_timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.update_timer.stop()
        self.clock_timer.stop()
        self.uptime_timer.stop()
        self.rotation_timer.stop()
        super().hideEvent(event)

# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================
if __name__ == "__main__":
    try:
        import psutil
    except ImportError:
        print("Error: psutil no instalado. Ejecuta: pip install psutil PyQt6")
        sys.exit(1)
    app = QApplication(sys.argv)
    panel = JarvisCircularPanel()
    panel.show()
    sys.exit(app.exec())