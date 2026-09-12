from datetime import datetime
import hashlib
import json
import logging
import os
import shutil
# Configuración de logging para depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("desorden_intervencin_manual")
def run(params):
    """Audita y clasifica de forma segura los archivos en un directorio de descargas
    para mantener el orden y verificar la integridad (seguridad defensiva).
    """
    download_dir = params.get(
        "target_dir", os.path.expanduser("~/Downloads")
    )
    destination_base = params.get(
        "destination_dir", os.path.expanduser("~/OrganizedDocs")
    )
    generate_report = params.get("generate_report", True)
    logger.info(f"Iniciando auditoría y clasificación en: {download_dir}")
    classification_rules = {
        "Documentos": [".pdf", ".docx", ".txt", ".xlsx", ".pptx", ".odt"],
        "Scripts_Codigo": [
            ".py",
            ".sh",
            ".js",
            ".html",
            ".cpp",
            ".json",
            ".sql",
        ],
        "Comprimidos": [".zip", ".tar", ".gz", ".rar", ".7z"],
        "Multimedia": [".mp4", ".mkv", ".mp3", ".jpg", ".png", ".gif"],
        "Ejecutables_Auditoria": [".exe", ".msi", ".deb", ".rpm", ".bin"],
    }
    processed_files = []
    errors = []
    try:
        if not os.path.exists(download_dir):
            raise FileNotFoundError(
                f"El directorio objetivo no existe: {download_dir}"
            )
        if not os.path.exists(destination_base):
            os.makedirs(destination_base, exist_ok=True)
            logger.info(f"Directorio base creado: {destination_base}")
        # Listar archivos en el directorio objetivo
        for filename in os.listdir(download_dir):
            file_path = os.path.join(download_dir, filename)
            if os.path.isdir(file_path):
                continue  # Solo procesar archivos individuales
            _, ext = os.path.splitext(filename)
            ext = ext.lower()
            target_category = "Otros"
            for category, extensions in classification_rules.items():
                if ext in extensions:
                    target_category = category
                    break
            category_dir = os.path.join(destination_base, target_category)
            os.makedirs(category_dir, exist_ok=True)
            destination_path = os.path.join(category_dir, filename)
            try:
                # Calcular hash SHA-256 para auditoría de integridad
                sha256_hash = hashlib.sha256()
                with open(file_path, "rb") as f:
                    for byte_block in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(byte_block)
                file_hash = sha256_hash.hexdigest()
                # Acción segura: Copilar/Mover (Usamos copia para evitar pérdida de datos)
                shutil.copy2(file_path, destination_path)
                file_info = {
                    "filename": filename,
                    "extension": ext,
                    "category": target_category,
                    "sha256": file_hash,
                    "source": file_path,
                    "destination": destination_path,
                    "status": "audited_and_classified",
                }
                processed_files.append(file_info)
                logger.info(
                    f"Archivo auditado y clasificado: {filename} -> {target_category}"
                )
            except Exception as e:
                error_msg = (
                    f"Error procesando el archivo {filename}: {str(e)}"
                )
                logger.error(error_msg)
                errors.append({"filename": filename, "error": str(e)})
        report_data = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "target_directory": download_dir,
            "total_processed": len(processed_files),
            "processed_files": processed_files,
            "errors": errors,
        }
        # Generar reporte JSON si se solicita
        if generate_report:
            report_path = os.path.join(
                destination_base,
                f"audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            )
            with open(report_path, "w", encoding="utf-8") as report_file:
                json.dump(report_data, report_file, indent=4, ensure_ascii=False)
            logger.info(f"Reporte de auditoría generado en: {report_path}")
            report_data["report_path"] = report_path
        return report_data
    except Exception as e:
        logger.critical(
            f"Fallo crítico en la habilidad 'desorden_intervencin_manual': {str(e)}"
        )
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "message": str(e),
        }