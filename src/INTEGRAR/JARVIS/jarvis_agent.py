import os
import json
import time
import logging
from pathlib import Path

def _cargar_nombre_usuario():
    try:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        with open(_p, "r", encoding="utf-8") as _f:
            return json.load(_f).get("user_name", "Christopher")
    except Exception:
        return "Christopher"

NOMBRE_USUARIO = _cargar_nombre_usuario()

try:
    import google.genai as genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


logging.basicConfig(level=logging.INFO, format="[JARVIS_AGENT] %(message)s")


class JarvisAgent:
    """Andamiaje mínimo y reutilizable para el agente del espacio de trabajo JARVIS."""

    def __init__(self,
                 api_key: str = None,
                 model: str = "gemini-2.5-flash",
                 archivo_memoria: str = "jarvis_memoire.json"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model
        self.archivo_memoria = Path(archivo_memoria)
        self.client = genai.Client(api_key=self.api_key) if genai else None
        self.memoria = self._cargar_memoria()

    def _cargar_memoria(self) -> dict:
        if self.archivo_memoria.exists():
            try:
                return json.loads(self.archivo_memoria.read_text(encoding="utf-8"))
            except Exception as exc:
                logging.warning("No se pudo cargar la memoria: %s", exc)
        return {}

    def _guardar_memoria(self) -> None:
        try:
            self.archivo_memoria.write_text(json.dumps(self.memoria, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logging.warning("No se pudo guardar la memoria: %s", exc)

    def recordar(self, clave: str, valor: str) -> None:
        self.memoria[clave] = {
            "valor": valor,
            "timestamp": time.strftime("%d/%m/%Y %H:%M")
        }
        self._guardar_memoria()

    def olvidar(self, clave: str) -> bool:
        if clave in self.memoria:
            del self.memoria[clave]
            self._guardar_memoria()
            return True
        return False

    def contexto_memoria(self) -> str:
        if not self.memoria:
            return ""
        lineas = ["MEMORIA PERSISTENTE:"]
        for clave, data in self.memoria.items():
            lineas.append(f"  - {clave} : {data['valor']} (anotado el {data['timestamp']})")
        return "\n".join(lineas)

    def prompt_sistema(self) -> str:
        base = (
            f"Eres JARVIS, asistente IA personal creado por {NOMBRE_USUARIO}.\n"
            "Respuestas cortas, tono sarcástico pero respetuoso.\n\n"
        )
        base += self.contexto_memoria()
        base += (
            f"\n\nEstás conectado a Home Assistant, la domótica de {NOMBRE_USUARIO}. "
            f"Cuando {NOMBRE_USUARIO} hable de luces, enchufes, calefacción, temperatura, "
            "escenas o alarma, DEBES generar un comando JSON. "
            "SOLO para estas solicitudes de domótica, responde con el JSON.\n"
        )
        return base

    def construir_prompt(self, mensaje_usuario: str) -> list:
        return [
            {"role": "system", "content": self.prompt_sistema()},
            {"role": "user", "content": mensaje_usuario}
        ]

    def generate_response(self, mensaje_usuario: str) -> str:
        if not self.client or not types:
            raise RuntimeError("google.genai no está instalado o falló la importación.")

        prompt = self.construir_prompt(mensaje_usuario)
        response = self.client.responses.create(
            model=self.model,
            messages=prompt
        )
        if response and getattr(response, "output", None):
            partes_texto = []
            for item in response.output:
                if getattr(item, "content", None):
                    for entrada in item.content:
                        if entrada.get("type") == "output_text":
                            partes_texto.append(entrada.get("text", ""))
            return "".join(partes_texto).strip()
        return ""


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Ejecuta el andamiaje del agente JARVIS.")
    parser.add_argument("message", nargs="+", help="Mensaje del usuario para el agente.")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Modelo a usar.")
    parser.add_argument("--memory-file", default="jarvis_memoire.json", help="Ruta del archivo de memoria.")
    args = parser.parse_args()

    agent = JarvisAgent(model=args.model, archivo_memoria=args.memory_file)
    message = " ".join(args.message)
    print("Prompt del sistema:\n", agent.prompt_sistema())
    print("\nMensaje del usuario:\n", message)

    try:
        response = agent.generate_response(message)
        print("\nRespuesta del agente:\n", response)
    except Exception as exc:
        logging.error("No se pudo generar la respuesta: %s", exc)


if __name__ == "__main__":
    main()