# OCR-Vision Benchmark Rubric

## Contract under test

An OCR/vision model receives a pre-rasterized PNG (150 DPI) from a document page containing one or more of: data tables, bar/line charts, scanned text, mixed layout. It must return faithful markdown extraction.

The core question is:

> Can this model faithfully transcribe all structured content — tables, chart titles, axis labels, numeric values with units, verbatim text — without summarizing, hallucinating boilerplate, or silently refusing?

This gate determines which models are safe to assign to the `ocr-burn` OmniRoute combo and the production PageIndex OCR backlog.

## Scoring dimensions (per page, 0–100 pts)

| Dimension | Points | Signal |
|---|---|---|
| **Tables present** | 25 | `\|...\|` rows + `---` separator in response |
| **Chart / figure title** | 20 | `^(chart\|figure\|graph)\s*\d*[:]?` match |
| **Axis labels / source notes** | 20 | `x-axis`, `y-axis`, `source:`, `note:` match |
| **Numeric values with units** | 20 | `\d[\d,.]*\s*([a-zA-Z%$€£¥°]+)` match |
| **Minimum content** | 15 | `len(stripped_response) > 100` |
| **Category bonus** | 20 | Scanned text: content-only pass; chart/table: any structure signal |

**Pass threshold:** ≥ 60 / 100 per page.

**Hard zero — polite refusal filter**: Responses containing known fallback phrases (`"I don't see any document"`, `"no image attached"`, etc.) are scored 0 regardless of length. This prevents polite ~150-char refusals from passing the old length-only heuristic.

## Page categories (from manifest.json)

| Category | Typical content | Primary scoring signals |
|---|---|---|
| `chart` | Bar/line charts with axis labels | chart title + axis labels + numerics |
| `table` | Data grids, comparison tables | table rows + numerics |
| `mixed` | Text + embedded figures | content length + any structural signal |
| `scanned_text` | Raster scan, no PDF text layer | content length (category bonus applied) |

## Pass gate for production use

A model should achieve **≥ 75% pass rate** on canonical-25 before assignment to `ocr-burn`. Below 60% → reject. 60–75% → conditional (use only for text-heavy pages, not Statista/WoodMac chart dossiers).

## Known failure modes

| Failure | Root cause | Example |
|---|---|---|
| 0% pass, polite refusals | Image not received (wrong MIME type, base64 encoding error, model is text-only) | Claude Haiku 4.5 via OmniRoute |
| Empty pages (0 chars) | Model received image but silently did not respond | gemini-3-flash-preview (8/25 empty) |
| Hallucinated boilerplate | Model generates plausible-looking generic tables | Check response for "Acme Corp", generic axis labels |
| `thought_signature` 400 | Gemini model + tool-call payload via OmniRoute | OCR-only prompts (no tools) unaffected |
| 429 rate limit | Free-tier quota exhausted | Add `--sleep 3`; lower concurrency |
