#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Extract microorganism temperature traits from Markdown with an LLM.

The API is OpenAI-compatible. Configure it with:
  LLM_API_KEY, LLM_API_URL, LLM_MODEL
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib import request

from tqdm import tqdm


DEFAULT_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"

SYSTEM_PROMPT = """You extract microorganism growth-condition data from taxonomy articles.
Return strict JSON only. Do not invent values. Use null when a value is absent.
Temperature values must preserve the article evidence and use Celsius units."""

USER_TEMPLATE = """Extract all microorganism species or strain records from this article.

Return this JSON schema:
{
  "article": {"doi": string|null, "title": string|null, "year": string|null},
  "species_detail_list": [
    {
      "species_name": string|null,
      "taxon_rank": string|null,
      "type_strain": string|null,
      "strains": string|null,
      "isolation_source": string|null,
      "isolation_location": string|null,
      "temperature_min": string|null,
      "temperature_opt": string|null,
      "temperature_max": string|null,
      "temperature_evidence": string|null,
      "confidence": "high"|"medium"|"low"
    }
  ]
}

Article Markdown:
```markdown
{markdown}
```"""


def load_cache(path: Path) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    if not path.exists():
        return cache
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            cache[row["key"]] = row["value"]
    return cache


def append_cache(path: Path, key: str, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "value": value}, ensure_ascii=False) + "\n")


def json_from_text(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def call_llm(markdown: str, api_key: str, api_url: str, model: str, timeout: int = 180) -> dict:
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(markdown=markdown)},
        ],
    }
    req = request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    return json_from_text(content)


def process_file(md_path: Path, outdir: Path, cache_path: Path, cache: dict[str, dict], args) -> tuple[str, str]:
    markdown = md_path.read_text(encoding="utf-8", errors="replace")
    key = hashlib.sha256((args.model + "\n" + markdown).encode("utf-8")).hexdigest()
    rel_name = md_path.with_suffix(".json").name
    out_path = outdir / rel_name
    if key in cache:
        result = cache[key]
    else:
        last_error = None
        for attempt in range(1, args.retries + 1):
            try:
                result = call_llm(markdown, args.api_key, args.api_url, args.model, args.timeout)
                append_cache(cache_path, key, result)
                break
            except Exception as exc:
                last_error = exc
                time.sleep(args.sleep * attempt)
        else:
            result = {"article": {}, "species_detail_list": [], "error": str(last_error)}
    result["_source_markdown"] = str(md_path)
    result["_prompt_version"] = "temperature-extraction-v1"
    result["_model"] = args.model
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(md_path), str(out_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--markdown-root", required=True)
    parser.add_argument("--outdir", default="data/llm_json")
    parser.add_argument("--cache", default="data/cache.jsonl")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--api-url", default=os.getenv("LLM_API_URL", DEFAULT_API_URL))
    parser.add_argument("--model", default=os.getenv("LLM_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-key", default=os.getenv("LLM_API_KEY", ""))
    args = parser.parse_args()
    if not args.api_key:
        raise SystemExit("Missing API key. Set LLM_API_KEY or pass --api-key.")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    cache_path = Path(args.cache)
    cache = load_cache(cache_path)
    files = sorted(Path(args.markdown_root).rglob("*.md"))

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(process_file, p, outdir, cache_path, cache, args) for p in files]
        for _ in tqdm(as_completed(futures), total=len(futures), desc="LLM extraction"):
            _.result()
    print(f"Wrote JSON outputs to {outdir}")


if __name__ == "__main__":
    main()
