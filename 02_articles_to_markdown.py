#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Download IJSEM article pages and convert main text to Markdown."""

from __future__ import annotations

import argparse
import csv
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from tqdm import tqdm


def safe_name(value: str) -> str:
    value = re.sub(r"^https?://", "", value or "")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")[:180] or "article"


def table_to_markdown(table) -> str:
    rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines.extend("| " + " | ".join(r) + " |" for r in rows[1:])
    return "\n".join(lines)


def article_to_markdown(html: str, meta: dict[str, str]) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title = meta.get("title") or ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)
    parts = [f"# {title}".strip(), ""]
    for key in ["doi", "year", "volume", "issue", "url", "article_type"]:
        if meta.get(key):
            parts.append(f"- {key}: {meta[key]}")
    parts.append("")

    container = soup.select_one("div.article-content") or soup.select_one("article") or soup.body
    if not container:
        return "\n".join(parts)

    for node in container.find_all(["h2", "h3", "h4", "p", "table"]):
        if node.name in {"h2", "h3", "h4"}:
            text = node.get_text(" ", strip=True)
            if text:
                parts.append(f"\n## {text}\n")
        elif node.name == "p":
            text = node.get_text(" ", strip=True)
            if text:
                parts.append(text)
        elif node.name == "table":
            md = table_to_markdown(node)
            if md:
                parts.append(md)
    return "\n\n".join(parts).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--articles", required=True, help="CSV from 01_fetch_ijsem_articles.py")
    parser.add_argument("--outdir", default="data/markdown")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(args.articles, encoding="utf-8-sig", newline="")))
    manifest = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        page = browser.new_page()
        for row in tqdm(rows, desc="articles"):
            url = row.get("url", "")
            if not url:
                continue
            try:
                page.goto(url, timeout=60000)
                page.wait_for_load_state("networkidle")
                time.sleep(args.delay)
                md = article_to_markdown(page.content(), row)
                issue_dir = outdir / safe_name(row.get("year") or "unknown") / safe_name(row.get("issue") or "issue")
                md_dir = issue_dir / "md"
                md_dir.mkdir(parents=True, exist_ok=True)
                md_path = md_dir / f"{safe_name(row.get('doi') or url)}.md"
                md_path.write_text(md, encoding="utf-8")
                manifest.append({**row, "md_path": str(md_path), "status": "ok", "error": ""})
            except Exception as exc:
                manifest.append({**row, "md_path": "", "status": "error", "error": str(exc)})
        browser.close()

    manifest_path = outdir / "markdown_manifest.csv"
    fields = sorted({k for r in manifest for k in r})
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(manifest)
    print(f"Wrote {len(manifest)} manifest rows to {manifest_path}")


if __name__ == "__main__":
    main()
