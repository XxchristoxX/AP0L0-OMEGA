from datetime import datetime
import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
# Configuración de logging para depuración
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("sospechosos_alertando_usuario")
def run(params):
    """Función principal para la habilidad de análisis estático y dinámico
    de scripts locales en busca de código malicioso o vulnerabilidades.
    Params esperados:
    - script_path: Ruta al archivo de script a analizar (opcional).
    - script_content: Contenido en texto plano del script a analizar (opcional).
    """
    script_path = params.get("script_path")
    script_content = params.get("script_content")
    findings = []
    metadata = {}
    try:
        if script_path:
            if not os.path.exists(script_path):
                return {
                    "status": "error",
                    "message": f"El archivo {script_path} no existe.",
                }
            metadata["path"] = script_path
            with open(script_path, "r", encoding="utf-8", errors="ignore") as f:
                script_content = f.read()
        if not script_content:
            return {
                "status": "error",
                "message": (
                    "No se proporcionó 'script_path' ni 'script_content'."
                ),
            }
        # Calcular hashes para identificación y auditoría
        metadata["sha256"] = hashlib.sha256(
            script_content.encode("utf-8")
        ).hexdigest()
        logger.info(f"Analizando script con SHA256: {metadata['sha256']}")
        # 1. Análisis Estático: Búsqueda de patrones peligrosos (Regex)
        patterns = {
            "Hardcoded Credentials": r"(?i)(password|passwd|pwd|api_key|secret|token)\s*=\s*['\"].+['\"]",
            "Command Injection / RCE": r"(?i)(os\.system|subprocess\.run|subprocess\.Popen|eval|exec)\s*\(",
            "Dangerous Network Activity": r"(?i)(urllib\.request|requests\.(get|post)|socket\.socket)\s*\(",
            "Potential Obfuscation": r"(?i)(base64\.b64decode|exec\(compile)",
        }
        lines = script_content.splitlines()
        for line_num, line in enumerate(lines, 1):
            for vuln_type, pattern in patterns.items():
                if re.search(pattern, line):
                    findings.append(
                        {
                            "line": line_num,
                            "type": vuln_type,
                            "code_snippet": line.strip(),
                            "suggestion": (
                                "Evite exponer credenciales o usar funciones"
                                " de ejecución dinámica sin validación."
                            ),
                        }
                    )
        # 2. Análisis Dinámico Seguro (Sandboxed Syntax Check)
        # Usamos subprocess para ejecutar 'python -m py_compile' en un archivo temporal
        # garantizando que no se ejecute código arbitrario, solo se valide la sintaxis y estructura.
        syntax_valid = True
        syntax_error_msg = ""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as temp_file:
            temp_file.write(script_content)
            temp_file_path = temp_file.name
        try:
            result = subprocess.run(
                ["python", "-m", "py_compile", temp_file_path],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                syntax_valid = False
                syntax_error_msg = result.stderr.strip()
        except Exception as e:
            syntax_valid = False
            syntax_error_msg = str(e)
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        report = {
            "status": "success",
            "scan_time": datetime.now().isoformat(),
            "metadata": metadata,
            "syntax_check": {
                "valid": syntax_valid,
                "error": syntax_error_msg if not syntax_valid else None,
            },
            "findings_count": len(findings),
            "findings": findings,
            "alert": (
                len(findings) > 0 or not syntax_valid
            ),  # Alerta al usuario si hay hallazgos
        }
        logger.info(
            f"Análisis completado. Hallazgos detectados: {len(findings)}"
        )
        return report
    except Exception as e:
        logger.error(f"Error crítico durante el análisis: {str(e)}")
        return {"status": "error", "message": str(e)}