# src/actions/jarvis_rap.py
"""
Generador de rap para AP0L0
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

log = logging.getLogger("JARVIS_RAP")
logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT_RAP = """
Eres JARVIS, IA que rapea con flow eléctrico, preciso y vivo.
REGLAS ABSOLUTAS:
- No describas la música. TÚ ERES el flow. TÚ ERES el rap.
- Adopta un ritmo natural: sílabas cortas = velocidad, largas = énfasis.
- Marca los beats con pausas visuales: "..." o "—" o líneas vacías.
- Usa onomatopeyas de percusión cuando cuadre: *tss*, *boom*, *clap*, *snap*.
- Estructura: [INTRO] → [VERSO] × 2 → [ESTRIBILLO] × 2 → [OUTRO]
- Rima obligatoria: al menos AABB o ABAB por estrofa.
- Intensidad creciente: comienza calmado, sube en el segundo verso.
- Termina con una caída fuerte, la última punchline que golpea.
- Solo español, argot y juegos de palabras bienvenidos.
ESTRUCTURA A RESPETAR:
[INTRO]  2-4 líneas de gancho, ritmo pausado.
*tss tss boom*
[VERSO 1]  8 líneas, flow fluido, presenta el tema.
*clap — clap — boom*
[ESTRIBILLO]  4 líneas pegadizas, repetidas dos veces.
*tss boom tss boom*
[VERSO 2]  8 líneas, subida de intensidad, punchlines.
*BOOM — CLAP — BOOM*
[ESTRIBILLO] (mismo estribillo)
[OUTRO]  2-4 líneas, caída fría, punchline devastadora.
...silencio...
"""


class JarvisRap:
    def __init__(self, api_key=None, model="gemini-2.5-flash", temperature=1.0):
        if not _GENAI_DISPONIBLE:
            raise RuntimeError("google-genai no instalado.")
        self.api_key = api_key or _get_config().get("gemini_api_key", "")
        if not self.api_key:
            raise ValueError("Falta GEMINI_API_KEY")
        self.model = model
        self.temperature = temperature
        self.client = genai.Client(api_key=self.api_key)

    def generer(self, theme, contexte=""):
        prompt_user = f"Crée un rap complet sur le thème : « {theme} »"
        if contexte:
            prompt_user += f"\nContexte / ambiance : {contexte}"
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt_user,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT_RAP,
                temperature=self.temperature,
                max_output_tokens=2048
            )
        )
        return response.text.strip() if response and response.text else ""

    async def _tts_async(self, texte, fichier, voix):
        try:
            import edge_tts
            comm = edge_tts.Communicate(texte, voice=voix, rate="+15%", pitch="-5Hz")
            await comm.save(fichier)
        except ImportError:
            pass

    def lire_rap(self, texte, voix="fr-FR-HenriNeural", fichier_sortie=None):
        if fichier_sortie is None:
            import time
            fichier_sortie = f"jarvis_rap_{int(time.time()*1000)}.mp3"
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

async def jarvis_rap(params: dict, player=None, speak=None) -> str:
    theme = params.get("theme", "").strip()
    play = params.get("play", False)
    if not theme:
        return "Falta el tema del rap."
    try:
        rap = JarvisRap()
        texte = rap.generer(theme)
        if play:
            rap.lire_rap(texte)
        result = f"Rap generado:\n{texte[:200]}..."
        if speak:
            speak(result)
        if player:
            player.write_log(f"[Rap] {result}")
        return result
    except Exception as e:
        return f"Error generando rap: {e}"