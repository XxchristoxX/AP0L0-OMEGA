# src/agent/multi_agent.py
"""
Módulo de agentes multi‑tarea.
Ejecuta múltiples objetivos en paralelo usando AgentExecutor.
"""

import asyncio
import threading
from typing import List, Dict, Any, Callable, Optional

from src.agent.executor import AgentExecutor


class MultiAgentOrchestrator:
    """
    Orquesta la ejecución paralela de múltiples agentes.
    """

    def __init__(self, max_concurrent: int = 4):
        self.max_concurrent = max_concurrent
        self._executor = AgentExecutor()
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def run_tasks(
        self,
        tasks: List[Dict[str, Any]],
        speak: Optional[Callable] = None,
        log_callback: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """
        Ejecuta una lista de tareas en paralelo.
        Cada tarea es un dict con 'goal' (obligatorio) y opcionalmente 'priority' o 'context'.
        Retorna una lista de resultados con el mismo orden.
        """
        if not tasks:
            return []

        async def _run_one(task: Dict[str, Any], index: int) -> Dict[str, Any]:
            goal = task.get("goal", "")
            if not goal:
                return {"index": index, "goal": "", "result": "Goal vacío", "error": True}

            async with self._semaphore:
                if log_callback:
                    log_callback(f"[MultiAgent] Ejecutando tarea {index+1}: {goal[:60]}...")
                # Ejecutar el agente en un hilo separado para no bloquear el event loop
                result = await asyncio.to_thread(
                    self._executor.execute,
                    goal=goal,
                    speak=speak,
                    cancel_flag=None,
                )
                return {"index": index, "goal": goal, "result": result, "error": False}

        # Lanzar todas las tareas en paralelo
        coros = [_run_one(task, i) for i, task in enumerate(tasks)]
        resultados = await asyncio.gather(*coros, return_exceptions=True)

        # Procesar resultados
        output = []
        for res in resultados:
            if isinstance(res, Exception):
                output.append({"index": len(output), "goal": "", "result": str(res), "error": True})
            else:
                output.append(res)

        # Ordenar por índice original
        output.sort(key=lambda x: x["index"])
        return output


# ===== Función herramienta para usar desde el asistente =====
def multi_agent_tool(
    parameters: Dict[str, Any],
    player=None,
    speak: Optional[Callable] = None,
) -> str:
    """
    Punto de entrada para la herramienta 'run_multi_agent'.
    """
    tasks = parameters.get("tasks", [])
    if not tasks or not isinstance(tasks, list):
        return "Debes proporcionar una lista de tareas (tasks)."

    # Validar que cada tarea tenga 'goal'
    for i, t in enumerate(tasks):
        if not isinstance(t, dict) or "goal" not in t:
            return f"La tarea {i+1} no tiene un campo 'goal'."

    # Crear orquestador y ejecutar
    orchestrator = MultiAgentOrchestrator()
    try:
        # Ejecutar de forma síncrona (desde un hilo no asíncrono)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        resultados = loop.run_until_complete(
            orchestrator.run_tasks(tasks, speak=speak, log_callback=player.write_log if player else None)
        )
        loop.close()
    except Exception as e:
        return f"Error ejecutando agentes: {e}"

    # Formatear resultado
    lines = [f"✅ {len(resultados)} tarea(s) ejecutada(s):"]
    for r in resultados:
        status = "❌" if r.get("error") else "✅"
        goal = r.get("goal", "Sin meta")
        result = r.get("result", "Sin resultado")
        lines.append(f"{status} {goal[:60]} → {result[:100]}{'...' if len(result) > 100 else ''}")
    return "\n".join(lines)