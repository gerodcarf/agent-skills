# Benchmark Page Presets

Fixed page sets for reproducible vision model benchmarking.

## Why presets?

Random page sampling means each run tests different content → noisy results. Fixed presets let you:
- Compare models apples-to-apples on identical pages
- Track quality drift across model versions
- Validate a new provider's OCR quality using the same stress-test pages

## Available presets

| Name | Document | Pages | Characteristics |
|------|----------|-------|-----------------|
| `statista-battery-minerals` | Statista Global Battery Minerals 2026 | [0,1,11,12,22,23,33,34,41,42] (10p) | Pure chart/graph dossier — worst-case for vision |
| `woodmac-solar` | WoodMac Solar Market Insight | [0,2,5,8,9,12,15,16] (8p) | Mixed tables + graphics, industry research |
| `sec-flash-crash` | SEC Flash Crash Preliminary Report | all 5 pages | Government report with figures + text |
| `loudoun-planning-agenda` | Loudoun County Planning Agenda | spaced across doc (~8p) | Agenda tables with extracted-text overlay |

## Usage

```bash
# Benchmark using the Statista preset (10 fixed pages)
ocr-benchmark --preset statista-battery-minerals --model openrouter/gpt-4o-mini --sleep 2

# Compare two models on the exact same pages
ocr-benchmark --preset woodmac-solar --model openrouter/gpt-4o-mini --output /tmp/woodmac_gpt.json
ocr-benchmark --preset woodmac-solar --model openrouter/llama-4-scout --output /tmp/woodmac_llama.json
```

## Adding new presets

Edit `resources/presets.json` with `{ "preset-name": { "pdf_path": "relative/path.pdf", "pages": [0,5,10], "description": "..." } }`.