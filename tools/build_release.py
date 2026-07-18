#!/usr/bin/env python3
"""Compila l'installer ARK in un unico EXE PyInstaller."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ICON_PATH = ROOT / "assets" / "ark-italian-installer-icon.ico"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def manifest_payloads(manifest: dict) -> list[dict[str, str]]:
    raw_payloads = manifest.get("payloads")
    if raw_payloads is None:
        raw_payloads = [
            {
                "payload_file": manifest["payload_file"],
                "installed_file": manifest["installed_file"],
                "payload_sha256": manifest["payload_sha256"],
            }
        ]
    if not isinstance(raw_payloads, list) or not raw_payloads:
        raise ValueError("Il manifest non contiene payload validi")
    return raw_payloads


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--payload",
        action="append",
        default=[],
        type=Path,
        help="File payload verificato da incorporare; ripetere l'opzione per ogni file",
    )
    parser.add_argument(
        "--pak",
        action="append",
        default=[],
        type=Path,
        help="Alias compatibile di --payload",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()

    manifest_path = ROOT / "data" / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not ICON_PATH.is_file():
        raise FileNotFoundError(f"Icona installer non trovata: {ICON_PATH}")
    payloads = manifest_payloads(manifest)
    supplied = [path.resolve() for path in [*args.payload, *args.pak]]
    if not supplied:
        parser.error("specificare tutti i payload con --payload (o --pak)")
    supplied_by_name: dict[str, Path] = {}
    for path in supplied:
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.name in supplied_by_name:
            raise ValueError(f"Payload fornito più volte: {path.name}")
        supplied_by_name[path.name] = path
    expected_names = {str(payload["payload_file"]) for payload in payloads}
    missing = sorted(expected_names - supplied_by_name.keys())
    unexpected = sorted(supplied_by_name.keys() - expected_names)
    if missing or unexpected:
        details = []
        if missing:
            details.append("mancanti: " + ", ".join(missing))
        if unexpected:
            details.append("inattesi: " + ", ".join(unexpected))
        raise ValueError("Elenco payload non corrispondente al manifest (" + "; ".join(details) + ")")

    build_root = ROOT / ".build"
    bundle_dir = build_root / "bundle"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    payload_dir = bundle_dir / "payload"
    payload_dir.mkdir(parents=True, exist_ok=True)
    for payload in payloads:
        payload_name = str(payload["payload_file"])
        source = supplied_by_name[payload_name]
        actual_hash = sha256_file(source)
        expected_hash = str(payload["payload_sha256"]).upper()
        if actual_hash != expected_hash:
            raise ValueError(f"SHA-256 inatteso per {payload_name}: {actual_hash} != {expected_hash}")
        shutil.copy2(source, payload_dir / payload_name)
    args.output.mkdir(parents=True, exist_ok=True)

    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("Installa requirements-build.txt nell'ambiente Python di build") from exc

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        "--icon",
        str(ICON_PATH.resolve()),
        "--name",
        Path(str(manifest["installer_asset"])).stem,
        "--distpath",
        str(args.output.resolve()),
        "--workpath",
        str((build_root / "work").resolve()),
        "--specpath",
        str((build_root / "spec").resolve()),
        "--add-data",
        f"{manifest_path.resolve()};data",
        "--add-data",
        f"{payload_dir.resolve()};payload",
        str((ROOT / "tools" / "ark_it_installer.py").resolve()),
    ]
    subprocess.run(command, check=True, cwd=ROOT)
    exe = args.output.resolve() / str(manifest["installer_asset"])
    if not exe.is_file():
        raise FileNotFoundError(f"PyInstaller non ha creato {exe}")
    unexpected = sorted(path.name for path in args.output.resolve().iterdir() if path.is_file() and path != exe)
    if unexpected:
        raise RuntimeError("La cartella di release deve contenere un solo EXE; file inattesi: " + ", ".join(unexpected))
    print("EXE:", exe)
    print("SHA-256:", sha256_file(exe))
    print("Payload incorporati:", len(payloads))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
