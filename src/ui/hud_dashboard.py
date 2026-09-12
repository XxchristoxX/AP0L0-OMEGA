# src/ui/hud_dashboard.py
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QRadialGradient

class HUDDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background: transparent;")
        
        # Métricas
        self.metrics = {
            "cpu": 38,
            "ram": 62,
            "red": 45,
            "audio": 82,
            "jarvis": 102
        }
        
        # Layout para etiquetas de texto
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Título
        title = QLabel("◆ ANÁLISIS DE SISTEMAS")
        title.setStyleSheet("color: #00d4ff; font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        
        # Grid de métricas
        grid = QHBoxLayout()
        for key, value in self.metrics.items():
            item = QWidget()
            item_layout = QVBoxLayout(item)
            
            label = QLabel(key.upper())
            label.setStyleSheet("color: #33aacc; font-size: 10px;")
            item_layout.addWidget(label)
            
            value_label = QLabel(f"{value}%")
            color = "#00ff88" if key == "jarvis" else "#00d4ff"
            value_label.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: bold;")
            item_layout.addWidget(value_label)
            
            grid.addWidget(item)
        
        layout.addLayout(grid)
        
        # Actualizar métricas cada segundo
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_metrics)
        self.timer.start(1000)
    
    def update_metrics(self):
        # Aquí iría la lógica real de monitoreo
        # Por ahora solo simula variación
        import random
        for key in self.metrics:
            if key != "jarvis":
                self.metrics[key] = max(0, min(100, self.metrics[key] + random.randint(-3, 3)))
        self.update()
    
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # 1. Fondo con efecto glassmorphism
        painter.setBrush(QBrush(QColor(10, 14, 26, 200)))
        painter.setPen(QPen(QColor(0, 212, 255, 50), 1))
        painter.drawRoundedRect(0, 0, w, h, 10, 10)
        
        # 2. Malla de datos (grid)
        painter.setPen(QPen(QColor(0, 212, 255, 20), 1))
        for x in range(0, w, 30):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, 30):
            painter.drawLine(0, y, w, y)
        
        # 3. Anillo decorativo
        painter.setPen(QPen(QColor(0, 212, 255, 40), 1))
        painter.drawEllipse(w - 80, 20, 60, 60)
        painter.drawEllipse(w - 75, 25, 50, 50)
        
        # 4. "JARVIS 102%" con glow
        painter.setPen(QPen(QColor(0, 255, 136, 200), 2))
        painter.setFont(QFont("Courier New", 20, QFont.Weight.Bold))
        painter.drawText(QRect(20, h - 50, 200, 40), Qt.AlignmentFlag.AlignLeft, "JARVIS 102%")
        
        # 5. Efecto de brillo en el texto
        glow = QRadialGradient(20, h - 30, 100)
        glow.setColorAt(0, QColor(0, 255, 136, 50))
        glow.setColorAt(1, QColor(0, 255, 136, 0))
        painter.setBrush(QBrush(glow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, h - 80, 120, 80)