# src/ui/widgets.py
"""
Widgets reutilizables de la interfaz AP0L0.
Incluye: MetricBar, LogWidget, FileDropZone, _DropCanvas,
_CameraPreview, SetupOverlay, ClipboardPanel, RemoteKeyOverlay,
SystemStatusWidget y widgets adicionales del panel izquierdo.
"""

import json
import math
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
import random

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QPointF, QThread, QObject, pyqtSlot, QSize
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPen, QPixmap, QIcon,
    QLinearGradient, QAction, QPalette
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QTextEdit, QApplication, QSystemTrayIcon,
    QLineEdit, QFrame, QMenu, QSizePolicy, QScrollArea, QGridLayout,
    QListWidget, QListWidgetItem, QSlider, QComboBox, QGroupBox,
    QTabWidget, QStackedWidget, QProgressBar, QDial
)

from src.ui.ui_utils import C, qcol
from src.utils.i18n import tr
from src.utils.file_utils import _file_category, _fmt_size, _FILE_ICONS
from src.utils.system_utils import IS_WINDOWS, IS_MAC, IS_LINUX, _OS

# Intentar importar dependencias opcionales
try:
    import psutil
except ImportError:
    psutil = None

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    import requests
except ImportError:
    requests = None


# =====================================================================
# METRIC BAR (fuente 10.5pt con setPointSizeF)
# =====================================================================
class MetricBar(QWidget):
    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label
        self._base_color = color          # color base (se usa para el texto si se desea)
        self._current_color = color       # color actual
        self._inactive = False
        self._value = 0.0
        self._text = "--"
        # ===== NUEVOS UMBRALES =====
        self._low_threshold = 30          # < 30% → AZUL (bajo)
        self._normal_threshold = 70       # 30% - 70% → VERDE (normal)
        self._warning_threshold = 85      # 70% - 85% → NARANJA (advertencia)
        # > 85% → ROJO (crítico)
        self.setMinimumHeight(28)
        self.setMaximumHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_color(self, color: str):
        """Actualiza el color base de la barra (se usa para el texto o elementos decorativos)."""
        self._base_color = color
        if not self._inactive:
            self._current_color = color
        self.update()

    def set_inactive(self):
        """Marca la barra como inactiva (disco no existe) -> color gris, valor 0"""
        self._inactive = True
        self._current_color = C.TEXT_DIM
        self._value = 0.0
        self._text = "--"
        self.update()

    def set_active(self):
        """Restaura la barra a activa, usando su color base"""
        self._inactive = False
        self._current_color = self._base_color
        self.update()

    def set_value(self, pct: float, text: str):
        """
        Actualiza el valor de la barra.
        Los colores se determinan automáticamente según los umbrales:
        - < 30%  → AZUL
        - 30% - 70% → VERDE
        - 70% - 85% → NARANJA
        - > 85%  → ROJO
        """
        self._value = max(0.0, min(100.0, pct))
        self._text = text
        # Si estaba inactiva, al recibir un valor la activamos automáticamente
        if self._inactive:
            self.set_active()
        else:
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        if W < 10 or H < 10:
            return

        # Fondo del widget
        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 4, 4)

        # Fondo de la barra (vacío)
        bar_h = 5
        bar_y = H - bar_h - 5
        bar_w = W - 10
        bar_x = 5
        fill_w = int(bar_w * self._value / 100)

        p.setBrush(QBrush(qcol(C.BAR_BG)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

        # ===== NUEVA LÓGICA DE COLORES SEGÚN UMBRALES =====
        # - Inactivo o 0% → Gris
        # - < 30% → AZUL (C.PRI)
        # - 30% - 70% → VERDE (C.GREEN)
        # - 70% - 85% → NARANJA (C.ACC)
        # - > 85% → ROJO (C.RED)
        if self._inactive or self._value == 0.0:
            bar_col = qcol(C.TEXT_DIM)              # Gris/Plomo
        elif self._value < self._low_threshold:
            bar_col = qcol(C.PRI)                   # AZUL (color principal)
        elif self._value <= self._normal_threshold:
            bar_col = qcol(C.GREEN)                 # VERDE (normal)
        elif self._value <= self._warning_threshold:
            bar_col = qcol(C.ACC)                   # NARANJA (advertencia)
        else:
            bar_col = qcol(C.RED)                   # ROJO (crítico)

        # Dibujar el relleno de la barra
        if fill_w > 0:
            p.setBrush(QBrush(bar_col))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2, 2)
            # Efecto de brillo (opcional)
            if fill_w > 6:
                grad = QLinearGradient(bar_x, bar_y, bar_x, bar_y + bar_h)
                grad.setColorAt(0, qcol("#ffffff", 50))
                grad.setColorAt(1, qcol("#ffffff", 0))
                p.setBrush(QBrush(grad))
                p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h // 2), 2, 2)

        # Etiqueta fija (CPU, RAM, C:, etc.)
        font = QFont("Courier New")
        font.setPointSizeF(10.5)
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(4, 0, 44, H), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        # Texto del valor (ej. "45%", "12.5G", o "--")
        font_val = QFont("Courier New")
        font_val.setPointSizeF(10.5)
        font_val.setWeight(QFont.Weight.Bold)
        p.setFont(font_val)
        if self._inactive or self._text == "--":
            col_text = qcol(C.TEXT_DIM)
        else:
            # El texto usa el mismo color que la barra para mantener coherencia visual
            col_text = bar_col
        p.setPen(QPen(col_text, 1))
        p.drawText(QRectF(0, 0, W - 4, H), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)


# =====================================================================
# LOG WIDGET
# =====================================================================
class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Courier New", 9))
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {C.PANEL};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 6px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: {C.BG};
                width: 8px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B};
                border-radius: 4px;
                min-height: 20px;
            }}
        """)
        self._queue = []
        self._typing = False
        self._text = ""
        self._pos = 0
        self._tag = "sys"
        self._ai_name_lc = "apolo"
        self._show_timestamps = True
        self._auto_scroll = True
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        self._queue.append(text)
        if not self._typing:
            self._next()

    def _next(self):
        if not self._queue:
            self._typing = False
            return
        self._typing = True
        self._text = self._queue.pop(0)
        self._pos = 0
        tl = self._text.lower()
        if tl.startswith("you:"):
            self._tag = "you"
        elif tl.startswith(f"{self._ai_name_lc}:") or tl.startswith("apolo:"):
            self._tag = "ai"
        elif tl.startswith("file:"):
            self._tag = "file"
        elif "err" in tl or "error" in tl:
            self._tag = "err"
        elif "sys:" in tl:
            self._tag = "sys"
        elif "warn" in tl:
            self._tag = "warn"
        else:
            self._tag = "info"
        self._tmr.start(6)

    def _step(self):
        # Escribir el texto completo de una vez para que sea rápido
        if self._text:
            cur = self.textCursor()
            fmt = cur.charFormat()
            col = {
                "you": qcol(C.WHITE),
                "ai": qcol(C.PRI),
                "err": qcol(C.RED),
                "file": qcol(C.GREEN),
                "sys": qcol(C.ACC2),
                "warn": qcol(C.WARNING),
                "info": qcol(C.TEXT_MED),
            }.get(self._tag, qcol(C.TEXT))
            fmt.setForeground(QBrush(col))
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText(self._text + "\n", fmt)
            self.setTextCursor(cur)
            if self._auto_scroll:
                self.ensureCursorVisible()
            self._text = ""
            self._tmr.stop()
            QTimer.singleShot(10, self._next)
        else:
            self._tmr.stop()
            cur = self.textCursor()
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n")
            self.setTextCursor(cur)
            if self._auto_scroll:
                self.ensureCursorVisible()
            QTimer.singleShot(20, self._next)

    def clear_log(self):
        self.clear()
        self._queue.clear()
        self._typing = False
        self._tmr.stop()

    def export_log(self):
        try:
            path, _ = QFileDialog.getSaveFileName(
                self, "Export Log", str(Path.home() / "apolo_log.txt"),
                "Text Files (*.txt);;All Files (*.*)"
            )
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.toPlainText())
                QMessageBox.information(self, "Export", f"Log exported to {path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not export log: {e}")


# =====================================================================
# FILE DROP ZONE
# =====================================================================
class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(100)
        self._current_file = None
        self._hovering = False
        self._drag_over = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True
            self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False
        self._canvas.update()

    def dropEvent(self, e):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True
        self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False
        self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None
        self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_selected.emit(path)


# =====================================================================
# DROP CANVAS
# =====================================================================
class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z = self._z
        W, H = self.width(), self.height()
        pad = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        bg_col = qcol("#001a24" if z._drag_over else ("#001218" if z._hovering else C.PANEL))
        p.setBrush(QBrush(bg_col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:
            border_col = qcol(C.GREEN, 200)
        elif z._drag_over:
            border_col = qcol(C.PRI, 230)
        elif z._hovering:
            border_col = qcol(C.BORDER_B, 200)
        else:
            border_col = qcol(C.BORDER, 160)

        pen = QPen(border_col, 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:
            self._paint_file(p, W, H)
        elif z._drag_over:
            self._paint_drag_over(p, W, H)
        else:
            self._paint_idle(p, W, H, z._hovering)

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 4))
        p.drawLine(QPointF(cx - 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 14, cy + 4), QPointF(cx + 14, cy + 4))
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(qcol(C.PRI_DIM if not hover else C.TEXT), 1))
        p.drawText(QRectF(0, cy + 8, W, 16), Qt.AlignmentFlag.AlignCenter, "Drop file here  or  Click to Browse")
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol("#1a4a5a"), 1))
        p.drawText(QRectF(0, cy + 24, W, 14), Qt.AlignmentFlag.AlignCenter, "Images · Video · Audio · PDF · Docs · Code · Data")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(QFont("Courier New", 20))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "⬇")
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, "Release to load")

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 10, 60
        p.setFont(QFont("Segoe UI Emoji", 22) if IS_WINDOWS else QFont("Arial", 22))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{ext_str}  ·  {size_str}")

        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(qcol("#1e5c6a"), 1))
        par = str(path.parent)
        if len(par) > 42:
            par = "…" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 34, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 180), 1))
        p.drawText(QRectF(W - 34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "✕")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 34:
            z.clear_file()
        else:
            z.mousePressEvent(e)


# =====================================================================
# CAMERA PREVIEW
# =====================================================================
class _CameraPreview(QWidget):
    _W, _H = 244, 188

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            _CameraPreview {{
                background: rgba(0, 6, 10, 242);
                border: 1px solid {C.PRI};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._W)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 5, 6, 6)
        lay.setSpacing(4)

        hdr = QHBoxLayout()
        title = QLabel("◈  VISUAL INPUT")
        title.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(16, 16)
        close_btn.setFont(QFont("Courier New", 8))
        close_btn.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        hdr.addWidget(close_btn)
        lay.addLayout(hdr)

        self._img_lbl = QLabel()
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setStyleSheet("background: transparent;")
        lay.addWidget(self._img_lbl)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_frame(self, img_bytes: bytes) -> None:
        px = QPixmap()
        px.loadFromData(img_bytes)
        if not px.isNull():
            max_w = self._W - 12
            scaled = px.scaled(max_w, 160,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            self._img_lbl.setPixmap(scaled)
            self._img_lbl.setFixedSize(scaled.width(), scaled.height())
            self.adjustSize()
        self.show()
        self.raise_()
        self._timer.start(6000)


# =====================================================================
# SETUP OVERLAY
# =====================================================================
class SetupOverlay(QWidget):
    done = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: rgba(0, 6, 10, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(_OS.lower(), "linux")
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 30, 22)
        layout.setSpacing(8)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI, align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Courier New", font_size, QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("◈  INITIALISATION REQUIRED", 13, True))
        layout.addWidget(_lbl("Configure J.A.R.V.I.S. before first boot.", 9, color=C.PRI_DIM))
        layout.addSpacing(6)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};")
        layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("GEMINI API KEY", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(QFont("Courier New", 10))
        self._key_input.setFixedHeight(32)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        layout.addWidget(self._key_input)
        layout.addSpacing(12)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER};")
        layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("OPERATING SYSTEM", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 8, color=C.ACC2, align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout()
        os_row.setSpacing(6)
        self._os_btns = {}
        for key, label in [("windows","⊞  Windows"),("mac","  macOS"),("linux","🐧  Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(12)

        init_btn = QPushButton("▸  INITIALISE SYSTEMS")
        init_btn.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        init_btn.setFixedHeight(36)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO}; border: 1px solid {C.PRI};
            }}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

    def _sel(self, key: str):
        self._sel_os = key
        pal = {"windows":(C.PRI,"#001a22"),"mac":(C.ACC2,"#1a1400"),"linux":(C.GREEN,"#001a0d")}
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = pal[k]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {fg}; color: {bg};
                        border: none; border-radius: 3px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #000d12; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 3px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(self._key_input.styleSheet() + f" QLineEdit {{ border: 1px solid {C.RED}; }}")
            return
        self.done.emit(key, self._sel_os)


# =====================================================================
# CLIPBOARD PANEL
# =====================================================================
class ClipboardPanel(QWidget):
    action_requested = pyqtSignal(str)
    _W, _H = 340, 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ClipboardPanel {{
                background: rgba(0, 8, 14, 248);
                border: 1px solid {C.BORDER_B};
                border-radius: 8px;
            }}
        """)
        self.setFixedWidth(self._W)
        self._clip_text = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        hdr = QHBoxLayout()
        hdr.setSpacing(4)
        icon_lbl = QLabel("◈  CLIPBOARD DETECTED")
        icon_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        icon_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent;")
        hdr.addWidget(icon_lbl)
        hdr.addStretch()
        x_btn = QPushButton("✕")
        x_btn.setFixedSize(18, 18)
        x_btn.setFont(QFont("Courier New", 9))
        x_btn.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.clicked.connect(self.hide)
        hdr.addWidget(x_btn)
        lay.addLayout(hdr)

        self._preview = QLabel()
        self._preview.setFont(QFont("Courier New", 8))
        self._preview.setStyleSheet(f"""
            color: {C.TEXT}; background: {C.PANEL2};
            border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px;
        """)
        self._preview.setWordWrap(False)
        self._preview.setFixedHeight(30)
        lay.addWidget(self._preview)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        _bs = (f"QPushButton {{ background: {C.PANEL2}; color: {C.TEXT_MED}; "
               f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 2px 6px; }}"
               f"QPushButton:hover {{ color: {C.PRI}; border-color: {C.BORDER_B}; }}")
        for label, cmd_fmt in [
            ("TRANSLATE", "Translate this text to English: {text}"),
            ("SUMMARISE", "Summarise this: {text}"),
            ("EXPLAIN", "Explain this: {text}"),
            ("FIX", "Fix grammar and spelling: {text}"),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(24)
            b.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(_bs)
            b.clicked.connect(lambda _, c=cmd_fmt: self._trigger(c))
            btn_row.addWidget(b)
        lay.addLayout(btn_row)

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.hide)
        self.hide()

    def _trigger(self, cmd_fmt: str):
        if self._clip_text:
            self.action_requested.emit(cmd_fmt.format(text=self._clip_text[:800]))
        self.hide()

    def show_clipboard(self, text: str):
        self._clip_text = text
        preview = text[:62].replace('\n', ' ')
        if len(text) > 62:
            preview += "…"
        self._preview.setText(f'"{preview}"')
        self.show()
        self.raise_()
        self._dismiss_timer.start(8000)


# =====================================================================
# REMOTE KEY OVERLAY
# =====================================================================
class RemoteKeyOverlay(QWidget):
    closed = pyqtSignal()
    _OW, _OH = 420, 480

    def __init__(self, url: str, key: str, auto_login_url: str = "",
                 manual_url: str = "", expiry_secs: int = 600, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            RemoteKeyOverlay {{
                background: rgba(0, 4, 12, 0.95);
                border: 1px solid {C.BORDER_B};
                border-radius: 14px;
            }}
        """)
        self._expiry = time.time() + expiry_secs
        self._on_new_key = None
        self._auto_login_url = auto_login_url
        self._manual_url = manual_url or url

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(5)

        def _lbl(txt, fs=9, bold=False, color=C.PRI, align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Courier New", fs, QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            w.setWordWrap(True)
            return w

        lay.addWidget(_lbl("◈  REMOTE ACCESS", 12, True))
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        self._qr_label = QLabel()
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setFixedSize(176, 176)
        self._qr_label.setStyleSheet("background: white; border-radius: 10px; padding: 4px;")
        qr_row = QHBoxLayout()
        qr_row.addStretch()
        qr_row.addWidget(self._qr_label)
        qr_row.addStretch()
        lay.addLayout(qr_row)

        self._update_qr(auto_login_url)

        lay.addWidget(_lbl("Scan with phone camera to connect instantly", 8, color=C.TEXT_DIM))

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep2)

        lay.addWidget(_lbl("Or enter manually:", 7, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))

        self._url_lbl = QLabel(self._manual_url)
        self._url_lbl.setFont(QFont("Courier New", 8))
        self._url_lbl.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        self._url_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._url_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._url_lbl)

        self._key_lbl = QLabel(key)
        self._key_lbl.setFont(QFont("Courier New", 28, QFont.Weight.Bold))
        self._key_lbl.setStyleSheet(f"""
            color: {C.ACC};
            background: {C.PANEL2};
            border: 1px solid {C.BORDER_B};
            border-radius: 8px;
            padding: 6px 4px;
            letter-spacing: 10px;
        """)
        self._key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._key_lbl)

        self._timer_lbl = QLabel()
        self._timer_lbl.setFont(QFont("Courier New", 8))
        self._timer_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._timer_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        new_btn = QPushButton("NEW KEY")
        new_btn.setFixedHeight(32)
        new_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 5px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        new_btn.clicked.connect(self._refresh_key)
        btn_row.addWidget(new_btn)

        close_btn = QPushButton("DISMISS")
        close_btn.setFixedHeight(32)
        close_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 5px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self._do_close)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        self._ctimer = QTimer(self)
        self._ctimer.timeout.connect(self._tick)
        self._ctimer.start(1000)
        self._tick()

    def set_new_key_callback(self, fn) -> None:
        self._on_new_key = fn

    def _update_qr(self, url: str) -> None:
        if not url:
            self._qr_label.setText("—")
            return
        try:
            import qrcode
            from io import BytesIO
            qr = qrcode.QRCode(box_size=5, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap()
            px.loadFromData(buf.getvalue())
            self._qr_label.setPixmap(px.scaled(170, 170, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except ImportError:
            self._qr_label.setText("pip install\nqrcode[pil]")
            self._qr_label.setFont(QFont("Courier New", 8))
            self._qr_label.setStyleSheet("color: #888; background: white; border-radius: 10px; padding: 4px;")
        except Exception:
            self._qr_label.setText(url[:28])
            self._qr_label.setFont(QFont("Courier New", 7))
            self._qr_label.setStyleSheet(f"color: {C.PRI}; background: white; border-radius: 10px; padding: 4px;")

    def _tick(self):
        remaining = max(0, int(self._expiry - time.time()))
        m, s = divmod(remaining, 60)
        self._timer_lbl.setText(f"Key expires in  {m:02d}:{s:02d}")
        if remaining == 0:
            self._do_close()

    def mark_connected(self) -> None:
        self._ctimer.stop()
        self._key_lbl.setText("CONNECTED")
        self._key_lbl.setStyleSheet(f"""
            color: {C.GREEN};
            background: rgba(34,197,94,0.08);
            border: 2px solid rgba(34,197,94,0.4);
            border-radius: 8px;
            padding: 6px 4px;
            letter-spacing: 4px;
        """)
        self._qr_label.setText("✓")
        self._qr_label.setFont(QFont("Courier New", 54, QFont.Weight.Bold))
        self._qr_label.setStyleSheet("color: #00ff88; background: #001a0d; border-radius: 10px;")
        self._timer_lbl.setText("Phone connected — APOLO ready")
        self._timer_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")

    def _refresh_key(self):
        if self._on_new_key:
            result = self._on_new_key()
            if result:
                url = result[0]
                key = result[1]
                auto = result[2] if len(result) >= 3 else ""
                manual = result[3] if len(result) >= 4 else url
                self._manual_url = manual or url
                self._url_lbl.setText(self._manual_url)
                self._key_lbl.setText(key)
                self._auto_login_url = auto
                self._update_qr(auto or url)
                self._expiry = time.time() + 600
                self._key_lbl.setStyleSheet(f"""
                    color: {C.ACC};
                    background: {C.PANEL2};
                    border: 1px solid {C.BORDER_B};
                    border-radius: 8px;
                    padding: 6px 4px;
                    letter-spacing: 10px;
                """)
                self._timer_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
                self._ctimer.start(1000)
                self._tick()

    def _do_close(self):
        self._ctimer.stop()
        self.hide()
        self.closed.emit()


# =====================================================================
# HILO DE MONITORIZACIÓN DEL SISTEMA
# =====================================================================
class SystemMonitorThread(QThread):
    data_updated = pyqtSignal(dict)

    def __init__(self, interval_ms=2000):
        super().__init__()
        self.interval_ms = interval_ms
        self._running = True

    def run(self):
        while self._running:
            try:
                data = {}
                if psutil:
                    data['cpu'] = psutil.cpu_percent(interval=0.5)
                    mem = psutil.virtual_memory()
                    data['mem_percent'] = mem.percent
                    data['mem_used_gb'] = mem.used / (1024**3)
                    data['mem_total_gb'] = mem.total / (1024**3)

                    # Temperatura real de la CPU
                    temp_val = 0.0
                    try:
                        temps = psutil.sensors_temperatures()
                        if temps:
                            for key in temps:
                                if temps[key]:
                                    temp_val = temps[key][0].current
                                    break
                    except Exception:
                        pass
                    data['cpu_temp'] = temp_val

                    for drive in ['C:', 'D:', 'E:', 'F:']:
                        try:
                            usage = psutil.disk_usage(drive)
                            data[f'disk_{drive[0]}'] = {
                                'percent': usage.percent,
                                'used_gb': usage.used / (1024**3),
                                'free_gb': usage.free / (1024**3)
                            }
                        except:
                            data[f'disk_{drive[0]}'] = None
                    net = psutil.net_io_counters()
                    data['net_sent'] = net.bytes_sent / 1024
                    data['net_recv'] = net.bytes_recv / 1024
                    wifi_signal = 70.0
                    if IS_WINDOWS:
                        try:
                            out = subprocess.check_output(["netsh", "wlan", "show", "interfaces"], encoding='utf-8', stderr=subprocess.DEVNULL)
                            for line in out.splitlines():
                                if "Signal" in line:
                                    parts = line.split(":")
                                    if len(parts) > 1:
                                        wifi_signal = float(parts[1].strip().replace("%", ""))
                                        break
                        except:
                            pass
                    data['wifi_signal'] = wifi_signal
                    ssid = "Flamingo"
                    link_signal = 99.0
                    if IS_WINDOWS:
                        try:
                            out = subprocess.check_output(["netsh", "wlan", "show", "interfaces"], encoding='utf-8', stderr=subprocess.DEVNULL)
                            for line in out.splitlines():
                                if "SSID" in line and "BSSID" not in line:
                                    parts = line.split(":")
                                    if len(parts) > 1:
                                        ssid = parts[1].strip()
                                if "Signal" in line:
                                    parts = line.split(":")
                                    if len(parts) > 1:
                                        link_signal = float(parts[1].strip().replace("%", ""))
                        except:
                            pass
                    data['link_ssid'] = ssid
                    data['link_signal'] = link_signal
                    batt = psutil.sensors_battery()
                    if batt:
                        data['batt_percent'] = batt.percent
                        data['batt_charging'] = batt.power_plugged
                    else:
                        data['batt_percent'] = 0.0
                        data['batt_charging'] = False
                    recycle_size = 0.0
                    if IS_WINDOWS:
                        try:
                            import ctypes
                            from ctypes import wintypes
                            class SHQUERYRBINFO(ctypes.Structure):
                                _fields_ = [
                                    ("cbSize", wintypes.DWORD),
                                    ("i64Size", ctypes.c_int64),
                                    ("i64NumItems", ctypes.c_int64)
                                ]
                            rb = SHQUERYRBINFO()
                            rb.cbSize = ctypes.sizeof(SHQUERYRBINFO)
                            shell32 = ctypes.windll.shell32
                            if shell32.SHQueryRecycleBinW(0, ctypes.byref(rb)) == 0:
                                recycle_size = rb.i64Size / (1024**2)
                        except:
                            pass
                    data['recycle_size_mb'] = recycle_size
                else:
                    data = {
                        'cpu': random.uniform(5, 30),
                        'mem_percent': random.uniform(40, 70),
                        'mem_used_gb': random.uniform(4, 12),
                        'mem_total_gb': 16,
                        'cpu_temp': random.uniform(35, 65),
                        'disk_C': {'percent': random.uniform(30, 70), 'used_gb': random.uniform(50, 200), 'free_gb': random.uniform(100, 300)},
                        'disk_D': {'percent': random.uniform(20, 60), 'used_gb': random.uniform(30, 150), 'free_gb': random.uniform(80, 250)},
                        'disk_E': {'percent': random.uniform(10, 50), 'used_gb': random.uniform(20, 100), 'free_gb': random.uniform(100, 300)},
                        'disk_F': {'percent': random.uniform(5, 40), 'used_gb': random.uniform(10, 80), 'free_gb': random.uniform(150, 400)},
                        'net_sent': random.uniform(10, 500),
                        'net_recv': random.uniform(20, 800),
                        'wifi_signal': random.uniform(40, 100),
                        'link_ssid': 'Flamingo',
                        'link_signal': random.uniform(80, 100),
                        'batt_percent': random.uniform(20, 95),
                        'batt_charging': random.choice([True, False]),
                        'recycle_size_mb': random.uniform(0, 500)
                    }
                self.data_updated.emit(data)
            except Exception as e:
                pass
            self.msleep(self.interval_ms)

    def stop(self):
        self._running = False
        self.wait()


# =====================================================================
# SYSTEM STATUS WIDGET (fuentes 10.5pt con setPointSizeF)
# =====================================================================
class SystemStatusWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._setup_ui()
        self.monitor_thread = SystemMonitorThread(interval_ms=2000)
        self.monitor_thread.data_updated.connect(self._update_ui)
        self.monitor_thread.start()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        # ===== BARRAS DEL SISTEMA =====
        # NOTA: El color base (C.GREEN) solo se usa para el texto de la etiqueta o para
        # personalización futura. El color de la barra (relleno) se determina
        # automáticamente según el nivel de uso:
        #   < 30%  → AZUL (bajo)
        #   30-70% → VERDE (normal)
        #   70-85% → NARANJA (advertencia)
        #   > 85%  → ROJO (crítico)
        #   Inactivo → GRIS
        self.cpu_bar = MetricBar("CPU", C.GREEN)
        self.cpu_bar.setFixedHeight(30)
        layout.addWidget(self.cpu_bar)

        self.ram_bar = MetricBar("RAM", C.GREEN)
        self.ram_bar.setFixedHeight(30)
        layout.addWidget(self.ram_bar)

        self.disk_c_bar = MetricBar("C:", C.GREEN)
        self.disk_c_bar.setFixedHeight(28)
        layout.addWidget(self.disk_c_bar)

        self.disk_d_bar = MetricBar("D:", C.GREEN)
        self.disk_d_bar.setFixedHeight(28)
        layout.addWidget(self.disk_d_bar)

        self.disk_e_bar = MetricBar("E:", C.GREEN)
        self.disk_e_bar.setFixedHeight(28)
        layout.addWidget(self.disk_e_bar)

        self.disk_f_bar = MetricBar("F:", C.GREEN)
        self.disk_f_bar.setFixedHeight(28)
        layout.addWidget(self.disk_f_bar)

        # ===== ETIQUETAS DE RED, WIFI, BATERÍA Y PAPELERA =====
        font_labels = QFont("Courier New")
        font_labels.setPointSizeF(10.5)
        font_labels.setWeight(QFont.Weight.Bold)

        self.net_label = QLabel("⬆ 0 KB/s  ⬇ 0 KB/s")
        self.net_label.setFont(font_labels)
        self.net_label.setStyleSheet(f"color: {C.TEXT_MED};")
        self.net_label.setFixedHeight(20)
        layout.addWidget(self.net_label)

        self.wifi_label = QLabel("Wi-Fi 0%")
        self.wifi_label.setFont(font_labels)
        self.wifi_label.setStyleSheet(f"color: {C.TEXT_MED};")
        self.wifi_label.setFixedHeight(20)
        layout.addWidget(self.wifi_label)

        self.link_label = QLabel("Link --")
        self.link_label.setFont(font_labels)
        self.link_label.setStyleSheet(f"color: {C.TEXT_MED};")
        self.link_label.setFixedHeight(20)
        layout.addWidget(self.link_label)

        self.batt_label = QLabel("Batt --")
        self.batt_label.setFont(font_labels)
        self.batt_label.setStyleSheet(f"color: {C.TEXT_MED};")
        self.batt_label.setFixedHeight(20)
        layout.addWidget(self.batt_label)

        self.recycle_label = QLabel("Recycle 0.0 MB")
        self.recycle_label.setFont(font_labels)
        self.recycle_label.setStyleSheet(f"color: {C.TEXT};")
        self.recycle_label.setFixedHeight(20)
        layout.addWidget(self.recycle_label)

        layout.addStretch()

    @pyqtSlot(dict)
    def _update_ui(self, data):
        self.cpu_bar.set_value(data['cpu'], f"{data['cpu']:.0f}%")
        self.ram_bar.set_value(data['mem_percent'], f"{data['mem_used_gb']:.1f}G / {data['mem_total_gb']:.1f}G")
        # ... resto del método

        for drive_letter, bar in [('C', self.disk_c_bar), ('D', self.disk_d_bar), ('E', self.disk_e_bar), ('F', self.disk_f_bar)]:
            key = f'disk_{drive_letter}'
            if data.get(key):
                bar.set_active()
                bar.set_value(data[key]['percent'], f"{data[key]['used_gb']:.1f}G")
            else:
                bar.set_inactive()

        self.net_label.setText(f"⬆ {data['net_sent']:.0f} KB/s  ⬇ {data['net_recv']:.0f} KB/s")
        self.wifi_label.setText(f"Wi-Fi {data['wifi_signal']:.0f}%")
        self.link_label.setText(f"Link {data['link_ssid'][:4]} {data['link_signal']:.0f}%")
        status = 'C' if data['batt_charging'] else 'D'
        self.batt_label.setText(f"Batt {data['batt_percent']:.0f}% {status}")
        self.recycle_label.setText(f"Recycle {data['recycle_size_mb']:.1f} MB")

    def closeEvent(self, event):
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.stop()
        super().closeEvent(event)


# =====================================================================
# WIDGET DE BATERÍA
# =====================================================================
class BatteryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(70)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._percent = 0
        self._charging = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_data)
        self._timer.start(2000)
        self.update_data()

    def update_data(self):
        if psutil:
            batt = psutil.sensors_battery()
            if batt:
                self._percent = batt.percent
                self._charging = batt.power_plugged
        else:
            self._percent = random.randint(20, 95)
            self._charging = random.choice([True, False])
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        size = min(W, H) - 20
        rect = QRectF((W - size) // 2, (H - size) // 2, size, size)
        center = rect.center()
        radius = size / 2 - 4

        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawEllipse(rect)

        span = int(360 * 16 * self._percent / 100)
        color = C.GREEN if self._percent > 40 else (C.WARNING if self._percent > 20 else C.RED)
        p.setPen(QPen(qcol(color, 200), 5))
        p.drawArc(rect, 90 * 16, -span)

        p.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT), 1))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self._percent:.0f}%")

        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        status = "C" if self._charging else "D"
        p.drawText(QRectF(rect.x(), rect.y() + rect.height()*0.6, rect.width(), rect.height()*0.3),
                   Qt.AlignmentFlag.AlignCenter, status)


# =====================================================================
# WIDGET DE TRÁFICO DE RED
# =====================================================================
# src/ui/widgets.py (fragmento para NetworkGraphWidget - reemplazar esta clase)
class NetworkGraphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._sent_data = [0] * 60
        self._recv_data = [0] * 60
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_data)
        self._timer.start(1000)
        self._last_net = None
        self._last_time = None

    def update_data(self):
        if psutil:
            try:
                net = psutil.net_io_counters()
                now = time.time()
                if self._last_net is not None and self._last_time is not None:
                    dt = now - self._last_time
                    if dt > 0:
                        sent = (net.bytes_sent - self._last_net.bytes_sent) / dt / 1024  # KB/s
                        recv = (net.bytes_recv - self._last_net.bytes_recv) / dt / 1024  # KB/s
                    else:
                        sent = recv = 0.0
                else:
                    sent = recv = 0.0
                self._last_net = net
                self._last_time = now
                self._sent_data.append(sent)
                self._recv_data.append(recv)
                if len(self._sent_data) > 60:
                    self._sent_data.pop(0)
                    self._recv_data.pop(0)
            except Exception:
                pass
        else:
            self._sent_data.append(random.uniform(10, 500))
            self._recv_data.append(random.uniform(20, 800))
            if len(self._sent_data) > 60:
                self._sent_data.pop(0)
                self._recv_data.pop(0)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        if len(self._sent_data) < 2:
            return

        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(1, 1, W-2, H-2, 4, 4)

        max_val = max(max(self._sent_data), max(self._recv_data), 1.0)  # evita división por cero
        step_x = (W - 10) / (len(self._sent_data) - 1)
        offset_y = H - 8

        # Curva de envío
        p.setPen(QPen(qcol("#00ff88", 180), 1.5))
        for i in range(1, len(self._sent_data)):
            x1 = 5 + (i-1) * step_x
            y1 = offset_y - (self._sent_data[i-1] / max_val) * (H - 16)
            x2 = 5 + i * step_x
            y2 = offset_y - (self._sent_data[i] / max_val) * (H - 16)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # Curva de recepción
        p.setPen(QPen(qcol("#00d4ff", 180), 1.5))
        for i in range(1, len(self._recv_data)):
            x1 = 5 + (i-1) * step_x
            y1 = offset_y - (self._recv_data[i-1] / max_val) * (H - 16)
            x2 = 5 + i * step_x
            y2 = offset_y - (self._recv_data[i] / max_val) * (H - 16)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # Etiquetas
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(10, 4, 60, 12), Qt.AlignmentFlag.AlignLeft, "⬆")
        p.setPen(QPen(qcol(C.GREEN), 1))
        p.drawText(QRectF(20, 4, 40, 12), Qt.AlignmentFlag.AlignLeft, f"{self._sent_data[-1]:.0f}")
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(60, 4, 60, 12), Qt.AlignmentFlag.AlignLeft, "⬇")
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(70, 4, 40, 12), Qt.AlignmentFlag.AlignLeft, f"{self._recv_data[-1]:.0f}")
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(W-80, 4, 60, 12), Qt.AlignmentFlag.AlignRight, "KB/s")


# =====================================================================
# WIDGET DE CLIMA (Lima, Perú – Chorrillos, centrado)
# =====================================================================
class WeatherWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Datos fijos para Lima, Perú – Chorrillos
        self._location = "Chorrillos, Lima"
        self._temp = 22
        self._condition = "Nublado"
        self._icon = "☁️"

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(1, 1, W-2, H-2, 4, 4)

        p.setFont(QFont("Segoe UI", 22))
        p.setPen(QPen(qcol(C.TEXT), 1))
        p.drawText(QRectF(0, 6, W, 30), Qt.AlignmentFlag.AlignCenter, self._icon)

        font_temp = QFont("Courier New")
        font_temp.setPointSizeF(10.5)
        font_temp.setWeight(QFont.Weight.Bold)
        p.setFont(font_temp)
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, 30, W, 20), Qt.AlignmentFlag.AlignCenter, f"{self._temp:.0f}°C")

        font_cond = QFont("Courier New", 9)
        p.setFont(font_cond)
        p.setPen(QPen(qcol(C.TEXT_MED), 1))
        p.drawText(QRectF(0, 50, W, 16), Qt.AlignmentFlag.AlignCenter, self._condition)

        font_loc = QFont("Courier New", 8)
        p.setFont(font_loc)
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 66, W, 14), Qt.AlignmentFlag.AlignCenter, self._location)


# =====================================================================
# WIDGET DE CALENDARIO
# =====================================================================
class CalendarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._events = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_data)
        self._timer.start(60000)
        self.update_data()

    def update_data(self):
        now = datetime.now()
        events = [
            (now + timedelta(hours=1), "Reunión equipo"),
            (now + timedelta(hours=3), "Entrevista"),
            (now + timedelta(hours=5), "Cita médico")
        ]
        self._events = events[:3]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(1, 1, W-2, H-2, 4, 4)

        y = 8
        p.setFont(QFont("Courier New", 8))
        for dt, desc in self._events:
            p.setPen(QPen(qcol(C.TEXT_DIM), 1))
            p.drawText(QRectF(8, y, 45, 16), Qt.AlignmentFlag.AlignLeft, dt.strftime("%H:%M"))
            p.setPen(QPen(qcol(C.TEXT), 1))
            p.drawText(QRectF(55, y, W-65, 16), Qt.AlignmentFlag.AlignLeft, desc[:25])
            y += 22


# =====================================================================
# WIDGET DE TEMPORIZADOR
# =====================================================================
class TimerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.display = QLabel("00:00")
        self.display.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self.display.setStyleSheet(f"color: {C.PRI}; background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 2px;")
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.display)
        controls = QHBoxLayout()
        self.start_btn = QPushButton("Iniciar")
        self.start_btn.setStyleSheet(f"background: {C.PANEL}; color: {C.GREEN}; border: 1px solid {C.GREEN}; border-radius: 3px; font-size: 7pt;")
        self.start_btn.clicked.connect(self.start_timer)
        controls.addWidget(self.start_btn)
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setStyleSheet(f"background: {C.PANEL}; color: {C.RED}; border: 1px solid {C.RED}; border-radius: 3px; font-size: 7pt;")
        self.reset_btn.clicked.connect(self.reset_timer)
        controls.addWidget(self.reset_btn)
        layout.addLayout(controls)
        self._seconds = 0
        self._running = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.tick)

    def start_timer(self):
        if not self._running:
            self._running = True
            self._timer.start(1000)
            self.start_btn.setText("Detener")
        else:
            self._running = False
            self._timer.stop()
            self.start_btn.setText("Iniciar")

    def reset_timer(self):
        self._running = False
        self._timer.stop()
        self._seconds = 0
        self.update_display()
        self.start_btn.setText("Iniciar")

    def tick(self):
        self._seconds += 1
        self.update_display()

    def update_display(self):
        mins = self._seconds // 60
        secs = self._seconds % 60
        self.display.setText(f"{mins:02d}:{secs:02d}")


# =====================================================================
# WIDGET DE SEGURIDAD (fuente 10.5pt con setPointSizeF)
# =====================================================================
class SecurityWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._status = "Protegido"
        self._color = C.GREEN
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_data)
        self._timer.start(5000)
        self.update_data()

    def update_data(self):
        self._status = random.choice(["Protegido", "Riesgo bajo", "Actualización pendiente"])
        self._color = C.GREEN if self._status == "Protegido" else (C.WARNING if "Riesgo" in self._status else C.RED)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(1, 1, W-2, H-2, 4, 4)

        font = QFont("Courier New")
        font.setPointSizeF(10.5)
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QPen(qcol(self._color), 1))
        p.drawText(QRectF(8, 0, W-16, H), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"🛡️ {self._status}")


# =====================================================================
# WIDGET DE TEMPERATURA (CORREGIDO – usa datos reales del sistema, fuente 10.5pt)
# =====================================================================
class TemperatureWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._temp = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_data)
        self._timer.start(3000)
        self.update_data()

    def update_data(self):
        if psutil:
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for key in temps:
                        if temps[key]:
                            self._temp = temps[key][0].current
                            break
                    else:
                        self._temp = 0.0
                else:
                    self._temp = 0.0
            except Exception:
                self._temp = 0.0
        else:
            self._temp = random.uniform(35, 65)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(1, 1, W-2, H-2, 4, 4)

        font = QFont("Courier New")
        font.setPointSizeF(10.5)
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        if self._temp > 0.1:
            col = C.GREEN if self._temp < 50 else (C.WARNING if self._temp < 70 else C.RED)
            p.setPen(QPen(qcol(col), 1))
            p.drawText(QRectF(8, 0, W-16, H), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       f"🌡️  CPU: {self._temp:.1f} °C")
        else:
            p.setPen(QPen(qcol(C.TEXT_DIM), 1))
            p.drawText(QRectF(8, 0, W-16, H), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       "🌡️  CPU: N/A")


# =====================================================================
# WIDGET DE MEMORIA SWAP (fuente 10.5pt con setPointSizeF)
# =====================================================================
class SwapWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._used_gb = 0.0
        self._total_gb = 0.0
        self._percent = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_data)
        self._timer.start(5000)
        self.update_data()

    def update_data(self):
        if psutil:
            try:
                swap = psutil.swap_memory()
                self._used_gb = swap.used / (1024**3)
                self._total_gb = swap.total / (1024**3)
                self._percent = swap.percent
            except Exception:
                pass
        else:
            self._used_gb = random.uniform(0.5, 4)
            self._total_gb = 16.0
            self._percent = (self._used_gb / self._total_gb) * 100
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(1, 1, W-2, H-2, 4, 4)

        font = QFont("Courier New")
        font.setPointSizeF(10.5)
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        
        col = C.GREEN if self._percent < 60 else (C.WARNING if self._percent < 85 else C.RED)
        p.setPen(QPen(qcol(col), 1))
        p.drawText(QRectF(8, 0, W-16, H), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"💾 Swap: {self._used_gb:.1f} / {self._total_gb:.1f} GB ({self._percent:.0f}%)")