from datetime import datetime
import hashlib
import json
import logging
import os
import shutil
import subprocess
# Configuración de logging para auditoría de seguridad
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [HackingDefensivo] - %(message)s",
)
logger = logging.getLogger("MantenedorEscritorioSeguro")
def run(params):
    """Habilidad defensiva y de auditoría: 'mantendr_escritorio_limpio'.
    Protege el sistema organizando archivos de forma segura, calculando
    hashes SHA-256 para auditoría de integridad y previniendo la acumulación
    de archivos desconocidos o potencialmente maliciosos en zonas de descarga.
    """
    logger.info("Iniciando auditoría y limpieza segura del escritorio.")
    # Directorio objetivo (por defecto la carpeta de descargas del usuario actual)
    target_dir = params.get(
        "target_dir", os.path.expanduser("~/Downloads")
    )
    categories = params.get(
        "categories",
        {
            "Trabajo": [".pdf", ".docx", ".xlsx", ".pptx", ".txt"],
            "Finanzas": [".csv", ".ofx", ".qfx", ".pdf"],
            "Multimedia": [".mp4", ".mkv", ".mp3", ".jpg", ".png", ".gif"],
            "Scripts_Analisis": [".py", ".sh", ".ps1", ".pcap", ".log"],
        },
    )
    audit_report = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "target_directory": target_dir,
        "files_processed": [],
        "errors": [],
    }
    try:
        if not os.path.exists(target_dir):
            raise FileNotFoundError(
                f"El directorio objetivo no existe: {target_dir}"
            )
        # Crear directorios temáticos si no existen
        base_secure_dir = os.path.join(target_dir, "EscritorioSeguro_Organizado")
        for category in categories.keys():
            cat_path = os.path.join(base_secure_dir, category)
            os.makedirs(cat_path, exist_ok=True)
        # Auditoría y movimiento seguro de archivos (excluyendo directorios)
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            if os.path.isdir(item_path):
                continue  # No tocar subdirectorios por seguridad
            _, ext = os.path.splitext(item)
            ext = ext.lower()
            moved = False
            for category, allowed_exts in categories.items():
                if ext in allowed_exts:
                    dest_folder = os.path.join(base_secure_dir, category)
                    dest_path = os.path.join(dest_folder, item)
                    try:
                        # Cálculo de hash SHA-256 para integridad y auditoría forense
                        sha256_hash = hashlib.sha256()
                        with open(item_path, "rb") as f:
                            for byte_block in iter(lambda: f.read(4096), b""):
                                sha256_hash.update(byte_block)
                        file_hash = sha256_hash.hexdigest()
                        # Movimiento seguro del archivo
                        shutil.move(item_path, dest_path)
                        audit_report["files_processed"].append(
                            {
                                "file_name": item,
                                "category": category,
                                "sha256": file_hash,
                                "destination": dest_path,
                            }
                        )
                        logger.info(
                            f"Archivo auditado y movido de forma segura: {item} -> {category}"
                        )
                        moved = True
                        break
                    except Exception as e:
                        logger.error(
                            f"Error procesando el archivo {item}: {str(e)}"
                        )
                        audit_report["errors"].append(
                            {"file": item, "error": str(e)}
                        )
            # Si el archivo no encaja en ninguna categoría, se aislará en 'Otros'
            if not moved:
                other_folder = os.path.join(base_secure_dir, "Otros")
                os.makedirs(other_folder, exist_ok=True)
                dest_path = os.path.join(other_folder, item)
                try:
                    shutil.move(item_path, dest_path)
                    audit_report["files_processed"].append(
                        {
                            "file_name": item,
                            "category": "Otros",
                            "destination": dest_path,
                        }
                    )
                    logger.warning(
                        f"Archivo sin categoría específica aislado en 'Otros': {item}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error aislando el archivo {item}: {str(e)}"
                    )
                    audit_report["errors"].append(
                        {"file": item, "error": str(e)}
                    )
        # Generar reporte en JSON para auditorías defensivas
        report_path = os.path.join(
            base_secure_dir, f"audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_path, "w", encoding="utf-8") as report_file:
            json.dump(audit_report, report_file, indent=4, ensure_ascii=False)
        audit_report["audit_report_file"] = report_path
        logger.info(f"Reporte de auditoría generado exitosamente en: {report_path}")
    except Exception as e:
        logger.critical(f"Fallo crítico en la ejecución de la habilidad: {str(e)}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error_message": str(e),
        }
    return audit_report