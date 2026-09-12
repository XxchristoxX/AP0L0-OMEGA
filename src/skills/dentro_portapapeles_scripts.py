from datetime import datetime
import hashlib
import json
import logging
import os
import re
import socket
import subprocess
# Configuración de logging para depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("dentro_portapapeles_scripts")
def run(params):
    """Módulo de análisis estático y detección de credenciales en texto plano
    para auditoría y defensa defensiva de código y portapapeles.
    """
    logger.info("Iniciando habilidad 'dentro_portapapeles_scripts'...")
    # Parámetros de entrada
    content = params.get(
        "content",
        (
            "# Ejemplo seguro\nAPI_KEY = 'AKIAIOSFODNN7EXAMPLE'\nSELECT * FROM"
            " users;"
        ),
    )
    analysis_type = params.get("analysis_type", "comprehensive")
    findings = []
    secrets_detected = []
    vulnerabilities_detected = []
    try:
        # 1. Verificador de credenciales y secretos (API Keys, contraseñas, tokens)
        logger.info("Ejecutando verificador de credenciales en texto plano...")
        secret_patterns = {
            "AWS Access Key": r"(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}",
            "Generic API Key": r"(?i)(api[_-]?key|apikey|secret[_-]?key|auth[_-]?token)['\" ]*[:=]['\" ]([a-zA-Z0-9_\-]{16,64})",
            "Private Key": r"-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----",
            "Bearer Token": r"Bearer [a-zA-Z0-9_\-\.]{20,}",
            "Password in Assignment": r"(?i)(password|passwd|pwd)['\" ]*[:=]['\" ]([^'\"]+)['\" ]",
        }
        for sec_name, pattern in secret_patterns.items():
            matches = re.finditer(pattern, content)
            for match in matches:
                secrets_detected.append(
                    {
                        "type": sec_name,
                        "match_preview": (
                            match.group(0)[:10] + "..."
                            if len(match.group(0)) > 10
                            else match.group(0)
                        ),
                        "position": match.start(),
                    }
                )
        # 2. Análisis estático de vulnerabilidades (SQLi, dependencias, malas prácticas)
        logger.info("Ejecutando análisis estático de vulnerabilidades...")
        vuln_patterns = {
            "SQL Injection Risk": r"(?i)(SELECT\s+.*\s+FROM\s+.*WHERE\s+.*=.*\+|execute\s*\(.*%s|cursor\.execute\s*\(\s*['\"].*%.*['\"])",
            "Command Injection Risk": r"(?i)(os\.system\s*\(|subprocess\.Popen\s*\(.*shell\s*=\s*True|eval\s*\(|exec\s*\()",
            "Insecure Hash Algorithm": r"(?i)(hashlib\.md5\(|hashlib\.sha1\()",
        }
        for vuln_name, pattern in vuln_patterns.items():
            matches = re.finditer(pattern, content)
            for match in matches:
                vulnerabilities_detected.append(
                    {
                        "vulnerability": vuln_name,
                        "matched_code": match.group(0),
                        "position": match.start(),
                    }
                )
        # Análisis de dependencias obsoletas o inseguras (simulado básico en texto)
        if "requirements.txt" in params.get("context", "") or "import" in content:
            insecure_deps = ["requests<2.20.0", "paramiko<2.8.0", "PyJWT<2.0.0"]
            for dep in insecure_deps:
                lib_name = dep.split("<")[0]
                if lib_name in content:
                    vulnerabilities_detected.append(
                        {
                            "vulnerability": "Potencial Dependencia Obsoleta/Insegura",
                            "matched_code": dep,
                            "details": (
                                "La librería detectada podría tener"
                                " vulnerabilidades conocidas."
                            ),
                        }
                    )
        # Construcción del reporte de auditoría
        report = {
            "status": "success",
            "scan_time": datetime.now().isoformat(),
            "analysis_type": analysis_type,
            "metrics": {
                "total_secrets_found": len(secrets_detected),
                "total_vulnerabilities_found": len(vulnerabilities_detected),
            },
            "secrets": secrets_detected,
            "vulnerabilities": vulnerabilities_detected,
            "recommendation": (
                "Revisar el contenido analizado. Si contiene credenciales,"
                " remuévalas inmediatamente y use variables de entorno."
                " Corrija las consultas parametrizadas para evitar SQLi."
            ),
        }
        logger.info(
            f"Análisis completado. Secretos: {len(secrets_detected)},"
            f" Vulnerabilidades: {len(vulnerabilities_detected)}"
        )
        return report
    except Exception as e:
        logger.error(f"Error durante el análisis del portapapeles/scripts: {e}")
        return {
            "status": "error",
            "scan_time": datetime.now().isoformat(),
            "error_message": str(e),
        }