# src/actions/obsidian_helper.py
"""
Ayudante para Obsidian en AP0L0
"""

import os
import json
import glob
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "api_keys.json")


def _load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def obtenir_chemin_vault():
    cfg = _load_config()
    vault_path = cfg.get("obsidian_vault_path")
    if vault_path and os.path.isdir(vault_path):
        return vault_path
    default_path = os.path.join(BASE_DIR, "ObsidianVault")
    if not os.path.exists(default_path):
        os.makedirs(default_path, exist_ok=True)
    return default_path


def creer_ou_modifier_note(titre, contenu):
    vault = obtenir_chemin_vault()
    filename = os.path.basename(titre)
    if not filename.endswith(".md"):
        filename += ".md"
    filepath = os.path.join(vault, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(contenu)
        return True, f"Nota '{titre}' creada/modificada."
    except Exception as e:
        return False, f"Error: {e}"


def lire_note(titre):
    vault = obtenir_chemin_vault()
    filename = os.path.basename(titre)
    if not filename.endswith(".md"):
        filename += ".md"
    filepath = os.path.join(vault, filename)
    if not os.path.exists(filepath):
        return False, f"Nota '{titre}' no encontrada."
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return True, content
    except Exception as e:
        return False, f"Error: {e}"


def supprimer_note(titre):
    vault = obtenir_chemin_vault()
    filename = os.path.basename(titre)
    if not filename.endswith(".md"):
        filename += ".md"
    filepath = os.path.join(vault, filename)
    if not os.path.exists(filepath):
        return False, f"Nota '{titre}' no encontrada."
    try:
        os.remove(filepath)
        return True, f"Nota '{titre}' eliminada."
    except Exception as e:
        return False, f"Error: {e}"


def lister_notes():
    vault = obtenir_chemin_vault()
    files = glob.glob(os.path.join(vault, "*.md"))
    notes = []
    for f in files:
        try:
            stat = os.stat(f)
            notes.append({
                "titre": os.path.basename(f)[:-3],
                "taille": stat.st_size,
                "mtime": stat.st_mtime
            })
        except Exception:
            pass
    notes.sort(key=lambda x: x["mtime"], reverse=True)
    return notes


def rechercher_notes(query):
    vault = obtenir_chemin_vault()
    files = glob.glob(os.path.join(vault, "*.md"))
    results = []
    query = query.lower()
    for f in files:
        titre = os.path.basename(f)[:-3]
        matched = False
        snippet = ""
        if query in titre.lower():
            matched = True
        try:
            with open(f, "r", encoding="utf-8") as file_obj:
                content = file_obj.read()
                if query in content.lower():
                    matched = True
                    idx = content.lower().find(query)
                    start = max(0, idx - 40)
                    end = min(len(content), idx + 80)
                    snippet = "..." + content[start:end].replace("\n", " ") + "..."
        except Exception:
            pass
        if matched:
            results.append({"titre": titre, "snippet": snippet})
    return results


# ===== FUNCIÓN EXPORTABLE =====

async def obsidian_control(params: dict, player=None, speak=None) -> str:
    action = params.get("action", "list")
    if action == "list":
        notes = lister_notes()
        if not notes:
            return "No hay notas en el vault."
        result = "Notas:\n" + "\n".join(f"  • {n['titre']}" for n in notes[:20])
    elif action == "read":
        titre = params.get("titre", "")
        if not titre:
            return "Falta el título."
        ok, content = lire_note(titre)
        result = content if ok else f"Error: {content}"
    elif action == "write":
        titre = params.get("titre", "")
        contenu = params.get("contenu", "")
        if not titre:
            return "Falta el título."
        ok, msg = creer_ou_modifier_note(titre, contenu)
        result = msg if ok else f"Error: {msg}"
    elif action == "delete":
        titre = params.get("titre", "")
        if not titre:
            return "Falta el título."
        ok, msg = supprimer_note(titre)
        result = msg if ok else f"Error: {msg}"
    elif action == "search":
        query = params.get("query", "")
        if not query:
            return "Falta la búsqueda."
        results = rechercher_notes(query)
        if not results:
            return f"No se encontraron notas con '{query}'."
        result = f"Resultados para '{query}':\n" + "\n".join(f"  • {r['titre']}" for r in results)
    else:
        result = "Acción no soportada."
    if speak:
        speak(result)
    if player:
        player.write_log(f"[Obsidian] {result}")
    return result