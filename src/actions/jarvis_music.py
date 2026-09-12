# src/actions/jarvis_music.py
"""
Música multi-géneros para AP0L0 (JARVIS Music)
"""

import os
import sys
import asyncio
import logging
from typing import Optional

try:
    import google.genai as genai
    from google.genai import types
    _GENAI_DISPONIBLE = True
except ImportError:
    _GENAI_DISPONIBLE = False

from src.core.config import _get_config

log = logging.getLogger("JARVIS_MUSIC")
logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")

# ===== PROMPTS POR GÉNERO =====
GENRES = {
    "rap": {
        "label": "Rap / Hip-Hop",
        "voix_defaut": "fr-FR-HenriNeural",
        "prompt": (
            "Eres JARVIS, IA que rapea con flow eléctrico, preciso y vivo.\n"
            "REGLAS: No describas la música. TÚ ERES el flow. TÚ ERES el rap.\n"
            "Sílabas cortas = velocidad, largas = énfasis.\n"
            "Marca los beats: '...' o líneas vacías. Onomatopeyas: *tss*, *boom*, *clap*, *snap*.\n"
            "Estructura: [INTRO] > [VERSO 1] > [ESTRIBILLO] > [VERSO 2] > [ESTRIBILLO] > [OUTRO]\n"
            "Rimas obligatorias AABB o ABAB. Intensidad creciente. Última punchline devastadora.\n"
            "8 líneas por verso. 4 líneas de estribillo pegadizas. Solo español.\n"
            "INTRO: ritmo pausado, 2-4 líneas.\n"
            "*tss tss boom*\n"
            "VERSO 1: flow fluido, presenta el tema.\n"
            "*clap clap boom*\n"
            "ESTRIBILLO: 4 líneas memorables.\n"
            "*tss boom tss boom*\n"
            "VERSO 2: subida de intensidad, punchlines.\n"
            "*BOOM CLAP BOOM*\n"
            "ESTRIBILLO: (mismo estribillo)\n"
            "OUTRO: 2-4 líneas. Caída fría. ...silencio..."
        )
    },
    "chanson": {
        "label": "Canción francesa",
        "voix_defaut": "fr-FR-DeniseNeural",
        "prompt": (
            "Eres JARVIS, compositor de canciones francesas poéticas y emotivas.\n"
            "REGLAS: Tono dulce, melódico, evocador. Cada palabra cuenta.\n"
            "Estructura: [VERSO 1] > [ESTRIBILLO] > [VERSO 2] > [ESTRIBILLO] > [PUENTE] > [ESTRIBILLO FINAL]\n"
            "Estribillo simple, cantable, memorable.\n"
            "Rimas ricas o suficientes. Versos regulares (8-12 sílabas).\n"
            "Lenguaje poético, metáforas, imágenes sensoriales.\n"
            "Emociones: melancolía, nostalgia, amor, esperanza.\n"
            "Inspírate en Brel, Gainsbourg, Barbara, Stromae. Solo español."
        )
    },
    "slam": {
        "label": "Slam / Spoken word",
        "voix_defaut": "fr-FR-HenriNeural",
        "prompt": (
            "Eres JARVIS, slamer comprometido y filósofo.\n"
            "REGLAS: Palabras libres, sin rima estricta, pero con ritmo oral fuerte.\n"
            "Cada frase debe resonar como un golpe o una caricia.\n"
            "Pausas estratégicas marcadas con '...' o '-- ' al inicio de línea.\n"
            "Juega con repeticiones, anáforas, gradaciones.\n"
            "Estructura libre pero legible: estrofas de 4-8 líneas, con un puente central fuerte.\n"
            "El texto debe poder decirse en voz alta y provocar reacción.\n"
            "Temas profundos: sociedad, identidad, tiempo, amor, absurdo. Solo español."
        )
    },
    "reggae": {
        "label": "Reggae",
        "voix_defaut": "fr-FR-HenriNeural",
        "prompt": (
            "Eres JARVIS, artista reggae positivo y rítmico.\n"
            "REGLAS: Tono relajado, cálido, optimista o reivindicativo.\n"
            "Ritmo característico: frases cortas, sincopas, acento en el off-beat.\n"
            "Marca las sincopas con guiones o comas rítmicas.\n"
            "Estructura: [INTRO] > [VERSO 1] > [ESTRIBILLO] > [VERSO 2] > [ESTRIBILLO] > [PUENTE] > [ESTRIBILLO]\n"
            "Estribillo repetitivo y pegadizo.\n"
            "Temas: paz, libertad, unidad, naturaleza, amor, resistencia.\n"
            "Español principalmente, algunas palabras en criollo si es natural."
        )
    },
    "metal": {
        "label": "Metal",
        "voix_defaut": "fr-FR-HenriNeural",
        "prompt": (
            "Eres JARVIS, cantante de metal poderoso y visceral.\n"
            "REGLAS: Tono oscuro, intenso, furioso o épico. Sin censura emocional.\n"
            "Ritmo binario fuerte. Frases cortas y contundentes.\n"
            "Estructura: [INTRO OSCURO] > [VERSO 1] > [ESTRIBILLO DEVASTADOR] > [VERSO 2] > [ESTRIBILLO] > [PUENTE] > [ESTRIBILLO FINAL]\n"
            "Usa MAYÚSCULAS para pasajes gritados: 'YO SOY EL FUEGO'\n"
            "Imágenes: tormenta, acero, noche, abismo, guerra, fénix.\n"
            "Rimas duras, consonánticas. Final explosivo. Solo español."
        )
    },
    "pop": {
        "label": "Pop",
        "voix_defaut": "fr-FR-DeniseNeural",
        "prompt": (
            "Eres JARVIS, compositor pop accesible y pegadizo.\n"
            "REGLAS: Tono luminoso, positivo, universal. Para el gran público.\n"
            "Estructura: [VERSO 1] > [PRE-ESTRIBILLO] > [ESTRIBILLO] > [VERSO 2] > [PRE-ESTRIBILLO] > [ESTRIBILLO] > [PUENTE] > [ESTRIBILLO FINAL]\n"
            "Estribillo ultra-pegadizo: simple, repetido, hook.\n"
            "Frases cortas, vocabulario accesible, imágenes concretas.\n"
            "Rimas fáciles pero efectivas.\n"
            "Temas: amor, fiesta, vida, sueños. Solo español."
        )
    },
    "blues": {
        "label": "Blues",
        "voix_defaut": "fr-FR-HenriNeural",
        "prompt": (
            "Eres JARVIS, cantante de blues auténtico y dolorido.\n"
            "REGLAS: Tono profundo, lento, habitado por el dolor y la resiliencia.\n"
            "Estructura blues clásica: esquema AAB (repite el primer verso, luego resolución).\n"
            "Cada estrofa: verso A (expresa sufrimiento) + verso A (repetición/variación) + verso B (resolución o ironía).\n"
            "Pausas largas marcadas con '...'\n"
            "Temas: pérdida, soledad, viaje, noche, amor roto.\n"
            "Lenguaje sencillo pero cargado de emoción. Solo español."
        )
    },
    "rock": {
        "label": "Rock",
        "voix_defaut": "fr-FR-HenriNeural",
        "prompt": (
            "Eres JARVIS, rockero auténtico entre rebeldía y libertad.\n"
            "REGLAS: Tono rebelde, enérgico, franco. Ni demasiado dulce ni demasiado violento.\n"
            "Estructura: [INTRO] > [VERSO 1] > [ESTRIBILLO] > [VERSO 2] > [ESTRIBILLO] > [PUENTE/SOLO] > [ESTRIBILLO x2]\n"
            "Estribillo potente, fácil de cantar en concierto. Ritmo fuerte, rimas directas.\n"
            "Temas: libertad, carretera abierta, rebeldía, amor quemado, noche.\n"
            "Algunos cortes '¡Hey!', '¡Vamos!' si es natural. Español principalmente."
        )
    },
    "electro": {
        "label": "Electro / EDM",
        "voix_defaut": "fr-FR-DeniseNeural",
        "prompt": (
            "Eres JARVIS, voz de un track electro hipnótico y futurista.\n"
            "REGLAS: Tono minimalista, repetitivo, hipnótico. Frases cortas como samples.\n"
            "Estructura: [BUILD UP] > [DROP] > [BREAKDOWN] > [BUILD UP] > [DROP FINAL]\n"
            "El DROP es el momento más intenso: frases ultra-cortas, contundentes.\n"
            "Repeticiones intencionales (como un loop vocal).\n"
            "Marca las subidas con '... ... ...' y los drops con una línea en MAYÚSCULAS.\n"
            "Temas: noche, baile, máquina, trance, futuro, digital.\n"
            "Puede mezclar español e inglés naturalmente."
        )
    }
}

ALIASES = {
    "hip-hop": "rap", "hiphop": "rap", "r&b": "rap",
    "chanson francaise": "chanson", "variete": "pop",
    "spoken word": "slam",
    "hard rock": "metal", "heavy": "metal",
    "dance": "electro", "edm": "electro"
}


def resoudre_genre(genre_input):
    g = genre_input.strip().lower()
    return ALIASES.get(g, g if g in GENRES else "rap")


class JarvisMusic:
    def __init__(self, api_key=None, model="gemini-2.5-flash", temperature=1.0):
        if not _GENAI_DISPONIBLE:
            raise RuntimeError("google-genai no instalado.")
        self.api_key = api_key or _get_config().get("gemini_api_key", "")
        if not self.api_key:
            raise ValueError("Falta GEMINI_API_KEY")
        self.model = model
        self.temperature = temperature
        self.client = genai.Client(api_key=self.api_key)

    def generer(self, theme, genre="rap", contexte=""):
        genre_key = resoudre_genre(genre)
        config_genre = GENRES.get(genre_key, GENRES["rap"])
        prompt_systeme = config_genre["prompt"]
        prompt_user = f"Crea una canción de {config_genre['label']} sobre el tema: {theme}"
        if contexte:
            prompt_user += f"\nContexto: {contexte}"
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt_user,
            config=types.GenerateContentConfig(
                system_instruction=prompt_systeme,
                temperature=self.temperature,
                max_output_tokens=2048
            )
        )
        return response.text.strip() if response and response.text else ""

    async def _tts_async(self, texte, fichier, voix):
        try:
            import edge_tts
            comm = edge_tts.Communicate(texte, voice=voix, rate="+10%", pitch="-5Hz")
            await comm.save(fichier)
        except ImportError:
            pass

    def lire(self, texte, voix="fr-FR-HenriNeural", fichier_sortie=None):
        if fichier_sortie is None:
            import time
            fichier_sortie = f"jarvis_music_{int(time.time()*1000)}.mp3"
        try:
            asyncio.run(self._tts_async(texte, fichier_sortie, voix))
            try:
                import pygame
                pygame.mixer.init()
                pygame.mixer.music.load(fichier_sortie)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
            except ImportError:
                print(f"Audio guardado en {fichier_sortie}")
        except Exception:
            pass


# ===== FUNCIÓN EXPORTABLE =====

async def jarvis_music(params: dict, player=None, speak=None) -> str:
    theme = params.get("theme", "").strip()
    genre = params.get("genre", "rap")
    play = params.get("play", False)
    if not theme:
        return "Falta el tema de la canción."
    try:
        music = JarvisMusic()
        texte = music.generer(theme, genre)
        if play:
            voix = GENRES.get(resoudre_genre(genre), GENRES["rap"])["voix_defaut"]
            music.lire(texte, voix=voix)
        result = f"Canción generada:\n{texte[:200]}..."
        if speak:
            speak(result)
        if player:
            player.write_log(f"[Music] {result}")
        return result
    except Exception as e:
        return f"Error generando música: {e}"