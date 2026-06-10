# Legacy Benchmark Results Import

Use this when historical benchmark results exist in old Obsidian notes, skill tables, JSON run artifacts, or ad-hoc result files and need to populate the new benchmark system.

## Pattern

1. Load `model-benchmark`, the target benchmark skill, and `obsidian`.
2. Search both locations:
   - `~/.hermes/skills/benchmarks/<benchmark>/`
   - `~/Obsidian/Main Vault/`
3. Prefer structured artifacts first:
   - JSON run files (`results/*.json`)
   - existing SQLite DBs
   - old generated reports
   - skill result tables / Obsidian archive notes only if no run artifacts exist
4. Normalize into `~/.hermes/skills/benchmarks/<benchmark>/results/benchmark.db` using the common schema.
5. Use explicit legacy labels:
   - `benchmark_version=legacy-*`
   - `suite_version=<old-suite-name-or-date>`
   - `status=legacy-imported`
   - `base_url=legacy/<source>` or `legacy/manual`
6. Record provenance in `args_json` and `notes`:
   - source file path
   - scoring assumptions
   - manual/estimated fields
   - known bugs such as combo-name cost reporting
7. Write/update Obsidian results at:
   - `~/Obsidian/Main Vault/40-Operations/Hermes/Benchmarks/<benchmark>/<benchmark>-results.md`
8. Patch the overview version history to say legacy results were imported.

## Scoring Discipline

- Do not pretend legacy/manual scores are equivalent to future normalized harness scores.
- If old rows lack exact pass/fail thresholds, define a clearly provisional threshold in the results note.
- If token/cost values are estimated, set `cost_estimated=1` and say so in the table.
- If combo aliases hid the actual model, keep the alias and add a warning instead of inventing the selected model.

## Session Examples

- `deep-reasoning-benchmark`: imported 15 `v2-run-20260429T*.json` files into SQLite and rendered legacy V2 Asterion results.
- `complex-coding-benchmark`: imported legacy WAF Resiliency Patch results from the old Obsidian archive and skill table into SQLite.
- `bouncer-benchmark`: previous results were found in `40-Operations/Models/Benchmarks/Fast and Dumb/Fast and Dumb Binary Benchmark - 2026-04-22.md`; import them before treating the new results table as populated.
