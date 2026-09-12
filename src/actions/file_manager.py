# src/actions/file_manager.py
"""
Gestor de archivos y carpetas para AP0L0
Fusionado con la versión de JARVIS
"""

import os
import shutil
import glob
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import time
import ctypes

try:
    user32 = ctypes.windll.user32
    _WINDOWS_API_AVAILABLE = True
except AttributeError:
    user32 = None
    _WINDOWS_API_AVAILABLE = False

# ===== EXTENSIONES =====
EXTENSIONS = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".svg", ".ico"],
    "Videos": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"],
    "Musique": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus"],
    "Documents": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".odt", ".ods", ".odp", ".rtf", ".csv", ".epub"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"],
    "Code": [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".h", ".cs", ".php", ".json", ".xml", ".yaml", ".yml", ".sh", ".bat", ".ps1", ".ts", ".jsx", ".tsx", ".vue", ".go", ".rs", ".rb"],
    "Executables": [".exe", ".msi", ".apk", ".dmg", ".deb"],
}


def resoudre_chemin(chemin):
    """Resuelve atajos como 'bureau', 'documents', etc."""
    if not chemin:
        return None
    chemin = chemin.strip().strip('"').strip("'")
    raccourcis = {
        "bureau": os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        "desktop": os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        "document": os.path.join(os.environ.get("USERPROFILE", ""), "Documents"),
        "documents": os.path.join(os.environ.get("USERPROFILE", ""), "Documents"),
        "téléchargement": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        "téléchargements": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        "telechargement": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        "telechargements": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        "downloads": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        "image": os.path.join(os.environ.get("USERPROFILE", ""), "Pictures"),
        "images": os.path.join(os.environ.get("USERPROFILE", ""), "Pictures"),
        "photo": os.path.join(os.environ.get("USERPROFILE", ""), "Pictures"),
        "photos": os.path.join(os.environ.get("USERPROFILE", ""), "Pictures"),
        "vidéo": os.path.join(os.environ.get("USERPROFILE", ""), "Videos"),
        "vidéos": os.path.join(os.environ.get("USERPROFILE", ""), "Videos"),
        "video": os.path.join(os.environ.get("USERPROFILE", ""), "Videos"),
        "videos": os.path.join(os.environ.get("USERPROFILE", ""), "Videos"),
        "musique": os.path.join(os.environ.get("USERPROFILE", ""), "Music"),
        "music": os.path.join(os.environ.get("USERPROFILE", ""), "Music"),
        "corbeille": "shell:RecycleBinFolder"
    }
    chemin_resolu = raccourcis.get(chemin.lower(), chemin)
    # Fallback con variantes francesas
    if not os.path.exists(chemin_resolu):
        variantes = {
            "Downloads": "Téléchargements",
            "Pictures": "Images",
            "Music": "Musique"
        }
        for eng, fra in variantes.items():
            if eng in chemin_resolu:
                test_fra = chemin_resolu.replace(eng, fra)
                if os.path.exists(test_fra):
                    chemin_resolu = test_fra
                    break
    return chemin_resolu


def trouver_extension(ext):
    for categorie, extensions in EXTENSIONS.items():
        if ext.lower() in extensions:
            return categorie
    return "Autres"


# Variable global para el directorio actual
dossier_courant = None


def ouvrir_dossier(chemin):
    global dossier_courant
    chemin_resolu = resoudre_chemin(chemin)
    if not chemin_resolu or (not os.path.exists(chemin_resolu) and not chemin_resolu.startswith("shell:")):
        return False, f"Dossier introuvable : {chemin_resolu}"
    dossier_courant = chemin_resolu
    if chemin_resolu.startswith("shell:"):
        if os.name != "nt":
            return False, "Los accesos shell solo están disponibles en Windows."
        subprocess.Popen(f'explorer "{chemin_resolu}"', shell=True)
    elif os.name == "nt":
        subprocess.Popen(['explorer', chemin_resolu])
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        try:
            subprocess.Popen([opener, chemin_resolu])
        except OSError:
            return False, "No se encontró un abridor de carpetas del sistema."
    return True, chemin_resolu


def arranger_fenetres_dossiers():
    """Abre y dispone los dossiers Documents, Téléchargements, Images, Vidéos en mosaïque."""
    if not _WINDOWS_API_AVAILABLE:
        return "La organización de ventanas solo está disponible en Windows."
    try:
        import pyautogui
    except ImportError:
        return "pyautogui no instalado."
    dossiers = [
        ("document", 0, 0),
        ("téléchargement", 1, 0),
        ("image", 0, 1),
        ("vidéo", 1, 1)
    ]
    sw, sh = pyautogui.size()
    w, h = sw // 2, (sh - 40) // 2
    for nom, qx, qy in dossiers:
        ouvrir_dossier(nom)
        time.sleep(0.8)
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            x = qx * w
            y = qy * h
            user32.SetWindowPos(hwnd, 0, x, y, w, h, 0x0040)
    return "J'ai ouvert et disposé vos dossiers principaux en mosaïque."


def lister_dossier(chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible or not os.path.exists(cible):
        return None, "Aucun dossier ouvert ou chemin invalide."
    fichiers = []
    dossiers = []
    for item in os.scandir(cible):
        if item.is_file():
            fichiers.append(item.name)
        elif item.is_dir():
            dossiers.append(item.name)
    return {"chemin": cible, "fichiers": fichiers, "dossiers": dossiers}, None


def trier_par_type(chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible or not os.path.exists(cible):
        return False, "Aucun dossier ouvert ou invalide."
    deplacements = 0
    erreurs = 0
    categories = {}
    for item in os.scandir(cible):
        if not item.is_file():
            continue
        ext = Path(item.name).suffix
        categorie = trouver_extension(ext)
        dest_dir = os.path.join(cible, categorie)
        try:
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, item.name)
            if os.path.exists(dest_path):
                base = Path(item.name).stem
                ext2 = Path(item.name).suffix
                dest_path = os.path.join(dest_dir, f"{base}_{int(time.time())}{ext2}")
            shutil.move(item.path, dest_path)
            deplacements += 1
            categories[categorie] = categories.get(categorie, 0) + 1
        except Exception as e:
            print(f"[FICHIER] Error moviendo {item.name}: {e}")
            erreurs += 1
    resume = ", ".join([f"{v} {k}" for k, v in categories.items()])
    return True, f"{deplacements} archivos ordenados: {resume}. {erreurs} errores."


def trier_par_date(chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible or not os.path.exists(cible):
        return False, "Aucun dossier ouvert o invalide."
    deplacements = 0
    erreurs = 0
    for item in os.scandir(cible):
        if not item.is_file():
            continue
        try:
            mtime = item.stat().st_mtime
            date = datetime.fromtimestamp(mtime)
            annee = str(date.year)
            mois = date.strftime("%m - %B")
            dest_dir = os.path.join(cible, annee, mois)
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, item.name)
            if os.path.exists(dest_path):
                base = Path(item.name).stem
                ext2 = Path(item.name).suffix
                dest_path = os.path.join(dest_dir, f"{base}_{int(time.time())}{ext2}")
            shutil.move(item.path, dest_path)
            deplacements += 1
        except Exception as e:
            print(f"[FICHIER] Error moviendo {item.name}: {e}")
            erreurs += 1
    return True, f"{deplacements} archivos ordenados por fecha. {erreurs} errores."


def trier_par_type_puis_date(chemin=None):
    cible = chemin or dossier_courant
    if not cible or not os.path.exists(cible):
        return False, "Aucun dossier ouvert."
    ok1, msg1 = trier_par_type(cible)
    if not ok1:
        return False, msg1
    for item in os.scandir(cible):
        if item.is_dir() and item.name in EXTENSIONS.keys():
            trier_par_date(item.path)
    return True, "Dossier organizado por tipo y luego por fecha en cada categoría."


def creer_sous_dossier(nom, chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible:
        return False, "Aucun dossier ouvert."
    nouveau = os.path.join(cible, nom)
    try:
        os.makedirs(nouveau, exist_ok=True)
        return True, f"Dossier {nom} creado."
    except Exception as e:
        return False, f"Error creando dossier: {e}"


def renommer_fichier(ancien_nom, nouveau_nom, chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible:
        return False, "Aucun dossier ouvert."
    ancien = os.path.join(cible, ancien_nom)
    nouveau = os.path.join(cible, nouveau_nom)
    try:
        os.rename(ancien, nouveau)
        return True, f"Archivo renombrado a {nouveau_nom}."
    except Exception as e:
        return False, f"Error renombrando: {e}"


def deplacer_fichier(nom_fichier, dossier_dest, chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible:
        return False, "Aucun dossier ouvert."
    source = os.path.join(cible, nom_fichier)
    dest = os.path.join(cible, dossier_dest, nom_fichier)
    try:
        os.makedirs(os.path.join(cible, dossier_dest), exist_ok=True)
        shutil.move(source, dest)
        return True, f"{nom_fichier} movido a {dossier_dest}."
    except Exception as e:
        return False, f"Error moviendo: {e}"


def chercher_fichier(nom, chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible:
        return [], "Aucun dossier ouvert."
    resultats = []
    for root, dirs, files in os.walk(cible):
        for f in files:
            if nom.lower() in f.lower():
                resultats.append(os.path.join(root, f))
    return resultats, None


# ===== FUNCIÓN EXPORTABLE PARA AP0L0 =====

async def file_manager(params: dict, player=None, speak=None) -> str:
    """
    Punto de entrada para el gestor de archivos.
    Parámetros:
        action: "open", "list", "sort_type", "sort_date", "sort_full", "create", "rename", "move", "search", "arrange"
        path: ruta (opcional)
        name: nombre (para create/rename)
        destination: destino (para move)
        query: búsqueda (para search)
    """
    action = params.get("action", "list")
    path = params.get("path", "")
    name = params.get("name", "")
    destination = params.get("destination", "")
    query = params.get("query", "")

    if action == "open":
        ok, msg = ouvrir_dossier(path or "bureau")
        if ok:
            result = f"Dossier abierto: {msg}"
        else:
            result = f"Error: {msg}"
    elif action == "list":
        content, err = lister_dossier(path)
        if err:
            result = err
        else:
            result = f"Dossier {content['chemin']}: {len(content['fichiers'])} archivos, {len(content['dossiers'])} subcarpetas."
    elif action == "sort_type":
        ok, msg = trier_par_type(path)
        result = msg if ok else f"Error: {msg}"
    elif action == "sort_date":
        ok, msg = trier_par_date(path)
        result = msg if ok else f"Error: {msg}"
    elif action == "sort_full":
        ok, msg = trier_par_type_puis_date(path)
        result = msg if ok else f"Error: {msg}"
    elif action == "create":
        if not name:
            return "Falta el nombre del dossier."
        ok, msg = creer_sous_dossier(name, path)
        result = msg if ok else f"Error: {msg}"
    elif action == "rename":
        if not name or not path:
            return "Faltan nombre o ruta."
        ok, msg = renommer_fichier(name, destination or name + "_new", path)
        result = msg if ok else f"Error: {msg}"
    elif action == "move":
        if not name or not destination:
            return "Faltan archivo o destino."
        ok, msg = deplacer_fichier(name, destination, path)
        result = msg if ok else f"Error: {msg}"
    elif action == "search":
        if not query:
            return "Falta el término de búsqueda."
        results, err = chercher_fichier(query, path)
        if err:
            result = err
        else:
            result = f"Encontrados {len(results)} archivos: {', '.join(os.path.basename(r) for r in results[:5])}"
    elif action == "arrange":
        result = arranger_fenetres_dossiers()
    else:
        result = f"Acción '{action}' no soportada."

    if speak:
        speak(result)
    if player:
        player.write_log(f"[FileManager] {result}")
    return result
