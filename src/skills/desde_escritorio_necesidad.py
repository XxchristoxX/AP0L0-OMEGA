from datetime import datetime
import hashlib
import json
import logging
import os
import requests
import subprocess
# Configuración de logs para depuración
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
def run(params):
    """
    Habilidad: desde_escritorio_necesidad
    Propósito: Auditar la seguridad de documentos locales de trabajo antes de realizar cualquier 
    acción de publicación externa (como marca personal), verificando que no contengan 
    credenciales expuestas, claves API, PII (información personal identificable) o 
    metadatos sensibles.
    """
    file_path = params.get("file_path", "")
    action = params.get("action", "audit_document")
    report = {
        "status": "success",
        "skill": "desde_escritorio_necesidad",
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "findings": []
    }
    try:
        if not file_path or not os.path.exists(file_path):
            logging.error(f"El archivo especificado no existe o no es válido: {file_path}")
            return {
                "status": "error",
                "message": f"Archivo no encontrado: {file_path}",
                "timestamp": datetime.now().isoformat()
            }
        logging.info(f"Iniciando auditoría de seguridad para el archivo: {file_path}")
        # 1. Calcular hash del documento para control de integridad
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        report["document_sha256"] = sha256_hash.hexdigest()
        # 2. Leer contenido de forma segura para análisis defensivo
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        # 3. Análisis de patrones sensibles (Defensa contra fuga de datos / Data Leakage)
        sensitive_patterns = {
            "api_key": r"(api[_-]?key|secret[_-]?key|token)['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{16,}",
            "private_key": r"-----BEGIN (RSA|PRIVATE) KEY-----",
            "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
            "password_leak": r"password\s*[:=]\s*['\"].+?['\"]"
        }
        import re
        for category, pattern in sensitive_patterns.items():
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                report["findings"].append({
                    "category": category,
                    "severity": "HIGH" if "key" in category or "password" in category else "MEDIUM",
                    "description": f"Se detectó un patrón coincidente con '{category}' que podría ser información sensible."
                })
                logging.warning(f"¡Alerta de seguridad! Hallazgo en {file_path}: {category}")
        # 4. Verificación de metadatos mediante herramientas del sistema (si aplica)
        try:
            file_stats = os.stat(file_path)
            report["file_metadata"] = {
                "size_bytes": file_stats.st_size,
                "permissions": oct(file_stats.st_mode)[-3:]
            }
        except Exception as meta_err:
            logging.warning(f"No se pudieron extraer todos los metadatos: {str(meta_err)}")
        # 5. Evaluación final de seguridad para la publicación
        if any(f["severity"] == "HIGH" for f in report["findings"]):
            report["security_recommendation"] = "BLOQUEADO: El documento contiene información altamente sensible. No proceder con la publicación."
        else:
            report["security_recommendation"] = "APROBADO: No se detectaron credenciales críticas. El resumen puede ser utilizado para la gestión de marca personal."
        logging.info(f"Auditoría completada exitosamente para {file_path}")
        return report
    except Exception as e:
        logging.error(f"Error crítico durante la ejecución de la habilidad: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }