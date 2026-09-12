# src/ui/ui_constants.py
try:
    from src.config.settings import CONFIG_DIR
except ImportError:  # compatibilidad con lanzadores antiguos
    from config.settings import CONFIG_DIR

WALLPAPER_DIR = CONFIG_DIR / "wallpapers"
_DEFAULT_ICON_PATH = "face.png"
