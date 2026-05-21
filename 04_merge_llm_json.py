#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Merge article-level LLM JSON files into a species-level CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ARTICLE_FIELDS = ["doi", "title", "year", "url", "volume", "issue", "article_type"]
SPECIES_FIELDS = [
    "species_name",
    "taxon_rank",
    "type_strain",
    "strains",
    "isolation_source",
    "isolation_location",
    "temperature_min",
    "temperature_opt",
    "temperature_max",
    "temperature_evidence",
    "confidence",
]


def scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(scalar(v) for v in value if scalar(v))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def rows_from_json(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    article = data.get("article") or {}
    records = data.get("species_detail_list") or data.get("species") or []
    rows = []
    for i, rec in enumerate(records, start=1):
        if not isinstance(rec, dict):
            continue
        row = {
            "json_path": str(path),
            "source_markdown": scalar(data.get("_source_markdown")),
            "record_index": str(i),
            "prompt_version": scalar(data.get("_prompt_version")),
            "model": scalar(data.get("_model")),
        }
        for key in ARTICLE_FIELDS:
            row[key] = scalar(article.get(key) or data.get(key))
        for key in SPECIES_FIELDS:
            row[key] = scalar(rec.get(key))
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Directory containing JSON files")
    parser.add_argument("--output", default="data/temperature_records_raw.csv")
    args = parser.parse_args()

    rows = []
    for path in sorted(Path(args.input).rglob("*.json")):
        try:
            rows.extend(rows_from_json(path))
        except Exception as exc:
            rows.append({"json_path": str(path), "error": str(exc)})

    fields = [
        "json_path",
        "source_markdown",
        "record_index",
        "prompt_version",
        "model",
        *ARTICLE_FIELDS,
        *SPECIES_FIELDS,
        "error",
    ]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})
    print(f"Wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
