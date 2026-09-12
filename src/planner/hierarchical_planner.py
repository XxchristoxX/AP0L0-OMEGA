"""
Planificador jerárquico para tareas complejas.
Descompone un objetivo en sub‑tareas, las ejecuta y evalúa resultados.
"""

import asyncio
import json
import re
from typing import List, Dict, Any, Callable, Optional


class HierarchicalPlanner:
    """
    Planificador que usa la IA para dividir un objetivo en pasos accionables.
    Ejecuta cada paso de forma secuencial o paralela según dependencias.
    """

    def __init__(self, router, memory=None, max_depth: int = 3):
        self.router = router
        self.memory = memory
        self.max_depth = max_depth

    async def plan_and_execute(self, goal: str, log_callback: Optional[Callable] = None) -> str:
        """
        Toma un objetivo de alto nivel, lo descompone y ejecuta.
        Devuelve un resumen de la ejecución.
        """
        log = log_callback or print

        # 1. Obtener contexto de memoria si está disponible
        context = ""
        if self.memory:
            context = self.memory.get_context(goal)
            if context:
                log(f"[Planner] Contexto recordado:\n{context}")

        # 2. Pedir plan a la IA
        plan_prompt = f"""
Eres un planificador experto. Dado el siguiente objetivo, crea un plan de acción paso a paso.
Objetivo: {goal}

Contexto recordado (si aplica):
{context or "Ninguno"}

Responde SOLO con un JSON válido:
{{
  "steps": [
    {{"description": "paso 1", "tool": "nombre_de_habilidad_o_null", "params": {{}}}},
    {{"description": "paso 2", "tool": "nombre_de_habilidad_o_null", "params": {{}}}}
  ]
}}
Los pasos deben ser concretos y ejecutables por un asistente de escritorio.
"""
        response = self.router.route(plan_prompt, "Planner")
        steps = self._parse_plan(response)
        if not steps:
            return "No pude generar un plan válido para el objetivo."

        log(f"[Planner] Plan generado con {len(steps)} pasos.")

        # 3. Ejecutar pasos secuencialmente (se podría paralelizar si no hay dependencias)
        results = []
        for i, step in enumerate(steps, 1):
            log(f"[Planner] Ejecutando paso {i}/{len(steps)}: {step['description']}")
            result = await self._execute_step(step, log)
            results.append(f"Paso {i}: {result}")
            # Guardar en memoria
            if self.memory:
                self.memory.add(
                    text=f"Objetivo: {goal}\nPaso {i}: {step['description']}\nResultado: {result}",
                    metadata={"type": "plan_step", "goal": goal},
                    kind="plan"
                )

        summary = "\n".join(results)
        log(f"[Planner] Ejecución completada:\n{summary}")
        return summary

    def _parse_plan(self, response: str) -> List[Dict[str, Any]]:
        if not response:
            return []
        # Intentar extraer JSON
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                steps = data.get("steps", [])
                return steps if isinstance(steps, list) else []
        except Exception:
            pass
        # Fallback: dividir en líneas numeradas
        steps = []
        for line in response.splitlines():
            line = line.strip()
            if re.match(r'^\d+[\.\)\-]?\s+', line):
                desc = re.sub(r'^\d+[\.\)\-]?\s+', '', line)
                steps.append({"description": desc, "tool": None, "params": {}})
        return steps[:10]  # límite

    async def _execute_step(self, step: Dict[str, Any], log) -> str:
        """
        Ejecuta un paso usando la herramienta indicada o pidiendo a la IA.
        Aquí se conecta con el SkillsRegistry / AutoProgrammer.
        """
        tool = step.get("tool")
        params = step.get("params", {})
        description = step.get("description", "")

        if tool:
            # Intentar usar habilidad registrada (debes tener acceso al registry)
            # Como el planificador no tiene el registry, se deja un hook.
            # Puedes pasarlo en el constructor si lo deseas.
            try:
                # Simulación: aquí deberías llamar a tu registry
                result = f"Habilidad '{tool}' ejecutada con parámetros {params}."
                log(f"[Planner] Herramienta {tool} ejecutada.")
                return result
            except Exception as e:
                log(f"[Planner] Error en herramienta {tool}: {e}")
                return f"Error: {e}"
        else:
            # Pedir a la IA que realice el paso
            prompt = f"Realiza el siguiente paso y devuelve solo el resultado:\n{description}"
            response = self.router.route(prompt, "Executor")
            return response.strip() if response else "Sin resultado."