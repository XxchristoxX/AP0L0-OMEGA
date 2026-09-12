# src/core/auto_programmer_advanced.py - VERSIÓN MEJORADA
# AutoProgramación, Autocuración y Autoaprendizaje
import os
import re
import sys
import ast
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from src.core.hybrid_router import HybridRouter
from src.core.skills_registry import SkillsRegistry
from src.core.persistence import Persistence
from src.utils.naming import generate_skill_name

# Importación opcional de Gemini, solo se intenta una vez
try:
    from src.core.config import gemini_generate
except ImportError:
    gemini_generate = None

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = BASE_DIR / "src" / "skills"
ACTIONS_DIR = BASE_DIR / "src" / "actions"
SKILLS_DIR.mkdir(parents=True, exist_ok=True)
ACTIONS_DIR.mkdir(parents=True, exist_ok=True)


def _log(msg: str):
    print(f"[AutoProgrammer] {msg}")


class AutoProgrammer:
    """
    Programador autónomo que genera, prueba, sana y aprende habilidades/acciones.
    - Crea habilidades en src/skills
    - Crea acciones en src/actions
    - Intenta autocorregir errores de ejecución hasta un máximo de intentos.
    - Registra todos los intentos para aprendizaje continuo.
    """

    def __init__(
        self,
        router: HybridRouter,
        registry: SkillsRegistry,
        persistence: Optional[Persistence] = None,
        max_attempts: int = 4,
    ):
        self.router = router
        self.registry = registry
        self.persistence = persistence if persistence else Persistence()
        self.max_attempts = max_attempts
        _log(f"Inicializado. Directorios: skills={SKILLS_DIR}, actions={ACTIONS_DIR}")

    # ------------------------------------------------------------------
    # Validación y limpieza
    # ------------------------------------------------------------------
    def _validate_syntax(self, code: str) -> Tuple[bool, str]:
        """Valida la sintaxis del código usando ast.parse."""
        try:
            ast.parse(code)
            return True, "Sintaxis correcta."
        except SyntaxError as e:
            return False, f"Error de sintaxis en línea {e.lineno}: {e.msg}"

    def _clean_code(self, code: str) -> str:
        """Limpia bloques markdown y caracteres no deseados."""
        code = code.strip()

        # Extraer código de un bloque markdown si existe
        fenced = re.search(r"```(?:python)?\s*(.*?)```", code, re.DOTALL)
        if fenced:
            code = fenced.group(1).strip()
        else:
            # Quitar cercas individuales
            code = re.sub(r"^```(?:python)?\s*", "", code)
            code = re.sub(r"\s*```$", "", code)

        # Colapsar líneas vacías repetidas
        code = re.sub(r"\n\s*\n", "\n", code)
        return code.strip()

    def _ensure_run(self, code: str) -> str:
        """
        Garantiza que exista una función run(params).
        Si no existe, intenta separar imports y envolver el resto en run.
        """
        # Si ya tiene función run, devolver tal cual
        if re.search(r"^\s*def run\s*\(", code, re.MULTILINE):
            return code

        # Buscar cualquier otra función y renombrarla a run
        first_func = re.search(r"^\s*def ([A-Za-z_]\w*)\s*\(", code, re.MULTILINE)
        if first_func:
            old_name = first_func.group(1)
            if old_name != "run":
                code = re.sub(rf"\bdef {re.escape(old_name)}\b", "def run", code, count=1)
                code = re.sub(rf"\b{re.escape(old_name)}\b", "run", code)
                return code

        # No hay función: separar imports al inicio y envolver el resto
        lines = code.split("\n")
        import_lines = []
        body_lines = []

        # Detectar imports al comienzo (respetando líneas en blanco)
        idx = 0
        while idx < len(lines):
            stripped = lines[idx].strip()
            if not stripped:
                # Conservar líneas en blanco como parte del cuerpo o ignorarlas
                idx += 1
                continue
            if stripped.startswith("import ") or stripped.startswith("from "):
                import_lines.append(lines[idx])
                idx += 1
            else:
                break

        # El resto se convierte en cuerpo de la función
        body_lines = lines[idx:]

        # Si no hay cuerpo, devolver una función vacía
        if not body_lines:
            return "def run(params=None):\n    return None\n"

        # Crear función con imports fuera y cuerpo indentado
        final_code = ""
        if import_lines:
            final_code += "\n".join(import_lines) + "\n\n"
        final_code += "def run(params=None):\n"
        final_code += '    """Habilidad generada."""\n'
        for line in body_lines:
            if line.strip():
                final_code += "    " + line + "\n"
            else:
                final_code += "\n"
        return final_code

    # ------------------------------------------------------------------
    # Seguridad
    # ------------------------------------------------------------------
    def _is_safe_code(self, code: str) -> bool:
        """
        Análisis estático de seguridad mejorado.
        Bloquea llamadas peligrosas, no importaciones estándar.
        """
        # Análisis AST
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Llamadas directas peligrosas
                if isinstance(node.func, ast.Name):
                    if node.func.id in {"eval", "exec", "compile", "__import__"}:
                        return False
                # Llamadas a métodos peligrosos
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        dangerous_calls = {
                            "os": {"system", "popen", "remove", "rmdir", "unlink"},
                            "subprocess": {"call", "popen", "run", "check_output", "check_call"},
                            "shutil": {"rmtree", "move", "copy", "copy2", "copytree"},
                        }
                        if (
                            node.func.value.id in dangerous_calls
                            and node.func.attr in dangerous_calls[node.func.value.id]
                        ):
                            return False

        # Patrón de respaldo
        lower_code = code.lower()
        dangerous_patterns = [
            "os.system",
            "subprocess.call",
            "subprocess.popen",
            "eval(",
            "exec(",
            "shutil.rmtree",
            "os.remove",
            "os.rmdir",
            "import builtins",
            "from builtins import",
            "__import__",
        ]
        for pattern in dangerous_patterns:
            if pattern in lower_code:
                return False

        return True

    # ------------------------------------------------------------------
    # Ejecución en sandbox
    # ------------------------------------------------------------------
    def _test_code_sandboxed(self, code: str, timeout: int = 10) -> Tuple[bool, str, str]:
        """
        Ejecuta el código en un subproceso aislado.
        Retorna (éxito, salida, error).
        """
        # Validar sintaxis primero
        valid, error = self._validate_syntax(code)
        if not valid:
            return False, "", f"Error de sintaxis: {error}"

        test_code = code + "\n\nif __name__ == '__main__':\n    print(run({}))"
        fd, path = tempfile.mkstemp(suffix=".py", prefix="skill_test_")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(test_code)

            cmd = [sys.executable, path]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(Path(path).parent),
            )

            if result.returncode == 0:
                return True, result.stdout.strip() or "Ejecutado sin salida.", ""
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                return False, result.stdout.strip(), error_msg[:300]

        except subprocess.TimeoutExpired:
            return False, "", f"Timeout: excedió {timeout} segundos."
        except Exception as e:
            return False, "", f"Error en sandbox: {str(e)[:200]}"
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Detección de tipo de artefacto
    # ------------------------------------------------------------------
    def _detect_artifact_type(self, task_description: str, skill_name: str, action: str) -> str:
        """Determina si se debe generar una acción o una habilidad."""
        if action in ("action", "create_action", "generar_accion", "accion"):
            return "action"

        combined = f"{task_description} {skill_name}".lower()
        keywords = [
            "acción",
            "accion",
            " action",
            "action_",
            "generar acción",
            "crear acción",
        ]
        if any(kw in combined for kw in keywords):
            return "action"
        return "skill"

    def _get_artifact_dir(self, artifact_type: str) -> Path:
        """Retorna el directorio correspondiente al tipo de artefacto."""
        return ACTIONS_DIR if artifact_type == "action" else SKILLS_DIR

    # ------------------------------------------------------------------
    # Generación de código con IA
    # ------------------------------------------------------------------
    def _generate_code(
        self,
        task_description: str,
        action: str,
        skill_name: str,
        artifact_type: str,
        reference_code: str = "",
    ) -> Optional[str]:
        """
        Genera código usando Gemini si está disponible, y luego el router.
        El prompt se adapta según se esté creando o mejorando.
        """
        kind_label = "acción" if artifact_type == "action" else "habilidad"
        action_label = "mejorar" if action == "improve" else "crear"

        prompt = f"""Eres un programador experto en Python. Necesito {action_label} una {kind_label} llamada '{skill_name}'.
Tarea: {task_description}

REGLAS ESTRICTAS:
1. Responde ÚNICAMENTE con código Python válido, sin markdown, sin explicaciones.
2. El código DEBE tener una función `def run(params):` que acepte un diccionario y devuelva un resultado (string o dict).
3. Usa solo librerías estándar (os, sys, json, datetime, subprocess, requests, pathlib).
4. Maneja errores con try/except.
5. Asegúrate de que la indentación sea correcta (4 espacios).
6. No uses imports externos no permitidos.
7. El código debe ser autocontenido.
8. Si es una acción, la función run puede realizar múltiples pasos y devolver un resumen o resultado.

Ejemplo de código válido:
def run(params):
    try:
        nombre = params.get("nombre", "mundo")
        return f"Hola, {{nombre}}!"
    except Exception as e:
        return f"Error: {{e}}"

Código para '{skill_name}':"""

        if reference_code:
            prompt += f"""

Código previo que falló o que debe mejorarse:
```python
{reference_code}
Corrige los errores y devuelve solo el código Python funcional."""

        # Intentar primero con Gemini si está disponible
        if gemini_generate:
            try:
                response = gemini_generate(prompt, model="gemini-2.5-flash-lite")
                if response and len(response.strip()) > 20:
                    return self._clean_code(response)
            except Exception as e:
                _log(f"Gemini falló: {e}, usando router...")

        # Fallback al router multi-proveedor
        response = self.router.route(prompt, "AutoProgrammer")
        if response:
            return self._clean_code(response)
        return None

    # ------------------------------------------------------------------
    # Ciclo principal de generación, prueba y autocuración
    # ------------------------------------------------------------------
    def generate_and_test(
        self,
        task_description: str,
        skill_name: str = None,
        action: str = "create",
        artifact_type: str = None,
    ) -> str:
        """
        Genera, prueba y guarda una habilidad o acción.
        Incluye autocuración: reintenta corrigiendo errores automáticamente.
        """

        # Normalizar acción
        if action in ("create_action", "generar_accion", "action"):
            action = "create"
            artifact_type = "action"

        if not skill_name:
            skill_name = generate_skill_name(task_description)
            _log(f"Nombre generado automáticamente: {skill_name}")

        if artifact_type is None:
            artifact_type = self._detect_artifact_type(task_description, skill_name, action)

        artifact_dir = self._get_artifact_dir(artifact_type)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        kind_label = "acción" if artifact_type == "action" else "habilidad"

        _log(f"Generando {kind_label} '{skill_name}' en {artifact_dir} (acción={action})")

        # Verificar versiones existentes
        existing_versions = (
            sorted(
                [
                    int(p.stem[1:])
                    for p in artifact_dir.glob("v*.py")
                    if p.stem[1:].isdigit()
                ]
            )
            if artifact_dir.exists()
            else []
        )
        current_version = existing_versions[-1] if existing_versions else 0

        # Si se pide crear y ya existe una versión funcional, no duplicar
        if action == "create" and current_version > 0:
            latest_file = artifact_dir / f"v{current_version}.py"
            if latest_file.exists():
                code = latest_file.read_text(encoding="utf-8")
                ok, output, error = self._test_code_sandboxed(code)
                if ok:
                    return (
                        f"Ya sé hacer eso (la {kind_label} '{skill_name}' ya existe y funciona). "
                        "Si quieres mejorarla, dime exactamente qué debo añadir o corregir."
                    )
                else:
                    action = "improve"
                    task_description = (
                        f"La {kind_label} '{skill_name}' falla con: {error}. Mejórala."
                    )
                    _log(f"La {kind_label} existente falla. Cambiando a modo 'improve'.")

        # Si se pide mejorar pero no existe, informar
        if action == "improve" and current_version == 0:
            return (
                f"No encuentro la {kind_label} '{skill_name}' para mejorarla. "
                f"¿Quieres que la cree desde cero? Di 'crea la {kind_label} {skill_name}'."
            )

        best_code = None
        best_error = None
        best_output = None
        last_code = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                _log(f"Intento {attempt}/{self.max_attempts} generando código para '{skill_name}'...")

                reference = last_code if last_code else ""
                code = self._generate_code(
                    task_description,
                    action,
                    skill_name,
                    artifact_type,
                    reference_code=reference,
                )
                if not code:
                    _log(" -> No se recibió código (vacío).")
                    continue

                code = self._clean_code(code)
                code = self._ensure_run(code)
                _log(f" -> Código generado ({len(code)} caracteres)")

                if not self._is_safe_code(code):
                    best_error = "Código contiene imports o llamadas peligrosas."
                    _log(f" -> {best_error}")
                    continue

                ok, output, error = self._test_code_sandboxed(code)

                if ok:
                    new_version = current_version + 1 if action == "improve" else 1
                    version_file = artifact_dir / f"v{new_version}.py"
                    _log(f"Guardando en: {version_file}")
                    version_file.write_text(code, encoding="utf-8")
                    _log(f" -> ✅ {kind_label.capitalize()} guardada en {version_file}")

                    # Registrar en el sistema
                    self.registry.register_skill(skill_name, str(version_file))
                    self.persistence.register_skill(
                        name=skill_name,
                        description=task_description,
                        file_path=str(version_file),
                        version=new_version,
                    )
                    self.persistence.log_attempt(
                        skill_name=skill_name,
                        attempt=attempt,
                        code=code,
                        success=True,
                        output=output,
                        error="",
                    )

                    return (
                        f"{kind_label.capitalize()} '{skill_name}' "
                        f"{'mejorada' if action == 'improve' else 'creada'} "
                        f"correctamente (versión {new_version}). "
                        f"Salida: {output[:100]}{'...' if len(output) > 100 else ''}"
                    )

                # Guardar el mejor intento fallido
                if best_code is None or (error and len(error) < len(best_error or "")):
                    best_code = code
                    best_error = error
                    best_output = output

                self.persistence.log_attempt(
                    skill_name=skill_name,
                    attempt=attempt,
                    code=code,
                    success=False,
                    output=output,
                    error=error,
                )
                _log(f" -> ❌ Falló: {error[:80]}...")

                # Preparar siguiente intento con contexto del error
                last_code = code
                task_description = (
                    f"El código anterior falló con: {error}\n"
                    f"Tarea original: {task_description}\n"
                    "Corrige y devuelve solo código Python funcional."
                )

            except Exception as e:
                best_error = str(e)
                _log(f" -> ❌ Excepción en intento {attempt}: {e}")
                break

        # -------------------------------------------------------------------
        # Manejo final si no se logró un código funcional
        # -------------------------------------------------------------------
        if best_code:
            if action == "create":
                # Guardar el mejor intento como versión fallida, para futura autocuración
                new_version = current_version + 1
                version_file = artifact_dir / f"v{new_version}.py"
                version_file.write_text(best_code, encoding="utf-8")
                self.registry.register_skill(skill_name, str(version_file))
                self.persistence.register_skill(
                    name=skill_name,
                    description=task_description,
                    file_path=str(version_file),
                    version=new_version,
                )
                try:
                    self.persistence.update_skill_status(skill_name, "failed", best_error)
                except AttributeError:
                    pass

                _log(f" -> ⚠️ Guardado como fallido en {version_file}")
                return (
                    f"No se pudo generar una {kind_label} 100% funcional. "
                    f"Se guardó el mejor intento (error: {best_error[:100]})."
                )
            else:
                # Si estamos mejorando, no sobrescribir la versión funcional anterior
                failed_file = artifact_dir / f"v{current_version + 1}.failed.py"
                failed_file.write_text(best_code, encoding="utf-8")
                _log(f" -> ⚠️ Intento fallido guardado en {failed_file}")
                return (
                    f"No se pudo mejorar la {kind_label} '{skill_name}'. "
                    f"Se guardó el intento fallido en {failed_file}. "
                    f"La versión {current_version} sigue activa."
                )

        return (
            f"No se pudo generar código válido. "
            f"Último error: {best_error[:200] if best_error else 'desconocido'}"
        )