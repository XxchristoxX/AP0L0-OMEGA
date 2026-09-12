# src/actions/func_bridge.py
"""
Puente para integrar func.py en AP0L0 OMEGA
Permite usar las capacidades de func.py como herramientas.
"""

import os
import sys
import json
import threading
import asyncio
from pathlib import Path

# ===== VARIABLES GLOBALES PARA FUNC =====
_func_loop = None
_func_client = None
_func_connected = False

def _get_func_path():
    """Obtiene la ruta a func.py"""
    # Buscar en la raíz del proyecto
    base = Path(__file__).resolve().parent.parent.parent
    func_path = base / "func.py"
    if func_path.exists():
        return func_path
    # Buscar en el directorio actual
    func_path = Path("func.py")
    if func_path.exists():
        return func_path
    return None

def iniciar_func():
    """Inicia el servidor func.py en segundo plano."""
    global _func_connected, _func_loop
    
    func_path = _get_func_path()
    if not func_path:
        return "func.py no encontrado en el proyecto."
    
    try:
        # Importar func.py dinámicamente
        import importlib.util
        spec = importlib.util.spec_from_file_location("func", func_path)
        if spec is None or spec.loader is None:
            return "No se pudo cargar func.py"
        
        module = importlib.util.module_from_spec(spec)
        sys.modules["func"] = module
        spec.loader.exec_module(module)
        
        # Iniciar el servidor WebSocket de func
        if hasattr(module, 'start_ia'):
            threading.Thread(target=module.start_ia, daemon=True).start()
            _func_connected = True
            return "✅ Servidor func.py iniciado en ws://localhost:8765"
        else:
            return "func.py no tiene función start_ia"
    except Exception as e:
        return f"Error iniciando func.py: {e}"

def ejecutar_funcion_func(nombre: str, params: dict = None):
    """Ejecuta una función de func.py por nombre."""
    func_path = _get_func_path()
    if not func_path:
        return "func.py no encontrado"
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("func", func_path)
        if spec is None or spec.loader is None:
            return "No se pudo cargar func.py"
        
        module = importlib.util.module_from_spec(spec)
        sys.modules["func"] = module
        spec.loader.exec_module(module)
        
        if hasattr(module, nombre):
            func = getattr(module, nombre)
            if callable(func):
                result = func(params) if params else func()
                return str(result)
        return f"Función '{nombre}' no encontrada en func.py"
    except Exception as e:
        return f"Error ejecutando {nombre}: {e}"