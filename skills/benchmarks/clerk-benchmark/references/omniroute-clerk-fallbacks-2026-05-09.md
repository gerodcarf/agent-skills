# OmniRoute Clerk Fallback Notes — 2026-05-09

## Context

Session tested strict JSON / Neo4j ingestion readiness fallback candidates for the Clerk role through OmniRoute.

## Key Workflow Correction

For Gerod's setup, run Clerk benchmark candidates through `--provider omniroute`, not direct `--provider openrouter`, unless explicitly testing direct OpenRouter behavior.

Direct OpenRouter run against `cerebras/qwen-3-235b-a22b-instruct-2507` failed with:

```text
HTTP 401: {"error":{"message":"No cookie auth credentials found","code":401}}
```

That produced a fake 0-score benchmark. Treat such rows as auth failures, not model results.

## Cerebras Qwen via OmniRoute

Model:

```text
cerebras/qwen-3-235b-a22b-instruct-2507
```

Findings:

- Reachable through OmniRoute, but sustained full-suite benchmark traffic triggers repeated 429s.
- Raw standalone lane is not representative if intended production use is low-weight combo membership.
- Partial paced run showed real Clerk promise:
  - `supplier_relationship_basic`: PASS, score 0.877
  - `metric_normalization`: PASS, score 0.935
  - `duplicate_entity_canonicalization`: PASS, score 0.749
  - `material_supply_chain`: PASS, score 0.969
- Operational conclusion: use as opportunistic low-weight capacity in a balanced combo, not as primary Clerk lane.

## Gemini Flash-Lite via OmniRoute

Model:

```text
gemini/gemini-2.5-flash-lite
```

Full Clerk benchmark result:

```text
run_id: clerk-benchmark-20260509T122747Z-09150ad9
provider: omniroute
score: 0.89575
pass: 7/8 ingestion-ready
avg_latency_ms: 2659
prompt_tokens: 20499
completion_tokens: 5560
total_tokens: 26059
estimated_cost_usd: 0.004274
```

Pricing assumption used for manual DB/Obsidian cost update:

```text
input:  $0.10 / 1M tokens
output: $0.40 / 1M tokens
```

Only ingestion-gate failure:

```text
supplier_relationship_basic emitted relationship type SUPPLIED_TO instead of allowed enum SUPPLIES
```

Interpretation: Flash-Lite is strong cheap strict-JSON fallback. Its main error is enum drift, which is easier to handle with prompt tightening or post-normalization than malformed JSON.

## Recommended Clerk Fallback Shape

- Primary/paid backbone: stable paid provider/model combo.
- Cheap strict JSON fallback: `gemini/gemini-2.5-flash-lite`.
- Opportunistic low-weight capacity: Cerebras Qwen, with cooldown/rate-limit protection.
- Test Grok mini separately before relying on it; ping worked for `xai/grok-3-mini`, but strict Clerk benchmark was not run in this session.

## Runner Fix Applied

The Clerk benchmark CLI accepted `--max-retries`, but the script did not actually use it around `chat_completion`. The runner was patched to retry retryable HTTP 429 responses and honor reset-after seconds when present. It also adds an OmniRoute inter-case delay to avoid hammering rate-limited providers.

Future improvement: make inter-case delay a CLI flag instead of hardcoded provider-specific sleep.
