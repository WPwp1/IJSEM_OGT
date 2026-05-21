#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Fetch IJSEM article metadata by volume.

The script uses Playwright because the journal pages can render links
dynamically. It writes one CSV row per article.
"""

from __future__ import annotations

import argparse
import csv
import re
import time
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from tqdm import tqdm


BASE_URL = "https://www.microbiologyresearch.org"
JOURNAL_URL = f"{BASE_URL}/content/journal/ijsem"
FIELDS = ["doi", "url", "title", "year", "volume", "issue", "article_type"]


def parse_volume_list(value: str) -> list[str]:
    return [x.strip() for x in re.split(r"[,\s]+", value) if x.strip()]


def accept_cookies(page) -> None:
    for selector in ["button#onetrust-accept-btn-handler", "text=Accept cookies", "text=Accept"]:
        try:
            page.click(selector, timeout=1200)
            return
        except Exception:
            continue


def goto(page, url: str, wait: float = 0.5) -> str:
    page.goto(url, timeout=60000)
    page.wait_for_load_state("networkidle")
    accept_cookies(page)
    time.sleep(wait)
    return page.content()


def issue_urls(page, volume: str) -> list[tuple[str, str]]:
    html = goto(page, f"{JOURNAL_URL}/issueslist?volume={volume}&showDates=false")
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, str] = {}
    pattern = re.compile(rf"/content/journal/ijsem/{re.escape(volume)}/[^/?#]+")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if pattern.search(href):
            url = urljoin(BASE_URL, href.split("?")[0])
            label = " ".join(a.get_text(" ", strip=True).split())
            out[url] = label
    return sorted(out.items())


def max_page_for_issue(page, issue_url: str) -> int:
    html = goto(page, f"{issue_url}?page=1")
    pages = [int(x) for x in re.findall(r"page=(\d+)", html)]
    return max(pages) if pages else 1


def article_rows_from_issue_page(html: str, volume: str, issue: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: dict[str, dict[str, str]] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/content/journal/ijsem/10.1099/" not in href:
            continue
        url = urljoin(BASE_URL, href.split("?")[0])
        doi_match = re.search(r"10\.1099/[^/?#]+(?:\.[^/?#]+)*", url)
        doi = doi_match.group(0) if doi_match else ""
        title = " ".join(a.get_text(" ", strip=True).split())
        if not title or len(title) < 8:
            continue
        rows[url] = {
            "doi": doi,
            "url": url,
            "title": title,
            "year": "",
            "volume": volume,
            "issue": issue,
            "article_type": "",
        }
    return list(rows.values())


def enrich_article(page, row: dict[str, str]) -> dict[str, str]:
    try:
        html = goto(page, row["url"], wait=0.2)
    except Exception:
        return row
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if h1:
        row["title"] = " ".join(h1.get_text(" ", strip=True).split())
    article_type = soup.select_one("h4.article-type")
    if article_type:
        row["article_type"] = article_type.get_text(" ", strip=True)
    text = soup.get_text(" ", strip=True)
    year_match = re.search(r"\b(19|20)\d{2}\b", text)
    if year_match:
        row["year"] = year_match.group(0)
    return row


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDS})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--volumes", required=True, help="Comma-separated IJSEM volume numbers, e.g. 70,71,72")
    parser.add_argument("--out", default="data/raw/ijsem_articles.csv")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--enrich", action="store_true", help="Open each article page to fill title/year/article_type")
    args = parser.parse_args()

    rows: dict[str, dict[str, str]] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        page = browser.new_page()
        for volume in parse_volume_list(args.volumes):
            for issue_url, issue_label in tqdm(issue_urls(page, volume), desc=f"volume {volume}"):
                issue = issue_url.rstrip("/").split("/")[-1]
                for page_no in range(1, max_page_for_issue(page, issue_url) + 1):
                    html = goto(page, f"{issue_url}?page={page_no}")
                    for row in article_rows_from_issue_page(html, volume, issue_label or issue):
                        rows[row["url"]] = row
        if args.enrich:
            for url in tqdm(list(rows), desc="enrich"):
                rows[url] = enrich_article(page, rows[url])
        browser.close()

    write_csv(Path(args.out), list(rows.values()))
    print(f"Wrote {len(rows)} article rows to {args.out}")


if __name__ == "__main__":
    main()
