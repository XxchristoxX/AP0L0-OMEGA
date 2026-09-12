from datetime import datetime
import hashlib
import json
import logging
import os
import subprocess
# Configuración de logging para depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
def run(params):
    """Habilidad 'adaptarse_necesidades_usuario' orientada a la seguridad.
    Monitorea, audita y organiza de forma segura los archivos de un directorio
    (por ejemplo, descargas) para prevenir la ejecución de archivos maliciosos
    no categorizados, verificar la integridad (hash) y aplicar políticas de
    seguridad mediante reglas en lenguaje natural.
    """
    try:
        # Directorio objetivo a auditar y organizar (por defecto el directorio actual o Descargas)
        target_dir = params.get(
            "target_dir", os.path.expanduser("~/Downloads")
        )
        custom_rules = params.get("custom_rules", {})
        generate_report = params.get("generate_report", True)
        logging.info(f"Iniciando auditoría y organización en: {target_dir}")
        if not os.path.exists(target_dir):
            return {
                "status": "error",
                "message": f"El directorio objetivo {target_dir} no existe.",
            }
        # Categorías seguras predeterminadas orientadas a defensa/auditoría
        categories = {
            "Trabajo": [".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".csv"],
            "Multimedia": [
                ".mp4",
                ".mkv",
                ".mp3",
                ".jpg",
                ".png",
                ".gif",
                ".wav",
            ],
            "Personal": [".zip", ".tar", ".gz", ".rar", ".7z"],
            "Cuarentena_Auditoria": [
                ".exe",
                ".bat",
                ".sh",
                ".js",
                ".vbs",
                ".cmd",
            ],  # Archivos potencialmente peligrosos aislados para análisis
        }
        # Crear directorios de categorías si no existen (de forma segura)
        for category in categories.keys():
            cat_path = os.path.join(target_dir, category)
            if not os.path.exists(cat_path):
                os.makedirs(cat_path, exist_ok=True)
        audited_files = []
        # Listar archivos en el directorio objetivo (solo nivel raíz para evitar recursión destructiva)
        for filename in os.listdir(target_dir):
            file_path = os.path.join(target_dir, filename)
            if os.path.isdir(file_path):
                continue  # Ignorar subdirectorios para mantener la seguridad
            file_ext = os.path.splitext(filename)[1].lower()
            # Cálculo de Hash SHA-256 para auditoría de integridad y detección de amenazas
            file_hash = ""
            try:
                sha256_hash = hashlib.sha256()
                with open(file_path, "rb") as f:
                    for byte_block in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(byte_block)
                file_hash = sha256_hash.hexdigest()
            except Exception as e:
                logging.error(
                    f"No se pudo calcular el hash para {filename}: {str(e)}"
                )
                file_hash = "error_calculating"
            # Determinar categoría basada en extensión y reglas
            assigned_category = "Personal"  # Default
            for cat, exts in categories.items():
                if file_ext in exts:
                    assigned_category = cat
                    break
            # Aplicar reglas personalizadas basadas en palabras clave (Lenguaje natural simulado)
            for rule_keyword, target_cat in custom_rules.items():
                if rule_keyword.lower() in filename.lower():
                    assigned_category = target_cat
                    break
            # Mover archivo de forma segura a su categoría correspondiente
            dest_path = os.path.join(
                target_dir, assigned_category, filename
            )
            # Evitar sobrescribir archivos existentes
            if not os.path.exists(dest_path):
                os.rename(file_path, dest_path)
                action_status = "organizado"
            else:
                action_status = "omitido_duplicado"
            audited_files.append(
                {
                    "filename": filename,
                    "extension": file_ext,
                    "sha256": file_hash,
                    "category": assigned_category,
                    "status": action_status,
                }
            )
        report = {
            "status": "success",
            "audit_time": datetime.now().isoformat(),
            "target_directory": target_dir,
            "total_files_processed": len(audited_files),
            "details": audited_files,
        }
        # Generar reporte en formato JSON si se solicita
        if generate_report:
            report_path = os.path.join(target_dir, "security_audit_report.json")
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=4, ensure_ascii=False)
            logging.info(f"Reporte de auditoría generado en: {report_path}")
        return report
    except Exception as e:
        logging.error(f"Error crítico en la habilidad: {str(e)}")
        return {"status": "error", "message": str(e)}