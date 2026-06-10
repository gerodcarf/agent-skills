---
name: model-benchmark
description: "Common baseline for Hermes model benchmark skills: OpenAI-compatible provider/model inputs, SQLite result storage, token/cost accounting, Obsidian reporting, and robust repeatable benchmark rules. Load before creating, refactoring, or running benchmark skills."
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [benchmark, models, sqlite, obsidian, openai-compatible, evaluation]
    related_skills: [model-ping, cheap-model-benchmark, bouncer-benchmark, orchestrator-model-benchmark, deep-reasoning-benchmark, complex-coding-benchmark, ocr-benchmark, scout-benchmark]
---

# Model Benchmark Common Baseline

## Purpose

Shared contract for every Hermes benchmark skill. Individual benchmarks own test suites and scoring logic; this common skill owns plumbing and standards.

## Mandatory Rules

1. Accept any OpenAI-compatible target via `--base-url`, `--api-key`, `--provider`, and `--model`.
2. Never rely on the active Hermes chat model. Benchmarks explicitly name provider/model/endpoint.
3. Persist every full run to SQLite with timestamped run metadata, per-test findings, token usage, estimated cost, raw response excerpts, latency, pass/fail, and scoring notes.
4. Track costs for the full run. Prefer provider `usage`; fall back to local token estimate + pricing config and mark `cost_estimated=1`. Benchmark runners must calculate cost for every provider, including OmniRoute/proxy runs, before rendering Obsidian tables. If a paid model has unknown pricing, add it to the benchmark's pricing table instead of leaving `$0.000000`; only genuinely free/provider-subsidized lanes should stay zero.
5. Use deterministic settings unless the benchmark explicitly tests creativity: `temperature=0`, `stream=false`, explicit timeout, low retries.
6. Record provenance: benchmark name/version, suite version, provider, model, base_url, command args, start/end timestamps.
7. Write Obsidian docs under `~/Obsidian/Main Vault/40-Operations/Hermes/Benchmarks/<benchmark-name>/`:
   - `<benchmark-name>-overview.md`: purpose, tested capabilities, versions/changelog, thresholds.
   - `<benchmark-name>-results.md`: results table, recommendations, links to DB/run artifacts.
8. Keep benchmark skills under `~/.hermes/skills/benchmarks/<benchmark-name>/`.
9. Fail closed on malformed output.
10. Separate harness from scoring: common scripts manage DB/API/reporting; each benchmark supplies cases and `score_response()`.
11. If a CLI exposes `--max-retries`, the runner must actually honor it around provider calls and classify retryable errors explicitly. A decorative retry flag is worse than no flag because it creates false confidence during rate-limit tests.
12. When benchmarking production routing, use the same provider path as production. For Gerod's OmniRoute-backed combos, prefer `--provider omniroute` unless the task is explicitly direct-provider testing.

## Standard Layout

```text
~/.hermes/skills/benchmarks/<benchmark-name>/
  SKILL.md
  scripts/run_<benchmark>.py
  tests/
  references/
  results/benchmark.db
```

## Standard CLI

```bash
python3 scripts/run_<benchmark>.py \
  --provider omniroute \
  --model bouncer \
  --base-url http://localhost:20128/v1 \
  --api-key "$OMNIROUTE_API_KEY" \
  --db results/benchmark.db \
  --obsidian-dir "$HOME/Obsidian/Main Vault/40-Operations/Hermes/Benchmarks/<benchmark-name>" \
  --suite-version v1 \
  --temperature 0 \
  --timeout 60 \
  --max-retries 0
```

Provider shortcuts may infer base URL/API key, but explicit flags must override.

## SQLite Schema

Use `scripts/benchmark_common.py`. It creates:

- `benchmark_runs`: one row per execution.
- `benchmark_cases`: one row per test case result.
- `benchmark_usage`: summarized usage/cost per run.

## Obsidian Reporting

Use `scripts/update_obsidian_results.py` or benchmark-specific equivalent to render `<benchmark-name>-results.md` from SQLite. Do not hand-edit result tables except notes/recommendations sections.

## Legacy Result Imports

When older benchmark artifacts need to populate current SQLite/Obsidian history, follow `references/legacy-result-import.md`. Import them as `legacy-*` benchmark versions with explicit provenance and caveats instead of pretending they were produced by the new harness.

Before updating Obsidian result files, distinguish a **harness smoke test** from a real benchmark run. A run against a dead endpoint, dummy model, or intentionally failing local URL may verify DB/report plumbing, but it must not be presented as a model result. Either delete it from the human table or explicitly mark it as plumbing-only.

## Migration Pattern

When consolidating benchmark skills, use this order:

1. Inventory existing benchmark skills and scripts first.
2. Create or update the common baseline before touching individual benchmark runners.
3. Create the Obsidian `README.md` and `AGENTS.md` at `~/Obsidian/Main Vault/40-Operations/Hermes/Benchmarks/`.
4. Create each benchmark's `<name>-overview.md` and `<name>-results.md` stub before running anything.
5. Move skills into `~/.hermes/skills/benchmarks/<name>/`, preserving existing scripts/results/references.
6. Add common-baseline notes to each migrated `SKILL.md`.
7. Upgrade one mature benchmark runner first — `bouncer-benchmark` is a good smoke target because it has a small deterministic YES/NO suite.
8. Verify Python compilation, folder layout, SQLite creation, and Obsidian writes.

## Cross-Skill Code Sharing

When multiple benchmark scripts under `~/.hermes/skills/benchmarks/` duplicate the same utility code (dotenv loading, API calls, JSON parsing, token cost calculation, provider resolution), consolidate into `model-benchmark/scripts/benchmark_common.py`. Consumer scripts import it via:

```python
COMMON = Path(__file__).resolve().parents[1].parent / 'model-benchmark' / 'scripts'
sys.path.insert(0, str(COMMON))
from benchmark_common import (Target, chat_completion, resolve_target, ...)
```

### Adapter Pattern for Existing Callers

If a benchmark already uses its own dataclass (e.g., `ProviderConfig`) with a different shape than `Target`, add thin bridge methods rather than rewriting the entire benchmark:

```python
@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key: str

    @classmethod
    def from_target(cls, t: Target) -> "ProviderConfig":
        return cls(t.provider, t.base_url, t.api_key)

    def to_target(self, model: str) -> Target:
        return Target(self.name, model, self.base_url, self.api_key)
```

Then `call_model(provider, model, prompt)` becomes a thin adapter over `chat_completion(provider.to_target(model), messages, ...)`.

### Pitfalls

- **OpenRouter model ID format.** When using `--provider openrouter`, the `--model` argument should be just the model ID (e.g., `google/gemini-3-flash-preview`) without the `openrouter:` prefix. The prefix is added internally by the provider resolution logic.
- **`subprocess` import.** After removing local `read_op_secret` definitions, make sure `subprocess` is still imported if any other code in the file uses it.
- **`sys.path` insert order.** Put the `sys.path.insert` **before** the `from benchmark_common import ...` block, not after. If you put it after, Python raises `ModuleNotFoundError` on the shared module.
- **Module loading verification alternatives.** If `importlib.util.spec_from_file_location` fails with dataclass or import errors, use standard import with `sys.path.insert` as a reliable alternative. This pattern works around Python version compatibility issues while still verifying module load success.
- **`chat_completion()` return arity.** The shared `chat_completion()` returns a **3-tuple** `(text, usage_dict, latency_ms)`, NOT a 2-tuple. Old benchmarks that wrapped it as `resp, latency_ms = chat_completion(...)` will throw `ValueError: too many values to unpack (expected 2)` at runtime. If a caller needs the raw response dict for storage (e.g., `raw_json=json.dumps(resp)`), have it call `chat_completion_raw()` instead (which returns `(resp_dict, latency_ms)`) and then call `extract_text_and_usage(resp)` locally. This is exactly the pattern used in the clerk benchmark's `chat_completion_with_retries`.

## References

- `references/2026-05-08-benchmark-library-baseline.md` — session notes for the initial benchmark-library consolidation, migrated skills, common scripts, and first runner upgrade.
- `references/2026-05-09-benchmark-bloat-audit.md` — session notes for the bloat audit and cross-skill consolidation refactor.

## Upgrade Checklist

- [ ] Skill lives in `~/.hermes/skills/benchmarks/<name>/`.
- [ ] Loads/mentions this `model-benchmark` skill.
- [ ] Runner accepts OpenAI-compatible endpoint/model flags.
- [ ] Runner writes SQLite run + per-case rows.
- [ ] Runner records token usage and estimated/actual cost.
- [ ] Obsidian overview/results files exist.
- [ ] Global Benchmarks README/AGENTS exist.
- [ ] Smoke run works against `omniroute` with `stream=false`.

## Legacy Results Import

When populating a results table from pre-baseline benchmark history, follow `references/legacy-results-import.md`. Search both the benchmark skill directory and old Obsidian benchmark archives, normalize historical rows into `results/benchmark.db`, label them `legacy-*`, and make provenance/estimation caveats explicit in the Obsidian results note.
