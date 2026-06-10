# Benchmark storage normalization and report regeneration

Use this when migrating old Hermes benchmark suites into the `benchmark-common` architecture or regenerating Obsidian reports from mixed legacy schemas.

## Standard storage

Canonical per-suite storage is:

```text
~/.hermes/skills/benchmarks/<benchmark-name>/results/benchmark.db
~/.hermes/skills/benchmarks/<benchmark-name>/results/raw/<run_id>/
~/Obsidian/main-vault/40-Operations/Hermes/Benchmarks/<benchmark-name>/
```

Legacy names encountered during migration included:

- `cheap-model-benchmark/results/cheap-benchmark.db`
- `hindsight-model-benchmark/results/hindsight-benchmark.db`
- `cheap-model-benchmark/benchmark_results.db`
- `orchestrator-model-benchmark/results/scores.db`
- `clerk-benchmark/scripts/results/benchmark.db`
- `results/runs/<run_id>/`
- historical Obsidian locations under `~/Obsidian/main-vault/Hermes/Benchmarks/...`

Migrate DBs/artifacts only after backing up originals. A practical rollback shape is:

```text
skills/benchmarks/_legacy-archive/<YYYY-MM-DD-storage-normalization>/MANIFEST.md
```

Long-term, benchmark DBs/raw artifacts should usually be ignored by git; commit skills, runners, docs, and report-generation scripts, not large/generated result payloads.

## Gitignore patterns

For benchmark result cleanup, prefer explicit generated-artifact ignore rules such as:

```gitignore
skills/*/*/results/raw/
skills/*/results/raw/
skills/benchmarks/*/results/
skills/benchmarks/_legacy-archive/
```

Keep `scripts/`, `references/`, `resources/`, and `SKILL.md` trackable.

## Schema normalization before reports

Do not destructively rewrite legacy DB tables just to make reports. Add read-only compatibility views with a stable shape:

- `common_benchmark_runs`
- `common_benchmark_cases`
- `common_benchmark_usage`

For suites already using `benchmark_runs` / `benchmark_cases` / `benchmark_usage`, these can be passthrough views. For legacy `runs` schemas, create adapter views that map available columns into the common shape. This is enough for report regeneration and preserves historical rows.

## Regenerating reports

Regenerate reports into the ops path:

```text
~/Obsidian/main-vault/40-Operations/Hermes/Benchmarks/<benchmark-name>/<benchmark-name>-overview.md
~/Obsidian/main-vault/40-Operations/Hermes/Benchmarks/<benchmark-name>/<benchmark-name>-results.md
```

A report generator should:

1. Normalize/create common views in the DB.
2. Read from `common_benchmark_runs` and `common_benchmark_cases`.
3. Write deterministic Markdown tables.
4. Leave a `## Notes` section for human interpretation and routing decisions.
5. Treat benchmark outputs as evidence for `model-routing`, not as automatic routing policy changes.

## Validation checklist

After storage/report cleanup:

- Confirm each suite with history has `results/benchmark.db`.
- Confirm no current `*/results/runs` directories remain after migration to `results/raw`.
- Query `common_benchmark_runs` for every migrated DB.
- Run YAML/frontmatter validation for touched skills.
- Run `python3 -m py_compile` over touched benchmark scripts.
- Run `git status --short -- .gitignore skills/benchmarks` and confirm generated DB/raw/archive payloads are ignored while scripts/docs remain visible.
- Record a Kanban handoff when the work modifies benchmark architecture or tracked runners.
