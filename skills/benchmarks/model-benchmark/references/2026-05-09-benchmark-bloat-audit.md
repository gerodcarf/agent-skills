# Benchmark Bloat Audit & Consolidation — 2026-05-09

## Context
User requested evaluation of custom skill scripts for bloat and refactoring opportunities.

## Bloat Audit Results

### Methodology
1. `find ~/.hermes/skills/ -name '*.py' -o -name '*.sh' -o -name '*.js'` excluding venvs/caches
2. Total: ~57K lines across all skill scripts
3. Identified ~5,335 reducible lines (9.3%) across 8 categories

### Categories & Line Counts
| Priority | Category | Reducible Lines | Root Cause |
|----------|----------|----------------|------------|
| Critical | Quadruple `call_omniroute` defs | 140 | Python executes last def only; first 3 are dead code |
| High | Benchmark copy-paste (3 scripts) | 1,275 | dotenv, JSON parse, token cost, HTTP boilerplate duplicated |
| Medium | maps_client.py triple HTTP boilerplate | ~300 | Same urllib pattern ×3 for geocode/POI/route |
| Medium | cost_aggregation.py 28 SQL stamp-cuts | ~600 | Template SQL with minor WHERE differences |
| Medium | gray-rhino ↔ market-tripwires duplication | 2,220 | Full skill mirror between two directories |
| Medium | Ledger 4 overlapping import scripts | 1,949 | 4 scripts doing partial overlaps of same data |
| Low | pageindex prompt repetition | ~700 | Same system prompt blocks repeated across cases |
| Low | Other small duplications | 1,700 | Misc single-function duplicates |

## Refactoring Completed

### Item 1: Remove Quadruple `call_omniroute`
- File: `deep-reasoning-benchmark/scripts/run_v2_committee_benchmark.py`
- Deleted lines 360–498 (3 dead `call_omniroute` definitions)
- 780 → 642 lines (−138)

### Item 2: Consolidate Benchmark Copy-Paste into `benchmark_common.py`

#### Extended `benchmark_common.py`
- 154 → 468 lines (+314)
- Added: `load_dotenv()`, `load_dotenv_key()`, `read_op_secret()`, `omniroute_hermes_key()`, `_config_provider()`, `resolve_target()`, `ProviderConfig`, `parse_json_loose()`, `strip_json_fences()`, `classify_error()`, `token_cost_from_pricing()`, `fetch_openrouter_pricing()`, `resolve_pricing()`, `canonical_model_id()`, `chat_completion_raw()`, `chat_completion()` (high-level), `add_common_args()`, `CaseResult`, `finish_run()`, `record_case()`, `connect_db()`, `make_run_id()`, `extract_text_and_usage()`
- Schema version bumped 0.1.0 → 0.2.0

#### Refactored `run_cheap_benchmark.py`
- 760 → 654 (−106)
- Replaced 7 duplicated functions with imports + thin adapters (`ProviderConfig.from_target()`, `ProviderConfig.to_target()`, `call_model()` adapter, `ping_model()` adapter, `strip_json_wrapper()` wrapper)
- Renamed local `resolve_provider` → `resolve_provider_config` to avoid shadowing shared name

#### Refactored `run_clerk_benchmark.py`
- 769 → 703 (−66)
- Replaced 6 duplicated functions with imports + thin wrappers
- Kept `scalar_or_scalar_list()` locally (benchmark-specific)
- Kept `parse_json_output()` locally (different error-reporting contract)

#### Refactored `run_v2_committee_benchmark.py`
- 642 → 605 (−37 additional, −175 total from original)
- Replaced env loading, JSON parsing, token cost, and API call functions with shared wrappers

### Live API Smoke Tests (T3–T5)

After T1/T2 (static) passed, running T3 revealed a **runtime bug** introduced by the refactoring:

**Bug**: `chat_completion()` returns `(text, usage, latency_ms)` (3-tuple), but `run_clerk_benchmark.py` line 635 was unpacking the result as `resp, latency_ms = chat_completion_with_retries(...)`. This caused `ValueError: too many values to unpack (expected 2)` on every test case, resulting in 0/8 pass.

**Root cause**: The clerk benchmark's `chat_completion_with_retries` wrapper was passing through the return value of `chat_completion()` directly. The original clerk code expected a 2-tuple `(resp_dict, latency_ms)` from a local API call function, but the shared `chat_completion()` returns already-extracted `(text, usage, latency_ms)`.

**Fix**: Changed `chat_completion_with_retries` to call `chat_completion_raw()` (which returns `(resp_dict, latency_ms)`) and then call `extract_text_and_usage(resp)` internally. It now returns a 4-tuple `(text, usage, latency_ms, resp)` — giving the caller both extracted values AND the raw dict needed for `raw_json` storage.

**Test results after fix**:
- Cheap: 4/4 pass, acc 90/60/100/100%, cost $0.0026 ✓
- Clerk: 8/8 pass, score 0.927, cost $0.019 ✓
- Deep: score 92, cost $0.009 ✓
- No leftover duplicate function names across the 3 scripts ✓
- `benchmark_common` imports resolve from all consumers ✓

### Net Reduction
- ~345 lines of dead/duplicate code eliminated
- `benchmark_common.py` +314 but serves 3 consumers

## Remaining Bloat Items (Not Yet Done)
- maps_client.py: Extract HTTP boilerplate into shared `_request_json()` helper
- cost_aggregations.py: Template SQL with parameter substitution
- gray-rhino ↔ market-tripwires: Full skill merge or symlink
- Ledger scripts: Consolidate 4 scripts → 2
- pageindex: Extract shared prompt builder
- google_workspace.py: Deduplicate OAuth/mount logic
