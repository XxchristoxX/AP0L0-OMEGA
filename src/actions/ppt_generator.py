# src/actions/ppt_generator.py
"""
Generador de presentaciones PowerPoint para AP0L0.
Delega en Agata Creator.
"""
import os
from pathlib import Path

from src.actions.agata_creator import agata_create


def generate_ppt_presentation(
    title: str,
    slides: list,
    output_path: str = None,
    palette: str = "moderno",
) -> str:
    """
    Genera una presentación PowerPoint.

    Args:
        title: Título de la presentación.
        slides: Lista de strings, cada uno representa el contenido de una diapositiva.
        output_path: Ruta de salida (opcional).
        palette: Nombre de la paleta de colores.

    Returns:
        Ruta del archivo generado o mensaje de error.
    """
    if not title or not slides:
        return "Faltan el título o las diapositivas para generar la presentación."

    # Unir las diapositivas con el separador que espera agata_creator
    content = "\n---\n".join(slides)

    params = {
        "type": "ppt",
        "title": title,
        "topic": content,
        "palette": palette,
    }

    if output_path:
        result = agata_create(params)
        # Extraer y mover el archivo (similar a word_generator)
        if "Archivo:" in result:
            import re
            match = re.search(r"Archivo:\s*([^\n]+)", result)
            if match:
                src_filename = match.group(1).strip()
                src_path = Path.home() / "Documents" / "Agata_Projects" / src_filename
                if src_path.exists():
                    dest_path = Path(output_path)
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    if dest_path.is_dir():
                        dest_path = dest_path / src_filename
                    os.rename(str(src_path), str(dest_path))
                    return f"Presentación guardada en: {dest_path}"
        return result
    else:
        return agata_create(params)