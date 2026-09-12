import os, sys, re, shutil, py_compile
from src.core.hybrid_router import HybridRouter

ALLOWED_MODULES = {
    "dashboard": "src/ui/dashboard.py",
    "panel_circular_IA": "src/utils/panel_circular_IA.py",
    "ui": "ui.py",
    "main": "main.py",
    "hybrid_router": "src/core/hybrid_router.py",
    "skills_registry": "src/core/skills_registry.py",
    "self_healer": "src/core/self_healer.py",
}

def run(params=None):
    if params is None:
        params = {}
    module_name = params.get("module", "").lower()
    task = params.get("task", "Optimizar el código para mayor rendimiento y legibilidad.")

    if module_name not in ALLOWED_MODULES:
        return f"Módulo no permitido. Opciones: {', '.join(ALLOWED_MODULES.keys())}"

    filepath = ALLOWED_MODULES[module_name]
    if not os.path.exists(filepath):
        return f"No se encontró el archivo: {filepath}"

    # Backup
    backup_path = filepath + ".bak"
    shutil.copy2(filepath, backup_path)

    with open(filepath, "r", encoding="utf-8") as f:
        original_code = f.read()

    prompt = f"""Eres un experto en Python. Modifica el siguiente código para: {task}
Código actual:
Devuelve SOLO el código completo y corregido, sin markdown."""
    router = HybridRouter()
    response = router.route(prompt, "J.A.R.V.I.S")
    if not response or len(response.strip()) < 20:
        return "La IA no generó una respuesta válida."

    new_code = response.strip().strip('`')
    if new_code.startswith("python"):
        new_code = new_code[6:].strip()

    # Verificar sintaxis
    try:
        compile(new_code, filepath, 'exec')
    except SyntaxError as e:
        return f"El código generado tiene errores de sintaxis: {e}"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_code)

    return f"Módulo '{module_name}' mejorado exitosamente. Backup en {backup_path}"
