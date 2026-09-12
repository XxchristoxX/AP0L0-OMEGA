from datetime import datetime
import hashlib
import json
import logging
import os
import re
import subprocess
# Configuración de logging para depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
def run(params):
    """Habilidad 'sean_funcionalmente_correctas':
    Realiza análisis estático de código fuente (Python) para detectar
    vulnerabilidades comunes como credenciales hardcodeadas, inyecciones de
    comandos y uso de funciones inseguras, asegurando que las soluciones
    sean seguras por defecto.
    """
    code_snippet = params.get("code", "")
    report_format = params.get("format", "json")
    logging.info(
        "Iniciando análisis estático de seguridad para el fragmento de código proporcionado."
    )
    if not code_snippet:
        logging.warning("No se proporcionó código para analizar.")
        return {
            "status": "error",
            "message": "No code provided for static analysis.",
            "timestamp": datetime.now().isoformat(),
        }
    # Definición de patrones de vulnerabilidades comunes (RegEx)
    patterns = {
        "hardcoded_credentials": {
            "regex": r"(password|passwd|pwd|secret|api_key|token)\s*=\s*['\"].*?['\"]",
            "severity": "HIGH",
            "description": "Posible credencial o secreto hardcodeado en el código.",
        },
        "command_injection": {
            "regex": r"(os\.system|subprocess\.Popen|subprocess\.run|eval|exec)\s*\(",
            "severity": "CRITICAL",
            "description": "Uso potencial de ejecución de comandos o evaluación dinámica (riesgo de inyección).",
        },
        "insecure_deserialization": {
            "regex": r"(pickle\.load|yaml\.load)\s*\(",
            "severity": "HIGH",
            "description": "Deserialización insegura detectada.",
        },
        "sql_injection_risk": {
            "regex": r"(execute|cursor\.execute)\s*\(\s*['\"].*?%s.*?['\"]",
            "severity": "MEDIUM",
            "description": "Posible concatenación o formato inseguro en consultas SQL.",
        },
    }
    findings = []
    lines = code_snippet.splitlines()
    # Análisis línea por línea y global
    for line_num, line in enumerate(lines, 1):
        for vuln_name, details in patterns.items():
            if re.search(details["regex"], line, re.IGNORECASE):
                finding = {
                    "line": line_num,
                    "vulnerability": vuln_name,
                    "severity": details["severity"],
                    "description": details["description"],
                    "matched_content": line.strip(),
                }
                findings.append(finding)
                logging.warning(
                    f"Vulnerabilidad detectada [{details['severity']}]: {vuln_name} en la línea {line_num}"
                )
    # Generación de métricas de código
    code_hash = hashlib.sha256(code_snippet.encode("utf-8")).hexdigest()
    report = {
        "status": "success",
        "scan_timestamp": datetime.now().isoformat(),
        "code_sha256": code_hash,
        "total_lines": len(lines),
        "vulnerabilities_found": len(findings),
        "safe_by_default": len(findings) == 0,
        "findings": findings,
    }
    # Manejo de formatos de salida (JSON o HTML simulado en estructura)
    if report_format.lower() == "html":
        logging.info("Generando reporte en formato HTML estructurado.")
        html_report = (
            f"<html><body><h1>Reporte de Auditoría de Código</h1>"
            f"<p>Timestamp: {report['scan_timestamp']}</p>"
            f"<p>Vulnerabilidades: {report['vulnerabilities_found']}</p>"
            f"<pre>{json.dumps(findings, indent=4)}</pre>"
            f"</body></html>"
        )
        return {
            "status": "success",
            "format": "html",
            "report_content": html_report,
        }
    logging.info(
        "Análisis estático completado exitosamente. Retornando reporte JSON."
    )
    return report