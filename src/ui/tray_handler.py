# src/ui/tray_handler.py
from pathlib import Path
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PyQt6.QtGui import QIcon, QAction, QPixmap, QColor
from src.utils.i18n import tr

class TrayHandler:
    def __init__(self, main_window):
        self.main = main_window
        self.tray_icon = None

    def create_icon(self):
        icon_path = self.main._face_path if Path(self.main._face_path).exists() else "face.png"
        if not Path(icon_path).exists():
            pix = QPixmap(64, 64)
            pix.fill(QColor("#00d4ff"))
            self.tray_icon = QSystemTrayIcon(QIcon(pix), self.main)
        else:
            self.tray_icon = QSystemTrayIcon(QIcon(icon_path), self.main)
        self.tray_icon.setToolTip("AP0L0 Assistant")

        tray_menu = QMenu()
        show_action = QAction(tr("Mostrar"), self.main)
        show_action.triggered.connect(self.main.showNormal)
        tray_menu.addAction(show_action)

        restart_action = QAction(tr("REINICIAR ASISTENTE"), self.main)
        restart_action.triggered.connect(self.main._restart_assistant)
        tray_menu.addAction(restart_action)

        tray_menu.addSeparator()

        exit_action = QAction(tr("Salir"), self.main)
        exit_action.triggered.connect(self._exit_app)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self._tray_activated)

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.main.showNormal()
            self.main.raise_()

    def _exit_app(self):
        reply = QMessageBox.question(
            self.main, tr("Salir"),
            "¿Estás seguro de que quieres cerrar AP0L0?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.main._cleanup_timers()
            QApplication.quit()

    def close_event(self, event):
        # Primer diálogo: minimizar o salir
        reply = QMessageBox.question(
            self.main,
            tr("Minimizar"),
            "¿Minimizar a la bandeja o salir?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Minimizar a la bandeja
            event.ignore()
            self.main.hide()
            self.tray_icon.showMessage(
                "AP0L0",
                "El asistente sigue ejecutándose en segundo plano.",
                QSystemTrayIcon.MessageIcon.Information, 2000
            )
        elif reply == QMessageBox.StandardButton.No:
            # Confirmar salida con un segundo diálogo
            confirm_reply = QMessageBox.question(
                self.main,
                tr("Salir"),
                "¿Estás seguro de que quieres cerrar AP0L0?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm_reply == QMessageBox.StandardButton.Yes:
                # Cerrar definitivamente
                self.main._cleanup_timers()
                QApplication.quit()
            else:
                # Cancelar cierre
                event.ignore()
        else:
            # Cancelar (opción Cancelar)
            event.ignore()