#!/usr/bin/env python3
"""Installer pubblico one-file per la traduzione italiana di ARK: Survival Ascended."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


APP_ID = "2399830"
GAME_FOLDER_NAME = "ARK Survival Ascended"
GAME_EXES = ("ArkAscended.exe", "ArkAscended_BE.exe")
BASE_PAK = "pakchunk0-Windows.pak"
USER_WORK_DIR = Path(os.environ.get("ARK_IT_WORK_DIR", Path.home() / "Documents" / "ARKItalianTranslation"))
UPDATE_APPLY_COMMAND = "_apply-update"
UPDATE_COMPLETE_COMMAND = "_update-complete"
UPDATE_SCHEDULED = 20

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parents[1]
    BUNDLE_DIR = APP_DIR

DATA_DIR = BUNDLE_DIR / "data"
PAYLOAD_DIR = BUNDLE_DIR / "payload"


class ConsoleColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"


@dataclass(frozen=True)
class GameLocation:
    game_dir: Path
    paks_dir: Path
    manifest: Path | None
    build_id: str | None
    source: str


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def release_manifest() -> dict:
    return read_json(DATA_DIR / "release_manifest.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def parse_acf(text: str) -> dict[str, str]:
    return {
        key.lower(): value
        for key, value in re.findall(r'^\s*"([^"]+)"\s+"([^"]*)"\s*$', text, re.MULTILINE)
    }


def read_app_manifest(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return parse_acf(path.read_text(encoding="utf-8-sig", errors="replace"))


def parse_library_paths(text: str) -> list[Path]:
    found: list[Path] = []
    for raw in re.findall(r'"path"\s+"((?:\\.|[^"\\])*)"', text):
        value = raw.replace("\\\\", "\\").strip()
        if value:
            found.append(Path(value))
    return found


def registry_steam_roots() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []
    roots: list[Path] = []
    keys = (
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Valve\Steam", ("SteamPath", "InstallPath")),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", ("InstallPath", "SteamPath")),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", ("InstallPath", "SteamPath")),
    )
    for hive, subkey, names in keys:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                for name in names:
                    try:
                        value, _ = winreg.QueryValueEx(key, name)
                    except OSError:
                        continue
                    if value:
                        roots.append(Path(os.path.expandvars(str(value))))
        except OSError:
            continue
    return unique_paths(roots)


def windows_drive_roots() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        return [Path(f"{chr(65 + index)}:\\") for index in range(26) if mask & (1 << index)]
    except Exception:
        return [Path(f"{letter}:\\") for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ"]


def unique_paths(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        try:
            marker = str(path.expanduser().resolve()).casefold()
        except OSError:
            marker = str(path).casefold()
        if marker not in seen:
            seen.add(marker)
            result.append(path)
    return result


def steam_libraries() -> list[Path]:
    roots = registry_steam_roots()
    program_files = os.environ.get("ProgramFiles(x86)")
    if program_files:
        roots.append(Path(program_files) / "Steam")
    roots.extend(Path(root) / "Steam" for root in windows_drive_roots())
    roots = unique_paths(roots)

    libraries: list[Path] = []
    for steam in roots:
        if not steam.is_dir():
            continue
        libraries.append(steam)
        vdf = steam / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            libraries.extend(parse_library_paths(vdf.read_text(encoding="utf-8", errors="ignore")))
    return unique_paths(libraries)


def paks_dir_for(game_dir: Path) -> Path:
    return game_dir / "ShooterGame" / "Content" / "Paks"


def looks_like_game_dir(path: Path) -> bool:
    paks = paks_dir_for(path)
    binaries = path / "ShooterGame" / "Binaries" / "Win64"
    return (paks / BASE_PAK).is_file() and any((binaries / name).is_file() for name in GAME_EXES)


def normalize_game_dir(path: Path) -> Path | None:
    path = path.expanduser()
    candidates = [
        path,
        path / GAME_FOLDER_NAME,
        path / "steamapps" / "common" / GAME_FOLDER_NAME,
        path / "common" / GAME_FOLDER_NAME,
    ]
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
        except OSError:
            continue
        if looks_like_game_dir(candidate):
            return candidate
    return None


def manifest_for_game_dir(game_dir: Path) -> Path | None:
    common = game_dir.parent
    manifest = common.parent / f"appmanifest_{APP_ID}.acf"
    return manifest if manifest.is_file() else None


def location_from_dir(game_dir: Path, source: str, manifest: Path | None = None) -> GameLocation:
    manifest = manifest or manifest_for_game_dir(game_dir)
    info = read_app_manifest(manifest) if manifest else {}
    return GameLocation(
        game_dir=game_dir.resolve(),
        paks_dir=paks_dir_for(game_dir).resolve(),
        manifest=manifest.resolve() if manifest else None,
        build_id=info.get("buildid"),
        source=source,
    )


def load_settings() -> dict:
    path = USER_WORK_DIR / "settings.json"
    if not path.is_file():
        return {}
    try:
        value = read_json(path)
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_game_dir(game_dir: Path) -> None:
    write_json(USER_WORK_DIR / "settings.json", {"game_dir": str(game_dir.resolve())})


def manifest_locations() -> list[GameLocation]:
    locations: list[GameLocation] = []
    for library in steam_libraries():
        manifest = library / "steamapps" / f"appmanifest_{APP_ID}.acf"
        info = read_app_manifest(manifest)
        if info.get("appid") != APP_ID:
            continue
        install_dir = info.get("installdir") or GAME_FOLDER_NAME
        game_dir = normalize_game_dir(library / "steamapps" / "common" / install_dir)
        if game_dir:
            locations.append(location_from_dir(game_dir, "manifest Steam", manifest))
    return locations


def fallback_candidates() -> list[Path]:
    values: list[Path] = []
    env = os.environ.get("ARK_SA_GAME_DIR")
    if env:
        values.append(Path(env))
    values.extend([APP_DIR, APP_DIR.parent, Path.cwd(), Path.cwd().parent])
    for library in steam_libraries():
        values.append(library / "steamapps" / "common" / GAME_FOLDER_NAME)
    for drive in windows_drive_roots():
        values.extend(
            [
                drive / "SteamLibrary" / "steamapps" / "common" / GAME_FOLDER_NAME,
                drive / "Steam" / "steamapps" / "common" / GAME_FOLDER_NAME,
                drive / "Games" / "Steam" / "steamapps" / "common" / GAME_FOLDER_NAME,
            ]
        )
    return unique_paths(values)


def resolve_game_location(raw: str | None = None) -> GameLocation:
    if raw:
        game_dir = normalize_game_dir(Path(raw.strip().strip('"')))
        if not game_dir:
            raise FileNotFoundError("La cartella scelta non contiene un'installazione valida di ARK: Survival Ascended.")
        return location_from_dir(game_dir, "manuale")

    saved = str(load_settings().get("game_dir") or "").strip()
    if saved:
        game_dir = normalize_game_dir(Path(saved))
        if game_dir:
            return location_from_dir(game_dir, "percorso salvato")

    detected = manifest_locations()
    if detected:
        return detected[0]
    for candidate in fallback_candidates():
        game_dir = normalize_game_dir(candidate)
        if game_dir:
            return location_from_dir(game_dir, "ricerca automatica")
    raise FileNotFoundError("ARK: Survival Ascended non è stato trovato automaticamente.")


def choose_game_dir_windows() -> str | None:
    if os.name != "nt":
        return None
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$d=New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$d.Description='Seleziona la cartella ARK Survival Ascended'; "
        "$d.ShowNewFolderButton=$false; "
        "if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){$d.SelectedPath}"
    )
    try:
        return subprocess.check_output(
            ["powershell", "-NoProfile", "-STA", "-Command", script],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def configure_game_dir() -> GameLocation | None:
    print("Seleziona la cartella che contiene ShooterGame.")
    print(r"Esempio: D:\SteamLibrary\steamapps\common\ARK Survival Ascended")
    raw = choose_game_dir_windows()
    if not raw:
        raw = input("Incolla il percorso, oppure premi Invio per annullare: ").strip().strip('"')
    if not raw:
        return None
    try:
        location = resolve_game_location(raw)
    except FileNotFoundError as exc:
        print(exc)
        return None
    save_game_dir(location.game_dir)
    print("Percorso verificato e salvato:", location.game_dir)
    return location


def payload_path(manifest: dict | None = None) -> Path:
    manifest = manifest or release_manifest()
    return PAYLOAD_DIR / str(manifest["payload_file"])


def installed_patch_path(location: GameLocation, manifest: dict | None = None) -> Path:
    manifest = manifest or release_manifest()
    return location.paks_dir / str(manifest["installed_file"])


def payload_is_valid(manifest: dict | None = None) -> bool:
    manifest = manifest or release_manifest()
    source = payload_path(manifest)
    return source.is_file() and sha256_file(source) == str(manifest["payload_sha256"]).upper()


def installation_status(location: GameLocation, manifest: dict | None = None) -> dict:
    manifest = manifest or release_manifest()
    target = installed_patch_path(location, manifest)
    if not target.is_file():
        return {"installed": False, "current": False, "hash": None}
    digest = sha256_file(target)
    return {
        "installed": True,
        "current": digest == str(manifest["payload_sha256"]).upper(),
        "hash": digest,
    }


def supported_build(location: GameLocation, manifest: dict | None = None) -> bool:
    manifest = manifest or release_manifest()
    supported = {str(item) for item in manifest.get("supported_builds", [])}
    return location.build_id is not None and location.build_id in supported


def process_running() -> list[str]:
    if os.name != "nt":
        return []
    try:
        output = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            text=True,
            errors="ignore",
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    lowered = output.casefold()
    return [name for name in GAME_EXES if f'"{name.casefold()}"' in lowered]


def timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def backup_current_patch(location: GameLocation, manifest: dict | None = None) -> Path:
    manifest = manifest or release_manifest()
    target = installed_patch_path(location, manifest)
    backup = USER_WORK_DIR / "backups" / timestamp()
    backup.mkdir(parents=True, exist_ok=False)
    existed = target.is_file()
    if existed:
        shutil.copy2(target, backup / target.name)
    write_json(
        backup / "backup_manifest.json",
        {
            "game_dir": str(location.game_dir),
            "target": str(target),
            "target_existed": existed,
            "translation_version": manifest["translation_version"],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    return backup


def install_translation(location: GameLocation, force: bool = False) -> Path:
    manifest = release_manifest()
    running = process_running()
    if running:
        raise RuntimeError("Chiudi prima ARK: " + ", ".join(running))
    if not payload_is_valid(manifest):
        raise RuntimeError("Il pacchetto incorporato è assente o non supera il controllo SHA-256.")
    if not supported_build(location, manifest) and not force:
        detected = location.build_id or "sconosciuta"
        raise RuntimeError(
            f"Build del gioco non verificata ({detected}). Scarica un installer aggiornato oppure usa --force."
        )
    location.paks_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_current_patch(location, manifest)
    source = payload_path(manifest)
    target = installed_patch_path(location, manifest)
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        shutil.copy2(source, temporary)
        if sha256_file(temporary) != str(manifest["payload_sha256"]).upper():
            raise RuntimeError("La copia della patch non supera il controllo SHA-256.")
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    write_json(
        USER_WORK_DIR / "installed_state.json",
        {
            "game_dir": str(location.game_dir),
            "patch": str(target),
            "backup": str(backup),
            "translation_version": manifest["translation_version"],
            "payload_sha256": manifest["payload_sha256"],
            "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    return backup


def latest_backup_for(location: GameLocation) -> Path | None:
    root = USER_WORK_DIR / "backups"
    if not root.is_dir():
        return None
    for backup in sorted((path for path in root.iterdir() if path.is_dir()), reverse=True):
        info_path = backup / "backup_manifest.json"
        if not info_path.is_file():
            continue
        try:
            info = read_json(info_path)
            if Path(str(info.get("game_dir", ""))).resolve() == location.game_dir.resolve():
                return backup
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return None


def restore_translation(location: GameLocation) -> Path:
    running = process_running()
    if running:
        raise RuntimeError("Chiudi prima ARK: " + ", ".join(running))
    backup = latest_backup_for(location)
    if not backup:
        raise FileNotFoundError("Nessun backup disponibile per questa installazione di ARK.")
    info = read_json(backup / "backup_manifest.json")
    target = installed_patch_path(location)
    previous = backup / target.name
    if info.get("target_existed"):
        if not previous.is_file():
            raise FileNotFoundError("Il backup della patch precedente è incompleto.")
        temporary = target.with_suffix(target.suffix + ".restore")
        shutil.copy2(previous, temporary)
        os.replace(temporary, target)
    elif target.is_file():
        target.unlink()
    state = USER_WORK_DIR / "installed_state.json"
    if state.is_file():
        state.unlink()
    return backup


def version_tuple(raw: str) -> tuple[int, ...]:
    values = re.findall(r"\d+", raw)
    return tuple(int(value) for value in values[:4]) or (0,)


def check_for_updates(silent: bool = False) -> dict:
    manifest = release_manifest()
    current = str(manifest["translation_version"])
    result = {"current": current, "latest": f"v{current}", "update_available": False}
    url = str(manifest["github_api_latest"])
    request = urllib.request.Request(url, headers={"User-Agent": "ARK-Italian-Translation-Installer"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            release = json.loads(response.read().decode("utf-8"))
        latest = str(release.get("tag_name") or current)
        result.update(
            {
                "latest": latest,
                "update_available": version_tuple(latest) > version_tuple(current),
                "release": release,
                "releases_url": str(manifest["github_releases_url"]),
            }
        )
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        result["error"] = str(exc)
        if not silent:
            print("Controllo aggiornamenti non disponibile; installazione locale ancora utilizzabile.")
    return result


def find_release_asset(release: dict) -> dict | None:
    expected = str(release_manifest()["installer_asset"])
    for asset in release.get("assets", []):
        if str(asset.get("name", "")).casefold() == expected.casefold():
            return asset
    return None


def download_update(asset: dict, destination: Path) -> None:
    url = str(asset.get("browser_download_url") or "")
    if not url.startswith("https://github.com/"):
        raise RuntimeError("URL di aggiornamento non valido.")
    request = urllib.request.Request(url, headers={"User-Agent": "ARK-Italian-Translation-Installer"})
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".download")
    digest = hashlib.sha256()
    size = 0
    try:
        with urllib.request.urlopen(request, timeout=30) as response, partial.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        expected_size = int(asset.get("size") or 0)
        expected_digest = str(asset.get("digest") or "")
        if expected_size and size != expected_size:
            raise RuntimeError("Dimensione dell'aggiornamento non valida.")
        if expected_digest.startswith("sha256:") and digest.hexdigest().lower() != expected_digest[7:].lower():
            raise RuntimeError("Hash SHA-256 dell'aggiornamento non valido.")
        os.replace(partial, destination)
    finally:
        if partial.exists():
            partial.unlink()


def schedule_update(status: dict) -> bool:
    if not getattr(sys, "frozen", False):
        print("L'aggiornamento automatico è disponibile soltanto nell'EXE compilato.")
        return False
    asset = find_release_asset(status.get("release") or {})
    if not asset:
        print("La release non contiene l'installer previsto.")
        return False
    cache = USER_WORK_DIR / "updates" / str(status["latest"])
    downloaded = cache / f"ARK-Italian-Translation-{os.getpid()}-{int(time.time() * 1000)}.exe"
    download_update(asset, downloaded)
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if os.name == "nt" else 0
    subprocess.Popen(
        [str(downloaded), UPDATE_APPLY_COMMAND, str(Path(sys.executable).resolve()), str(status["current"])],
        cwd=str(downloaded.parent),
        creationflags=flags,
    )
    return True


def apply_update(source: Path, target: Path, previous_version: str) -> int:
    for _ in range(40):
        try:
            temporary = target.with_suffix(target.suffix + ".new")
            shutil.copy2(source, temporary)
            os.replace(temporary, target)
            flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if os.name == "nt" else 0
            subprocess.Popen([str(target), UPDATE_COMPLETE_COMMAND, previous_version], cwd=str(target.parent), creationflags=flags)
            return 0
        except PermissionError:
            time.sleep(0.25)
    print("Aggiornamento non riuscito: chiudi le altre finestre dell'installer e riprova.")
    return 1


def enable_console_colors() -> bool:
    if not sys.stdout.isatty():
        return False
    if os.name != "nt":
        return True
    try:
        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def colored(text: str, color: str, enabled: bool) -> str:
    return f"{color}{text}{ConsoleColor.RESET}" if enabled else text


def startup_status() -> dict:
    manifest = release_manifest()
    result = {
        "manifest": manifest,
        "location": None,
        "installed": None,
        "update": check_for_updates(silent=True),
    }
    try:
        location = resolve_game_location()
        result["location"] = location
        result["installed"] = installation_status(location, manifest)
    except (FileNotFoundError, OSError):
        pass
    return result


def print_status(status: dict, colors: bool) -> None:
    manifest = status["manifest"]
    location = status.get("location")
    installed = status.get("installed")
    update = status["update"]
    supported = ", ".join(str(item) for item in manifest.get("supported_builds", []))
    print(colored("ARK: Survival Ascended - Traduzione Italiana", ConsoleColor.BOLD + ConsoleColor.CYAN, colors))
    print("=" * 68)
    if location:
        print("Percorso del gioco          :", colored(f"✓ {location.source}", ConsoleColor.GREEN, colors))
        print("Cartella                    :", location.game_dir)
        build_label = str(location.build_id or "non rilevata")
        build_color = ConsoleColor.GREEN if supported_build(location, manifest) else ConsoleColor.YELLOW
        print("Build del gioco rilevata    :", colored(build_label, build_color, colors))
    else:
        print("Percorso del gioco          :", colored("✗ NON TROVATO", ConsoleColor.RED, colors))
        print("Build del gioco rilevata    : non disponibile")
    print("Build verificata            :", supported or "non specificata")
    if installed and installed["current"]:
        install_label = colored("✓ INSTALLATA E AGGIORNATA", ConsoleColor.GREEN, colors)
    elif installed and installed["installed"]:
        install_label = colored("⚠ PRESENTE, VERSIONE DIVERSA", ConsoleColor.YELLOW, colors)
    else:
        install_label = colored("✗ NON INSTALLATA", ConsoleColor.YELLOW, colors)
    print("Traduzione italiana         :", install_label)
    print("Versione installer          :", manifest["translation_version"])
    if update.get("error"):
        latest = colored("controllo non disponibile", ConsoleColor.YELLOW, colors)
    elif update.get("update_available"):
        latest = colored(f"{update['latest']}  ← NUOVA", ConsoleColor.GREEN, colors)
    else:
        latest = colored("nessuna  ✓ AGGIORNATO", ConsoleColor.GREEN, colors)
    print("Nuova versione disponibile  :", latest)
    print("=" * 68)
    print("GitHub:", manifest["github_project_url"])


def show_credits() -> int:
    manifest = release_manifest()
    print("Progetto e traduzione : Sici29")
    print("GitHub                :", manifest["github_project_url"])
    print("Segnala un problema   :", manifest["github_issues_url"])
    print("Sostieni il progetto  :", manifest["support_url"])
    answer = input("Aprire la pagina GitHub? [S/n]: ").strip().lower()
    if answer in {"", "s", "si", "sì", "y", "yes"}:
        webbrowser.open(str(manifest["github_project_url"]))
    return 0


def install_from_menu(force: bool = False) -> int:
    try:
        location = resolve_game_location()
    except FileNotFoundError:
        location = configure_game_dir()
        if not location:
            return 1
    try:
        backup = install_translation(location, force=force)
    except (OSError, RuntimeError) as exc:
        print("Installazione non riuscita:", exc)
        if isinstance(exc, PermissionError):
            print("Riapri l'installer come amministratore e riprova.")
        return 1
    save_game_dir(location.game_dir)
    print("Traduzione installata correttamente.")
    print("Backup:", backup)
    print("Nel gioco seleziona la lingua: Italiano")
    return 0


def restore_from_menu() -> int:
    try:
        location = resolve_game_location()
        backup = restore_translation(location)
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        print("Ripristino non riuscito:", exc)
        return 1
    print("File originali ripristinati dal backup:", backup)
    return 0


def run_menu() -> int:
    colors = enable_console_colors()
    status = startup_status()
    print_status(status, colors)
    if not status.get("location"):
        print()
        answer = input("ARK non è stato trovato. Vuoi indicare la cartella? [S/n]: ").strip().lower()
        if answer in {"", "s", "si", "sì", "y", "yes"} and configure_game_dir():
            print()
            status = startup_status()
            print_status(status, colors)
    update = status["update"]
    if update.get("update_available"):
        print()
        answer = input("Vuoi aggiornare automaticamente l'installer? [S/n]: ").strip().lower()
        if answer in {"", "s", "si", "sì", "y", "yes"} and schedule_update(update):
            return UPDATE_SCHEDULED
    print()
    print("1. Installa o aggiorna la traduzione (consigliato)")
    print("2. Ripristina i file originali")
    print("3. Controlla gli aggiornamenti")
    print("4. Indica o modifica la cartella di ARK")
    print("5. Crediti, GitHub e sostieni il progetto")
    print("0. Esci")
    choice = input("Scelta [Invio = installa]: ").strip() or "1"
    if choice == "0":
        return 0
    if choice == "1":
        return install_from_menu()
    if choice == "2":
        return restore_from_menu()
    if choice == "3":
        update = check_for_updates()
        if update.get("update_available"):
            print("Nuova versione:", update["latest"])
            return UPDATE_SCHEDULED if schedule_update(update) else 1
        print("Stai già usando la versione più recente.")
        return 0
    if choice == "4":
        return 0 if configure_game_dir() else 1
    if choice == "5":
        return show_credits()
    print("Scelta non valida.")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")
    for name in ("install", "check", "restore"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--game-dir")
        if name == "install":
            sub.add_argument("--force", action="store_true")
    apply_parser = subparsers.add_parser(UPDATE_APPLY_COMMAND)
    apply_parser.add_argument("target_exe")
    apply_parser.add_argument("previous_version")
    complete = subparsers.add_parser(UPDATE_COMPLETE_COMMAND)
    complete.add_argument("previous_version")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == UPDATE_APPLY_COMMAND:
        return apply_update(Path(sys.executable).resolve(), Path(args.target_exe).resolve(), args.previous_version)
    if args.command == UPDATE_COMPLETE_COMMAND:
        print(f"Aggiornamento completato: v{args.previous_version} → v{release_manifest()['translation_version']}")
        input("Premi Invio per continuare...")
        return run_menu()
    if args.command == "check":
        location = resolve_game_location(args.game_dir)
        print(location)
        print(installation_status(location))
        return 0
    if args.command == "install":
        location = resolve_game_location(args.game_dir)
        backup = install_translation(location, force=args.force)
        save_game_dir(location.game_dir)
        print("Traduzione installata. Backup:", backup)
        return 0
    if args.command == "restore":
        location = resolve_game_location(args.game_dir)
        print("Ripristinato backup:", restore_translation(location))
        return 0
    return run_menu()


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("Errore:", exc)
        code = 1
    if getattr(sys, "frozen", False) and code != UPDATE_SCHEDULED:
        try:
            input("\nPremi Invio per chiudere...")
        except EOFError:
            pass
    raise SystemExit(code)
