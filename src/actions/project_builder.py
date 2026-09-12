# src/actions/project_builder.py
"""
Constructor de proyectos para AP0L0
"""

import os
import time
import threading
import json
from pathlib import Path
from typing import Optional

from src.core.config import _get_config
from src.core.ai_providers import generate


class ProjectBuilder:
    def __init__(self, gui=None):
        self.gui = gui
        self.project_path = None
        self.project_name = None
        self.run_id = None
        self.conversation_history = []
        self._MAX_HISTORY = 20

    def start_project(self, project_name, project_path):
        self.project_path = project_path
        self.project_name = project_name
        if self.gui:
            self.gui.set_project_path(project_path)
            self.gui.show_dev_panel()
            self.gui.update_status(f"Dossier: {project_name}")

    def load_existing_project(self, folder_path):
        self.project_path = folder_path
        self.project_name = os.path.basename(folder_path)
        if self.gui:
            self.gui.set_project_path(folder_path)
            self.gui.show_dev_panel()

    def _scan_directory(self, path):
        structure = {}
        try:
            for item in os.listdir(path):
                if item in ['.git', '__pycache__', 'venv', 'node_modules']:
                    continue
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    structure[item] = self._scan_directory(full_path)
                else:
                    structure[item] = "file"
        except Exception:
            pass
        return structure

    def _build_context(self):
        context = ""
        if not self.project_path or not os.path.exists(self.project_path):
            return context
        file_count = 0
        for root, dirs, files in os.walk(self.project_path):
            for d in ['.git', '__pycache__', 'venv', 'node_modules']:
                if d in dirs:
                    dirs.remove(d)
            for file in files:
                if file_count >= 15:
                    break
                if file.endswith(('.html', '.css', '.js', '.py', '.json', '.txt')):
                    full_path = os.path.join(root, file)
                    if os.path.getsize(full_path) > 100000:
                        continue
                    rel_path = os.path.relpath(full_path, self.project_path).replace("\\", "/")
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        context += f"--- Archivo: {rel_path} ---\n{content}\n"
                        file_count += 1
                    except Exception:
                        pass
        return context

    def _parse_and_save_files(self, raw_text):
        import re
        os.makedirs(self.project_path, exist_ok=True)
        pattern = r"---BEGIN_FILE:\s*(.+?)---(.*?)(?=---END_FILE---|---BEGIN_FILE:|$)"
        matches = list(re.finditer(pattern, raw_text, re.DOTALL))
        if not matches:
            # Fallback: bloques de código markdown
            md_blocks = re.findall(r"```[a-zA-Z0-9_-]*\s*(.*?)```", raw_text, re.DOTALL)
            if md_blocks:
                content = "\n\n".join(md_blocks)
                filename = "index.html"
                full_path = os.path.join(self.project_path, filename)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content.strip())
                return
            # Fallback: si no hay bloques, guardar como respuesta
            debug_path = os.path.join(self.project_path, "reponse_ia_brute.txt")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(raw_text)
            return
        for match in matches:
            filename = match.group(1).strip()
            content = match.group(2).strip()
            if ".." in filename:
                continue
            full_path = os.path.join(self.project_path, filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

    def handle_message(self, message, image_path=None):
        if not self.project_path:
            return "Primero crea o abre un proyecto."
        self.conversation_history.append({"role": "user", "content": message})
        if len(self.conversation_history) > self._MAX_HISTORY * 2:
            self.conversation_history = self.conversation_history[-(self._MAX_HISTORY * 2):]
        # Generar código con IA (usando el proveedor de AP0L0)
        system_prompt = (
            "Eres un desarrollador experto. Genera código para el proyecto solicitado. "
            "Usa el formato ---BEGIN_FILE: nombre.ext--- ... ---END_FILE--- para cada archivo. "
            "No uses markdown, solo el formato especificado."
        )
        context = self._build_context()
        full_prompt = f"{context}\n\n{message}" if context else message
        raw_text = generate(full_prompt, system_instruction=system_prompt, provider="gemini")
        self._parse_and_save_files(raw_text)
        return "Proyecto generado."


# ===== FUNCIÓN EXPORTABLE =====

async def project_builder(params: dict, player=None, speak=None) -> str:
    action = params.get("action", "create")
    project_name = params.get("project_name", "proyecto_apolo")
    description = params.get("description", "")
    if action == "create":
        if not description:
            return "Falta la descripción del proyecto."
        desktop = Path.home() / "Desktop" / "Proyectos_APOLO"
        desktop.mkdir(parents=True, exist_ok=True)
        project_path = desktop / project_name.replace(" ", "_")
        project_path.mkdir(exist_ok=True)
        builder = ProjectBuilder()
        builder.start_project(project_name, str(project_path))
        result = builder.handle_message(description)
        if speak:
            speak("Proyecto creado.")
        if player:
            player.write_log(f"[ProjectBuilder] {result}")
        return f"Proyecto '{project_name}' creado en {project_path}."
    else:
        return "Acción no soportada."