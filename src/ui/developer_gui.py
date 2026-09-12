# src/ui/developer_gui.py
# -*- coding: utf-8 -*-
"""
Interfaz de Desarrollo AP0L0
Fusionada con el ProjectBuilder de JARVIS
Panel de control para construir y editar proyectos
"""

import os
import sys
import json
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor, QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QComboBox,
    QFileDialog, QMessageBox, QSplitter, QTreeWidget, QTreeWidgetItem,
    QTabWidget, QFrame, QScrollArea, QProgressBar, QCheckBox,
    QGroupBox, QGridLayout, QMenu, QMenuBar, QStatusBar, QDialog,
    QDialogButtonBox, QTextBrowser
)

from src.core.config import _get_config
from src.core.ai_providers import generate


class DeveloperGUI(QMainWindow):
    """
    Interfaz de desarrollo con constructor de proyectos integrado.
    """

    def __init__(self, project_builder=None, parent=None):
        super().__init__(parent)
        self.project_builder = project_builder
        self.current_project_path = None
        self.current_file = None
        self.is_running = False

        self.setWindowTitle("AP0L0 - Constructor de Proyectos")
        self.setGeometry(100, 100, 1400, 800)
        self.setMinimumSize(1000, 600)

        self._setup_ui()
        self._apply_style()

        # Cargar configuración
        self._load_config()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # ---- Barra superior ----
        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("⚡ Constructor de Proyectos AP0L0")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #00d4ff;")
        top_layout.addWidget(title)
        top_layout.addStretch()

        self.btn_nuevo = QPushButton("📁 Nuevo Proyecto")
        self.btn_nuevo.clicked.connect(self._nuevo_proyecto)
        top_layout.addWidget(self.btn_nuevo)

        self.btn_abrir = QPushButton("📂 Abrir Proyecto")
        self.btn_abrir.clicked.connect(self._abrir_proyecto)
        top_layout.addWidget(self.btn_abrir)

        self.btn_guardar = QPushButton("💾 Guardar")
        self.btn_guardar.clicked.connect(self._guardar_archivo)
        top_layout.addWidget(self.btn_guardar)

        self.btn_ejecutar = QPushButton("▶ Ejecutar")
        self.btn_ejecutar.clicked.connect(self._ejecutar_proyecto)
        top_layout.addWidget(self.btn_ejecutar)

        self.btn_vscode = QPushButton("📝 VS Code")
        self.btn_vscode.clicked.connect(self._abrir_vscode)
        top_layout.addWidget(self.btn_vscode)

        layout.addWidget(top_bar)

        # ---- Cuerpo principal (splitter) ----
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)

        # --- Panel izquierdo: Explorador de archivos ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        lbl_explorador = QLabel("📁 Explorador de Archivos")
        lbl_explorador.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl_explorador.setStyleSheet("color: #33aacc;")
        left_layout.addWidget(lbl_explorador)

        self.tree_archivos = QTreeWidget()
        self.tree_archivos.setHeaderLabel("Archivos")
        self.tree_archivos.itemDoubleClicked.connect(self._abrir_archivo)
        self.tree_archivos.setStyleSheet("""
            QTreeWidget {
                background: #010d14;
                color: #66eeff;
                border: 1px solid #0d3347;
                border-radius: 4px;
                font-family: 'Courier New';
                font-size: 10pt;
            }
            QTreeWidget::item:selected {
                background: #001a2e;
            }
        """)
        left_layout.addWidget(self.tree_archivos)
        splitter.addWidget(left_panel)

        # --- Panel central: Editor de código ---
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                background: #010d14;
                border: 1px solid #0d3347;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #000d14;
                color: #33aacc;
                padding: 6px 12px;
                border: 1px solid #0d3347;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #010d14;
                color: #00d4ff;
            }
        """)
        center_layout.addWidget(self.tab_widget)

        # Pestaña Editor
        tab_editor = QWidget()
        editor_layout = QVBoxLayout(tab_editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)

        self.code_editor = QTextEdit()
        self.code_editor.setFont(QFont("Consolas", 11))
        self.code_editor.setStyleSheet("""
            QTextEdit {
                background: #000d14;
                color: #66eeff;
                border: none;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11pt;
            }
        """)
        editor_layout.addWidget(self.code_editor)
        self.tab_widget.addTab(tab_editor, "📄 Editor")

        # Pestaña Vista Previa
        tab_preview = QWidget()
        preview_layout = QVBoxLayout(tab_preview)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_label = QLabel("Vista previa del proyecto")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                background: #010d14;
                color: #1a5577;
                font-size: 12pt;
            }
        """)
        preview_layout.addWidget(self.preview_label)
        self.tab_widget.addTab(tab_preview, "🌐 Vista Previa")

        splitter.addWidget(center_panel)

        # --- Panel derecho: Consola/Log ---
        right_panel = QWidget()
        right_panel.setMaximumWidth(400)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        lbl_consola = QLabel("📋 Consola")
        lbl_consola.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl_consola.setStyleSheet("color: #33aacc;")
        right_layout.addWidget(lbl_consola)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 10))
        self.console.setStyleSheet("""
            QTextEdit {
                background: #010d14;
                color: #33aacc;
                border: 1px solid #0d3347;
                border-radius: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
            }
        """)
        right_layout.addWidget(self.console)

        splitter.addWidget(right_panel)
        splitter.setSizes([250, 600, 300])

        # Barra de estado
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet("background: #010d14; color: #33aacc;")
        self.status_bar.showMessage("Listo")

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background: #000d14; }
            QPushButton {
                background: #001a2e;
                color: #00d4ff;
                border: 1px solid #0d3347;
                border-radius: 4px;
                padding: 6px 14px;
                font-family: 'Segoe UI';
                font-size: 10pt;
            }
            QPushButton:hover {
                background: #002a3e;
                border-color: #00d4ff;
            }
            QPushButton:pressed { background: #003a4e; }
            QComboBox {
                background: #001a2e;
                color: #66eeff;
                border: 1px solid #0d3347;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QLineEdit {
                background: #001a2e;
                color: #66eeff;
                border: 1px solid #0d3347;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QLineEdit:focus { border-color: #00d4ff; }
            QLabel { color: #33aacc; font-family: 'Segoe UI'; }
            QStatusBar {
                background: #010d14;
                color: #33aacc;
            }
            QProgressBar {
                background: #001a2e;
                border: 1px solid #0d3347;
                border-radius: 2px;
                text-align: center;
                color: #00d4ff;
                font-size: 9pt;
                height: 16px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00d4ff, stop:0.5 #00ff88, stop:1 #00d4ff);
                border-radius: 2px;
            }
        """)

    # ---- Métodos de log ----
    def log(self, mensaje, nivel="info"):
        colores = {"info": "#33aacc", "success": "#00ff88", "warning": "#ffcc00", "error": "#ff2244"}
        color = colores.get(nivel, "#33aacc")
        self.console.append(f'<span style="color:{color};">{mensaje}</span>')

    def set_status(self, mensaje):
        self.status_bar.showMessage(mensaje)

    # ---- Manejo de proyectos ----
    def _nuevo_proyecto(self):
        from PyQt6.QtWidgets import QInputDialog
        nombre, ok = QInputDialog.getText(
            self, "Nuevo Proyecto",
            "Nombre del proyecto:",
            text="proyecto_apolo"
        )
        if not ok or not nombre.strip():
            return
        carpeta = QFileDialog.getExistingDirectory(
            self, "Seleccionar ubicación para el proyecto",
            str(Path.home() / "Desktop"),
            QFileDialog.Option.ShowDirsOnly
        )
        if not carpeta:
            return
        ruta_proyecto = Path(carpeta) / nombre.strip().replace(" ", "_")
        ruta_proyecto.mkdir(parents=True, exist_ok=True)
        self.current_project_path = str(ruta_proyecto)
        self.setWindowTitle(f"AP0L0 - {nombre} - Constructor de Proyectos")

        # Crear archivo principal
        archivo_main = ruta_proyecto / "index.html"
        archivo_main.write_text("""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Proyecto AP0L0</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #0a0e1a;
            color: #00d4ff;
            font-family: 'Courier New', monospace;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .container {
            border: 1px solid #00d4ff33;
            border-radius: 12px;
            padding: 40px;
            max-width: 600px;
            text-align: center;
        }
        h1 { color: #00ff88; }
        .status { color: #33aacc; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ AP0L0</h1>
        <p class="status">Proyecto iniciado correctamente</p>
    </div>
</body>
</html>""", encoding="utf-8")

        self._cargar_arbol()
        self._abrir_archivo_por_nombre("index.html")
        self.log(f"✅ Proyecto '{nombre}' creado en: {ruta_proyecto}", "success")
        self.set_status(f"Proyecto: {nombre}")

    def _abrir_proyecto(self):
        carpeta = QFileDialog.getExistingDirectory(
            self, "Seleccionar proyecto",
            str(Path.home() / "Desktop"),
            QFileDialog.Option.ShowDirsOnly
        )
        if not carpeta:
            return
        self.current_project_path = carpeta
        nombre = Path(carpeta).name
        self.setWindowTitle(f"AP0L0 - {nombre} - Constructor de Proyectos")
        self._cargar_arbol()
        self.log(f"📂 Proyecto abierto: {carpeta}", "info")
        self.set_status(f"Proyecto: {nombre}")

    def _cargar_arbol(self):
        self.tree_archivos.clear()
        if not self.current_project_path:
            return
        root_item = QTreeWidgetItem(self.tree_archivos)
        root_item.setText(0, Path(self.current_project_path).name)
        root_item.setData(0, Qt.ItemDataRole.UserRole, self.current_project_path)
        self._cargar_directorio(root_item, self.current_project_path)
        root_item.setExpanded(True)

    def _cargar_directorio(self, parent_item, path):
        try:
            for item in sorted(os.listdir(path)):
                if item in ['.git', '__pycache__', 'venv', 'node_modules', '.env', '.idea']:
                    continue
                full_path = os.path.join(path, item)
                child = QTreeWidgetItem(parent_item)
                child.setText(0, item)
                child.setData(0, Qt.ItemDataRole.UserRole, full_path)
                if os.path.isdir(full_path):
                    self._cargar_directorio(child, full_path)
                    child.setExpanded(True)
                else:
                    if item.endswith(('.py')):
                        child.setText(0, f"🐍 {item}")
                    elif item.endswith(('.html', '.htm')):
                        child.setText(0, f"🌐 {item}")
                    elif item.endswith(('.js')):
                        child.setText(0, f"📜 {item}")
                    elif item.endswith(('.css')):
                        child.setText(0, f"🎨 {item}")
                    elif item.endswith(('.json')):
                        child.setText(0, f"📋 {item}")
                    elif item.endswith(('.md')):
                        child.setText(0, f"📝 {item}")
        except Exception as e:
            self.log(f"Error cargando directorio: {e}", "error")

    def _abrir_archivo(self, item, column):
        ruta = item.data(0, Qt.ItemDataRole.UserRole)
        if not ruta or os.path.isdir(ruta):
            return
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                contenido = f.read()
            self.current_file = ruta
            self.code_editor.setText(contenido)
            nombre = os.path.basename(ruta)
            self.tab_widget.setTabText(0, f"📄 {nombre}")
            self.set_status(f"Editando: {nombre}")
            if ruta.endswith(('.html', '.htm')):
                self._actualizar_preview(contenido)
            self.log(f"📄 Abierto: {nombre}", "info")
        except Exception as e:
            self.log(f"Error abriendo archivo: {e}", "error")

    def _abrir_archivo_por_nombre(self, nombre):
        def buscar(item):
            if item.text(0) == nombre or item.text(0).endswith(nombre):
                return item
            for i in range(item.childCount()):
                resultado = buscar(item.child(i))
                if resultado:
                    return resultado
            return None
        root = self.tree_archivos.topLevelItem(0)
        if not root:
            return
        item = buscar(root)
        if item:
            self.tree_archivos.setCurrentItem(item)
            self._abrir_archivo(item, 0)

    def _guardar_archivo(self):
        if not self.current_file:
            QMessageBox.warning(self, "Guardar", "No hay un archivo abierto para guardar.")
            return
        contenido = self.code_editor.toPlainText()
        try:
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(contenido)
            nombre = os.path.basename(self.current_file)
            self.log(f"💾 Guardado: {nombre}", "success")
            self.set_status(f"Guardado: {nombre}")
            if self.current_file.endswith(('.html', '.htm')):
                self._actualizar_preview(contenido)
        except Exception as e:
            self.log(f"Error guardando: {e}", "error")
            QMessageBox.critical(self, "Error", f"No se pudo guardar el archivo:\n{e}")

    def _actualizar_preview(self, contenido):
        try:
            self.preview_label.setText(
                "🌐 Vista previa HTML\n\n"
                "(Para ver la vista previa completa, abre el proyecto en un navegador)"
            )
        except Exception as e:
            self.log(f"Error en preview: {e}", "error")

    def _ejecutar_proyecto(self):
        if not self.current_project_path:
            QMessageBox.warning(self, "Ejecutar", "No hay un proyecto abierto.")
            return
        index = Path(self.current_project_path) / "index.html"
        if not index.exists():
            QMessageBox.warning(self, "Ejecutar", "No se encontró index.html")
            return
        webbrowser.open(f"file://{index}")
        self.log("🚀 Proyecto ejecutado en el navegador", "success")

    def _abrir_vscode(self):
        if not self.current_project_path:
            QMessageBox.warning(self, "VS Code", "No hay un proyecto abierto.")
            return
        try:
            subprocess.Popen(["code", self.current_project_path], shell=True)
            self.log("📝 VS Code abierto", "success")
        except Exception as e:
            self.log(f"Error abriendo VS Code: {e}", "error")
            QMessageBox.warning(self, "VS Code", f"No se pudo abrir VS Code:\n{e}")

    def _load_config(self):
        config_path = Path.home() / ".apolo_dev_config.json"
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                if config.get("ultimo_proyecto") and os.path.exists(config["ultimo_proyecto"]):
                    self.current_project_path = config["ultimo_proyecto"]
                    self._cargar_arbol()
                    self.set_status(f"Proyecto: {Path(self.current_project_path).name}")
            except Exception:
                pass

    def _save_config(self):
        config_path = Path.home() / ".apolo_dev_config.json"
        try:
            config = {"ultimo_proyecto": self.current_project_path}
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except Exception:
            pass

    def closeEvent(self, event):
        self._save_config()
        event.accept()


# ===== FUNCIÓN DE PUNTO DE ENTRADA =====

def iniciar_developer_gui():
    """Inicia la interfaz de desarrollo."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    gui = DeveloperGUI()
    gui.show()
    return gui


if __name__ == "__main__":
    gui = iniciar_developer_gui()
    if gui:
        sys.exit(QApplication.instance().exec())