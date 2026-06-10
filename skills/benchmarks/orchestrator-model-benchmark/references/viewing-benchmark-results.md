# Retrieving Benchmark Results

When asked to read back scores or compare recent benchmark runs, do not attempt to write raw SQL against `benchmark.db` (which uses a generic `runs` schema and lacks tables like `messages` or `orchestrator_evals`). Also do not search for an `evaluate.py` script.

Instead, use the included CLI tool to parse and format the history:

```bash
# Target the benchmark's scripts directory:
cd ~/.hermes/skills/benchmarks/orchestrator-model-benchmark/scripts
python3 score_history.py --help
```

### Common Usage
- **Compare All:** `python3 score_history.py`
- **Summarize Specific Run:** `python3 score_history.py --model <run_alias>`
- **Generate Markdown Breakdown:** `python3 score_history.py --model <run_alias> --report` (This generates a sectioned report matching Obsidian formatting rules)

### Model Name Discovery

OmniRoute combo names do not always match stored benchmark aliases. For example:

| OmniRoute combo | Stored benchmark model name |
|---|---|
| `agy/gemini-pro-agent` | `gemini-pro-agent` |
| `agy/gemini-3.1-pro-high` | `google/gemini-3.1-pro-preview` |
| `agy/gemini-3-flash-agent` | `gemini-3-flash-agent` |

If `score_history.py --model <name> --report` returns empty output (exit 0, no text), the model name likely doesn't match. Discover stored names with:

```bash
sqlite3 ~/.hermes/skills/benchmarks/orchestrator-model-benchmark/results/benchmark.db \
  "SELECT DISTINCT model FROM runs ORDER BY model;"
```

This is the one acceptable use of direct SQL — listing distinct model names when the CLI tool doesn't surface them. Use it for discovery only; never for extracting scores.

### Cross-Model Comparison

To compare multiple candidates, run `score_history.py --model <name> --report` for each model separately, then synthesize. There is no built-in side-by-side comparison mode. When comparing, note:

- **Scenario coverage varies.** Some runs cover 3 scenarios (43–54 pts); full-suite runs cover 10 (135–180 pts). Normalise to percentages.
- **Scenarios in common.** Delegation Judgment (S4), Security Restraint (S5), and Incident Response (S6) appear in most runs and are the best basis for direct comparison.
- **Repeated runs.** The same model may have multiple runs on different dates. Use the most recent run per model, or average across runs if the user wants stability analysis.