# Legacy Benchmark Result Import

Use this when older benchmark runs exist as JSON/markdown/log artifacts and the user wants Obsidian result tables populated without re-running expensive benchmarks.

## Procedure

1. Load `model-benchmark` and the specific benchmark skill.
2. Inspect legacy result shape first; do not assume keys. Typical fields seen in deep-reasoning V2:
   - run metadata: `run_id`, `candidate_model`, `candidate_provider`, `candidate_reasoning`, `case`
   - response: `candidate.content`
   - timing/cost: `candidate.elapsed_sec`, `candidate.cost_usd`, `candidate.usage.{prompt_tokens,completion_tokens,total_tokens,cost}`
   - scores: `heuristic_score.score`, `aggregate.final_score`, `aggregate.judge_average_score`, `aggregate.parsed_judge_count`, `aggregate.judge_count`, `aggregate.judge_parse_penalty`
3. Normalize into the common SQLite schema:
   - `benchmark_runs`: one row per legacy artifact
   - `benchmark_cases`: one row per scored case; keep raw aggregate/heuristic JSON excerpt in `raw_json`
   - `benchmark_usage`: one summary row per run
4. Prefix imported run IDs with `legacy-<suite>-` to avoid collision with new harness-generated IDs.
5. Mark `benchmark_version` as `legacy-<version>` and `suite_version` as the historical suite name.
6. Preserve provenance in `notes`: source filename, original case name, reasoning setting, heuristic score, judge average, parsed judge count, parse penalty.
7. Generate/update the Obsidian `<benchmark-name>-results.md` table from SQLite, but include a visible score/provenance note explaining that results are imported legacy runs.
8. Update `<benchmark-name>-overview.md` version history to record that legacy results were normalized.

## Pitfalls

- Combo aliases can have bad/zero cost if the old runner priced the requested combo name instead of the actual selected model. Call this out in notes; do not silently rank it as clean.
- Some legacy runs have no judge rows (`0/0`) but still have heuristic/final scores. Treat them as promising but dirty.
- Zero token/cost accounting in legacy files usually indicates provider/route instrumentation failure, not free inference.
- Do not paste full model responses into Obsidian tables; keep excerpts/raw JSON in SQLite.

## Example Outcome

Deep-reasoning V2 Asterion imports used:

```text
benchmark_version = legacy-v2
suite_version = v2-asterion
run_id = legacy-v2-<original_run_id>
```

The Obsidian result table included final score, pass threshold, judge average, heuristic score, parsed judges, elapsed time, tokens, and cost.