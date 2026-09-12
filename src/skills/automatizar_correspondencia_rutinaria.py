from datetime import datetime
import hashlib
import json
import os
import re
import socket
import subprocess
import requests
def run(params):
    """Audita y clasifica la correspondencia rutinaria (simulada localmente)
    para detectar posibles vectores de ataque (Phishing/Spam/Malware)
    y generar borradores de respuesta seguros.
    """
    inbox_path = params.get("inbox_path", "./inbox_samples")
    output_report = params.get("output_report", "email_audit_report.json")
    allowed_domains = params.get(
        "allowed_domains", ["company.com", "trusted-partner.com"]
    )
    results = []
    audited_count = 0
    threats_detected = 0
    # Asegurar directorio de prueba si no existe
    if not os.path.exists(inbox_path):
        os.makedirs(inbox_path, exist_ok=True)
        # Crear un archivo de prueba seguro
        sample_email = os.path.join(inbox_path, "sample_msg.txt")
        with open(sample_email, "w") as f:
            f.write(
                "From: urgent@suspicious-domain.com\nSubject: Update your password immediately\nBody: Click here to reset your credentials."
            )
    try:
        for filename in os.listdir(inbox_path):
            if filename.endswith(".txt"):
                file_full_path = os.path.join(inbox_path, filename)
                audited_count += 1
                with open(file_full_path, "r", encoding="utf-8") as file:
                    content = file.read()
                # Análisis heurístico básico para seguridad (Phishing/Spoofing)
                sender_match = re.search(r"From:\s*(.*)", content)
                subject_match = re.search(r"Subject:\s*(.*)", content)
                sender = sender_match.group(1).strip() if sender_match else ""
                subject = (
                    subject_match.group(1).strip() if subject_match else ""
                )
                # Verificar si el dominio del remitente es confiable
                domain = (
                    sender.split("@")[-1] if "@" in sender else "unknown"
                )
                is_trusted = any(
                    domain.endswith(d) for d in allowed_domains
                )
                threat_indicators = []
                if not is_trusted:
                    threat_indicators.append("Remitente no en lista blanca")
                if "urgent" in subject.lower() or "password" in content.lower():
                    threat_indicators.append(
                        "Posible intento de Phishing/Credencial Harvesting"
                    )
                if threat_indicators:
                    threats_detected += 1
                    status = "ALERTA_SEGURIDAD"
                    draft_response = (
                        "ACCIÓN REQUERIDA: Mensaje marcado como sospechoso. "
                        "No hacer clic en enlaces. Notificar al SOC."
                    )
                else:
                    status = "SEGURO"
                    draft_response = (
                        "Estimado usuario, hemos recibido su correspondencia rutinaria y será procesada."
                    )
                email_hash = hashlib.sha256(
                    content.encode("utf-8")
                ).hexdigest()
                results.append(
                    {
                        "filename": filename,
                        "sender": sender,
                        "subject": subject,
                        "domain": domain,
                        "status": status,
                        "threat_indicators": threat_indicators,
                        "email_hash": email_hash,
                        "draft_response": draft_response,
                    }
                )
        report_data = {
            "status": "success",
            "audit_time": datetime.now().isoformat(),
            "total_audited": audited_count,
            "threats_detected": threats_detected,
            "details": results,
        }
        # Guardar reporte JSON
        with open(output_report, "w", encoding="utf-8") as report_file:
            json.dump(report_data, report_file, indent=4, ensure_ascii=False)
        return {
            "status": "success",
            "message": "Auditoría de correspondencia completada con éxito.",
            "report_path": output_report,
            "audited_count": audited_count,
            "threats_detected": threats_detected,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error durante la ejecución del módulo de correspondencia: {str(e)}",
            "audit_time": datetime.now().isoformat(),
        }