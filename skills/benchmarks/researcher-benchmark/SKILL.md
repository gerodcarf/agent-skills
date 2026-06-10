---
name: researcher-benchmark
description: "Benchmark candidate models for the Hermes Researcher role: source-grounded research planning, bounded evidence extraction, citation discipline, temporal/lookahead control, stop-condition judgment, and handoff-ready synthesis for supply-chain and market-structure backfills."
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [benchmark, researcher, research, citations, source-grounding, supply-chain, market-knowledge-date, model-evaluation]
    related_skills: [benchmark-common, scout-benchmark, clerk-benchmark, research-recon, supply-chain-knowledge-graph, model-routing]
trigger:
  - researcher benchmark
  - benchmark researcher profile
  - compare models for research tasks
  - source-grounded research benchmark
  - semiconductor supply chain backfill benchmark
  - market_knowledge_date benchmark
---

# Researcher Benchmark

This is the benchmark spoke for the Hermes **Researcher** contract. It uses `benchmark-common` as the hub execution layer and keeps this skill focused on researcher-specific cases, scoring, rubrics, and reporting interpretation.

## Common benchmark contract

Always load `benchmark-common` before modifying or running this benchmark.

Additional session-derived reference: `references/provider-routing-and-json-failure-triage.md` documents provider/model namespace pitfalls and how to diagnose `0.000` runs caused by strict-JSON failures, truncation, and temporal lookahead leakage.

This suite tests the **Researcher role**: convert bounded evidence packets into source-grounded, temporally correct, handoff-ready research outputs. It is designed to catch the failure mode where a researcher keeps searching or synthesizing loosely instead of converging on cited facts with clear stop conditions.

## What this benchmark evaluates

The Researcher benchmark rewards models that:

1. Identify authoritative source coverage and missing-source gaps.
2. Extract material facts with source IDs and dates.
3. Preserve point-in-time reasoning using `market_knowledge_date`.
4. Avoid lookahead bias when historical outcomes are known now but unavailable at the evidence date.
5. Separate evidence from implication/synthesis.
6. Produce a bounded handoff suitable for Clerk/Neo4j ingestion or downstream synthesis.
7. Stop cleanly when enough evidence exists instead of expanding the search indefinitely.

## What this benchmark does not evaluate yet

The initial `v0.1` suite is **source-grounded and no-tool** because it runs on the shared `benchmark-common` chat-completions harness. It does not directly benchmark live web-search tool loops. That is intentional: the first failure to screen for is whether the model can follow the Researcher output contract once evidence is present.

A future `v0.2` can add a Hermes subagent/tool-loop harness that runs actual researcher profiles against web tasks and scores search discipline, extraction completeness, and run budget behavior.

## Unified execution

Run from the benchmark skill directory so the case module is importable:

```bash
cd ~/.hermes/skills/benchmarks/researcher-benchmark
PYTHONPATH="$PWD/scripts" \
python3 ~/.hermes/skills/benchmarks/benchmark-common/scripts/run_benchmark.py run \
  --benchmark-name researcher-benchmark \
  --benchmark-version 0.1.0 \
  --suite-version semiconductor-v0.1 \
  --cases-module researcher_cases \
  --provider omniroute \
  --model '<model-id>' \
  --temperature 0.1 \
  --max-tokens 4000 \
  --db ~/.hermes/skills/benchmarks/researcher-benchmark/results/benchmark.db \
  --obsidian-dir ~/Obsidian/main-vault/40-Operations/Hermes/Benchmarks/researcher-benchmark
```

For OpenRouter:

```bash
cd ~/.hermes/skills/benchmarks/researcher-benchmark
PYTHONPATH="$PWD/scripts" \
python3 ~/.hermes/skills/benchmarks/benchmark-common/scripts/run_benchmark.py run \
  --benchmark-name researcher-benchmark \
  --benchmark-version 0.1.0 \
  --suite-version semiconductor-v0.1 \
  --cases-module researcher_cases \
  --provider openrouter \
  --model '<provider/model>' \
  --temperature 0.1 \
  --max-tokens 4000 \
  --db ~/.hermes/skills/benchmarks/researcher-benchmark/results/benchmark.db \
  --obsidian-dir ~/Obsidian/main-vault/40-Operations/Hermes/Benchmarks/researcher-benchmark
```

## Output contract

Cases require strict JSON with this shape:

```json
{
  "task_assessment": {
    "sufficient_evidence": true,
    "recommended_next_action": "handoff_to_clerk|targeted_followup|block_for_missing_source",
    "missing_sources": []
  },
  "source_plan": [
    {
      "source_id": "S1",
      "source_type": "annual_report|earnings_call|investor_presentation|industry_data|trade_press|other",
      "use": "what this source supports"
    }
  ],
  "fact_table": [
    {
      "fact_id": "F1",
      "company": "SK Hynix",
      "cycle": "2018-2019 memory downturn",
      "market_knowledge_date": "2019-01-24",
      "source_id": "S2",
      "fact_type": "pricing|inventory|capex|demand|supply|technology|customer_constraint|management_commentary",
      "metric": "DRAM bit shipment growth",
      "value": "single-digit percent decline QoQ",
      "constraint_implication": "why this matters for downstream AI/data-center supply chain mapping",
      "confidence": "high|medium|low"
    }
  ],
  "synthesis": {
    "cycle_read": "short synthesis grounded only in cited facts",
    "downstream_constraint_relevance": "how the evidence maps to AI/data-center chokepoints",
    "lookahead_guardrails": ["claims avoided because unavailable at market_knowledge_date"]
  },
  "handoff": {
    "ready_for_clerk": true,
    "neo4j_candidate_entities": [],
    "neo4j_candidate_relationships": [],
    "followup_tasks": []
  }
}
```

## Scoring dimensions

The scorer in `scripts/researcher_cases.py` uses a 100-point rubric:

- 20 pts — JSON validity and required top-level schema.
- 20 pts — source discipline: required source IDs used, no invented source IDs, source dates/types respected.
- 20 pts — fact extraction completeness: required fact anchors appear in the fact table with source IDs and market dates.
- 15 pts — temporal discipline: avoids forbidden lookahead dates/claims and uses `market_knowledge_date`.
- 15 pts — bounded research judgment: correct next action and stop-condition behavior.
- 10 pts — handoff utility: Clerk/Neo4j-ready entities, relationships, and follow-up gaps.

Default pass threshold: **0.80**.

## Current suite: `semiconductor-v0.1`

The initial cases are built around semiconductor supply-chain backfill work for AI/data-center downstream constraints:

1. `skhynix_2018_2019_memory_downturn` — historical DRAM/NAND bust; tests point-in-time downturn extraction and avoids later HBM lookahead.
2. `micron_2023_2024_hbm_ramp` — AI/HBM capacity ramp; tests demand/capacity facts and downstream constraint synthesis.
3. `cross_cycle_semiconductor_backfill_plan` — asks for a bounded research plan across prior booms/busts; tests decomposition and stop-condition discipline.

## Interpretation

A good Researcher model should score highly without being the strongest final synthesizer. The important behaviors are citation discipline, temporal humility, and practical handoff quality. If a model writes impressive prose but fails source IDs, dates, or stop conditions, route it away from autonomous researcher tasks.

## Pitfalls

### Forbidden-term scoring vs lookahead guardrails

The scorer checks for forbidden lookahead terms in the response. A model that correctly names a forbidden concept *inside* its `synthesis.lookahead_guardrails` array (e.g. `"Avoided referencing HBM3 or ChatGPT"`) should **not** be penalized — that is the guardrail working as intended. The scorer must strip the guardrail JSON text before scanning for forbidden terms. If you restructure the scorer, preserve this exclusion or self-tests will regress from 1.0 to 0.96.

### CaseDef.expected is metadata, not literal output

Each case's `expected` field is a JSON-encoded dict of scoring metadata (required sources, required terms, forbidden terms, min facts, required next action, etc.). The scorer parses it via `_load_expected()`. Do not put literal expected response text here — it is not compared character-by-character.

## Related roles

- `scout-benchmark`: first-pass, no-tool reconnaissance before sources are validated.
- `researcher-benchmark`: source-grounded research extraction and handoff.
- `clerk-benchmark`: convert researcher handoff into strict Neo4j-safe graph JSON.
- `deep-reasoning-benchmark`: contradiction/logic audit across documents after evidence has been assembled.
