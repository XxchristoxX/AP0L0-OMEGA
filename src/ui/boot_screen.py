# src/ui/boot_screen.py
# -*- coding: utf-8 -*-
"""
Pantalla de arranque (Boot Sequence) para AP0L0 — Versión Iron Man Style.
"""

import sys
import random
import math
import json
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import (
    QFont, QPainter, QColor, QBrush, QLinearGradient, QPen,
    QRadialGradient, QPainterPath, QIcon
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar, QApplication,
    QGraphicsOpacityEffect, QFrame
)


def _get_config():
    try:
        base_dir = Path(__file__).resolve().parent.parent.parent
        config_path = base_dir / "src" / "config" / "api_keys.json"
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

PERSONALITY_NAMES = {
    "jarvis": "JARVIS", "agata": "AGATA", "tony": "TONY",
    "friday": "FRIDAY", "apolo": "APOLO",
}

PERSONALITY_SUBTITLES = {
    "jarvis": "Just A Rather Very Intelligent System",
    "agata": "Advanced Generative Assistant for Technology & Art",
    "tony": "Technology Oriented Network Yield",
    "friday": "Female Replacement Intelligent Digital Assistant Youth",
    "apolo": "Autonomous Platform for Orchestration, Learning and Operations",
}

PERSONALITY_COLORS = {
    "jarvis": {"primary": "#00d4ff", "secondary": "#0066aa", "accent": "#00ff88"},
    "agata": {"primary": "#ff6b9d", "secondary": "#cc3377", "accent": "#ff99cc"},
    "tony": {"primary": "#ff6b00", "secondary": "#cc5500", "accent": "#ffaa00"},
    "friday": {"primary": "#9b59b6", "secondary": "#7d3c98", "accent": "#d77dfe"},
    "apolo": {"primary": "#00ff88", "secondary": "#00aa55", "accent": "#00d4ff"},
}

BOOT_MODULES = [
    "▶ INICIALIZANDO NÚCLEO PRINCIPAL...",
    "▶ CARGANDO MÓDULO DE VOZ...",
    "▶ CONECTANDO SENSORES AMBIENTALES...",
    "▶ VERIFICANDO INTEGRIDAD DE DATOS...",
    "▶ CARGANDO MOTORES DE IA...",
    "▶ SINCRONIZANDO RELOJ DEL SISTEMA...",
    "▶ ACTIVANDO PROTOCOLOS DE SEGURIDAD...",
    "▶ INICIANDO INTERFAZ DE USUARIO...",
    "▶ TODOS LOS SISTEMAS OPERATIVOS.",
]


class BootScreen(QWidget):
    boot_closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._is_fullscreen = True
        self.angle = 0
        self.particles = []
        self.scan_phase = 0.0
        self.glow_intensity = 0.0
        self.step = 0
        self.progress = 0
        self.pulse_value = 0.0
        self.pulse_direction = 1
        self._timer = None
        self._boot_completed = False
        self._closing = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        screen = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(screen)
        self.showFullScreen()

        self._load_personality()
        self._init_particles()
        self._setup_ui()
        self._load_window_icon()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_boot)
        self._timer.start(150)

        self.raise_()
        self.activateWindow()

    def _load_personality(self):
        try:
            cfg = _get_config()
            personality = cfg.get("personality", "apolo").lower()
            custom_name = cfg.get("assistant_name", "").strip()
            custom_subtitle = cfg.get("assistant_subtitle", "").strip()

            self.display_name = custom_name.upper() if custom_name else PERSONALITY_NAMES.get(personality, "APOLO")
            self.display_subtitle = custom_subtitle if custom_subtitle else PERSONALITY_SUBTITLES.get(personality, 
                "Autonomous Platform for Orchestration, Learning and Operations")

            colors = PERSONALITY_COLORS.get(personality, PERSONALITY_COLORS["apolo"])
            self.primary_color = colors["primary"]
            self.secondary_color = colors["secondary"]
            self.accent_color = colors["accent"]
            self.personality = personality
        except Exception:
            self.display_name = "APOLO"
            self.display_subtitle = "Autonomous Platform for Orchestration, Learning and Operations"
            self.primary_color = "#00ff88"
            self.secondary_color = "#00aa55"
            self.accent_color = "#00d4ff"
            self.personality = "apolo"

    def _load_window_icon(self):
        try:
            icon_path = Path(__file__).resolve().parent.parent.parent / "face.png"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

        logo_frame = QFrame()
        logo_frame.setStyleSheet(f"""
            QFrame {{
                border: 2px solid {self.primary_color};
                border-radius: 15px;
                background: transparent;
                padding: 20px 40px;
            }}
        """)
        logo_layout = QVBoxLayout(logo_frame)
        logo_layout.setSpacing(8)
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.logo_label = QLabel(self.display_name)
        self.logo_label.setFont(QFont("Courier New", 62, QFont.Weight.Bold))
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setStyleSheet(f"color: {self.primary_color}; background: transparent;")
        self.logo_effect = QGraphicsOpacityEffect()
        self.logo_effect.setOpacity(0.7)
        self.logo_label.setGraphicsEffect(self.logo_effect)
        logo_layout.addWidget(self.logo_label)

        self.sub_label = QLabel(self.display_subtitle)
        self.sub_label.setFont(QFont("Courier New", 11))
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setStyleSheet(f"color: {self.secondary_color}; background: transparent; letter-spacing: 2px;")
        logo_layout.addWidget(self.sub_label)

        line = QFrame()
        line.setFixedHeight(2)
        line.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 transparent, stop:0.3 {self.primary_color}, stop:0.7 {self.primary_color}, stop:1 transparent);")
        logo_layout.addWidget(line)

        layout.addWidget(logo_frame, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(20)

        self.lines = []
        for text in BOOT_MODULES:
            lbl = QLabel(f"► {text}")
            lbl.setFont(QFont("Courier New", 11))
            lbl.setStyleSheet(f"color: {self.secondary_color}; background: transparent;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
            lbl.setVisible(False)
            layout.addWidget(lbl)
            self.lines.append(lbl)

        layout.addSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(0,20,40,0.15);
                border: 1px solid {self.secondary_color};
                border-radius: 2px;
                text-align: center;
                color: {self.primary_color};
                font-family: 'Courier New';
                font-size: 9px;
                height: 4px;
                max-width: 500px;
                margin: 0 auto;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.accent_color}, stop:0.4 {self.primary_color}, stop:0.7 {self.accent_color}, stop:1 {self.primary_color});
                border-radius: 2px;
            }}
        """)
        self.progress_bar.setMaximumWidth(500)
        layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)

        self.percent_label = QLabel("0%")
        self.percent_label.setFont(QFont("Courier New", 10))
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.percent_label.setStyleSheet(f"color: {self.secondary_color}; background: transparent;")
        layout.addWidget(self.percent_label, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

    def _init_particles(self):
        self.particles = []
        w, h = self.width(), self.height()
        colors = [
            QColor(100, 200, 255), QColor(0, 212, 255),
            QColor(150, 255, 200), QColor(255, 200, 100),
            QColor(200, 150, 255),
        ]
        for _ in range(250):
            self.particles.append({
                'x': random.randint(0, w),
                'y': random.randint(0, h),
                'size': random.uniform(0.8, 3.5),
                'speed': random.uniform(0.15, 1.2),
                'alpha': random.randint(30, 200),
                'color': random.choice(colors),
                'twinkle': random.uniform(0, math.pi * 2),
                'twinkle_speed': random.uniform(0.015, 0.07),
            })

    def _update_particles(self):
        w, h = self.width(), self.height()
        for p in self.particles:
            p['y'] += p['speed'] * 0.25
            p['twinkle'] += p['twinkle_speed']
            if p['y'] > h:
                p['y'] = -10
                p['x'] = random.randint(0, w)

    def _update_boot(self):
        if self._closing or self._boot_completed:
            return

        try:
            if self.step < len(self.lines):
                self.lines[self.step].setVisible(True)
                self._fade_in_label(self.lines[self.step], self.step)
                self.step += 1

            self.progress += 3
            if self.progress > 100:
                self.progress = 100
            self.progress_bar.setValue(self.progress)
            self.percent_label.setText(f"{self.progress}%")

            self.angle = (self.angle + 2.0) % 360
            self.scan_phase = (self.scan_phase + 0.045) % (2 * math.pi)
            self.glow_intensity = 0.3 + 0.7 * math.sin(self.scan_phase * 1.1)
            self.glow_intensity = max(0.0, min(1.0, self.glow_intensity))

            self.pulse_value += 0.025 * self.pulse_direction
            if self.pulse_value > 1.0:
                self.pulse_value = 1.0
                self.pulse_direction = -1
            elif self.pulse_value < 0.25:
                self.pulse_value = 0.25
                self.pulse_direction = 1

            if hasattr(self, 'logo_effect') and self.logo_effect:
                self.logo_effect.setOpacity(0.4 + 0.6 * self.pulse_value)

            self._update_particles()
            self.update()

            if self.progress >= 100 and self.step >= len(self.lines) and not self._boot_completed:
                self._boot_completed = True
                if self._timer:
                    self._timer.stop()
                QTimer.singleShot(300, self._finish_boot)

        except Exception as e:
            print(f"[BootScreen] Error: {e}")
            if not self._boot_completed:
                self._boot_completed = True
                if self._timer:
                    self._timer.stop()
                QTimer.singleShot(300, self._finish_boot)

    def _fade_in_label(self, label, index):
        try:
            eff = QGraphicsOpacityEffect()
            eff.setOpacity(0.0)
            label.setGraphicsEffect(eff)
            is_last = (index == len(self.lines) - 1)
            color = self.primary_color if not is_last else self.accent_color

            def fade():
                try:
                    current = eff.opacity()
                    if current < 1.0:
                        eff.setOpacity(min(1.0, current + 0.12))
                        QTimer.singleShot(35, fade)
                    else:
                        label.setGraphicsEffect(None)
                        label.setStyleSheet(f"color: {color}; background: transparent; font-weight: bold;")
                except Exception:
                    pass
            QTimer.singleShot(50, fade)
        except Exception:
            pass

    def _finish_boot(self):
        if self._closing:
            return
        self._closing = True
        try:
            self.boot_closed.emit()
            self.close()
            QApplication.processEvents()
        except Exception as e:
            print(f"[BootScreen] Error closing: {e}")
        finally:
            self._closing = False

    def update_personality(self):
        try:
            self._load_personality()
            if hasattr(self, 'logo_label'):
                self.logo_label.setText(self.display_name)
                self.logo_label.setStyleSheet(f"color: {self.primary_color}; background: transparent;")
            if hasattr(self, 'sub_label'):
                self.sub_label.setText(self.display_subtitle)
                self.sub_label.setStyleSheet(f"color: {self.secondary_color}; background: transparent; letter-spacing: 2px;")
            self.update()
        except Exception:
            pass

    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            w, h = self.width(), self.height()
            cx, cy = w // 2, h // 2
            max_dim = max(w, h)

            bg_grad = QRadialGradient(cx, cy, max_dim * 0.7)
            bg_grad.setColorAt(0.0, QColor(0, 20, 40))
            bg_grad.setColorAt(0.3, QColor(0, 12, 25))
            bg_grad.setColorAt(0.7, QColor(0, 6, 14))
            bg_grad.setColorAt(1.0, QColor(0, 0, 0))
            painter.setBrush(QBrush(bg_grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.fillRect(self.rect(), bg_grad)

            # Nebulosas
            nebula_positions = [
                (cx - w * 0.3, cy - h * 0.2, w * 0.5, QColor(20, 0, 60, 20)),
                (cx + w * 0.25, cy + h * 0.15, w * 0.4, QColor(0, 40, 60, 18)),
                (cx - w * 0.1, cy + h * 0.4, w * 0.35, QColor(40, 0, 40, 15)),
                (cx + w * 0.35, cy - h * 0.35, w * 0.3, QColor(0, 20, 80, 12)),
            ]
            for nx, ny, radius, color in nebula_positions:
                grad = QRadialGradient(nx, ny, radius)
                grad.setColorAt(0.0, color)
                grad.setColorAt(1.0, QColor(0, 0, 0, 0))
                painter.setBrush(QBrush(grad))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(nx - radius, ny - radius, radius * 2, radius * 2))

            # Partículas
            for p in self.particles:
                alpha_factor = 0.4 + 0.6 * math.sin(p['twinkle'])
                alpha = int(p['alpha'] * alpha_factor)
                alpha = max(0, min(255, alpha))
                color = QColor(p['color'])
                color.setAlpha(alpha)
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(p['x'], p['y']), p['size'] * 0.6, p['size'] * 0.6)

            # Anillos giratorios
            ring_configs = [
                (max_dim * 0.22, 2.5, 75, 0, self.primary_color, 45),
                (max_dim * 0.17, 2.0, 55, 90, self.accent_color, 30),
                (max_dim * 0.12, 1.5, 40, 180, self.primary_color, 20),
                (max_dim * 0.07, 1.0, 25, 270, self.accent_color, 15),
            ]
            for radius, width, arc_span, offset, color_hex, alpha_val in ring_configs:
                color = QColor(color_hex)
                color.setAlpha(max(0, min(255, alpha_val)))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                pen = QPen(color, width)
                pen.setStyle(Qt.PenStyle.SolidLine)
                painter.setPen(pen)
                painter.drawEllipse(QPointF(cx, cy), radius, radius)

                bright_color = QColor(color_hex)
                bright_color.setAlpha(max(0, min(255, 180)))
                bright_pen = QPen(bright_color, width + 0.5)
                bright_pen.setStyle(Qt.PenStyle.SolidLine)
                painter.setPen(bright_pen)
                start_angle = int((self.angle + offset) * 16)
                span_angle = int(arc_span * 16)
                painter.drawArc(
                    int(cx - radius), int(cy - radius),
                    int(radius * 2), int(radius * 2),
                    start_angle, span_angle
                )

            # Scan line
            scan_radius = max_dim * 0.30
            painter.setBrush(Qt.BrushStyle.NoBrush)
            scan_alpha = int(40 + 60 * self.glow_intensity)
            scan_alpha = max(0, min(255, scan_alpha))
            scan_color = QColor(0, 212, 255)
            scan_color.setAlpha(scan_alpha)
            scan_pen = QPen(scan_color, 2.5)
            painter.setPen(scan_pen)
            scan_angle = int(self.angle * 16 - 25 * 16)
            painter.drawArc(
                int(cx - scan_radius), int(cy - scan_radius),
                int(scan_radius * 2), int(scan_radius * 2),
                scan_angle, 50 * 16
            )

            # Círculo central
            core_radius = max_dim * 0.055
            core_grad = QRadialGradient(cx, cy, core_radius * 2)
            glow_alpha = int(100 + 120 * self.glow_intensity)
            glow_alpha = max(0, min(255, glow_alpha))

            accent_color = QColor(self.accent_color)
            accent_color.setAlpha(glow_alpha)
            primary_color = QColor(self.primary_color)
            primary_color.setAlpha(max(0, min(255, int(glow_alpha * 0.5))))
            core_grad.setColorAt(0.0, accent_color)
            core_grad.setColorAt(0.3, primary_color)
            mid_color = QColor(0, 212, 255)
            mid_color.setAlpha(max(0, min(255, int(glow_alpha * 0.15))))
            core_grad.setColorAt(0.7, mid_color)
            core_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(core_grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx, cy), core_radius * 2, core_radius * 2)

            # Borde decorativo
            margin = 30
            rect = self.rect().adjusted(margin, margin, -margin, -margin)
            path = QPainterPath()
            corner = 25
            path.moveTo(rect.x() + corner, rect.y())
            path.lineTo(rect.right() - corner, rect.y())
            path.arcTo(rect.right() - corner, rect.y(), corner * 2, corner * 2, 90, -90)
            path.lineTo(rect.right(), rect.bottom() - corner)
            path.arcTo(rect.right() - corner, rect.bottom() - corner, corner * 2, corner * 2, 0, -90)
            path.lineTo(rect.x() + corner, rect.bottom())
            path.arcTo(rect.x(), rect.bottom() - corner, corner * 2, corner * 2, -90, -90)
            path.lineTo(rect.x(), rect.y() + corner)
            path.arcTo(rect.x(), rect.y(), corner * 2, corner * 2, 180, -90)
            path.closeSubpath()

            border_alpha = int(60 + 140 * self.glow_intensity)
            border_alpha = max(0, min(255, border_alpha))
            border_color = QColor(self.primary_color)
            border_color.setAlpha(border_alpha)
            painter.setPen(QPen(border_color, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

            # Esquinas
            corner_length = 50
            for bx, by, dx, dy in [
                (rect.x(), rect.y(), 1, 1),
                (rect.right(), rect.y(), -1, 1),
                (rect.x(), rect.bottom(), 1, -1),
                (rect.right(), rect.bottom(), -1, -1),
            ]:
                primary_color_220 = QColor(self.primary_color)
                primary_color_220.setAlpha(220)
                painter.setPen(QPen(primary_color_220, 3))
                painter.drawLine(QPointF(bx, by), QPointF(bx + dx * corner_length, by))
                painter.drawLine(QPointF(bx, by), QPointF(bx, by + dy * corner_length))
                accent_color_80 = QColor(self.accent_color)
                accent_color_80.setAlpha(80)
                painter.setPen(QPen(accent_color_80, 1.5))
                inner = int(corner_length * 0.35)
                painter.drawLine(
                    QPointF(bx + dx * (corner_length - inner), by + dy * (corner_length - inner)),
                    QPointF(bx + dx * corner_length, by + dy * (corner_length - inner))
                )
                painter.drawLine(
                    QPointF(bx + dx * (corner_length - inner), by + dy * (corner_length - inner)),
                    QPointF(bx + dx * (corner_length - inner), by + dy * corner_length)
                )

            # Versión
            secondary_color_80 = QColor(self.secondary_color)
            secondary_color_80.setAlpha(80)
            painter.setPen(QPen(secondary_color_80))
            painter.setFont(QFont("Courier New", 9))
            painter.drawText(
                self.rect().adjusted(0, 0, -25, -25),
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight,
                f"v3.0.1 | {self.display_name}"
            )

        except Exception as e:
            print(f"[BootScreen] Paint error: {e}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
                self._is_fullscreen = False
            else:
                self.showFullScreen()
                self._is_fullscreen = True
        elif event.key() == Qt.Key.Key_Escape:
            if self._timer:
                self._timer.stop()
            self._finish_boot()

    def resizeEvent(self, event):
        self._init_particles()
        super().resizeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, '_is_fullscreen'):
            self._is_fullscreen = True
        if not self._is_fullscreen:
            self.showFullScreen()
            self._is_fullscreen = True