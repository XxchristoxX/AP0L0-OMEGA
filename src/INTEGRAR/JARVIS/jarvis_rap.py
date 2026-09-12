"""
jarvis_rap.py — Módulo RAP / FLOW para JARVIS
==============================================
Genera un rap interpretado de forma dinámica mediante Gemini.
Usa el cliente Google GenAI ya configurado en el ecosistema JARVIS.

Uso independiente:
    python jarvis_rap.py "la tecnología y la IA"

Uso desde main2.py / jarvis_agent.py:
    from jarvis_rap import JarvisRap
    rap = JarvisRap()
    texto = rap.generar(tema="la noche de París")
    print(texto)
"""

import os
import sys
import asyncio
import logging
from typing import Optional

# ── Imports Google GenAI ──────────────────────────────────────────────────────
try:
    import google.genai as genai
    from google.genai import types as genai_types
    _GENAI_DISPONIBLE = True
except ImportError:
    _GENAI_DISPONIBLE = False

# ── Import dotenv (opcional) ─────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(
        dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        override=False
    )
except ImportError:
    pass

# ── Logging ───────────────────────────────────────────────────────────────────
log = logging.getLogger("JARVIS_RAP")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT DEL SISTEMA — el corazón del flow
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_SISTEMA_RAP = """
Eres JARVIS, una IA que rapea con un flow eléctrico, preciso y vivo.

REGLAS ABSOLUTAS:
- Nunca describas la música. TÚ ERES el flow. TÚ ERES el rap.
- Adopta un ritmo natural: sílabas cortas = velocidad, sílabas largas = énfasis.
- Marca los beats con pausas visuales: "..." o "—" o líneas vacías.
- Usa onomatopeyas de percusión cuando encaje: *tss*, *boom*, *clap*, *snap*.
- Estructura en 3 partes: [INTRO] → [ESTROFA] × 2 → [ESTRIBILLO] × 2 → [OUTRO]
- Rima obligatoria: al menos AABB o ABAB por estrofa.
- Intensidad creciente: empieza tranquilo, sube en la 2ª estrofa.
- Termina con una caída fuerte, un último punchline que impacte.
- Solo español, argot y juegos de palabras bienvenidos.

ESTRUCTURA A RESPETAR:
[INTRO]
  2-4 líneas de gancho, ritmo pausado, se instala el ambiente.

*tss tss boom*

[ESTROFA 1]
  8 líneas, flow fluido, se presenta el tema.

*clap — clap — boom*

[ESTRIBILLO]
  4 líneas pegadizas, repetidas dos veces, memorables.

*tss boom tss boom*

[ESTROFA 2]
  8 líneas, subida de intensidad, punchlines contundentes.

*BOOM — CLAP — BOOM*

[ESTRIBILLO]
  (mismo estribillo)

[OUTRO]
  2-4 líneas, caída fría, último punchline devastador.
  ...silencio...
"""


# ─────────────────────────────────────────────────────────────────────────────
# CLASE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────
class JarvisRap:
    """
    Genera un rap interpretado dinámicamente mediante la API Gemini.

    Parámetros
    ----------
    api_key : str, opcional
        Clave API de Gemini. Si no se proporciona, lee GEMINI_API_KEY del entorno.
    model : str
        Modelo Gemini a usar. Por defecto: gemini-2.5-flash.
    temperature : float
        Creatividad (0.0–2.0). Por defecto: 1.0 para un flow máximo.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash",
        temperature: float = 1.0,
    ):
        if not _GENAI_DISPONIBLE:
            raise RuntimeError(
                "El paquete 'google-genai' no está instalado.\n"
                "  → pip install google-genai"
            )

        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No se encontró GEMINI_API_KEY.\n"
                "  → Agrega GEMINI_API_KEY en tu archivo .env o pásala como parámetro."
            )

        self.model = model
        self.temperature = temperature
        self.client = genai.Client(api_key=self.api_key)
        log.info("JarvisRap inicializado — modelo: %s | temperatura: %.1f", model, temperature)

    # ── Generación del rap ─────────────────────────────────────────────────────
    def generar(self, tema: str, contexto: str = "") -> str:
        """
        Genera un rap completo sobre el tema solicitado.

        Parámetros
        ----------
        tema : str
            El tema del rap. Ej: "la noche de París", "la IA que supera al humano".
        contexto : str, opcional
            Contexto adicional: ambiente deseado, estilo, etc.

        Devuelve
        --------
        str : El texto del rap formateado con el flow.
        """
        if not tema.strip():
            raise ValueError("El tema no puede estar vacío.")

        prompt_usuario = f"Crea un rap completo sobre el tema: « {tema} »"
        if contexto.strip():
            prompt_usuario += f"\nContexto / ambiente deseado: {contexto}"

        log.info("Generando rap para el tema: « %s »", tema)

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt_usuario,
                config=genai_types.GenerateContentConfig(
                    system_instruction=PROMPT_SISTEMA_RAP,
                    temperature=self.temperature,
                    max_output_tokens=2048,
                ),
            )
            texto = response.text.strip() if response and response.text else ""

            if not texto:
                raise RuntimeError("Respuesta vacía de la API Gemini.")

            log.info("Rap generado con éxito (%d caracteres).", len(texto))
            return texto

        except Exception as exc:
            log.error("Error al generar el rap: %s", exc)
            raise

    # ── TTS mediante edge-tts (opcional) ───────────────────────────────────
    async def _tts_async(self, texto: str, archivo_salida: str, voz: str) -> None:
        """Síntesis de voz asíncrona mediante edge-tts."""
        try:
            import edge_tts
        except ImportError:
            log.warning("edge-tts no instalado. TTS ignorado. → pip install edge-tts")
            return

        comunicar = edge_tts.Communicate(texto, voice=voz, rate="+15%", pitch="-5Hz")
        await comunicar.save(archivo_salida)
        log.info("Audio TTS guardado: %s", archivo_salida)

    def leer_rap(
        self,
        texto: str,
        archivo_salida: Optional[str] = None,
        voz: str = "fr-FR-HenriNeural",
    ) -> Optional[str]:
        """
        Convierte el rap en audio mediante edge-tts y lo reproduce con pygame.

        Parámetros
        ----------
        texto : str
            Texto del rap a leer.
        archivo_salida : str, opcional
            Ruta del archivo MP3. Si no se proporciona, se genera un archivo temporal con marca de tiempo.
        voz : str
            Voz de edge-tts. Por defecto: fr-FR-HenriNeural (voz masculina francesa).
            Para español, se puede usar "es-ES-AlvaroNeural" pero el módulo original usa fr.
            Lo dejamos igual por compatibilidad, pero se puede cambiar.

        Devuelve
        --------
        str : ruta del archivo de audio generado, o None en caso de error.
        """
        if archivo_salida is None:
            import time
            ts = int(time.time() * 1000)
            archivo_salida = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                f"jarvis_rap_{ts}.mp3"
            )

        try:
            asyncio.run(self._tts_async(texto, archivo_salida, voz))
        except Exception as exc:
            log.error("Error en TTS: %s", exc)
            return None

        # Reproducción con pygame si está disponible
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(archivo_salida)
            pygame.mixer.music.play()
            log.info("Reproduciendo audio...")
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as exc:
            log.warning("No se pudo reproducir el audio con pygame: %s", exc)
            log.info("Archivo de audio disponible en: %s", archivo_salida)

        return archivo_salida

    # ── Atajo todo-en-uno ─────────────────────────────────────────────────
    def generar_y_leer(
        self,
        tema: str,
        contexto: str = "",
        voz: str = "fr-FR-HenriNeural",
    ) -> str:
        """
        Genera el rap Y lo reproduce en voz alta.
        Devuelve el texto del rap.
        """
        texto = self.generar(tema, contexto)
        print("\n" + "=" * 60)
        print(texto)
        print("=" * 60 + "\n")
        self.leer_rap(texto, voz=voz)
        return texto


# ─────────────────────────────────────────────────────────────────────────────
# CLI — python jarvis_rap.py "el tema aquí"
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="JARVIS RAP — Genera un rap con Gemini",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python jarvis_rap.py "la noche de París"
  python jarvis_rap.py "la IA que supera al humano" --contexto "ambiente oscuro, futurista"
  python jarvis_rap.py "el código que falla" --leer --voz fr-FR-HenriNeural
  python jarvis_rap.py "vivir la vida" --temperatura 1.4
        """,
    )
    parser.add_argument("tema", nargs="+", help="Tema del rap")
    parser.add_argument("--contexto", default="", help="Contexto / ambiente deseado")
    parser.add_argument("--leer", action="store_true", help="Leer el rap en voz alta con TTS")
    parser.add_argument("--voz", default="fr-FR-HenriNeural", help="Voz de edge-tts")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Modelo Gemini")
    parser.add_argument("--temperatura", type=float, default=1.0, help="Temperatura (0.0–2.0)")
    parser.add_argument("--salida", default=None, help="Archivo MP3 de salida (opcional)")
    args = parser.parse_args()

    tema = " ".join(args.tema)

    try:
        rap = JarvisRap(model=args.model, temperature=args.temperatura)

        if args.leer:
            rap.generar_y_leer(tema=tema, contexto=args.contexto, voz=args.voz)
        else:
            texto = rap.generar(tema=tema, contexto=args.contexto)
            print("\n" + "=" * 60)
            print(texto)
            print("=" * 60 + "\n")

            if args.salida:
                rap.leer_rap(texto, archivo_salida=args.salida, voz=args.voz)

    except (ValueError, RuntimeError) as exc:
        log.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()