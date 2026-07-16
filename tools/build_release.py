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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pak", required=True, type=Path, help="PAK italiano verificato da incorporare")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()

    manifest_path = ROOT / "data" / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    pak = args.pak.resolve()
    if not pak.is_file():
        raise FileNotFoundError(pak)
    actual_hash = sha256_file(pak)
    expected_hash = str(manifest["payload_sha256"]).upper()
    if actual_hash != expected_hash:
        raise ValueError(f"SHA-256 PAK inatteso: {actual_hash} != {expected_hash}")

    build_root = ROOT / ".build"
    payload_dir = build_root / "bundle" / "payload"
    payload_dir.mkdir(parents=True, exist_ok=True)
    payload_copy = payload_dir / str(manifest["payload_file"])
    shutil.copy2(pak, payload_copy)
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
        f"{payload_copy.resolve()};payload",
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
