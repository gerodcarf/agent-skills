#!/usr/bin/env python3
"""Regenerate Obsidian benchmark reports from normalized benchmark SQLite DBs."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from normalize_benchmark_schema import normalize

DEFAULT_ROOT = Path.home() / "Obsidian" / "Main Vault" / "40-Operations" / "Hermes" / "Benchmarks"
BENCHMARKS_ROOT = Path.home() / ".hermes" / "skills" / "benchmarks"


def pct(value: float | None) -> str:
    if value is None:
        value = 0.0
    return f"{value * 100:.1f}%"


def money(value: float | None, estimated: int | None = 1) -> str:
    value = value or 0.0
    suffix = " est" if estimated else ""
    return f"${value:.6f}{suffix}"


def fetch_runs(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT * FROM common_benchmark_runs
        ORDER BY COALESCE(started_at, completed_at, run_id) DESC
        LIMIT 200
        """
    ).fetchall()


def fetch_case_summary(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT category,
               COUNT(*) AS cases,
               AVG(score) AS avg_score,
               SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS passed,
               AVG(latency_ms) AS avg_latency_ms,
               SUM(total_tokens) AS total_tokens,
               SUM(cost_usd) AS cost_usd
        FROM common_benchmark_cases
        GROUP BY category
        ORDER BY category
        """
    ).fetchall()


def render_results(benchmark_name: str, db_path: Path, runs: list[sqlite3.Row], case_summary: list[sqlite3.Row]) -> str:
    lines = [
        f"# {benchmark_name} Results",
        "",
        "Generated from the normalized benchmark SQLite views. Do not hand-edit generated tables; add human interpretation under Notes.",
        "",
        f"Source DB: `{db_path}`",
        "",
        "## Run History",
        "",
        "| Started UTC | Provider | Model | Suite | Status | Score | Pass | Avg ms | Tokens | Cost | Run |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    if not runs:
        lines.append("| _No runs_ |  |  |  |  |  |  |  |  |  |  |")
    for r in runs:
        lines.append(
            "| {started} | {provider} | `{model}` | {suite} | {status} | {score} | {passed}/{total} | {lat:.0f} | {tokens} | {cost} | `{run}` |".format(
                started=r["started_at"] or "",
                provider=r["provider"] or "",
                model=r["model"] or "",
                suite=r["suite_version"] or "",
                status=r["status"] or "",
                score=pct(r["score"]),
                passed=r["passed_cases"] or 0,
                total=r["total_cases"] or 0,
                lat=r["avg_latency_ms"] or 0,
                tokens=r["total_tokens"] or 0,
                cost=money(r["cost_usd"], r["cost_estimated"]),
                run=r["run_id"] or "",
            )
        )
    lines += [
        "",
        "## Case Category Summary",
        "",
        "| Category | Cases | Avg Score | Passed | Avg ms | Tokens | Cost |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    if not case_summary:
        lines.append("| _No cases_ | 0 | 0.0% | 0 | 0 | 0 | $0.000000 |")
    for r in case_summary:
        lines.append(
            f"| {r['category']} | {r['cases']} | {pct(r['avg_score'])} | {r['passed'] or 0} | {(r['avg_latency_ms'] or 0):.0f} | {r['total_tokens'] or 0} | {money(r['cost_usd'], 1)} |"
        )
    lines += [
        "",
        "## Notes",
        "",
        "- Add benchmark interpretation, routing recommendations, and review decisions here.",
    ]
    return "\n".join(lines) + "\n"


def render_overview(benchmark_name: str, db_path: Path, runs: list[sqlite3.Row]) -> str:
    latest = runs[0] if runs else None
    latest_line = "No runs found."
    if latest:
        latest_line = f"Latest run `{latest['run_id']}`: `{latest['model']}` scored {pct(latest['score'])} with status `{latest['status']}`."
    return "\n".join([
        f"# {benchmark_name} Overview",
        "",
        "This is the Obsidian report surface for the Hermes benchmark suite.",
        "",
        "## Canonical storage",
        "",
        f"- Skill-local DB: `{db_path}`",
        f"- Raw artifacts: `{db_path.parent / 'raw' / '<run_id>'}`",
        f"- Results report: `./{benchmark_name}-results.md`",
        "",
        "## Current status",
        "",
        latest_line,
        "",
        "## Routing discipline",
        "",
        "Benchmark results provide evidence for `model-routing`; they do not independently mutate production routing policy without review.",
        "Fallbacks should be disabled for candidate comparisons unless the suite explicitly tests fallback chains.",
        "",
    ]) + "\n"


def regenerate_one(benchmark_name: str, obsidian_root: Path) -> tuple[Path, Path, int]:
    db_path = BENCHMARKS_ROOT / benchmark_name / "results" / "benchmark.db"
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    normalize(db_path, benchmark_name)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        runs = fetch_runs(con)
        cases = fetch_case_summary(con)
    finally:
        con.close()
    out_dir = obsidian_root / benchmark_name
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / f"{benchmark_name}-results.md"
    overview_path = out_dir / f"{benchmark_name}-overview.md"
    results_path.write_text(render_results(benchmark_name, db_path, runs, cases))
    overview_path.write_text(render_overview(benchmark_name, db_path, runs))
    return overview_path, results_path, len(runs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--obsidian-root", default=str(DEFAULT_ROOT))
    ap.add_argument("benchmarks", nargs="*")
    args = ap.parse_args()
    obsidian_root = Path(args.obsidian_root).expanduser()
    benchmarks = args.benchmarks or [
        p.parent.parent.name for p in sorted(BENCHMARKS_ROOT.glob("*/results/benchmark.db"))
    ]
    for name in benchmarks:
        overview, results, run_count = regenerate_one(name, obsidian_root)
        print(f"{name}: {run_count} runs -> {overview}, {results}")


if __name__ == "__main__":
    main()
