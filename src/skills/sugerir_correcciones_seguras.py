from datetime import datetime
import hashlib
import json
import logging
import os
import re
import subprocess
import requests
# Configuración de logs para depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ShieldScan")
def run(params):
    """Módulo ShieldScan: Analiza fragmentos de código en busca de vulnerabilidades,
    malas prácticas y credenciales filtradas, sugiriendo correcciones seguras.
    """
    code_snippet = params.get("code", "")
    language = params.get("language", "python").lower()
    if not code_snippet:
        logger.error("No se proporcionó código para analizar.")
        return {
            "status": "error",
            "message": "El parámetro 'code' es obligatorio.",
        }
    logger.info(
        f"Iniciando análisis de seguridad para código en {language}..."
    )
    vulnerabilities = []
    # 1. Detección de credenciales hardcodeadas (Patrones de API Keys, contraseñas, tokens)
    credential_patterns = [
        (
            r"(?i)(api[_-]?key|secret|password|passwd|pwd|token)\s*=\s*['\"'][a-zA-Z0-9_\-\.]{8,}['\"']",
            "Credencial hardcodeada detectada.",
            "Utiliza variables de entorno (os.environ) o un gestor de secretos seguro.",
        ),
        (
            r"sk_live_[0-9a-zA-Z]{24,}",
            "Llave secreta de Stripe en texto plano.",
            "Revoca la llave inmediatamente y almacénala en variables de entorno.",
        ),
        (
            r"-----BEGIN RSA PRIVATE KEY-----",
            "Llave privada RSA expuesta en el código.",
            "Remueve la llave del código fuente y utiliza almacenamiento seguro de certificados.",
        ),
    ]
    for pattern, desc, fix in credential_patterns:
        matches = re.finditer(pattern, code_snippet)
        for match in matches:
            vulnerabilities.append(
                {
                    "type": "Fuga de Credenciales",
                    "severity": "ALTA",
                    "description": desc,
                    "matched": match.group(0)[
                        :10
                    ]
                    + "...",  # Ocultar parte por seguridad
                    "suggestion": fix,
                }
            )
    # 2. Detección de malas prácticas y vulnerabilidades comunes según el lenguaje
    if language == "python":
        python_vulnerabilities = [
            (
                r"\beval\s*\(",
                "Uso peligroso de la función eval()",
                "CRÍTICA",
                "Evita usar eval() ya que permite la ejecución arbitraria de código. Usa alternativas seguras como ast.literal_eval().",
            ),
            (
                r"\bexec\s*\(",
                "Uso peligroso de la función exec()",
                "CRÍTICA",
                "Evita ejecutar código dinámicamente con exec(). Rediseña la lógica para evitarlo.",
            ),
            (
                r"subprocess\..*shell\s*=\s*True",
                "Inyección de comandos mediante shell=True",
                "ALTA",
                "Establece shell=False y pasa los argumentos como una lista de strings.",
            ),
            (
                r"sqlite3\.cursor\(\)\.execute\(f['\"].*\{.*\}",
                "Posible Inyección SQL",
                "ALTA",
                "Utiliza consultas parametrizadas (?) en lugar de formatear strings directamente en SQL.",
            ),
        ]
        for pattern, desc, severity, fix in python_vulnerabilities:
            if re.search(pattern, code_snippet):
                vulnerabilities.append(
                    {
                        "type": "Vulnerabilidad de Código",
                        "severity": severity,
                        "description": desc,
                        "suggestion": fix,
                    }
                )
    # Generación de reporte estructurado en JSON
    report = {
        "status": "success",
        "scan_timestamp": datetime.now().isoformat(),
        "language": language,
        "code_hash": hashlib.sha256(code_snippet.encode("utf-8")).hexdigest(),
        "total_issues_found": len(vulnerabilities),
        "vulnerabilities": vulnerabilities,
    }
    logger.info(
        f"Análisis completado. Se encontraron {len(vulnerabilities)} problemas de seguridad."
    )
    # Opcional: Guardar reporte localmente para auditoría
    try:
        report_filename = f"shieldscan_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        logger.info(f"Reporte guardado exitosamente en {report_filename}")
    except Exception as e:
        logger.warning(f"No se pudo guardar el archivo de reporte: {str(e)}")
    return report