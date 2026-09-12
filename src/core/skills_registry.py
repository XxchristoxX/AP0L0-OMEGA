# src/core/skills_registry.py
"""
Registro de habilidades con carga perezosa (lazy loading).
Solo recolecta nombres y rutas al inicio; importa el módulo solo cuando se ejecuta.
"""

import os
import sys
import importlib.util
import logging
import builtins  # <-- ¡IMPORTANTE!
from contextlib import redirect_stdout, redirect_stderr
from typing import Dict, Callable, Optional

_logger = logging.getLogger("SkillsRegistry")
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    _logger.addHandler(handler)

class _DevNull:
    """Sumidero para silenciar salidas durante la carga."""
    def write(self, *args, **kwargs): pass
    def flush(self, *args, **kwargs): pass
    def close(self): pass

class SkillsRegistry:
    def __init__(self, silent: bool = False, debug: bool = False):
        self._skills_meta: Dict[str, dict] = {}   # name -> {'path': str, 'source': str}
        self._skills_cache: Dict[str, Callable] = {}
        self._failed_skills: Dict[str, str] = {}
        self._silent = silent
        self._debug = debug
        self.load_all_skills()   # solo recolecta metadatos

    def load_all_skills(self):
        """Recolecta todos los nombres y rutas sin importar los módulos."""
        # Usamos contextlib para silenciar stdout/stderr y builtins.input de forma segura
        if self._silent:
            null = _DevNull()
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout, sys.stderr = null, null
            # Redirigir input a una función que no haga nada
            old_input = builtins.input
            builtins.input = lambda prompt="": ""
        else:
            old_stdout = old_stderr = None
            old_input = None

        try:
            base_dir = os.path.dirname(os.path.dirname(__file__))
            skills_dir = os.path.join(base_dir, 'skills')
            actions_dir = os.path.join(base_dir, 'actions')

            _logger.info(f"📂 Escaneando skills desde: {skills_dir}")
            if os.path.isdir(skills_dir):
                self._scan_dir(skills_dir, "skills")

            _logger.info(f"📂 Escaneando acciones desde: {actions_dir}")
            if os.path.isdir(actions_dir):
                self._scan_dir(actions_dir, "actions")

            total = len(self._skills_meta)
            _logger.info(f"✅ {total} habilidades/acciones registradas (carga perezosa).")
        finally:
            if self._silent:
                sys.stdout, sys.stderr = old_stdout, old_stderr
                builtins.input = old_input

    def _scan_dir(self, directory: str, source: str):
        for file in os.listdir(directory):
            if not file.endswith('.py') or file.startswith('__'):
                continue
            if file.endswith('.bak') or '.broken' in file:
                continue
            name = file[:-3]
            full_path = os.path.join(directory, file)
            self._skills_meta[name] = {'path': full_path, 'source': source}

    def get_skill(self, name: str) -> Optional[Callable]:
        """Obtiene la función de una habilidad, cargándola bajo demanda."""
        if name in self._skills_cache:
            return self._skills_cache[name]

        meta = self._skills_meta.get(name)
        if not meta:
            return None

        try:
            spec = importlib.util.spec_from_file_location(f"{meta['source']}.{name}", meta['path'])
            if spec is None or spec.loader is None:
                raise ImportError(f"No se pudo crear spec para {name}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            func = None
            func_name = f"skill_{name}"
            if hasattr(module, func_name):
                func = getattr(module, func_name)
            elif hasattr(module, "run"):
                func = module.run

            if func is not None and callable(func):
                self._skills_cache[name] = func
                if self._debug:
                    _logger.debug(f"   ✅ {name} cargado bajo demanda")
                return func
            else:
                _logger.warning(f"   ⚠️ {name} no tiene función ejecutable")
                return None
        except Exception as e:
            _logger.error(f"   ❌ Error cargando {name}: {e}")
            self._failed_skills[name] = str(e)
            return None

    def execute_relevant(self, text: str) -> Optional[str]:
        """Busca y ejecuta la primera habilidad cuyo nombre aparezca en el texto."""
        text_lower = text.lower()
        words = set(text_lower.split())
        for name in self._skills_meta.keys():
            if name.lower() in words:
                func = self.get_skill(name)
                if func:
                    try:
                        return func({"orchestrator": None, "text": text})
                    except Exception as e:
                        _logger.error(f"Error ejecutando skill '{name}': {e}")
                        return None
        return None

    def list_skills(self) -> list:
        return sorted(self._skills_meta.keys())

    def register_skill(self, name: str, path: str, source: str = "skills") -> bool:
        """Registra una habilidad manualmente (para auto-programación)."""
        self._skills_meta[name] = {'path': path, 'source': source}
        # Limpiamos caché por si estaba
        self._skills_cache.pop(name, None)
        return True

    def reload_skill(self, name: str) -> bool:
        """Recarga una habilidad (borra caché y la vuelve a registrar)."""
        if name not in self._skills_meta:
            return False
        self._skills_cache.pop(name, None)
        # No necesitamos recargar el archivo, se cargará la próxima vez que se pida
        return True

    def reload_all(self):
        """Vuelve a escanear los directorios (no recarga módulos ya cargados)."""
        self._skills_meta.clear()
        self._skills_cache.clear()
        self.load_all_skills()