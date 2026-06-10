# Antigravity OmniRoute Clerk benchmark runs — 2026-05-21

Session-specific comparison for the `clerk-benchmark` against new OmniRoute Antigravity routes. Use as a quick calibration reference before choosing Clerk routing defaults.

## Commands used

Preflight each route first:

```bash
python3 ~/.hermes/skills/devops/model-ping/ping.py omniroute '<model>'
```

Then run the benchmark with strict JSON mode:

```bash
python3 ~/.hermes/skills/benchmarks/clerk-benchmark/scripts/run_clerk_benchmark.py \
  --provider omniroute \
  --model '<model>' \
  --db ~/.hermes/data/benchmarks/clerk/benchmark.db \
  --obsidian-dir "$HOME/Obsidian/Main Vault/40-Operations/Hermes/Benchmarks/clerk-benchmark" \
  --temperature 0 \
  --max-tokens 2048 \
  --timeout 120 \
  --max-retries 2 \
  --json-mode
```

## Results

| Model | Ping | Score | Pass | Avg ms | Tokens | Notes |
|---|---:|---:|---:|---:|---:|---|
| `antigravity/gemini-2.5-flash-lite` | ok, 1.33s | 0.8876 | 6/8 | 2852 | 25,821 | Best Clerk candidate in this set. |
| `antigravity/gemini-3.1-flash-lite` | ok, 2.44s | 0.8724 | 6/8 | 2370 | 25,822 | Faster than 2.5 Flash Lite but slightly worse extraction. |
| `antigravity/gemini-3.5-flash-preview` | ok, 2.57s | 0.0000 | 0/8 | 3258 | 37,459 | Not viable for this suite; produced no usable scored JSON/notes despite completing. |
| `antigravity/gemini-3.5-flash` | 404 | n/a | n/a | n/a | n/a | Alias not available at time of run. |
| `antigravity/gpt-oss-120b-medium` | timeout, then 502 empty content | n/a | n/a | n/a | n/a | Did not run full benchmark because minimal ping failed. |

## Common failure modes for the passing Flash Lite models

The two viable Flash Lite models both passed 6/8 and tended to fail or lose points on the same harder graph-ingestion cases:

- `document_citation_spans`: missed `Location: Loudoun County` and `Constraint: interconnection`; schema-invalid.
- `subsidiary_and_location`: missed `Location: Northern Virginia`, `Product: H100`, and `LOCATED_IN`; schema-invalid.
- `duplicate_entity_canonicalization`: weak dedupe around `watsonx` / `watsonx.governance`, missed `OWNS`, and emitted too many organization nodes.
- `govcon_award_extraction`: missed contract-number-as-Contract node, `FUNDED_BY`, and numeric/currency normalization on award amount.

## Operational lessons

- The Clerk benchmark does **not** require tool use/function calling. It is a pure structured-output JSON extraction benchmark.
- For new OmniRoute aliases, do not start the full benchmark until a minimal `model-ping` succeeds. Timeout/502/404 routes should be treated as route availability failures, not model quality results.
- Use `notify_on_complete=true` for full benchmark runs, then read `benchmark_runs` and `benchmark_cases.notes` from the SQLite DB for concrete per-case failures.
- A completed run with `score=0.000` and unparseable/empty case notes is usually a structured-output failure, not a meaningful graph-quality score.
