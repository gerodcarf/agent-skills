# OpenRouter Nemotron 3 Ultra Free Clerk Benchmark Notes — 2026-06-06

## Target

- Provider/model: `openrouter:nvidia/nemotron-3-ultra-550b-a55b:free`
- Mode: `--json-mode`
- Runner DB: `~/.hermes/skills/benchmarks/clerk-benchmark/results/benchmark.db`
- Canonical output directory used in-session: `~/Obsidian/main-vault/Hermes/Benchmarks/Clerk`

## Operational notes

- Preflight with `model-ping` succeeded after sourcing `~/.hermes/.env`.
- OpenRouter accepted `response_format: {"type":"json_object"}` for this model, but JSON mode did not guarantee Clerk pass quality.
- The skill-local source runner path was absent in this session, but the compiled runner existed at:
  `~/.hermes/skills/benchmarks/clerk-benchmark/scripts/__pycache__/run_clerk_benchmark.cpython-311.pyc`
- The compiled runner must be executed with Python 3.11 and the benchmark-common scripts on `PYTHONPATH`:

```bash
set -a; source ~/.hermes/.env >/dev/null 2>&1; set +a
PYTHONPATH="$HOME/.hermes/skills/benchmarks/benchmark-common/scripts" \
  /opt/homebrew/bin/python3.11 \
  ~/.hermes/skills/benchmarks/clerk-benchmark/scripts/__pycache__/run_clerk_benchmark.cpython-311.pyc \
  --provider openrouter \
  --model 'nvidia/nemotron-3-ultra-550b-a55b:free' \
  --db ~/.hermes/skills/benchmarks/clerk-benchmark/results/benchmark.db \
  --obsidian-dir "$HOME/Obsidian/main-vault/Hermes/Benchmarks/Clerk" \
  --timeout 240 \
  --max-retries 1 \
  --json-mode \
  --notes 'Nemotron 3 Ultra Free Clerk benchmark.'
```

## Run-state pitfall

The benchmark runner inserts per-case rows as it progresses, but the aggregate `benchmark_runs` row remains `status='running'`, `total_cases=0`, `passed_cases=0`, and `score=0.0` until finalization. For long or interrupted runs, inspect `benchmark_cases` for the active run instead of assuming the run table has current partial totals.

Useful partial-progress query:

```sql
select count(*), group_concat(case_id||':'||passed,' | ')
from benchmark_cases
where run_id='<run_id>';
```

## Observed partial result

Clean rerun observed through 6/8 cases before the tool-call budget ended:

| Case | Pass |
|---|---:|
| `supplier_relationship_basic` | 1 |
| `govcon_award_extraction` | 0 |
| `subsidiary_and_location` | 1 |
| `negative_ambiguity_warning` | 0 |
| `metric_normalization` | 0 |
| `duplicate_entity_canonicalization` | 0 |

Interim decision: do not route Clerk to this model unless a completed rerun later clears the baseline. The partial trajectory was far below the Clerk baseline and latency was high.