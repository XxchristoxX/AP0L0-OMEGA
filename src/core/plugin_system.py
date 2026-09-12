# src/core/plugin_system.py
"""
Sistema de plugins para AP0L0 - Estilo Mark LI.
Drop a single .py file into plugins/ and the assistant learns a new skill.
"""
import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Dict, Any, Callable, Optional

class PluginSystem:
    """
    Sistema de carga de plugins dinámicos.
    """
    
    def __init__(self, plugin_dir: str = "plugins"):
        self.plugin_dir = Path(plugin_dir)
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self.plugins: Dict[str, Dict[str, Any]] = {}
        self._loaded = False
        
    def load_plugins(self) -> Dict[str, Dict[str, Any]]:
        """
        Carga todos los plugins del directorio plugins/.
        """
        self.plugins = {}
        
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
                
                # Buscar la función run o la clase Plugin
                plugin_info = self._extract_plugin_info(module, plugin_name)
                if plugin_info:
                    self.plugins[plugin_name] = plugin_info
                    print(f"[PluginSystem] ✅ Cargado: {plugin_name}")
                    
            except Exception as e:
                print(f"[PluginSystem] ⚠️ Error cargando {plugin_file.name}: {e}")
                
        self._loaded = True
        return self.plugins
    
    def _extract_plugin_info(self, module, name: str) -> Optional[Dict[str, Any]]:
        """
        Extrae información del plugin.
        """
        info = {
            "name": name,
            "module": module,
            "run": None,
            "description": "",
            "parameters": {},
        }
        
        # Buscar función run
        if hasattr(module, "run") and callable(module.run):
            info["run"] = module.run
            
            # Extraer documentación
            if module.run.__doc__:
                info["description"] = module.run.__doc__.strip()
                
            # Extraer parámetros de la firma
            sig = inspect.signature(module.run)
            for param_name, param in sig.parameters.items():
                if param_name != "params":
                    info["parameters"][param_name] = {
                        "default": param.default if param.default != inspect.Parameter.empty else None,
                        "required": param.default == inspect.Parameter.empty
                    }
                    
        # Buscar clase Plugin
        elif hasattr(module, "Plugin"):
            plugin_class = module.Plugin
            if hasattr(plugin_class, "run") and callable(plugin_class.run):
                info["run"] = lambda params: plugin_class().run(params)
                if plugin_class.__doc__:
                    info["description"] = plugin_class.__doc__.strip()
                    
        # Buscar función main o execute
        elif hasattr(module, "main") and callable(module.main):
            info["run"] = module.main
            
        if info["run"] is None:
            return None
            
        return info
    
    def get_plugin(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un plugin por nombre.
        """
        if not self._loaded:
            self.load_plugins()
        return self.plugins.get(name)
    
    def run_plugin(self, name: str, params: Dict[str, Any] = None) -> Any:
        """
        Ejecuta un plugin.
        """
        plugin = self.get_plugin(name)
        if plugin is None:
            return f"Plugin '{name}' no encontrado."
            
        try:
            if params is None:
                params = {}
            result = plugin["run"](params)
            return result
        except Exception as e:
            return f"Error ejecutando plugin '{name}': {e}"
    
    def list_plugins(self) -> str:
        """
        Lista todos los plugins disponibles.
        """
        if not self._loaded:
            self.load_plugins()
            
        if not self.plugins:
            return "No hay plugins cargados."
            
        lines = ["Plugins disponibles:"]
        for name, info in self.plugins.items():
            desc = info.get("description", "Sin descripción")[:60]
            lines.append(f"  • {name}: {desc}")
        return "\n".join(lines)
    
    def reload_plugin(self, name: str) -> bool:
        """
        Recarga un plugin específico.
        """
        if name not in self.plugins:
            return False
            
        # Eliminar del caché de módulos
        module_name = self.plugins[name]["module"].__name__
        if module_name in sys.modules:
            del sys.modules[module_name]
            
        # Recargar
        self.plugins.pop(name, None)
        self.load_plugins()
        return name in self.plugins