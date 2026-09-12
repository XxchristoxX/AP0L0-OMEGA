# src/ui/theme_handler.py
import subprocess
import ctypes
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QGroupBox, QWidget
from PyQt6.QtGui import QFont

from src.ui.ui_utils import (
    C, apply_ui_accent, current_palette, retheme_all_widgets,
    apply_theme, qcol, _read_full_config, _save_config
)
try:
    from src.config.themes import THEME_MAP, DEFAULT_THEME
except ImportError:  # compatibilidad con ejecución antigua desde src/
    from config.themes import THEME_MAP, DEFAULT_THEME
from src.utils.system_utils import IS_WINDOWS, IS_MAC

class ThemeHandler:
    def __init__(self, main_window):
        self.main = main_window
        self._applying_theme = False

    def set_theme(self, accent_hex: str):
        # Capturar antes de cambiar la paleta. Si se captura después, old y
        # new son iguales y los widgets conservan los colores anteriores.
        old = current_palette()
        if apply_ui_accent(accent_hex):
            new = current_palette()
            retheme_all_widgets(old, new)
            self.apply_ui_colors()
            self.main._log.append_log(f"SYS: Theme changed to {accent_hex}")
            self.main._theme_changed.emit(accent_hex)
            if self.main.panel:
                self.main.panel.set_theme_color(accent_hex)

    def set_window_opacity(self, opacity: float):
        """
        Ajusta la opacidad de la ventana principal.
        opacity: valor entre 0.0 (transparente) y 1.0 (opaco)
        """
        if 0.0 <= opacity <= 1.0:
            self.main.setWindowOpacity(opacity)
            # Guardar en configuración
            cfg = _read_full_config()
            cfg["window_opacity"] = opacity
            _save_config(cfg)
            if hasattr(self.main, '_log'):
                self.main._log.append_log(f"SYS: Opacidad ajustada a {opacity:.2f}")

    def apply_ui_colors(self, cfg: dict = None):
        try:
            main_bg = C.BG
            log_bg = C.PANEL
            log_text = C.TEXT
            input_bg = C.PANEL
            input_text = C.TEXT
            border_color = C.BORDER
            ui_color = C.PRI
            title_color = C.PRI

            if self.main.centralWidget():
                self.main.centralWidget().setStyleSheet(f"background: {main_bg};")

            # ===== ACTUALIZAR ESTILOS DE LOS GRUPOS DEL PANEL IZQUIERDO =====
            if hasattr(self.main, '_left_panel') and self.main._left_panel is not None:
                grupo_style = f"""
                    QGroupBox {{
                        color: {ui_color};
                        border: 1px solid {C.BORDER_A};
                        border-radius: 4px;
                        margin-top: 12px;
                        padding-top: 8px;
                        font-weight: bold;
                        font-size: 8pt;
                    }}
                    QGroupBox::title {{
                        subcontrol-origin: margin;
                        left: 8px;
                        padding: 0 6px 0 6px;
                        background-color: {C.PANEL};
                        color: {ui_color};
                    }}
                """
                for child in self.main._left_panel.findChildren(QGroupBox):
                    child.setStyleSheet(grupo_style)

            # ===== ACTUALIZAR BADGES =====
            if hasattr(self.main, '_badge_labels'):
                cfg = cfg or _read_full_config()
                badge_colors = [
                    cfg.get("badge1_color", "#00ff88"),
                    cfg.get("badge2_color", "#00d4ff"),
                    cfg.get("badge3_color", "#5ab8cc"),
                    cfg.get("badge4_color", "#ffcc00"),
                    cfg.get("badge5_color", "#ff6b00"),
                ]
                for i, lbl in enumerate(self.main._badge_labels):
                    if i < len(badge_colors):
                        lbl.setStyleSheet(
                            f"color: {badge_colors[i]}; background: {C.PANEL2};"
                            f"border: 1px solid {C.BORDER_A}; border-radius: 3px; padding: 4px;"
                        )

            # ===== ACTUALIZAR BOTONES DE CONTROL (Apagar, Reiniciar, Suspender) =====
            if hasattr(self.main, 'shutdown_btn'):
                self.main.shutdown_btn.setStyleSheet(f"""
                    QPushButton {{
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 4px 2px;
                        font-weight: bold;
                        font-size: 7pt;
                        font-family: 'Segoe UI', 'Courier New', monospace;
                        background: #d32f2f !important;
                    }}
                    QPushButton:hover {{ opacity: 0.85; }}
                    QPushButton:pressed {{ opacity: 0.70; }}
                """)
            if hasattr(self.main, 'restart_btn'):
                self.main.restart_btn.setStyleSheet(f"""
                    QPushButton {{
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 4px 2px;
                        font-weight: bold;
                        font-size: 7pt;
                        font-family: 'Segoe UI', 'Courier New', monospace;
                        background: #f57c00 !important;
                    }}
                    QPushButton:hover {{ opacity: 0.85; }}
                    QPushButton:pressed {{ opacity: 0.70; }}
                """)
            if hasattr(self.main, 'sleep_btn'):
                self.main.sleep_btn.setStyleSheet(f"""
                    QPushButton {{
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 4px 2px;
                        font-weight: bold;
                        font-size: 7pt;
                        font-family: 'Segoe UI', 'Courier New', monospace;
                        background: #1976d2 !important;
                    }}
                    QPushButton:hover {{ opacity: 0.85; }}
                    QPushButton:pressed {{ opacity: 0.70; }}
                """)

            # ===== ACTUALIZAR BOTONES DEL QUICK DRAWER =====
            if hasattr(self.main, '_quick_drawer') and self.main._quick_drawer is not None:
                btn_style_pri = f"""
                    QPushButton {{
                        background: #00091a;
                        color: {ui_color};
                        border: 1px solid {C.PRI_DIM};
                        border-radius: 4px;
                        text-align: left;
                        padding: 0 10px;
                    }}
                    QPushButton:hover {{
                        background: {C.PRI_GHO};
                        border-color: {ui_color};
                    }}
                """
                btn_style_dim = f"""
                    QPushButton {{
                        background: transparent;
                        color: {C.TEXT_MED};
                        border: 1px solid {C.BORDER};
                        border-radius: 4px;
                        text-align: left;
                        padding: 0 10px;
                    }}
                    QPushButton:hover {{
                        color: {ui_color};
                        border-color: {C.BORDER_B};
                    }}
                """
                for btn in self.main._quick_drawer.findChildren(QPushButton):
                    text = btn.text()
                    if "◉" in text or "⚙" in text or "◈" in text:
                        btn.setStyleSheet(btn_style_pri)
                    else:
                        btn.setStyleSheet(btn_style_dim)
                    btn.update()

                # Actualizar el título "◈ CONTROLS"
                for lbl in self.main._quick_drawer.findChildren(QLabel):
                    if "◈" in lbl.text() and "CONTROLS" in lbl.text():
                        lbl.setStyleSheet(f"color: {ui_color}; background: transparent; border-bottom: 1px solid {C.BORDER}; padding-bottom: 4px;")
                        lbl.update()

            # ===== ACTUALIZAR TÍTULOS DEL PANEL IZQUIERDO Y DERECHO =====
            if hasattr(self.main, '_left_panel_title'):
                self.main._left_panel_title.setStyleSheet(
                    f"color: {ui_color}; background: transparent; "
                    f"border-bottom: 1px solid {border_color}; padding: 6px 8px;"
                )
                self.main._left_panel_title.update()

            if hasattr(self.main, '_right_panel_title'):
                self.main._right_panel_title.setStyleSheet(
                    f"color: {ui_color}; background: transparent;"
                )
                self.main._right_panel_title.update()

            if hasattr(self.main, '_file_upload_label'):
                self.main._file_upload_label.setStyleSheet(
                    f"color: {ui_color}; background: transparent;"
                )
                self.main._file_upload_label.update()

            if hasattr(self.main, '_command_input_label'):
                self.main._command_input_label.setStyleSheet(
                    f"color: {ui_color}; background: transparent;"
                )
                self.main._command_input_label.update()

            # Forzar repintado del panel izquierdo
            if hasattr(self.main, '_left_panel') and self.main._left_panel is not None:
                for widget in self.main._left_panel.findChildren(QWidget):
                    widget.update()

            # Actualizar overlay de personalización si está abierto
            if hasattr(self.main, '_customize_overlay') and self.main._customize_overlay and self.main._customize_overlay.isVisible():
                self.main._customize_overlay._apply_styles()

            # ===== ACTUALIZAR LOG =====
            if hasattr(self.main, '_log') and self.main._log:
                self.main._log.setStyleSheet(f"""
                    QTextEdit {{
                        background: {log_bg};
                        color: {log_text};
                        border: 1px solid {border_color};
                        border-radius: 4px;
                        padding: 6px;
                        selection-background-color: {C.PRI_GHO};
                    }}
                    QScrollBar:vertical {{
                        background: {main_bg};
                        width: 8px;
                        border: none;
                    }}
                    QScrollBar::handle:vertical {{
                        background: {C.BORDER_B};
                        border-radius: 4px;
                        min-height: 20px;
                    }}
                """)

            # ===== ACTUALIZAR INPUT =====
            if hasattr(self.main, '_input') and self.main._input:
                self.main._input.setStyleSheet(f"""
                    QLineEdit {{
                        background: {input_bg}; color: {input_text};
                        border: 1px solid {border_color}; border-radius: 4px; padding: 4px 8px;
                    }}
                    QLineEdit:focus {{ border: 1px solid {ui_color}; }}
                """)

            # ===== ACTUALIZAR TÍTULO Y SUBTÍTULO =====
            if hasattr(self.main, '_title_lbl') and self.main._title_lbl:
                self.main._title_lbl.setStyleSheet(f"color: {title_color}; background: transparent;")

            if hasattr(self.main, '_sub_lbl') and self.main._sub_lbl:
                self.main._sub_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")

            # ===== ACTUALIZAR PANELES LATERALES =====
            if hasattr(self.main, '_left_panel') and self.main._left_panel:
                self.main._left_panel.setStyleSheet(f"background: {C.DARK}; border-right: 1px solid {border_color};")

            if hasattr(self.main, '_right_panel') and self.main._right_panel:
                self.main._right_panel.setStyleSheet(f"background: {C.DARK}; border-left: 1px solid {border_color};")

            # ===== ACTUALIZAR CONTENIDO =====
            if hasattr(self.main, '_content_title_lbl'):
                self.main._content_title_lbl.setStyleSheet(f"color: {ui_color}; background: transparent; letter-spacing: 1px; font-weight: bold;")
            if hasattr(self.main, '_content_dot'):
                self.main._content_dot.setStyleSheet(f"color: {ui_color}; background: transparent;")
            if hasattr(self.main, '_content_ts_lbl'):
                self.main._content_ts_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")

            # ===== ACTUALIZAR BOTÓN DE CONFIGURACIÓN (⚙) =====
            if hasattr(self.main, '_drawer_btn'):
                self.main._drawer_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 4px;
                    }}
                    QPushButton:hover {{ color: {C.PRI}; border-color: {C.PRI_DIM}; }}
                    QPushButton:checked {{ color: {C.PRI}; border-color: {C.PRI}; background: {C.PRI_GHO}; }}
                """)

            # ===== ACTUALIZAR BOTÓN DE INTERRUPCIÓN =====
            if hasattr(self.main, '_interrupt_btn'):
                self.main._interrupt_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #140008; color: {C.MUTED_C};
                        border: 1px solid {C.MUTED_C}; border-radius: 4px;
                    }}
                    QPushButton:hover {{ background: #200010; border: 1px solid #ff6688; }}
                    QPushButton:pressed {{ background: #300018; }}
                """)

            # ===== ACTUALIZAR FOOTER =====
            if hasattr(self.main, '_footer_widget') and self.main._footer_widget:
                self.main._footer_widget.setStyleSheet(f"background: {C.DARK}; border-top: 1px solid {border_color};")

            # ===== ACTUALIZAR BARRAS DEL SISTEMA (CPU, RAM, DISCOS) =====
            if hasattr(self.main, 'system_widget'):
                sw = self.main.system_widget
                # CPU -> Rojo
                if hasattr(sw, 'cpu_bar'):
                    sw.cpu_bar.set_color(C.BLUE)
                # RAM -> Naranja
                if hasattr(sw, 'ram_bar'):
                    sw.ram_bar.set_color(C.ACC)
                # Disco C: -> Azul (principal)
                if hasattr(sw, 'disk_c_bar'):
                    sw.disk_c_bar.set_color(C.PRI)
                # Discos D:, E:, F: -> Verde
                if hasattr(sw, 'disk_d_bar'):
                    sw.disk_d_bar.set_color(C.GREEN)
                if hasattr(sw, 'disk_e_bar'):
                    sw.disk_e_bar.set_color(C.GREEN)
                if hasattr(sw, 'disk_f_bar'):
                    sw.disk_f_bar.set_color(C.GREEN)

            # ===== ACTUALIZAR BADGES =====
            self.main._update_badges()

            # ===== ACTUALIZAR HUD =====
            if hasattr(self.main, 'hud') and self.main.hud:
                self.main.hud.update()

            # ===== ACTUALIZAR RELOJ Y FECHA =====
            if hasattr(self.main, '_clock_lbl'):
                self.main._clock_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
            if hasattr(self.main, '_date_lbl'):
                self.main._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")

            # ===== ACTUALIZAR CONTENIDO DISPLAY =====
            if hasattr(self.main, '_content_display'):
                self.main._content_display.setStyleSheet(f"""
                    QTextEdit {{
                        background: {C.DARK};
                        color: {C.TEXT};
                        border: 1px solid {C.BORDER};
                        border-radius: 4px;
                        padding: 6px 8px;
                        selection-background-color: {C.PRI_GHO};
                    }}
                    QScrollBar:vertical {{
                        background: {C.BG}; width: 6px; border: none;
                    }}
                    QScrollBar::handle:vertical {{
                        background: {C.BORDER_B}; border-radius: 3px; min-height: 16px;
                    }}
                """)

            # ===== ACTUALIZAR BOTÓN DE ENVÍO =====
            if hasattr(self.main, '_send_btn') and self.main._send_btn:
                self.main._send_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PANEL}; color: {C.PRI};
                        border: 1px solid {C.PRI_DIM}; border-radius: 4px;
                    }}
                    QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
                """)

            # ===== ACTUALIZAR OVERLAY DE PERSONALIZACIÓN =====
            if hasattr(self.main, '_customize_overlay') and self.main._customize_overlay and self.main._customize_overlay.isVisible():
                self.main._customize_overlay._apply_styles()

        except Exception as e:
            print(f"[UI] Error aplicando colores: {e}")

    def apply_font_sizes(self, font_cfg: dict):
        try:
            size = font_cfg.get("font_size_header", 10)
            self.main._title_lbl.setFont(QFont("Courier New", size + 6, QFont.Weight.Bold))
            self.main._sub_lbl.setFont(QFont("Courier New", size - 2))
            self.main._clock_lbl.setFont(QFont("Courier New", size + 4, QFont.Weight.Bold))
            self.main._date_lbl.setFont(QFont("Courier New", size - 2))

            size_l = font_cfg.get("font_size_left", 10)
            self.main._left_panel_title.setFont(QFont("Courier New", size_l - 2, QFont.Weight.Bold))
            for lbl in self.main._badge_labels:
                lbl.setFont(QFont("Courier New", size_l - 2, QFont.Weight.Bold))

            size_r = font_cfg.get("font_size_right", 10)
            self.main._right_panel_title.setFont(QFont("Courier New", size_r - 2, QFont.Weight.Bold))
            self.main._file_upload_label.setFont(QFont("Courier New", size_r - 2, QFont.Weight.Bold))
            self.main._command_input_label.setFont(QFont("Courier New", size_r - 2, QFont.Weight.Bold))
            self.main._input.setFont(QFont("Courier New", size_r))
            self.main._interrupt_btn.setFont(QFont("Courier New", size_r - 1, QFont.Weight.Bold))
            self.main._mute_btn.setFont(QFont("Courier New", size_r - 1, QFont.Weight.Bold))

            size_c = font_cfg.get("font_size_center", 10)
            self.main._content_title_lbl.setFont(QFont("Courier New", size_c - 1, QFont.Weight.Bold))
            self.main._content_display.setFont(QFont("Courier New", size_c - 1))

            size_f = font_cfg.get("font_size_footer", 10)
            for child in self.main._footer_widget.findChildren(QLabel):
                child.setFont(QFont("Courier New", size_f - 2))
            if hasattr(self.main, '_footer_clock_lbl'):
                self.main._footer_clock_lbl.setFont(QFont("Courier New", size_f - 2))
            if hasattr(self.main, '_footer_dashboard_lbl'):
                self.main._footer_dashboard_lbl.setFont(QFont("Courier New", size_f - 2))

            self.main._log.setFont(QFont("Courier New", size_c - 1))

        except Exception as e:
            print(f"[UI] Error aplicando fuentes: {e}")

    def apply_wallpaper(self, path: str):
        try:
            if IS_WINDOWS:
                ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 0)
            elif IS_MAC:
                script = f'''
                tell application "System Events"
                    tell every desktop
                        set picture to "{path}"
                    end tell
                end tell
                '''
                subprocess.run(["osascript", "-e", script], check=False)
            else:
                if Path("/usr/bin/gsettings").exists():
                    subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{path}"], check=False)
                elif Path("/usr/bin/plasma-apply-wallpaperimage").exists():
                    subprocess.run(["plasma-apply-wallpaperimage", path], check=False)
            self.main._log.append_log(f"SYS: Wallpaper aplicado: {Path(path).name}")
        except Exception as e:
            self.main._log.append_log(f"ERR: No se pudo aplicar wallpaper — {e}")

    def on_theme_changed(self, theme_hex: str):
        if self._applying_theme:
            return
        self._applying_theme = True
        try:
            QTimer.singleShot(0, lambda: self.set_theme(theme_hex))
            if hasattr(self.main, 'refresh_customize_overlay'):
                QTimer.singleShot(50, self.main.refresh_customize_overlay)
        finally:
            QTimer.singleShot(100, lambda: setattr(self, '_applying_theme', False))
