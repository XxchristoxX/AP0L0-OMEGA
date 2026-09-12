import sqlite3
import time
from pathlib import Path
from typing import Optional, Dict, Any

class Persistence:
    """
    Persistencia sencilla con SQLite para el sistema autónomo.
    Guarda historial de habilidades, intentos, errores y logs.
    """
    def __init__(self, db_path: str = "data/assistant.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_db()

    def _init_db(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT,
            version INTEGER DEFAULT 1,
            file_path TEXT,
            created_at TEXT,
            last_tested_at TEXT,
            status TEXT DEFAULT 'active',  -- active, disabled, failed
            error_message TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS skill_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_name TEXT,
            attempt INTEGER,
            code TEXT,
            success BOOLEAN,
            output TEXT,
            error TEXT,
            timestamp TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS auto_learn_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            level TEXT,
            message TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        self.conn.commit()

    # ---------- Habilidades ----------
    def register_skill(self, name: str, description: str, file_path: str, version: int = 1) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO skills (name, description, version, file_path, created_at, status)
            VALUES (?, ?, ?, ?, datetime('now'), 'active')
            ON CONFLICT(name) DO UPDATE SET
                description=excluded.description,
                version=excluded.version,
                file_path=excluded.file_path,
                status='active',
                error_message=NULL
        """, (name, description, version, file_path))
        self.conn.commit()

    def update_skill_status(self, name: str, status: str, error_message: Optional[str] = None) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE skills SET status=?, error_message=?, last_tested_at=datetime('now')
            WHERE name=?
        """, (status, error_message, name))
        self.conn.commit()

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM skills WHERE name=?", (name,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))

    def get_all_skills(self) -> list:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM skills ORDER BY created_at DESC")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    # ---------- Intentos ----------
    def log_attempt(self, skill_name: str, attempt: int, code: str,
                    success: bool, output: str, error: str) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO skill_attempts (skill_name, attempt, code, success, output, error, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, (skill_name, attempt, code, success, output, error))
        self.conn.commit()

    # ---------- Log del sistema ----------
    def log(self, level: str, message: str) -> None:
        cur = self.conn.cursor()
        cur.execute("INSERT INTO auto_learn_log (timestamp, level, message) VALUES (datetime('now'), ?, ?)",
                    (level, message))
        self.conn.commit()

    # ---------- Meta / límite diario ----------
    def get_meta(self, key: str) -> Optional[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM meta WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO meta (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, value))
        self.conn.commit()

    def get_daily_skill_count(self) -> int:
        today = time.strftime("%Y-%m-%d")
        val = self.get_meta(f"daily_count_{today}")
        return int(val) if val else 0

    def increment_daily_skill_count(self) -> int:
        today = time.strftime("%Y-%m-%d")
        count = self.get_daily_skill_count() + 1
        self.set_meta(f"daily_count_{today}", str(count))
        return count

    def close(self):
        self.conn.close()

    def load_memory(self) -> dict:
        """Carga la memoria desde la tabla meta (si existe)."""
        try:
            val = self.get_meta("memory")
            if val:
                import json
                return json.loads(val)
            return {}
        except Exception:
            return {}

    def save_memory(self, memory: dict) -> None:
        """Guarda la memoria en la tabla meta."""
        import json
        self.set_meta("memory", json.dumps(memory))