# OpenRouter `~google/gemini-flash-latest` clerk benchmark note — 2026-05-08

## What happened

Requested target: provider `openrouter`, model `~google/gemini-flash-latest`.

Initial run without resolving Hermes env failed every case:

```text
HTTP 401: {"error":{"message":"No cookie auth credentials found","code":401}}
```

Sourcing `~/.hermes/.env` fixed auth, but using `google/gemini-flash-latest` without the leading tilde failed:

```text
HTTP 400: {"error":{"message":"google/gemini-flash-latest is not a valid model ID","code":400}}
```

OpenRouter `/v1/models` listed the actual ID as:

```text
~google/gemini-flash-latest
```

Known-good command shape:

```bash
set -a; . ~/.hermes/.env >/dev/null 2>&1; set +a
MODEL='~google/gemini-flash-latest'
python3 ~/.hermes/skills/benchmarks/clerk-benchmark/scripts/run_clerk_benchmark.py \
  --provider openrouter \
  --model "$MODEL" \
  --db ~/.hermes/data/benchmarks/clerk/benchmark.db \
  --obsidian-dir "~/Obsidian/Main Vault/40-Operations/Hermes/Benchmarks/clerk-benchmark" \
  --temperature 0 \
  --max-tokens 1024 \
  --timeout 60
```

## Observed result

Run ID: `clerk-benchmark-20260508T205615Z-3d37cc47`

Summary:

```text
score=0.200 pass=1/5 avg_ms=1395 tokens=797 cost=$0.000000
```

Failure modes:

- `company_apple`: fenced JSON and field/value drift.
- `financial_metrics`: values included `billion`; used `net income` instead of `net_income`.
- `entity_relationships`: fenced JSON and `relationship_type: supplies` instead of expected `supplier`.
- `iphone_research`: mostly factual but too verbose for exact-match scorer.

Conclusion: this alias was a poor strict Clerk candidate under the exact-schema benchmark because it added formatting/verbosity and drifted on required values.
