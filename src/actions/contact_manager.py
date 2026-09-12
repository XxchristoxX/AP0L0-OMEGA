# src/actions/contact_manager.py
"""
Gestión de contactos con SQLite.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/contacts.db")

def _get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return conn

def add_contact(name: str, phone: str = "", email: str = "", notes: str = "") -> str:
    if not name:
        return "El nombre es obligatorio."
    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO contacts (name, phone, email, notes) VALUES (?, ?, ?, ?)",
            (name, phone, email, notes)
        )
        conn.commit()
        return f"Contacto '{name}' añadido correctamente."
    except sqlite3.IntegrityError:
        return f"El contacto '{name}' ya existe."
    finally:
        conn.close()

def list_contacts() -> str:
    conn = _get_db()
    cursor = conn.execute("SELECT id, name, phone, email FROM contacts ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return "No hay contactos guardados."
    lines = ["📋 Lista de contactos:"]
    for row in rows:
        parts = [f"ID:{row[0]}", row[1]]
        if row[2]: parts.append(row[2])
        if row[3]: parts.append(row[3])
        lines.append("  " + " | ".join(parts))
    return "\n".join(lines)

def remove_contact(contact_id: int) -> str:
    conn = _get_db()
    cursor = conn.execute("SELECT name FROM contacts WHERE id = ?", (contact_id,))
    row = cursor.fetchone()
    if not row:
        return f"No se encontró contacto con ID {contact_id}."
    name = row[0]
    conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()
    return f"Contacto '{name}' eliminado."

def contact_manager(parameters: dict, player=None, speak=None) -> str:
    action = parameters.get("action", "list")
    if action == "add":
        return add_contact(
            parameters.get("name", ""),
            parameters.get("phone", ""),
            parameters.get("email", ""),
            parameters.get("notes", "")
        )
    elif action == "list":
        return list_contacts()
    elif action == "remove":
        return remove_contact(int(parameters.get("contact_id", 0)))
    else:
        return f"Acción '{action}' no soportada. Usa: add, list, remove"