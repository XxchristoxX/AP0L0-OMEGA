# src/ui/dashboard_widget.py
# -*- coding: utf-8 -*-
"""
Dashboard Widget para AP0L0 — Integrado en la UI principal.
Muestra métricas en tiempo real con diseño estilo JARVIS.
"""

import sys
import os
import time
import psutil
import threading
from pathlib import Path
from datetime import datetime

# ===== CORRECCIÓN: AÑADIR LA RUTA DEL PROYECTO AL PYTHONPATH =====
def _fix_imports():
    """Añade la raíz del proyecto al PythonPath para que funcione standalone."""
    # Obtener la ruta del directorio actual
    current_dir = Path(__file__).resolve().parent  # src/ui
    # Subir dos niveles para llegar a la raíz del proyecto
    project_root = current_dir.parent.parent  # AP0L0 OMEGA
    
    # Añadir al PythonPath si no está
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        print(f"[Dashboard] ✅ PythonPath actualizado: {project_root}")
    
    return project_root

# Ejecutar la corrección de imports
PROJECT_ROOT = _fix_imports()

# Ahora podemos importar los módulos de src
from src.ui.ui_utils import C
from src.utils.system_utils import _metrics
from src.utils.i18n import tr

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QRectF, QPointF
from PyQt6.QtGui import (
    QFont, QPainter, QColor, QBrush, QPen, QLinearGradient,
    QRadialGradient, QPainterPath, QPalette
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QGroupBox, QGridLayout, QScrollArea,
    QSizePolicy, QApplication, QMainWindow
)


# =====================================================================
# 1. MEDIDOR RADIAL (tipo JARVIS)
# =====================================================================
class RadialGauge(QWidget):
    """Medidor circular con valor y etiqueta."""
    
    def __init__(self, label="CPU", color="#00d4ff", min_val=0, max_val=100, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = QColor(color)
        self._min_val = min_val
        self._max_val = max_val
        self._value = 0
        self._target_value = 0
        self._animation_speed = 0.15
        self.setMinimumSize(80, 80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Timer para animación suave
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start(30)
    
    def setValue(self, value):
        self._target_value = max(self._min_val, min(self._max_val, value))
    
    def setColor(self, color):
        self._color = QColor(color)
        self.update()
    
    def _animate(self):
        diff = self._target_value - self._value
        if abs(diff) > 0.5:
            self._value += diff * self._animation_speed
            self.update()
        elif abs(diff) > 0.01:
            self._value = self._target_value
            self.update()
    
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        center = rect.center()
        radius = min(rect.width(), rect.height()) / 2 - 8
        
        # Fondo
        p.setBrush(QBrush(QColor(0, 8, 16, 240)))
        p.setPen(QPen(QColor(10, 40, 70), 1))
        p.drawEllipse(center, radius, radius)
        
        # Arco de fondo
        start_angle = 135 * 16
        span_angle = 270 * 16
        p.setPen(QPen(QColor(20, 50, 80, 100), 6))
        p.drawArc(
            int(center.x() - radius + 3), int(center.y() - radius + 3),
            int((radius - 3) * 2), int((radius - 3) * 2),
            start_angle, span_angle
        )
        
        # Arco de valor
        normalized = (self._value - self._min_val) / (self._max_val - self._min_val)
        value_angle = int(normalized * 270 * 16)
        
        # Color según valor
        if normalized < 0.4:
            col = QColor(0, 255, 136)      # Verde
        elif normalized < 0.7:
            col = QColor(255, 200, 0)      # Amarillo
        else:
            col = QColor(255, 50, 50)      # Rojo
        
        p.setPen(QPen(col, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(
            int(center.x() - radius + 3), int(center.y() - radius + 3),
            int((radius - 3) * 2), int((radius - 3) * 2),
            start_angle, -value_angle
        )
        
        # Valor
        p.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        p.setPen(QPen(QColor(200, 230, 255)))
        p.drawText(
            QRectF(center.x() - 30, center.y() - 12, 60, 24),
            Qt.AlignmentFlag.AlignCenter,
            f"{int(self._value)}%"
        )
        
        # Etiqueta
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(QColor(100, 150, 200)))
        p.drawText(
            QRectF(center.x() - 30, center.y() + 14, 60, 16),
            Qt.AlignmentFlag.AlignCenter,
            self._label
        )


# =====================================================================
# 2. PANEL DE BADGES
# =====================================================================
class BadgePanel(QWidget):
    """Panel con insignias de estado."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._badges = [
            {"text": "AI CORE ACTIVE", "color": "#00ff88"},
            {"text": "SEC CLEARED", "color": "#00d4ff"},
            {"text": "PROTOCOL C", "color": "#5ab8cc"},
            {"text": "READY", "color": "#ffcc00"},
            {"text": "ONLINE", "color": "#ff6b00"},
        ]
        self.setLayout(self._build_layout())
    
    def _build_layout(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        for badge in self._badges:
            lbl = QLabel(badge["text"])
            lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {badge['color']}; "
                f"background: rgba(0, 10, 20, 0.6); "
                f"border: 1px solid {badge['color']}; "
                f"border-radius: 3px; padding: 4px;"
            )
            layout.addWidget(lbl)
        
        layout.addStretch()
        return layout


# =====================================================================
# 3. WIDGET DE CLIMA
# =====================================================================
class WeatherWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self._temp = 22
        self._condition = "Nublado"
        self._location = "Chorrillos, Lima"
        
        # Timer para actualizar (cada 10 minutos)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_weather)
        self._timer.start(600000)  # 10 minutos
        self._update_weather()
    
    def _update_weather(self):
        try:
            import requests
            resp = requests.get("https://wttr.in/Lima?format=%C+%t", timeout=5)
            if resp.status_code == 200:
                parts = resp.text.strip().split()
                if len(parts) >= 2:
                    self._condition = " ".join(parts[:-1])
                    temp_str = parts[-1].replace("+", "").replace("°C", "")
                    self._temp = int(temp_str) if temp_str.lstrip("-").isdigit() else 22
        except Exception:
            pass
        self.update()
    
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        W, H = self.width(), self.height()
        p.setBrush(QBrush(QColor(0, 8, 16, 200)))
        p.setPen(QPen(QColor(0, 40, 80), 1))
        p.drawRoundedRect(1, 1, W-2, H-2, 8, 8)
        
        # Icono (emoji)
        p.setFont(QFont("Segoe UI", 22))
        p.setPen(QPen(QColor(255, 255, 200)))
        p.drawText(QRectF(10, 10, 50, 60), Qt.AlignmentFlag.AlignCenter, "☁️")
        
        # Temperatura
        p.setFont(QFont("Courier New", 18, QFont.Weight.Bold))
        p.setPen(QPen(QColor(0, 255, 136)))
        p.drawText(QRectF(60, 10, 100, 30), Qt.AlignmentFlag.AlignLeft, f"{self._temp}°C")
        
        # Condición
        p.setFont(QFont("Courier New", 9))
        p.setPen(QPen(QColor(150, 200, 255)))
        p.drawText(QRectF(60, 38, 120, 20), Qt.AlignmentFlag.AlignLeft, self._condition)
        
        # Ubicación
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(QColor(80, 130, 180)))
        p.drawText(QRectF(60, 56, 150, 16), Qt.AlignmentFlag.AlignLeft, self._location)


# =====================================================================
# 4. WIDGET DE BATERÍA
# =====================================================================
class BatteryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self._percent = 80
        self._charging = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update)
        self._timer.start(5000)
        self._update()
    
    def _update(self):
        try:
            batt = psutil.sensors_battery()
            if batt:
                self._percent = batt.percent
                self._charging = batt.power_plugged
        except:
            pass
        self.update()
    
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        W, H = self.width(), self.height()
        p.setBrush(QBrush(QColor(0, 8, 16, 200)))
        p.setPen(QPen(QColor(0, 40, 80), 1))
        p.drawRoundedRect(1, 1, W-2, H-2, 8, 8)
        
        # Cuerpo de la batería
        rect = QRectF(20, 18, W-70, H-36)
        p.setPen(QPen(QColor(100, 180, 220), 2))
        p.setBrush(QBrush(QColor(0, 20, 40)))
        p.drawRoundedRect(rect, 4, 4)
        
        # Terminal de la batería
        term = QRectF(W-48, H//2 - 8, 12, 16)
        p.setPen(QPen(QColor(100, 180, 220), 2))
        p.drawRoundedRect(term, 2, 2)
        
        # Nivel
        fill_w = (rect.width() - 4) * (self._percent / 100)
        if fill_w > 2:
            col = QColor(0, 255, 136) if self._percent > 30 else QColor(255, 200, 0) if self._percent > 15 else QColor(255, 50, 50)
            p.setBrush(QBrush(col))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(rect.x()+2, rect.y()+2, fill_w, rect.height()-4, 3, 3)
        
        # Porcentaje
        p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        p.setPen(QPen(QColor(200, 230, 255)))
        p.drawText(
            QRectF(0, 0, W-20, H),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{self._percent}% {'C' if self._charging else 'D'}"
        )


# =====================================================================
# 5. WIDGET DE TRÁFICO DE RED
# =====================================================================
class NetworkGraphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self._sent = [0] * 30
        self._recv = [0] * 30
        self._last_net = None
        self._last_time = None
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update)
        self._timer.start(1000)
    
    def _update(self):
        try:
            net = psutil.net_io_counters()
            now = time.time()
            if self._last_net and self._last_time:
                dt = now - self._last_time
                if dt > 0:
                    sent = (net.bytes_sent - self._last_net.bytes_sent) / dt / 1024
                    recv = (net.bytes_recv - self._last_net.bytes_recv) / dt / 1024
                    self._sent.append(sent)
                    self._recv.append(recv)
                    if len(self._sent) > 30:
                        self._sent.pop(0)
                        self._recv.pop(0)
            self._last_net = net
            self._last_time = now
        except:
            pass
        self.update()
    
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        W, H = self.width(), self.height()
        p.setBrush(QBrush(QColor(0, 8, 16, 200)))
        p.setPen(QPen(QColor(0, 40, 80), 1))
        p.drawRoundedRect(1, 1, W-2, H-2, 8, 8)
        
        if len(self._sent) < 2:
            p.setPen(QPen(QColor(80, 130, 180)))
            p.setFont(QFont("Courier New", 9))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Recopilando datos...")
            return
        
        max_val = max(max(self._sent), max(self._recv), 1.0)
        step_x = (W - 20) / (len(self._sent) - 1)
        
        # Envío (verde)
        p.setPen(QPen(QColor(0, 255, 136, 180), 2))
        for i in range(1, len(self._sent)):
            x1 = 10 + (i-1) * step_x
            y1 = H - 8 - (self._sent[i-1] / max_val) * (H - 16)
            x2 = 10 + i * step_x
            y2 = H - 8 - (self._sent[i] / max_val) * (H - 16)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        
        # Recepción (azul)
        p.setPen(QPen(QColor(0, 180, 255, 180), 2))
        for i in range(1, len(self._recv)):
            x1 = 10 + (i-1) * step_x
            y1 = H - 8 - (self._recv[i-1] / max_val) * (H - 16)
            x2 = 10 + i * step_x
            y2 = H - 8 - (self._recv[i] / max_val) * (H - 16)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        
        # Etiquetas
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(QColor(100, 150, 200)))
        p.drawText(QRectF(12, 4, 80, 12), Qt.AlignmentFlag.AlignLeft, f"⬆ {int(self._sent[-1])} KB/s")
        p.drawText(QRectF(12, H-16, 80, 12), Qt.AlignmentFlag.AlignLeft, f"⬇ {int(self._recv[-1])} KB/s")


# =====================================================================
# 6. DASHBOARD PRINCIPAL (INTEGRADO)
# =====================================================================
class DashboardWidget(QWidget):
    """Panel de control principal integrado en la UI."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 500)
        self.setStyleSheet("background: rgba(0, 6, 12, 0.95); border: 1px solid #0a2a44; border-radius: 12px;")
        
        self._setup_ui()
        self._start_monitoring()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # ===== TÍTULO =====
        title = QLabel("◈ MONITOR SISTEMA")
        title.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #00d4ff; background: transparent; border-bottom: 1px solid #0a2a44; padding-bottom: 6px;")
        layout.addWidget(title)
        
        # ===== MÉTRICAS PRINCIPALES (Medidores radiales) =====
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(6)
        
        self.cpu_gauge = RadialGauge("CPU", "#00d4ff")
        metrics_layout.addWidget(self.cpu_gauge)
        
        self.ram_gauge = RadialGauge("RAM", "#00ff88")
        metrics_layout.addWidget(self.ram_gauge)
        
        self.net_gauge = RadialGauge("RED", "#ff8800")
        metrics_layout.addWidget(self.net_gauge)
        
        self.audio_gauge = RadialGauge("AUDIO", "#ff44cc")
        metrics_layout.addWidget(self.audio_gauge)
        
        self.ia_gauge = RadialGauge("IA", "#9b59b6")
        metrics_layout.addWidget(self.ia_gauge)
        
        layout.addLayout(metrics_layout)
        
        # ===== SEPARADOR =====
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #0a2a44; margin: 4px 0;")
        layout.addWidget(sep)
        
        # ===== SISTEMA (CPU, RAM, Discos) =====
        system_group = QGroupBox("SISTEMA")
        system_group.setStyleSheet("""
            QGroupBox {
                color: #00d4ff;
                border: 1px solid #0a2a44;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 8px;
                font-weight: bold;
                font-size: 9pt;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px;
                background-color: rgba(0, 6, 12, 0.95);
                color: #00d4ff;
            }
        """)
        system_layout = QVBoxLayout(system_group)
        system_layout.setSpacing(2)
        system_layout.setContentsMargins(8, 4, 8, 4)
        
        # CPU
        cpu_row = QHBoxLayout()
        cpu_row.addWidget(QLabel("CPU"))
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setStyleSheet(self._bar_style("#00d4ff"))
        cpu_row.addWidget(self.cpu_bar)
        self.cpu_label = QLabel("0%")
        self.cpu_label.setFont(QFont("Courier New", 9))
        self.cpu_label.setStyleSheet("color: #66eeff;")
        cpu_row.addWidget(self.cpu_label)
        system_layout.addLayout(cpu_row)
        
        # RAM
        ram_row = QHBoxLayout()
        ram_row.addWidget(QLabel("RAM"))
        self.ram_bar = QProgressBar()
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setStyleSheet(self._bar_style("#00ff88"))
        ram_row.addWidget(self.ram_bar)
        self.ram_label = QLabel("0.0G / 0.0G")
        self.ram_label.setFont(QFont("Courier New", 9))
        self.ram_label.setStyleSheet("color: #66eeff;")
        ram_row.addWidget(self.ram_label)
        system_layout.addLayout(ram_row)
        
        # Discos
        self.disk_bars = {}
        for drive in ['C:', 'D:', 'E:', 'F:']:
            row = QHBoxLayout()
            lbl = QLabel(drive)
            lbl.setFont(QFont("Courier New", 9))
            lbl.setStyleSheet("color: #88ccff;")
            row.addWidget(lbl)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setStyleSheet(self._bar_style("#4488cc"))
            row.addWidget(bar)
            label = QLabel("--")
            label.setFont(QFont("Courier New", 8))
            label.setStyleSheet("color: #66eeff;")
            row.addWidget(label)
            system_layout.addLayout(row)
            self.disk_bars[drive] = (bar, label)
        
        layout.addWidget(system_group)
        
        # ===== RED, WIFI, BATERÍA =====
        info_layout = QHBoxLayout()
        info_layout.setSpacing(6)
        
        # Red
        net_widget = QWidget()
        net_widget.setStyleSheet("background: rgba(0, 8, 16, 0.5); border-radius: 6px; padding: 2px;")
        net_layout = QVBoxLayout(net_widget)
        net_layout.setContentsMargins(6, 4, 6, 4)
        net_layout.setSpacing(1)
        net_layout.addWidget(QLabel("📶 TRÁFICO"))
        self.net_speed_label = QLabel("⬆ 0 KB/s  ⬇ 0 KB/s")
        self.net_speed_label.setFont(QFont("Courier New", 9))
        self.net_speed_label.setStyleSheet("color: #88ccff;")
        net_layout.addWidget(self.net_speed_label)
        self.wifi_label = QLabel("Wi-Fi 70%")
        self.wifi_label.setFont(QFont("Courier New", 9))
        self.wifi_label.setStyleSheet("color: #88ccff;")
        net_layout.addWidget(self.wifi_label)
        info_layout.addWidget(net_widget)
        
        # Batería
        batt_widget = BatteryWidget()
        info_layout.addWidget(batt_widget)
        
        # Clima
        weather_widget = WeatherWidget()
        info_layout.addWidget(weather_widget)
        
        layout.addLayout(info_layout)
        
        # ===== BADGES =====
        badge_widget = BadgePanel()
        layout.addWidget(badge_widget)
        
        # ===== CONTROLES =====
        control_group = QGroupBox("CONTROL")
        control_group.setStyleSheet("""
            QGroupBox {
                color: #00d4ff;
                border: 1px solid #0a2a44;
                border-radius: 6px;
                margin-top: 4px;
                padding-top: 6px;
                font-weight: bold;
                font-size: 9pt;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px;
                background-color: rgba(0, 6, 12, 0.95);
                color: #00d4ff;
            }
        """)
        control_layout = QHBoxLayout(control_group)
        control_layout.setSpacing(6)
        
        btn_style = """
            QPushButton {
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 8pt;
                font-family: 'Courier New', monospace;
            }
            QPushButton:hover { opacity: 0.85; }
            QPushButton:pressed { opacity: 0.70; }
        """
        
        self.shutdown_btn = QPushButton("⏻ Apagar")
        self.shutdown_btn.setStyleSheet(btn_style + "background: #d32f2f !important;")
        self.shutdown_btn.clicked.connect(self._shutdown_system)
        control_layout.addWidget(self.shutdown_btn)
        
        self.restart_btn = QPushButton("⟳ Reiniciar")
        self.restart_btn.setStyleSheet(btn_style + "background: #f57c00 !important;")
        self.restart_btn.clicked.connect(self._restart_system)
        control_layout.addWidget(self.restart_btn)
        
        self.sleep_btn = QPushButton("☾ Suspender")
        self.sleep_btn.setStyleSheet(btn_style + "background: #1976d2 !important;")
        self.sleep_btn.clicked.connect(self._suspend_system)
        control_layout.addWidget(self.sleep_btn)
        
        layout.addWidget(control_group)
        
        # ===== BOTÓN DE CERRAR =====
        close_btn = QPushButton("✕ CERRAR DASHBOARD")
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #6688aa;
                border: 1px solid #0a2a44;
                border-radius: 4px;
                padding: 4px;
                font-size: 8pt;
            }
            QPushButton:hover {
                color: #ff4466;
                border-color: #ff4466;
            }
        """)
        close_btn.clicked.connect(self.hide)
        layout.addWidget(close_btn)
    
    def _bar_style(self, color):
        return f"""
            QProgressBar {{
                background: rgba(0, 20, 40, 0.5);
                border: none;
                border-radius: 3px;
                text-align: center;
                height: 12px;
            }}
            QProgressBar::chunk {{
                background: {color};
                border-radius: 3px;
            }}
        """
    
    def _start_monitoring(self):
        """Inicia el monitoreo en segundo plano."""
        self._monitor_timer = QTimer(self)
        self._monitor_timer.timeout.connect(self._update_metrics)
        self._monitor_timer.start(1000)
        self._update_metrics()
    
    def _update_metrics(self):
        """Actualiza todas las métricas del sistema."""
        try:
            # CPU
            cpu = psutil.cpu_percent()
            self.cpu_gauge.setValue(cpu)
            self.cpu_bar.setValue(int(cpu))
            self.cpu_label.setText(f"{int(cpu)}%")
            
            # RAM
            mem = psutil.virtual_memory()
            self.ram_gauge.setValue(mem.percent)
            self.ram_bar.setValue(int(mem.percent))
            self.ram_label.setText(f"{mem.used/(1024**3):.1f}G / {mem.total/(1024**3):.1f}G")
            
            # Red (simplificado)
            net = psutil.net_io_counters()
            self.net_gauge.setValue(45)  # Placeholder
            self.net_speed_label.setText(f"⬆ {net.bytes_sent/1024:.0f} KB/s  ⬇ {net.bytes_recv/1024:.0f} KB/s")
            
            # WiFi (placeholder)
            try:
                import subprocess
                result = subprocess.run(["netsh", "wlan", "show", "interfaces"], 
                                      capture_output=True, text=True, timeout=3)
                for line in result.stdout.splitlines():
                    if "Signal" in line:
                        parts = line.split(":")
                        if len(parts) > 1:
                            signal = parts[1].strip().replace("%", "")
                            self.wifi_label.setText(f"Wi-Fi {signal}%")
                            break
            except:
                pass
            
            # Audio (placeholder)
            self.audio_gauge.setValue(82)
            
            # IA (placeholder - basado en uso de CPU)
            ia_value = min(100, cpu * 1.1 + 10)
            self.ia_gauge.setValue(ia_value)
            
            # Discos
            for drive, (bar, label) in self.disk_bars.items():
                try:
                    usage = psutil.disk_usage(drive)
                    bar.setValue(int(usage.percent))
                    label.setText(f"{usage.used/(1024**3):.1f}G")
                except:
                    bar.setValue(0)
                    label.setText("-")
            
        except Exception as e:
            print(f"[Dashboard] Error actualizando métricas: {e}")
    
    def _shutdown_system(self):
        """Apaga el sistema."""
        try:
            import subprocess
            import platform
            if platform.system() == "Windows":
                subprocess.run(["shutdown", "/s", "/t", "5"])
        except Exception as e:
            print(f"[Dashboard] Error apagando: {e}")
    
    def _restart_system(self):
        """Reinicia el sistema."""
        try:
            import subprocess
            import platform
            if platform.system() == "Windows":
                subprocess.run(["shutdown", "/r", "/t", "5"])
        except Exception as e:
            print(f"[Dashboard] Error reiniciando: {e}")
    
    def _suspend_system(self):
        """Suspende el sistema."""
        try:
            import subprocess
            import platform
            if platform.system() == "Windows":
                subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"])
        except Exception as e:
            print(f"[Dashboard] Error suspendiendo: {e}")


# =====================================================================
# 7. FUNCIÓN PARA INTEGRAR EN LA UI PRINCIPAL
# =====================================================================

def create_dashboard(parent=None):
    """Crea y devuelve el dashboard como widget flotante."""
    dashboard = DashboardWidget(parent)
    dashboard.setWindowFlags(
        Qt.WindowType.Window |
        Qt.WindowType.WindowStaysOnTopHint |
        Qt.WindowType.FramelessWindowHint
    )
    dashboard.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    return dashboard


def toggle_dashboard(main_window):
    """Alterna la visibilidad del dashboard."""
    # Obtener la ventana principal
    if hasattr(main_window, '_win'):
        main_window = main_window._win
    elif hasattr(main_window, 'parent'):
        main_window = main_window.parent()
    
    if not hasattr(main_window, '_dashboard_widget'):
        main_window._dashboard_widget = create_dashboard(main_window)
        # Posicionar a la derecha del panel circular
        if hasattr(main_window, 'panel') and main_window.panel:
            geo = main_window.panel.geometry()
            x = geo.x() + geo.width() + 20
            y = geo.y()
            main_window._dashboard_widget.move(x, y)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.width() - 420 - 20
            y = 80
            main_window._dashboard_widget.move(x, y)
    
    if main_window._dashboard_widget.isVisible():
        main_window._dashboard_widget.hide()
    else:
        main_window._dashboard_widget.show()
        main_window._dashboard_widget.raise_()
        main_window._dashboard_widget.activateWindow()


# =====================================================================
# 8. EJEMPLO DE USO (PRUEBA)
# =====================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Ventana de prueba
    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("AP0L0 Dashboard Test")
            self.setGeometry(100, 100, 800, 600)
            self.setStyleSheet("background: #000810;")
            
            # Panel circular simulado (solo para posicionar)
            self.panel = QWidget(self)
            self.panel.setGeometry(600, 100, 300, 300)
            self.panel.setStyleSheet("background: rgba(0, 255, 136, 0.1); border: 1px solid #00ff88; border-radius: 150px;")
            
            btn = QPushButton("📊 Toggle Dashboard", self)
            btn.setGeometry(300, 250, 200, 40)
            btn.setStyleSheet("""
                QPushButton {
                    background: #00d4ff;
                    color: #000;
                    border: none;
                    border-radius: 6px;
                    padding: 10px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background: #00ff88; }
            """)
            btn.clicked.connect(lambda: toggle_dashboard(self))
            
            # Crear el dashboard widget
            self._dashboard_widget = None
    
    win = TestWindow()
    win.show()
    
    sys.exit(app.exec())