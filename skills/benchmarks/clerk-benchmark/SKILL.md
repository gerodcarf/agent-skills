---
name: clerk-benchmark
description: "Neo4j ingestion-readiness benchmark for the Clerk role: messy text -> strict graph JSON with schema validity, Neo4j-safe properties, entity/relationship extraction, source spans, ambiguity handling, and dedupe checks."
version: 0.4.0
author: Hermes Agent
license: MIT
tags: [clerk, extraction, json, benchmark, neo4j, knowledge-graph, ingestion]
related_skills: [cheap-model-benchmark, bouncer-benchmark, model-benchmark, neo4j-http]
triggers: [structured extraction, classification, research, clerk work, neo4j ingestion, graph extraction]
pinned: false
---

# Clerk Benchmark — Neo4j Ingestion Readiness

## Purpose

The Clerk's real job is not toy exact-match JSON. It takes unstructured text and emits strict, machine-ingestible graph JSON that can feed Neo4j without breaking the pipeline.

This benchmark evaluates whether a model can produce:

- valid JSON with no markdown fences or prose
- exact top-level shape: `nodes`, `relationships`, `warnings`
- allowed Neo4j labels and relationship types
- Neo4j-safe property values: scalar or scalar arrays only, no nested property objects
- non-empty temp IDs and relationship references that point to existing nodes
- confidence values between 0 and 1
- source spans for traceability
- normalized dates/money/metrics where obvious
- warnings instead of hallucinated relationships when the source is ambiguous
- basic entity canonicalization/dedupe

## Output Contract

Models are prompted to return only:

```json
{
  "nodes": [
    {
      "temp_id": "stable_snake_case_id",
      "labels": ["Organization"],
      "properties": {"name": "Example Corp"},
      "confidence": 0.95,
      "source_span": "exact quote from source"
    }
  ],
  "relationships": [
    {
      "start_temp_id": "example_corp",
      "end_temp_id": "product_x",
      "type": "MANUFACTURES",
      "properties": {},
      "confidence": 0.85,
      "source_span": "exact quote from source"
    }
  ],
  "warnings": []
}
```

Allowed labels:
`Agency`, `Capability`, `Constraint`, `Contract`, `Document`, `Event`, `Facility`, `Location`, `Material`, `Metric`, `Opportunity`, `Organization`, `Person`, `Product`, `Program`, `Project`, `Technology`.

Allowed relationship types:
`APPLIES_TO`, `AWARDED_TO`, `COMPETES_WITH`, `CUSTOMER_OF`, `DEPENDS_ON`, `FUNDED_BY`, `HAS_CAPABILITY`, `HAS_EVENT`, `HAS_METRIC`, `LOCATED_IN`, `MANUFACTURES`, `MENTIONS`, `OPERATES`, `OWNS`, `PARTNERS_WITH`, `PRODUCES`, `REGULATES`, `SUBSIDIARY_OF`, `SUPPLIES`, `USES_TECHNOLOGY`.

## Scenario Suite: `neo4j-v1`

The rebuilt suite has 8 scenarios designed to expose Clerk failure points:

1. `supplier_relationship_basic`
   - Basic supplier/customer/product extraction.
   - Catches relationship direction and enum drift.

2. `govcon_award_extraction`
   - Agency, contractor, contract, award amount, date, contract number, product.
   - Catches contract normalization and GovCon schema failures.

3. `subsidiary_and_location`
   - Parent/subsidiary, facility/location, technology usage.
   - Catches missed facility nodes and multi-hop graph extraction.

4. `negative_ambiguity_warning`
   - Ambiguous prime contractor source.
   - Catches hallucinated relationships; requires structured warning.

5. `metric_normalization`
   - Revenue, currency, percentage, period, technology contribution.
   - Catches numeric type safety and invalid relation labels.

6. `duplicate_entity_canonicalization`
   - IBM alias/entity duplication.
   - Catches duplicate org nodes and missing product ownership.

7. `material_supply_chain`
   - Materials, facility/location, supplier agreement, dependency chain.
   - Catches supply-chain relationship extraction and illegal relation types.

8. `document_citation_spans`
   - Document/source, organization, location, constraint, traceability.
   - Catches missing Document/Constraint nodes and source-span discipline.

## Scoring Dimensions

Session-specific implementation notes and model results from the Neo4j rebuild/profile cleanup are in `references/neo4j-clerk-scoring-and-profile-cleanup-2026-05-08.md`.

Each case stores JSON in `benchmark_cases.notes` with `score_dimensions` and failures:

- `json_valid` — output parses as JSON
- `strict_no_repair` — no markdown fence stripping or JSON extraction repair needed
- `schema_valid` — required top-level arrays, required node/relationship fields, allowed enums, enough nodes/rels
- `neo4j_property_safe` — all properties are Neo4j-safe scalar/scalar-array values
- `reference_integrity` — every relationship points to existing node temp IDs
- `required_nodes` — fraction of expected core nodes found
- `required_relationships` — fraction of expected core relationships found
- `required_properties` — fraction of key normalized properties found
- `ambiguity_handling` — warnings present and forbidden hallucinated relationships absent
- `source_traceability` — node/relationship source spans present
- `dedupe` — alias/canonicalization checks

A case pass now means hard Neo4j ingestion safety only. It does not mean the graph is semantically complete.

Separated scores are stored in `benchmark_cases.notes.scores`:

- `safety`: average of JSON validity, no repair needed, schema validity, Neo4j property safety, and relationship reference integrity.
- `graph_quality`: weighted extraction quality: required nodes, required relationships, source traceability, and dedupe.
- `domain_fidelity`: normalized domain-specific properties plus ambiguity handling.
- `overall`: 50% safety, 35% graph quality, 15% domain fidelity.
- `ingestion_ready`: boolean hard-safety gate.

The SQLite `passed_cases` count is now the count of ingestion-ready cases. Use `overall`, `graph_quality`, and `domain_fidelity` to choose the better Clerk among safe models.

## Running the Benchmark

Default to OmniRoute for Gerod's local benchmark workflow unless explicitly testing a direct provider. Direct OpenRouter can fail credential resolution or bypass routing behavior that production combos rely on.

```bash
python3 ~/.hermes/skills/benchmarks/clerk-benchmark/scripts/run_clerk_benchmark.py \
  --provider omniroute \
  --model gemini/gemini-2.5-flash-lite \
  --db "$HOME/.hermes/data/benchmarks/clerk/benchmark.db" \
  --obsidian-dir "$HOME/Obsidian/Main Vault/40-Operations/Hermes/Benchmarks/clerk-benchmark" \
  --temperature 0 \
  --max-tokens 2048 \
  --timeout 120 \
  --max-retries 2 \
  --json-mode
```

Direct provider example, only when intentionally testing direct OpenRouter:

```bash
python3 ~/.hermes/skills/benchmarks/clerk-benchmark/scripts/run_clerk_benchmark.py \
  --provider openrouter \
  --model openai/gpt-4o \
  --db "$HOME/.hermes/data/benchmarks/clerk/benchmark.db" \
  --obsidian-dir "$HOME/Obsidian/Main Vault/40-Operations/Hermes/Benchmarks/clerk-benchmark" \
  --temperature 0 \
  --max-tokens 2048 \
  --timeout 60 \
  --json-mode
```


For raw model probes through OmniRoute, pass the concrete model ID as `--model`, e.g. `cerebras/qwen-3-235b-a22b-instruct-2507`. Use `--json-mode` for OpenAI-compatible `response_format: {"type":"json_object"}`. This enforces JSON syntax, but it does not enforce the full schema. The benchmark still validates schema and graph safety itself.

## Cost Estimates

Version `0.4.0` estimates benchmark cost per case and per run.

The runner must calculate costs for every provider, including OmniRoute. It fetches live OpenRouter catalog pricing when available and then falls back to the local `FALLBACK_PRICING_PER_TOKEN` table for direct provider / OmniRoute model IDs. Add every newly benchmarked paid model to that table before trusting the Obsidian cost column. Free/provider-subsidized lanes intentionally remain `$0.000000` unless invoice-backed pricing exists.

Per-case `benchmark_cases.notes.cost` includes:

- `usd`
- `per_100_runs_usd`
- `pricing_source`
- `pricing_required` — true when pricing is unknown and the local pricing table needs coverage

`benchmark_runs.cost_usd` is the sum of case estimates. The value remains marked estimated because provider routing/invoice details can differ slightly from catalog pricing. Obsidian tables are generated from SQLite, so fix missing costs in SQLite first, then rerender the table.

## Session Notes / References

- `references/clerk-fallback-models-2026-05-09.md` records benchmark results for Gemini 2.5 Flash-Lite, Gemini 3.1 Flash-Lite Preview, and Cerebras/Qwen as Clerk fallback candidates.
- `references/omniroute-clerk-fallbacks-2026-05-09.md` records the OmniRoute-vs-OpenRouter correction, Cerebras Qwen 429 behavior, Flash-Lite Clerk result/cost, and the `--max-retries` runner fix.
- `references/neo4j-scoring-rebuild-2026-05-08.md` records the session that rebuilt the benchmark from toy exact-match extraction into separated Neo4j ingestion safety, graph quality, and domain fidelity scoring. It also captures the cheap-model rerun results, the StepFun/OpenRouter JSON-mode failure, the cost-estimate fix, and the Clerk profile cleanup decision.

## Results

Results are saved to:

- SQLite: `~/.hermes/data/benchmarks/clerk/benchmark.db`
- Obsidian: `~/Obsidian/Main Vault/40-Operations/Hermes/Benchmarks/clerk-benchmark/clerk-benchmark-results.md`

Quick inspection:

```bash
sqlite3 -header -column ~/.hermes/data/benchmarks/clerk/benchmark.db \
  "SELECT run_id, provider, model, suite_version, score, passed_cases, total_cases, avg_latency_ms FROM benchmark_runs WHERE benchmark_name='clerk-benchmark' ORDER BY started_at DESC LIMIT 10;"
```

Per-case failure inspection:

```bash
python3 - <<'PY'
import sqlite3, json
run_id = 'PASTE_RUN_ID'
con = sqlite3.connect('~/.hermes/data/benchmarks/clerk/benchmark.db')
con.row_factory = sqlite3.Row
for r in con.execute('SELECT case_id, passed, score, notes FROM benchmark_cases WHERE run_id=?', (run_id,)):
    notes = json.loads(r['notes']) if r['notes'] else {}
    print('\n', r['case_id'], 'PASS' if r['passed'] else 'FAIL', r['score'])
    for f in notes.get('failures', [])[:10]:
        print(' -', f)
PY
```

## Local Model Testing via LM Studio (2026-05-14)

When testing a Clerk candidate via LM Studio or any local GGUF:
- Use `--provider custom --base-url http://<ip>:1234/v1 --api-key dummy --model <model-id>`
- The `--json-mode` flag still applies for `response_format: {type: "json_object"}`
- LM Studio may return `{"error": {"message": "No models loaded..."}}` if no model is loaded yet — this is an infrastructure error, not a model failure
- LM Studio uses Tailscale IPs (100.x.x.x) — security scans may flag raw IPs; this is expected
- Caveman system prompt available at `templates/clerk-system-prompt.txt` for minimal token overhead
- **Pitfall:** Even strong 26B models may produce invalid JSON (dropping colons mid-stream). Benchmark with multiple identical prompts to distinguish one-time glitch from systematic instability.
- **Latency expectation:** ~25-30s per case on Apple Silicon via LM Studio

## Reference Notes

Session-specific rebuild detail is captured in `references/neo4j-ingestion-rebuild-2026-05-08.md`.

## Current Smoke Result

OpenRouter `openai/gpt-4o` with `--json-mode` smoke run after rebuild:

- Run: `clerk-benchmark-20260508T212453Z-1dcd8995`
- Score: `0.821`
- Pass: `3/8`
- Avg latency: `3364 ms`
- Tokens: `7515`

Interpretation: JSON syntax and Neo4j property safety were mostly fine, but GPT-4o still missed domain graph semantics: GovCon contract normalization, dedupe, document/constraint modeling, and some relationship enum choices.

## Pitfalls This Benchmark Is Designed To Catch

- Markdown fenced JSON
- extra prose before/after JSON
- invalid relationship labels like `HAS_CONTRACT`, `CONTRIBUTES_TO`, or `SUPPLIED_TO`
- relationship references to nonexistent temp IDs
- nested JSON objects inside Neo4j properties
- ambiguous-source hallucinations
- duplicate entities from aliases/acronyms
- missing source spans
- plausible facts that are not graph-ready

## Operational Pitfalls

- Use `--provider omniroute` for Gerod's production-like benchmark path. Direct `openrouter` runs can fail auth (`No cookie auth credentials found`) and should not be treated as model-quality results.
- If a run records zero tokens and per-case HTTP 401/429 errors, interpret it as infrastructure/provider failure, not model performance.
- Cerebras-backed models can be excellent in isolated cases but unreliable under sustained full-suite traffic. Benchmark the intended combo, not just the raw Cerebras lane, when production usage will be low-weight round-robin.
- `gemini/gemini-2.5-flash-lite` is a proven cheap strict-JSON fallback candidate as of 2026-05-09: 7/8 ingestion-ready, score 0.896, estimated full-suite cost $0.004274.

## Routing Implication

For production Clerk routing, prefer models that score high on:

1. `json_valid`
2. `schema_valid`
3. `neo4j_property_safe`
4. `reference_integrity`
5. `required_relationships`

A model with great prose or plausible extraction but bad relationship enums is not a Clerk. It's a liability with a vocabulary.

## Relationship to intake-curator Schema Validator

The `intake-curator` skill now has a dedicated schema validation pipeline under `scripts/schema_validator/` with the same allowed labels, relationship types, and Neo4j safety constraints (no nested properties, reference integrity, enum validation). The validator is a CLI tool that can be used independently: `python3 schema_validator.py --file packet.json`. When building Clerk prompts or validating Clerk output, use this validator rather than re-implementing the checks.
