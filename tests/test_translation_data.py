from __future__ import annotations

import csv
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRANSLATION = ROOT / "data" / "translation_it.csv"
MANIFEST = ROOT / "data" / "release_manifest.json"
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

    def test_release_manifest(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["translation_version"], "2.0.1")
        self.assertEqual(manifest["supported_builds"], ["24159380", "24230788"])
        expected = [
            (
                "ARK_Italian_Review_24230788_P.pak",
                "ARK_Italian_Review_P.pak",
                "88142178794EA50D0AE8670A8D8C4E01686D24044C34B8256F8E637A6D86ED9B",
            ),
            (
                "zz_ARK_Italian_UI_Review-Windows.pak",
                "zz_ARK_Italian_UI_Review-Windows.pak",
                "75E7144577253917F6DA7312EF5E585B12FB728226A22B0938323751A6B555CD",
            ),
            (
                "zz_ARK_Italian_UI_Review-Windows.ucas",
                "zz_ARK_Italian_UI_Review-Windows.ucas",
                "7B38AB7B90FC19F5B4756BB6AF725D1EB11CE76042A0EAD15E99523FDC27FC69",
            ),
            (
                "zz_ARK_Italian_UI_Review-Windows.utoc",
                "zz_ARK_Italian_UI_Review-Windows.utoc",
                "0C5C72C1F2CCF8B063CDB5300142D80A1E31DC8E9F0BA1FC201072F184523913",
            ),
        ]
        actual = [
            (item["payload_file"], item["installed_file"], item["payload_sha256"])
            for item in manifest["payloads"]
        ]
        self.assertEqual(actual, expected)
        self.assertTrue(all(re.fullmatch(r"[0-9A-F]{64}", item[2]) for item in actual))


if __name__ == "__main__":
    unittest.main()
