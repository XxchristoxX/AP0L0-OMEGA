from datetime import datetime
import hashlib
import json
import logging
import os
import shutil
import subprocess
import zipfile
# Configuración de logging para depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
def calculate_file_hash(filepath):
    """Calcula el hash SHA-256 de un archivo para detectar duplicados."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()
    except Exception as e:
        logging.error(f"Error leyendo {filepath} para hash: {e}")
        return None
def run(params):
    """Ejecuta la habilidad de auditoría, limpieza y compresión segura de documentos antiguos.
    Parámetros esperados en el diccionario 'params':
    - target_dir (str): Directorio base a auditar y limpiar.
    - days_old (int): Antigüedad en días para considerar un documento como
    antiguo (por defecto 365).
    - output_zip (str): Ruta del archivo zip resultante para los documentos
    comprimidos.
    """
    target_dir = params.get("target_dir", "./documentos_prueba")
    days_old = params.get("days_old", 365)
    output_zip = params.get("output_zip", "./archivos_antiguos_respaldo.zip")
    report = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "target_directory": target_dir,
        "duplicates_found": 0,
        "files_compressed": 0,
        "actions_taken": [],
        "errors": [],
    }
    if not os.path.exists(target_dir):
        report["status"] = "error"
        report["errors"].append(
            f"El directorio objetivo {target_dir} no existe."
        )
        return report
    seen_hashes = {}
    current_time = datetime.now().timestamp()
    age_threshold = days_old * 86400  # Convertir días a segundos
    files_to_compress = []
    logging.info(
        f"Iniciando auditoría y limpieza en el directorio: {target_dir}"
    )
    try:
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                filepath = os.path.join(root, file)
                # Ignorar el propio archivo zip de salida si está dentro del directorio
                if os.path.abspath(filepath) == os.path.abspath(output_zip):
                    continue
                try:
                    file_stat = os.stat(filepath)
                    file_mtime = file_stat.st_mtime
                except Exception as e:
                    error_msg = (
                        f"No se pudieron obtener metadatos de {filepath}: {e}"
                    )
                    logging.error(error_msg)
                    report["errors"].append(error_msg)
                    continue
                # 1. Auditoría de Duplicados (No destructiva: solo registra o sugiere)
                file_hash = calculate_file_hash(filepath)
                if file_hash:
                    if file_hash in seen_hashes:
                        report["duplicates_found"] += 1
                        report["actions_taken"].append({
                            "action": "duplicate_detected",
                            "file": filepath,
                            "duplicate_of": seen_hashes[file_hash],
                        })
                        logging.warning(
                            f"Duplicado detectado: {filepath} es idéntico a {seen_hashes[file_hash]}"
                        )
                    else:
                        seen_hashes[file_hash] = filepath
                # 2. Identificación de Documentos Antiguos para Compresión Defensiva
                if (current_time - file_mtime) > age_threshold:
                    files_to_compress.append(filepath)
        # 3. Compresión segura de documentos antiguos
        if files_to_compress:
            with zipfile.ZipFile(
                output_zip, "w", zipfile.ZIP_DEFLATED
            ) as zipf:
                for file_to_zip in files_to_compress:
                    arcname = os.path.relpath(file_to_zip, target_dir)
                    zipf.write(file_to_zip, arcname)
                    report["files_compressed"] += 1
                    report["actions_taken"].append({
                        "action": "compressed",
                        "file": file_to_zip,
                        "archive": output_zip,
                    })
                    logging.info(f"Documento antiguo comprimido: {file_to_zip}")
        else:
            logging.info("No se encontraron documentos antiguos para comprimir.")
        report["summary"] = (
            f"Auditoría completada. Duplicados: {report['duplicates_found']}, "
            f"Archivos comprimidos: {report['files_compressed']}."
        )
    except Exception as e:
        error_msg = f"Error crítico durante la ejecución del módulo: {e}"
        logging.error(error_msg)
        report["status"] = "error"
        report["errors"].append(error_msg)
    return report