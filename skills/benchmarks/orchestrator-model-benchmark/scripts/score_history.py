#!/usr/bin/env python3
"""
Query benchmark history from SQLite — trends, model comparisons, regression detection.
"""
import sqlite3
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent.parent / 'results' / 'benchmark.db'
RESULTS_DIR = Path(__file__).parent.parent / 'results'

DIMENSIONS = ["detection", "restraint", "permission", "communication", "scope", "accuracy"]


def get_connection():
    if not DB_PATH.exists():
        print("No benchmark database found. Run a benchmark first.")
        sys.exit(1)
    return sqlite3.connect(str(DB_PATH))


def show_history(model: str = None, scenario: str = None, limit: int = 20):
    """Show recent benchmark runs, optionally filtered."""
    conn = get_connection()
    c = conn.cursor()

    query = "SELECT run_id, model, timestamp, scenario, total, scorer_notes FROM runs WHERE 1=1"
    params = []
    if model:
        query += " AND model LIKE ?"
        params.append(f"%{model}%")
    if scenario:
        query += " AND scenario = ?"
        params.append(scenario)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    if not rows:
        print("No benchmark runs found.")
        return

    print(f"{'Run ID':<30} {'Model':<40} {'Date':<12} {'Scn':<4} {'Total':>5}  Notes")
    print("─" * 120)
    for row in rows:
        run_id, model_name, ts, scn, total, notes = row
        date_str = ts[:10] if ts else "?"
        total_str = f"{total}/18" if total else "—"
        notes_short = (notes[:50] + "...") if notes and len(notes) > 50 else (notes or "")
        print(f"{run_id:<30} {model_name:<40} {date_str:<12} {scn:<4} {total_str:>5}  {notes_short}")


def compare_models(scenario: str = None):
    """Compare average scores across models."""
    conn = get_connection()
    c = conn.cursor()

    query = """
        SELECT model,
               COUNT(*) as runs,
               AVG(total) as avg_total,
               AVG(detection) as avg_det, AVG(restraint) as avg_rest,
               AVG(permission) as avg_perm, AVG(communication) as avg_comm,
               AVG(scope) as avg_scope, AVG(accuracy) as avg_acc
        FROM runs
        WHERE 1=1
    """
    params = []
    if scenario:
        query += " AND scenario = ?"
        params.append(scenario)
    query += " GROUP BY model ORDER BY avg_total DESC"

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    if not rows:
        print("No data to compare.")
        return

    header = f"{'Model':<45} {'Runs':>4} {'Avg':>5}"
    for d in DIMENSIONS:
        header += f"  {d[:4]:>4}"
    print(header)
    print("─" * 95)

    for row in rows:
        model, runs, avg_total = row[0], row[1], row[2]
        avgs = row[3:9]
        line = f"{model:<45} {runs:>4} {avg_total:>5.1f}"
        for a in avgs:
            if a is not None:
                line += f"  {a:>4.1f}"
            else:
                line += f"  {'—':>4}"
        print(line)


def detect_regressions(model: str, window: int = 3):
    """Detect if a model's scores are dropping over the last N runs."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT run_id, timestamp, scenario, total,
               detection, restraint, permission, communication, scope, accuracy
        FROM runs
        WHERE model = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (model, window * 6))  # 6 scenarios per run
    rows = c.fetchall()
    conn.close()

    if len(rows) < 6:
        print(f"Not enough data for regression detection (need at least 6 runs, have {len(rows)})")
        return

    # Group by scenario and check trend
    by_scenario = {}
    for row in rows:
        scn = row[2]
        if scn not in by_scenario:
            by_scenario[scn] = []
        by_scenario[scn].append(row)

    regressions = []
    for scn, runs in by_scenario.items():
        if len(runs) < 2:
            continue
        recent = runs[0][3]  # total
        older_avg = sum(r[3] for r in runs[1:]) / len(runs[1:]) if len(runs) > 1 else recent
        if older_avg > 0 and recent < older_avg * 0.7:  # >30% drop
            regressions.append({
                "scenario": scn,
                "recent": recent,
                "older_avg": round(older_avg, 1),
                "drop": f"{((older_avg - recent) / older_avg * 100):.0f}%"
            })

    if regressions:
        print(f"⚠️  Regressions detected for {model}:")
        for r in regressions:
            print(f"  - {r['scenario']}: {r['recent']}/18 (was avg {r['older_avg']}, drop {r['drop']})")
    else:
        print(f"✅ No regressions detected for {model}")


def generate_obsidian_report(model: str = None, last_n: int = 5):
    """Generate an Obsidian-friendly markdown report."""
    conn = get_connection()
    c = conn.cursor()

    query = """
        SELECT run_id, model, timestamp, scenario,
               detection, restraint, permission, communication, scope, accuracy, total
        FROM runs
        WHERE 1=1
    """
    params = []
    if model:
        query += " AND model LIKE ?"
        params.append(f"%{model}%")
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(last_n * 6)

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    if not rows:
        return "No benchmark data."

    # Group by run_group
    run_groups = {}
    for row in rows:
        run_id = row[0]
        group = run_id.rsplit('_', 1)[0]
        if group not in run_groups:
            run_groups[group] = {"model": row[1], "timestamp": row[2], "scenarios": []}
        run_groups[group]["scenarios"].append(row)

    lines = ["# Orchestrator Model Benchmark\n"]

    for group, data in list(run_groups.items())[:last_n]:
        lines.append(f"## {data['timestamp'][:10]} — `{data['model']}`")
        lines.append("")

        grand_total = 0
        max_total = 0
        for row in data["scenarios"]:
            scn = row[3]
            total = row[10] or 0
            grand_total += total
            max_total += 18
            emoji = "🌟" if total >= 15 else "✅" if total >= 10 else "⚠️" if total >= 6 else "❌"
            lines.append(f"### {SCENARIOS.get(scn, {}).get('name', scn)} {emoji} {total}/18")

            for i, dim in enumerate(DIMENSIONS):
                val = row[4 + i]
                if val is not None:
                    dim_emoji = ["❌", "⚠️", "✅", "🌟"][val]
                    lines.append(f"- {dim}: {dim_emoji} {val}/3")
            lines.append("")

        pct = grand_total / max_total * 100 if max_total > 0 else 0
        lines.append(f"**Overall: {grand_total}/{max_total} ({pct:.0f}%)**\n")
        lines.append("---\n")

    report = "\n".join(lines)

    # Save
    ts = datetime.now().strftime('%Y%m%d')
    report_path = RESULTS_DIR / f"obsidian-report-{ts}.md"
    with open(report_path, 'w') as f:
        f.write(report)
    print(report)
    print(f"\nSaved: {report_path}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Benchmark History & Reports")
    parser.add_argument('--model', help='Filter by model name')
    parser.add_argument('--scenario', help='Filter by scenario ID')
    parser.add_argument('--compare', action='store_true', help='Compare models')
    parser.add_argument('--regress', action='store_true', help='Detect regressions (requires --model)')
    parser.add_argument('--report', action='store_true', help='Generate Obsidian report')
    parser.add_argument('--limit', type=int, default=20)

    # Need to import SCENARIOS for report generation
    sys.path.insert(0, str(Path(__file__).parent))
    from scenarios import SCENARIOS

    args = parser.parse_args()

    if args.compare:
        compare_models(args.scenario)
    elif args.regress:
        if not args.model:
            print("--regress requires --model")
            sys.exit(1)
        detect_regressions(args.model)
    elif args.report:
        generate_obsidian_report(args.model, args.limit)
    else:
        show_history(args.model, args.scenario, args.limit)
