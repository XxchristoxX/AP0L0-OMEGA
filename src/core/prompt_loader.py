# core/prompt_loader.py
import sys
from pathlib import Path

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
PROMPTS_DIR = BASE_DIR / "core"

def load_prompt(filename: str) -> str:
    """
    Carga un prompt desde un archivo de texto.
    Busca en:
      1. Ruta absoluta o relativa al directorio actual
      2. core/ (directorio de prompts)
      3. config/ (directorio alternativo)
    """
    path = Path(filename)
    if path.exists():
        return path.read_text(encoding="utf-8")
    
    core_path = PROMPTS_DIR / filename
    if core_path.exists():
        return core_path.read_text(encoding="utf-8")
    
    config_path = BASE_DIR / "config" / filename
    if config_path.exists():
        return config_path.read_text(encoding="utf-8")
    
    print(f"[PromptLoader] ⚠️ Archivo no encontrado: {filename}")
    return _get_default_prompt(filename)

def _get_default_prompt(filename: str) -> str:
    if "jarvis" in filename.lower():
        return """Eres {assistant_name}, el asistente de IA de Christopher.
Eres técnico, preciso y directo. Te diriges al usuario como "señor" o "sir".
Siempre das respuestas claras y concisas. Usas herramientas para completar tareas.
Nunca simulas resultados: siempre llamas a la herramienta apropiada.
{assistant_subtitle}"""
    elif "agata" in filename.lower():
        return """Eres Ágata, una asistente creativa y diseñadora.
Eres elegante, detallista y tienes un ojo para el diseño y la estética.
Te diriges al usuario con calidez y creatividad.
Ayudas con diseño, presentaciones y documentos.
Tus respuestas son inspiradoras, visuales y llenas de estilo.
{assistant_subtitle}"""
    elif "tony" in filename.lower():
        return """Eres Tony Stark, el genio, multimillonario, playboy y filántropo.
Eres ingenioso, sarcástico y extremadamente inteligente.
Te diriges a todos con un tono confiado y a menudo humorístico.
Siempre tienes una solución tecnológica para cualquier problema.
{assistant_subtitle}"""
    elif "friday" in filename.lower():
        return """Eres Friday, la asistente de IA de Tony Stark, más joven y menos formal que JARVIS.
Eres amable, eficiente y siempre dispuesta a ayudar con un toque de calidez.
Te diriges al usuario con respeto pero con un tono más cercano.
{assistant_subtitle}"""
    else:
        return "Eres un asistente inteligente y útil. Responde en el idioma del usuario."

def get_prompt(name: str) -> str:
    return load_prompt(name)

def switch_personality(personality: str) -> str:
    if personality.lower() == "jarvis":
        return load_prompt("prompt_jarvis.txt")
    elif personality.lower() == "agata":
        return load_prompt("prompt_agata.txt")
    elif personality.lower() == "tony":
        return load_prompt("prompt_tony.txt")
    elif personality.lower() == "friday":
        return load_prompt("prompt_friday.txt")
    return load_prompt("prompt.txt")