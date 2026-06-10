# Benchmark Master Project Migration

Use this reference when migrating Hermes benchmark skills into the shared benchmark project architecture.

## Desired architecture

Benchmarks are one project with multiple suites, not isolated skills. `benchmark-common` is the canonical master contract. Individual benchmark skills should describe only their suite-specific contract, fixtures, prompts, scoring, and failure gates.

## Migration checklist

For each benchmark skill:

1. Add `benchmark-common` to `metadata.hermes.related_skills`.
2. Add a concise `Common benchmark contract` section.
3. Name the profile/role/capability contract under test.
4. State standard storage:
   - `~/.hermes/skills/benchmarks/<benchmark-name>/results/benchmark.db`
   - `~/.hermes/skills/benchmarks/<benchmark-name>/results/raw/<run_id>/`
5. State the Obsidian report location and preserve historical report paths if they already exist.
6. Link or move long prompt banks/rubrics to `references/` or `resources/`.
7. Define promotion/demotion rules or routing implications.
8. Define hard failure gates, including hidden fallback responses.
9. Remove duplicated DB/report/provenance boilerplate that belongs in `benchmark-common`.
10. Validate frontmatter and any touched scripts.

## Compatibility rule

`model-benchmark` may remain temporarily as a compatibility alias while older scripts import `model-benchmark/scripts/benchmark_common.py`. New or refactored runners should target `benchmark-common/scripts/` as the canonical location.

## Profile/contract examples

- `bouncer-benchmark`: Tier 5 binary pre-filter; strict YES/NO, low latency, no verbose reasoning.
- `cheap-model-benchmark`: Tier 4 cheap/fast structured model; sanity, cost, latency, preflight.
- `clerk-benchmark`: Clerk ingestion-readiness; messy text to strict graph JSON.
- `librarian-benchmark`: Knowledge OS librarian; classification, metadata, filing/routing decisions.
- `hindsight-model-benchmark`: memory retain/recall compatibility and large-context headroom.
- `complex-coding-benchmark`: Tier 2 coding specialist; patches, tests, reviewability.
- `deep-reasoning-benchmark`: Tier 1 frontier/deep reasoning; hard reasoning and judge architecture.
- `ocr-benchmark`: vision/OCR contract; document page to faithful markdown/structured extraction.
- `orchestrator-model-benchmark`: main/orchestrator contract; routing, safety, delegation, memory, tool choice, communication.
- `scout-benchmark`: tool-less scout/recon contract; uncertainty and handoff usefulness.
