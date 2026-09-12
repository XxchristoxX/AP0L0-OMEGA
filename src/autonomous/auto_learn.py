# src/autonomous/auto_learn.py
"""
Aprendiz autónomo avanzado con límite diario configurable, generación de habilidades,
guardado de ideas fallidas y estadísticas de evolución.
Versión definitiva: evita repetición de propuestas mediante un historial de ideas fallidas.
"""

import asyncio
import json
import re
import time
import random
from pathlib import Path
from typing import Callable, Optional, Dict, List

# ===== CONFIGURACIÓN =====
try:
    from config.settings import API_CONFIG_PATH, LIVE_MODEL, AUTO_LEARN_INTERVAL
except ImportError:
    API_CONFIG_PATH = Path("config/api_keys.json")
    AUTO_LEARN_INTERVAL = 600
    LIVE_MODEL = "gemini-3.5-flash-lite"

try:
    from src.core.multi_provider import MultiProvider
except ImportError:
    class MultiProvider:
        def generate(self, prompt: str):
            return None, "dummy"

try:
    from src.utils.naming import generate_skill_name
except ImportError:
    def generate_skill_name(desc: str) -> str:
        import re
        words = re.findall(r'[a-zA-Záéíóúñ]+', desc.lower())
        return '_'.join(words[:4]) if words else "skill_auto"

DAILY_LIMIT = 50


def _get_api_key() -> str:
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("gemini_api_key", "")
    except Exception as e:
        print(f"[AutoLearn] Error al leer API key: {e}")
        return ""


class AutonomousLearner:
    def __init__(
        self,
        router,
        skills_registry,
        self_healer=None,
        auto_programmer=None,
        persistence=None,
        daily_limit: int = DAILY_LIMIT,
    ):
        self.router = router
        self.skills_registry = skills_registry
        self.self_healer = self_healer
        self.auto_programmer = auto_programmer
        self.persistence = persistence
        self.daily_limit = daily_limit

        self.ideas_dir = Path("data/ideas")
        self.ideas_dir.mkdir(parents=True, exist_ok=True)

        self.stats = {
            "total_attempts": 0,
            "successful_skills": 0,
            "failed_ideas": 0,
            "last_run": None,
        }

        # Historial de propuestas fallidas o ya existentes
        self._failed_proposals: Dict[str, float] = {}  # skill_name -> timestamp
        self._proposal_cooldown = 600  # 10 minutos
        self._max_failed_retries = 3   # después de 3 fallos, cambiar de tema

        self._load_stats()

    def _load_stats(self):
        if self.persistence is None:
            return
        try:
            memory = self.persistence.load_memory()
            if "auto_learn_stats" in memory:
                self.stats.update(memory["auto_learn_stats"])
        except Exception as e:
            print(f"[AutoLearn] Error cargando estadísticas: {e}")

    def _save_stats(self):
        if self.persistence is None:
            return
        try:
            memory = self.persistence.load_memory()
            memory["auto_learn_stats"] = self.stats
            self.persistence.save_memory(memory)
        except Exception as e:
            print(f"[AutoLearn] Error guardando estadísticas: {e}")

    async def run_loop(self, log_callback: Callable[[str], None]):
        while True:
            await asyncio.sleep(AUTO_LEARN_INTERVAL)
            try:
                await self._autonomous_evolution(log_callback)
            except Exception as e:
                log_callback(f"[Autonomous] Error en bucle principal: {e}")

    async def _autonomous_evolution(self, log: Callable[[str], None]):
        try:
            self.stats["total_attempts"] += 1
            api_key = _get_api_key()
            if not api_key:
                log("[Autonomous] ⚠️ No se encontró API key. Saltando evolución.")
                return

            if self.persistence:
                daily_count = self.persistence.get_daily_skill_count()
                if daily_count >= self.daily_limit:
                    log(f"[Autonomous] ⏳ Límite diario de {self.daily_limit} habilidades alcanzado.")
                    return

            # ===== GENERAR PROPUESTA CON VARIEDAD =====
            # Añadir un contexto aleatorio para que la IA no repita la misma idea
            temas = [
                "organización de archivos",
                "automatización de correos",
                "control de aplicaciones",
                "resumen de noticias",
                "gestión de tareas",
                "monitoreo del sistema",
                "seguridad informática",
                "asistente de voz",
                "integración con redes sociales",
                "mejora de rendimiento"
            ]
            tema = random.choice(temas)

            prompt = (
                f"Eres AP0L0, un asistente IA avanzado con capacidad de auto‑programación. "
                f"Propón UNA nueva habilidad o mejora concreta para ti mismo, relacionada con '{tema}'. "
                "La propuesta debe ser práctica, útil y realista para un asistente de escritorio. "
                "Responde en español, máximo 2 oraciones, describiendo claramente la funcionalidad."
            )

            provider = MultiProvider()
            try:
                response_text, used_provider = await asyncio.wait_for(
                    asyncio.to_thread(provider.generate, prompt),
                    timeout=30
                )
            except asyncio.TimeoutError:
                log("[Autonomous] ⏰ Timeout esperando respuesta del proveedor.")
                return

            if response_text is None:
                log("[Autonomous] ⛔ TODOS LOS PROVEEDORES HAN FALLADO.")
                return

            propuesta = response_text.strip()
            skill_name = generate_skill_name(propuesta)

            log(f"[Autonomous] 💡 Propuesta de mejora (usando {used_provider}): {propuesta[:200]}...")

            # ===== VERIFICAR SI FALLÓ DEMASIADAS VECES =====
            if skill_name in self._failed_proposals:
                fallos = self._failed_proposals.get(skill_name, 0)
                if fallos >= self._max_failed_retries:
                    log(f"[Autonomous] ⛔ La propuesta '{skill_name}' ha fallado {fallos} veces. Buscando otra idea...")
                    # Forzar una nueva propuesta saltando a la siguiente iteración
                    return

            # ===== VERIFICAR SI YA EXISTE =====
            if self.skills_registry is not None:
                try:
                    existing_func = self.skills_registry.get_skill(skill_name)
                    if existing_func is not None:
                        log(f"[Autonomous] ⏭️ La habilidad '{skill_name}' ya existe. Saltando.")
                        self._failed_proposals[skill_name] = self._failed_proposals.get(skill_name, 0) + 1
                        return
                except Exception as e:
                    log(f"[Autonomous] ⚠️ Error verificando existencia: {e}")

            if self.persistence is not None:
                try:
                    existing_skills = self.persistence.get_all_skills()
                    for skill in existing_skills:
                        if skill.get("name") == skill_name:
                            log(f"[Autonomous] ⏭️ La habilidad '{skill_name}' ya está registrada. Saltando.")
                            self._failed_proposals[skill_name] = self._failed_proposals.get(skill_name, 0) + 1
                            return
                except Exception as e:
                    log(f"[Autonomous] ⚠️ Error verificando en persistencia: {e}")

            # ===== CREAR LA HABILIDAD =====
            log(f"[Autonomous] 🛠️ Creando habilidad '{skill_name}'...")

            if self.auto_programmer:
                try:
                    resultado = await asyncio.wait_for(
                        asyncio.to_thread(
                            self.auto_programmer.generate_and_test,
                            task_description=propuesta,
                            skill_name=skill_name,
                            action="create"
                        ),
                        timeout=120
                    )
                    if "correctamente" in resultado:
                        self.stats["successful_skills"] += 1
                        if self.persistence:
                            self.persistence.increment_daily_skill_count()
                        log(f"[Autonomous] ✅ {resultado}")
                        # Limpiar fallos si tuvo éxito
                        if skill_name in self._failed_proposals:
                            del self._failed_proposals[skill_name]
                    else:
                        self.stats["failed_ideas"] += 1
                        log(f"[Autonomous] ⚠️ {resultado}")
                        self._failed_proposals[skill_name] = self._failed_proposals.get(skill_name, 0) + 1
                        self._save_idea(propuesta, skill_name)
                except asyncio.TimeoutError:
                    log("[Autonomous] ⏰ Timeout en AutoProgrammer.")
                    self._failed_proposals[skill_name] = self._failed_proposals.get(skill_name, 0) + 1
                    self._save_idea(propuesta, skill_name)
                except Exception as e:
                    self.stats["failed_ideas"] += 1
                    log(f"[Autonomous] ❌ Error al crear habilidad: {e}")
                    self._failed_proposals[skill_name] = self._failed_proposals.get(skill_name, 0) + 1
                    self._save_idea(propuesta, skill_name)
            else:
                log("[Autonomous] ⚠️ Auto-programador no disponible, guardando idea.")
                self.stats["failed_ideas"] += 1
                self._failed_proposals[skill_name] = self._failed_proposals.get(skill_name, 0) + 1
                self._save_idea(propuesta, "idea")

            self.stats["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self._save_stats()

            # Limpiar fallos antiguos (más de 1 hora)
            now = time.time()
            for name, ts in list(self._failed_proposals.items()):
                if now - ts > 3600:
                    del self._failed_proposals[name]

        except Exception as e:
            log(f"[Autonomous] ❌ Error generando propuesta: {e}")

    def _save_idea(self, idea: str, name: str = "idea"):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = self.ideas_dir / f"{name}_{timestamp}.txt"
        content = f"IDEA: {idea}\n\nTimestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[AutoLearn] 💡 Idea guardada en: {filename}")
        except Exception as e:
            print(f"[AutoLearn] ⚠️ Error guardando idea: {e}")

    def get_stats(self) -> Dict:
        return self.stats.copy()