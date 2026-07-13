from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ark_installer", ROOT / "tools" / "ark_it_installer.py")
installer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)


def make_game(root: Path, build_id: str = "24159380") -> tuple[Path, Path]:
    library = root / "SteamLibrary"
    game = library / "steamapps" / "common" / installer.GAME_FOLDER_NAME
    (game / "ShooterGame" / "Binaries" / "Win64").mkdir(parents=True)
    (game / "ShooterGame" / "Content" / "Paks").mkdir(parents=True)
    (game / "ShooterGame" / "Binaries" / "Win64" / "ArkAscended.exe").write_bytes(b"exe")
    (game / "ShooterGame" / "Content" / "Paks" / installer.BASE_PAK).write_bytes(b"pak")
    manifest = library / "steamapps" / f"appmanifest_{installer.APP_ID}.acf"
    manifest.write_text(
        f'"AppState"\n{{\n"appid" "{installer.APP_ID}"\n"installdir" "{installer.GAME_FOLDER_NAME}"\n"buildid" "{build_id}"\n}}\n',
        encoding="utf-8",
    )
    return game, manifest


class DetectionTests(unittest.TestCase):
    def test_parse_acf(self) -> None:
        parsed = installer.parse_acf('"appid" "2399830"\n"buildid" "24159380"')
        self.assertEqual(parsed["appid"], "2399830")
        self.assertEqual(parsed["buildid"], "24159380")

    def test_parse_library_paths_with_escaped_backslashes(self) -> None:
        paths = installer.parse_library_paths('"path" "D:\\\\SteamLibrary"')
        self.assertEqual(paths, [Path(r"D:\SteamLibrary")])

    def test_game_requires_executable_and_base_pak(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            game, _ = make_game(Path(temp))
            self.assertTrue(installer.looks_like_game_dir(game))
            (game / "ShooterGame" / "Content" / "Paks" / installer.BASE_PAK).unlink()
            self.assertFalse(installer.looks_like_game_dir(game))

    def test_manifest_detection_reads_install_dir_and_build(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game, manifest = make_game(root)
            library = manifest.parent.parent
            with patch.object(installer, "steam_libraries", return_value=[library]):
                found = installer.manifest_locations()
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].game_dir, game.resolve())
            self.assertEqual(found[0].build_id, "24159380")
            self.assertEqual(found[0].source, "manifest Steam")

    def test_saved_path_is_preferred(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game, _ = make_game(root)
            work = root / "work"
            with patch.object(installer, "USER_WORK_DIR", work), patch.object(
                installer, "manifest_locations", return_value=[]
            ), patch.object(installer, "fallback_candidates", return_value=[]):
                installer.save_game_dir(game)
                found = installer.resolve_game_location()
            self.assertEqual(found.game_dir, game.resolve())
            self.assertEqual(found.source, "percorso salvato")


class InstallRestoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.game, self.app_manifest = make_game(self.root)
        self.location = installer.location_from_dir(self.game, "test", self.app_manifest)
        self.work = self.root / "work"
        self.bundle = self.root / "bundle"
        (self.bundle / "payload").mkdir(parents=True)
        (self.bundle / "data").mkdir(parents=True)
        self.payload = self.bundle / "payload" / "patch.pak"
        self.payload.write_bytes(b"verified translation patch")
        self.manifest = {
            "translation_version": "1.0.0",
            "supported_builds": ["24159380"],
            "payload_file": "patch.pak",
            "payload_sha256": installer.sha256_file(self.payload),
            "installed_file": "ARK_Italian_Review_P.pak",
        }
        (self.bundle / "data" / "release_manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def patches(self):
        return patch.multiple(
            installer,
            USER_WORK_DIR=self.work,
            BUNDLE_DIR=self.bundle,
            DATA_DIR=self.bundle / "data",
            PAYLOAD_DIR=self.bundle / "payload",
        )

    def test_install_creates_backup_and_verified_target(self) -> None:
        with self.patches(), patch.object(installer, "process_running", return_value=[]):
            backup = installer.install_translation(self.location)
            target = installer.installed_patch_path(self.location, self.manifest)
            self.assertEqual(target.read_bytes(), self.payload.read_bytes())
            self.assertTrue((backup / "backup_manifest.json").is_file())
            self.assertTrue(installer.installation_status(self.location, self.manifest)["current"])

    def test_restore_removes_patch_if_none_existed_before(self) -> None:
        with self.patches(), patch.object(installer, "process_running", return_value=[]):
            installer.install_translation(self.location)
            target = installer.installed_patch_path(self.location, self.manifest)
            self.assertTrue(target.is_file())
            installer.restore_translation(self.location)
            self.assertFalse(target.exists())

    def test_restore_recovers_previous_patch(self) -> None:
        target = installer.installed_patch_path(self.location, self.manifest)
        target.write_bytes(b"older community patch")
        with self.patches(), patch.object(installer, "process_running", return_value=[]):
            installer.install_translation(self.location)
            installer.restore_translation(self.location)
        self.assertEqual(target.read_bytes(), b"older community patch")

    def test_wrong_build_is_refused_without_force(self) -> None:
        location = installer.GameLocation(
            self.location.game_dir,
            self.location.paks_dir,
            self.location.manifest,
            "99999999",
            "test",
        )
        with self.patches(), patch.object(installer, "process_running", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "non verificata"):
                installer.install_translation(location)

    def test_tampered_payload_is_refused(self) -> None:
        with self.patches(), patch.object(installer, "process_running", return_value=[]):
            self.payload.write_bytes(b"tampered")
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                installer.install_translation(self.location)


class VersionTests(unittest.TestCase):
    def test_semantic_versions(self) -> None:
        self.assertGreater(installer.version_tuple("v1.2.0"), installer.version_tuple("1.1.9"))

    def test_stable_version_is_newer_than_matching_beta(self) -> None:
        self.assertGreater(installer.normalize_version("1.1.0"), installer.normalize_version("1.1.0-beta"))
        self.assertGreater(installer.normalize_version("1.1.0-beta.2"), installer.normalize_version("1.1.0-beta.1"))


class UpdateSafetyTests(unittest.TestCase):
    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            self.close()

    def test_download_requires_github_sha256_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            asset = {"browser_download_url": "https://github.com/example/release.exe"}
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                installer.download_update(asset, Path(temp) / "installer.exe")

    def test_download_accepts_only_matching_size_and_hash(self) -> None:
        payload = b"verified installer"
        digest = installer.hashlib.sha256(payload).hexdigest()
        asset = {
            "browser_download_url": "https://github.com/example/release.exe",
            "digest": f"sha256:{digest}",
            "size": len(payload),
        }
        with tempfile.TemporaryDirectory() as temp, patch.object(
            installer.urllib.request, "urlopen", return_value=self.FakeResponse(payload)
        ):
            target = Path(temp) / "installer.exe"
            installer.download_update(asset, target)
            self.assertEqual(target.read_bytes(), payload)

    def test_download_rejects_wrong_hash_without_publishing_file(self) -> None:
        asset = {
            "browser_download_url": "https://github.com/example/release.exe",
            "digest": "sha256:" + "0" * 64,
            "size": 3,
        }
        with tempfile.TemporaryDirectory() as temp, patch.object(
            installer.urllib.request, "urlopen", return_value=self.FakeResponse(b"bad")
        ):
            target = Path(temp) / "installer.exe"
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                installer.download_update(asset, target)
            self.assertFalse(target.exists())

    def test_failed_replacement_keeps_old_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "new.exe"
            target = root / "old.exe"
            source.write_bytes(b"new")
            target.write_bytes(b"old")
            with patch.object(installer.shutil, "copy2", side_effect=PermissionError("locked")):
                with self.assertRaisesRegex(RuntimeError, "sostituire"):
                    installer.apply_update_payload(source, target, retries=1, delay=0, launch=False)
            self.assertEqual(target.read_bytes(), b"old")

    def test_cleanup_removes_only_installer_cache_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            cache = work / "updates" / "v1.1.0"
            cache.mkdir(parents=True)
            known = cache / "ARK-Italian-Translation-123.exe"
            partial = cache / "release.exe.download"
            unrelated = cache / "keep.txt"
            known.write_bytes(b"exe")
            partial.write_bytes(b"partial")
            unrelated.write_bytes(b"keep")
            with patch.object(installer, "USER_WORK_DIR", work), patch.object(
                installer, "release_manifest", return_value={"installer_asset": "ARK-Translation.exe"}
            ):
                self.assertEqual(installer.cleanup_update_cache(), 2)
            self.assertTrue(unrelated.is_file())

    def test_newer_installer_blocks_install_unless_explicitly_ignored(self) -> None:
        update = {"update_available": True, "latest": "v1.1.0"}
        with patch.object(installer, "check_for_updates", return_value=update):
            with self.assertRaisesRegex(RuntimeError, "Aggiornalo"):
                installer.ensure_current_installer()
            installer.ensure_current_installer(ignore_update=True)


class StatusTests(unittest.TestCase):
    def test_recorded_version_is_scoped_to_detected_game(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game, manifest_path = make_game(root)
            location = installer.location_from_dir(game, "test", manifest_path)
            work = root / "work"
            work.mkdir()
            state = {"game_dir": str(root / "another-game"), "translation_version": "1.0.0"}
            (work / "installed_state.json").write_text(json.dumps(state), encoding="utf-8")
            with patch.object(installer, "USER_WORK_DIR", work):
                self.assertIsNone(installer.recorded_translation_version(location))
                state["game_dir"] = str(game)
                (work / "installed_state.json").write_text(json.dumps(state), encoding="utf-8")
                self.assertEqual(installer.recorded_translation_version(location), "1.0.0")

    def test_status_calls_out_unverified_game_update(self) -> None:
        location = installer.GameLocation(Path("C:/ARK"), Path("C:/ARK/Paks"), None, "99999999", "test")
        status = {
            "manifest": {"translation_version": "1.1.0", "supported_builds": ["24159380"]},
            "location": location,
            "installed": {"installed": False, "current": False, "hash": None},
            "installed_version": None,
            "update": {"current": "1.1.0", "latest": "v1.1.0", "update_available": False},
        }
        overview = installer.status_overview(status, colors=False)
        self.assertIn("ARK È STATO AGGIORNATO", overview["headline"])


if __name__ == "__main__":
    unittest.main()
