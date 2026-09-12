# ==========================================
# J.A.R.V.I.S — Module Impression 3D (Image → STL)
# Module autonome et isolé — Aucune dépendance sur le reste de JARVIS
# ==========================================
"""
Pipeline complet : Image → Détourage (rembg) → Inférence 3D (TripoSR) → Réparation → STL watertight

Ce module fonctionne en 100% lazy-loading : aucun import lourd au démarrage.
Les dépendances (torch, rembg, trimesh, etc.) ne sont importées qu'à l'utilisation.
"""

import os
import sys
import json
import time
import subprocess
import threading
import gc
import shutil
import base64
import importlib.util
from datetime import datetime
from pathlib import Path

# ── Chemins de référence ──────────────────────────────────────────────────────
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(_MODULE_DIR, "models", "3d")
OUTPUT_DIR = os.path.join(_MODULE_DIR, "output", "stl")
_TRIPOSR_REPO_DIR = os.path.join(MODELS_DIR, "TripoSR")

# ── Profils matériels ─────────────────────────────────────────────────────────
PROFILE_GPU_OPTIMAL = "GPU_OPTIMAL"     # ≥ 6 Go VRAM
PROFILE_GPU_LIMITED = "GPU_LIMITED"     # < 6 Go VRAM
PROFILE_CPU_ONLY    = "CPU_ONLY"        # Pas de GPU NVIDIA

# ── Packages requis ───────────────────────────────────────────────────────────
REQUIRED_PACKAGES = [
    "torch",
    "torchvision",
    "rembg",
    "onnxruntime",
    "trimesh",
    "einops",
    "transformers",
    "scipy",
    "Pillow",
    "numpy",
    "huggingface_hub",
    "omegaconf",
    "jaxtyping",
    "tqdm",
    "PyMCubes",
]

# ── Verrouillage global ──────────────────────────────────────────────────────
_model_lock = threading.Lock()
_triposr_model = None
_model_last_used = 0.0
_MODEL_UNLOAD_DELAY = 300  # 5 minutes d'inactivité avant déchargement


# ══════════════════════════════════════════════════════════════════════════════
# 1. DIAGNOSTIC MATÉRIEL
# ══════════════════════════════════════════════════════════════════════════════

def check_hardware() -> dict:
    """
    Diagnostique le matériel GPU/CPU de l'utilisateur.
    Retourne un dict JSON-serializable avec le profil détecté.
    Ne nécessite aucune dépendance lourde — torch est importé en try/except.
    """
    result = {
        "cuda_available": False,
        "gpu_name": None,
        "vram_total_gb": 0,
        "vram_free_gb": 0,
        "profile": PROFILE_CPU_ONLY,
        "cpu_name": _get_cpu_name(),
        "ram_total_gb": _get_ram_gb(),
        "message": "",
    }

    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            total_mem_bytes = getattr(props, "total_memory", getattr(props, "total_mem", 0))
            vram_total_gb = round(total_mem_bytes / (1024 ** 3), 1)
            # Mémoire libre
            try:
                vram_free_bytes = torch.cuda.mem_get_info(0)[0]
                vram_free_gb = round(vram_free_bytes / (1024 ** 3), 1)
            except Exception:
                vram_free_gb = vram_total_gb  # Estimation si l'API n'est pas dispo

            result["cuda_available"] = True
            result["gpu_name"] = props.name
            result["vram_total_gb"] = vram_total_gb
            result["vram_free_gb"] = vram_free_gb

            if vram_total_gb >= 6:
                result["profile"] = PROFILE_GPU_OPTIMAL
                result["message"] = f"GPU détecté : {props.name} ({vram_total_gb} Go VRAM) — Accélération GPU complète"
            else:
                result["profile"] = PROFILE_GPU_LIMITED
                result["message"] = f"GPU détecté : {props.name} ({vram_total_gb} Go VRAM) — Mode économie mémoire activé"
        else:
            result["message"] = "Aucun GPU NVIDIA détecté — Mode CPU (génération plus lente : 2 à 5 min)"
    except ImportError:
        result["message"] = "PyTorch non installé — Installation requise pour utiliser ce module"
    except Exception as e:
        result["message"] = f"Erreur détection GPU : {e} — Mode CPU par défaut"

    return result


def _get_cpu_name() -> str:
    """Récupère le nom du processeur (Windows)."""
    try:
        import platform
        return platform.processor() or "CPU inconnu"
    except Exception:
        return "CPU inconnu"


def _get_ram_gb() -> float:
    """Récupère la RAM totale en Go."""
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# 2. VÉRIFICATION DES DÉPENDANCES
# ══════════════════════════════════════════════════════════════════════════════

def check_dependencies() -> dict:
    """
    Vérifie quels packages sont manquants et si le modèle est téléchargé.
    """
    missing = []
    for pkg in REQUIRED_PACKAGES:
        pkg_import = pkg.replace("-", "_").lower()
        # Cas spéciaux de noms d'import
        import_map = {
            "pillow": "PIL",
            "huggingface_hub": "huggingface_hub",
            "jaxtyping": "jaxtyping",
            "pymcubes": "mcubes",
        }
        mod_name = import_map.get(pkg_import, pkg_import)
        # Ne jamais importer les modules lourds ici. En particulier, rembg
        # termine le processus avec SystemExit lorsqu'aucun backend ONNX
        # n'est installé, ce qui coupait le WebSocket et figeait l'UI à 5 %.
        try:
            available = importlib.util.find_spec(mod_name) is not None
        except (ImportError, AttributeError, ValueError):
            available = False
        if not available:
            missing.append(pkg)

    backend_ready = False
    backend_error = ""
    if "rembg" not in missing and "onnxruntime" not in missing:
        backend_ready, backend_error = _probe_rembg_backend()
        if not backend_ready:
            # Force l'affichage du bouton de réparation même si les dossiers
            # des deux packages existent mais que leurs DLL sont incomplètes.
            missing.append("rembg[cpu]")

    # Vérification du modèle TripoSR
    model_ready = _is_model_downloaded()

    return {
        "packages_missing": missing,
        "model_downloaded": model_ready,
        "ready": len(missing) == 0 and model_ready,
        "rembg_backend_ready": backend_ready,
        "rembg_backend_error": backend_error,
        "models_dir": MODELS_DIR,
    }


def _is_model_downloaded() -> bool:
    """Vérifie si les poids du modèle TripoSR sont présents."""
    # On vérifie l'existence du fichier config du modèle OU du dossier complet
    config_path = os.path.join(MODELS_DIR, "config.yaml")
    model_path = os.path.join(MODELS_DIR, "model.ckpt")
    # Alternative : vérifier via le cache huggingface_hub
    hf_marker = os.path.join(MODELS_DIR, ".hf_downloaded")
    return (os.path.exists(config_path) and os.path.exists(model_path)) or os.path.exists(hf_marker)


# ══════════════════════════════════════════════════════════════════════════════
# 3. INSTALLATION AUTOMATIQUE DES DÉPENDANCES
# ══════════════════════════════════════════════════════════════════════════════

def install_dependencies(callback=None):
    """
    Installe tous les packages requis et télécharge le modèle TripoSR.
    callback(progress_pct: int, message: str, done: bool) est appelé pour le suivi.
    Doit être exécuté dans un thread séparé.
    """
    def _cb(pct, msg, done=False, error=False):
        if callback:
            callback(pct, msg, done, error)
        print(f"[PRINT3D] {'[ERREUR] ' if error else ''}{msg} ({pct}%)")

    try:
        _cb(0, "Démarrage de l'installation du module Impression 3D...")

        # ── Étape 1 : Installation de PyTorch (si absent) ─────────────
        try:
            import torch
            _cb(5, f"PyTorch déjà installé (version {torch.__version__})")
        except ImportError:
            _cb(5, "Installation de PyTorch (cette étape peut prendre quelques minutes)...")
            # Installer la version CUDA si un GPU NVIDIA est détecté
            _install_torch(_cb)

        # ── Étape 2 : Installation des packages Python ────────────────
        _cb(30, "Vérification des packages Python complémentaires...")
        packages_to_install = []
        for pkg in REQUIRED_PACKAGES:
            if pkg in ("torch", "torchvision"):
                continue  # Déjà traité
            pkg_import = pkg.replace("-", "_").lower()
            import_map = {"pillow": "PIL", "huggingface_hub": "huggingface_hub", "jaxtyping": "jaxtyping"}
            mod_name = import_map.get(pkg_import, pkg_import)
            try:
                available = importlib.util.find_spec(mod_name) is not None
            except (ImportError, AttributeError, ValueError):
                available = False
            if not available:
                packages_to_install.append(pkg)

        if packages_to_install:
            total = len(packages_to_install)
            for i, pkg in enumerate(packages_to_install):
                pct = 30 + int((i / total) * 30)
                _cb(pct, f"Installation de {pkg} ({i+1}/{total})...")
                _pip_install(pkg)
            _cb(60, f"{total} packages installés avec succès")
        else:
            _cb(60, "Tous les packages Python sont déjà installés")

        # Valider réellement le couple rembg + ONNX dans le même Python que
        # JARVIS. La seule présence du package rembg ne suffit pas.
        _cb(62, "Validation du moteur de détourage ONNX...")
        _validate_rembg_backend()

        # ── Étape 3 : Téléchargement du modèle TripoSR ───────────────
        _cb(65, "Téléchargement du modèle TripoSR (stabilityai/TripoSR)...")
        _download_triposr_model(_cb)

        _cb(100, "Installation terminée avec succès ! Veuillez fermer et relancer JARVIS pour activer le module 3D.", done=True)

    except Exception as e:
        _cb(0, f"Erreur fatale lors de l'installation : {e}", done=True, error=True)


def _install_torch(callback):
    """Installe PyTorch avec CUDA ou CPU selon le matériel disponible."""
    try:
        # Tenter de détecter un GPU NVIDIA via nvidia-smi
        result = subprocess.run(
            ["nvidia-smi"], capture_output=True, text=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        )
        has_nvidia = result.returncode == 0
    except FileNotFoundError:
        has_nvidia = False

    if has_nvidia:
        callback(10, "GPU NVIDIA détecté — Installation de PyTorch avec CUDA...")
        # PyTorch avec CUDA 12.1 (compatibilité large)
        cmd = [
            sys.executable, "-m", "pip", "install", "--upgrade",
            "torch", "torchvision",
            "--index-url", "https://download.pytorch.org/whl/cu121"
        ]
    else:
        callback(10, "Pas de GPU NVIDIA — Installation de PyTorch CPU...")
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "torch", "torchvision"]

    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Échec de l'installation de PyTorch : {proc.stderr[-500:]}")
    callback(25, "PyTorch installé avec succès")


def _pip_install(package_name: str):
    """Installe un package Python via pip."""
    # Gestion spéciale pour trimesh avec les extras
    if package_name == "trimesh":
        package_name = "trimesh[easy]"
    elif package_name == "rembg":
        # L'extra CPU fournit le backend ONNX indispensable et fonctionne
        # aussi sur les PC NVIDIA. Le GPU reste utilisé par TripoSR/PyTorch.
        package_name = "rembg[cpu]"

    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", package_name]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Échec installation {package_name} : {proc.stderr[-500:]}")


def _probe_rembg_backend():
    """Teste rembg dans un sous-processus et retourne (ok, détail)."""
    probe = (
        "import onnxruntime; "
        "from rembg import remove; "
        "print('REMBG_BACKEND_OK')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    )
    if proc.returncode == 0 and "REMBG_BACKEND_OK" in proc.stdout:
        return True, ""
    details = (proc.stderr or proc.stdout or "backend ONNX indisponible")[-500:]
    return False, details


def _validate_rembg_backend():
    """Refuse une fausse installation réussie lorsque le backend est cassé."""
    ok, details = _probe_rembg_backend()
    if not ok:
        raise RuntimeError(
            "Le moteur de détourage rembg/ONNX n'est pas opérationnel. "
            f"Détail : {details}"
        )


def _download_triposr_model(callback):
    """
    Télécharge les poids du modèle TripoSR depuis Hugging Face.
    Utilise huggingface_hub pour un téléchargement fiable avec reprise.
    """
    os.makedirs(MODELS_DIR, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download

        callback(70, "Téléchargement des poids du modèle TripoSR depuis Hugging Face...")

        # Télécharger le snapshot complet du repo dans models/3d/
        snapshot_download(
            repo_id="stabilityai/TripoSR",
            local_dir=MODELS_DIR,
            local_dir_use_symlinks=False,
        )

        # Marqueur de téléchargement réussi
        marker = os.path.join(MODELS_DIR, ".hf_downloaded")
        with open(marker, "w") as f:
            f.write(datetime.now().isoformat())

        callback(95, "Modèle TripoSR téléchargé avec succès")

    except Exception as e:
        callback(70, f"Erreur téléchargement modèle : {e}. Tentative alternative...", error=True)
        # Fallback : cloner le repo git si huggingface_hub échoue
        _clone_triposr_repo(callback)


def _clone_triposr_repo(callback):
    """Fallback : clone le repo TripoSR via git."""
    try:
        if os.path.exists(_TRIPOSR_REPO_DIR):
            shutil.rmtree(_TRIPOSR_REPO_DIR, ignore_errors=True)

        callback(75, "Clonage du dépôt TripoSR via git...")
        cmd = ["git", "clone", "--depth", "1", "https://github.com/VAST-AI-Research/TripoSR.git", _TRIPOSR_REPO_DIR]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git clone échoué : {proc.stderr[-300:]}")

        marker = os.path.join(MODELS_DIR, ".hf_downloaded")
        with open(marker, "w") as f:
            f.write(datetime.now().isoformat())

        callback(90, "Dépôt TripoSR cloné avec succès")
    except Exception as e:
        raise RuntimeError(f"Impossible de télécharger le modèle TripoSR : {e}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. PIPELINE DE GÉNÉRATION STL
# ══════════════════════════════════════════════════════════════════════════════

# Résolutions de marching cubes par qualité
QUALITY_RESOLUTIONS = {
    "fast": 64,
    "standard": 128,
    "high": 256,
}

def generate_stl(image_data_b64: str, quality: str = "standard",
                 optimize_for_print: bool = True, callback=None) -> dict:
    """
    Pipeline complet : Image (base64) → Détourage → Inférence 3D → Réparation → STL.

    Args:
        image_data_b64: Image encodée en base64 (PNG/JPG/WEBP)
        quality: "fast" | "standard" | "high"
        optimize_for_print: Si True, applique la réparation géométrique complète
        callback: callback(step: int, total: int, message: str) pour la progression

    Returns:
        dict avec "success", "file_path", "file_name", "file_size_mb", "is_watertight", "message"
    """
    global _model_last_used

    def _cb(step, total, msg, pct=0):
        if callback:
            callback(step, total, msg, pct)
        print(f"[PRINT3D] [{pct}%] Étape {step}/{total} — {msg}")
        sys.stdout.flush()

    try:
        import torch
        import numpy as np
        from PIL import Image
        import io

        mc_resolution = QUALITY_RESOLUTIONS.get(quality, 128)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float32

        _cb(1, 4, "Suppression de l'arrière-plan...", pct=15)

        # ── Étape 1 : Détourage (rembg) ──────────────────────────────
        image_bytes = base64.b64decode(image_data_b64)
        input_image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

        # Redimensionner si trop grande (limiter la mémoire)
        max_dim = 1024
        if max(input_image.size) > max_dim:
            input_image.thumbnail((max_dim, max_dim), Image.LANCZOS)

        # Suppression de l'arrière-plan
        from rembg import remove as rembg_remove
        processed_image = rembg_remove(input_image)

        # Centrer et recadrer le sujet
        processed_image = _center_and_crop(processed_image)

        _cb(2, 4, "Calcul du volume 3D (inférence IA)...", pct=40)

        # ── Étape 2 : Inférence 3D via TripoSR ───────────────────────
        mesh = _run_triposr_inference(processed_image, device, dtype, mc_resolution)
        _model_last_used = time.time()

        _cb(3, 4, "Réparation géométrique pour l'impression...", pct=75)

        # ── Étape 3 : Réparation géométrique (trimesh) ────────────────
        import trimesh

        if optimize_for_print:
            mesh = _repair_mesh(mesh)

        is_watertight = mesh.is_watertight

        _cb(4, 4, "Finalisation du fichier STL...", pct=95)

        # ── Étape 4 : Export STL ──────────────────────────────────────
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"modele_3d_{timestamp}.stl"
        file_path = os.path.join(OUTPUT_DIR, file_name)

        # Export en STL binaire (plus compact)
        mesh.export(file_path, file_type="stl")

        file_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)

        # ── Nettoyage mémoire ─────────────────────────────────────────
        _cleanup_memory(device)

        return {
            "success": True,
            "file_path": file_path,
            "file_name": file_name,
            "file_size_mb": file_size_mb,
            "is_watertight": is_watertight,
            "quality": quality,
            "device_used": device,
            "message": f"Fichier STL généré avec succès ({file_size_mb} Mo)"
                       + (" — Maillage étanche (OK)" if is_watertight else " — Attention: Maillage non étanche"),
        }

    except torch.cuda.OutOfMemoryError:
        _cleanup_memory("cuda")
        return {
            "success": False,
            "message": "Mémoire GPU insuffisante. Essayez la qualité 'Rapide' ou fermez d'autres applications utilisant le GPU.",
        }
    except Exception as e:
        _cleanup_memory("cuda" if "torch" in dir() and hasattr(torch, 'cuda') else "cpu")
        return {
            "success": False,
            "message": f"Erreur lors de la génération : {str(e)}",
        }


# ══════════════════════════════════════════════════════════════════════════════
# 4b. PIPELINE DE GÉNÉRATION DE LITHOPHANIE 3D (Photo → Relief Lumineux)
# ══════════════════════════════════════════════════════════════════════════════

def generate_lithophane(
    image_data_b64: str,
    shape: str = "flat",              # "flat" | "curved"
    width_mm: float = 120.0,
    min_thickness_mm: float = 0.8,
    max_thickness_mm: float = 3.0,
    has_frame: bool = True,
    has_base: bool = True,
    callback=None
) -> dict:
    """
    Génère une Lithophanie 3D étanche à partir d'une photo encodée en base64.

    Args:
        image_data_b64: Image encodée en base64 (PNG/JPG/WEBP)
        shape: "flat" (Plaque classique) | "curved" (Arc de cercle)
        width_mm: Largeur physique en mm (ex: 120mm)
        min_thickness_mm: Épaisseur minimale pour le blanc (ex: 0.8mm)
        max_thickness_mm: Épaisseur maximale pour le noir (ex: 3.0mm)
        has_frame: Bordure solide autour de la photo
        has_base: Socle d'exposition intégré à la base pour tenir debout
        callback: callback(step, total, message, progress) pour le suivi UI

    Returns:
        dict avec "success", "file_path", "file_name", "file_size_mb", "is_watertight", "message"
    """
    def _cb(step, total, msg, pct=0):
        if callback:
            callback(step, total, msg, pct)
        print(f"[LITHOPHANE] [{pct}%] Étape {step}/{total} — {msg}")
        sys.stdout.flush()

    try:
        import numpy as np
        from PIL import Image, ImageOps, ImageFilter
        import trimesh
        import io

        _cb(1, 4, "Lecture et traitement de l'image...", pct=15)

        # 1. Charger l'image et la convertir en niveaux de gris
        image_bytes = base64.b64decode(image_data_b64)
        img = Image.open(io.BytesIO(image_bytes)).convert("L")

        # Rehausser légèrement le contraste pour un rendu optimal
        img = ImageOps.autocontrast(img, cutoff=1)

        # Résolution de la grille (max 380px sur la largeur pour un maillage net et ultra rapide)
        max_res_w = 380
        w_px, h_px = img.size
        aspect = h_px / max(w_px, 1)
        res_w = min(max_res_w, max(w_px, 80))
        res_h = max(20, int(res_w * aspect))

        img_resized = img.resize((res_w, res_h), Image.LANCZOS)
        # Léger flou pour lisser les micro-artefacts
        img_resized = img_resized.filter(ImageFilter.GaussianBlur(radius=0.4))

        arr = np.array(img_resized, dtype=np.float32) / 255.0

        _cb(2, 4, "Calcul du relief et des épaisseurs...", pct=40)

        # Inversion : Sombre (0.0) -> max_thickness, Clair (1.0) -> min_thickness
        thickness_map = min_thickness_mm + (1.0 - arr) * (max_thickness_mm - min_thickness_mm)

        # Cadre solide autour si demandé
        if has_frame:
            frame_px = max(2, int(res_w * 0.03))  # ~3% de bordure
            thickness_map[:frame_px, :] = max_thickness_mm + 0.4
            thickness_map[-frame_px:, :] = max_thickness_mm + 0.4
            thickness_map[:, :frame_px] = max_thickness_mm + 0.4
            thickness_map[:, -frame_px:] = max_thickness_mm + 0.4

        height_mm = width_mm * aspect

        # Coordonnées X, Y
        x_lin = np.linspace(-width_mm / 2.0, width_mm / 2.0, res_w, dtype=np.float32)
        y_lin = np.linspace(height_mm / 2.0, -height_mm / 2.0, res_h, dtype=np.float32)
        X, Y = np.meshgrid(x_lin, y_lin)

        _cb(3, 4, "Génération du maillage 3D étanche...", pct=70)

        # Calcul des sommets avant et arrière
        if shape == "curved":
            # Arc de cercle (courbure 60 degrés = pi / 3 radians)
            arc_rad = np.pi / 3.0
            radius = width_mm / arc_rad
            theta = X / radius

            # Surface arrière (courbe)
            x_back = radius * np.sin(theta)
            z_back = radius * (1.0 - np.cos(theta))
            y_back = Y

            # Surface avant (courbe + relief normal)
            nx = np.sin(theta)
            nz = np.cos(theta)
            x_front = x_back + nx * thickness_map
            y_front = y_back
            z_front = z_back + nz * thickness_map
        else:
            # Plat
            x_back = X
            y_back = Y
            z_back = np.zeros_like(X)

            x_front = X
            y_front = Y
            z_front = thickness_map

        # Aplatir les grilles de sommets
        front_verts = np.stack([x_front, y_front, z_front], axis=-1).reshape(-1, 3)
        back_verts = np.stack([x_back, y_back, z_back], axis=-1).reshape(-1, 3)

        num_verts_side = res_h * res_w
        all_verts = np.vstack([front_verts, back_verts])

        # Indices de grille
        r, c = np.meshgrid(np.arange(res_h - 1), np.arange(res_w - 1), indexing="ij")
        r = r.flatten()
        c = c.flatten()

        v0 = r * res_w + c
        v1 = (r + 1) * res_w + c
        v2 = r * res_w + (c + 1)
        v3 = (r + 1) * res_w + (c + 1)

        # Faces avant (normale vers +Z)
        front_faces_1 = np.stack([v0, v1, v2], axis=-1)
        front_faces_2 = np.stack([v1, v3, v2], axis=-1)

        # Faces arrière (normale vers -Z)
        b0 = v0 + num_verts_side
        b1 = v1 + num_verts_side
        b2 = v2 + num_verts_side
        b3 = v3 + num_verts_side

        back_faces_1 = np.stack([b0, b2, b1], axis=-1)
        back_faces_2 = np.stack([b1, b2, b3], axis=-1)

        faces_list = [front_faces_1, front_faces_2, back_faces_1, back_faces_2]

        # Parois latérales (Top, Bottom, Left, Right)
        # Top (row 0)
        c_top = np.arange(res_w - 1)
        f_top1 = c_top
        f_top2 = c_top + 1
        b_top1 = f_top1 + num_verts_side
        b_top2 = f_top2 + num_verts_side
        top_faces_1 = np.stack([f_top1, b_top1, f_top2], axis=-1)
        top_faces_2 = np.stack([f_top2, b_top1, b_top2], axis=-1)
        faces_list.extend([top_faces_1, top_faces_2])

        # Bottom (row res_h - 1)
        c_bot = np.arange(res_w - 1)
        f_bot1 = (res_h - 1) * res_w + c_bot
        f_bot2 = (res_h - 1) * res_w + c_bot + 1
        b_bot1 = f_bot1 + num_verts_side
        b_bot2 = f_bot2 + num_verts_side
        bot_faces_1 = np.stack([f_bot1, f_bot2, b_bot1], axis=-1)
        bot_faces_2 = np.stack([f_bot2, b_bot2, b_bot1], axis=-1)
        faces_list.extend([bot_faces_1, bot_faces_2])

        # Left (col 0)
        r_side = np.arange(res_h - 1)
        f_left1 = r_side * res_w
        f_left2 = (r_side + 1) * res_w
        b_left1 = f_left1 + num_verts_side
        b_left2 = f_left2 + num_verts_side
        left_faces_1 = np.stack([f_left1, b_left1, f_left2], axis=-1)
        left_faces_2 = np.stack([f_left2, b_left1, b_left2], axis=-1)
        faces_list.extend([left_faces_1, left_faces_2])

        # Right (col res_w - 1)
        f_right1 = r_side * res_w + (res_w - 1)
        f_right2 = (r_side + 1) * res_w + (res_w - 1)
        b_right1 = f_right1 + num_verts_side
        b_right2 = f_right2 + num_verts_side
        right_faces_1 = np.stack([f_right1, f_right2, b_right1], axis=-1)
        right_faces_2 = np.stack([f_right2, b_right2, b_right1], axis=-1)
        faces_list.extend([right_faces_1, right_faces_2])

        all_faces = np.vstack(faces_list)
        mesh = trimesh.Trimesh(vertices=all_verts, faces=all_faces)

        # Socle d'exposition à la base si demandé (sur plaque plate)
        if has_base and shape == "flat":
            base_w = width_mm + 10.0
            base_d = 18.0
            base_h = 4.0
            base_box = trimesh.creation.box(extents=[base_w, base_h, base_d])
            base_box.apply_translation([0, -height_mm / 2.0 - base_h / 2.0 + 0.5, max_thickness_mm / 2.0])
            mesh = trimesh.util.concatenate([mesh, base_box])

        # Réparation et validation géométrique
        mesh = _repair_mesh(mesh)
        is_watertight = mesh.is_watertight

        _cb(4, 4, "Export du fichier STL...", pct=95)

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shape_suffix = "courbee" if shape == "curved" else "plate"
        file_name = f"lithophanie_{shape_suffix}_{timestamp}.stl"
        file_path = os.path.join(OUTPUT_DIR, file_name)

        mesh.export(file_path, file_type="stl")
        file_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)

        _cb(4, 4, "Lithophanie générée avec succès !", pct=100)

        return {
            "success": True,
            "file_path": file_path,
            "file_name": file_name,
            "file_size_mb": file_size_mb,
            "is_watertight": is_watertight,
            "mode": "lithophane",
            "shape": shape,
            "message": f"Lithophanie 3D générée avec succès ({file_size_mb} Mo)"
                       + (" — Maillage étanche (OK)" if is_watertight else ""),
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Erreur lors de la génération de la lithophanie : {str(e)}",
        }


def _center_and_crop(image):
    """Centre le sujet (alpha > 0) et le recadre avec une marge."""
    from PIL import Image
    import numpy as np

    arr = np.array(image)
    if arr.shape[2] < 4:
        return image

    alpha = arr[:, :, 3]
    rows = np.any(alpha > 20, axis=1)
    cols = np.any(alpha > 20, axis=0)

    if not rows.any() or not cols.any():
        return image

    y_min, y_max = np.where(rows)[0][[0, -1]]
    x_min, x_max = np.where(cols)[0][[0, -1]]

    # Ajouter une marge de 10%
    h, w = y_max - y_min, x_max - x_min
    margin = int(max(h, w) * 0.1)
    y_min = max(0, y_min - margin)
    y_max = min(arr.shape[0], y_max + margin)
    x_min = max(0, x_min - margin)
    x_max = min(arr.shape[1], x_max + margin)

    cropped = image.crop((x_min, y_min, x_max, y_max))

    # Rendre carré avec fond transparent
    size = max(cropped.size)
    square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset = ((size - cropped.width) // 2, (size - cropped.height) // 2)
    square.paste(cropped, offset)

    # Redimensionner en 512×512 (taille d'entrée TripoSR)
    return square.resize((512, 512), Image.LANCZOS)


def _run_triposr_inference(image, device, dtype, mc_resolution):
    """
    Exécute l'inférence TripoSR et retourne un objet trimesh.Trimesh.
    Charge le modèle de façon lazy et le garde en cache.
    """
    global _triposr_model, _model_last_used
    import torch
    import trimesh
    import numpy as np
    from PIL import Image as PILImage

    with _model_lock:
        if _triposr_model is None:
            print("[PRINT3D] Chargement du modèle TripoSR...")
            _triposr_model = _load_triposr_model(device, dtype)
            print("[PRINT3D] Modèle TripoSR chargé avec succès")

    model = _triposr_model

    # Convertir RGBA en RGB avec fond neutre gris 0.5 (format optimal attendu par TripoSR)
    if image.mode == "RGBA":
        arr = np.array(image).astype(np.float32) / 255.0
        alpha = arr[:, :, 3:4]
        rgb = arr[:, :, :3] * alpha + (1.0 - alpha) * 0.5
        image_rgb = PILImage.fromarray((rgb * 255.0).astype(np.uint8))
    else:
        image_rgb = image.convert("RGB")

    # Exécution de l'inférence (en float32 standard comme TripoSR)
    with torch.no_grad():
        scene_codes = model([image_rgb], device=device)

    # Extraction du mesh via marching cubes
    try:
        meshes = model.extract_mesh(scene_codes, has_vertex_color=False, resolution=mc_resolution)
    except TypeError:
        meshes = model.extract_mesh(scene_codes, resolution=mc_resolution)

    if not meshes or len(meshes) == 0:
        raise RuntimeError("Le modèle n'a pas pu générer de mesh 3D à partir de cette image")

    mesh_data = meshes[0]

    # Convertir en trimesh.Trimesh
    if isinstance(mesh_data, trimesh.Trimesh):
        return mesh_data

    # Si c'est un tuple (vertices, faces) ou un objet custom
    if hasattr(mesh_data, 'vertices') and hasattr(mesh_data, 'faces'):
        vertices = mesh_data.vertices
        faces = mesh_data.faces
        if isinstance(vertices, torch.Tensor):
            vertices = vertices.cpu().numpy()
        if isinstance(faces, torch.Tensor):
            faces = faces.cpu().numpy()
        return trimesh.Trimesh(vertices=vertices, faces=faces)

    raise RuntimeError("Format de mesh non reconnu en sortie du modèle")


def _load_triposr_model(device, dtype):
    """
    Charge le modèle TripoSR. Tente plusieurs méthodes :
    1. Via le package tsr (si installé ou cloné dans models/3d/)
    2. Via huggingface_hub + code local
    """
    import torch
    import sys

    # S'assurer que les dossiers contenant tsr sont dans sys.path
    triposr_paths = [
        MODELS_DIR,
        _TRIPOSR_REPO_DIR,
        os.path.join(MODELS_DIR, "TripoSR"),
    ]

    for path in triposr_paths:
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)

    # Si le repo TripoSR n'est pas encore présent, le cloner
    if not os.path.exists(_TRIPOSR_REPO_DIR):
        try:
            _clone_triposr_repo(lambda *args, **kwargs: None)
            if _TRIPOSR_REPO_DIR not in sys.path:
                sys.path.insert(0, _TRIPOSR_REPO_DIR)
        except Exception:
            pass

    try:
        from tsr.system import TSR

        # Charger depuis le dossier local s'il contient config.yaml
        local_target = MODELS_DIR if os.path.exists(os.path.join(MODELS_DIR, "config.yaml")) else "stabilityai/TripoSR"
        model = TSR.from_pretrained(
            local_target,
            config_name="config.yaml",
            weight_name="model.ckpt",
        )
        model.renderer.set_chunk_size(8192)
        model.to(device)
        return model

    except ImportError:
        pass

    # Méthode 2 : Télécharger et charger directement via huggingface_hub
    try:
        from huggingface_hub import snapshot_download

        local_path = snapshot_download(
            repo_id="stabilityai/TripoSR",
            local_dir=MODELS_DIR,
            local_dir_use_symlinks=False,
        )

        if local_path not in sys.path:
            sys.path.insert(0, local_path)
        if MODELS_DIR not in sys.path:
            sys.path.insert(0, MODELS_DIR)

        from tsr.system import TSR

        model = TSR.from_pretrained(
            MODELS_DIR,
            config_name="config.yaml",
            weight_name="model.ckpt",
        )
        model.renderer.set_chunk_size(8192)
        model.to(device)

        marker = os.path.join(MODELS_DIR, ".hf_downloaded")
        with open(marker, "w") as f:
            f.write(datetime.now().isoformat())

        return model

    except Exception as e:
        raise RuntimeError(
            f"Impossible de charger le modèle TripoSR. "
            f"Vérifiez que l'installation est complète. Erreur : {e}"
        )


def _repair_mesh(mesh):
    """
    Répare le maillage pour l'impression 3D :
    - Suppression des sommets dupliqués et orphelins
    - Correction des normales
    - Fermeture des trous
    - Vérification de l'étanchéité
    """
    import trimesh
    import numpy as np

    # 1. Fusionner les sommets proches (dupliqués)
    mesh.merge_vertices()

    # 2. Supprimer les faces dégénérées (aire nulle) et dupliquées
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.update_faces(mesh.unique_faces())

    # 3. Supprimer les sommets orphelins (non référencés par des faces)
    mesh.remove_unreferenced_vertices()

    # 4. Corriger l'orientation des normales (toutes vers l'extérieur)
    trimesh.repair.fix_normals(mesh)

    # 5. Corriger l'enroulement des faces (winding order)
    trimesh.repair.fix_winding(mesh)

    # 6. Remplir les trous pour obtenir un maillage étanche
    trimesh.repair.fill_holes(mesh)

    # 7. Si toujours pas watertight, tenter de rendre le maillage convexe
    if not mesh.is_watertight:
        try:
            # Seconde passe de réparation
            trimesh.repair.fill_holes(mesh)
            trimesh.repair.fix_normals(mesh)
        except Exception:
            pass  # Le mesh est réparé au mieux

    # 8. Centrer le modèle à l'origine et normaliser la taille
    mesh.rezero()  # Déplacer le barycentre à l'origine
    # Normaliser pour que le modèle fasse ~100mm (taille impression standard)
    extents = mesh.extents
    if extents.max() > 0:
        scale_factor = 100.0 / extents.max()
        mesh.apply_scale(scale_factor)

    return mesh


# ══════════════════════════════════════════════════════════════════════════════
# 5. GESTION MÉMOIRE & UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def _cleanup_memory(device="cpu"):
    """Libère la mémoire GPU/CPU après une génération."""
    try:
        gc.collect()
        if device == "cuda":
            import torch
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass


def unload_model():
    """Décharge explicitement le modèle de la mémoire."""
    global _triposr_model
    with _model_lock:
        if _triposr_model is not None:
            print("[PRINT3D] Déchargement du modèle TripoSR...")
            del _triposr_model
            _triposr_model = None
            _cleanup_memory("cuda")
            print("[PRINT3D] Modèle déchargé — mémoire libérée")


def _auto_unload_daemon():
    """
    Thread daemon qui décharge automatiquement le modèle
    si inactif depuis plus de _MODEL_UNLOAD_DELAY secondes.
    """
    global _triposr_model, _model_last_used
    while True:
        time.sleep(60)  # Vérifier toutes les minutes
        if _triposr_model is not None and _model_last_used > 0:
            elapsed = time.time() - _model_last_used
            if elapsed > _MODEL_UNLOAD_DELAY:
                unload_model()


# Lancer le daemon de déchargement automatique
_unload_thread = threading.Thread(target=_auto_unload_daemon, daemon=True)
_unload_thread.start()


def get_stl_file_b64(file_path: str) -> str:
    """Lit un fichier STL et le retourne encodé en base64."""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def open_output_folder():
    """Ouvre le dossier de sortie STL dans l'explorateur de fichiers."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(OUTPUT_DIR)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", OUTPUT_DIR])
    else:
        subprocess.Popen(["xdg-open", OUTPUT_DIR])
