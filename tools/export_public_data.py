#!/usr/bin/env python3
"""Esporta il master pubblico senza alterare spazi, tag o ritorni a capo."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


FIELDS = ["key", "category", "it", "review_status", "review_note"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    with args.master.open("r", encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    if len(rows) != 38_751:
        raise ValueError(f"Numero righe inatteso: {len(rows)}")

    public_rows = [
        {
            "key": row["key"],
            "category": row["category"],
            "it": row["it_revision"],
            "review_status": row["review_status"],
            "review_note": row["review_note"],
        }
        for row in rows
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(public_rows)
    print(f"Esportate {len(public_rows)} righe in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
