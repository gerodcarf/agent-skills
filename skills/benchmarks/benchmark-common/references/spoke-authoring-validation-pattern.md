# Benchmark Spoke Authoring & Validation Pattern

Use this when creating a new benchmark spoke on top of `benchmark-common`.

## Shape

A spoke should specialize only:

- role/profile contract
- cases
- scorer
- rubric and interpretation notes

Execution, SQLite persistence, provider resolution, report rendering, and leaderboard logic stay in `benchmark-common`.

## Recommended file layout

```text
~/.hermes/skills/benchmarks/<spoke-name>/
├── SKILL.md
├── references/
│   └── rubric.md
└── scripts/
    └── <spoke>_cases.py
```

## Case module pattern

The case module should:

1. Add the benchmark-common scripts directory to `sys.path`.
2. Import `CaseDef` from `run_benchmark`.
3. Expose `CASES: list[CaseDef]`.
4. Expose `score(response: str, case: CaseDef) -> tuple[bool, float, str]`.

Example import shim:

```python
import sys
from pathlib import Path

_COMMON = Path.home() / ".hermes" / "skills" / "benchmarks" / "benchmark-common" / "scripts"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

from run_benchmark import CaseDef  # type: ignore
```

## `CaseDef.expected` convention

For structured/scored benchmark spokes, use `CaseDef.expected` as machine-readable scoring metadata, not as literal expected output. Encode it as JSON and parse it inside the scorer.

Example:

```python
expected=json.dumps({
    "required_sources": ["S1", "S2"],
    "required_terms": ["inventory", "market_knowledge_date"],
    "forbidden_terms": ["lookahead claim"],
    "required_next_action": "handoff_to_clerk",
    "min_facts": 5,
})
```

## Validation pattern

Before declaring the spoke done:

1. Import the module and print benchmark metadata/case IDs.
2. Score at least one deliberately well-formed synthetic response.
3. Assert that it passes and exceeds threshold.
4. Run `py_compile` on the case module.
5. List created files.

Example:

```bash
cd ~/.hermes/skills/benchmarks/<spoke-name>
PYTHONPATH="$PWD/scripts:$HOME/.hermes/skills/benchmarks/benchmark-common/scripts" \
python3 -m py_compile scripts/<spoke>_cases.py
```

For a full runner invocation:

```bash
cd ~/.hermes/skills/benchmarks/<spoke-name>
PYTHONPATH="$PWD/scripts:$HOME/.hermes/skills/benchmarks/benchmark-common/scripts" \
python3 ~/.hermes/skills/benchmarks/benchmark-common/scripts/run_benchmark.py run \
  --benchmark-name <spoke-name> \
  --benchmark-version <version> \
  --suite-version <suite-version> \
  --cases-module <spoke>_cases \
  --provider <provider> \
  --model '<model-id>' \
  --temperature 0.1 \
  --max-tokens 4000 \
  --db ~/.hermes/skills/benchmarks/<spoke-name>/results/benchmark.db
```

## Scorer nuance

When a scorer checks forbidden terms, distinguish between actual forbidden claims and explicit guardrail text. A model saying `"I avoided X"` inside a lookahead/safety guardrail may be correct; penalize only unsupported use outside the guardrail field.
