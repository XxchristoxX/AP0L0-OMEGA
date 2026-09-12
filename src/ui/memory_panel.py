# src/ui/memory_panel.py
# ============================================================================
# PANEL DE MEMORIA - Ver y gestionar la memoria del asistente
# ============================================================================

import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QPushButton, QLabel, QMessageBox,
    QSplitter, QTextEdit, QWidget, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from src.memory.memory_manager import load_memory, save_memory, _empty_memory

class MemoryPanel(QDialog):
    """Panel para ver y gestionar la memoria del asistente."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🧠 Panel de Memoria")
        self.setMinimumSize(700, 500)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #0a0a1a;
                color: #c0c0c0;
            }
            QListWidget {
                background-color: #111122;
                border: 1px solid #1a3a4a;
                border-radius: 6px;
                color: #c0c0c0;
                font-size: 11px;
                font-family: 'Courier New', monospace;
            }
            QListWidget::item {
                padding: 6px 10px;
                border-bottom: 1px solid #1a2a3a;
            }
            QListWidget::item:selected {
                background-color: #1a3a5a;
                color: #00d4ff;
            }
            QListWidget::item:hover {
                background-color: #122a3a;
            }
            QPushButton {
                background-color: #1a2a3a;
                color: #00d4ff;
                border: 1px solid #2a4a5a;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
                font-family: 'Courier New', monospace;
            }
            QPushButton:hover {
                background-color: #2a4a5a;
                border-color: #00d4ff;
            }
            QPushButton#delete {
                color: #ff4466;
                border-color: #ff4466;
            }
            QPushButton#delete:hover {
                background-color: #441122;
            }
            QPushButton#clear {
                color: #ff8844;
                border-color: #ff8844;
            }
            QPushButton#clear:hover {
                background-color: #442211;
            }
            QGroupBox {
                border: 1px solid #1a3a4a;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                color: #00d4ff;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }
            QTextEdit {
                background-color: #111122;
                border: 1px solid #1a3a4a;
                border-radius: 4px;
                color: #c0c0c0;
                font-family: 'Courier New', monospace;
                font-size: 10px;
            }
            QLabel#info {
                color: #667788;
                font-size: 10px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Título
        title = QLabel("📋 DATOS ALMACENADOS EN MEMORIA")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #00d4ff; font-family: 'Courier New';")
        layout.addWidget(title)
        
        # Splitter: lista a la izquierda, detalles a la derecha
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Widget izquierdo: lista
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.memory_list = QListWidget()
        self.memory_list.itemClicked.connect(self._show_item_details)
        left_layout.addWidget(self.memory_list)
        
        splitter.addWidget(left_widget)
        
        # Widget derecho: detalles
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        detail_group = QGroupBox("Detalles")
        detail_layout = QVBoxLayout(detail_group)
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText("Selecciona un elemento para ver sus detalles")
        detail_layout.addWidget(self.detail_text)
        right_layout.addWidget(detail_group)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 300])
        
        layout.addWidget(splitter, stretch=1)
        
        # Estadísticas
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #667788; font-size: 10px; font-family: 'Courier New';")
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)
        
        # Botones
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        
        refresh_btn = QPushButton("🔄 REFRESCAR")
        refresh_btn.clicked.connect(self.load_memory_data)
        btn_layout.addWidget(refresh_btn)
        
        delete_btn = QPushButton("🗑️ ELIMINAR SELECCIONADO")
        delete_btn.setObjectName("delete")
        delete_btn.clicked.connect(self.delete_selected)
        btn_layout.addWidget(delete_btn)
        
        clear_btn = QPushButton("🧹 LIMPIAR TODO")
        clear_btn.setObjectName("clear")
        clear_btn.clicked.connect(self.clear_all)
        btn_layout.addWidget(clear_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton("✕ CERRAR")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        # Info
        info_label = QLabel("ℹ️ Los cambios se guardan automáticamente. Los datos se usan para personalizar las respuestas.")
        info_label.setObjectName("info")
        layout.addWidget(info_label)
        
        self.load_memory_data()
    
    def load_memory_data(self):
        """Carga los datos de memoria en la lista."""
        self.memory_list.clear()
        memory = load_memory()
        
        # Categorías principales
        categories = {
            "identity": "👤 IDENTIDAD",
            "preferences": "⚙️ PREFERENCIAS",
            "projects": "📁 PROYECTOS",
            "relationships": "👥 RELACIONES",
            "wishes": "💭 DESEOS",
            "notes": "📝 NOTAS"
        }
        
        total_items = 0
        
        for category, display_name in categories.items():
            items = memory.get(category, {})
            if items:
                # Título de categoría
                cat_item = QListWidgetItem(f"─── {display_name} ───")
                cat_item.setFlags(Qt.ItemFlag.NoItemFlags)
                cat_item.setForeground(QColor("#00d4ff"))
                cat_item.setBackground(QColor("#0a1a2a"))
                self.memory_list.addItem(cat_item)
                
                for key, value in items.items():
                    if isinstance(value, dict):
                        val = value.get("value", str(value))
                        updated = value.get("updated", "")
                    else:
                        val = str(value)
                        updated = ""
                    
                    # Mostrar solo la clave y un preview
                    preview = val[:60] + "..." if len(val) > 60 else val
                    display = f"  {key}: {preview}"
                    
                    item = QListWidgetItem(display)
                    # Almacenar datos completos
                    item.setData(Qt.ItemDataRole.UserRole, {
                        "category": category,
                        "key": key,
                        "value": val,
                        "updated": updated,
                        "full_data": value
                    })
                    self.memory_list.addItem(item)
                    total_items += 1
        
        # Actualizar estadísticas
        self.stats_label.setText(f"📊 {total_items} elementos en {len([c for c in categories if memory.get(c, {})])} categorías")
    
    def _show_item_details(self, item):
        """Muestra los detalles del elemento seleccionado."""
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            self.detail_text.setText("")
            return
        
        category = data.get("category", "Desconocido")
        key = data.get("key", "Sin clave")
        value = data.get("value", "Sin valor")
        updated = data.get("updated", "Desconocido")
        
        details = f"""
📌 CATEGORÍA: {category.upper()}
🔑 CLAVE: {key}
📅 ACTUALIZADO: {updated}

📝 CONTENIDO:
{value}
"""
        self.detail_text.setText(details)
    
    def delete_selected(self):
        """Elimina el elemento seleccionado de la memoria."""
        current = self.memory_list.currentItem()
        if not current:
            QMessageBox.information(self, "Información", "Selecciona un elemento para eliminar.")
            return
        
        data = current.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        category = data.get("category")
        key = data.get("key")
        
        if not category or not key:
            return
        
        # Confirmar eliminación
        reply = QMessageBox.question(
            self,
            "Eliminar elemento",
            f"¿Eliminar '{key}' de {category}?\n\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            memory = load_memory()
            if category in memory and key in memory[category]:
                del memory[category][key]
                save_memory(memory)
                self.load_memory_data()
                self.detail_text.setText("")
    
    def clear_all(self):
        """Limpia toda la memoria."""
        reply = QMessageBox.question(
            self,
            "Limpiar toda la memoria",
            "¿Eliminar TODOS los datos de memoria?\n\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            save_memory(_empty_memory())
            self.load_memory_data()
            self.detail_text.setText("")
            QMessageBox.information(self, "Éxito", "Todos los datos de memoria han sido eliminados.")