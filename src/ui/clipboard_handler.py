# src/ui/clipboard_handler.py
import threading
from PyQt6.QtWidgets import QApplication

class ClipboardHandler:
    def __init__(self, main_window):
        self.main = main_window
        self._clipboard_panel = main_window._clipboard_panel
        self._clipboard_panel.action_requested.connect(self._on_clipboard_action)
        QApplication.clipboard().dataChanged.connect(self._on_clipboard_changed)

    def _on_clipboard_changed(self):
        try:
            text = QApplication.clipboard().text().strip()
            if len(text) >= 10:
                self.main._clipboard_sig.emit(text)
        except Exception:
            pass

    def show_clipboard_panel(self, text: str):
        self._clipboard_panel.show_clipboard(text)
        self._position_clipboard_panel()

    def _position_clipboard_panel(self):
        cw = self.main.centralWidget()
        pw = self._clipboard_panel._W
        ph = self._clipboard_panel.sizeHint().height() or self._clipboard_panel._H
        x = (cw.width() - pw) // 2
        y = cw.height() - ph - 6
        self._clipboard_panel.setGeometry(x, y, pw, ph)
        self._clipboard_panel.raise_()

    def _on_clipboard_action(self, cmd: str):
        if self.main.on_text_command:
            threading.Thread(target=self.main.on_text_command, args=(cmd,), daemon=True).start()