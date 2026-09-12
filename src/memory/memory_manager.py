# src/memory/memory_manager.py
"""
Gestión de memoria persistente para AP0L0.
Maneja la memoria a largo plazo, sesiones, resúmenes y límites.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, Any, Optional, List

# ============================================================================
# CONFIGURACIÓN DE RUTAS
# ============================================================================

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
MEMORY_PATH = BASE_DIR / "memory" / "long_term.json"
_lock = Lock()
MAX_VALUE_LENGTH = 380
MEMORY_MAX_CHARS = 3200  # Aumentado ligeramente para permitir más contexto


def _empty_memory() -> dict:
    """Retorna una estructura de memoria vacía."""
    return {
        "identity": {},
        "preferences": {},
        "projects": {},
        "relationships": {},
        "wishes": {},
        "notes": {},
        "sessions": [],          # Resúmenes de sesiones anteriores
        "reflections": {},       # Reflexiones generadas
        "monitors": {},          # Temas monitorizados
        "skills": {},            # Habilidades generadas
        "stats": {               # Estadísticas de uso
            "total_interactions": 0,
            "last_interaction": "",
            "daily_skill_count": 0,
            "last_skill_date": ""
        }
    }


def load_memory() -> dict:
    """Carga la memoria desde el archivo JSON."""
    if not MEMORY_PATH.exists():
        return _empty_memory()
    with _lock:
        try:
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                base = _empty_memory()
                # Asegurar que todas las claves existan
                for key in base:
                    if key not in data:
                        data[key] = {} if key not in ("sessions", "stats") else []
                return data
            return _empty_memory()
        except Exception as e:
            print(f"[Memory] ⚠️ Load error: {e}")
            return _empty_memory()


def _all_entries(memory: dict) -> list[tuple]:
    """Devuelve todas las entradas de la memoria para recorte."""
    entries = []
    for cat, items in memory.items():
        if cat in ("sessions", "stats", "monitors"):
            continue
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            if isinstance(entry, dict) and "value" in entry:
                entries.append((cat, key, entry))
    return entries


def _trim_to_limit(memory: dict) -> dict:
    """Recorta la memoria si excede el límite de caracteres."""
    if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
        return memory
    entries = _all_entries(memory)
    # Ordenar por fecha de actualización (las más antiguas primero)
    entries.sort(key=lambda t: t[2].get("updated", "0000-00-00"))
    for cat, key, _ in entries:
        if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
            break
        del memory[cat][key]
        print(f"[Memory] 🗑️ Trimmed {cat}/{key}")
    return memory


def save_memory(memory: dict) -> None:
    """Guarda la memoria en el archivo JSON."""
    if not isinstance(memory, dict):
        return
    memory = _trim_to_limit(memory)
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        MEMORY_PATH.write_text(
            json.dumps(memory, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _truncate_value(val: str) -> str:
    """Trunca un valor si excede la longitud máxima."""
    if isinstance(val, str) and len(val) > MAX_VALUE_LENGTH:
        return val[:MAX_VALUE_LENGTH].rstrip() + "…"
    return val


def _recursive_update(target: dict, updates: dict) -> bool:
    """Actualiza recursivamente un diccionario."""
    changed = False
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, dict) and "value" not in value:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
                changed = True
            if _recursive_update(target[key], value):
                changed = True
        else:
            new_val = _truncate_value(str(value["value"] if isinstance(value, dict) else value))
            entry = {"value": new_val, "updated": datetime.now().strftime("%Y-%m-%d")}
            existing = target.get(key, {})
            if not isinstance(existing, dict) or existing.get("value") != new_val:
                target[key] = entry
                changed = True
    return changed


def update_memory(memory_update: dict) -> dict:
    """
    Actualiza la memoria con un diccionario de actualizaciones.
    Las claves pueden ser: identity, preferences, projects, relationships, wishes, notes.
    """
    if not isinstance(memory_update, dict) or not memory_update:
        return load_memory()
    memory = load_memory()
    if _recursive_update(memory, memory_update):
        # Actualizar estadísticas
        if "stats" not in memory:
            memory["stats"] = {}
        memory["stats"]["total_interactions"] = memory["stats"].get("total_interactions", 0) + 1
        memory["stats"]["last_interaction"] = datetime.now().isoformat()
        save_memory(memory)
        print(f"[Memory] 💾 Saved: {list(memory_update.keys())}")
    return memory


def format_memory_for_prompt(memory: dict | None) -> str:
    """
    Formatea la memoria para inyectarla en el prompt del sistema.
    """
    if not memory:
        return ""

    lines = []
    # === IDENTIDAD ===
    identity = memory.get("identity", {})
    id_fields = ["name", "age", "birthday", "city", "job", "language", "school", "nationality"]
    for field in id_fields:
        entry = identity.get(field)
        if entry:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"{field.title()}: {val}")
    for key, entry in identity.items():
        if key in id_fields:
            continue
        val = entry.get("value") if isinstance(entry, dict) else entry
        if val:
            lines.append(f"{key.replace('_', ' ').title()}: {val}")

    # === PREFERENCIAS ===
    prefs = memory.get("preferences", {})
    if prefs:
        lines.append("")
        lines.append("Preferences:")
        for key, entry in list(prefs.items())[:15]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    # === PROYECTOS ===
    projects = memory.get("projects", {})
    if projects:
        lines.append("")
        lines.append("Active Projects / Goals:")
        for key, entry in list(projects.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    # === RELACIONES ===
    rels = memory.get("relationships", {})
    if rels:
        lines.append("")
        lines.append("People in their life:")
        for key, entry in list(rels.items())[:10]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    # === DESEOS ===
    wishes = memory.get("wishes", {})
    if wishes:
        lines.append("")
        lines.append("Wishes / Plans / Wants:")
        for key, entry in list(wishes.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    # === NOTAS ===
    notes = memory.get("notes", {})
    if notes:
        lines.append("")
        lines.append("Other notes:")
        for key, entry in list(notes.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key}: {val}")

    if not lines:
        return ""

    header = "[WHAT YOU KNOW ABOUT THIS PERSON — use naturally, never recite like a list]\n"
    result = header + "\n".join(lines)
    if len(result) > 2500:
        result = result[:2497] + "…"

    return result + "\n"


# ============================================================================
# FUNCIONES DE MEMORIA DE SESIÓN
# ============================================================================

_SESSION_MAX = 5  # Número máximo de resúmenes de sesión a mantener


def save_session_summary(summary: str, language: str = "") -> None:
    """
    Guarda un resumen de la sesión actual en la memoria.
    """
    summary = (summary or "").strip()
    if not summary:
        return
    memory = load_memory()
    sessions = memory.get("sessions", [])
    if not isinstance(sessions, list):
        sessions = []
    entry: dict = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "summary": summary[:280],
    }
    if language:
        entry["language"] = language
    sessions.append(entry)
    # Mantener solo las últimas N sesiones
    if len(sessions) > _SESSION_MAX:
        sessions = sessions[-_SESSION_MAX:]
    memory["sessions"] = sessions
    # Actualizar estadísticas
    if "stats" not in memory:
        memory["stats"] = {}
    memory["stats"]["last_session"] = datetime.now().isoformat()
    save_memory(memory)
    print(f"[Memory] 📝 Session saved ({entry['date']}): {summary[:60]}…")


def pop_last_session() -> dict | None:
    """
    Obtiene y elimina el último resumen de sesión (para el briefing matutino).
    """
    with _lock:
        if not MEMORY_PATH.exists():
            return None
        try:
            memory = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            sessions = memory.get("sessions", [])
            if not isinstance(sessions, list) or not sessions:
                return None
            entry = sessions.pop()  # Elimina el último
            memory["sessions"] = sessions
            MEMORY_PATH.write_text(
                json.dumps(memory, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return entry
        except Exception as e:
            print(f"[Memory] ⚠️ pop_last_session error: {e}")
            return None


def get_last_session_summary() -> str:
    """
    Obtiene el último resumen de sesión sin eliminarlo.
    """
    memory = load_memory()
    sessions = memory.get("sessions", [])
    if sessions and isinstance(sessions, list):
        last = sessions[-1]
        return last.get("summary", "")
    return ""


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def save_user_language(lang: str) -> None:
    """Guarda el idioma preferido del usuario en memoria."""
    if not lang:
        return
    update_memory({"identity": {"language": {"value": lang}}})


def get_user_language() -> str:
    """Recupera el idioma preferido del usuario desde memoria."""
    memory = load_memory()
    lang_entry = memory.get("identity", {}).get("language", {})
    if isinstance(lang_entry, dict):
        return lang_entry.get("value", "")
    return ""


def remember(key: str, value: str, category: str = "notes") -> str:
    """Función de conveniencia para recordar algo."""
    valid = {"identity", "preferences", "projects", "relationships", "wishes", "notes"}
    if category not in valid:
        category = "notes"
    update_memory({category: {key: {"value": value}}})
    return f"Remembered: {category}/{key} = {value}"


def forget(key: str, category: str = "notes") -> str:
    """Función de conveniencia para olvidar algo."""
    memory = load_memory()
    cat = memory.get(category, {})
    if key in cat:
        del cat[key]
        memory[category] = cat
        save_memory(memory)
        return f"Forgotten: {category}/{key}"
    return f"Not found: {category}/{key}"


# ============================================================================
# FUNCIONES PARA LÍMITES DIARIOS
# ============================================================================

def get_daily_skill_count() -> int:
    """Obtiene el número de habilidades creadas hoy."""
    memory = load_memory()
    stats = memory.get("stats", {})
    today = datetime.now().strftime("%Y-%m-%d")
    if stats.get("last_skill_date") != today:
        return 0
    return stats.get("daily_skill_count", 0)


def increment_daily_skill_count() -> int:
    """Incrementa el contador diario de habilidades creadas."""
    memory = load_memory()
    stats = memory.get("stats", {})
    today = datetime.now().strftime("%Y-%m-%d")
    if stats.get("last_skill_date") != today:
        stats["daily_skill_count"] = 1
        stats["last_skill_date"] = today
    else:
        stats["daily_skill_count"] = stats.get("daily_skill_count", 0) + 1
    memory["stats"] = stats
    save_memory(memory)
    return stats["daily_skill_count"]


def reset_daily_skill_count_if_needed() -> None:
    """Reinicia el contador diario si es un nuevo día."""
    memory = load_memory()
    stats = memory.get("stats", {})
    today = datetime.now().strftime("%Y-%m-%d")
    if stats.get("last_skill_date") != today:
        stats["daily_skill_count"] = 0
        stats["last_skill_date"] = today
        memory["stats"] = stats
        save_memory(memory)