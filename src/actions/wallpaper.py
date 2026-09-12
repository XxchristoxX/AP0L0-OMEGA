# actions/wallpaper.py
import ctypes
import subprocess
import platform
from pathlib import Path

class WallpaperChanger:
    def __init__(self):
        self._os = platform.system()

    def change(self, image_path: str) -> str:
        path = Path(image_path).resolve()
        if not path.exists():
            return f"Imagen no encontrada: {image_path}"

        if self._os == "Windows":
            try:
                ctypes.windll.user32.SystemParametersInfoW(20, 0, str(path), 3)
                return f"Wallpaper cambiado a {path.name}"
            except Exception as e:
                return f"Error en Windows: {e}"

        elif self._os == "Darwin":
            script = f'tell application "System Events" to set picture of every desktop to POSIX file "{path}"'
            try:
                subprocess.run(["osascript", "-e", script], capture_output=True, check=True)
                return f"Wallpaper cambiado a {path.name}"
            except Exception as e:
                return f"Error en macOS: {e}"

        else:  # Linux – probar varios entornos
            try:
                # GNOME / Unity
                subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{path}"], check=True)
                return f"Wallpaper cambiado a {path.name}"
            except:
                try:
                    # KDE Plasma
                    script = f"""
                    var allDesktops = desktops();
                    for (var i = 0; i < allDesktops.length; i++) {{
                        d = allDesktops[i];
                        d.wallpaperPlugin = "org.kde.image";
                        d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
                        d.writeConfig("Image", "file://{path}");
                    }}
                    """
                    subprocess.run(["qdbus", "org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript", script], check=True)
                    return f"Wallpaper cambiado a {path.name}"
                except:
                    return "No se pudo cambiar el wallpaper en Linux. Prueba con 'feh' o manualmente."