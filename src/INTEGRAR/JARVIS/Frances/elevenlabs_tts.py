# ==============================================================================
#  elevenlabs_tts.py — Module TTS ElevenLabs pour J.A.R.V.I.S
#  Site : www.techenclair.fr
# ==============================================================================
#
#  Ce module gère :
#   - La récupération de la liste des voix disponibles via l'API ElevenLabs
#   - La synthèse vocale (TTS) en MP3 avec le modèle eleven_multilingual_v2
#   - La gestion robuste des erreurs (401 / 429 / quota) avec fallback signal
#
#  Dépendances : elevenlabs>=1.0.0, python-dotenv (déjà présent dans JARVIS)
#
#  Sécurité :
#   - Aucune clé API n'est codée en dur dans ce fichier.
#   - La clé est toujours lue depuis os.environ / .env au moment de l'appel.
# ==============================================================================

import os

# ── Constantes ─────────────────────────────────────────────────────────────────
ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"  # Meilleur modèle pour le français
ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"       # Qualité MP3 standard


def _build_client(api_key: str):
    """
    Instancie le client ElevenLabs avec la clé fournie.
    Retourne None si la clé est vide ou invalide.
    """
    try:
        from elevenlabs import ElevenLabs
        if not api_key or not api_key.strip():
            return None
        # Placeholder guard — on n'accepte jamais les valeurs de template
        _placeholders = {"VOTRE_CLE_ICI", "Votre ID", "votre_id", "VOTRE_TOKEN_ICI", ""}
        if api_key.strip() in _placeholders or "VOTRE" in api_key.upper():
            return None
        return ElevenLabs(api_key=api_key.strip())
    except ImportError:
        print("[ELEVENLABS] Bibliothèque 'elevenlabs' non installée. "
              "Lancez : pip install elevenlabs")
        return None
    except Exception as e:
        print(f"[ELEVENLABS] Erreur instanciation client : {e}")
        return None


def _reload_env_if_needed():
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.exists(env_path):
            load_dotenv(dotenv_path=env_path, override=True)
    except Exception:
        pass


def get_elevenlabs_voices(api_key: str = "") -> list:
    """
    Interroge l'API ElevenLabs pour récupérer la liste complète des voix
    disponibles sur le compte associé à la clé fournie.

    Args:
        api_key: Clé API ElevenLabs. Si vide, tente de lire ELEVENLABS_API_KEY
                 depuis les variables d'environnement.

    Returns:
        Liste de dicts : [{"id": "...", "name": "Marcel", "category": "cloned", ...}]
        Liste vide en cas d'erreur ou de clé invalide.
    """
    _reload_env_if_needed()
    # Résolution de la clé
    key = api_key.strip() if api_key else os.getenv("ELEVENLABS_API_KEY", "").strip()
    eli_client = _build_client(key)

    if eli_client is None:
        print("[ELEVENLABS] Clé API manquante ou invalide — impossible de récupérer les voix.")
        return []

    try:
        response = eli_client.voices.get_all()

        voices_list = []
        # La réponse peut être un objet avec .voices ou une liste directe
        raw_voices = getattr(response, "voices", response)
        if not raw_voices:
            return []

        for voice in raw_voices:
            # Extraction robuste des propriétés selon la version du SDK
            voice_id   = getattr(voice, "voice_id", None) or getattr(voice, "id", None)
            voice_name = getattr(voice, "name", "Voix inconnue")
            category   = getattr(voice, "category", "")

            if not voice_id:
                continue

            # Labels optionnels (langue, genre, etc.)
            labels = {}
            raw_labels = getattr(voice, "labels", {}) or {}
            if isinstance(raw_labels, dict):
                labels = raw_labels

            voices_list.append({
                "id":       voice_id,
                "name":     voice_name,
                "category": category,
                "language": labels.get("language", ""),
                "gender":   labels.get("gender", ""),
                "accent":   labels.get("accent", ""),
            })

        print(f"[ELEVENLABS] {len(voices_list)} voix récupérées avec succès.")
        return voices_list

    except Exception as e:
        err_str = str(e).lower()
        if "401" in err_str or "unauthorized" in err_str or "invalid" in err_str:
            print("[ELEVENLABS] Clé API invalide (401) — vérifiez votre clé dans Paramètres API.")
        elif "429" in err_str or "quota" in err_str or "rate" in err_str:
            print("[ELEVENLABS] Quota ElevenLabs atteint (429) — réessayez plus tard.")
        else:
            print(f"[ELEVENLABS] Erreur récupération des voix : {e}")
        return []


def elevenlabs_tts_to_file(
    texte: str,
    voice_id: str,
    api_key: str = "",
    out_mp3: str = "elevenlabs_tts_temp.mp3"
) -> bool:
    """
    Génère un fichier audio MP3 via ElevenLabs TTS.

    Utilise le modèle eleven_multilingual_v2 pour une prononciation française
    optimale. Gestion robuste des erreurs 401 (clé invalide) et 429 (quota).

    Args:
        texte:    Texte à synthétiser (déjà nettoyé — sans emojis ni markdown).
        voice_id: Identifiant ElevenLabs de la voix (ex: "AZnzlk1XvdvUeBnXmlld").
        api_key:  Clé API. Si vide, lue depuis ELEVENLABS_API_KEY dans os.environ.
        out_mp3:  Chemin de sortie du fichier MP3.

    Returns:
        True si le fichier MP3 a été généré avec succès.
        False en cas d'erreur (l'appelant doit déclencher le fallback Edge TTS).
    """
    # Vérifications préalables
    if not texte or not texte.strip():
        return False

    _reload_env_if_needed()
    key = api_key.strip() if api_key else os.getenv("ELEVENLABS_API_KEY", "").strip()
    eli_client = _build_client(key)

    if eli_client is None:
        print("[ELEVENLABS TTS] Clé API manquante — fallback Edge TTS")
        return False

    if not voice_id or not voice_id.strip():
        print("[ELEVENLABS TTS] Aucun voice_id fourni — fallback Edge TTS")
        return False

    try:
        # Appel TTS — génère un générateur de chunks audio
        audio_generator = eli_client.text_to_speech.convert(
            voice_id=voice_id.strip(),
            text=texte.strip(),
            model_id=ELEVENLABS_MODEL_ID,
            output_format=ELEVENLABS_OUTPUT_FORMAT,
        )

        # Écriture du MP3 sur disque par chunks
        with open(out_mp3, "wb") as f:
            for chunk in audio_generator:
                if chunk:
                    f.write(chunk)

        # Vérification que le fichier n'est pas vide
        if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 0:
            print(f"[ELEVENLABS TTS] [OK] Audio genere : {out_mp3} "
                  f"({os.path.getsize(out_mp3)} octets)")
            return True
        else:
            print("[ELEVENLABS TTS] Fichier genere vide - fallback Edge TTS")
            return False

    except Exception as e:
        err_str = str(e).lower()
        if "401" in err_str or "unauthorized" in err_str or "invalid" in err_str:
            print("[ELEVENLABS TTS] [WARN] Cle API invalide (401) - fallback Edge TTS. "
                  "Verifiez votre cle dans Menu > Parametres API.")
        elif "429" in err_str or "quota" in err_str or "rate" in err_str:
            print("[ELEVENLABS TTS] [WARN] Quota ElevenLabs atteint (429) - "
                  "fallback Edge TTS jusqu'au renouvellement.")
        elif "404" in err_str or "not found" in err_str:
            print(f"[ELEVENLABS TTS] [WARN] Voix introuvable (ID: {voice_id}) - fallback Edge TTS.")
        else:
            print(f"[ELEVENLABS TTS] [ERR] Erreur : {e} - fallback Edge TTS")

        # Nettoyage du fichier partiellement écrit
        try:
            if os.path.exists(out_mp3):
                os.remove(out_mp3)
        except Exception:
            pass

        return False
