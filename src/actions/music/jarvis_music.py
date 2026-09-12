# jarvis_music.py - MÓDULO DE COMPOSICIÓN MUSICAL PARA AP0L0
# Géneros: rap, chanson, slam, reggae, metal, pop, blues, rock, electro

import os
import sys
import asyncio
import logging
from typing import Optional, Dict, Any

# ===== INTENTAR IMPORTAR GOOGLE GENAI =====
try:
    import google.genai as genai
    from google.genai import types as genai_types
    _GENAI_DISPONIBLE = True
except ImportError:
    _GENAI_DISPONIBLE = False
    genai = None
    genai_types = None
    print("[JarvisMusic] ⚠️ google-genai no instalado. pip install google-genai")

# ===== CONFIGURACIÓN DE AP0L0 =====
try:
    from src.core.config import get_api_key, get_config, BASE_DIR
except ImportError:
    # Fallback para pruebas
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    def get_api_key():
        return os.getenv("GEMINI_API_KEY", "")
    def get_config():
        return {}

# ===== LOGGER =====
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger("JarvisMusic")

# ===== PROMPTS POR GÉNERO (EN ESPAÑOL) =====

GENRES = {
    "rap": {
        "label": "Rap / Hip-Hop",
        "voz_defecto": "es-ES-AlvaroNeural",
        "prompt": (
            "Eres JARVIS, un MC que rapea con flow eléctrico, preciso y vivo.\n"
            "REGLAS: Nunca describas la música. TÚ eres el flow. TÚ eres el rap.\n"
            "Sílabas cortas = velocidad, sílabas largas = énfasis.\n"
            "Marca los beats con '...' o líneas vacías. Onomatopeyas: *tss*, *boom*, *clap*.\n"
            "Estructura: [INTRO] > [VERSO 1] > [ESTRIBILLO] > [VERSO 2] > [ESTRIBILLO] > [OUTRO]\n"
            "Rimas obligatorias AABB o ABAB. Intensidad creciente.\n"
            "8 líneas por verso. 4 líneas de estribillo pegadizo. Español únicamente."
        ),
    },
    "chanson": {
        "label": "Canción",
        "voz_defecto": "es-ES-ElviraNeural",
        "prompt": (
            "Eres JARVIS, compositor de canciones poéticas y emotivas.\n"
            "REGLAS: Tono dulce, melódico, evocador. Cada palabra cuenta.\n"
            "Estructura: [VERSO 1] > [ESTRIBILLO] > [VERSO 2] > [ESTRIBILLO] > [PUENTE] > [ESTRIBILLO FINAL]\n"
            "El estribillo debe ser simple, cantable, memorable.\n"
            "Rimas ricas o suficientes. Versos regulares (8 a 12 sílabas).\n"
            "Lenguaje poético, metáforas, imágenes sensoriales.\n"
            "Emociones: melancolía, nostalgia, amor, esperanza. Español únicamente."
        ),
    },
    "slam": {
        "label": "Slam / Spoken word",
        "voz_defecto": "es-ES-AlvaroNeural",
        "prompt": (
            "Eres JARVIS, slameur comprometido y filósofo.\n"
            "REGLAS: Palabras libres, sin rima estricta, pero con ritmo oral fuerte.\n"
            "Cada frase debe resonar como un golpe o una caricia.\n"
            "Pausas estratégicas marcadas con '...' o '-- ' al inicio de línea.\n"
            "Juega con repeticiones, anáforas, gradaciones.\n"
            "Estructura libre pero legible: estrofas de 4-8 líneas.\n"
            "Temas profundos: sociedad, identidad, tiempo, amor. Español únicamente."
        ),
    },
    "reggae": {
        "label": "Reggae",
        "voz_defecto": "es-ES-AlvaroNeural",
        "prompt": (
            "Eres JARVIS, artista reggae positivo y rítmico.\n"
            "REGLAS: Tono relajado, cálido, optimista o reivindicativo.\n"
            "Ritmo característico: frases cortas, síncopas, acento en el off-beat.\n"
            "Estructura: [INTRO] > [VERSO 1] > [ESTRIBILLO] > [VERSO 2] > [ESTRIBILLO] > [PUENTE] > [ESTRIBILLO]\n"
            "Estribillo repetitivo y pegadizo.\n"
            "Temas: paz, libertad, unidad, amor, resistencia. Español principal."
        ),
    },
    "metal": {
        "label": "Metal",
        "voz_defecto": "es-ES-AlvaroNeural",
        "prompt": (
            "Eres JARVIS, cantante de metal poderoso y visceral.\n"
            "REGLAS: Tono oscuro, intenso, furioso o épico.\n"
            "Ritmo binario potente. Frases cortas y contundentes.\n"
            "Estructura: [INTRO OSCURO] > [VERSO 1] > [ESTRIBILLO DEVASTADOR] > [VERSO 2] > [ESTRIBILLO] > [PUENTE] > [ESTRIBILLO FINAL]\n"
            "Usa MAYÚSCULAS para los pasajes gritados.\n"
            "Imágenes: tormenta, acero, noche, abismo, guerra. Español únicamente."
        ),
    },
    "pop": {
        "label": "Pop",
        "voz_defecto": "es-ES-ElviraNeural",
        "prompt": (
            "Eres JARVIS, compositor pop accesible y pegadizo.\n"
            "REGLAS: Tono luminoso, positivo, universal.\n"
            "Estructura: [VERSO 1] > [PRE-ESTRIBILLO] > [ESTRIBILLO] > [VERSO 2] > [PRE-ESTRIBILLO] > [ESTRIBILLO] > [PUENTE] > [ESTRIBILLO FINAL]\n"
            "Estribillo ultra-pegadizo: simple, repetido.\n"
            "Frases cortas, vocabulario accesible. Español únicamente."
        ),
    },
    "blues": {
        "label": "Blues",
        "voz_defecto": "es-ES-AlvaroNeural",
        "prompt": (
            "Eres JARVIS, cantante de blues auténtico y herido.\n"
            "REGLAS: Tono profundo, lento, habitado por el dolor y la resiliencia.\n"
            "Estructura blues clásica: esquema AAB (repite el primer verso, luego resolución).\n"
            "Cada estrofa: verso A (sufrimiento) + verso A (repetición/variación) + verso B (resolución o ironía).\n"
            "Pausas largas marcadas con '...'\n"
            "Temas: pérdida, soledad, viaje, noche, amor roto. Español únicamente."
        ),
    },
    "rock": {
        "label": "Rock",
        "voz_defecto": "es-ES-AlvaroNeural",
        "prompt": (
            "Eres JARVIS, rockero auténtico entre rebeldía y libertad.\n"
            "REGLAS: Tono rebelde, enérgico, franco.\n"
            "Estructura: [INTRO] > [VERSO 1] > [ESTRIBILLO] > [VERSO 2] > [ESTRIBILLO] > [PUENTE] > [ESTRIBILLO x2]\n"
            "Estribillo potente, fácil de cantar. Rimas directas.\n"
            "Temas: libertad, rebeldía, amor quemado. Español principal."
        ),
    },
    "electro": {
        "label": "Electro / EDM",
        "voz_defecto": "es-ES-ElviraNeural",
        "prompt": (
            "Eres JARVIS, voz de un track electro hipnótico y futurista.\n"
            "REGLAS: Tono minimalista, repetitivo, hipnótico.\n"
            "Estructura: [BUILD UP] > [DROP] > [BREAKDOWN] > [BUILD UP] > [DROP FINAL]\n"
            "El DROP es el momento más intenso: frases ultra-cortas.\n"
            "Repeticiones intencionales (como un loop vocal).\n"
            "Temas: noche, danza, máquina, trance, futuro. Español principal."
        ),
    },
}

# Alias en español
ALIASES = {
    "hip-hop": "rap", "hiphop": "rap",
    "r&b": "rap", "rnb": "rap",
    "chanson": "chanson",
    "spoken word": "slam",
    "hard rock": "metal", "heavy": "metal",
    "dance": "electro", "edm": "electro",
}


def resolver_genero(genero_input: str) -> str:
    """Normaliza el género musical."""
    g = genero_input.strip().lower()
    return ALIASES.get(g, g if g in GENRES else "rap")


# ===== CLASE PRINCIPAL =====

class JarvisMusic:
    """
    Genera letras musicales en cualquier género vía Gemini.
    
    Géneros soportados: rap, chanson, slam, reggae, metal, pop, blues, rock, electro.
    """
    
    DEFAULT_MODEL = "gemini-2.5-flash"
    
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL, temperature: float = 1.0):
        if not _GENAI_DISPONIBLE:
            raise RuntimeError(
                "El paquete google-genai no está instalado.\n"
                "  pip install google-genai"
            )
        
        self.api_key = api_key or get_api_key()
        if not self.api_key:
            raise ValueError(
                "No se encontró GEMINI_API_KEY en la configuración de AP0L0.\n"
                "  Asegúrate de tener la clave en src/config/api_keys.json"
            )
        
        self.model = model
        self.temperature = temperature
        self.client = genai.Client(api_key=self.api_key)
        log.info(f"JarvisMusic inicializado — modelo: {model} | temperatura: {temperature}")
    
    def generos_disponibles(self) -> list:
        """Retorna la lista de géneros soportados."""
        return list(GENRES.keys())
    
    def generar(self, tema: str, genero: str = "rap", contexto: str = "") -> str:
        """
        Genera una letra musical.
        
        Args:
            tema: El tema de la canción.
            genero: El estilo musical (rap, chanson, slam, reggae, metal, pop, blues, rock, electro).
            contexto: Ambiente o contexto adicional.
        
        Returns:
            str: Letras completas formateadas.
        """
        if not tema.strip():
            raise ValueError("El tema no puede estar vacío.")
        
        genero_key = resolver_genero(genero)
        config_genre = GENRES.get(genero_key, GENRES["rap"])
        prompt_system = config_genre["prompt"]
        label = config_genre["label"]
        
        prompt_user = f"Crea una canción de {label} sobre el tema: {tema}"
        if contexto.strip():
            prompt_user += f"\nContexto / ambiente: {contexto}"
        
        log.info(f"Generando: {label} | Tema: {tema}")
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt_user,
                config=genai_types.GenerateContentConfig(
                    system_instruction=prompt_system,
                    temperature=self.temperature,
                    max_output_tokens=2048,
                ),
            )
            texto = response.text.strip() if response and response.text else ""
            if not texto:
                raise RuntimeError("Respuesta vacía de Gemini.")
            log.info(f"Letras generadas: {len(texto)} caracteres")
            return texto
        except Exception as e:
            raise RuntimeError(f"Error generando canción: {e}")
    
    async def _tts_async(self, texto: str, archivo: str, voz: str) -> None:
        """Sintetiza voz con edge-tts."""
        try:
            import edge_tts
        except ImportError:
            log.warning("edge-tts no instalado. pip install edge-tts")
            return
        
        communicate = edge_tts.Communicate(texto, voice=voz, rate="+10%", pitch="-5Hz")
        await communicate.save(archivo)
    
    def leer(self, texto: str, voz: str = "es-ES-AlvaroNeural", archivo_salida: Optional[str] = None) -> Optional[str]:
        """
        Lee las letras en voz alta con edge-tts + pygame.
        
        Args:
            texto: Texto a leer.
            voz: Voz de edge-tts (ej: es-ES-AlvaroNeural, es-ES-ElviraNeural).
            archivo_salida: Ruta del archivo MP3 de salida.
        
        Returns:
            str: Ruta del archivo generado o None si falló.
        """
        if archivo_salida is None:
            import time
            ts = int(time.time() * 1000)
            archivo_salida = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                f"jarvis_music_{ts}.mp3"
            )
        
        try:
            asyncio.run(self._tts_async(texto, archivo_salida, voz))
        except Exception as e:
            log.error(f"Error TTS: {e}")
            return None
        
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(archivo_salida)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            return archivo_salida
        except Exception as e:
            log.warning(f"Error reproduciendo: {e}")
            log.info(f"Audio disponible en: {archivo_salida}")
            return archivo_salida
    
    def generar_y_leer(self, tema: str, genero: str = "rap", contexto: str = "", voz: Optional[str] = None) -> str:
        """
        Genera y lee la canción. Retorna el texto.
        """
        genero_key = resolver_genero(genero)
        voz_auto = voz or GENRES.get(genero_key, GENRES["rap"])["voz_defecto"]
        label = GENRES.get(genero_key, {}).get("label", genero.upper())
        
        texto = self.generar(tema=tema, genero=genero, contexto=contexto)
        print("\n" + "=" * 65)
        print(f"🎵 JARVIS -- {label} : {tema}")
        print("=" * 65)
        print(texto)
        print("=" * 65 + "\n")
        self.leer(texto, voz=voz_auto)
        return texto


# ===== FUNCIÓN PRINCIPAL PARA AP0L0 =====

def compose_music(params: Dict[str, Any], player=None, speak=None) -> str:
    """
    Función de punto de entrada para AP0L0.
    
    Parámetros:
        theme (str): Tema de la canción (obligatorio)
        genre (str): Género (rap, chanson, slam, reggae, metal, pop, blues, rock, electro)
        play (bool): Si debe reproducir la canción (True/False)
    
    Returns:
        str: Mensaje de resultado
    """
    theme = params.get("theme", "").strip()
    genre = params.get("genre", "rap").lower()
    play = params.get("play", False)
    
    if not theme:
        return "❌ Necesito un tema para la canción, señor."
    
    if player:
        player.write_log(f"[Music] Componiendo {genre} sobre: {theme}")
    
    try:
        music = JarvisMusic()
        if play:
            result = music.generar_y_leer(theme, genre)
            return f"🎵 Canción de {genre} compuesta y reproducida."
        else:
            lyrics = music.generar(theme, genre)
            if speak:
                speak(f"He compuesto una canción de {genre} sobre {theme}")
            return f"🎵 Canción de {genre} sobre {theme}:\n\n{lyrics}"
    except Exception as e:
        return f"❌ Error al componer: {e}"


# ===== PRUEBA =====
if __name__ == "__main__":
    print("=== Prueba de JarvisMusic ===")
    music = JarvisMusic()
    resultado = music.generar("la noche estrellada", "slam")
    print(resultado)