# 2026-05-08 Benchmark Library Baseline

Session outcome: established a class-level benchmark library pattern for Hermes model/profile suitability tests.

## Decisions

- All benchmark skills live under `~/.hermes/skills/benchmarks/<benchmark-name>/`.
- Common harness skill: `model-benchmark`.
- Human-facing benchmark docs live under `~/Obsidian/Main Vault/40-Operations/Hermes/Benchmarks/`.
- Each benchmark gets:
  - `<benchmark-name>-overview.md`
  - `<benchmark-name>-results.md`
- Global Obsidian folder gets:
  - `README.md` for humans
  - `AGENTS.md` for agents

## Common Harness Files

Created under `~/.hermes/skills/benchmarks/model-benchmark/`:

- `scripts/benchmark_common.py`
  - OpenAI-compatible `/v1/chat/completions` helper
  - provider defaults for OmniRoute/OpenRouter/Nous/OpenAI/xAI/Groq/Cerebras
  - SQLite schema creation
  - run/case/usage recording helpers
- `scripts/update_obsidian_results.py`
  - renders a markdown results table from `benchmark_runs`

## SQLite Tables

- `benchmark_runs`
- `benchmark_cases`
- `benchmark_usage`
- `schema_meta`

## Migrated Benchmark Skills

Moved into `~/.hermes/skills/benchmarks/`:

- `bouncer-benchmark`
- `cheap-model-benchmark`
- `orchestrator-model-benchmark`
- `deep-reasoning-benchmark`
- `complex-coding-benchmark`
- `ocr-benchmark`
- `scout-benchmark`
- `model-benchmark`

## First Runner Upgrade

Added `bouncer-benchmark/scripts/run_bouncer_benchmark.py` using the common harness.

Important pitfall: a dummy run against `http://127.0.0.1:9/v1` was useful to verify DB/report plumbing but should not be included as a real model result.

## Next Best Upgrade

Upgrade `cheap-model-benchmark` next. It already has a relatively mature runner and DB, so it is the best candidate for shaking out schema and reporting annoyances before touching more complex benchmarks.
