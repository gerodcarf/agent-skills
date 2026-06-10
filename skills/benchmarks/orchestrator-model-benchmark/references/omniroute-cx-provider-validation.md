# OmniRoute `cx/` Provider — Orchestrator Benchmark Validation

**Date:** 2026-05-16
**Model tested:** `cx/gpt-5.5-medium` → resolved to `gpt-5.5`
**Result:** 83/108 (77%) — #2 on the S1-S6 leaderboard

## What Was Validated

The OmniRoute `cx/` provider (OpenAI Codex subscription) has full function-calling tool support. All 6 orchestrator benchmark scenarios (S1-S6) ran successfully with `read_file` and `search_files` tools. The model made up to 5 tool-turn iterations per scenario without issue.

## How to Run

```bash
cd ~/.hermes/skills/benchmarks/orchestrator-model-benchmark
python3 scripts/managed_run.py omniroute cx/<model-id> "<label>"
```

**Prerequisites:**
- `OMNIROUTE_URL` env var set (e.g., `https://omniroute.cow-hippocampus.ts.net`)
- OmniRoute API key in `storage.sqlite` table `api_keys` with name `Hermes`
- `managed_run.py` resolves both automatically

## Script Bug Fixed This Session

`managed_run.py` had literal `${OMNIROUTE_URL}` strings in the ping and base_url setup (lines ~192, ~215). These were shell-style variables that Python does NOT resolve. Fixed to use `os.environ.get('OMNIROUTE_URL', 'https://omniroute.cow-hippocampus.ts.net')`.

## Verified Behavior

- Ping: direct curl to `{OMNIROUTE_URL}/v1/chat/completions` with `POST {"model":"cx/gpt-5.5-medium","messages":[{"role":"user","content":"ping"}],"stream":false}` → 200 OK
- Tool calls: model correctly invoked `read_file` and `search_files` functions
- Scoring: auto-scoring via `record_score()` worked with no modifications
- Summarize: `summarize_run()` generated the benchmark report

## Obsidian Logging Failure

`update_obsidian_log()` crashes if the target directory `Hermes/Benchmarks/Orchestrator/` doesn't exist under the Obsidian vault. This is a non-fatal error — benchmark results are still saved to SQLite.

## Cost

No cost data captured because `managed_run.py` doesn't save `usage.json` files. If cost tracking is needed, use `run_with_tools.py` (OpenRouter) instead, or manually pipe `$OMNIROUTE_URL/v1/chat/completions` responses.