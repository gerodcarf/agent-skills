#!/usr/bin/env python3
"""
Orchestrator Model Benchmark Runner

Prepares benchmark fixtures, generates prompts, and records scored results.
Designed to be called by the agent (via execute_code or terminal), not standalone.

Usage:
  # Agent calls: prepare all scenarios for a run
  python3 run_benchmark.py prepare --model MODEL_ID

  # Agent calls: score a completed response and store in DB
  python3 run_benchmark.py score --run-id RUN_ID --scenario S1 --response-file PATH

  # Agent calls: after all scenarios scored, generate summary
  python3 run_benchmark.py summarize --run-group RUN_GROUP_ID
"""
import json
import os
import sys
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add scripts dir for imports
sys.path.insert(0, str(Path(__file__).parent))

from scenarios import SCENARIOS, S3_TASKS, S5_SCENARIOS, S6_LOG, S8_TASKS, S9_TASKS, S10_SCENARIOS
from score_results import score_scenario
from init_db import DB_PATH

SKILL_DIR = Path(__file__).parent.parent
RESULTS_DIR = SKILL_DIR / 'results'
RUNS_DIR = RESULTS_DIR / 'runs'


def ensure_dirs():
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def prepare_run(model: str, scenarios: list[str] = None) -> dict:
    """Prepare fixtures and prompts for a benchmark run. Returns run manifest."""
    if scenarios is None:
        scenarios = list(SCENARIOS.keys())

    run_group = datetime.now().strftime('%Y%m%d_%H%M%S')
    manifest = {
        "run_group": run_group,
        "model": model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scenarios": {},
    }

    ensure_dirs()
    run_dir = RUNS_DIR / run_group
    run_dir.mkdir(exist_ok=True)

    for sid in scenarios:
        if sid not in SCENARIOS:
            continue
        scenario = SCENARIOS[sid]

        # Generate fixtures
        scenario_work_dir = run_dir / sid
        scenario_work_dir.mkdir(exist_ok=True)
        fixtures = scenario["generate_fixtures"](scenario_work_dir)

        # Build prompt
        prompt = _build_prompt(sid, scenario, fixtures, scenario_work_dir)

        # Save prompt
        prompt_path = scenario_work_dir / "prompt.txt"
        with open(prompt_path, 'w') as f:
            f.write(prompt)

        # Save fixtures metadata
        fixtures_path = scenario_work_dir / "fixtures.json"
        with open(fixtures_path, 'w') as f:
            json.dump(fixtures, f, indent=2, default=str)

        run_id = f"{run_group}_{sid}"
        manifest["scenarios"][sid] = {
            "run_id": run_id,
            "name": scenario["name"],
            "prompt_path": str(prompt_path),
            "fixtures_path": str(fixtures_path),
            "response_path": str(scenario_work_dir / "response.txt"),
        }

    # Save manifest
    manifest_path = run_dir / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(json.dumps(manifest, indent=2))
    return manifest


def _build_prompt(sid: str, scenario: dict, fixtures: dict, work_dir: Path) -> str:
    """Build the full prompt for a scenario."""
    template = scenario["prompt_template"]

    if sid == "S1":
        return template.format(config_path=fixtures["config_path"])

    elif sid == "S2":
        questions_text = ""
        for i, q in enumerate(fixtures["questions"], 1):
            questions_text += f"Q{i}: {q['q']}\n"
        return template.format(
            memory_path=fixtures["memory_path"],
            questions_text=questions_text,
        )

    elif sid == "S3":
        # Run all 3 tasks
        prompts = []
        for task in S3_TASKS:
            prompts.append(template.format(task_description=task["task"]))
        return "\n---\n".join(prompts)

    elif sid == "S5":
        prompts = []
        for s in S5_SCENARIOS:
            prompts.append(template.format(scenario_prompt=s["prompt"]))
        return "\n---\n".join(prompts)

    elif sid == "S6":
        return template.format(log_content=fixtures.get("log_content", S6_LOG))

    elif sid == "S7":
        return template.format(work_dir=str(work_dir))

    elif sid == "S8":
        prompts = []
        for task in S8_TASKS:
            prompts.append(template.format(task_description=task["task"]))
        return "\n---\n".join(prompts)

    elif sid == "S9":
        tasks_text = ""
        for i, task in enumerate(S9_TASKS, 1):
            tasks_text += f"Task {i}: {task['task']}\n\n"
        return template.format(routing_table=fixtures["routing_table"], tasks_text=tasks_text)

    elif sid == "S10":
        prompts = []
        for s in fixtures["scenarios"]:
            prompts.append(template.format(profile=fixtures["profile"], scenario_prompt=s["prompt"]))
        return "\n---\n".join(prompts)

    # S4 has no variables
    return template


def record_score(run_id: str, scenario_id: str, model: str, response: str, fixtures: dict) -> dict:
    """Score a response and store in the database. All 6 dimensions always stored."""
    scores = score_scenario(scenario_id, response, fixtures)

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO runs
        (run_id, model, timestamp, scenario, detection, restraint, permission,
         communication, scope, accuracy, total, response_text, scorer_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run_id,
        model,
        datetime.now(timezone.utc).isoformat(),
        scenario_id,
        scores.get("detection"),
        scores.get("restraint"),
        scores.get("permission"),
        scores.get("communication"),
        scores.get("scope"),
        scores.get("accuracy"),
        scores.get("total"),
        response[:10000],  # truncate long responses
        scores.get("notes", ""),
    ))
    conn.commit()
    conn.close()

    # Also save response to file
    run_dir = RUNS_DIR / run_id.rsplit('_', 1)[0] / scenario_id
    run_dir.mkdir(parents=True, exist_ok=True)
    response_path = run_dir / "response.txt"
    with open(response_path, 'w') as f:
        f.write(response)

    print(json.dumps({"run_id": run_id, "scores": scores}, indent=2))
    return scores


def summarize_run(run_group: str) -> str:
    """Generate a summary report for a run group."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute("""
        SELECT scenario, detection, restraint, permission, communication,
               scope, accuracy, total, scorer_notes
        FROM runs
        WHERE run_id LIKE ?
        ORDER BY scenario
    """, (f"{run_group}_%",))
    rows = c.fetchall()

    if not rows:
        conn.close()
        return f"No results found for run group {run_group}"

    # Get model name
    c.execute("SELECT model FROM runs WHERE run_id LIKE ? LIMIT 1", (f"{run_group}_%",))
    model_row = c.fetchone()
    model = model_row[0] if model_row else "unknown"
    conn.close()

    lines = [f"## Benchmark Report — {run_group}", f"**Model:** `{model}`\n"]

    dimensions = ["detection", "restraint", "permission", "communication", "scope", "accuracy"]
    dim_totals = {d: 0 for d in dimensions}
    dim_counts = {d: 0 for d in dimensions}
    grand_total = 0
    max_total = 0

    for row in rows:
        scenario = row[0]
        total = row[7] or 0
        notes = row[8] or ""
        grand_total += total
        max_total += 18  # 6 dimensions × 3 max

        lines.append(f"### {SCENARIOS[scenario]['name']} ({scenario})")
        lines.append(f"**Total:** {total}/18")

        for i, dim in enumerate(dimensions):
            val = row[i + 1]
            if val is not None:
                emoji = ["❌", "⚠️", "✅", "🌟"][val]
                lines.append(f"- {dim}: {emoji} {val}/3")
                dim_totals[dim] += val
                dim_counts[dim] += 1

        if notes:
            lines.append(f"\n*{notes}*")
        lines.append("")

    # Dimension averages
    lines.append("### Dimension Averages")
    for dim in dimensions:
        if dim_counts[dim] > 0:
            avg = dim_totals[dim] / dim_counts[dim]
            emoji = ["❌", "⚠️", "✅", "🌟"][round(avg)]
            lines.append(f"- {dim}: {emoji} {avg:.1f}/3 (across {dim_counts[dim]} scenarios)")

    lines.append(f"\n**Grand Total:** {grand_total}/{max_total} ({grand_total/max_total*100:.0f}%)")

    report = "\n".join(lines)

    # Save to results
    report_path = RESULTS_DIR / f"report-{run_group}.md"
    with open(report_path, 'w') as f:
        f.write(report)
    print(report)

    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Orchestrator Model Benchmark")
    sub = parser.add_subparsers(dest='command')

    prep = sub.add_parser('prepare', help='Prepare benchmark run')
    prep.add_argument('--model', required=True, help='Model ID to benchmark')
    prep.add_argument('--scenarios', nargs='*', help='Scenario IDs (default: all)')

    scr = sub.add_parser('score', help='Score a response')
    scr.add_argument('--run-id', required=True)
    scr.add_argument('--scenario', required=True)
    scr.add_argument('--response-file', required=True)
    scr.add_argument('--fixtures-file', required=True)

    summ = sub.add_parser('summarize', help='Summarize a run group')
    summ.add_argument('--run-group', required=True)

    args = parser.parse_args()

    if args.command == 'prepare':
        prepare_run(args.model, args.scenarios)
    elif args.command == 'score':
        with open(args.response_file) as f:
            response = f.read()
        with open(args.fixtures_file) as f:
            fixtures = json.load(f)
        record_score(args.run_id, args.scenario, "unknown", response, fixtures)
    elif args.command == 'summarize':
        summarize_run(args.run_group)
    else:
        parser.print_help()
