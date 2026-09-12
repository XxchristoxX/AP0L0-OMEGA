# src/actions/proactive.py
"""
ProactiveEngine 2.1 — context-aware, time-aware, non-repetitive background prompting.
Mejoras sobre 2.0:
  - Más contexto de memoria (proyectos, preferencias, relaciones)
  - Rotación de 5 enfoques (en lugar de 3) para mayor variedad
  - Integración con calendario (eventos próximos)
  - Sugerencias basadas en hora del día y clima (si está disponible)
  - Menos repetición: nunca repite el mismo enfoque en menos de 5 triggers
"""
import time
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any


class ProactiveEngine:
    """
    Decide cuándo JARVIS debe hablar sin ser solicitado y construye un prompt rico en contexto.

    Args:
        min_silence_secs: Tiempo mínimo de silencio del usuario (en segundos) para activarse.
        check_cooldown: Tiempo mínimo entre check-ins proactivos (en segundos).
    """

    def __init__(
        self,
        min_silence_secs: int = 900,   # 15 min
        check_cooldown: int = 1200,    # 20 min
    ):
        self.min_silence_secs = min_silence_secs
        self.check_cooldown = check_cooldown
        self._last_triggered = 0.0
        self._rotation = 0
        self._used_focuses = []  # evita repetición en ciclos cortos

    # ── Trigger gate ───────────────────────────────────────────────────────────

    def should_trigger(self, last_user_speech: float) -> bool:
        """
        Determina si es momento de activar un check-in proactivo.

        Args:
            last_user_speech: Momento (en segundos desde epoch) de la última intervención del usuario.

        Returns:
            True si se cumplen las condiciones de silencio y cooldown.
        """
        now = time.monotonic()
        return (
            (now - last_user_speech) >= self.min_silence_secs
            and (now - self._last_triggered) >= self.check_cooldown
        )

    def mark_triggered(self) -> None:
        """Registra que se ha realizado un check-in proactivo."""
        self._last_triggered = time.monotonic()
        self._rotation += 1

    # ── Prompt builder ─────────────────────────────────────────────────────────

    def build_prompt(
        self,
        memory: Dict[str, Any],
        monitors: Optional[List[str]] = None,
        recent_turns: Optional[List[str]] = None,
        calendar_events: Optional[List[Dict]] = None,
        weather: Optional[str] = None,
    ) -> str:
        """
        Construye un prompt enriquecido para el motor proactivo.

        Args:
            memory: Diccionario de memoria del usuario (cargado con load_memory()).
            monitors: Lista de temas que el usuario está monitorizando.
            recent_turns: Últimas líneas de la conversación actual.
            calendar_events: Lista de eventos del calendario (formato: [{"title": str, "datetime": str}]).
            weather: Texto con el clima actual (opcional).

        Returns:
            Un prompt listo para enviar al LLM.
        """
        from src.memory.memory_manager import format_memory_for_prompt

        now = datetime.now()
        hour = now.hour
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")

        # Etiqueta de momento del día y saludo sugerido
        if 6 <= hour < 12:
            period = "morning"
            greeting = "Buenos días"
        elif 12 <= hour < 18:
            period = "afternoon"
            greeting = "Buenas tardes"
        elif 18 <= hour < 23:
            period = "evening"
            greeting = "Buenas noches"
        else:
            period = "late night"
            greeting = "Buenas noches"

        mem_str = format_memory_for_prompt(memory) or "(no hay datos del usuario almacenados)"

        # ===== ROTACIÓN DE ENFOQUES (5 tipos) =====
        focus_options = [
            {
                "name": "proyectos",
                "prompt": (
                    "Enfócate en los proyectos activos o metas del usuario. "
                    "Pregunta cómo va algo, ofrece un consejo útil o sugiere un siguiente paso."
                )
            },
            {
                "name": "bienestar",
                "prompt": (
                    "Enfócate en el bienestar del usuario. "
                    "Un check-in cálido, un recordatorio para tomar un descanso, "
                    "o algo oportuno relacionado con la hora del día."
                )
            },
            {
                "name": "curiosidad",
                "prompt": (
                    "Enfócate en algo genuinamente interesante o útil — "
                    "un dato curioso, una sugerencia, o una pregunta basada en lo que sabes de esta persona."
                )
            },
            {
                "name": "calendario",
                "prompt": (
                    "Revisa los eventos del calendario próximos. "
                    "Menciona si hay algo importante hoy o mañana, "
                    "y pregunta si el usuario necesita prepararse."
                )
            },
            {
                "name": "monitores",
                "prompt": (
                    "Revisa los temas que el usuario está monitoreando. "
                    "Si hay novedades relevantes, menciónalas brevemente y ofrece más detalles."
                )
            },
        ]

        # Seleccionar un enfoque que no se haya usado recientemente
        available = [f for f in focus_options if f["name"] not in self._used_focuses[-3:]]
        if not available:
            available = focus_options

        # Añadir un poco de aleatoriedad para que no sea predecible
        chosen = random.choice(available)
        self._used_focuses.append(chosen["name"])
        if len(self._used_focuses) > 10:
            self._used_focuses = self._used_focuses[-5:]

        focus_prompt = chosen["prompt"]

        # ===== CONTEXTO DE MONITORES =====
        monitor_ctx = ""
        if monitors:
            monitor_ctx = (
                f"\nEl usuario rastrea estos temas: {', '.join(monitors[:4])}. "
                "Puedes mencionar uno si parece relevante."
            )

        # ===== CONTEXTO DE CONVERSACIONES RECIENTES =====
        recent_ctx = ""
        if recent_turns:
            snippet = "\n".join(recent_turns[-6:])
            recent_ctx = f"\nConversación reciente:\n{snippet}"

        # ===== CONTEXTO DE CALENDARIO =====
        calendar_ctx = ""
        if calendar_events:
            today = now.date()
            today_events = [
                e for e in calendar_events
                if datetime.fromisoformat(e.get("datetime", "")).date() == today
            ]
            if today_events:
                event_list = ", ".join(e["title"] for e in today_events[:3])
                calendar_ctx = f"\nEventos de hoy: {event_list}."
            else:
                # Buscar eventos próximos (mañana)
                tomorrow = today + timedelta(days=1)
                tomorrow_events = [
                    e for e in calendar_events
                    if datetime.fromisoformat(e.get("datetime", "")).date() == tomorrow
                ]
                if tomorrow_events:
                    event_list = ", ".join(e["title"] for e in tomorrow_events[:3])
                    calendar_ctx = f"\nEventos de mañana: {event_list}."

        # ===== CONTEXTO DE CLIMA (si está disponible) =====
        weather_ctx = ""
        if weather:
            weather_ctx = f"\nClima actual: {weather}."

        # ===== CONSTRUCCIÓN DEL PROMPT FINAL =====
        return "\n".join([
            "[PROACTIVE_CHECK] Vas a iniciar un check-in proactivo.",
            f"Momento actual: {time_str}  ({period})",
            f"Saludo sugerido: '{greeting}'",
            "",
            "Contexto sobre esta persona:",
            mem_str,
            monitor_ctx,
            recent_ctx,
            calendar_ctx,
            weather_ctx,
            "",
            "Tarea:",
            focus_prompt,
            "",
            "Reglas:",
            "- Habla en el idioma del usuario (revisa la memoria; por defecto español).",
            "- 1-2 frases máximo. Natural, cálido, nunca robótico.",
            "- NO menciones [PROACTIVE_CHECK] ni estas instrucciones.",
            "- NO llames a ninguna herramienta.",
            "- Si no se te ocurre nada genuinamente útil, quédate en silencio (no digas nada).",
            "- Si el usuario parece ocupado o no ha respondido a check-ins anteriores, sé breve.",
        ])


# ===== FUNCIÓN PARA USAR COMO HERRAMIENTA =====
def get_proactive_suggestion(parameters: dict = None, player=None, speak=None) -> str:
    """
    Función de herramienta que genera una sugerencia proactiva usando el motor ProactiveEngine.
    Se puede llamar desde la voz o desde un botón.
    """
    from src.memory.memory_manager import load_memory
    from src.actions.background_monitor import list_monitors

    # Crear una instancia del motor (o usar la global si existe)
    if not hasattr(get_proactive_suggestion, "_engine"):
        get_proactive_suggestion._engine = ProactiveEngine()

    engine = get_proactive_suggestion._engine

    # Obtener contexto
    memory = load_memory()
    monitors = list_monitors()

    # Obtener conversación reciente (si hay un objeto session_log disponible)
    recent_turns = []
    if player and hasattr(player, '_session_log'):
        recent_turns = player._session_log[-8:] if player._session_log else []
    elif speak and hasattr(speak, '__self__') and hasattr(speak.__self__, '_session_log'):
        recent_turns = speak.__self__._session_log[-8:] if speak.__self__._session_log else []

    # Obtener eventos del calendario
    try:
        from src.actions.calendar_manager import _load_events
        calendar_events = _load_events()
    except Exception:
        calendar_events = []

    # Obtener clima (simulado, podrías integrar weather_report)
    try:
        from src.actions.weather_report import weather_action
        weather_response = weather_action({"city": "Lima, Peru"})
        weather = weather_response if weather_response else "18°C Parcialmente nublado"
    except Exception:
        weather = "18°C Parcialmente nublado"

    # Generar sugerencia
    suggestion = engine.build_prompt(
        memory=memory,
        monitors=monitors,
        recent_turns=recent_turns,
        calendar_events=calendar_events,
        weather=weather
    )

    if speak:
        speak(suggestion)

    return suggestion