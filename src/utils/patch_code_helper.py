import os
import importlib
import src.actions.code_helper as orig

# Guardar referencia al objeto code_helper original
original_code_helper = orig.code_helper

# Definir un wrapper que intercepta las llamadas de generación de código
def new_code_helper(params):
    # Si la llamada es para generar código, usar OpenRouter
    if params.get('action') == 'write':
        return generate_via_openrouter(params.get('description', params.get('task', '')))
    # Si no, delegar en el comportamiento original
    return original_code_helper(params)

def generate_via_openrouter(description):
    import requests
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "Error: OPENROUTER_API_KEY no configurada."
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "anthropic/claude-3.5-sonnet",
        "messages": [
            {"role": "system", "content": "Eres un programador experto. Responde únicamente con el código Python solicitado, sin markdown."},
            {"role": "user", "content": f"Escribe código Python para: {description}"}
        ],
        "temperature": 0.3
    }
    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    if r.status_code == 200:
        return r.json()["choices"][0]["message"]["content"].strip()
    return f"Error {r.status_code}: {r.text}"

# Reemplazar el objeto code_helper con nuestro wrapper
orig.code_helper = new_code_helper
print("code_helper parcheado: la generación de código usará OpenRouter.")
