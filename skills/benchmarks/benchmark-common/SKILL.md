---
name: benchmark-common
description: "Canonical master project contract for Hermes benchmark skills: profile/contract mapping, shared SQLite schema, Obsidian reporting, result storage, and runner conventions. Load before creating, refactoring, or running any benchmark skill."
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [benchmark, benchmarks, evaluation, sqlite, obsidian, profiles, contracts, reporting]
    related_skills: [model-ping, model-routing, bouncer-benchmark, clerk-benchmark, ocr-benchmark, orchestrator-model-benchmark, scout-benchmark, complex-coding-benchmark, deep-reasoning-benchmark, model-benchmark]
trigger:
  - creating, refactoring, consolidating, or reviewing benchmark skills
  - standardizing benchmark result storage, SQLite schemas, reports, or runner CLIs
  - deciding which Hermes profile, role contract, or model tier a benchmark evaluates
  - comparing benchmark outputs across OCR, scout, clerk, orchestrator, bouncer, coding, or reasoning suites
---

# Benchmark Common

`benchmark-common` is the master project contract for Hermes benchmarks. Every benchmark skill should load or cite this skill, then specialize only the suite-specific prompt set, scoring rubric, and verification nuance.

## Archiving stale benchmark skills

When the user asks to retire/archive benchmark skills that have not been executed recently:

1. Identify last execution from `results/benchmark.db` first, then fall back to `results/`, `logs/`, `runs/`, or report artifact dates. Distinguish real execution evidence from SKILL.md edit timestamps.
2. Preserve historical result data. Do **not** delete benchmark directories or result databases unless explicitly asked.
3. Move retired benchmark skill directories out of the active skill scan tree, e.g. from `~/.hermes/skills/benchmarks/<name>/` to `~/.hermes/archived-skills/benchmarks/retired-YYYY-MM-DD/<name>/`. Moving under another subdirectory of `~/.hermes/skills/` can leave the retired skill discoverable.
4. Add a short archive `README.md` listing why and when the benchmarks were retired.
5. Verify active skill discovery by scanning only `~/.hermes/skills/` for remaining `SKILL.md` files and confirm the retired names no longer appear.
6. Check `git status --short` before and after; do not commit broad `.hermes` changes when unrelated dirty runtime or skill edits already exist.

## Migration / cleanup gate

Before cleaning, untracking, or deleting benchmark result artifacts, first verify that the benchmark runner contract and storage migration are actually present in the current repo/workspace. Do not infer that cleanup is safe merely because an earlier Kanban task or session says benchmark runners were consolidated.

Minimum verification checklist:

1. Confirm the shared runner/script paths referenced by prior handoffs still exist in the current checkout.
2. Search benchmark scripts/docs for legacy per-skill paths such as `results/benchmark.db`.
3. Confirm benchmark defaults point at the canonical shared DB, normally `~/data/benchmarks/benchmark.db` unless the active project contract overrides it.
4. Inventory tracked `*/results/*` files and distinguish generated artifacts from source-like files accidentally stored under `results/`.
5. Only after import/manifest verification should generated benchmark result artifacts be removed from git tracking.

If any of those checks fail, treat the state as "migration not yet complete" and patch/refactor the benchmark contract before artifact cleanup.

## Pitfalls

- **Cost accounting must preserve direct API costs and cache live pricing.** When benchmark runners normalize API responses, keep both `usage["cost"]` and `usage["cost_usd"]` as aliases; reporting/DB code often reads `cost_usd`, while pricing helpers may historically read `cost`. In multi-model OpenRouter runs, fetch `/models` pricing once at runner initialization and pass the live pricing cache into every case instead of refetching per case/model. Verify with a tiny regression check that direct `cost_usd` wins over computed pricing and that fallback pricing still computes expected token costs. OpenRouter `:free` models can legitimately report `$0.000000` with non-zero token counts; keep latency/tokens in the report so quality/cost/throughput tradeoffs remain visible. See `references/openrouter-pricing-cache-and-free-models.md` for the session-derived pattern.
- **Preserve provider namespace when benchmarking routed models.** If the user asks for an OmniRoute benchmark of a model that is only available behind a routed prefix, do not substitute a direct provider run (for example, do not treat `openrouter:stepfun/...` as equivalent to `--provider omniroute --model openrouter/stepfun/...`). First enumerate or confirm the router's model IDs, then run the benchmark with the exact router-visible ID and record the route in `--notes`.
- **Timeouts are signal, not completion.** For slow routed models, use bounded foreground attempts for quick validation, then background the full benchmark with `notify_on_complete=true`; report the process/session ID and poll the finished run before drawing conclusions.

- **`run_benchmark.py` internal Namespace must include `notes`.** The `BenchmarkRunner.run()` method builds a minimal `argparse.Namespace` to pass to `start_run()`. If you add new fields to `add_common_args()` (or to the `benchmark_runs` schema), you must also add them to that internal `Namespace()` constructor (~line 163 of `run_benchmark.py`) or `start_run()` will raise `AttributeError`. The `notes` field was missing from the constructor even though `add_common_args()` defined it, causing every runner-based benchmark to crash on start. Fixed 2026-06-06.
- **Don't duplicate CLI arguments.** If `add_common_args()` already registers `--notes`, do not re-register it in a subparser. `argparse` will raise `ArgumentError: conflicting option string`. Add new args only to `add_common_args()` so all subcommands inherit them uniformly.

See `references/hub-and-spoke-architecture.md` for details on how to use subclass profile benchmarks and the centralized execution runner. See `references/spoke-authoring-validation-pattern.md` for the case-module shape, `CaseDef.expected` metadata convention, PYTHONPATH runner invocation, validation self-test pattern, and scorer pitfalls for new spokes.

## Core principle

Benchmarks are one project with multiple suites, not unrelated skills. Individual benchmark skills own domain-specific cases and scoring; this common skill owns the shared harness, run metadata, storage, profile/contract mapping, and reporting conventions.

## Required benchmark shape

Every benchmark skill must state:

1. **Contract under test** — the Hermes profile, role, model tier, or capability being evaluated.
2. **Neighbor boundaries** — which nearby benchmark covers adjacent capabilities.
3. **Suite version** — stable test-case/rubric version, not just skill version.
4. **Runner path** — reproducible command from the skill directory.
5. **Storage path** — canonical shared SQLite DB (`~/data/benchmarks/benchmark.db`) and raw-output location.
6. **Report path** — Obsidian human review surface.
7. **Promotion rule** — what score/result justifies changing model routing or profile assignment.

## Profile and contract map

| Benchmark | Primary contract tested | Typical profile/tool state | Neighbor boundary |
|---|---|---|---|
| `bouncer-benchmark` | Tier 5 binary pre-filter / YES-NO triage | fast/cheap, minimal context, strict answer format | Not extraction or reasoning synthesis |
| `clerk-benchmark` | Clerk ingestion contract: messy text -> strict Neo4j-ready JSON | structured-output capable, no browsing needed unless suite says so | Not scout discovery or analyst synthesis |
| `scout-benchmark` | Scout/recon contract: tool-less first-pass mapping and handoff quality | stripped scout profile, no tools, no memory, no fallback | Not fact validation; follow with source-backed research |
| `orchestrator-model-benchmark` | Main/orchestrator contract: routing, safety, delegation, memory, communication | tool-aware orchestration context, realistic Hermes prompt | Not raw coding/OCR/extraction quality |
| `ocr-benchmark` | Vision/OCR contract: document page -> markdown/structured extraction | vision-capable endpoint; image input verified | Not production intake/enrichment workflow |
| `complex-coding-benchmark` | Tier 2 coding specialist contract | repo-local coding agent/model, tests available | Not main orchestrator judgment |
| `deep-reasoning-benchmark` | Tier 1 deep reasoning / long synthesis | high-context reasoning model, tools usually off unless suite says | Not cheap short-pass structured checks |
| `cheap-model-benchmark` | Low-cost model sanity and structured reliability | cheap/free target with fallbacks disabled for measurement | Not promotion alone; use role-specific suite next |
| `hindsight-model-benchmark` | Hindsight retain/recall compatibility | memory-provider interaction focused | Not general memory product evaluation |
| `librarian-benchmark` | Knowledge OS librarian classification/organization | KOS-aware structured decisions | Not clerk graph ingestion |

## Standard filesystem layout

```text
~/.hermes/skills/benchmarks/<benchmark-name>/
├── SKILL.md
├── scripts/
│   └── run_<benchmark>.py
├── resources/              # pinned suites, corpora, manifests, fixtures
├── references/             # rubric, scenario notes, historical reports
├── results/
│   └── benchmark.db        # canonical SQLite history for this benchmark
└── reports/                # generated local artifacts if not written directly to Obsidian
```

Shared code belongs under:

```text
~/.hermes/skills/benchmarks/benchmark-common/scripts/
```

If transitional code still lives under `model-benchmark/scripts/benchmark_common.py`, benchmark runners may import it as a compatibility shim, but new/refactored runners should target `benchmark-common` as the canonical home.

## Standard CLI contract

Every runner should accept this common argument surface unless the suite has a documented reason not to:

```bash
python3 scripts/run_<benchmark>.py \
  --provider omniroute \
  --model <model-or-combo> \
  --base-url "$OMNIROUTE_URL/v1" \
  --api-key "$OMNIROUTE_API_KEY" \
  --db results/benchmark.db \
  --obsidian-dir "$HOME/Obsidian/Main Vault/40-Operations/Hermes/Benchmarks/<benchmark-name>" \
  --suite-version v1 \
  --benchmark-version <skill-or-runner-version> \
  --temperature 0 \
  --timeout 60 \
  --max-retries 0 \
  --notes ""
```

Provider shortcuts may infer base URL/API key, but explicit flags must override.

## SQLite storage contract

Use one canonical SQLite DB for all benchmark suites:

```text
~/data/benchmarks/benchmark.db
```

Every row must include or link to `benchmark_name` / `run_id` so suites remain separable while history stays queryable from one database. Raw artifacts that are too large or interpretively important should live outside git under:

```text
~/data/benchmarks/raw/<benchmark_name>/<run_id>/...
```

The shared schema must contain at least:

- `benchmark_runs` — one row per run: run id, benchmark name/version, suite version, provider, model, base URL, profile/contract metadata, args JSON, timestamps, status, aggregate score, cost, latency, notes, error.
- `benchmark_cases` — one row per case: case id, category, prompt/input reference, expected/rubric reference, response excerpt/path, score, pass/fail, latency, usage, cost, errors, scoring notes.
- `benchmark_usage` — token/cost summary per run.

Suite-specific tables are allowed for nuance, e.g. OCR page metadata, graph-schema validation results, or orchestrator dimension scores, but they must link back to `run_id` and `case_id`.

## Raw artifact storage

Do not rely only on summarized reports. Keep raw artifacts when they affect later interpretation:

```text
results/raw/<run_id>/<case_id>.json
results/raw/<run_id>/<case_id>.txt
results/raw/<run_id>/<case_id>.<suite-specific-ext>
```

OCR may also keep page images/markdown sidecars; coding benchmarks may keep patch/test logs; scout benchmarks should keep raw model handoffs for hallucination review.

## Storage normalization and legacy cleanup

When consolidating benchmark skills or changing the master storage contract, do the cleanup as part of the migration rather than leaving runners and old artifacts split across paths:

1. Inventory current databases and artifact directories before moving anything: list `*.db*`, count key tables with SQLite, and identify `results/runs/`, nested `scripts/results/`, and zero-byte DB strays.
2. Preserve rollback copies under a dated skill-local archive such as `skills/benchmarks/_legacy-archive/<YYYY-MM-DD>-storage-normalization/` and write a `MANIFEST.md` describing every move/removal.
3. Normalize suite databases to `~/.hermes/skills/benchmarks/<benchmark-name>/results/benchmark.db`. If a suite used names like `cheap-benchmark.db` or `hindsight-benchmark.db`, move the DB plus WAL/SHM sidecars when present, then update runner constants and docs.
4. Normalize raw artifacts from legacy `results/runs/<run_id>/` to `results/raw/<run_id>/`. Update moved manifest/prompt/fixture files if they contain absolute self-references to the old `results/runs/` path.
5. Remove only clearly disposable zero-byte strays or duplicate nested outputs after archiving them first; do not delete historical benchmark history without a rollback copy.
6. Patch all runner defaults and human-facing docs after the filesystem move: DB path, raw artifact path, and Obsidian report path should all match this common contract.
7. Validate with: DB table counts before/after, no remaining current `*/results/runs` directories, stale-reference scan excluding `_legacy-archive`, YAML/frontmatter parse, `python3 -m py_compile` over benchmark scripts, and `git status --short -- skills/benchmarks`.

## Obsidian reporting contract

Human-facing reports belong under the operations benchmark root for new generated reports:

```text
~/Obsidian/main-vault/40-Operations/Hermes/Benchmarks/<benchmark-name>/
```

Migration compatibility rule: if older benchmark history exists under `~/Obsidian/main-vault/Hermes/Benchmarks/`, preserve it and either link it forward from the operations note or document the historical path in the benchmark skill. Do not silently delete or overwrite historical benchmark notes when normalizing paths.

Minimum files:

- `<benchmark-name>-overview.md` — purpose, contract tested, suite version, promotion rule, links to skill/resources.
- `<benchmark-name>-results.md` — generated table from SQLite plus short human notes.
- `runs/<YYYY-MM-DD>-<run_id>.md` — optional run-level narrative for expensive or routing-changing tests.

Do not hand-edit generated result tables except in clearly marked notes/recommendations sections.

For migrations from legacy benchmark DBs/artifacts, see `references/storage-normalization-and-reporting.md`: normalize to `results/benchmark.db` + `results/raw/<run_id>/`, create read-only common compatibility views before regenerating reports, and ignore generated DB/raw/archive payloads in git.

## Scoring and promotion rules

Every benchmark must define:

- score scale and dimension weights;
- failure gates that override average score, e.g. tool-call crash, invalid JSON, missing image support, hidden fallback, refusal, safety violation;
- minimum sample size for routing decisions;
- promotion/demotion threshold for the relevant profile or model tier;
- retest cadence after model/provider/routing changes.

## Fallback and routing discipline

- Benchmarks must explicitly record provider, model/combo id, base URL, and fallback configuration.
- For model comparison, disable fallback providers unless the suite is intentionally testing a fallback chain.
- If a fallback answered instead of the candidate, mark the run invalid for candidate scoring.
- Run `model-ping` or an equivalent minimal request before expensive suites.
- Keep model-selection policy in `model-routing`; benchmark skills provide evidence, not ad hoc routing policy.

## Migration checklist for individual benchmark skills

For the full migration playbook, see `references/master-project-migration.md`.

When refactoring a benchmark skill:

1. Add `benchmark-common` to `metadata.hermes.related_skills`.
2. Add a short “Common benchmark contract” section linking to this skill.
3. State the profile/role/capability contract under test and explicitly name the profile or routing tier the benchmark informs.
4. Normalize output/storage/report sections to the standard paths above.
5. Move long prompt banks and rubrics to `references/` or `resources/`.
6. Keep suite-specific nuance local, but do not duplicate common DB/reporting/provenance rules.
7. Resolve legacy Obsidian benchmark paths deliberately: preserve existing history where it already lives, and document any move between `Hermes/Benchmarks/...` and `40-Operations/Hermes/Benchmarks/...` instead of silently hardcoding a new root.
8. Validate YAML frontmatter and referenced files.
9. Record before/after notes in the Kanban task or hygiene report.
10. Leave broad benchmark-architecture changes in review-required state until Gerod approves the common contract and path choices.

## Review-driven refactor pattern

When a benchmark hygiene task rewrites several benchmark skills at once, first stop and define the master project shape in `benchmark-common`; do not polish each skill independently. Then patch each individual benchmark with the same small contract block:

- “profile/contract under test”;
- common SQLite DB and raw artifact path;
- Obsidian report path;
- promotion/failure gates;
- suite-specific nuance that remains local.

If an older umbrella such as `model-benchmark` already exists, keep it as a compatibility alias during migration instead of deleting or duplicating it immediately. Move shared scripts toward `benchmark-common/scripts/`, but preserve legacy import paths until every runner has been migrated and verified.

## Unified runner: `run_benchmark.py`

**Path:** `benchmark-common/scripts/run_benchmark.py`

This is the consolidated execution harness that all benchmark subclass skills should use. It replaces the duplicated execution logic previously found in each skill's `run_*.py` script.

### What subclass skills provide

Each benchmark skill owns only its **domain-specific** pieces:

| Piece | What it is | Where it lives |
|---|---|---|
| Cases | `CaseDef` list with id, category, prompt, expected | Subclass `cases.py` or inline |
| Scorer | `score(response, case) -> (passed, score, notes)` | Subclass `scorer.py` or inline |
| System prompt | Optional system message prepended to all cases | Runner constructor arg |
| Pricing table | Optional `model -> (input_price, output_price)` | Runner constructor arg |

### Python API (preferred)

```python
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent / 'benchmark-common' / 'scripts'))
from run_benchmark import BenchmarkRunner, CaseDef

# Define cases
CASES = [
    CaseDef(id="e1", category="extraction", prompt="Extract entities from...", expected="..."),
    CaseDef(id="e2", category="classification", prompt="Classify...", expected="YES"),
]

# Define scorer
def my_scorer(response: str, case: CaseDef) -> tuple[bool, float, str]:
    passed = case.expected.lower() in response.lower()
    score = 1.0 if passed else 0.0
    return passed, score, "exact match"

# Run
runner = BenchmarkRunner(
    benchmark_name="my-benchmark",
    benchmark_version="1.0.0",
    suite_version="v1",
    cases=CASES,
    scorer=my_scorer,
    system_prompt="You are a data extraction assistant.",
    db_path="~/.hermes/skills/benchmarks/my-benchmark/results/benchmark.db",
    obsidian_dir="~/Obsidian/main-vault/40-Operations/Hermes/Benchmarks/my-benchmark",
)
result = runner.run(
    provider="omniroute",
    model="google/gemma-4-26b-a4b-it",
    temperature=0.0,
    max_tokens=512,
    timeout=60,
)
```

### CLI usage

```bash
# Run with cases loaded from a Python module
python run_benchmark.py run \
  --benchmark-name clerk-benchmark \
  --cases-module clerk_benchmark.cases \
  --scorer-module clerk_benchmark.scorer \
  --provider omniroute \
  --model google/gemma-4-26b-a4b-it

# Run multiple models
python run_benchmark.py run \
  --benchmark-name bouncer-benchmark \
  --cases-module bouncer_benchmark.cases \
  --models antigravity/gemini-3.1-flash-lite groq/llama-3.3-70b-versatile

# Render Obsidian report
python run_benchmark.py report \
  --benchmark-name clerk-benchmark \
  --db ~/.hermes/skills/benchmarks/clerk-benchmark/results/benchmark.db \
  --obsidian-dir ~/Obsidian/main-vault/40-Operations/Hermes/Benchmarks/clerk-benchmark

# Render leaderboard
python run_benchmark.py leaderboard \
  --benchmark-name clerk-benchmark \
  --db ~/.hermes/skills/benchmarks/clerk-benchmark/results/benchmark.db
```

### Module loading convention

For CLI mode, the cases module must expose `CASES: list[CaseDef]` and the scorer module must expose `score(response: str, case: CaseDef) -> tuple[bool, float, str]`. If `--scorer-module` is omitted, it defaults to `--cases-module`.

### Report templates

Markdown templates live in `benchmark-common/templates/`:
- `report.md` — full run results table + leaderboard
- `leaderboard.md` — best-score-per-model ranking

These templates use Handlebars-style `{{ variable }}` placeholders. The `render_obsidian_report()` and `render_leaderboard()` functions produce the final markdown.

### Migrating an existing benchmark skill

To migrate a benchmark skill from its own `run_*.py` to the unified runner:

1. Extract cases into a `CaseDef` list (or a module exposing `CASES`).
2. Extract the scoring logic into a function matching the `ScorerFn` signature.
3. Replace the custom `main()` with a thin wrapper that constructs `BenchmarkRunner` and calls `run()`.
4. Keep suite-specific scoring nuance (JSON validation, regex matching, etc.) in the subclass scorer — don't generalize it into the runner.
5. Verify DB writes match the existing schema (the runner uses `benchmark_common.record_case` and `benchmark_common.start_run`/`finish_run`).
6. Update the skill's runner path in its SKILL.md to point to `benchmark-common/scripts/run_benchmark.py`.

## Nuance by suite

- OCR: page manifests, rasterization parameters, and markdown sidecars matter; score tables/charts/scanned text separately.
- Clerk: strict JSON schema validity and Neo4j-safe properties are hard gates.
- Scout: tool-less uncertainty and handoff usefulness matter more than factual precision; facts must be validated downstream.
- Orchestrator: score operational judgment and safety, not just answer quality.
- Bouncer: binary compliance and speed matter; verbose reasoning is usually a failure.
- Coding: store patches, tests run, and failure logs; require repository cleanliness before and after.
