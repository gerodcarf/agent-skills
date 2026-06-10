# OmniRoute + Cerebras Clerk benchmark rate-limit note — 2026-05-09

## Context

Attempted to benchmark `cerebras/qwen-3-235b-a22b-instruct-2507` for Clerk Neo4j ingestion readiness.

## What went wrong

1. Direct `--provider openrouter` produced an invalid benchmark run:
   - All cases failed with `HTTP 401: {"error":{"message":"No cookie auth credentials found","code":401}}`.
   - Tokens/cost were zero; this measures auth failure, not model quality.

2. Correct path for this setup was `--provider omniroute` with the same model ID.

3. Raw sustained Cerebras lane hit RPM limits through OmniRoute:
   - Frequent `HTTP 429 ... Requests per minute limit exceeded ... reset after 3s`.
   - A full standalone 8-case run stalled even with pacing/retries.

4. The runner had a bug: `--max-retries` existed in common args but was ignored by `run_clerk_benchmark.py`.
   - Patched the script to retry 429s and add an OmniRoute inter-case delay.

## Useful signal despite failed full run

Partial paced runs showed the model can produce ingestion-ready Clerk output on several cases:

- `supplier_relationship_basic`: PASS, approx score `0.877`
- `metric_normalization`: PASS, approx score `0.935`
- `duplicate_entity_canonicalization`: PASS, approx score `0.749`
- `material_supply_chain`: PASS, approx score `0.969`

But standalone throughput is not representative of intended production usage.

## Routing implication

Use Cerebras Qwen selectively in a Clerk combo, not as the primary lane:

- low round-robin weight / small percentage of traffic
- hard cooldown / retry behavior around 429s
- paid providers as the backbone
- benchmark the actual combo, not just the raw Cerebras lane, when evaluating production suitability

## Hygiene

Mark direct OpenRouter 401 runs and stalled 429 runs as failed/invalid; do not include them as model-quality results in recommendations.
