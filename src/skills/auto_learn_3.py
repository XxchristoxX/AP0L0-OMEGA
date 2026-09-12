import json
def explain_vulnerability(vulnerability):
    explanations = {
        "SQL Injection": {
            "description": "Una técnica donde un atacante inserta código SQL malicioso en una consulta.",
            "protection": "Usar consultas preparadas y ORM para evitar inyecciones."
        },
        "XSS": {
            "description": "Cross-Site Scripting permite a un atacante inyectar scripts en páginas vistas por otros usuarios.",
            "protection": "Validar y escapar datos de entrada del usuario."
        },
        "CSRF": {
            "description": "Cross-Site Request Forgery engaña a un usuario para que ejecute acciones no deseadas en una aplicación web.",
            "protection": "Implementar tokens CSRF y verificar la autenticidad de las solicitudes."
        }
    }
    return explanations.get(vulnerability, {"description": "Vulnerabilidad no reconocida.", "protection": "Ninguna protección disponible."})
def run(params):
    vulnerability = params.get("vulnerability")
    if vulnerability:
        result = explain_vulnerability(vulnerability)
        return json.dumps(result)
    return json.dumps({"error": "Se requiere un parámetro 'vulnerability'."})