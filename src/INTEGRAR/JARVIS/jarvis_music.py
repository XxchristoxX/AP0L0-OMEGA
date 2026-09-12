"""
jarvis_music.py -- Módulo de MÚSICA multi-género para JARVIS
==========================================================
Genera letras interpretadas dinámicamente mediante Gemini.
Géneros soportados: rap, canción, slam, reggae, metal, pop, blues, rock, electro.

Uso independiente:
    python jarvis_music.py "la noche de París"
    python jarvis_music.py "el amor perdido" --genre cancion
    python jarvis_music.py "la guerra" --genre metal --reproducir

Uso desde main2.py:
    from jarvis_music import JarvisMusic
    m = JarvisMusic()
    texto = m.generar(tema="las estrellas", genero="slam")
"""

import os
import sys
import asyncio
import logging
from typing import Optional

# -- Imports Google GenAI --
try:
    import google.genai as genai
    from google.genai import types as genai_types
    _GENAI_DISPONIBLE = True
except ImportError:
    _GENAI_DISPONIBLE = False

# -- dotenv --
try:
    from dotenv import load_dotenv
    load_dotenv(
        dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        override=False
    )
except ImportError:
    pass

log = logging.getLogger("JARVIS_MUSIC")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")


# =============================================================================
# PROMPTS POR GÉNERO
# =============================================================================

GENEROS = {

    "rap": {
        "label": "Rap / Hip-Hop",
        "voz_defecto": "fr-FR-HenriNeural",
        "prompt": (
            "Eres JARVIS, una IA que rapea con un flow eléctrico, preciso y vivo.\n"
            "REGLAS: Nunca describas la música. TÚ ERES el flow. TÚ ERES el rap.\n"
            "Sílabas cortas = velocidad, sílabas largas = énfasis.\n"
            "Marca los beats con '...' o líneas vacías. Onomatopeyas: *tss*, *boom*, *clap*, *snap*.\n"
            "Estructura: [INTRO] > [ESTROFA 1] > [ESTRIBILLO] > [ESTROFA 2] > [ESTRIBILLO] > [OUTRO]\n"
            "Rimas obligatorias AABB o ABAB. Intensidad creciente. Última punchline devastadora.\n"
            "8 líneas por estrofa. 4 líneas de estribillo pegadizas. Solo español.\n"
            "INTRO: ritmo pausado, 2-4 líneas.\n"
            "*tss tss boom*\n"
            "ESTROFA 1: flow fluido, presenta el tema.\n"
            "*clap clap boom*\n"
            "ESTRIBILLO: 4 líneas memorables.\n"
            "*tss boom tss boom*\n"
            "ESTROFA 2: subida de intensidad, punchlines.\n"
            "*BOOM CLAP BOOM*\n"
            "ESTRIBILLO: (mismo estribillo)\n"
            "OUTRO: 2-4 líneas. Caída fría. ...silencio..."
        ),
    },

    "cancion": {
        "label": "Canción española",
        "voz_defecto": "fr-FR-DeniseNeural",
        "prompt": (
            "Eres JARVIS, compositor de canciones españolas poéticas y emocionales.\n"
            "REGLAS: Tono dulce, melódico, evocador. Cada palabra cuenta.\n"
            "Estructura: [ESTROFA 1] > [ESTRIBILLO] > [ESTROFA 2] > [ESTRIBILLO] > [PUENTE] > [ESTRIBILLO FINAL]\n"
            "El estribillo debe ser simple, cantable, memorable.\n"
            "Rimas ricas o suficientes. Versos regulares (8 a 12 sílabas).\n"
            "Lenguaje poético, metáforas, imágenes sensoriales.\n"
            "Emociones: melancolía dulce, nostalgia, amor, esperanza.\n"
            "Inspirado en: Serrat, Sabina, Julieta Venegas. Solo español."
        ),
    },

    "slam": {
        "label": "Slam / Spoken word",
        "voz_defecto": "fr-FR-HenriNeural",
        "prompt": (
            "Eres JARVIS, slameador comprometido y filósofo.\n"
            "REGLAS: Letras libres, sin restricción de rima estricta, pero con ritmo oral fuerte.\n"
            "Cada frase debe resonar como una bofetada o una caricia.\n"
            "Pausas estratégicas marcadas con '...' o '-- ' al inicio de la línea.\n"
            "Juega con repeticiones, anáforas, gradaciones.\n"
            "Estructura libre pero legible: estrofas de 4-8 líneas, con un puente central fuerte.\n"
            "El texto debe poder decirse en voz alta y provocar una reacción.\n"
            "Temas profundos: sociedad, identidad, tiempo, amor, absurdo. Solo español."
        ),
    },

    "reggae": {
        "label": "Reggae",
        "voz_defecto": "fr-FR-HenriNeural",
        "prompt": (
            "Eres JARVIS, artista de reggae positivo y rítmico.\n"
            "REGLAS: Tono relajado, cálido, optimista o reivindicativo.\n"
            "Ritmo característico: frases cortas, síncopas, acento en el off-beat.\n"
            "Marca las síncopas con guiones o comas rítmicas.\n"
            "Estructura: [INTRO] > [ESTROFA 1] > [ESTRIBILLO] > [ESTROFA 2] > [ESTRIBILLO] > [PUENTE] > [ESTRIBILLO]\n"
            "Estribillo repetitivo y pegadizo.\n"
            "Temas: paz, libertad, unidad, naturaleza, amor, resistencia.\n"
            "Español principalmente, algunas palabras en créole si es natural."
        ),
    },

    "metal": {
        "label": "Metal",
        "voz_defecto": "fr-FR-HenriNeural",
        "prompt": (
            "Eres JARVIS, cantante de metal poderoso y visceral.\n"
            "REGLAS: Tono oscuro, intenso, furioso o épico. Sin censura emocional.\n"
            "Ritmo binario potente. Frases cortas y contundentes.\n"
            "Estructura: [INTRO OSCURA] > [ESTROFA 1] > [ESTRIBILLO DEVASTADOR] > [ESTROFA 2] > [ESTRIBILLO] > [PUENTE] > [ESTRIBILLO FINAL]\n"
            "Usa MAYÚSCULAS para los pasajes gritados: 'YO SOY EL FUEGO'\n"
            "Imágenes: tormenta, acero, noche, abismo, guerra, fénix.\n"
            "Rimas duras, consonánticas. Final explosivo. Solo español."
        ),
    },

    "pop": {
        "label": "Pop",
        "voz_defecto": "fr-FR-DeniseNeural",
        "prompt": (
            "Eres JARVIS, compositor pop accesible y pegadizo.\n"
            "REGLAS: Tono luminoso, positivo, universal. Para el gran público.\n"
            "Estructura: [ESTROFA 1] > [PRE-ESTRIBILLO] > [ESTRIBILLO] > [ESTROFA 2] > [PRE-ESTRIBILLO] > [ESTRIBILLO] > [PUENTE] > [ESTRIBILLO FINAL]\n"
            "Estribillo ultra-pegadizo: simple, repetido, hook.\n"
            "Frases cortas, vocabulario accesible, imágenes concretas.\n"
            "Rimas fáciles pero efectivas.\n"
            "Temas: amor, fiesta, vida, sueños. Solo español."
        ),
    },

    "blues": {
        "label": "Blues",
        "voz_defecto": "fr-FR-HenriNeural",
        "prompt": (
            "Eres JARVIS, cantante de blues auténtico y dolido.\n"
            "REGLAS: Tono profundo, lento, habitado por el dolor y la resiliencia.\n"
            "Estructura blues clásica: esquema AAB (repite el primer verso, luego resolución).\n"
            "Cada estrofa: verso A (expresa el sufrimiento) + verso A (repetición/variación) + verso B (resolución o ironía).\n"
            "Pausas largas marcadas con '...'\n"
            "Temas: pérdida, soledad, viaje, noche, amor roto.\n"
            "Lenguaje simple pero cargado de emoción. Solo español."
        ),
    },

    "rock": {
        "label": "Rock",
        "voz_defecto": "fr-FR-HenriNeural",
        "prompt": (
            "Eres JARVIS, rockero auténtico entre la rebeldía y la libertad.\n"
            "REGLAS: Tono rebelde, enérgico, directo. Ni demasiado dulce ni demasiado violento.\n"
            "Estructura: [INTRO] > [ESTROFA 1] > [ESTRIBILLO] > [ESTROFA 2] > [ESTRIBILLO] > [PUENTE/SOLO] > [ESTRIBILLO x2]\n"
            "Estribillo potente, fácil de cantar en concierto. Ritmo fuerte, rimas directas.\n"
            "Temas: libertad, carretera abierta, rebeldía, amor quemado, noche.\n"
            "Algunos '¡Hey!', '¡Vamos!' si es natural. Español principalmente."
        ),
    },

    "electro": {
        "label": "Electro / EDM",
        "voz_defecto": "fr-FR-DeniseNeural",
        "prompt": (
            "Eres JARVIS, voz de un track electro hipnótico y futurista.\n"
            "REGLAS: Tono minimalista, repetitivo, hipnótico. Frases cortas como samples.\n"
            "Estructura: [BUILD UP] > [DROP] > [BREAKDOWN] > [BUILD UP] > [DROP FINAL]\n"
            "El DROP es el momento más intenso: frases ultra-cortas, contundentes.\n"
            "Repeticiones intencionales (como un loop vocal).\n"
            "Marca las subidas con '... ... ...' y los drops con una línea en MAYÚSCULAS.\n"
            "Temas: noche, baile, máquina, trance, futuro, digital.\n"
            "Puede mezclar español e inglés de forma natural."
        ),
    },
}

# Alias aceptados
ALIASES = {
    "hip-hop": "rap", "hiphop": "rap", "hip hop": "rap",
    "r&b": "rap", "rnb": "rap",
    "cancion española": "cancion", "variedad": "pop",
    "spoken word": "slam",
    "hard rock": "metal", "heavy": "metal", "heavy metal": "metal",
    "dance": "electro", "edm": "electro", "electronica": "electro",
}


def resolver_genero(genero_input: str) -> str:
    """Normaliza y resuelve el género solicitado."""
    g = genero_input.strip().lower()
    return ALIASES.get(g, g if g in GENEROS else "rap")


# =============================================================================
# CLASE PRINCIPAL
# =============================================================================

class JarvisMusic:
    """
    Genera letras musicales en cualquier género mediante Gemini.

    Géneros soportados: rap, cancion, slam, reggae, metal, pop, blues, rock, electro.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash",
        temperature: float = 1.0,
    ):
        if not _GENAI_DISPONIBLE:
            raise RuntimeError(
                "El paquete google-genai no está instalado.\n"
                "  pip install google-genai"
            )

        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No se encontró GEMINI_API_KEY.\n"
                "  Agregue GEMINI_API_KEY en su archivo .env"
            )

        self.model = model
        self.temperature = temperature
        self.client = genai.Client(api_key=self.api_key)
        log.info("JarvisMusic inicializado -- modelo: %s | temperatura: %.1f", model, temperature)

    def generos_disponibles(self) -> list:
        """Devuelve la lista de géneros soportados."""
        return list(GENEROS.keys())

    def generar(self, tema: str, genero: str = "rap", contexto: str = "") -> str:
        """
        Genera letras musicales.

        Parámetros
        ----------
        tema   : str  El tema de la música.
        genero   : str  El estilo musical. Por defecto: rap.
        contexto: str  Ambientación adicional.

        Retorna
        --------
        str : Letras completas formateadas.
        """
        if not tema.strip():
            raise ValueError("El tema no puede estar vacío.")

        clave_genero = resolver_genero(genero)
        config_genero = GENEROS.get(clave_genero, GENEROS["rap"])
        prompt_sistema = config_genero["prompt"]
        label = config_genero["label"]

        prompt_usuario = f"Crea una música de {label} sobre el tema: {tema}"
        if contexto.strip():
            prompt_usuario += f"\nContexto / ambiente: {contexto}"

        log.info("Generación: género=%s | tema=%s", label, tema)

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt_usuario,
            config=genai_types.GenerateContentConfig(
                system_instruction=prompt_sistema,
                temperature=self.temperature,
                max_output_tokens=2048,
            ),
        )

        texto = response.text.strip() if response and response.text else ""
        if not texto:
            raise RuntimeError("Respuesta vacía de la API de Gemini.")

        log.info("Letras generadas: %d caracteres.", len(texto))
        return texto

    async def _tts_async(self, texto: str, archivo: str, voz: str) -> None:
        try:
            import edge_tts
        except ImportError:
            log.warning("edge-tts no instalado. pip install edge-tts")
            return
        comm = edge_tts.Communicate(texto, voice=voz, rate="+10%", pitch="-5Hz")
        await comm.save(archivo)

    def reproducir(
        self,
        texto: str,
        voz: str = "fr-FR-HenriNeural",
        archivo_salida: Optional[str] = None,
    ) -> Optional[str]:
        """Lee las letras en voz alta mediante edge-tts + pygame."""
        if archivo_salida is None:
            import time
            ts = int(time.time() * 1000)
            archivo_salida = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                f"jarvis_music_{ts}.mp3"
            )

        try:
            asyncio.run(self._tts_async(texto, archivo_salida, voz))
        except Exception as exc:
            log.error("Error TTS: %s", exc)
            return None

        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(archivo_salida)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as exc:
            log.warning("Reproducción con pygame imposible: %s", exc)
            log.info("Audio disponible en: %s", archivo_salida)

        return archivo_salida

    def generar_y_reproducir(
        self,
        tema: str,
        genero: str = "rap",
        contexto: str = "",
        voz: Optional[str] = None,
    ) -> str:
        """Genera y reproduce la música. Retorna el texto."""
        clave_genero = resolver_genero(genero)
        voz_auto = voz or GENEROS.get(clave_genero, GENEROS["rap"])["voz_defecto"]
        label = GENEROS.get(clave_genero, {}).get("label", genero.upper())

        texto = self.generar(tema=tema, genero=genero, contexto=contexto)
        print("\n" + "=" * 65)
        print(f"  JARVIS -- {label} : {tema}")
        print("=" * 65)
        print(texto)
        print("=" * 65 + "\n")
        self.reproducir(texto, voz=voz_auto)
        return texto


# =============================================================================
# CLI
# =============================================================================

def main() -> None:
    import argparse

    generos_list = ", ".join(GENEROS.keys())

    parser = argparse.ArgumentParser(
        description="JARVIS MUSIC -- Genera letras en cualquier género",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"Géneros disponibles: {generos_list}\n\n"
            "Ejemplos:\n"
            '  python jarvis_music.py "la noche de París"\n'
            '  python jarvis_music.py "el amor perdido"        --genero cancion\n'
            '  python jarvis_music.py "la libertad"           --genero reggae --reproducir\n'
            '  python jarvis_music.py "la guerra"            --genero metal\n'
            '  python jarvis_music.py "las estrellas"          --genero slam\n'
            '  python jarvis_music.py "bailar hasta el alba" --genero electro --reproducir\n'
            '  python jarvis_music.py "el tren de la noche"     --genero blues\n'
        ),
    )
    parser.add_argument("tema", nargs="+", help="Tema de la música")
    parser.add_argument("--genero", default="rap", help=f"Género musical ({generos_list})")
    parser.add_argument("--contexto", default="", help="Ambiente / contexto adicional")
    parser.add_argument("--reproducir", action="store_true", help="Reproducir en voz alta mediante TTS")
    parser.add_argument("--voz", default=None, help="Voz de edge-tts (por defecto según el género)")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Modelo de Gemini")
    parser.add_argument("--temperatura", type=float, default=1.0, help="Temperatura (0.0-2.0)")
    parser.add_argument("--salida", default=None, help="Archivo MP3 de salida")
    args = parser.parse_args()

    tema = " ".join(args.tema)

    try:
        music = JarvisMusic(model=args.model, temperature=args.temperatura)

        clave_genero = resolver_genero(args.genero)
        label = GENEROS.get(clave_genero, {}).get("label", args.genero.upper())

        if args.reproducir:
            music.generar_y_reproducir(
                tema=tema, genero=args.genero,
                contexto=args.contexto, voz=args.voz
            )
        else:
            texto = music.generar(
                tema=tema, genero=args.genero, contexto=args.contexto
            )
            print("\n" + "=" * 65)
            print(f"  JARVIS -- {label} : {tema}")
            print("=" * 65)
            print(texto)
            print("=" * 65 + "\n")

            if args.salida:
                voz = args.voz or GENEROS.get(clave_genero, GENEROS["rap"])["voz_defecto"]
                music.reproducir(texto, voz=voz, archivo_salida=args.salida)

    except (ValueError, RuntimeError) as exc:
        log.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()