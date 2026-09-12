# src/actions/file_analyzer.py
import os
import hashlib
from pathlib import Path
import json
import shutil
from collections import defaultdict

class FileAnalyzer:
    def __init__(self):
        pass

    def calculate_md5(self, file_path):
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return None

    def find_duplicates(self, directory, min_size=1024):
        """
        Encuentra archivos duplicados por MD5 en un directorio.
        """
        duplicates = defaultdict(list)
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.getsize(file_path) < min_size:
                    continue
                md5 = self.calculate_md5(file_path)
                if md5:
                    duplicates[md5].append(file_path)
        return {k: v for k, v in duplicates.items() if len(v) > 1}

    def organize_by_type(self, directory):
        """Organiza archivos en subcarpetas por tipo."""
        type_map = {
            "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"],
            "Documents": [".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp"],
            "Videos": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"],
            "Music": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
            "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
            "Code": [".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".cpp", ".java", ".cs", ".go", ".rs"],
        }

        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()
                moved = False
                for folder, exts in type_map.items():
                    if ext in exts:
                        dest_dir = os.path.join(directory, folder)
                        os.makedirs(dest_dir, exist_ok=True)
                        dest_path = os.path.join(dest_dir, file)
                        counter = 1
                        while os.path.exists(dest_path):
                            base, ext2 = os.path.splitext(file)
                            dest_path = os.path.join(dest_dir, f"{base}_{counter}{ext2}")
                            counter += 1
                        shutil.move(file_path, dest_path)
                        moved = True
                        break
                if not moved:
                    dest_dir = os.path.join(directory, "Others")
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.move(file_path, os.path.join(dest_dir, file))
        return f"Archivos organizados en {directory}."

    def clean_duplicates(self, duplicates, keep="first"):
        """
        Elimina archivos duplicados, manteniendo el primero o el más nuevo.
        keep: "first" (primero encontrado) o "latest" (más reciente)
        """
        removed = []
        for md5, files in duplicates.items():
            if keep == "first":
                keep_file = files[0]
                for f in files[1:]:
                    os.remove(f)
                    removed.append(f)
            elif keep == "latest":
                latest = max(files, key=lambda x: os.path.getmtime(x))
                for f in files:
                    if f != latest:
                        os.remove(f)
                        removed.append(f)
        return f"Eliminados {len(removed)} archivos duplicados."


def file_analyzer(parameters: dict, player=None, speak=None) -> str:
    analyzer = FileAnalyzer()
    action = parameters.get("action", "find_duplicates")
    directory = parameters.get("directory", str(Path.home() / "Downloads"))
    min_size = int(parameters.get("min_size", 1024))
    keep = parameters.get("keep", "first")

    if action == "find_duplicates":
        duplicates = analyzer.find_duplicates(directory, min_size)
        if not duplicates:
            return f"No se encontraron duplicados en {directory}."
        result = f"Duplicados en {directory}:\n"
        for md5, files in duplicates.items():
            result += f"MD5: {md5}\n"
            for f in files:
                result += f"  - {f}\n"
        return result

    elif action == "organize":
        return analyzer.organize_by_type(directory)

    elif action == "clean_duplicates":
        duplicates = analyzer.find_duplicates(directory, min_size)
        if not duplicates:
            return "No hay duplicados para limpiar."
        return analyzer.clean_duplicates(duplicates, keep)

    else:
        return f"Acción '{action}' no soportada. Usa: find_duplicates, organize, clean_duplicates"