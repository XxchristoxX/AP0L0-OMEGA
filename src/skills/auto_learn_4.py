import requests
import json
def run(params):
    tool_name = params.get('tool_name', 'LangChain')
    tools_info = {
        "LangChain": "LangChain es una herramienta diseñada para construir aplicaciones de lenguaje natural utilizando modelos de lenguaje.",
        "AutoGPT": "AutoGPT es un modelo de inteligencia artificial que genera texto de manera autónoma, permitiendo la creación de contenido sin intervención humana.",
        "CrewAI": "CrewAI es una plataforma que facilita la colaboración entre equipos mediante la integración de inteligencia artificial en flujos de trabajo."
    }
    result = tools_info.get(tool_name, "Herramienta no encontrada.")
    return json.dumps({"tool_name": tool_name, "description": result})