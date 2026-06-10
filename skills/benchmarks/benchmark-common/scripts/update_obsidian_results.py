#!/usr/bin/env python3
from __future__ import annotations
import argparse, sqlite3
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    ap.add_argument('--benchmark-name', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    con = sqlite3.connect(Path(args.db).expanduser())
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM benchmark_runs WHERE benchmark_name=? ORDER BY started_at DESC LIMIT 100", (args.benchmark_name,)).fetchall()
    lines = [
        f'# {args.benchmark_name} Results',
        '',
        'Generated from SQLite benchmark history. Do not hand-edit the table; add human notes below it.',
        '',
        '| Started UTC | Provider | Model | Suite | Status | Score | Pass | Avg ms | Tokens | Cost | Run |',
        '|---|---|---|---|---:|---:|---:|---:|---:|---:|---|',
    ]
    for r in rows:
        cost = f"${(r['cost_usd'] or 0):.6f}" + (' est' if r['cost_estimated'] else '')
        lines.append(f"| {r['started_at']} | {r['provider']} | `{r['model']}` | {r['suite_version']} | {r['status']} | {(r['score'] or 0):.3f} | {r['passed_cases']}/{r['total_cases']} | {(r['avg_latency_ms'] or 0):.0f} | {r['total_tokens']} | {cost} | `{r['run_id']}` |")
    lines += ['', '## Notes', '', '- Add benchmark interpretation and routing decisions here.']
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n')
    print(out)

if __name__ == '__main__':
    main()
