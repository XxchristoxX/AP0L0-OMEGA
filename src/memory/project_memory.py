# src/memory/project_memory.py
"""
Gestión de memoria persistente para proyectos y contexto.
Basado en OpenJarvis y Mark-L.
"""
import json
from pathlib import Path
from datetime import datetime

class ProjectMemory:
    def __init__(self, memory_file="data/project_memory.json"):
        self.memory_file = Path(memory_file)
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()
    
    def _load(self):
        if self.memory_file.exists():
            try:
                return json.loads(self.memory_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}
    
    def save(self):
        self.memory_file.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    def get_project(self, name):
        return self.data.get("projects", {}).get(name, {})
    
    def set_project(self, name, data):
        if "projects" not in self.data:
            self.data["projects"] = {}
        self.data["projects"][name] = data
        self.data["projects"][name]["updated"] = datetime.now().isoformat()
        self.save()
    
    def get_context(self):
        """Devuelve el contexto actual para inyectar en el prompt."""
        projects = self.data.get("projects", {})
        context = []
        for name, data in projects.items():
            context.append(f"Proyecto: {name}")
            if "description" in data:
                context.append(f"  Descripción: {data['description']}")
            if "status" in data:
                context.append(f"  Estado: {data['status']}")
        return "\n".join(context) if context else ""