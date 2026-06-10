# Neo4j Clerk Benchmark Rebuild — 2026-05-08

## Why this exists

The original Clerk benchmark was a brittle toy exact-match suite: Apple company fields, simple product classification, CSV metrics, and exact answer strings. It punished semantically acceptable answers and did not measure the Clerk role's real production objective: safely converting unstructured text into strict structured output that can feed Neo4j.

Gerod clarified the core requirement: Clerk's most important feature is reliable structured output for Neo4j ingestion. That drove the rebuild.

## Benchmark shape after rebuild

Script:
`~/.hermes/skills/benchmarks/clerk-benchmark/scripts/run_clerk_benchmark.py`

Current benchmark version after session:
`0.4.0-cost-estimates`

Suite:
`neo4j-v1`

The suite now has 8 scenarios targeting real failure modes:

1. `supplier_relationship_basic` — supplier/customer/product relationship direction and enum discipline.
2. `govcon_award_extraction` — agency, awardee, contract, award amount, award date, contract number, product.
3. `subsidiary_and_location` — parent/subsidiary, facility/location, technology use.
4. `negative_ambiguity_warning` — ambiguity should produce warnings, not hallucinated relationships.
5. `metric_normalization` — numeric values, currency, percentages, period/technology metrics.
6. `duplicate_entity_canonicalization` — alias/dedupe behavior for IBM / International Business Machines.
7. `material_supply_chain` — producer, supplier, dependency, facility/location, material/product chain.
8. `document_citation_spans` — document/source, constraint, organization, location, source traceability.

## Separated scoring model

The first rebuilt pass had scores around 0.85 but only 2–3/8 passes. Gerod correctly questioned whether that was a good benchmark. The issue was pass/fail conflated hard ingestion safety with semantic graph completeness.

The scoring model was split:

- `safety`: hard Neo4j ingestion readiness; averages JSON validity, strict no-repair output, schema validity, Neo4j-safe properties, and relationship reference integrity.
- `graph_quality`: required nodes, required relationships, source traceability, and dedupe.
- `domain_fidelity`: normalized properties plus ambiguity handling.
- `overall`: 50% safety, 35% graph quality, 15% domain fidelity.
- `ingestion_ready`: boolean hard-safety gate.

SQLite `passed_cases` now means ingestion-ready cases only, not semantic perfection.

## Cost estimate fix

The runner used to hardcode `cost_usd=0.0`, so benchmark results falsely showed `$0`. Version `0.4.0` fixes this:

- Fetch live OpenRouter model pricing from `https://openrouter.ai/api/v1/models`.
- Read `pricing.prompt` and `pricing.completion` as dollars/token.
- Estimate per-case cost from prompt/completion tokens.
- Store per-case `notes.cost.usd`, `notes.cost.per_100_runs_usd`, and `notes.cost.pricing_source`.
- Store run aggregate in `benchmark_runs.cost_usd`.
- Keep `cost_estimated=True` because final invoices/routing may differ slightly.

Fallback prices were added for frequently tested models:

- `qwen/qwen3-235b-a22b-2507`: prompt `$0.000000071`, completion `$0.0000001`
- `google/gemma-4-26b-a4b-it`: prompt `$0.00000006`, completion `$0.00000033`
- `stepfun/step-3.5-flash`: prompt `$0.0000001`, completion `$0.0000003`
- `openai/gpt-4o`: prompt `$0.0000025`, completion `$0.00001`

## Model results from the session

### google/gemma-4-26b-a4b-it

Best cheap candidate tested.

Run after separated scoring:
`clerk-benchmark-20260508T214747Z-41f81de6`

- Ingestion-ready: `7/8`
- Overall: `0.9093`
- Safety: `0.9750`
- Graph quality: `0.7997`
- Domain fidelity: `0.9458`
- Avg latency: `13.3s`
- Tokens: `9,794`

Fresh cost-estimate verification run:
`clerk-benchmark-20260508T220959Z-433880ed`

- Ingestion-ready: `7/8`
- Overall: `0.928`
- Avg latency: `16.3s`
- Tokens: `9,902`
- Estimated cost/run: `$0.002027`
- Estimated cost/100 runs: `$0.202701`
- Pricing source: `openrouter_catalog`

Common misses: weak exact supplier relationship modeling, GovCon contract normalization, duplicate IBM ownership/dedupe, H100/data-center facility modeling.

### qwen/qwen3-235b-a22b-2507

Good but slower fallback.

Run:
`clerk-benchmark-20260508T214505Z-2a443477`

- Ingestion-ready: `6/8`
- Overall: `0.8803`
- Safety: `0.9500`
- Graph quality: `0.7757`
- Domain fidelity: `0.8917`
- Avg latency: `20.3s`
- Tokens: `7,978`

Common misses: H100/product/facility extraction, metric normalization, duplicate IBM/watsonx modeling, document/constraint case.

### stepfun/step-3.5-flash

Disqualified on this OpenRouter route.

- With `--json-mode`, OpenRouter/DeepInfra returned HTTP 405: `json_object response format is not supported for model: stepfun-ai/Step-3.5-Flash`.
- Without `--json-mode`, the model returned empty content for every case despite token usage.
- Result: `0/8`, score `0.0`.

Do not route Clerk through `stepfun/step-3.5-flash` on OpenRouter unless a different endpoint/provider behavior is verified.

## Clerk profile cleanup from same session

The profile at `~/.hermes/profiles/clerk/` was slimmed after benchmarking:

- `config.yaml` reduced to a small OmniRoute `clerk` combo profile.
- `SOUL.md` rewritten as a general structured-output worker, not Neo4j-hardcoded and not old document-router-only behavior.
- Local skills reduced from 186 to 3: `devops/kanban-worker`, `data-science/neo4j-http`, `note-taking/obsidian`.
- Archive/rollback snapshot: `~/.hermes/profiles/clerk/archive/20260508-175825`.

Key lesson: keep Neo4j schema details in the task prompt; keep the Clerk profile generally focused on strict structured output.
