# src/core/memory_manager.py
"""
Gestor de memoria persistente para AP0L0
"""

import os
import json
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMOIRE_FILE = os.path.join(BASE_DIR, "data", "jarvis_memoire.json")


def charger_memoire():
    if os.path.exists(MEMOIRE_FILE):
        try:
            with open(MEMOIRE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def sauvegarder_memoire(memoire):
    try:
        os.makedirs(os.path.dirname(MEMOIRE_FILE), exist_ok=True)
        with open(MEMOIRE_FILE, "w", encoding="utf-8") as f:
            json.dump(memoire, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error guardando memoria: {e}")


def ajouter_memoire(cle, valeur):
    memoire = charger_memoire()
    memoire[cle] = {"valeur": valeur, "timestamp": time.strftime("%d/%m/%Y %H:%M")}
    sauvegarder_memoire(memoire)


def supprimer_memoire(cle):
    memoire = charger_memoire()
    if cle in memoire:
        del memoire[cle]
        sauvegarder_memoire(memoire)
        return True
    return False


def construire_contexte_memoire():
    memoire = charger_memoire()
    if not memoire:
        return ""
    lignes = ["MEMORIA PERSISTENTE:"]
    for cle, data in memoire.items():
        lignes.append(f"  - {cle}: {data['valeur']} (desde {data['timestamp']})")
    return "\n".join(lignes)


# ===== FUNCIÓN EXPORTABLE =====

async def memory_operations(params: dict, player=None, speak=None) -> str:
    action = params.get("action", "list")
    if action == "save":
        key = params.get("key", "")
        value = params.get("value", "")
        if not key or not value:
            return "Faltan clave o valor."
        ajouter_memoire(key, value)
        result = f"Memoria guardada: {key} = {value}"
    elif action == "delete":
        key = params.get("key", "")
        if not key:
            return "Falta la clave."
        ok = supprimer_memoire(key)
        result = f"Clave {key} eliminada." if ok else "Clave no encontrada."
    elif action == "list":
        mem = charger_memoire()
        if not mem:
            result = "No hay datos en memoria."
        else:
            result = "Datos en memoria:\n" + "\n".join(f"  {k}: {v['valeur']}" for k, v in mem.items())
    else:
        result = "Acción no soportada."
    if speak:
        speak(result)
    if player:
        player.write_log(f"[Memory] {result}")
    return result