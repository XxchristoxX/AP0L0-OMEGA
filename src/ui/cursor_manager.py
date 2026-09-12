# src/ui/cursor_manager.py
"""
Sistema de Puntero Personalizado para AP0L0
Integra:
- Nivel 1: Cursor global del sistema (Windows)
- Nivel 3: Cursor por widget (PyQt6)
- Nivel 4: Efecto de rastro (trail) estilo JARVIS
"""

import os
import ctypes
import tempfile
import math
from pathlib import Path
from typing import Optional, List, Tuple

from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPixmap, QCursor, QPainter, QColor, QPen, QBrush, 
    QRadialGradient, QFont, QPainterPath, QLinearGradient
)
from PyQt6.QtWidgets import QWidget, QApplication


# ============================================================
# CONFIGURACIÓN DEL CURSOR
# ============================================================

CURSOR_CONFIG = {
    # Colores del rastro
    "trail_color": "#00d4ff",      # Cian neón (principal)
    "trail_color2": "#00ff88",     # Verde neón (secundario)
    "trail_glow_color": "#00d4ff", # Color del resplandor
    
    # Tamaños
    "trail_radius": 8,             # Radio de los puntos del rastro
    "trail_glow_radius": 25,       # Radio del resplandor
    "cursor_size": 32,             # Tamaño del cursor personalizado
    
    # Comportamiento
    "trail_length": 15,            # Número de puntos en el rastro
    "trail_speed": 25,             # ms entre actualizaciones (más bajo = más suave)
    "fade_speed": 0.92,            # Velocidad de desvanecimiento (0-1)
}


class CursorTrailManager:
    """
    Gestor del efecto de rastro del cursor (Nivel 4).
    """
    
    def __init__(self, parent_widget: QWidget, config: dict = None):
        self.parent = parent_widget
        self.config = config or CURSOR_CONFIG
        self.trail_positions: List[Tuple[QPoint, float]] = []
        self.max_trail = self.config.get("trail_length", 15)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_trail)
        self.timer.start(self.config.get("trail_speed", 25))
        self._enabled = True
        self._last_pos = None
        self._parent_size = parent_widget.size()
        
    def enable(self):
        self._enabled = True
        self.timer.start()
        
    def disable(self):
        self._enabled = False
        self.timer.stop()
        self.trail_positions.clear()
        
    def toggle(self):
        if self._enabled:
            self.disable()
        else:
            self.enable()
            
    def is_enabled(self) -> bool:
        return self._enabled
    
    def update_trail(self):
        if not self._enabled:
            return
            
        # Obtener posición global del cursor
        cursor_pos = QCursor.pos()
        parent_pos = self.parent.mapFromGlobal(cursor_pos)
        
        # Verificar si el cursor está dentro del widget
        if not self.parent.rect().contains(parent_pos):
            # Si el cursor está fuera, desvanecer y no añadir nuevos puntos
            if self.trail_positions:
                self._fade_trail()
                self.parent.update()
            return
            
        # Evitar actualizaciones si el cursor no se ha movido
        if self._last_pos and parent_pos == self._last_pos:
            self._fade_trail()
            self.parent.update()
            return
            
        self._last_pos = parent_pos
        
        # Añadir nuevo punto con opacidad máxima
        self.trail_positions.append((parent_pos, 1.0))
        
        # Limitar longitud del rastro
        if len(self.trail_positions) > self.max_trail:
            self.trail_positions.pop(0)
            
        # Desvanecer puntos antiguos
        self._fade_trail()
        
        # Forzar repintado
        self.parent.update()
        
    def _fade_trail(self):
        """Desvanece gradualmente los puntos del rastro."""
        fade_speed = self.config.get("fade_speed", 0.92)
        for i in range(len(self.trail_positions)):
            pos, alpha = self.trail_positions[i]
            alpha *= fade_speed
            if alpha < 0.01:
                self.trail_positions[i] = (pos, 0.0)
            else:
                self.trail_positions[i] = (pos, alpha)
                
        # Eliminar puntos completamente desvanecidos
        self.trail_positions = [(p, a) for p, a in self.trail_positions if a > 0.01]
        
    def paint_trail(self, painter: QPainter):
        """Dibuja el rastro del cursor."""
        if not self._enabled or len(self.trail_positions) < 2:
            return
            
        trail_color = QColor(self.config.get("trail_color", "#00d4ff"))
        trail_color2 = QColor(self.config.get("trail_color2", "#00ff88"))
        glow_color = QColor(self.config.get("trail_glow_color", "#00d4ff"))
        base_radius = self.config.get("trail_radius", 8)
        
        # Dibujar el rastro desde el más antiguo al más nuevo
        for i, (pos, alpha) in enumerate(self.trail_positions):
            if alpha <= 0.01:
                continue
                
            # Interpolar color entre los dos colores configurados
            mix = i / max(1, len(self.trail_positions))
            r = trail_color.red() * (1 - mix) + trail_color2.red() * mix
            g = trail_color.green() * (1 - mix) + trail_color2.green() * mix
            b = trail_color.blue() * (1 - mix) + trail_color2.blue() * mix
            
            color = QColor(int(r), int(g), int(b))
            color.setAlpha(int(255 * alpha))
            
            # Tamaño del punto (más grande en el centro, más pequeño en los extremos)
            size_factor = 1.0 - abs(mix - 0.5) * 2
            radius = base_radius * (0.5 + 0.5 * size_factor) * (0.3 + 0.7 * alpha)
            
            # Resplandor exterior
            glow_radius = radius * 3.5
            posf = QPointF(pos)
            glow = QRadialGradient(posf, glow_radius)
            glow_color_alpha = QColor(glow_color)
            glow_color_alpha.setAlpha(int(60 * alpha))
            glow.setColorAt(0, glow_color_alpha)
            glow.setColorAt(1, QColor(0, 0, 0, 0))
            
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(pos, int(glow_radius), int(glow_radius))
            
            # Punto principal
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(pos, int(radius), int(radius))
            
            # Núcleo brillante
            core_color = QColor(255, 255, 255)
            core_color.setAlpha(int(120 * alpha))
            painter.setBrush(QBrush(core_color))
            painter.drawEllipse(pos, int(radius * 0.3), int(radius * 0.3))


class CustomCursorManager:
    """
    Gestor de cursores personalizados (Niveles 1 y 3).
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._custom_cursors: dict = {}
        self._default_cursor = None
        self._system_cursor_changed = False
        self._current_cursor_name = "default"
        self._trail_overlay = None
        
        # Crear cursores personalizados
        self._create_custom_cursors()
        
    def _create_custom_cursors(self):
        """Crea cursores personalizados para diferentes estados."""
        size = CURSOR_CONFIG.get("cursor_size", 32)
        
        # 1. Cursor estándar (JARVIS)
        self._custom_cursors["default"] = self._create_jarvis_cursor(size)
        
        # 2. Cursor de carga/espera
        self._custom_cursors["waiting"] = self._create_waiting_cursor(size)
        
        # 3. Cursor de clic
        self._custom_cursors["click"] = self._create_click_cursor(size)
        
        # 4. Cursor de arrastre
        self._custom_cursors["drag"] = self._create_drag_cursor(size)
        
        # 5. Cursor de selección de texto
        self._custom_cursors["text"] = self._create_text_cursor(size)
        
        # 6. Cursor de prohibido
        self._custom_cursors["forbidden"] = self._create_forbidden_cursor(size)
        
    def _create_cursor_pixmap(self, size: int, draw_func) -> QPixmap:
        """Crea un QPixmap para un cursor personalizado."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_func(painter, size)
        painter.end()
        return pixmap
    
    def _create_jarvis_cursor(self, size: int) -> QCursor:
        """Crea el cursor principal estilo JARVIS."""
        def draw(painter: QPainter, s: int):
            cx, cy = s // 2, s // 2
            r = s // 2 - 4
            
            # Anillo exterior
            pen = QPen(QColor("#00d4ff"), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))
            
            # Anillo interior
            color1 = QColor("#00ff88")
            color1.setAlpha(150)
            pen = QPen(color1, 1.5)
            painter.setPen(pen)
            painter.drawEllipse(int(cx - r * 0.6), int(cy - r * 0.6), int(r * 1.2), int(r * 1.2))
            
            # Punto central
            gradient = QRadialGradient(cx, cy, r * 0.3)
            gradient.setColorAt(0, QColor("#00ff88"))
            gradient.setColorAt(0.5, QColor("#00d4ff"))
            gradient.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(cx - r * 0.25), int(cy - r * 0.25), int(r * 0.5), int(r * 0.5))
            
            # Líneas direccionales (arriba y derecha)
            color2 = QColor("#00d4ff")
            color2.setAlpha(150)
            pen = QPen(color2, 1)
            painter.setPen(pen)
            # Flecha arriba
            painter.drawLine(int(cx), int(cy - r * 0.7), int(cx), int(cy - r * 0.2))
            painter.drawLine(int(cx - 4), int(cy - r * 0.5), int(cx), int(cy - r * 0.7))
            painter.drawLine(int(cx + 4), int(cy - r * 0.5), int(cx), int(cy - r * 0.7))
            # Flecha derecha
            painter.drawLine(int(cx + r * 0.7), int(cy), int(cx + r * 0.2), int(cy))
            painter.drawLine(int(cx + r * 0.5), int(cy - 4), int(cx + r * 0.7), int(cy))
            painter.drawLine(int(cx + r * 0.5), int(cy + 4), int(cx + r * 0.7), int(cy))
            
            # Texto "J" minúsculo
            color3 = QColor("#00ff88")
            color3.setAlpha(200)
            painter.setPen(QPen(color3, 1))
            painter.setFont(QFont("Arial", s // 4, QFont.Weight.Bold))
            painter.drawText(int(cx - s // 8), int(cy + s // 10), "j")
        
        pixmap = self._create_cursor_pixmap(size, draw)
        return QCursor(pixmap, hotX=size // 2, hotY=size // 2)
    
    def _create_waiting_cursor(self, size: int) -> QCursor:
        """Cursor de espera/carga."""
        def draw(painter: QPainter, s: int):
            cx, cy = s // 2, s // 2
            r = s // 2 - 5
            
            # Arco giratorio (estático en la imagen)
            pen = QPen(QColor("#00d4ff"), 3)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(int(cx - r), int(cy - r), int(r * 2), int(r * 2), 0, 270 * 16)
            
            # Punto brillante
            color = QColor("#00ff88")
            color.setAlpha(200)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(cx + r * 0.5), int(cy - r * 0.5), 6, 6)
        
        pixmap = self._create_cursor_pixmap(size, draw)
        return QCursor(pixmap, hotX=size // 2, hotY=size // 2)
    
    def _create_click_cursor(self, size: int) -> QCursor:
        """Cursor de clic."""
        def draw(painter: QPainter, s: int):
            cx, cy = s // 2, s // 2
            r = s // 2 - 4
            
            # Círculo con efecto de pulso
            for i in range(3):
                rad = r * (0.3 + i * 0.25)
                alpha = 255 - i * 80
                color = QColor("#00d4ff")
                color.setAlpha(alpha)
                painter.setPen(QPen(color, 2 - i * 0.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(int(cx - rad), int(cy - rad), int(rad * 2), int(rad * 2))
            
            # Punto central
            gradient = QRadialGradient(cx, cy, r * 0.2)
            gradient.setColorAt(0, QColor(255, 255, 255))
            color1 = QColor("#00ff88")
            color1.setAlpha(200)
            gradient.setColorAt(0.5, color1)
            color2 = QColor("#00d4ff")
            color2.setAlpha(100)
            gradient.setColorAt(1, color2)
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(cx - r * 0.2), int(cy - r * 0.2), int(r * 0.4), int(r * 0.4))
        
        pixmap = self._create_cursor_pixmap(size, draw)
        return QCursor(pixmap, hotX=size // 2, hotY=size // 2)
    
    def _create_drag_cursor(self, size: int) -> QCursor:
        """Cursor de arrastre."""
        def draw(painter: QPainter, s: int):
            cx, cy = s // 2, s // 2
            r = s // 2 - 6
            
            # Mano estilizada (simplificada)
            pen = QPen(QColor("#00d4ff"), 2)
            painter.setPen(pen)
            color = QColor("#00d4ff")
            color.setAlpha(50)
            painter.setBrush(QBrush(color))
            
            # Palma
            painter.drawRoundedRect(int(cx - r * 0.6), int(cy - r * 0.2), int(r * 1.2), int(r * 0.8), 5, 5)
            
            # Dedos
            for i in range(4):
                x = cx - r * 0.4 + i * r * 0.3
                painter.drawRoundedRect(int(x), int(cy - r * 0.6), int(r * 0.15), int(r * 0.5), 3, 3)
            
            # Pulgar
            painter.drawRoundedRect(int(cx - r * 0.5), int(cy + r * 0.1), int(r * 0.3), int(r * 0.3), 3, 3)
        
        pixmap = self._create_cursor_pixmap(size, draw)
        return QCursor(pixmap, hotX=size // 2, hotY=size // 2)
    
    def _create_text_cursor(self, size: int) -> QCursor:
        """Cursor de selección de texto."""
        def draw(painter: QPainter, s: int):
            cx, cy = s // 2, s // 2
            h = s - 10
            
            # Barra vertical con efecto neón
            gradient = QLinearGradient(cx, cy - h // 2, cx, cy + h // 2)
            gradient.setColorAt(0, QColor(0, 0, 0, 0))
            color1 = QColor("#00d4ff")
            color1.setAlpha(200)
            gradient.setColorAt(0.3, color1)
            color2 = QColor("#00ff88")
            color2.setAlpha(255)
            gradient.setColorAt(0.5, color2)
            color3 = QColor("#00d4ff")
            color3.setAlpha(200)
            gradient.setColorAt(0.7, color3)
            gradient.setColorAt(1, QColor(0, 0, 0, 0))
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(cx - 2, cy - h // 2, 4, h, 2, 2)
            
            # Resplandor
            glow = QRadialGradient(cx, cy, h * 0.7)
            glow_color = QColor("#00d4ff")
            glow_color.setAlpha(60)
            glow.setColorAt(0, glow_color)
            glow.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(cx - h * 0.7), int(cy - h * 0.7), int(h * 1.4), int(h * 1.4))
        
        pixmap = self._create_cursor_pixmap(size, draw)
        return QCursor(pixmap, hotX=size // 2, hotY=size // 2)
    
    def _create_forbidden_cursor(self, size: int) -> QCursor:
        """Cursor de prohibido/no permitido."""
        def draw(painter: QPainter, s: int):
            cx, cy = s // 2, s // 2
            r = s // 2 - 4
            
            # Círculo
            pen = QPen(QColor("#ff2244"), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))
            
            # Barra diagonal
            pen = QPen(QColor("#ff2244"), 3)
            painter.setPen(pen)
            offset = r * 0.6
            painter.drawLine(int(cx - offset), int(cy - offset), int(cx + offset), int(cy + offset))
            
            # Borde interior
            color = QColor("#ff2244")
            color.setAlpha(100)
            pen = QPen(color, 1)
            painter.setPen(pen)
            painter.drawEllipse(int(cx - r * 0.7), int(cy - r * 0.7), int(r * 1.4), int(r * 1.4))
        
        pixmap = self._create_cursor_pixmap(size, draw)
        return QCursor(pixmap, hotX=size // 2, hotY=size // 2)
    
    # ============================================================
    # MÉTODOS PÚBLICOS
    # ============================================================
    
    def apply_system_cursor(self):
        """Aplica el cursor personalizado a nivel de sistema (Nivel 1 - Windows)."""
        try:
            # Buscar un archivo .cur en assets
            assets_dir = Path(__file__).resolve().parent.parent / "assets"
            cursor_files = ["jarvis_cursor.cur", "custom_cursor.cur", "cursor.cur"]
            
            for cf in cursor_files:
                cursor_path = assets_dir / cf
                if cursor_path.exists():
                    ctypes.windll.user32.SetSystemCursor(
                        ctypes.windll.user32.LoadCursorFromFileW(str(cursor_path)),
                        32512  # OCR_NORMAL
                    )
                    self._system_cursor_changed = True
                    print(f"[CursorManager] ✅ Cursor del sistema cambiado a: {cursor_path}")
                    return
            
            # Si no hay archivo .cur, al menos cambiamos el cursor en la aplicación
            print("[CursorManager] ℹ️ No se encontró .cur. Usando cursor de aplicación.")
            
        except Exception as e:
            print(f"[CursorManager] ⚠️ No se pudo cambiar el cursor del sistema: {e}")
    
    def restore_system_cursor(self):
        """Restaura el cursor del sistema al predeterminado."""
        try:
            ctypes.windll.user32.SetSystemCursor(
                ctypes.windll.user32.LoadCursorW(0, 32512),  # IDC_ARROW
                32512
            )
            self._system_cursor_changed = False
            print("[CursorManager] ✅ Cursor del sistema restaurado.")
        except Exception as e:
            print(f"[CursorManager] ⚠️ No se pudo restaurar el cursor: {e}")
    
    def get_cursor(self, name: str = "default") -> QCursor:
        """Obtiene un cursor personalizado por nombre."""
        return self._custom_cursors.get(name, self._custom_cursors.get("default"))
    
    def set_widget_cursor(self, widget: QWidget, cursor_name: str = "default"):
        """Aplica un cursor personalizado a un widget específico (Nivel 3)."""
        cursor = self.get_cursor(cursor_name)
        if cursor:
            widget.setCursor(cursor)
    
    def set_global_override_cursor(self, cursor_name: str = "default"):
        """Aplica un cursor personalizado a toda la aplicación."""
        cursor = self.get_cursor(cursor_name)
        if cursor:
            QApplication.setOverrideCursor(cursor)
    
    def restore_global_override_cursor(self):
        """Restaura el cursor global de la aplicación."""
        QApplication.restoreOverrideCursor()
    
    def get_trail_overlay(self, parent: QWidget):
        """Crea un overlay para el rastro del cursor."""
        if self._trail_overlay is None:
            from PyQt6.QtWidgets import QWidget
            
            class TrailOverlay(QWidget):
                def __init__(self, parent_widget):
                    super().__init__(parent_widget)
                    self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                    self.setStyleSheet("background: transparent;")
                    self.setGeometry(parent_widget.rect())
                    self.trail_mgr = CursorTrailManager(self)
                    self.trail_mgr.enable()
                    self.show()
                    
                    # Conectar al resize del padre
                    parent_widget.installEventFilter(self)
                    
                def eventFilter(self, obj, event):
                    if event.type() == event.Type.Resize:
                        self.setGeometry(obj.rect())
                    return super().eventFilter(obj, event)
                    
                def paintEvent(self, event):
                    painter = QPainter(self)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    self.trail_mgr.paint_trail(painter)
                    painter.end()
                    
                def enable_trail(self):
                    self.trail_mgr.enable()
                    
                def disable_trail(self):
                    self.trail_mgr.disable()
                    
                def toggle_trail(self):
                    self.trail_mgr.toggle()
            
            self._trail_overlay = TrailOverlay(parent)
        return self._trail_overlay


# ============================================================
# FUNCIÓN DE INICIALIZACIÓN
# ============================================================

def init_cursor_system(main_window=None):
    """
    Inicializa el sistema completo de cursores.
    Llama a esta función al inicio de tu aplicación.
    """
    cursor_mgr = CustomCursorManager()
    
    # 1. Intentar aplicar cursor a nivel de sistema (Nivel 1)
    try:
        cursor_mgr.apply_system_cursor()
    except Exception as e:
        print(f"[CursorManager] No se pudo aplicar cursor del sistema: {e}")
    
    # 2. Aplicar cursor global a la aplicación (Nivel 3)
    try:
        cursor_mgr.set_global_override_cursor("default")
    except Exception as e:
        print(f"[CursorManager] No se pudo aplicar cursor global: {e}")
    
    # 3. Crear overlay para el rastro (Nivel 4)
    if main_window:
        try:
            overlay = cursor_mgr.get_trail_overlay(main_window)
            print("[CursorManager] ✅ Overlay de rastro creado.")
        except Exception as e:
            print(f"[CursorManager] ⚠️ No se pudo crear overlay de rastro: {e}")
    
    print("[CursorManager] ✅ Sistema de cursor personalizado inicializado.")
    return cursor_mgr


# ============================================================
# WIDGET MIXIN PARA RASTRO
# ============================================================

class CursorWidgetMixin:
    """
    Mixin que añade cursor personalizado y rastro a cualquier QWidget.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cursor_manager = CustomCursorManager()
        self._trail_overlay = None
        self._cursor_name = "default"
        self._trail_enabled = True
        self._setup_cursor_trail()
    
    def _setup_cursor_trail(self):
        """Configura el rastro del cursor en este widget."""
        try:
            self._trail_overlay = self._cursor_manager.get_trail_overlay(self)
            if self._trail_enabled:
                self._trail_overlay.enable_trail()
        except Exception as e:
            print(f"[CursorWidgetMixin] No se pudo configurar rastro: {e}")
    
    def disable_trail(self):
        """Desactiva el rastro del cursor."""
        self._trail_enabled = False
        if self._trail_overlay:
            self._trail_overlay.disable_trail()
    
    def enable_trail(self):
        """Activa el rastro del cursor."""
        self._trail_enabled = True
        if self._trail_overlay:
            self._trail_overlay.enable_trail()
    
    def toggle_trail(self):
        """Alterna el rastro del cursor."""
        self._trail_enabled = not self._trail_enabled
        if self._trail_overlay:
            self._trail_overlay.toggle_trail()
    
    def set_cursor_style(self, cursor_name: str):
        """Cambia el estilo del cursor en este widget."""
        self._cursor_name = cursor_name
        cursor = self._cursor_manager.get_cursor(cursor_name)
        if cursor:
            self.setCursor(cursor)
    
    def get_cursor_manager(self) -> CustomCursorManager:
        """Devuelve el gestor de cursores."""
        return self._cursor_manager