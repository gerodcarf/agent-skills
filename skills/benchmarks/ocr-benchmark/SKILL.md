---
name: ocr-benchmark
description: "Benchmark vision models on the canonical-25 corpus of pre-rasterized document pages (Statista charts, WoodMac tables, SEC filings, scanned text). Produces per-page scores, SQLite run history, and an Obsidian leaderboard. Hub: benchmark-common."
version: 0.2.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [benchmark, ocr, vision, document-extraction, tables, charts]
    related_skills: [benchmark-common, model-routing, research-enrichment, ocr-and-documents]
trigger:
  - ocr benchmark
  - benchmark vision model
  - benchmark ocr model
  - compare vision models for document extraction
  - canonical-25 benchmark
  - which model handles charts tables scanned documents best
  - test ocr model quality
---

# OCR-Vision Benchmark

Spoke skill for the **OCR / Vision** contract in `benchmark-common`. Always load `benchmark-common` before modifying or running this benchmark.

## What this benchmark evaluates

> Can a vision-capable model faithfully extract all structured content — tables, chart titles, axis labels, numeric values with units — from a mixed-format document page, without summarizing, hallucinating boilerplate, or silently failing?

This is the gate before assigning a model to the `ocr-burn` OmniRoute combo or the production PageIndex OCR backlog.

## Contract under test: `ocr-vision`

| Dimension | Description |
|---|---|
| **Profile** | Vision/OCR extraction — any endpoint with image input |
| **Input** | Pre-rasterized PNG at 150 DPI (from PyMuPDF) |
| **Output** | Clean markdown: tables, chart titles, axis labels, numeric data, verbatim text |
| **Failure modes caught** | Polite refusals ("I don't see a document"), hallucinated boilerplate, empty output, wrong image format, per-page 429/timeout |

## Corpus: canonical-25

Fixed set of 25 pre-rasterized PNGs from 4 document types, stored in `resources/pages/`:

| Source | Pages | Content type |
|---|---|---|
| Statista battery minerals dossier | 10 | Charts, TOC thumbnails, data tables |
| WoodMac lithium report | 7 | Mixed table + text |
| SEC flash-crash filing | 3 | Dense regulatory text + figures |
| Knight Risk scanned doc | 5 | Scanned raster text (no text layer) |

See `resources/pages/manifest.json` for the full page index with categories and descriptions.

**Context window:** A single PNG at 150 DPI is ~100–300 KB encoded. One page call uses at most ~10–20k tokens including system + response. 256k context is ample — no 1M window needed for per-page evaluation.

## Scoring rubric

Scoring is per-page, computed locally from response text. No LLM judge.

| Signal | Points | Detection |
|---|---|---|
| Tables present | 25 | `\|...\|` rows + `---` separator |
| Chart/figure title | 20 | `^(chart\|figure\|graph)\s*\d*[:]?` |
| Axis labels / source notes | 20 | `x-axis`, `y-axis`, `source:`, `note:` |
| Numeric values with units | 20 | `\d[\d,.]*\s*([a-zA-Z%$€£¥°]+)` |
| Minimum content length >100 chars | 15 | len(stripped response) |

**Pass threshold:** score ≥ 60 / 100 on a given page (weighted by page category from manifest).

**Invalid-output filter:** Responses matching known polite-refusal patterns (`"I don't see any document"`, `"no image attached"`, etc.) are scored 0 regardless of length.

## Running the benchmark

### Prerequisites

```bash
# Install dependencies (once)
pip install openai pymupdf

# Load env
set -a; source ~/.hermes/.env; set +a
```

### Execution

```bash
# Canonical-25 sweep, single model via OmniRoute
python3 ~/.hermes/skills/benchmarks/ocr-benchmark/scripts/ocr_cases.py \
  --provider omniroute --model gemini-cli/gemini-2.5-flash

# Via OpenRouter
python3 ~/.hermes/skills/benchmarks/ocr-benchmark/scripts/ocr_cases.py \
  --provider openrouter --model google/gemini-2.5-flash-preview

# Using the benchmark-common runner (wraps ocr_cases.py)
python3 ~/.hermes/skills/benchmarks/benchmark-common/scripts/run_benchmark.py \
  --suite ocr \
  --cases ~/.hermes/skills/benchmarks/ocr-benchmark/scripts/ocr_cases.py \
  --provider omniroute --model gemini-cli/gemini-2.5-flash

# Smoke test (1 page, fast gate)
python3 ~/.hermes/skills/benchmarks/ocr-benchmark/scripts/ocr_cases.py \
  --provider omniroute --model gemini-cli/gemini-2.5-flash \
  --smoke

# Batch multi-model (models.txt, one provider:model per line)
python3 ~/.hermes/skills/benchmarks/ocr-benchmark/scripts/ocr_cases.py \
  --model-list /tmp/models.txt --output-dir /tmp/bench/
```

### Provider routing

| Provider flag | Env var | Endpoint |
|---|---|---|
| `omniroute` | `OMNIROUTE_API_KEY` + `OMNIROUTE_URL` | `$OMNIROUTE_URL/v1` |
| `openrouter` | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| `openai` | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| `nous` | `NOUS_API_KEY` | `https://inference-api.nousresearch.com/v1` |

### Rate-limiting

- Add `--sleep 3` for free-tier Gemini (avoids 429s)
- OmniRoute `ocr-burn` combo throttles at high concurrency — use `--sleep 1` minimum

## Output and storage

Results are written to the shared benchmark SQLite DB:

```
~/.hermes/skills/benchmarks/benchmark-common/results/benchmark.db
```

Table: `ocr_benchmark_runs` — one row per page per run (run_id, model, provider, page_id, category, score, latency_ms, tokens, passed, error).

Obsidian report auto-updated at:
```
~/Obsidian/main-vault/20-Knowledge/Benchmarks/ocr-benchmark.md
```

Run the Obsidian updater after a sweep:
```bash
python3 ~/.hermes/skills/benchmarks/benchmark-common/scripts/update_obsidian_results.py \
  --suite ocr
```

## Leaderboard (as of 2026-04-28, canonical-25)

| Model | Pass rate | Avg latency | Notes |
|---|---|---|---|
| `nvidia/mistral-small-4-119b` | ~88% | 7.2s/page | Top performer |
| `gemini-cli/gemini-2.5-flash` | ~84% | 8.2s/page | Best for backlog |
| `cx/gpt-5.4-mini` | ~80% | 9.8s/page | Strong second |
| `gemini-cli/gemini-3-flash-preview` | ~60% | 6.1s/page | 8/25 empty baseline |
| `openai/gpt-4o-mini` | ~72% | 11.4s/page | Slow on 90+ page PDFs |
| `kr/claude-haiku-4.5` | 0% | — | Image input not accepted |

Update leaderboard after each sweep via `update_obsidian_results.py`.

## Adding models to the benchmark

Add a line to `resources/models-candidates.txt`:
```
omniroute:gemini-cli/gemini-2.5-flash-lite
openrouter:nvidia/llama-3.2-90b-vision-instruct
```

Then run with `--model-list resources/models-candidates.txt`.

## Pitfalls

- **Empty pages ≠ pass**: The old `benchmark.py` scored by length alone — polite refusals of ~150 chars passed. `ocr_cases.py` uses the `BAD_FALLBACKS` filter.
- **Haiku image format**: Claude Haiku 4.5 via OmniRoute rejected base64 PNGs — scored 0/25. Verify image-input support before benchmarking.
- **gemini-3-flash-preview `thought_signature`**: When routing through OmniRoute, this model may return a 400 error on tool-call payloads with missing `thought_signature`. OCR-only prompts (no tools) are unaffected.
- **`ocr-burn` 429 flooding**: The weighted combo (40% Gemini / 40% gpt-5.4-mini / 20% Mistral) throttles under sustained load. Use `--sleep 2` or lower concurrency.
- **Preset validation false positives**: Checking native PDF text layers instead of rasterized vision output can give misleading pass rates. Always use the PNG corpus.
- **Context window**: 256k is sufficient per page. Do NOT send multi-page batches — attention dilution degrades table extraction quality.
