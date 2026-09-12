# src/ui/gesture_overlay.py
"""
Overlay transparente que muestra la mano y los gestos en la pantalla.
Se superpone a todas las ventanas para visualizar el control por gestos.
"""

from PyQt6.QtCore import Qt, QTimer, QPoint, QRect
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPixmap
from PyQt6.QtWidgets import QWidget, QApplication

class GestureOverlay(QWidget):
    """
    Widget transparente que se superpone a toda la pantalla.
    Muestra la posición de la mano y el gesto actual.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

        # Obtener tamaño de pantalla
        screen = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(screen)

        # Estado
        self.hand_pos = QPoint(0, 0)
        self.gesture_name = ""
        self.is_pinching = False
        self.is_dragging = False
        self.show_overlay = True

        # Timer para actualizar
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(30)  # ~33 FPS

    def update_gesture(self, x, y, gesture, pinching=False, dragging=False):
        """Actualiza la información del gesto."""
        self.hand_pos = QPoint(x, y)
        self.gesture_name = gesture
        self.is_pinching = pinching
        self.is_dragging = dragging
        self.update()

    def paintEvent(self, event):
        if not self.show_overlay:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dibujar círculo en la posición de la mano
        color = QColor(0, 212, 255, 180)  # Cyan
        if self.is_dragging:
            color = QColor(255, 136, 0, 200)  # Naranja
        elif self.is_pinching:
            color = QColor(0, 255, 136, 200)  # Verde

        # Sombra
        painter.setBrush(QBrush(QColor(0, 0, 0, 80)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(self.hand_pos, 30, 30)

        # Círculo principal
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(255, 255, 255, 150), 2))
        painter.drawEllipse(self.hand_pos, 25, 25)

        # Texto del gesto
        if self.gesture_name:
            painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            painter.setPen(QPen(QColor(255, 255, 255, 220)))
            painter.drawText(
                self.hand_pos.x() - 40,
                self.hand_pos.y() - 50,
                80, 20,
                Qt.AlignmentFlag.AlignCenter,
                self.gesture_name
            )

        # Indicador de arrastre
        if self.is_dragging:
            painter.setPen(QPen(QColor(255, 136, 0, 100), 2, Qt.PenStyle.DashLine))
            painter.drawEllipse(self.hand_pos, 45, 45)

        painter.end()