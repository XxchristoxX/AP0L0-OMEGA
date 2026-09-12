# actions/todo_list.py
# Lista de tareas con persistencia JSON

import json
import os
from datetime import datetime

class TodoListGenerator:
    def __init__(self):
        self.todo_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'todo_list.json')
        os.makedirs(os.path.dirname(self.todo_path), exist_ok=True)
        if not os.path.exists(self.todo_path):
            self._save([])
        print("[TodoList] Inicializado.")

    def _load(self):
        try:
            with open(self.todo_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    def _save(self, tasks):
        with open(self.todo_path, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)

    def add_task(self, task: str) -> str:
        if not task or not task.strip():
            return "No se proporcionó una tarea válida."
        tasks = self._load()
        new_task = {
            "id": len(tasks) + 1,
            "task": task.strip(),
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "completed": False
        }
        tasks.append(new_task)
        self._save(tasks)
        return f"Tarea añadida: '{task.strip()}' (ID: {new_task['id']})"

    def list_tasks(self) -> str:
        tasks = self._load()
        if not tasks:
            return "No hay tareas pendientes."

        pending = [t for t in tasks if not t.get('completed', False)]
        completed = [t for t in tasks if t.get('completed', False)]

        result = []
        if pending:
            result.append("📋 Tareas Pendientes:")
            for t in pending:
                result.append(f"  [{t['id']}] {t['task']} (Creada: {t['created']})")
        if completed:
            result.append("\n✅ Tareas Completadas:")
            for t in completed:
                result.append(f"  [{t['id']}] {t['task']}")
        if not result:
            return "No hay tareas."
        return "\n".join(result)

    def remove_task(self, task_id: int) -> str:
        tasks = self._load()
        for i, t in enumerate(tasks):
            if t['id'] == task_id:
                removed = tasks.pop(i)
                self._save(tasks)
                return f"Tarea eliminada: '{removed['task']}' (ID: {task_id})"
        return f"No se encontró ninguna tarea con ID {task_id}."

    def clear_tasks(self) -> str:
        tasks = self._load()
        count = len(tasks)
        self._save([])
        return f"Se eliminaron {count} tareas de la lista."