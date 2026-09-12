# src/skills/auto_programmer_advanced.py

"""
AutoProgrammer Avanzado - Fábrica Universal de Herramientas + Ciberseguridad

Genera código para:
- Automatización del sistema (archivos, procesos, ventanas)
- Mensajería (WhatsApp, Telegram, Facebook, correo)
- Dictado por voz y síntesis de voz
- Notificaciones del sistema
- Control de llamadas (VoIP / Twilio)
- Web scraping, navegación y automatización de navegadores
- Multimedia (música, vídeo, capturas de pantalla)
- Ciberseguridad y hacking ético
  (detección de vulnerabilidades, escaneo de puertos,
   análisis de red, etc.)
- Cualquier tarea útil para un asistente autónomo 100%
"""

import os
import sys
import re
import ast
import json
import subprocess
import tempfile
import time
import traceback
import shutil

from pathlib import Path
from typing import Optional, Tuple, Dict, Any


# =============================================================================
# CONFIGURACIÓN DE RUTAS
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SKILLS_DIR = BASE_DIR / "src" / "skills"
ACTIONS_DIR = BASE_DIR / "src" / "actions"

SKILLS_DIR.mkdir(parents=True, exist_ok=True)
ACTIONS_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# LOGGER SIMPLE
# =============================================================================

def _log(msg: str, level: str = "INFO"):
    print(f"[AutoProgrammer] {level}: {msg}")


# =============================================================================
# IMPORTS DE DEPENDENCIAS
# =============================================================================

try:
    from src.core.hybrid_router import HybridRouter
    from src.core.skills_registry import SkillsRegistry
    from src.core.persistence import Persistence
    from src.utils.naming import generate_skill_name

except ImportError as e:
    _log(
        f"No se pudieron importar módulos del core: {e}",
        "ERROR",
    )

    class HybridRouter:
        pass

    class SkillsRegistry:
        pass

    class Persistence:
        pass

    def generate_skill_name(desc):
        return "skill_auto"


# =============================================================================
# CLASE AUTOPROGRAMMER
# =============================================================================

class AutoProgrammer:
    """
    Programador autónomo universal + ciberseguridad.

    Genera habilidades para cualquier tarea de automatización del sistema,
    mensajería, voz, notificaciones, llamadas, web, multimedia y seguridad.
    """

    # =========================================================================
    # INICIALIZACIÓN
    # =========================================================================

    def __init__(
        self,
        router: Optional[HybridRouter] = None,
        registry: Optional[SkillsRegistry] = None,
        persistence: Optional[Persistence] = None,
        max_attempts: int = 4,
    ):
        self.router = router or HybridRouter()
        self.registry = registry or SkillsRegistry()
        self.persistence = persistence or Persistence()
        self.max_attempts = max_attempts

        _log(
            f"Inicializado. "
            f"Skills dir: {SKILLS_DIR}, "
            f"Actions dir: {ACTIONS_DIR}"
        )

    # =========================================================================
    # VALIDACIÓN Y LIMPIEZA DE CÓDIGO
    # =========================================================================

    def _validate_syntax(
        self,
        code: str,
    ) -> Tuple[bool, str]:

        try:
            ast.parse(code)
            return True, "Sintaxis correcta."

        except SyntaxError as e:
            return (
                False,
                f"Error de sintaxis en línea {e.lineno}: {e.msg}",
            )

    def _clean_code(
        self,
        code: str,
    ) -> str:

        code = code.strip()

        fenced = re.search(
            r"```(?:python)?\s*(.*?)```",
            code,
            re.DOTALL,
        )

        if fenced:
            code = fenced.group(1).strip()

        else:
            code = re.sub(
                r"^```(?:python)?\s*",
                "",
                code,
            )

            code = re.sub(
                r"\s*```$",
                "",
                code,
            )

        code = re.sub(
            r"\n\s*\n",
            "\n",
            code,
        )

        return code.strip()

    def _ensure_run(
        self,
        code: str,
    ) -> str:

        if re.search(
            r"^\s*def run\s*\(",
            code,
            re.MULTILINE,
        ):
            return code

        first_func = re.search(
            r"^\s*def ([A-Za-z_]\w*)\s*\(",
            code,
            re.MULTILINE,
        )

        if first_func:

            old_name = first_func.group(1)

            if old_name != "run":

                code = re.sub(
                    rf"\bdef {re.escape(old_name)}\b",
                    "def run",
                    code,
                    count=1,
                )

                code = re.sub(
                    rf"\b{re.escape(old_name)}\b",
                    "run",
                    code,
                )

            return code

        indented = "\n".join(
            "    " + line
            for line in code.split("\n")
        )

        return (
            "def run(params=None):\n"
            '    """Habilidad generada."""\n'
            f"{indented}\n"
        )

    # =========================================================================
    # SEGURIDAD
    # =========================================================================

    def _is_safe_code(
        self,
        code: str,
    ) -> bool:
        """
        Permite automatización del sistema pero bloquea
        destrucción masiva.
        """

        dangerous_patterns = [
            "os.system('rm -rf",
            "shutil.rmtree('/'",
            "subprocess.call('sudo rm",
            "os.remove('/",
            "os.unlink('/",
            "shutil.rmtree('/",
            "os.system('format",
            "subprocess.call('format",
            "os.system('del /f",
            "subprocess.call('del /f",
            "__import__('os').system('shutdown",
            "os.system('shutdown /s",
            "os.system('shutdown -s",
            "subprocess.run(['shutdown'",
        ]

        lower_code = code.lower()

        for pattern in dangerous_patterns:
            if pattern in lower_code:
                return False

        if "/etc/passwd" in lower_code:
            return False

        if "/etc/shadow" in lower_code:
            return False

        if (
            "c:/windows/system32" in lower_code
            and (
                "os.remove" in lower_code
                or "shutil.rmtree" in lower_code
            )
        ):
            return False

        return True

    # =========================================================================
    # EJECUCIÓN EN SANDBOX
    # =========================================================================

    def _test_code_sandboxed(
        self,
        code: str,
        timeout: int = 60,
    ) -> Tuple[bool, str, str]:

        valid, error = self._validate_syntax(code)

        if not valid:
            return (
                False,
                "",
                f"Error de sintaxis: {error}",
            )

        test_code = (
            code
            + "\n\n"
            + "if __name__ == '__main__':\n"
            + "    print(run({}))"
        )

        fd, path = tempfile.mkstemp(
            suffix=".py",
            prefix="skill_test_",
        )

        os.close(fd)

        try:
            with open(
                path,
                "w",
                encoding="utf-8",
            ) as f:
                f.write(test_code)

            cmd = [
                sys.executable,
                path,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(Path(path).parent),
            )

            if result.returncode == 0:
                return (
                    True,
                    result.stdout.strip()
                    or "Ejecutado sin salida.",
                    "",
                )

            error_msg = (
                result.stderr.strip()
                or result.stdout.strip()
            )

            return (
                False,
                result.stdout.strip(),
                error_msg[:300],
            )

        except subprocess.TimeoutExpired:
            return (
                False,
                "",
                f"Timeout: excedió {timeout} segundos.",
            )

        except Exception as e:
            return (
                False,
                "",
                f"Error en sandbox: {str(e)[:200]}",
            )

        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    # =========================================================================
    # DETECCIÓN DE TIPO DE ARTEFACTO
    # =========================================================================

    def _detect_artifact_type(
        self,
        task_description: str,
        skill_name: str,
        action: str,
    ) -> str:

        if action in (
            "action",
            "create_action",
            "generar_accion",
            "accion",
        ):
            return "action"

        return "skill"

    def _get_artifact_dir(
        self,
        artifact_type: str,
    ) -> Path:

        return (
            ACTIONS_DIR
            if artifact_type == "action"
            else SKILLS_DIR
        )

    # =========================================================================
    # GENERACIÓN DE CÓDIGO UNIVERSAL + SEGURIDAD
    # =========================================================================

    def _generate_code(
        self,
        task_description: str,
        action: str,
        skill_name: str,
        artifact_type: str,
        reference_code: str = "",
    ) -> Optional[str]:

        kind_label = (
            "acción"
            if artifact_type == "action"
            else "habilidad"
        )

        action_label = (
            "mejorar"
            if action == "improve"
            else "crear"
        )

        # ---------------------------------------------------------------------
        # DETECTAR SI LA TAREA ES DE SEGURIDAD
        # ---------------------------------------------------------------------

        security_keywords = [
            "vulnerabilidad",
            "escaneo",
            "puerto",
            "red",
            "ataque",
            "defensa",
            "seguridad",
            "pentest",
            "hack",
            "exploit",
            "ransomware",
            "keylogger",
            "sniffer",
            "firewall",
            "intrusion",
            "malware",
            "antivirus",
            "rootkit",
            "cve",
            "nmap",
            "wireshark",
            "contraseña",
            "password",
            "cifrado",
            "encriptar",
            "desencriptar",
            "hash",
            "phishing",
            "spoofing",
            "dos",
            "ddos",
            "tcp",
            "udp",
            "icmp",
            "arp",
            "dns",
        ]

        is_security = any(
            keyword in task_description.lower()
            for keyword in security_keywords
        )

        # ---------------------------------------------------------------------
        # PROMPT UNIVERSAL
        # ---------------------------------------------------------------------

        if not is_security:

            prompt = f"""
Eres un programador experto en Python especializado en automatización
de sistemas, mensajería, voz, notificaciones y control de aplicaciones.

Necesito {action_label} una {kind_label} llamada '{skill_name}'
que REALICE UNA TAREA ÚTIL Y AUTÓNOMA en el sistema del usuario.

Tarea:
{task_description}

REGLAS ESTRICTAS Y GUÍA DE LIBRERÍAS:

1. Responde ÚNICAMENTE con código Python, sin markdown, sin explicaciones.

2. El código DEBE tener una función:
   def run(params):

3. Usa LIBRERÍAS REALES según la tarea.

4. Si una librería no está disponible, intenta instalarla con:

subprocess.check_call(
    [sys.executable, '-m', 'pip', 'install', 'nombre']
)

--- LIBRERÍAS POR CATEGORÍA ---

SISTEMA:
- os
- subprocess
- shutil
- pathlib
- psutil
- pygetwindow
- pyautogui
- keyboard
- mouse

MENSAJERÍA:
- WhatsApp: pywhatkit
- selenium + webdriver_manager
- Telegram: python-telegram-bot
- Facebook Messenger: selenium
- Correo: smtplib, imaplib, email
- SMS/Llamadas: twilio

VOZ:
- speech_recognition
- pyttsx3
- edge_tts
- gtts
- pyaudio
- sounddevice

NOTIFICACIONES:
- win10toast
- plyer

WEB:
- requests
- beautifulsoup4
- selenium
- playwright
- webbrowser

MULTIMEDIA:
- pyautogui
- mss
- pycaw
- vlc
- pydub

INTELIGENCIA:
- src.core.config.gemini_generate
- HybridRouter

INSTRUCCIONES:

- Si requiere navegador, usa selenium.
- Si requiere interfaz gráfica, usa pyautogui con FAILSAFE=True.
- Si requiere llamadas, usa twilio si existe API key.
- Si requiere voz, usa speech_recognition y pyttsx3.
- Si requiere notificaciones, usa plyer.
- Maneja errores con try/except.
- Devuelve mensajes claros.
- Incluye comentarios útiles.
- Verifica dependencias antes de ejecutar.

Código para la {kind_label} '{skill_name}':
""".strip()

        # ---------------------------------------------------------------------
        # PROMPT DE CIBERSEGURIDAD
        # ---------------------------------------------------------------------

        else:

            prompt = f"""
Eres un experto en ciberseguridad y hacking ético.

Necesito {action_label} una {kind_label} llamada '{skill_name}'
para PROTEGER, AUDITAR y DEFENDER sistemas.

Tarea:
{task_description}

REGLAS ESTRICTAS:

1. Responde ÚNICAMENTE con código Python.
2. El código DEBE tener una función def run(params).
3. Utiliza librerías reales como:
   - nmap
   - scapy
   - requests
   - socket
   - subprocess
   - os
   - psutil
   - cryptography
   - hashlib
   - paramiko
   - dnspython
   - whois
   - shodan

4. Las acciones deben ser seguras y no destructivas.
5. Genera reportes JSON o HTML cuando corresponda.
6. Maneja errores correctamente.
7. Incluye logs para depuración.

Ejemplo de escaneo:

import socket
from datetime import datetime


def run(params):

    target = params.get(
        "target",
        "127.0.0.1",
    )

    ports = params.get(
        "ports",
        [22, 80, 443, 3306, 8080],
    )

    results = []

    for port in ports:

        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        )

        sock.settimeout(1)

        result = sock.connect_ex(
            (target, port)
        )

        if result == 0:
            results.append(
                f"Puerto {{port}} ABIERTO"
            )

        sock.close()

    return {{
        "status": "success",
        "target": target,
        "scan_time": datetime.now().isoformat(),
        "open_ports": results,
    }}


Código para la {kind_label} de seguridad '{skill_name}':
""".strip()

        # ---------------------------------------------------------------------
        # CÓDIGO DE REFERENCIA
        # ---------------------------------------------------------------------

        if reference_code:

            prompt += (
                "\n\n"
                "Código previo que necesita mejora o corrección:\n"
                f"{reference_code}\n"
                "Corrige los errores y devuelve "
                "solo el código Python funcional."
            )

        # ---------------------------------------------------------------------
        # GEMINI
        # ---------------------------------------------------------------------

        try:

            from src.core.config import gemini_generate

            response = gemini_generate(
                prompt,
                model="gemini-3.5-flash-lite",
            )

            if response and len(response.strip()) > 20:
                return self._clean_code(response)

        except Exception as e:

            _log(
                f"Gemini 3.5 falló: {e}. "
                "Intentando 2.5...",
                "WARNING",
            )

            try:

                response = gemini_generate(
                    prompt,
                    model="gemini-2.5-flash-lite",
                )

                if response and len(response.strip()) > 20:
                    return self._clean_code(response)

            except Exception as e2:

                _log(
                    f"Gemini 2.5 falló: {e2}",
                    "WARNING",
                )

        # ---------------------------------------------------------------------
        # FALLBACK AL ROUTER
        # ---------------------------------------------------------------------

        try:

            response = self.router.route(
                prompt,
                "AutoProgrammer",
            )

            if response and len(response.strip()) > 20:
                return self._clean_code(response)

        except Exception as e:

            _log(
                f"Router falló: {e}",
                "ERROR",
            )

        return None

    # =========================================================================
    # GUARDADO DEL ARCHIVO
    # =========================================================================

    def _save_artifact(
        self,
        artifact_dir: Path,
        skill_name: str,
        code: str,
        action: str = "create",
    ) -> Optional[Path]:

        try:

            if not artifact_dir.exists():

                _log(
                    f"Creando directorio: {artifact_dir}",
                    "INFO",
                )

                artifact_dir.mkdir(
                    parents=True,
                    exist_ok=True,
                )

            filename = f"{skill_name}.py"
            filepath = artifact_dir / filename

            if filepath.exists() and action == "create":

                _log(
                    f"El archivo {filename} ya existe. "
                    "Usa 'improve' para sobrescribir.",
                    "WARNING",
                )

                return None

            _log(
                f"Escribiendo archivo: {filepath}",
                "INFO",
            )

            with open(
                filepath,
                "w",
                encoding="utf-8",
            ) as f:
                f.write(code)

            if (
                filepath.exists()
                and filepath.stat().st_size > 0
            ):

                _log(
                    f"Archivo guardado correctamente: "
                    f"{filepath} "
                    f"({filepath.stat().st_size} bytes)",
                    "INFO",
                )

                return filepath

            _log(
                f"El archivo parece vacío o no se creó: "
                f"{filepath}",
                "ERROR",
            )

        except PermissionError as e:

            _log(
                f"Permiso denegado al escribir "
                f"{filepath}: {e}",
                "ERROR",
            )

        except OSError as e:

            _log(
                f"Error de sistema al escribir "
                f"{filepath}: {e}",
                "ERROR",
            )

        except Exception as e:

            _log(
                f"Error inesperado al guardar: {e}",
                "ERROR",
            )

            traceback.print_exc()

        return None

    # =========================================================================
    # CICLO PRINCIPAL DE GENERACIÓN Y PRUEBA
    # =========================================================================

    def generate_and_test(
        self,
        task_description: str,
        skill_name: str = None,
        action: str = "create",
        artifact_type: str = None,
    ) -> str:
        """
        Genera, prueba y guarda una habilidad universal o de seguridad.
        """

        if action in (
            "create_action",
            "generar_accion",
            "action",
        ):

            action = "create"
            artifact_type = "action"

        if not skill_name:

            skill_name = generate_skill_name(
                task_description
            )

            _log(
                f"Nombre generado automáticamente: "
                f"{skill_name}"
            )

        if artifact_type is None:

            artifact_type = self._detect_artifact_type(
                task_description,
                skill_name,
                action,
            )

        artifact_dir = self._get_artifact_dir(
            artifact_type
        )

        kind_label = (
            "acción"
            if artifact_type == "action"
            else "habilidad"
        )

        _log(
            f"Generando {kind_label} universal "
            f"'{skill_name}' en {artifact_dir} "
            f"(acción={action})"
        )

        filename = f"{skill_name}.py"
        filepath = artifact_dir / filename
        file_exists = filepath.exists()

        # ---------------------------------------------------------------------
        # COMPROBAR ARCHIVO EXISTENTE
        # ---------------------------------------------------------------------

        if file_exists and action == "create":

            try:

                existing_code = filepath.read_text(
                    encoding="utf-8"
                )

                ok, output, error = (
                    self._test_code_sandboxed(
                        existing_code
                    )
                )

                if ok:

                    return (
                        f"✅ La {kind_label} universal "
                        f"'{skill_name}' ya existe y funciona.\n"
                        f"Archivo: {filepath}\n"
                        f"Salida de prueba: {output[:100]}\n"
                        "Si quieres mejorar o ampliar su "
                        "funcionalidad, usa 'improve'."
                    )

                _log(
                    f"La {kind_label} existente falla. "
                    "Cambiando a modo 'improve'.",
                    "WARNING",
                )

                action = "improve"

                task_description = (
                    f"La {kind_label} '{skill_name}' "
                    f"falla con: {error}. "
                    "Corrígela y amplía su funcionalidad "
                    "si es necesario."
                )

            except Exception as e:

                _log(
                    f"Error al leer el archivo existente: {e}",
                    "WARNING",
                )

                action = "improve"

                task_description = (
                    f"La {kind_label} '{skill_name}' "
                    "tiene errores. Repárala."
                )

        if action == "improve" and not file_exists:

            _log(
                f"No existe {kind_label} universal "
                f"'{skill_name}'. Creando nueva.",
                "INFO",
            )

            action = "create"

        best_code = None
        best_error = None
        last_code = None

        # ---------------------------------------------------------------------
        # INTENTOS DE GENERACIÓN
        # ---------------------------------------------------------------------

        for attempt in range(
            1,
            self.max_attempts + 1,
        ):

            _log(
                f"Intento {attempt}/{self.max_attempts} "
                f"generando código para '{skill_name}'..."
            )

            reference = (
                last_code
                if last_code
                else ""
            )

            code = self._generate_code(
                task_description,
                action,
                skill_name,
                artifact_type,
                reference_code=reference,
            )

            if not code:

                _log(
                    " -> No se recibió código (vacío).",
                    "WARNING",
                )

                continue

            code = self._clean_code(code)
            code = self._ensure_run(code)

            _log(
                f" -> Código generado "
                f"({len(code)} caracteres)"
            )

            # -----------------------------------------------------------------
            # SEGURIDAD
            # -----------------------------------------------------------------

            if not self._is_safe_code(code):

                best_error = (
                    "Código contiene operaciones "
                    "destructivas no permitidas."
                )

                _log(
                    f" -> {best_error}",
                    "WARNING",
                )

                continue

            # -----------------------------------------------------------------
            # PRUEBA
            # -----------------------------------------------------------------

            ok, output, error = (
                self._test_code_sandboxed(code)
            )

            if ok:

                filepath_result = self._save_artifact(
                    artifact_dir,
                    skill_name,
                    code,
                    action,
                )

                if filepath_result is None:

                    if (
                        action == "create"
                        and file_exists
                    ):

                        return (
                            f"⚠️ La {kind_label} universal "
                            f"'{skill_name}' ya existe. "
                            "Usa 'improve' para actualizarla."
                        )

                    return (
                        f"❌ No se pudo guardar el archivo "
                        f"para '{skill_name}'. "
                        "Verifica permisos."
                    )

                # -------------------------------------------------------------
                # REGISTRO
                # -------------------------------------------------------------

                try:

                    self.registry.register_skill(
                        skill_name,
                        str(filepath_result),
                    )

                    self.persistence.register_skill(
                        name=skill_name,
                        description=task_description,
                        file_path=str(filepath_result),
                        version=1,
                    )

                    self.persistence.log_attempt(
                        skill_name=skill_name,
                        attempt=attempt,
                        code=code,
                        success=True,
                        output=output,
                        error="",
                    )

                except Exception as e:

                    _log(
                        f"Error al registrar la habilidad: {e}",
                        "ERROR",
                    )

                return (
                    f"✅ {kind_label.capitalize()} universal "
                    f"'{skill_name}' "
                    f"{'mejorada' if action == 'improve' else 'creada'} "
                    "correctamente.\n"
                    f"Archivo: {filepath_result}\n"
                    f"Salida de prueba: "
                    f"{output[:150]}"
                    f"{'...' if len(output) > 150 else ''}\n"
                    f"Tamaño: "
                    f"{filepath_result.stat().st_size} bytes"
                )

            # -------------------------------------------------------------
            # GUARDAR MEJOR INTENTO
            # -------------------------------------------------------------

            if (
                best_code is None
                or (
                    error
                    and len(error)
                    < len(best_error or "")
                )
            ):

                best_code = code
                best_error = error

            self.persistence.log_attempt(
                skill_name=skill_name,
                attempt=attempt,
                code=code,
                success=False,
                output=output,
                error=error,
            )

            _log(
                f" -> ❌ Falló: "
                f"{error[:100] if error else 'desconocido'}...",
                "WARNING",
            )

            last_code = code

            task_description = (
                f"El código anterior falló con: {error}\n"
                f"Tarea original: {task_description}\n"
                "Corrige los errores y devuelve código funcional."
            )

        # ---------------------------------------------------------------------
        # GUARDAR MEJOR INTENTO FALLIDO
        # ---------------------------------------------------------------------

        if best_code:

            failed_filename = (
                f"{skill_name}_failed.py"
            )

            failed_filepath = (
                artifact_dir / failed_filename
            )

            try:

                with open(
                    failed_filepath,
                    "w",
                    encoding="utf-8",
                ) as f:
                    f.write(best_code)

                _log(
                    f" -> ⚠️ Intento fallido guardado en "
                    f"{failed_filepath}",
                    "WARNING",
                )

                return (
                    f"⚠️ No se pudo generar una "
                    f"{kind_label} funcional "
                    f"para '{skill_name}'.\n"
                    f"Se guardó el mejor intento en "
                    f"{failed_filepath}\n"
                    f"Error: "
                    f"{best_error[:200] if best_error else 'desconocido'}"
                )

            except Exception as e:

                _log(
                    f"Error al guardar intento fallido: {e}",
                    "ERROR",
                )

                return (
                    f"❌ No se pudo guardar el intento "
                    f"fallido para '{skill_name}': {e}"
                )

        return (
            f"❌ No se pudo generar código para "
            f"'{skill_name}'. "
            f"Último error: "
            f"{best_error[:200] if best_error else 'desconocido'}"
        )


# =============================================================================
# FUNCIÓN EXPORTABLE PARA USO COMO SKILL
# =============================================================================

def skill_auto_programmer_advanced(
    params: dict,
) -> str:
    """
    Skill que invoca al AutoProgrammer para crear/mejorar
    cualquier habilidad útil, incluyendo ciberseguridad.
    """

    task = params.get(
        "task",
        "",
    )

    if not task:
        return (
            "Necesito una descripción de la tarea (task)."
        )

    name = params.get(
        "name",
        None,
    )

    action = params.get(
        "action",
        "create",
    )

    artifact_type = params.get(
        "type",
        None,
    )

    try:

        from src.core.hybrid_router import HybridRouter
        from src.core.skills_registry import SkillsRegistry
        from src.core.persistence import Persistence

        router = HybridRouter()
        registry = SkillsRegistry()
        persistence = Persistence()

        programmer = AutoProgrammer(
            router,
            registry,
            persistence,
        )

        return programmer.generate_and_test(
            task,
            skill_name=name,
            action=action,
            artifact_type=artifact_type,
        )

    except Exception as e:

        return (
            f"Error al ejecutar AutoProgrammer: {e}"
        )


# =============================================================================
# PRUEBA RÁPIDA
# =============================================================================

if __name__ == "__main__":

    prog = AutoProgrammer()

    result = prog.generate_and_test(
        "Habilidad que escucha el micrófono, "
        "transcribe lo que digo y lo escribe "
        "en la pantalla usando pyautogui",
        "dictador_por_voz",
        action="create",
        artifact_type="skill",
    )

    print(result)