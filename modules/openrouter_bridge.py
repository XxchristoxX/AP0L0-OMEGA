"""
openrouter_bridge.py - Puente para OpenRouter
Permite usar modelos de OpenRouter para acciones específicas
Basado en FatihMakes/Mark-XXXIX-OR
"""

import os
import json
import requests

class OpenRouterBridge:
    def __init__(self, api_key=None, base_url="https://openrouter.ai/api/v1"):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def is_available(self):
        return bool(self.api_key)

    def chat(self, messages, model="meta-llama/llama-3-70b-instruct", temperature=0.7):
        """Envía un chat a OpenRouter"""
        if not self.is_available():
            return "API key de OpenRouter no configurada"
        
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except requests.exceptions.RequestException as e:
            return f"Error en OpenRouter: {str(e)}"

    def web_search(self, query):
        """Realiza una búsqueda web usando OpenRouter (si está disponible)"""
        if not self.is_available():
            return "API key de OpenRouter no configurada"
        
        messages = [
            {"role": "system", "content": "Eres un asistente que busca información en internet."},
            {"role": "user", "content": f"Busca información sobre: {query}"}
        ]
        return self.chat(messages, model="meta-llama/llama-3-70b-instruct")

# ============================================================
# EJEMPLO DE USO
# ============================================================
if __name__ == "__main__":
    bridge = OpenRouterBridge()
    if bridge.is_available():
        response = bridge.chat([{"role": "user", "content": "Hola, ¿cómo estás?"}])
        print(f"OpenRouter: {response}")
    else:
        print("OpenRouter no configurado. Configura OPENROUTER_API_KEY")