# OpenRouter strict JSON caveat — GPT-4o / Gemini Flash

Session date: 2026-05-08

## What happened

Clerk benchmark was run through OpenRouter with:

- `~google/gemini-flash-latest`
- `openai/gpt-4o`

Both failed the strict exact-match Clerk benchmark under the current harness.

## Key observations

1. OpenRouter dynamic model IDs with a leading tilde must be shell-quoted.
   - Correct: `--model '~google/gemini-flash-latest'`
   - Incorrect: `--model google/gemini-flash-latest` returned model-not-found.

2. Loading `~/.hermes/.env` may be required before direct benchmark runs outside Hermes env-loader.
   - Symptom without key: OpenRouter 401 `No cookie auth credentials found`.
   - Working shell pattern:
     `set -a; . ~/.hermes/.env >/dev/null 2>&1; set +a; ...`

3. The current Clerk harness is prompt-only and does not pass OpenAI/OpenRouter `response_format`.
   - GPT-4o returned fenced JSON/CSV in normal chat mode despite “return ONLY” prompting.
   - Ad-hoc `response_format: {"type":"json_object"}` removed JSON fences but did not guarantee exact field values or array top-level shape.

4. Strict JSON validity is not the same as exact benchmark pass.
   Common failure modes:
   - Markdown fences around otherwise valid JSON.
   - Synonym drift: `supplies` vs expected `supplier`.
   - Plausible enrichment: adding `United States`, extra camera details, etc.
   - CSV normalization drift: `394 billion` vs expected numeric `394`.
   - JSON mode forcing object-style output where the task expects a top-level array.

## Runs

- Gemini Flash latest via OpenRouter:
  - Run ID: `clerk-benchmark-20260508T205615Z-3d37cc47`
  - Score: 1/5, avg latency 1395 ms.

- GPT-4o via OpenRouter prompt-only:
  - Run ID: `clerk-benchmark-20260508T211138Z-8a762300`
  - Score: 0/5, avg latency 1250 ms.

## Recommendation

For strict JSON benchmarking, update the harness rather than trusting prompt wording:

- Add optional `--response-format json_object` / provider-specific schema flags.
- For top-level arrays, either wrap expected output in an object schema or avoid JSON object mode.
- Preserve exact-match scoring, but separately record `json_valid` / `csv_valid` so schema adherence and semantic exactness are not conflated.
- Validate, normalize only if the benchmark explicitly allows it, then retry with a stricter repair prompt if production workflow requires valid structure.