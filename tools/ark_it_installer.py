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
_INSTANCE_LOCK_HANDLE = None

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


def recorded_translation_version(location: GameLocation) -> str | None:
    state_path = USER_WORK_DIR / "installed_state.json"
    if not state_path.is_file():
        return None
    try:
        state = read_json(state_path)
        recorded_game = Path(str(state.get("game_dir") or "")).resolve()
        if recorded_game != location.game_dir.resolve():
            return None
        version = str(state.get("translation_version") or "").strip()
        return version or None
    except (OSError, ValueError, json.JSONDecodeError):
        return None


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


def normalize_version(version: str) -> tuple[int, ...]:
    """Compare semantic versions while ranking a stable build above its prerelease."""
    raw = version.strip().lower().lstrip("v")
    core, separator, suffix = raw.partition("-")
    values = [int(part) for part in re.findall(r"\d+", core)]
    values = (values + [0, 0, 0])[:3]
    stable_rank = 1 if not separator else 0
    suffix_values = [int(part) for part in re.findall(r"\d+", suffix)]
    return tuple(values + [stable_rank] + suffix_values)


def version_tuple(raw: str) -> tuple[int, ...]:
    """Backward-compatible alias used by older tests and integrations."""
    return normalize_version(raw)


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
                "update_available": normalize_version(latest) > normalize_version(current),
                "release": release,
                "asset": find_release_asset(release),
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
    expected_digest = str(asset.get("digest") or "")
    if not url.startswith("https://github.com/"):
        raise RuntimeError("URL di aggiornamento non valido.")
    if not expected_digest.lower().startswith("sha256:"):
        raise RuntimeError("GitHub non ha fornito l'hash SHA-256: aggiornamento automatico annullato.")
    expected_hash = expected_digest.split(":", 1)[1].lower()
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
        if expected_size and size != expected_size:
            raise RuntimeError("Dimensione dell'aggiornamento non valida.")
        if digest.hexdigest().lower() != expected_hash:
            raise RuntimeError("Hash SHA-256 dell'aggiornamento non valido.")
        os.replace(partial, destination)
    finally:
        if partial.exists():
            partial.unlink()


def acquire_installer_instance_lock() -> bool:
    """Impedisce che due finestre interattive blocchino l'auto-aggiornamento."""
    global _INSTANCE_LOCK_HANDLE
    if _INSTANCE_LOCK_HANDLE is not None or os.name != "nt":
        return True
    import msvcrt

    try:
        USER_WORK_DIR.mkdir(parents=True, exist_ok=True)
        handle = (USER_WORK_DIR / "installer.lock").open("a+b")
    except OSError:
        return True
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return False
    _INSTANCE_LOCK_HANDLE = handle
    return True


def prompt_close_other_installers() -> bool:
    if os.name != "nt":
        return False
    try:
        message = (
            "Un'altra finestra di ARK - Traduzione Italiana sta usando il vecchio EXE.\n\n"
            "Chiudi tutte le altre finestre dell'installer, poi premi Riprova."
        )
        flags = 0x00000005 | 0x00000030 | 0x00040000
        return ctypes.windll.user32.MessageBoxW(None, message, "Aggiornamento installer", flags) == 4
    except Exception:
        return False


def show_update_failure_message() -> None:
    if os.name != "nt":
        return
    try:
        message = (
            "Aggiornamento non completato.\n\n"
            "Chiudi tutte le finestre dell'installer e riprova. Il vecchio EXE non è stato modificato."
        )
        ctypes.windll.user32.MessageBoxW(
            None, message, "ARK - Traduzione Italiana", 0x00000010 | 0x00040000
        )
    except Exception:
        pass


def cleanup_update_cache() -> int:
    updates = USER_WORK_DIR / "updates"
    if not updates.is_dir():
        return 0
    removed = 0
    current = Path(sys.executable).resolve()
    expected = str(release_manifest().get("installer_asset") or "")
    for file in updates.rglob("*"):
        if not file.is_file() or not (
            file.name == expected
            or file.name.startswith("ARK-Italian-Translation-")
            or file.name.endswith(".exe.download")
        ):
            continue
        try:
            if file.resolve() != current:
                file.unlink()
                removed += 1
        except OSError:
            pass
    return removed


def apply_update_payload(
    source: Path,
    target: Path,
    retries: int = 120,
    delay: float = 0.5,
    launch: bool = True,
    launch_args: list[str] | None = None,
) -> bool:
    """Sostituisce il vecchio EXE solo dopo averne ottenuto l'accesso esclusivo."""
    source = source.resolve()
    target = target.resolve()
    if source == target or target.suffix.lower() != ".exe":
        raise ValueError("Percorso di aggiornamento non valido.")
    staging = target.with_name(target.name + ".new")
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            shutil.copy2(source, staging)
            os.replace(staging, target)
            if launch:
                launch_kwargs: dict[str, object] = {"cwd": str(target.parent)}
                if os.name == "nt":
                    launch_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
                subprocess.Popen([str(target), *(launch_args or [])], **launch_kwargs)
            return True
        except (PermissionError, OSError) as exc:
            last_error = exc
            time.sleep(delay)
        finally:
            if staging.exists():
                try:
                    staging.unlink()
                except OSError:
                    pass
    raise RuntimeError(f"Impossibile sostituire il vecchio installer: {last_error}")


def schedule_update(status: dict) -> bool:
    if not getattr(sys, "frozen", False):
        print("L'aggiornamento automatico è disponibile soltanto nell'EXE compilato.")
        return False
    asset = status.get("asset") or find_release_asset(status.get("release") or {})
    if not asset:
        print("La release non contiene l'installer previsto.")
        return False
    cache = USER_WORK_DIR / "updates" / str(status["latest"])
    downloaded = cache / f"ARK-Italian-Translation-{os.getpid()}-{int(time.time() * 1000)}.exe"
    download_update(asset, downloaded)
    print("Download verificato tramite SHA-256.")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    subprocess.Popen(
        [str(downloaded), UPDATE_APPLY_COMMAND, str(Path(sys.executable).resolve()), str(status["current"])],
        cwd=str(downloaded.parent),
        creationflags=flags,
    )
    return True


def apply_update(source: Path, target: Path, previous_version: str) -> int:
    log_path = USER_WORK_DIR / "update_error.txt"
    completion_args = [UPDATE_COMPLETE_COMMAND, previous_version]
    try:
        try:
            apply_update_payload(source, target, retries=20, delay=0.25, launch_args=completion_args)
        except RuntimeError:
            if not prompt_close_other_installers():
                raise
            apply_update_payload(source, target, launch_args=completion_args)
        if log_path.exists():
            log_path.unlink()
        return 0
    except Exception as exc:
        USER_WORK_DIR.mkdir(parents=True, exist_ok=True)
        log_path.write_text(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {exc}\n", encoding="utf-8")
        show_update_failure_message()
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
        "installed_version": None,
        "update": check_for_updates(silent=True),
    }
    try:
        location = resolve_game_location()
        result["location"] = location
        result["installed"] = installation_status(location, manifest)
        result["installed_version"] = recorded_translation_version(location)
    except (FileNotFoundError, OSError):
        pass
    return result


def status_overview(status: dict, colors: bool) -> dict[str, str]:
    manifest = status["manifest"]
    location = status.get("location")
    installed = status.get("installed")
    installed_version = status.get("installed_version")
    update = status["update"]
    current = f"v{str(manifest.get('translation_version') or '0.0.0').lstrip('v')}"
    latest = str(update.get("latest") or current)

    if location:
        source_note = "trovato automaticamente" if location.source != "manuale" else "percorso scelto"
        if supported_build(location, manifest):
            game_label = colored(
                f"✓ build {location.build_id or 'rilevata'} compatibile ({source_note})",
                ConsoleColor.GREEN,
                colors,
            )
        else:
            game_label = colored(
                f"⚠ build {location.build_id or 'sconosciuta'} da verificare ({source_note})",
                ConsoleColor.YELLOW,
                colors,
            )
    else:
        game_label = colored("✗ non trovato", ConsoleColor.RED, colors)

    if update.get("error"):
        installer_label = colored(f"{current} (controllo online non disponibile)", ConsoleColor.YELLOW, colors)
    elif update.get("update_available"):
        installer_label = colored(f"{current} → {latest} disponibile", ConsoleColor.GREEN, colors)
    else:
        installer_label = colored(f"{current} aggiornato", ConsoleColor.GREEN, colors)

    if installed and installed.get("current"):
        translation_label = colored(f"✓ {current} installata", ConsoleColor.GREEN, colors)
    elif installed and installed.get("installed"):
        recorded = f"v{str(installed_version).lstrip('v')}" if installed_version else "versione non registrata"
        translation_label = colored(f"⚠ {recorded} installata → {current} disponibile", ConsoleColor.YELLOW, colors)
    elif installed is not None:
        translation_label = colored(f"non installata → {current} disponibile", ConsoleColor.YELLOW, colors)
    else:
        translation_label = colored("? stato non verificabile", ConsoleColor.YELLOW, colors)

    if not location:
        headline = colored("✗ GIOCO NON TROVATO", ConsoleColor.BOLD + ConsoleColor.RED, colors)
        message = "Indica la cartella di ARK: Survival Ascended per continuare."
        action = "Scegli 4 per selezionare la cartella del gioco."
    elif not supported_build(location, manifest):
        headline = colored("⚠ ARK È STATO AGGIORNATO — BUILD DA VERIFICARE", ConsoleColor.BOLD + ConsoleColor.YELLOW, colors)
        message = f"La build {location.build_id or 'rilevata'} non è ancora certificata per questa traduzione."
        action = "Aggiorna l'installer oppure attendi una release compatibile; non forzare l'installazione."
    elif update.get("update_available"):
        headline = colored("↑ NUOVO INSTALLER DISPONIBILE", ConsoleColor.BOLD + ConsoleColor.GREEN, colors)
        message = f"È disponibile {latest}."
        action = "Accetta l'aggiornamento automatico consigliato."
    elif installed and installed.get("current"):
        headline = colored("✓ TUTTO AGGIORNATO", ConsoleColor.BOLD + ConsoleColor.GREEN, colors)
        message = "La traduzione installata coincide con quella dell'installer."
        action = "Non devi fare nulla."
    elif installed and installed.get("installed"):
        headline = colored("↑ TRADUZIONE DA AGGIORNARE", ConsoleColor.BOLD + ConsoleColor.YELLOW, colors)
        message = f"L'installer contiene la traduzione {current}."
        action = "Premi Invio per aggiornarla."
    else:
        headline = colored("✓ PRONTA PER L'INSTALLAZIONE", ConsoleColor.BOLD + ConsoleColor.GREEN, colors)
        message = f"La traduzione {current} è compatibile con questa build di ARK."
        action = "Premi Invio per installarla."

    return {
        "headline": headline,
        "message": message,
        "game": game_label,
        "translation": translation_label,
        "installer": installer_label,
        "action": action,
    }


def print_status(status: dict, colors: bool) -> None:
    overview = status_overview(status, colors)
    print(colored("ARK: Survival Ascended - Traduzione Italiana", ConsoleColor.BOLD + ConsoleColor.CYAN, colors))
    print("=" * 68)
    print(overview["headline"])
    print(overview["message"])
    print()
    print(f"Gioco       : {overview['game']}")
    print(f"Traduzione  : {overview['translation']}")
    print(f"Installer   : {overview['installer']}")
    print()
    print(colored("COSA FARE", ConsoleColor.BOLD, colors))
    print(overview["action"])
    print("=" * 68)
    print("GitHub:", status["manifest"]["github_project_url"])


def print_technical_status(status: dict, colors: bool) -> None:
    manifest = status["manifest"]
    location = status.get("location")
    installed = status.get("installed") or {}
    print(colored("Dettagli tecnici", ConsoleColor.BOLD + ConsoleColor.CYAN, colors))
    print("=" * 68)
    print("Cartella gioco     :", location.game_dir if location else "non rilevata")
    print("Metodo rilevamento :", location.source if location else "non disponibile")
    print("Build rilevata     :", location.build_id if location else "non rilevata")
    print("Build supportate   :", ", ".join(str(item) for item in manifest.get("supported_builds", [])) or "nessuna")
    print("Versione registrata:", status.get("installed_version") or "non registrata")
    print("Hash PAK installato:", installed.get("hash") or "non presente")
    print("=" * 68)


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


def ensure_current_installer(ignore_update: bool = False, no_update_check: bool = False) -> None:
    if ignore_update or no_update_check:
        return
    update = check_for_updates(silent=True)
    if update.get("update_available"):
        raise RuntimeError(
            f"È disponibile l'installer {update['latest']}. Aggiornalo prima di installare la traduzione."
        )


def install_from_menu(force: bool = False, ignore_update: bool = False) -> int:
    try:
        ensure_current_installer(ignore_update=ignore_update)
    except RuntimeError as exc:
        print("Installazione non avviata:", exc)
        return 1
    try:
        location = resolve_game_location()
    except FileNotFoundError:
        try:
            location = configure_game_dir()
        except (OSError, RuntimeError) as exc:
            print("Installazione non riuscita:", exc)
            return 1
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
    print("6. Mostra i dettagli tecnici")
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
    if choice == "6":
        print()
        print_technical_status(status, colors)
        return 0
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
            sub.add_argument("--no-update-check", action="store_true")
            sub.add_argument("--ignore-update", action="store_true")
    update = subparsers.add_parser("update")
    update.set_defaults(command="update")
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
        if not acquire_installer_instance_lock():
            print("Aggiornamento completato, ma un'altra finestra dell'installer è ancora aperta.")
            return 4
        cleanup_update_cache()
        print(colored("✓ AGGIORNAMENTO COMPLETATO", ConsoleColor.BOLD + ConsoleColor.GREEN, enable_console_colors()))
        print(f"Versione precedente : v{args.previous_version.lstrip('v')}")
        print(f"Versione attuale    : v{str(release_manifest()['translation_version']).lstrip('v')}")
        print("L'installer è stato riavviato automaticamente.\n")
        return run_menu()
    if args.command == "check":
        location = resolve_game_location(args.game_dir)
        print(location)
        print(installation_status(location))
        return 0
    if args.command == "install":
        ensure_current_installer(ignore_update=args.ignore_update, no_update_check=args.no_update_check)
        location = resolve_game_location(args.game_dir)
        backup = install_translation(location, force=args.force)
        save_game_dir(location.game_dir)
        print("Traduzione installata. Backup:", backup)
        return 0
    if args.command == "restore":
        location = resolve_game_location(args.game_dir)
        print("Ripristinato backup:", restore_translation(location))
        return 0
    if args.command == "update":
        update = check_for_updates()
        if update.get("update_available"):
            return UPDATE_SCHEDULED if schedule_update(update) else 1
        return 0
    if not acquire_installer_instance_lock():
        print("L'installer è già aperto in un'altra finestra.")
        print("Chiudi l'altra finestra prima di riaprirlo.")
        return 4
    cleanup_update_cache()
    return run_menu()


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("Errore:", exc)
        code = 1
    internal_apply = len(sys.argv) > 1 and sys.argv[1] == UPDATE_APPLY_COMMAND
    if getattr(sys, "frozen", False) and code != UPDATE_SCHEDULED and not internal_apply:
        try:
            input("\nPremi Invio per chiudere...")
        except EOFError:
            pass
    raise SystemExit(code)
