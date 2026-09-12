# src/actions/color_palette.py
"""
Extrae paletas de colores de imágenes usando Colorthief.
"""
import os
from pathlib import Path

try:
    from colorthief import ColorThief
    _COLORTHIEF_AVAILABLE = True
except ImportError:
    _COLORTHIEF_AVAILABLE = False


def extract_color_palette(image_path: str, num_colors: int = 5) -> str:
    """
    Extrae una paleta de colores de una imagen.

    Args:
        image_path: Ruta a la imagen.
        num_colors: Número de colores a extraer (máximo 10).

    Returns:
        Lista de colores en formato hexadecimal, o mensaje de error.
    """
    if not _COLORTHIEF_AVAILABLE:
        return "Error: Librería 'colorthief' no instalada. Ejecuta: pip install colorthief"

    if not os.path.exists(image_path):
        return f"Error: Imagen no encontrada en {image_path}"

    try:
        color_thief = ColorThief(image_path)
        palette = color_thief.get_palette(color_count=min(num_colors, 10), quality=1)
        # Convertir RGB a Hex
        hex_palette = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in palette]
        return "Paleta de colores extraída:\n" + "\n".join(hex_palette)
    except Exception as e:
        return f"Error al extraer la paleta: {e}"