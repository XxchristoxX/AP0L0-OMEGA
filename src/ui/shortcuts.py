# src/ui/shortcuts.py
from PyQt6.QtGui import QKeySequence, QShortcut

class ShortcutsHandler:
    def __init__(self, main_window):
        self.main = main_window

    def setup_shortcuts(self):
        sc_mute = QShortcut(QKeySequence("F4"), self.main)
        sc_mute.activated.connect(self.main._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"), self.main)
        sc_full.activated.connect(self.main._toggle_fullscreen)
        sc_intr = QShortcut(QKeySequence("Escape"), self.main)
        sc_intr.activated.connect(self.main._do_interrupt)