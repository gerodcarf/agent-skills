#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

COMMON = Path(__file__).resolve().parents[1].parent / 'model-benchmark' / 'scripts'
sys.path.insert(0, str(COMMON))
from benchmark_common import (  # type: ignore
    CaseResult, add_common_args, chat_completion, connect_db, extract_text_and_usage,
    finish_run, make_run_id, record_case, resolve_target, start_run,
)

BENCHMARK_NAME = 'bouncer-benchmark'
BENCHMARK_VERSION = '0.1.0'

CASES = [
    {'id':'signal_tesla','category':'clear_yes','input':'Tesla Inc., Austin, Texas, is awarded a $98,000,000 firm-fixed-price contract for providing lithium-ion battery modules for the Department of Defense.','expected':'YES'},
    {'id':'signal_lockheed','category':'clear_yes','input':'Lockheed Martin Corp., Orlando, Florida, is awarded $150,000,000 for the production of advanced quantum sensing systems for high-altitude reconnaissance.','expected':'YES'},
    {'id':'noise_maintenance','category':'clear_no','input':'Standard Electric Co., Denver, Colorado, is awarded a $5,000,000 contract for routine electrical maintenance at Buckley SFB.','expected':'NO'},
    {'id':'noise_food','category':'clear_no','input':'Aramark Services, Philadelphia, Pennsylvania, is awarded a $120,000,000 contract for food service operations at Fort Bragg.','expected':'NO'},
    {'id':'noise_construction','category':'noise','input':'Turner Construction Co., New York, NY, is awarded a $500,000,000 contract for building a new administrative facility for the VA.','expected':'NO'},
    {'id':'borderline_energy','category':'borderline','input':'Sion Power Corp. receives a $52,000,000 prototype award for high-density lithium-metal cells for unmanned aerial systems.','expected':'YES'},
]

PROMPT = "Is this a deep-tech/lithium/energy supply chain award with a value > $50,000,000? Return ONLY YES or NO.\n\nAward: {input}"

def score_response(text: str, expected: str) -> tuple[bool, float, str]:
    cleaned = (text or '').strip().upper()
    format_ok = cleaned in {'YES','NO'}
    passed = format_ok and cleaned == expected
    notes = '' if format_ok else 'malformed output; expected exactly YES or NO'
    return passed, 1.0 if passed else 0.0, notes

def render_obsidian(db: str, obsidian_dir: str):
    import subprocess
    out = Path(obsidian_dir).expanduser() / f'{BENCHMARK_NAME}-results.md'
    script = COMMON / 'update_obsidian_results.py'
    subprocess.run([sys.executable, str(script), '--db', db, '--benchmark-name', BENCHMARK_NAME, '--out', str(out)], check=False)

def main():
    ap = argparse.ArgumentParser(description='Run bouncer YES/NO benchmark')
    add_common_args(ap)
    ap.set_defaults(benchmark_version=BENCHMARK_VERSION, max_tokens=10)
    args = ap.parse_args()
    target = resolve_target(args.provider, args.model, args.base_url, args.api_key)
    con = connect_db(args.db)
    run_id = make_run_id(BENCHMARK_NAME, target.model.replace('/','_'))
    start_run(con, run_id, BENCHMARK_NAME, args, target)
    status, error = 'completed', ''
    try:
        for c in CASES:
            prompt = PROMPT.format(input=c['input'])
            try:
                resp, latency_ms = chat_completion(target, [{'role':'user','content':prompt}], temperature=args.temperature, max_tokens=args.max_tokens, timeout=args.timeout)
                text, usage = extract_text_and_usage(resp)
                passed, score, notes = score_response(text, c['expected'])
                record_case(con, run_id, CaseResult(
                    case_id=c['id'], category=c['category'], prompt=prompt, expected=c['expected'], response=text.strip(),
                    passed=passed, score=score, latency_ms=latency_ms, prompt_tokens=usage['prompt_tokens'], completion_tokens=usage['completion_tokens'], total_tokens=usage['total_tokens'],
                    cost_usd=0.0, cost_estimated=True, notes=notes, raw_json=json.dumps(resp)[:8000]
                ))
            except Exception as e:
                record_case(con, run_id, CaseResult(case_id=c['id'], category=c['category'], prompt=prompt, expected=c['expected'], response='', passed=False, score=0.0, latency_ms=0, error=str(e)))
        finish_run(con, run_id, status)
    except Exception as e:
        status, error = 'failed', str(e)
        finish_run(con, run_id, status, error)
        raise
    finally:
        if args.obsidian_dir:
            render_obsidian(args.db, args.obsidian_dir)
    row = con.execute('SELECT score, passed_cases, total_cases, avg_latency_ms, total_tokens, cost_usd FROM benchmark_runs WHERE run_id=?', (run_id,)).fetchone()
    print(f"{run_id} score={row['score']:.3f} pass={row['passed_cases']}/{row['total_cases']} avg_ms={row['avg_latency_ms']:.0f} tokens={row['total_tokens']} cost=${row['cost_usd']:.6f}")

if __name__ == '__main__':
    main()
