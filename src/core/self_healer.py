# src/core/self_healer.py
import threading
import time
import importlib   # ← AÑADIDO
import sys
from typing import Optional, Callable

class SelfHealer:
    """
    Módulo de autocuración que monitorea y repara componentes críticos.
    No depende de un orquestador global; recibe funciones de diagnóstico y reparación.
    """
    def __init__(self, log_callback: Optional[Callable] = None):
        self.monitoring = False
        self.monitor_thread = None
        self.last_health_report = {}
        self.log = log_callback or print
        self._repair_handlers = {}
        self._check_handlers = {}
        # Para llevar la cuenta de errores por skill
        self.skill_errors = {}

    def register_check(self, name: str, check_fn: Callable[[], bool], repair_fn: Optional[Callable] = None):
        """Registra una comprobación de salud y su función de reparación."""
        self._check_handlers[name] = check_fn
        if repair_fn:
            self._repair_handlers[name] = repair_fn

    def start_monitoring(self, interval: int = 30):
        """Inicia el monitoreo periódico en un hilo separado."""
        if self.monitoring:
            return
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,), daemon=True)
        self.monitor_thread.start()
        self.log("[SelfHealer] Monitor de salud activo.")

    def _monitor_loop(self, interval: int):
        while self.monitoring:
            self.check_health()
            time.sleep(interval)

    def check_health(self) -> dict:
        """Ejecuta todas las comprobaciones registradas y retorna el estado."""
        report = {}
        for name, check_fn in self._check_handlers.items():
            try:
                ok = check_fn()
                report[name] = "OK" if ok else "ERROR"
                if not ok and name in self._repair_handlers:
                    self.log(f"[SelfHealer] Reparando {name}...")
                    self._repair_handlers[name]()
            except Exception as e:
                report[name] = f"ERROR: {e}"
                if name in self._repair_handlers:
                    try:
                        self._repair_handlers[name]()
                    except Exception as rep:
                        self.log(f"[SelfHealer] Falló reparación de {name}: {rep}")
        self.last_health_report = report
        return report

    def run_full_diagnostic(self):
        """Ejecuta un diagnóstico completo y repara todo lo posible."""
        self.log("[SelfHealer] Diagnóstico completo iniciado...")
        self.check_health()
        self.log("[SelfHealer] Diagnóstico completado.")

    def stop(self):
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)

    def record_skill_error(self, skill_name, error):
        """Registra un error de un skill y lo recarga si se supera el umbral."""
        self.skill_errors[skill_name] = self.skill_errors.get(skill_name, 0) + 1
        if self.skill_errors[skill_name] >= 3:
            self.log(f"[SelfHealer] Recargando skill {skill_name} por errores acumulados...")
            self._reload_skill(skill_name)
            self.skill_errors[skill_name] = 0

    def _reload_skill(self, skill_name):
        """Recarga un módulo de skill de forma segura."""
        try:
            module_name = f"src.skills.{skill_name}"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
                self.log(f"[SelfHealer] Skill {skill_name} recargado.")
            else:
                # Si no estaba cargado, lo importamos normalmente
                __import__(module_name, fromlist=[''])
                self.log(f"[SelfHealer] Skill {skill_name} importado por primera vez.")
        except Exception as e:
            self.log(f"[SelfHealer] Error recargando {skill_name}: {e}")