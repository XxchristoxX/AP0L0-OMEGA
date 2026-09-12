# src/actions/sports_web.py
"""
Deportes (resultados, clasificaciones, imágenes) para AP0L0
"""

import requests
import json
import os
from src.core.config import _get_config

THESPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/3"


def get_resultats_football(equipe=None, ligue=None):
    try:
        if equipe:
            r = requests.get(f"{THESPORTSDB_BASE}/searchteams.php", params={"t": equipe}, timeout=5)
            data = r.json()
            teams = data.get("teams")
            if not teams:
                return f"No encontré el equipo {equipe}."
            team_id = teams[0]["idTeam"]
            team_name = teams[0]["strTeam"]
            res_last = requests.get(f"{THESPORTSDB_BASE}/eventslast.php", params={"id": team_id}, timeout=5).json()
            res_next = requests.get(f"{THESPORTSDB_BASE}/eventsnext.php", params={"id": team_id}, timeout=5).json()
            matchs_passes = res_last.get("results", [])
            matchs_futurs = res_next.get("events", [])
            reponse = f"Acerca del {team_name}: "
            if matchs_futurs:
                m = matchs_futurs[0]
                reponse += f"Próximo partido el {m.get('dateEvent')} contra {m.get('strOpponent')}. "
            if matchs_passes:
                m = matchs_passes[0]
                reponse += f"Último resultado: {m.get('intHomeScore')} - {m.get('intAwayScore')} vs {m.get('strOpponent')}."
            if not matchs_futurs and not matchs_passes:
                return f"No tengo información reciente para {team_name}."
            return reponse
        else:
            nom_ligue = ligue or "Ligue 1"
            ligue_ids = {
                "ligue 1": "4334", "premier league": "4328", "liga": "4335",
                "bundesliga": "4331", "serie a": "4332", "champions league": "4480"
            }
            ligue_id = ligue_ids.get(nom_ligue.lower(), "4334")
            r = requests.get(f"{THESPORTSDB_BASE}/eventspastleague.php", params={"id": ligue_id}, timeout=5)
            data = r.json()
            matchs = data.get("events", [])
            if not matchs:
                return f"No hay resultados para {nom_ligue}."
            reponse = f"Últimos resultados {nom_ligue}:\n"
            for m in matchs[-6:]:
                reponse += f"{m.get('strHomeTeam')} {m.get('intHomeScore')}-{m.get('intAwayScore')} {m.get('strAwayTeam')} ({m.get('dateEvent')})\n"
            return reponse.strip()
    except Exception as e:
        return f"Error: {e}"


def get_classement_football(ligue=None):
    try:
        nom_ligue = ligue or "Ligue 1"
        ligue_ids = {
            "ligue 1": "4334", "premier league": "4328", "liga": "4335",
            "bundesliga": "4331", "serie a": "4332", "champions league": "4480"
        }
        ligue_id = ligue_ids.get(nom_ligue.lower(), "4334")
        r = requests.get(f"{THESPORTSDB_BASE}/lookuptable.php", params={"l": ligue_id, "s": "2024-2025"}, timeout=8)
        data = r.json()
        tableau = data.get("table", [])
        if not tableau:
            return f"Clasificación {nom_ligue} no disponible."
        reponse = f"Clasificación {nom_ligue}:\n"
        for eq in tableau[:10]:
            reponse += f"{eq.get('intRank')}. {eq.get('strTeam')} - {eq.get('intPoints')} pts ({eq.get('intPlayed')} J)\n"
        return reponse.strip()
    except Exception as e:
        return f"Error: {e}"


# ===== FUNCIÓN EXPORTABLE =====

async def sports_web(params: dict, player=None, speak=None) -> str:
    action = params.get("action", "results")
    equipe = params.get("equipe", "")
    ligue = params.get("ligue", "")
    if action == "results":
        result = get_resultats_football(equipe, ligue)
    elif action == "standings":
        result = get_classement_football(ligue)
    else:
        result = "Acción no soportada."
    if speak:
        speak(result)
    if player:
        player.write_log(f"[Sports] {result}")
    return result