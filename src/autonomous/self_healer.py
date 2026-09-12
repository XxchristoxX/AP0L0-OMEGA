import asyncio
import time
from pathlib import Path
from typing import Callable, Optional

from src.core.persistence import Persistence
from src.skills.auto_programmer_advanced import AutoProgrammer

class SelfHealer:
    """
    Auto‑curador: verifica que las habilidades generadas sigan funcionando.
    Si una falla, intenta mejorarla automáticamente.
    """
    def __init__(self, auto_programmer: AutoProgrammer, persistence: Persistence,
                 check_interval: int = 3600):  # 1 hora por defecto
        self.auto_programmer = auto_programmer
        self.persistence = persistence
        self.check_interval = check_interval

    async def run_loop(self, log_callback: Callable[[str], None]):
        while True:
            await asyncio.sleep(self.check_interval)
            try:
                await self._heal_all(log_callback)
            except Exception as e:
                log_callback(f"[SelfHealer] Error: {e}")

    async def _heal_all(self, log: Callable[[str], None]):
        """Revisa todas las habilidades activas y repara las que fallen."""
        skills = self.persistence.get_all_skills()
        for skill in skills:
            if skill["status"] == "disabled":
                continue
            name = skill["name"]
            file_path = Path(skill["file_path"])
            if not file_path.exists():
                log(f"[SelfHealer] ⚠️ Falta archivo de '{name}', marcando como rota.")
                self.persistence.update_skill_status(name, "failed", "Archivo no encontrado")
                continue

            code = file_path.read_text(encoding="utf-8")
            ok, output, error = self.auto_programmer._test_code_sandboxed(code)
            if not ok:
                log(f"[SelfHealer] 🔧 Habilidad '{name}' falla: {error}. Intentando reparar...")
                # Usar el AutoProgrammer para mejorar
                result = await asyncio.to_thread(
                    self.auto_programmer.generate_and_test,
                    task_description=f"Reparar habilidad '{name}' que falla con: {error}",
                    skill_name=name,
                    action="improve"
                )
                log(f"[SelfHealer] {result}")
                self.persistence.update_skill_status(name, "active" if "correctamente" in result else "failed")
            else:
                # Actualizar timestamp
                self.persistence.update_skill_status(name, "active")