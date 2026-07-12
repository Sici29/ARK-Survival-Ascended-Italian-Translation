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

    def test_release_manifest(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["translation_version"], "1.0.0")
        self.assertEqual(manifest["supported_builds"], ["24159380"])
        self.assertRegex(manifest["payload_sha256"], r"^[0-9A-F]{64}$")


if __name__ == "__main__":
    unittest.main()
