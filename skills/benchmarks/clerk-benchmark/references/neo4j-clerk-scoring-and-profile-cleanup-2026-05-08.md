# Neo4j Clerk scoring + profile cleanup notes (2026-05-08)

Session outcome: the Clerk benchmark was rebuilt from toy exact-match extraction into a Neo4j ingestion-readiness benchmark, then refactored again to separate hard safety from semantic graph quality.

## Benchmark scoring lesson

Do not use one pass/fail gate for both ingestion safety and semantic graph quality. If models score around 0.85 but pass only 2-3/8 cases, the benchmark is probably conflating:

1. Hard safety — can this JSON be ingested without breaking Neo4j?
2. Graph quality — did it extract the right nodes/relationships?
3. Domain fidelity — did it normalize domain-specific fields and handle ambiguity?

Current separated scoring model:

- `safety`: average of `json_valid`, `strict_no_repair`, `schema_valid`, `neo4j_property_safe`, `reference_integrity`.
- `graph_quality`: weighted node/relation/source/dedupe quality.
- `domain_fidelity`: normalized properties + ambiguity handling.
- `overall`: 50% safety, 35% graph quality, 15% domain fidelity.
- `passed`: ingestion-ready hard safety only.

Interpretation: `passed_cases` now counts safe-to-ingest cases. Rank Clerk candidates by `overall`, `graph_quality`, and `domain_fidelity` among models with high safety.

## Cheap model rerun after separated scoring

OpenRouter, temperature 0, max_tokens 2048.

| Model | Run | Ready | Overall | Safety | Graph | Domain | Avg latency |
|---|---|---:|---:|---:|---:|---:|---:|
| `google/gemma-4-26b-a4b-it` | `clerk-benchmark-20260508T214747Z-41f81de6` | 7/8 | 0.9093 | 0.9750 | 0.7997 | 0.9458 | 13.3s |
| `qwen/qwen3-235b-a22b-2507` | `clerk-benchmark-20260508T214505Z-2a443477` | 6/8 | 0.8803 | 0.9500 | 0.7757 | 0.8917 | 20.3s |
| `stepfun/step-3.5-flash` | `clerk-benchmark-20260508T214934Z-fd0664c8` | 0/8 | 0.0000 | 0 | 0 | 0 | 13.3s |

StepFun caveat: OpenRouter/DeepInfra rejects `json_object` for this model, and without JSON mode the route returned empty content for every case. Treat as disqualified for this route unless another endpoint/provider fixes structured output.

## Profile cleanup lesson

The Clerk worker profile should remain a structured-output producer, not a full research/orchestration agent. Neo4j-specific schemas should usually be supplied in prompts, while the profile SOUL enforces generic structured-output behavior.

Cleanup applied to `~/.hermes/profiles/clerk/`:

- `config.yaml` reduced to a tiny OmniRoute profile pointing at the `clerk` combo and `cheap-structured`.
- Removed direct provider sprawl, fallback duplication, personality blocks, giant inherited terminal config, and random model lists.
- Kept `toolsets: [hermes-cli]`, but disabled noisy/sensitive toolsets (`browser`, `web`, `search`, `discord`, `spotify`, `image_gen`, `tts`, `github`, `mcp`, `mesh`, `hindsight`, `homeassistant`).
- Reduced autonomy: `max_turns: 20`, `gateway_timeout: 900`, `reasoning_effort: low`.
- Rewrote `SOUL.md` as generic structured-output worker: exact schema, no fences, no commentary, no invented facts, confidence/source evidence, ambiguity as structured warning.
- Slimmed profile-local skills from 186 to 3: `devops/kanban-worker`, `data-science/neo4j-http`, `note-taking/obsidian`.

Rollback snapshot made at:
`~/.hermes/profiles/clerk/archive/20260508-175825`

## Recommended future behavior

- Keep model fallback/routing in OmniRoute combos, not duplicated in profile YAML.
- Treat Clerk as "safe structured JSON first"; use task prompts for specific graph schemas.
- Do not over-penalize semantic incompleteness as ingestion failure.
- If a model emits valid safe graph JSON but misses edges/properties, mark it safe but lower graph/domain scores.
