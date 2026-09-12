# src/actions/word_generator.py
"""
Generador de documentos Word para AP0L0.
Delega en Agata Creator para el diseño y contenido.
"""
import os
from pathlib import Path

from src.actions.agata_creator import agata_create


def generate_word_document(
    title: str,
    content: str,
    output_path: str = None,
    palette: str = "elegant",
) -> str:
    """
    Genera un documento Word profesional.

    Args:
        title: Título del documento.
        content: Contenido en texto plano (estructurado con #, -, etc.).
        output_path: Ruta de salida (opcional).
        palette: Nombre de la paleta de colores.

    Returns:
        Ruta del archivo generado o mensaje de error.
    """
    if not title or not content:
        return "Faltan el título o el contenido para generar el documento."

    params = {
        "type": "word",
        "title": title,
        "topic": content,
        "palette": palette,
    }

    if output_path:
        # Agata Creator usa su propia carpeta (Documentos/Agata_Projects)
        # Pasamos el parámetro como sugerencia, pero si no, lo guarda en su carpeta.
        # Podemos modificar agata_creator para aceptar output_path, pero es más sencillo
        # mover el archivo después.
        result = agata_create(params)
        # Si el resultado contiene la ruta, podemos intentar moverlo
        if "Archivo:" in result:
            # Extraer nombre del archivo
            import re
            match = re.search(r"Archivo:\s*([^\n]+)", result)
            if match:
                src_filename = match.group(1).strip()
                src_path = Path.home() / "Documents" / "Agata_Projects" / src_filename
                if src_path.exists():
                    dest_path = Path(output_path)
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    # Si es directorio, concatenar nombre
                    if dest_path.is_dir():
                        dest_path = dest_path / src_filename
                    os.rename(str(src_path), str(dest_path))
                    return f"Documento guardado en: {dest_path}"
        return result
    else:
        return agata_create(params)