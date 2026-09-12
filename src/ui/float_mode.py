# src/ui/float_mode.py
from PyQt6.QtWidgets import QApplication

class FloatModeHandler:
    def __init__(self, main_window):
        self.main = main_window

    def toggle_float_mode(self):
        if self.main.panel is None:
            self.main._log.append_log("SYS: Panel circular no disponible.")
            return

        if not self.main.floating_mode_active:
            self.main.hide()
            screen = QApplication.primaryScreen().availableGeometry()
            panel_width = self.main.panel.width()
            panel_height = self.main.panel.height()
            x = (screen.width() - panel_width) // 2
            y = (screen.height() - panel_height) // 2
            self.main.panel.move(x, y)
            self.main.panel.show()
            self.main.panel.raise_()
            self.main.panel.activateWindow()
            self.main.floating_mode_active = True
            self.main._log.append_log("SYS: Modo flotante activado (panel circular).")
        else:
            self.main.panel.hide()
            self.main.show()
            self.main.raise_()
            self.main.activateWindow()
            self.main.floating_mode_active = False
            self.main._log.append_log("SYS: Modo flotante desactivado.")

    def deactivate_float_mode(self):
        if self.main.floating_mode_active:
            self.main.panel.hide()
            self.main.show()
            self.main.raise_()
            self.main.floating_mode_active = False
            self.main._log.append_log("SYS: Modo flotante desactivado (panel cerrado).")