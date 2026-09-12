"""Bibliothèque de jeux locale JARVIS (Steam, Epic, GOG et dossiers manuels)."""

import json
import os
import re
import string
import subprocess
import unicodedata
import winreg
import base64
import io
import time
from functools import lru_cache


APP_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.dirname(os.path.abspath(__file__))), "Jarvis")
CONFIG_FILE = os.path.join(APP_DIR, "games_library.json")
IGNORED_EXE = {
    "setup", "install", "installer", "unins000", "uninstall", "crashreporter",
    "unitycrashhandler64", "unitycrashhandler32", "vc_redist.x64", "vc_redist.x86",
    "dxsetup", "launcherhelper", "eac_launcher", "easyanticheat_eos_setup"
}
IGNORED_STEAM_APPS = {"228980"}  # Steamworks Common Redistributables
SYSTEM_FOLDERS = {
    "$recycle.bin", "system volume information", "windows", "users", "programdata",
    "program files", "program files (x86)", "recovery", "perflogs", "msocache"
}
NON_GAME_FOLDERS = {"jarvis", "hoptodesk", "obsidian", "docker", "python", "nodejs", "yuzu-windows-msvc", "yuzu"}
GAME_ASSET_EXTENSIONS = {".pak", ".forge", ".utoc", ".ucas", ".vpk", ".big", ".bundle", ".rpf"}


def _load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"folders": [], "custom_games": [], "hidden_ids": [], "cached_catalog": [], "last_scan": 0}


def _save_config(data):
    os.makedirs(APP_DIR, exist_ok=True)
    temporary = CONFIG_FILE + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, CONFIG_FILE)


def get_folders():
    return [path for path in _load_config().get("folders", []) if os.path.isdir(path)]


def add_folder(path):
    path = os.path.abspath(os.path.expandvars(path or "")).rstrip("\\/")
    if not os.path.isdir(path):
        return False
    config = _load_config()
    folders = config.setdefault("folders", [])
    if path.casefold() not in {item.casefold() for item in folders}:
        folders.append(path)
        _save_config(config)
    return True


def remove_folder(path):
    config = _load_config()
    original = config.get("folders", [])
    config["folders"] = [item for item in original if item.casefold() != (path or "").casefold()]
    _save_config(config)
    return len(original) != len(config["folders"])


def hide_game(game_id):
    config = _load_config()
    hidden = config.setdefault("hidden_ids", [])
    if game_id and game_id not in hidden:
        hidden.append(game_id)
        _save_config(config)
    return True


def restore_hidden_games():
    config = _load_config()
    config["hidden_ids"] = []
    _save_config(config)


def get_cached_games():
    """Retourne immédiatement la dernière bibliothèque connue, sans rescanner le PC."""
    config = _load_config()
    catalog = config.get("cached_catalog", [])
    if not isinstance(catalog, list):
        catalog = []
    hidden = set(config.get("hidden_ids", []))
    return [game for game in catalog if isinstance(game, dict) and game.get("id") not in hidden]


def has_cached_catalog():
    return isinstance(_load_config().get("cached_catalog"), list) and bool(_load_config().get("cached_catalog"))


def add_custom_game(executable, name="", cover_path=""):
    executable = os.path.abspath(executable or "")
    if not os.path.isfile(executable):
        return False
    config = _load_config()
    custom = config.setdefault("custom_games", [])
    item = {
        "name": (name or os.path.splitext(os.path.basename(executable))[0]).strip(),
        "executable": executable,
        "cover_path": cover_path if os.path.isfile(cover_path or "") else ""
    }
    custom = [old for old in custom if old.get("executable", "").casefold() != executable.casefold()]
    custom.append(item)
    config["custom_games"] = custom
    _save_config(config)
    return True


def _normalise(value):
    value = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in value if not unicodedata.combining(char)).casefold().strip()


def _game(name, platform, launch, install_path="", app_id="", cover_url=""):
    return {
        "id": f"{platform}:{app_id or _normalise(name)}",
        "name": name.strip(),
        "platform": platform,
        "launch": launch,
        "install_path": install_path,
        "app_id": str(app_id or ""),
        "cover_url": cover_url,
        "cover_data": _local_cover(install_path, launch) if install_path else "",
    }


def _steam_roots():
    roots = set()
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for key_name in (r"Software\Valve\Steam", r"Software\WOW6432Node\Valve\Steam"):
            try:
                with winreg.OpenKey(hive, key_name) as key:
                    for value_name in ("SteamPath", "InstallPath"):
                        try:
                            roots.add(winreg.QueryValueEx(key, value_name)[0].replace("/", "\\"))
                        except OSError:
                            pass
            except OSError:
                pass
    for drive in _existing_drives():
        roots.update((f"{drive}\\Steam", f"{drive}\\SteamLibrary", f"{drive}\\Program Files (x86)\\Steam"))
    return [root for root in roots if os.path.isdir(root)]


def _steam_games():
    games = []
    libraries = set()
    for steam_root in _steam_roots():
        libraries.add(steam_root)
        vdf = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
        try:
            text = open(vdf, "r", encoding="utf-8", errors="ignore").read()
            libraries.update(match.replace("\\\\", "\\") for match in re.findall(r'"path"\s+"([^"]+)"', text))
        except OSError:
            pass
    for library in libraries:
        manifests = os.path.join(library, "steamapps")
        if not os.path.isdir(manifests):
            continue
        for filename in os.listdir(manifests):
            if not filename.startswith("appmanifest_") or not filename.endswith(".acf"):
                continue
            try:
                text = open(os.path.join(manifests, filename), "r", encoding="utf-8", errors="ignore").read()
                app_id = re.search(r'"appid"\s+"(\d+)"', text)
                name = re.search(r'"name"\s+"([^"]+)"', text)
                install = re.search(r'"installdir"\s+"([^"]+)"', text)
                if app_id and name:
                    if app_id.group(1) in IGNORED_STEAM_APPS or "redistributable" in name.group(1).casefold():
                        continue
                    install_path = os.path.join(manifests, "common", install.group(1)) if install else ""
                    games.append(_game(name.group(1), "Steam", f"steam://rungameid/{app_id.group(1)}",
                                       install_path, app_id.group(1),
                                       f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id.group(1)}/header.jpg"))
            except OSError:
                pass
    return games


def _epic_games():
    games = []
    manifest_dir = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
                                "Epic", "EpicGamesLauncher", "Data", "Manifests")
    if not os.path.isdir(manifest_dir):
        return games
    for filename in os.listdir(manifest_dir):
        if not filename.endswith(".item"):
            continue
        try:
            with open(os.path.join(manifest_dir, filename), "r", encoding="utf-8-sig") as handle:
                item = json.load(handle)
            name = item.get("DisplayName")
            root = item.get("InstallLocation", "")
            executable = os.path.join(root, item.get("LaunchExecutable", ""))
            if name and os.path.isfile(executable):
                games.append(_game(name, "Epic Games", executable, root, item.get("CatalogItemId", "")))
        except Exception:
            pass
    return games


def _gog_games():
    games = []
    key_roots = (
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    )
    for hive, key_name in key_roots:
        try:
            with winreg.OpenKey(hive, key_name) as root:
                for index in range(winreg.QueryInfoKey(root)[0]):
                    try:
                        sub_name = winreg.EnumKey(root, index)
                        if "gog.com" not in sub_name.casefold():
                            continue
                        with winreg.OpenKey(root, sub_name) as sub:
                            name = winreg.QueryValueEx(sub, "DisplayName")[0]
                            location = winreg.QueryValueEx(sub, "InstallLocation")[0]
                        executable = _best_executable(location)
                        if executable:
                            games.append(_game(name, "GOG", executable, location, sub_name))
                    except OSError:
                        pass
        except OSError:
            pass
    return games


def _ubisoft_games():
    games = []
    keys = []
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            keys.append((hive, r"Software\Ubisoft\Launcher\Installs", view))
        keys.append((hive, r"Software\WOW6432Node\Ubisoft\Launcher\Installs", winreg.KEY_WOW64_64KEY))
    for hive, key_name, view in keys:
        try:
            with winreg.OpenKey(hive, key_name, 0, winreg.KEY_READ | view) as root:
                for index in range(winreg.QueryInfoKey(root)[0]):
                    try:
                        app_id = winreg.EnumKey(root, index)
                        with winreg.OpenKey(root, app_id) as sub:
                            install_dir = winreg.QueryValueEx(sub, "InstallDir")[0].replace("/", "\\").rstrip("\\")
                            try: display_name = winreg.QueryValueEx(sub, "DisplayName")[0]
                            except OSError: display_name = ""
                        if os.path.isdir(install_dir):
                            name = display_name or os.path.basename(install_dir)
                            game = _game(name, "Ubisoft Connect", f"uplay://launch/{app_id}/0", install_dir, app_id)
                            if not game["cover_data"]:
                                executable = _best_executable(install_dir, max_depth=5)
                                game["cover_data"] = _local_cover(install_dir, executable)
                            games.append(game)
                    except OSError:
                        pass
        except OSError:
            pass
    return games


def _existing_drives():
    return [f"{letter}:" for letter in string.ascii_uppercase if os.path.exists(f"{letter}:\\")]


def _best_executable(folder, max_depth=2):
    if not folder or not os.path.isdir(folder):
        return ""
    candidates = []
    base_depth = folder.rstrip("\\/").count(os.sep)
    try:
        for current, directories, files in os.walk(folder):
            depth = current.rstrip("\\/").count(os.sep) - base_depth
            directories[:] = [] if depth >= max_depth else [d for d in directories if d.casefold() not in {"redist", "redistributables", "support", "installer", "engine"}]
            for filename in files:
                if not filename.casefold().endswith(".exe"):
                    continue
                stem = os.path.splitext(filename)[0].casefold()
                if stem not in IGNORED_EXE and not any(word in stem for word in ("unins", "crash", "setup", "report")):
                    candidates.append(os.path.join(current, filename))
    except OSError:
        pass
    if not candidates:
        return ""
    folder_name = os.path.basename(folder).replace(" ", "").casefold()
    return min(candidates, key=lambda path: (folder_name not in os.path.basename(path).replace(" ", "").casefold(), path.count(os.sep), len(path)))


def _game_signature(folder):
    """Score prudent : évite de transformer chaque logiciel portable en jeu."""
    if os.path.basename(folder).casefold() in NON_GAME_FOLDERS:
        return 0
    score = 0
    largest_exe = 0
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return 0
    names = {entry.name.casefold() for entry in entries}
    if any(name in names for name in ("steam_api.dll", "steam_api64.dll", "goggame.info", "goggame-*.ico")):
        score += 4
    if any(name in names for name in ("easyanticheat", "eaanticheat", "__installer", "binaries", "engine", "data", "content", "videos")):
        score += 1
    if "engine" in names and any(name.endswith("game") for name in names):
        score += 3
    for entry in entries:
        if not entry.is_file():
            continue
        extension = os.path.splitext(entry.name)[1].casefold()
        if extension in GAME_ASSET_EXTENSIONS:
            score += 2
        if extension == ".exe":
            try: largest_exe = max(largest_exe, entry.stat().st_size)
            except OSError: pass
    if largest_exe >= 20 * 1024 * 1024:
        score += 2
    elif largest_exe >= 8 * 1024 * 1024:
        score += 1
    if any(name.endswith((".py", ".sln", ".csproj")) for name in names) or "venv" in names or "node_modules" in names:
        score -= 4
    return score


@lru_cache(maxsize=512)
def _cover_from_file(image_path):
    try:
        if not os.path.isfile(image_path) or os.path.getsize(image_path) > 12 * 1024 * 1024:
            return ""
        from PIL import Image, ImageOps
        with Image.open(image_path) as source:
            source.seek(0)
            source = source.convert("RGB")
            canvas = Image.new("RGB", (460, 215), (5, 22, 34))
            fitted = ImageOps.fit(source, (460, 215), method=Image.Resampling.LANCZOS)
            canvas.paste(fitted, (0, 0))
            buffer = io.BytesIO()
            canvas.save(buffer, format="JPEG", quality=84, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return ""


@lru_cache(maxsize=512)
def _local_cover(folder, executable=""):
    """Fabrique une petite jaquette intégrée depuis les images/ICO déjà présents."""
    if not folder or not os.path.isdir(folder):
        return ""
    ranked = []
    base_depth = folder.rstrip("\\/").count(os.sep)
    try:
        for current, directories, files in os.walk(folder):
            depth = current.rstrip("\\/").count(os.sep) - base_depth
            directories[:] = [] if depth >= 6 else directories[:40]
            for filename in files:
                extension = os.path.splitext(filename)[1].casefold()
                if extension not in {".jpg", ".jpeg", ".png", ".webp", ".ico"}:
                    continue
                lower = filename.casefold()
                if any(bad in lower for bad in ("installer", "uninstall", "crash", "logo-small")):
                    continue
                priority = next((index for index, word in enumerate(("cover", "header", "capsule", "keyart", "poster", "background", "splash", "icon")) if word in lower), 20)
                ranked.append((priority, depth, os.path.join(current, filename)))
    except OSError:
        pass
    # L'icône portant le nom de l'exécutable est préférable à une image sans rapport.
    exe_stem = os.path.splitext(os.path.basename(executable))[0].casefold()
    ranked.sort(key=lambda item: (0 if exe_stem and exe_stem in os.path.basename(item[2]).casefold() else 1, item[0], item[1]))
    for _, _, image_path in ranked[:12]:
        try:
            if os.path.getsize(image_path) > 12 * 1024 * 1024:
                continue
            from PIL import Image, ImageOps
            with Image.open(image_path) as source:
                source.seek(0)
                source = source.convert("RGB")
                canvas = Image.new("RGB", (460, 215), (5, 22, 34))
                fitted = ImageOps.contain(source, (460, 215))
                canvas.paste(fitted, ((460 - fitted.width) // 2, (215 - fitted.height) // 2))
                buffer = io.BytesIO()
                canvas.save(buffer, format="JPEG", quality=82, optimize=True)
            return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        except Exception:
            continue
    # Dernier recours : extraire l'icône Windows du véritable exécutable du jeu.
    if executable and os.path.isfile(executable):
        try:
            encoded_path = base64.b64encode(executable.encode("utf-8")).decode("ascii")
            ps_script = (
                "Add-Type -AssemblyName System.Drawing;"
                f"$p=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded_path}'));"
                "$i=[Drawing.Icon]::ExtractAssociatedIcon($p);"
                "if($i){$m=New-Object IO.MemoryStream;$i.ToBitmap().Save($m,[Drawing.Imaging.ImageFormat]::Png);"
                "[Convert]::ToBase64String($m.ToArray())}"
            )
            encoded_script = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
            result = subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", encoded_script],
                                    capture_output=True, text=True, timeout=8)
            icon_b64 = result.stdout.strip()
            if icon_b64:
                from PIL import Image, ImageOps
                with Image.open(io.BytesIO(base64.b64decode(icon_b64))) as icon:
                    icon = icon.convert("RGBA")
                    icon.thumbnail((150, 150))
                    canvas = Image.new("RGB", (460, 215), (5, 22, 34))
                    canvas.paste(icon, ((460 - icon.width) // 2, (215 - icon.height) // 2), icon)
                    buffer = io.BytesIO()
                    canvas.save(buffer, format="JPEG", quality=84)
                return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        except Exception:
            pass
    return ""


def _drive_root_games():
    """Cherche les jeux autonomes placés directement sur les disques du PC."""
    games = []
    for drive in _existing_drives():
        root = drive + os.sep
        try:
            entries = [entry for entry in os.scandir(root) if entry.is_dir() and entry.name.casefold() not in SYSTEM_FOLDERS]
        except OSError:
            continue
        for entry in entries[:400]:
            # Bibliothèques de ROM déjà présentes : lancement via l'association Windows.
            if any(word in entry.name.casefold() for word in ("jeux", "games", "roms")):
                try:
                    for rom in os.scandir(entry.path):
                        if rom.is_file() and os.path.splitext(rom.name)[1].casefold() in {".xci", ".nsp", ".rom", ".3ds"}:
                            title = re.sub(r"\s*\[[^\]]+\].*$", "", os.path.splitext(rom.name)[0]).strip()
                            games.append(_game(title, "Nintendo / Émulateur", rom.path, entry.path, rom.path))
                except OSError:
                    pass
            if _game_signature(entry.path) < 3:
                continue
            executable = _best_executable(entry.path, max_depth=5)
            if executable:
                launch = executable
                if entry.name.casefold() == "fortnite":
                    launch = "com.epicgames.launcher://apps/Fortnite?action=launch&silent=true"
                games.append(_game(entry.name, "Jeu PC détecté", launch, entry.path))
    return games


def _xbox_games():
    games = []
    for drive in _existing_drives():
        root = os.path.join(drive + os.sep, "XboxGames")
        if not os.path.isdir(root):
            continue
        try:
            entries = [entry for entry in os.scandir(root) if entry.is_dir()]
        except OSError:
            continue
        for entry in entries:
            content = os.path.join(entry.path, "Content")
            executable = _best_executable(content if os.path.isdir(content) else entry.path)
            if executable:
                games.append(_game(entry.name, "Xbox", executable, entry.path))
    return games


def _manual_games():
    games = []
    for library in get_folders():
        base_depth = library.rstrip("\\/").count(os.sep)
        visited = 0
        try:
            for current, directories, _ in os.walk(library):
                visited += 1
                if visited > 12000:
                    print(f"[JEUX] Limite de sécurité atteinte pendant l'analyse de {library}")
                    break
                depth = current.rstrip("\\/").count(os.sep) - base_depth
                directories[:] = [name for name in directories if name.casefold() not in {
                    "$recycle.bin", "system volume information", "windows", "users", "programdata",
                    "winsxs", "windowsapps", "node_modules", "venv", "__pycache__", "support",
                    "redist", "redistributables", "logs", "temp", "download", "matchreplay"
                }]
                if depth >= 7:
                    directories[:] = []
                # Les launchers installés dans Program Files sont déjà lus via leurs registres/manifeste.
                if depth == 0 and os.path.splitdrive(library)[1] in ("", "\\"):
                    directories[:] = [name for name in directories if name.casefold() not in SYSTEM_FOLDERS]
                current_name = os.path.basename(current.rstrip("\\/")).casefold()
                if current_name == "ubisoft game launcher":
                    directories[:] = [name for name in directories if name.casefold() == "games"]
                if _game_signature(current) < 3:
                    continue
                executable = _best_executable(current, max_depth=3)
                if not executable:
                    continue
                name = os.path.basename(current.rstrip("\\/"))
                launch = executable
                platform = "Dossier personnel"
                if "ubisoft" in current.casefold() and "rainbow" in name.casefold():
                    launch, platform = "uplay://launch/635/0", "Ubisoft Connect"
                games.append(_game(name, platform, launch, current))
                directories[:] = []
        except OSError:
            continue
    return games


def _custom_games():
    games = []
    for item in _load_config().get("custom_games", []):
        executable = item.get("executable", "")
        if not os.path.isfile(executable):
            continue
        game = _game(item.get("name") or os.path.splitext(os.path.basename(executable))[0],
                     "Ajout manuel", executable, os.path.dirname(executable), executable)
        cover_path = item.get("cover_path", "")
        if cover_path:
            custom_cover = _cover_from_file(cover_path)
            if custom_cover:
                game["cover_data"] = custom_cover
        games.append(game)
    return games


def scan_games():
    games = (_custom_games() + _steam_games() + _epic_games() + _gog_games() + _ubisoft_games()
             + _xbox_games() + _drive_root_games() + _manual_games())
    unique = {}
    for game in games:
        key = _normalise(game["name"])
        unique.setdefault(key, game)
    catalog = sorted(unique.values(), key=lambda game: _normalise(game["name"]))
    config = _load_config()
    config["cached_catalog"] = catalog
    config["last_scan"] = time.time()
    _save_config(config)
    hidden = set(config.get("hidden_ids", []))
    return [game for game in catalog if game["id"] not in hidden]


def launch_game(identifier):
    wanted = _normalise(identifier)
    games = get_cached_games() or scan_games()
    exact = [game for game in games if wanted in {_normalise(game["id"]), _normalise(game["name"])}]
    partial = [game for game in games if wanted and wanted in _normalise(game["name"])]
    matches = exact or partial
    if not matches:
        return {"success": False, "error": f"Je ne trouve pas le jeu {identifier} dans votre bibliothèque."}
    game = min(matches, key=lambda item: len(item["name"]))
    try:
        launch = game["launch"]
        if re.match(r"^[a-z][a-z0-9+.-]*://", launch, flags=re.IGNORECASE) or not launch.casefold().endswith(".exe"):
            os.startfile(launch)
        else:
            try:
                subprocess.Popen([launch], cwd=os.path.dirname(launch), creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            except OSError as exc:
                if getattr(exc, "winerror", None) != 740:
                    raise
                # Le jeu exige les droits administrateur : Windows affiche alors l'UAC officiel.
                import ctypes
                result = ctypes.windll.shell32.ShellExecuteW(None, "runas", launch, None, os.path.dirname(launch), 1)
                if result <= 32:
                    raise OSError(f"Windows n'a pas autorisé l'élévation (code {result}).")
        return {"success": True, "game": game}
    except Exception as exc:
        return {"success": False, "error": str(exc), "game": game}


def launch_from_voice(text):
    """Lance un jeu connu sans détourner les commandes destinées aux autres applications."""
    normalised = _normalise(text)
    prefixes = ("lance le jeu ", "ouvre le jeu ", "demarre le jeu ", "joue au jeu ",
                "lance ", "ouvre ", "demarre ", "joue a ")
    query = next((normalised[len(prefix):].strip() for prefix in prefixes if normalised.startswith(prefix)), "")
    if not query:
        return None
    known = get_cached_games() or scan_games()
    matches = [game for game in known if _normalise(game["name"]) == query]
    if not matches and "jeu " in normalised:
        matches = [game for game in known if query in _normalise(game["name"])]
    if not matches:
        return None
    return launch_game(matches[0]["id"])
