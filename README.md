# IJSEM_OGT
Extract the IJSEM microbial physiological information database using LLM

This directory documents a minimal reproducible workflow from the IJSEM website to a structured CSV table. The workflow contains four stages:

1. Crawl IJSEM article metadata
2. Download article pages and convert them to Markdown
3. Use an LLM to extract structured microbial information from Markdown
4. Merge per-article JSON outputs into a unified CSV table

This public workflow corresponds to the data-extraction part of our study. 

## What This Part Does

From input to output, this workflow performs the following steps:

- crawl article-level metadata from the IJSEM website
- download article full-text pages
- convert article text, section headings, and tables into Markdown
- call an OpenAI-compatible LLM API for structured extraction
- write one JSON output per article
- merge article-level JSON outputs into an analysis-ready CSV file

The extracted information retained in this workflow includes:

- article metadata: DOI, title, year, volume, issue, URL, and article type
- microbial identity: species name, taxon rank, type strain, and strain aliases
- ecological context: isolation source and isolation location
- temperature information: minimum, optimum, and maximum growth temperatures, plus evidence text
- extraction quality label: confidence

The public file [data/ijsem_llm_extracted_microbe_records.csv] represents a broader internal extraction result. In addition to temperature, it also includes fields such as `pH`, `NaCl`, oxygen preference, Gram stain, morphology, motility, spore formation, pigmentation, and molecular accession identifiers.

## Environment Setup

We recommend using an isolated Python environment.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r web/requirements-web.txt
playwright install chromium
```

The LLM extraction stage also requires an OpenAI-compatible API configuration:

- `LLM_API_KEY`
- `LLM_API_URL`
- `LLM_MODEL`

If not explicitly set:

- `LLM_API_URL` defaults to `https://api.deepseek.com/v1/chat/completions`
- `LLM_MODEL` defaults to `deepseek-chat`

## Step 1: Crawl IJSEM Article Metadata

Script:

- [01_fetch_ijsem_articles.py]

This script performs the following tasks:

1. open the IJSEM volume page
2. enumerate all issues under the specified volume(s)
3. crawl all article entries from each issue
4. parse DOI, title, URL, volume, issue, year, and article type for each article

### Input

- one or more volume identifiers, for example `70,71,72`

### Output

- a CSV file, for example `data/raw/ijsem_articles.csv`

### Output Fields

- `doi`
- `url`
- `title`
- `year`
- `volume`
- `issue`
- `article_type`

### Example Commands

Single volume:

```bash
python web/scripts/01_fetch_ijsem_articles.py --volumes 76 --out data/raw/ijsem_articles_v76.csv --headless --enrich
```

Multiple volumes:

```bash
python web/scripts/01_fetch_ijsem_articles.py --volumes 70,71,72,73,74,75,76 --out data/raw/ijsem_articles.csv --headless --enrich
```

### Implementation Notes

This script uses Playwright rather than simple `requests`, because links and pagination on the IJSEM website are more reliably handled in a browser environment.

Key internal logic includes:

- automatically accepting cookie popups
- enumerating issue URLs for each volume
- detecting issue pagination
- extracting article URLs and DOIs from issue pages
- optionally visiting article pages again to enrich title, year, and article type

## Step 2: Download Article Pages and Convert Them to Markdown

Script:

- [02_articles_to_markdown.py]

This script performs the following tasks:

1. read the article metadata CSV from Step 1
2. open each article URL
3. locate the main article content area
4. convert headings, metadata, paragraphs, and tables into Markdown
5. save one `.md` file per article
6. generate a `markdown_manifest.csv` file to record success or failure status

### Input

- the article metadata CSV produced in Step 1

### Output

- `data/markdown/<year>/<issue>/md/*.md`
- `data/markdown/markdown_manifest.csv`

### Markdown Content Includes

- article title
- metadata such as DOI, year, volume, issue, URL, and article type
- section headings
- paragraph text
- HTML tables converted into Markdown tables

### Example Command

```bash
python web/scripts/02_articles_to_markdown.py --articles data/raw/ijsem_articles.csv --outdir data/markdown --headless
```
The purpose of this step is not perfect visual formatting. Instead, it aims to preserve stable and reusable structured article text for downstream information extraction.

## Step 3: Use an LLM to Perform Structured Extraction from Markdown

Script:

- [03_extract_temperature_llm.py]

This script performs the following tasks:

1. recursively read all `.md` files under `markdown-root`
2. send each article Markdown file to an OpenAI-compatible LLM
3. extract article-level and species-level information using a fixed JSON schema
4. write one `.json` output per article
5. cache successful requests to avoid repeated API calls

### Input

- the Markdown directory produced in Step 2, for example `data/markdown`

### Output

- `data/llm_json/*.json`
- `data/cache.jsonl`

### Core Fields Extracted by the Public Script

- `article.doi`
- `article.title`
- `article.year`
- `species_name`
- `taxon_rank`
- `type_strain`
- `strains`
- `isolation_source`
- `isolation_location`
- `temperature_min`
- `temperature_opt`
- `temperature_max`
- `temperature_evidence`
- `confidence`

### Example Commands
```bash
export LLM_API_KEY="your_api_key"
export LLM_API_URL="https://api.deepseek.com/v1/chat/completions"
export LLM_MODEL="deepseek-chat"

python web/scripts/03_extract_temperature_llm.py \
  --markdown-root data/markdown \
  --outdir data/llm_json \
  --cache data/cache.jsonl \
  --workers 4
```

## Step 4: Merge Per-Article JSON Files into a Unified CSV

Script:

- [04_merge_llm_json.py]

This script performs the following tasks:

1. recursively read all `.json` outputs from Step 3
2. expand `species_detail_list` into one row per extracted record
3. combine article-level fields with species-level fields
4. write a unified CSV table for downstream filtering, checking, and analysis

### Input

- the `data/llm_json` directory produced in Step 3

### Output

- `data/temperature_records_raw.csv`

### Major Output Field Groups

- JSON and provenance fields:
  `json_path`, `source_markdown`, `record_index`, `prompt_version`, `model`
- article fields:
  `doi`, `title`, `year`, `url`, `volume`, `issue`, `article_type`
- species and temperature fields:
  `species_name`, `taxon_rank`, `type_strain`, `strains`,
  `isolation_source`, `isolation_location`,
  `temperature_min`, `temperature_opt`, `temperature_max`,
  `temperature_evidence`, `confidence`

### Example Command

```bash
python web/scripts/04_merge_llm_json.py --input data/llm_json --output data/temperature_records_raw.csv
```

### Implementation Notes

This step does not yet perform final temperature normalization or cross-paper deduplication. Its role is to convert per-article JSON outputs into a structured raw table that can be inspected, filtered, and further processed.

## Full Reproducible Workflow

To reproduce the public minimal structured-extraction workflow from the IJSEM website, run the following steps in order.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r web/requirements-web.txt
playwright install chromium

export LLM_API_KEY="your_api_key"
export LLM_API_URL="https://api.deepseek.com/v1/chat/completions"
export LLM_MODEL="deepseek-chat"

python web/scripts/01_fetch_ijsem_articles.py --volumes 70,71,72,73,74,75,76 --out data/raw/ijsem_articles.csv --headless --enrich
python web/scripts/02_articles_to_markdown.py --articles data/raw/ijsem_articles.csv --outdir data/markdown --headless
python web/scripts/03_extract_temperature_llm.py --markdown-root data/markdown --outdir data/llm_json --cache data/cache.jsonl --workers 4
python web/scripts/04_merge_llm_json.py --input data/llm_json --output data/temperature_records_raw.csv
```

## Recommended Output Checks

we recommend checking the following outputs:

1. whether `ijsem_articles.csv` contains DOI, title, and URL
2. whether most rows in `markdown_manifest.csv` have `status = ok`
3. whether `.md` files were generated under `data/markdown/<year>/<issue>/md/`
4. whether per-article `.json` files were generated under `data/llm_json/`
5. whether `cache.jsonl` continues to grow during extraction
6. whether `temperature_records_raw.csv` contains merged species-level rows

## Notes

- the scripts in this directory provide the minimal public workflow
- This directory already covers the full public workflow from website crawling to minimal LLM-based structured extraction，and `data/ijsem_llm_extracted_microbe_records.csv` represents the result of above extraction work.
- The complete Supplementary Table 1 was derived from `data/ijsem_llm_extracted_microbe_records.csv` through temperature standardization, outlier filtering, cross-source deduplication, and conflict resolution.

