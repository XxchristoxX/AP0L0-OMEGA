# agent/executor.py
import json
import re
import sys
import time
import threading
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Callable

from src.core.config import gemini_generate, LITE_MODEL
from src.core.logging import get_logger

log = get_logger("jarvis.executor")

from src.agent.planner       import create_plan, replan
from src.agent.error_handler import analyze_error, generate_fix, ErrorDecision

# ------------------------------------------------------------
# Función para ejecutar código generado (fallback)
# ------------------------------------------------------------
def _run_generated_code(description: str, speak: Callable | None = None) -> str:
    home      = Path.home()
    desktop   = home / "Desktop"
    downloads = home / "Downloads"
    documents = home / "Documents"

    if not desktop.exists():
        try:
            import winreg
            key     = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
            desktop = Path(winreg.QueryValueEx(key, "Desktop")[0])
        except Exception:
            pass

    system_instruction = (
        "You are an expert Python developer. "
        "Write clean, complete, working Python code. "
        "Use standard library + common packages. "
        "Install missing packages with subprocess + pip if needed. "
        "Return ONLY the Python code. No explanation, no markdown, no backticks.\n\n"
        f"SYSTEM PATHS:\n"
        f"  Desktop   = r'{desktop}'\n"
        f"  Downloads = r'{downloads}'\n"
        f"  Documents = r'{documents}'\n"
        f"  Home      = r'{home}'\n"
    )

    try:
        code = gemini_generate(
            f"Write Python code to accomplish this task:\n\n{description}",
            system_instruction=system_instruction,
            model=LITE_MODEL
        )
        code = re.sub(r"```(?:python)?", "", code).strip().rstrip("`").strip()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        print(f"[Executor] 🐍 Running generated code: {tmp_path}")

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True,
            timeout=120, cwd=str(Path.home())
        )

        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        output = result.stdout.strip()
        error  = result.stderr.strip()

        if result.returncode == 0 and output:
            return output
        elif result.returncode == 0:
            return "Task completed successfully."
        elif error:
            raise RuntimeError(f"Code error: {error[:400]}")
        return "Completed."

    except subprocess.TimeoutExpired:
        raise RuntimeError("Generated code timed out after 120 seconds.")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Generated code failed: {e}")

# ------------------------------------------------------------
# Inyección de contexto y traducción
# ------------------------------------------------------------
def _inject_context(params: dict, tool: str, step_results: dict, goal: str = "") -> dict:
    if not step_results:
        return params

    params = dict(params)

    if tool == "file_controller" and params.get("action") in ("write", "create_file"):
        content = params.get("content", "")
        if not content or len(content) < 50:
            all_results = [
                v for v in step_results.values()
                if v and len(v) > 100 and v not in ("Done.", "Completed.")
            ]
            if all_results:
                combined = "\n\n---\n\n".join(all_results)
                translated = _translate_to_goal_language(combined, goal)
                params["content"] = translated
                print(f"[Executor] 💉 Injected + translated content")

    return params

def _detect_language(text: str) -> str:
    try:
        return gemini_generate(
            f"What language is this text written in? "
            f"Reply with ONLY the language name in English (e.g. Turkish, English, French).\n\n"
            f"Text: {text[:200]}",
            model=LITE_MODEL,
        )
    except Exception:
        return "English"

def _translate_to_goal_language(content: str, goal: str) -> str:
    if not goal:
        return content
    try:
        target_lang = _detect_language(goal)
        print(f"[Executor] 🌐 Translating to: {target_lang}")

        prompt = (
            f"You are a professional translator. "
            f"Translate the following text into {target_lang}.\n"
            f"IMPORTANT:\n"
            f"- Translate EVERYTHING, leave nothing in English\n"
            f"- Keep all facts, numbers, and data intact\n"
            f"- Keep the structure and formatting\n"
            f"- Output ONLY the translated text, nothing else\n\n"
            f"Text to translate:\n{content[:4000]}"
        )
        translated = gemini_generate(prompt, model=LITE_MODEL).strip()
        print(f"[Executor] ✅ Translation done ({target_lang})")
        return translated
    except Exception as e:
        print(f"[Executor] ⚠️ Translation failed: {e}")
        return content

# ------------------------------------------------------------
# Registro de herramientas
# ------------------------------------------------------------
_TOOL_HANDLERS: dict = {}

def _register(tool_name: str):
    def decorator(func):
        _TOOL_HANDLERS[tool_name] = func
        return func
    return decorator

def _call_tool(tool: str, parameters: dict, speak: Callable | None) -> str:
    handler = _TOOL_HANDLERS.get(tool)
    if handler:
        return handler(parameters, speak)
    log.warning("Unknown tool '%s' — falling back to generated_code", tool)
    return _run_generated_code(f"Accomplish this task: {parameters}", speak=speak)

# ------------------------------------------------------------
# Handlers para cada herramienta (importaciones seguras)
# ------------------------------------------------------------
try:
    from src.actions.open_app import open_app
    @_register("open_app")
    def _tool_open_app(params, speak):
        return open_app(parameters=params, player=None) or "Done."
except Exception:
    pass

try:
    from src.actions.web_search import web_search
    @_register("web_search")
    def _tool_web_search(params, speak):
        return web_search(parameters=params, player=None) or "Done."
except Exception:
    pass

try:
    from src.actions.game_updater import game_updater
    @_register("game_updater")
    def _tool_game_updater(params, speak):
        return game_updater(parameters=params, player=None, speak=speak) or "Done."
except Exception:
    pass

try:
    from src.actions.browser_control import browser_control
    @_register("browser_control")
    def _tool_browser_control(params, speak):
        return browser_control(parameters=params, player=None) or "Done."
except Exception:
    pass

try:
    from src.actions.file_controller import file_controller
    @_register("file_controller")
    def _tool_file_controller(params, speak):
        return file_controller(parameters=params, player=None) or "Done."
except Exception:
    pass

try:
    from src.actions.code_helper import code_helper
    @_register("code_helper")
    def _tool_code_helper(params, speak):
        return code_helper(parameters=params, player=None, speak=speak) or "Done."
except Exception:
    pass

try:
    from src.actions.dev_agent import dev_agent
    @_register("dev_agent")
    def _tool_dev_agent(params, speak):
        return dev_agent(parameters=params, player=None, speak=speak) or "Done."
except Exception:
    pass

try:
    from src.actions.screen_processor import _capture_screen, _capture_camera
    @_register("screen_process")
    def _tool_screen_process(params, speak):
        angle = params.get("angle", "screen")
        if angle == "camera":
            img_b, mime = _capture_camera()
        else:
            img_b, mime = _capture_screen()
        # Aquí se podría procesar la imagen con IA, pero devolvemos un placeholder
        return "Screen captured and analyzed."
except Exception:
    pass

try:
    from src.actions.send_message import send_message
    @_register("send_message")
    def _tool_send_message(params, speak):
        return send_message(parameters=params, player=None) or "Done."
except Exception:
    pass

try:
    from src.actions.reminder import reminder
    @_register("reminder")
    def _tool_reminder(params, speak):
        return reminder(parameters=params, player=None) or "Done."
except Exception:
    pass

try:
    from src.actions.youtube_video import youtube_video
    @_register("youtube_video")
    def _tool_youtube_video(params, speak):
        return youtube_video(parameters=params, player=None) or "Done."
except Exception:
    pass

try:
    from src.actions.weather_report import weather_action
    @_register("weather_report")
    def _tool_weather_report(params, speak):
        return weather_action(parameters=params, player=None) or "Done."
except Exception:
    pass

try:
    from src.actions.computer_settings import computer_settings
    @_register("computer_settings")
    def _tool_computer_settings(params, speak):
        return computer_settings(parameters=params, player=None) or "Done."
except Exception:
    pass

try:
    from src.actions.desktop import desktop_control
    @_register("desktop_control")
    def _tool_desktop_control(params, speak):
        return desktop_control(parameters=params, player=None) or "Done."
except Exception:
    pass

try:
    from src.actions.computer_control import computer_control
    @_register("computer_control")
    def _tool_computer_control(params, speak):
        return computer_control(parameters=params, player=None) or "Done."
except Exception:
    pass

try:
    from src.actions.flight_finder import flight_finder
    @_register("flight_finder")
    def _tool_flight_finder(params, speak):
        return flight_finder(parameters=params, player=None, speak=speak) or "Done."
except Exception:
    pass

# Handler para generated_code (siempre disponible)
@_register("generated_code")
def _tool_generated_code(params, speak):
    description = params.get("description", "")
    if not description:
        raise ValueError("generated_code requires a 'description' parameter.")
    return _run_generated_code(description, speak=speak)

# ------------------------------------------------------------
# Clase AgentExecutor
# ------------------------------------------------------------
class AgentExecutor:
    MAX_REPLAN_ATTEMPTS = 2

    def execute(
        self,
        goal:        str,
        speak:       Callable | None        = None,
        cancel_flag: threading.Event | None = None,
    ) -> str:
        print(f"\n[Executor] 🎯 Goal: {goal}")

        replan_attempts = 0
        completed_steps = []
        step_results    = {}
        plan            = create_plan(goal)

        while True:
            steps = plan.get("steps", [])

            if not steps:
                return "I couldn't create a valid plan for this task, sir."

            success      = True
            failed_step  = None
            failed_error = ""

            for step in steps:
                if cancel_flag and cancel_flag.is_set():
                    return "Task cancelled."

                step_num = step.get("step", "?")
                tool     = step.get("tool", "generated_code")
                desc     = step.get("description", "")
                params   = step.get("parameters", {})

                params = _inject_context(params, tool, step_results, goal=goal)

                print(f"\n[Executor] ▶️ Step {step_num}: [{tool}] {desc}")

                attempt = 1
                step_ok = False

                while attempt <= 3:
                    if cancel_flag and cancel_flag.is_set():
                        break
                    try:
                        result = _call_tool(tool, params, speak)
                        step_results[step_num] = result
                        completed_steps.append(step)
                        print(f"[Executor] ✅ Step {step_num} done: {str(result)[:100]}")
                        step_ok = True
                        break

                    except Exception as e:
                        error_msg = str(e)
                        print(f"[Executor] ❌ Step {step_num} attempt {attempt} failed: {error_msg}")

                        recovery = analyze_error(step, error_msg, attempt=attempt)
                        decision = recovery["decision"]
                        user_msg = recovery.get("user_message", "")

                        if speak and user_msg:
                            speak(user_msg)

                        if decision == ErrorDecision.RETRY:
                            attempt += 1
                            time.sleep(2)
                            continue

                        elif decision == ErrorDecision.SKIP:
                            print(f"[Executor] ⏭️ Skipping step {step_num}")
                            completed_steps.append(step)
                            step_ok = True
                            break

                        elif decision == ErrorDecision.ABORT:
                            return f"Task aborted, sir. {recovery.get('reason', '')}"

                        else:  # REPLAN
                            fix_suggestion = recovery.get("fix_suggestion", "")
                            if fix_suggestion and tool != "generated_code":
                                try:
                                    fixed_step = generate_fix(step, error_msg, fix_suggestion)
                                    res = _call_tool(
                                        fixed_step["tool"],
                                        fixed_step["parameters"],
                                        speak
                                    )
                                    step_results[step_num] = res
                                    completed_steps.append(step)
                                    step_ok = True
                                    break
                                except Exception as fix_err:
                                    print(f"[Executor] ⚠️ Fix failed: {fix_err}")

                            failed_step  = step
                            failed_error = error_msg
                            success      = False
                            break

                if not step_ok and not failed_step:
                    failed_step  = step
                    failed_error = "Max retries exceeded"
                    success      = False

                if not success:
                    break

            if success:
                return self._summarize(goal, completed_steps, speak)

            if replan_attempts >= self.MAX_REPLAN_ATTEMPTS:
                return f"Task failed after {replan_attempts} replan attempts, sir."

            replan_attempts += 1
            plan = replan(goal, completed_steps, failed_step, failed_error)

    def _summarize(self, goal: str, completed_steps: list, speak: Callable | None) -> str:
        fallback = f"All done, sir. Completed {len(completed_steps)} steps for: {goal[:60]}."
        try:
            steps_str = "\n".join(f"- {s.get('description', '')}" for s in completed_steps)
            prompt    = (
                f'User goal: "{goal}"\n'
                f"Completed steps:\n{steps_str}\n\n"
                "Write a single natural sentence summarizing what was accomplished. "
                "Address the user as 'sir'. Be direct and positive."
            )
            summary = gemini_generate(prompt, model=LITE_MODEL).strip()
            return summary
        except Exception:
            return fallback