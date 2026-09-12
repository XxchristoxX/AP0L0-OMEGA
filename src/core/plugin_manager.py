# src/core/plugin_manager.py
"""
Gestión avanzada de plugins con persistencia y API.
"""

import json
import os
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

from src.core.config import get_config


class PluginManager:
    """Gestor de plugins con persistencia y control de estado."""

    def __init__(self, plugin_dir: str = "plugins"):
        self.plugin_dir = Path(plugin_dir)
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self._plugins: Dict[str, Dict[str, Any]] = {}
        self._loaded = False
        self._load_plugins()

    def _load_plugins(self):
        """Carga todos los plugins del directorio."""
        self._plugins = {}
        for plugin_file in self.plugin_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            try:
                plugin_name = plugin_file.stem
                spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Verificar que tiene la estructura esperada
                if hasattr(module, "PLUGIN") and hasattr(module, "run"):
                    plugin_info = {
                        "name": plugin_name,
                        "module": module,
                        "run": module.run,
                        "enabled": self._is_enabled(plugin_name),
                        "description": module.PLUGIN.get("description", ""),
                        "parameters": module.PLUGIN.get("parameters", {}),
                    }
                    self._plugins[plugin_name] = plugin_info
                    print(f"[PluginManager] ✅ Cargado: {plugin_name}")
            except Exception as e:
                print(f"[PluginManager] ⚠️ Error cargando {plugin_file.name}: {e}")
        self._loaded = True

    def _is_enabled(self, name: str) -> bool:
        """Verifica si un plugin está habilitado."""
        try:
            from src.memory.config_manager import get_plugin_enabled
            return get_plugin_enabled(name)
        except Exception:
            return True

    def _save_enabled(self, name: str, enabled: bool):
        """Guarda el estado de un plugin."""
        try:
            from src.memory.config_manager import save_plugin_enabled
            save_plugin_enabled(name, enabled)
        except Exception as e:
            print(f"[PluginManager] Error guardando estado: {e}")

    def get_plugin(self, name: str) -> Optional[Dict[str, Any]]:
        """Obtiene un plugin por nombre."""
        if not self._loaded:
            self._load_plugins()
        return self._plugins.get(name)

    def run_plugin(self, name: str, parameters: Dict[str, Any] = None) -> str:
        """Ejecuta un plugin."""
        plugin = self.get_plugin(name)
        if plugin is None:
            return f"Plugin '{name}' no encontrado"
        if not plugin.get("enabled", True):
            return f"Plugin '{name}' está deshabilitado"
        try:
            result = plugin["run"](parameters or {})
            return str(result) if result else "Ejecutado correctamente"
        except Exception as e:
            return f"Error ejecutando plugin '{name}': {e}"

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Lista todos los plugins con su estado."""
        if not self._loaded:
            self._load_plugins()
        return [
            {
                "name": name,
                "enabled": info.get("enabled", True),
                "description": info.get("description", ""),
                "parameters": info.get("parameters", {}),
            }
            for name, info in self._plugins.items()
        ]

    def enable_plugin(self, name: str) -> bool:
        """Habilita un plugin."""
        if name not in self._plugins:
            return False
        self._plugins[name]["enabled"] = True
        self._save_enabled(name, True)
        return True

    def disable_plugin(self, name: str) -> bool:
        """Deshabilita un plugin."""
        if name not in self._plugins:
            return False
        self._plugins[name]["enabled"] = False
        self._save_enabled(name, False)
        return True

    def reload_plugin(self, name: str) -> bool:
        """Recarga un plugin específico."""
        if name not in self._plugins:
            return False
        plugin_file = self.plugin_dir / f"{name}.py"
        if not plugin_file.exists():
            return False
        # Eliminar del caché
        module_name = f"plugins.{name}"
        if module_name in importlib.sys.modules:
            del importlib.sys.modules[module_name]
        # Recargar
        self._load_plugins()
        return name in self._plugins

    def reload_all(self):
        """Recarga todos los plugins."""
        self._loaded = False
        self._load_plugins()


# ──────────────────────────────────────────────────────────────
# INSTANCIA GLOBAL
# ──────────────────────────────────────────────────────────────

_plugin_manager = None

def get_plugin_manager() -> PluginManager:
    """Obtiene la instancia global del gestor de plugins."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


# ──────────────────────────────────────────────────────────────
# FUNCIÓN DE CONVENIENCIA
# ──────────────────────────────────────────────────────────────

def run_plugin(name: str, parameters: Dict[str, Any] = None) -> str:
    """Ejecuta un plugin por nombre."""
    return get_plugin_manager().run_plugin(name, parameters)

def list_plugins() -> List[Dict[str, Any]]:
    """Lista todos los plugins disponibles."""
    return get_plugin_manager().list_plugins()