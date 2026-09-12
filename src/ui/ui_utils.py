# src/ui/ui_utils.py
# Utilidades compartidas entre ui.py y customize_overlay.py (colores, temas, config, brand)

import json
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QLinearGradient, QPainter
from PyQt6.QtWidgets import QApplication

try:
    from src.config.settings import API_FILE, CONFIG_DIR
except ImportError:  # compatibilidad con lanzadores antiguos que exponen config
    from config.settings import API_FILE, CONFIG_DIR

# =====================================================================
# PALETA DE COLORES Y MAPA DE PERSONALIDAD
# =====================================================================

class C:
    BG        = "#00020d"
    BG_DEEP   = "#000108"
    BORDER    = "#0d2444"
    BORDER_B  = "#1a5a99"
    BORDER_A  = "#0f3a66"
    PRI       = "#00d4ff"
    PRI_DIM   = "#0077aa"
    PRI_GHO   = "#001a2e"
    ACC       = "#ff8800"
    ACC2      = "#ffe066"
    GREEN     = "#00ffaa"
    GREEN_D   = "#00aa66"
    RED       = "#ff2244"
    MUTED_C   = "#ff2266"
    TEXT      = "#66eeff"
    TEXT_DIM  = "#1a5577"
    TEXT_MED  = "#33aacc"
    WHITE     = "#ccf4ff"
    DARK      = "#01060f"
    BAR_BG    = "#020f1e"
    STAR      = "#4477bb"
    NEBULA    = "#080835"
    NEBULA2   = "#030a28"
    AURORA    = "#00ccaa"
    COSMIC    = "#4400cc"
    GLASS_BG  = "rgba(0, 8, 22, 220)"
    GLASS_BDR = "rgba(0, 140, 220, 150)"
    PLANET    = "#0a1a44"
    RING1     = "#00aaff"
    RING2     = "#0055cc"
    ENERGY    = "#00ffee"
    PANEL     = "#010d14"
    PANEL2    = "#001218"
    WARNING   = "#ff8800"
    BLUE      = "#0077ff"

_JARVIS_THEME = {
    "BG": "#00020d", "BG_DEEP": "#000108", "BORDER": "#0d2444", "BORDER_B": "#1a5a99",
    "BORDER_A": "#0f3a66", "PRI": "#00d4ff", "PRI_DIM": "#0077aa", "PRI_GHO": "#001a2e",
    "ACC": "#ff8800", "ACC2": "#ffe066", "GREEN": "#00ffaa", "GREEN_D": "#00aa66",
    "RED": "#ff2244", "MUTED_C": "#ff2266", "TEXT": "#66eeff", "TEXT_DIM": "#1a5577",
    "TEXT_MED": "#33aacc", "WHITE": "#ccf4ff", "DARK": "#01060f", "BAR_BG": "#020f1e",
    "STAR": "#4477bb", "NEBULA": "#080835", "NEBULA2": "#030a28",
    "AURORA": "#00ccaa", "COSMIC": "#4400cc",
    "PLANET": "#0a1a44", "RING1": "#00aaff", "RING2": "#0055cc", "ENERGY": "#00ffee",
}
_AGATA_THEME = {
    "BG": "#080010", "BG_DEEP": "#050008", "BORDER": "#3a0835", "BORDER_B": "#aa1177",
    "BORDER_A": "#770d55", "PRI": "#ff44cc", "PRI_DIM": "#aa0077", "PRI_GHO": "#280020",
    "ACC": "#ff5599", "ACC2": "#ffcc44", "GREEN": "#44ffaa", "GREEN_D": "#22aa66",
    "RED": "#ff1144", "MUTED_C": "#ff2266", "TEXT": "#ffaaee", "TEXT_DIM": "#883366",
    "TEXT_MED": "#cc55aa", "WHITE": "#ffe0f8", "DARK": "#0d0010", "BAR_BG": "#18001e",
    "STAR": "#dd88cc", "NEBULA": "#2a0028", "NEBULA2": "#150015",
    "AURORA": "#ff0099", "COSMIC": "#cc00ff",
    "PLANET": "#2a0030", "RING1": "#ff44dd", "RING2": "#aa0088", "ENERGY": "#ff88ff",
}
_TONY_THEME = {
    "BG": "#0d0800", "BG_DEEP": "#080400", "BORDER": "#3a2a08", "BORDER_B": "#aa6611",
    "BORDER_A": "#77440d", "PRI": "#ff6b00", "PRI_DIM": "#aa4400", "PRI_GHO": "#281800",
    "ACC": "#ff8800", "ACC2": "#ffcc00", "GREEN": "#44ffaa", "GREEN_D": "#22aa66",
    "RED": "#ff2244", "MUTED_C": "#ff2266", "TEXT": "#ffaa66", "TEXT_DIM": "#885533",
    "TEXT_MED": "#cc8833", "WHITE": "#f0e0c0", "DARK": "#0d0800", "BAR_BG": "#1a1000",
    "STAR": "#dd8844", "NEBULA": "#2a1a00", "NEBULA2": "#150d00",
    "AURORA": "#ff4400", "COSMIC": "#ff2200",
    "PLANET": "#2a1a00", "RING1": "#ff8833", "RING2": "#aa4400", "ENERGY": "#ffaa33",
}
_FRIDAY_THEME = {
    "BG": "#0a0010", "BG_DEEP": "#050008", "BORDER": "#2a083a", "BORDER_B": "#7711aa",
    "BORDER_A": "#550d77", "PRI": "#9b59b6", "PRI_DIM": "#6a2a8a", "PRI_GHO": "#1a0028",
    "ACC": "#aa55ff", "ACC2": "#dd88ff", "GREEN": "#44ffaa", "GREEN_D": "#22aa66",
    "RED": "#ff1144", "MUTED_C": "#ff2266", "TEXT": "#cc88ee", "TEXT_DIM": "#663388",
    "TEXT_MED": "#9955aa", "WHITE": "#f0d8ff", "DARK": "#0a0010", "BAR_BG": "#12001a",
    "STAR": "#bb88dd", "NEBULA": "#2a0028", "NEBULA2": "#150015",
    "AURORA": "#8800ff", "COSMIC": "#cc00ff",
    "PLANET": "#2a0030", "RING1": "#bb44ff", "RING2": "#7700aa", "ENERGY": "#cc88ff",
}
_APOLO_THEME = {
    "BG": "#000d08", "BG_DEEP": "#000804", "BORDER": "#083a22", "BORDER_B": "#11aa55",
    "BORDER_A": "#0d7733", "PRI": "#00ff88", "PRI_DIM": "#00aa55", "PRI_GHO": "#002818",
    "ACC": "#44ff88", "ACC2": "#aaff88", "GREEN": "#00ffaa", "GREEN_D": "#00aa66",
    "RED": "#ff2244", "MUTED_C": "#ff2266", "TEXT": "#66ffaa", "TEXT_DIM": "#338855",
    "TEXT_MED": "#55cc88", "WHITE": "#c0ffe0", "DARK": "#000d08", "BAR_BG": "#001a10",
    "STAR": "#44dd88", "NEBULA": "#002a18", "NEBULA2": "#00150d",
    "AURORA": "#00ffaa", "COSMIC": "#00cc88",
    "PLANET": "#002a20", "RING1": "#33ffaa", "RING2": "#00aa66", "ENERGY": "#88ffcc",
}

def apply_ui_accent(hex_color: str) -> bool:
    if not hex_color.startswith("#") or len(hex_color) != 7:
        return False
    try:
        int(hex_color[1:], 16)
    except ValueError:
        return False
    C.PRI = hex_color
    return True

def current_palette() -> dict:
    keys = [
        "BG", "BG_DEEP", "BORDER", "BORDER_B", "BORDER_A", "PRI", "PRI_DIM", "PRI_GHO",
        "ACC", "ACC2", "GREEN", "GREEN_D", "RED", "MUTED_C", "TEXT", "TEXT_DIM",
        "TEXT_MED", "WHITE", "DARK", "BAR_BG", "STAR", "NEBULA", "NEBULA2",
        "AURORA", "COSMIC", "PLANET", "RING1", "RING2", "ENERGY", "PANEL", "PANEL2", "WARNING",
        "BLUE",
    ]
    return {k: getattr(C, k) for k in keys}

def retheme_all_widgets(old: dict, new: dict):
    mapping = {old[k].lower(): new[k].lower() for k in old if old[k].lower() != new.get(k, old[k]).lower()}
    if not mapping:
        return
    app = QApplication.instance()
    if app is None:
        return
    for w in app.allWidgets():
        try:
            ss = w.styleSheet()
            if ss:
                s2 = ss
                for o, n in mapping.items():
                    if o in s2:
                        s2 = s2.replace(o, n)
                if s2 != ss:
                    w.setStyleSheet(s2)
            w.update()
        except Exception:
            pass

def apply_theme(name: str):
    if name == "agata":
        theme = _AGATA_THEME
    elif name == "tony":
        theme = _TONY_THEME
    elif name == "friday":
        theme = _FRIDAY_THEME
    elif name == "apolo":
        theme = _APOLO_THEME
    else:
        theme = _JARVIS_THEME
    old = current_palette()
    for k, v in theme.items():
        setattr(C, k, v)
    retheme_all_widgets(old, current_palette())

def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h)
    c.setAlpha(a)
    return c

# =====================================================================
# CARGA DE CONFIGURACIÓN DE BRAND (WHITE-LABEL)
# =====================================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def load_brand_config() -> dict:
    """Carga la configuración de branding desde config/brand.json."""
    brand_path = BASE_DIR / "config" / "brand.json"
    defaults = {
        "assistant_name": "AP0L0",
        "assistant_title": "Autonomous Platform for Orchestration, Learning and Operations",
        "wake_phrases": ["apolo", "jarvis", "asistente"],
        "primary_color": "#00ff88",
        "secondary_color": "#00d4ff",
        "accent_color": "#ff8800",
        "warning_color": "#ff2244",
        "logo_path": "face.png",
        "footer_text": "By XxchristoxX",
        "default_voice": "Charon",
        "default_personality": "apolo",
        "default_theme": "#00ff88",
        "enable_animations": True,
        "enable_sounds": True,
    }
    if brand_path.exists():
        try:
            data = json.loads(brand_path.read_text(encoding="utf-8"))
            # Combinar con defaults (los valores del archivo sobreescriben)
            merged = defaults.copy()
            merged.update(data)
            return merged
        except Exception as e:
            print(f"[UI] Error cargando brand.json: {e}")
            return defaults
    return defaults

# =====================================================================
# CONFIGURACIÓN (EXISTENTE)
# =====================================================================

def _read_full_config() -> dict:
    defaults = {
        "assistant_name": "APOLO",
        "assistant_subtitle": "Autonomous Platform for Orchestration, Learning and Operations",
        "user_name": "Christopher",
        "ui_color": "#00ff88",
        "ui_main_bg": "#00060a",
        "ui_log_bg": "#010d14",
        "ui_log_text": "#8ffcff",
        "ui_news_bg": "#010f18",
        "ui_news_text": "#5ab8cc",
        "ui_input_bg": "#000d14",
        "ui_input_text": "#d8f8ff",
        "ui_button_bg": "#00ff88",
        "ui_button_text": "#000000",
        "ui_title_color": "#00ff88",
        "ui_status_color": "#00ff88",
        "ui_border_color": "#0d3347",
        "ui_font_size": 10,
        "ui_icon_path": "face.png",
        "shortcut_name": "APOLO AI",
        "shortcut_icon": "",
        "os_system": "windows",
        "ui_language": "es",
        "font_size_header": 10,
        "font_size_left": 10,
        "font_size_right": 10,
        "font_size_center": 10,
        "font_size_footer": 10,
        "badge1_text": "AI CORE ACTIVE",
        "badge2_text": "SEC CLEARED",
        "badge3_text": "PROTOCOL XLIX",
        "badge4_text": "READY",
        "badge5_text": "ONLINE",
        "badge1_color": "#00ff88",
        "badge2_color": "#00d4ff",
        "badge3_color": "#5ab8cc",
        "badge4_color": "#ffcc00",
        "badge5_color": "#ff6b00",
        "wallpaper_path": "",
        "personality": "apolo",
        "voice": "Zephyr",
        "theme_name": "dark",
        "enable_animations": True,
        "enable_sounds": True,
        "show_timestamps": True,
        "auto_scroll_log": True,
        "sync_system_theme": False,
        "response_mode": "voice_text",
        "focus_mode": False,
        "vad_enabled": False,
        "rag_enabled": False,
    }
    try:
        if API_FILE.exists():
            data = json.loads(API_FILE.read_text(encoding="utf-8"))
            for k, v in defaults.items():
                if k not in data:
                    data[k] = v
            return data
        return defaults
    except Exception:
        return defaults

def _save_config(cfg: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        API_FILE.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
    except Exception as e:
        print(f"[UI] Error guardando configuración: {e}")
