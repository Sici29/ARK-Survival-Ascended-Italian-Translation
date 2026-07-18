from __future__ import annotations

import csv
import json
import re
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRANSLATION = ROOT / "data" / "translation_it.csv"
MANIFEST = ROOT / "data" / "release_manifest.json"
ICON_PNG = ROOT / "assets" / "ark-italian-installer-icon.png"
ICON_ICO = ROOT / "assets" / "ark-italian-installer-icon.ico"
MOJIBAKE = ("Ã", "Â", "â€™", "â€œ", "â€", "�")


class TranslationDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with TRANSLATION.open("r", encoding="utf-8-sig", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_complete_unique_keyset(self) -> None:
        self.assertEqual(len(self.rows), 38_751)
        keys = [row["key"] for row in self.rows]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertNotIn("", keys)

    def test_only_final_statuses(self) -> None:
        self.assertEqual({row["review_status"] for row in self.rows}, {"approved", "technical_preserve"})

    def test_public_csv_contains_no_extracted_english_column(self) -> None:
        self.assertNotIn("source_en", self.rows[0])

    def test_empty_values_are_only_intentional_technical_resources(self) -> None:
        invalid = [row["key"] for row in self.rows if not row["it"] and row["review_status"] != "technical_preserve"]
        self.assertEqual(invalid, [])

    def test_no_mojibake(self) -> None:
        bad = [row["key"] for row in self.rows if any(marker in row["it"] for marker in MOJIBAKE)]
        self.assertEqual(bad, [])

    def test_reported_ui_regressions_stay_fixed(self) -> None:
        values = {row["key"]: row["it"] for row in self.rows}
        expected = {
            "Content::1408111756": "indietro",
            "GraphLiteral::2850147001": "IMPOSTAZIONI",
            "GraphLiteral::3522676686": "TASTIERA",
            "GraphLiteral::1414235690": "CONTROLLER",
            "GraphLiteral::2667066748": "INTERFACCIA",
            "GraphLiteral::2854445489": "COSMETICI",
            "GraphLiteral::3998490662": "ATTIVO",
            "GraphLiteral::3851593686": "Abilita le particelle dei passi",
            "GraphLiteral::3965879518": "Soffoca",
            "GraphLiteral::3909508214": "Lancia",
            "GraphLiteral::3919423147": "Nuoto rapido",
            "GraphLiteral::1683757797": "IN EVIDENZA",
            "GraphLiteral::1943104726": "SALUTE",
            "GraphLiteral::2750903942": "Sempre",
            "GraphLiteral::2820092888": "PACCHETTI DLC",
            "GraphLiteral::3586629712": "Vibrazione",
            "GraphLiteral::3707105056": "PESO",
            "Content::1579144908": "SOVRIMPRESSIONI DEI DANNI DA SANGUE:",
            "Content::2498807650": "Gesto amichevole",
            "GraphLiteral::159169701": "Hai trovato la chiave di crittografia principale! Ora ti resta solo da trovare il resto del codice di forzatura, da qualche parte in quell'armeria.",
        }
        for key, value in expected.items():
            self.assertEqual(values.get(key), value, key)

    def test_natural_gaming_anglicisms_are_preserved(self) -> None:
        values = {row["key"]: row["it"] for row in self.rows}
        expected = {
            "Content::2054521003": "Camera",
            "GraphLiteral::2520716185": "Password",
            "GraphLiteral::4174992090": "Display",
            "Content::347257845": "GAMEPLAY",
            "Content::1918923023": "MULTIPLAYER",
            "Globals::4265803950": "ONLINE",
            "Globals::2010672823": "OFFLINE",
            "Content::2480994461": "Preset",
            "Content::1085785189": "Skin",
            "Globals::3019685387": "PING",
        }
        for key, value in expected.items():
            self.assertEqual(values.get(key), value, key)

    def test_release_manifest(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["translation_version"], "2.1.0")
        self.assertEqual(manifest["supported_builds"], ["24159380", "24230788", "24271369"])
        expected = [
            (
                "ARK_Italian_Review_24271369_P.pak",
                "ARK_Italian_Review_P.pak",
                "E32449D5077D73F3D29DB5505C39651F837AC53E0AD96EE20FFD98D2A8C4A0BB",
            ),
            (
                "zz_ARK_Italian_UI_Review-Windows.pak",
                "zz_ARK_Italian_UI_Review-Windows.pak",
                "75E7144577253917F6DA7312EF5E585B12FB728226A22B0938323751A6B555CD",
            ),
            (
                "zz_ARK_Italian_UI_Review-Windows.ucas",
                "zz_ARK_Italian_UI_Review-Windows.ucas",
                "15DB970623BE830E0769190EBE35979ED554A8148A15619CE7C276D758A0D583",
            ),
            (
                "zz_ARK_Italian_UI_Review-Windows.utoc",
                "zz_ARK_Italian_UI_Review-Windows.utoc",
                "FF373FA9AED50E6D5837B980514323761ACA38208AAE4FCAAF0FEE768FDFB795",
            ),
        ]
        actual = [
            (item["payload_file"], item["installed_file"], item["payload_sha256"])
            for item in manifest["payloads"]
        ]
        self.assertEqual(actual, expected)
        self.assertTrue(all(re.fullmatch(r"[0-9A-F]{64}", item[2]) for item in actual))

    def test_installer_icon_assets(self) -> None:
        self.assertTrue(ICON_PNG.is_file())
        self.assertTrue(ICON_ICO.is_file())
        self.assertEqual(ICON_PNG.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        ico = ICON_ICO.read_bytes()
        self.assertGreater(len(ico), 80_000)
        reserved, image_type, count = struct.unpack("<HHH", ico[:6])
        self.assertEqual((reserved, image_type), (0, 1))
        self.assertGreaterEqual(count, 7)


if __name__ == "__main__":
    unittest.main()
