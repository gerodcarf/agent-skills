#!/usr/bin/env python3
"""Merge multiple librarian benchmark runs into a single combined report."""

import json, os, glob, datetime
from pathlib import Path

HERMES_HOME = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))

SKILL_DIR = str(HERMES_HOME / 'skills/benchmarks/librarian-benchmark')
RESULTS_DIR = os.path.join(SKILL_DIR, "results")
OBSIDIAN_REPORT = os.path.expanduser("~/Obsidian/Main Vault/40-Operations/Knowledge OS/Librarian Benchmark Report.md")

SCORING = {
    "json_validity": 25, "required_schema_fields": 15,
    "decision_accuracy": 35, "policy_safety": 15, "latency_cost": 10,
}
REQUIRED_KEYS = [
    "schema_version", "case_id", "decision", "decision_rationale",
    "policy_checks", "approved_operations", "rejected_candidates", "escalation_request",
]
EXPECTED_DECISION_MAP = {
    "promote-candidate": "needs_human_review", "cite-only": "accepted",
    "defer": "deferred", "archive": "rejected", "noise": "rejected",
}

def extract_json(text):
    if text is None:
        return None, "response was None"
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        pass
    for delim in ["```json", "```"]:
        start = text.find(delim)
        if start >= 0:
            start += len(delim)
            end = text.find("```", start)
            if end < 0: end = len(text)
            try:
                return json.loads(text[start:end].strip()), None
            except json.JSONDecodeError:
                pass
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace+1]), None
        except json.JSONDecodeError:
            pass
    return None, "failed to parse JSON"

def score_case(parsed, expected_decision, case):
    scores = {"json_valid": False, "required_keys_present": False,
              "decision_correct": False, "policy_safe": True,
              "over_automation_error": False, "false_escalation": False,
              "invented_citation": False, "penalty": 0}
    if parsed is None:
        return scores
    scores["json_valid"] = True
    missing = [k for k in REQUIRED_KEYS if k not in parsed]
    scores["required_keys_present"] = len(missing) == 0
    decision = parsed.get("decision", "")
    scores["decision_correct"] = decision == expected_decision
    scores["actual_decision"] = decision
    triage_fate = case.get("triage_fate", "")
    if triage_fate == "promote-candidate" and decision == "accepted":
        scores["over_automation_error"] = True
        scores["penalty"] -= 25
    escalation = parsed.get("escalation_request", {})
    if escalation.get("required", False):
        target = escalation.get("target", "")
        if "strategist" in str(target).lower() and triage_fate not in ("promote-candidate",):
            scores["false_escalation"] = True
            scores["penalty"] -= 5
    rationale = parsed.get("decision_rationale", "")
    if len(rationale) < 15:
        scores["penalty"] -= 3
    return scores

def compute_total_score(case_results):
    n = len(case_results)
    if n == 0: return 0, {}
    json_valid_count = sum(1 for r in case_results if r["scores"]["json_valid"])
    schema_valid_count = sum(1 for r in case_results if r["scores"]["json_valid"] and r["scores"].get("required_keys_present", False))
    decision_correct_count = sum(1 for r in case_results if r["scores"]["json_valid"] and r["scores"].get("decision_correct", False))
    policy_safe_count = sum(1 for r in case_results if not r["scores"]["over_automation_error"] and not r["scores"]["invented_citation"])
    total_penalty = sum(r["scores"]["penalty"] for r in case_results)
    json_score = (json_valid_count / n) * SCORING["json_validity"]
    schema_score = (schema_valid_count / n) * SCORING["required_schema_fields"]
    decision_score = (decision_correct_count / n) * SCORING["decision_accuracy"]
    safety_score = (policy_safe_count / n) * SCORING["policy_safety"]
    latencies = [r["latency_ms"] for r in case_results]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    latency_score = max(0, SCORING["latency_cost"] * (1 - avg_latency / 10000))
    total = json_score + schema_score + decision_score + safety_score + latency_score + (total_penalty / max(n, 1))
    return round(total, 1), {
        "json_validity": round(json_score, 1), "required_schema_fields": round(schema_score, 1),
        "decision_accuracy": round(decision_score, 1), "policy_safety": round(safety_score, 1),
        "latency_cost": round(latency_score, 1), "total_penalty": total_penalty,
    }

def main():
    # Gather all per-model JSON files from all run dirs
    run_dirs = sorted(glob.glob(os.path.join(RESULTS_DIR, "runs", "*")))
    all_model_results = {}  # model_id -> list of case results
    all_model_stats = {}    # model_id -> summary stats

    case_info = {}  # case_id -> {title, triage_fate, expected}

    for run_dir in run_dirs:
        for fpath in glob.glob(os.path.join(run_dir, "*.json")):
            fname = os.path.basename(fpath)
            if fname == "summary.json":
                continue
            # Load model results
            with open(fpath) as f:
                results = json.load(f)
            if not results:
                continue
            # Extract model_id from filename or first result
            model_id = fname.replace(".json", "").replace("_", "/")
            # Try to find model_id in the results themselves
            # Actually the filename was already converted, but let's use the actual model_id
            # Better: extract from the first result's raw data or use a mapping
            # The filename format is {provider}_{model}.json with / replaced by _
            # But this is lossy. Let's load the summary.json from the same dir
            
            # Load summary to get actual model IDs
            summary_path = os.path.join(run_dir, "summary.json")
            if os.path.exists(summary_path):
                with open(summary_path) as f:
                    summary = json.load(f)
                # Map filename to model_id
                for m in summary.get("models", []):
                    mid = m["model_id"]
                    safe = mid.replace("/", "_")
                    if safe in fname:
                        model_id = mid
                        break

            # Load cases.json for scoring
            cases_path = os.path.join(SKILL_DIR, "resources", "cases.json")
            with open(cases_path) as f:
                cases_data = json.load(f)
            cases = cases_data["cases"]

            rescored = []
            for r in results:
                cid = r["case_id"]
                case = next((c for c in cases if c["case_id"] == cid), None)
                if case:
                    expected = EXPECTED_DECISION_MAP.get(case["triage_fate"], "needs_human_review")
                    expected = case.get("expected_decision", expected)
                    parsed, _ = extract_json(r.get("raw_response_excerpt", ""))
                    # Re-extract from full response if available
                    if r.get("parsed_json"):
                        parsed = r["parsed_json"]
                    scores = score_case(parsed, expected, case)
                    scores["actual_decision"] = parsed.get("decision", "N/A") if parsed else "PARSE_FAIL"
                    rescored.append({**r, "scores": scores, "expected_decision": expected})
                    case_info[cid] = {
                        "title": case.get("title", ""),
                        "triage_fate": case["triage_fate"],
                    }
                else:
                    rescored.append(r)
                    case_info[cid] = {"title": r.get("title", ""), "triage_fate": r.get("triage_fate", "")}

            all_model_results[model_id] = rescored
            total_score, breakdown = compute_total_score(rescored)
            avg_latency = sum(r["latency_ms"] for r in rescored) / len(rescored) if rescored else 0
            all_model_stats[model_id] = {
                "total_score": total_score, "score_breakdown": breakdown,
                "total_cases": len(rescored),
                "json_valid_count": sum(1 for r in rescored if r["scores"]["json_valid"]),
                "decision_correct_count": sum(1 for r in rescored if r["scores"].get("decision_correct", False)),
                "avg_latency_ms": round(avg_latency, 0),
                "total_tokens": sum(r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in rescored),
                "total_cost": round(sum(r.get("cost", 0) for r in rescored), 4),
            }

    # Rank models
    ranked = sorted(all_model_stats.keys(), key=lambda m: all_model_stats[m]["total_score"], reverse=True)

    # Generate combined report
    lines = []
    lines.append("# Librarian Benchmark Report — Combined")
    lines.append("")
    lines.append(f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Cases:** 12 from `resources/cases.json`")
    lines.append(f"**Mode:** Non-destructive dry-run (no canonical writes)")
    lines.append("")

    # Rankings
    lines.append("## Model Rankings")
    lines.append("")
    lines.append("| Rank | Model | Score | JSON ✓ | Decision ✓ | Avg Latency |")
    lines.append("|------|-------|-------|--------|------------|-------------|")
    for rank, mid in enumerate(ranked, 1):
        m = all_model_stats[mid]
        lines.append(f"| {rank} | `{mid}` | **{m['total_score']}** | {m['json_valid_count']}/{m['total_cases']} | {m['decision_correct_count']}/{m['total_cases']} | {m['avg_latency_ms']:.0f}ms |")
    lines.append("")

    # Score Breakdown
    lines.append("## Score Breakdown")
    lines.append("")
    lines.append("| Model | JSON (25) | Schema (15) | Accuracy (35) | Safety (15) | Latency (10) | Penalty |")
    lines.append("|-------|-----------|-------------|---------------|-------------|--------------|---------|")
    for mid in ranked:
        m = all_model_stats[mid]
        bd = m["score_breakdown"]
        short = mid.split("/")[-1]
        lines.append(f"| `{short}` | {bd['json_validity']} | {bd['required_schema_fields']} | {bd['decision_accuracy']} | {bd['policy_safety']} | {bd['latency_cost']} | {bd['total_penalty']} |")
    lines.append("")

    # Per-Case Grid
    lines.append("## Per-Case Decision Matrix")
    lines.append("")
    header_cols = ["| Case | Triage | Expected"] + [f" `{mid.split('/')[-1]}`" for mid in ranked]
    lines.append(" | ".join(header_cols) + " |")
    sep_cols = ["|------|--------|---------"] + ["------" for _ in ranked]
    lines.append(" | ".join(sep_cols) + " |")

    case_ids = sorted(case_info.keys())
    for cid in case_ids:
        ci = case_info[cid]
        cells = [f"`{cid[-8:]}`", ci["triage_fate"]]
        # Get expected from first model result
        first_mr = all_model_results[ranked[0]]
        expected = next((r["expected_decision"] for r in first_mr if r["case_id"] == cid), "?")
        cells.append(expected)
        for mid in ranked:
            mr = all_model_results[mid]
            r = next((x for x in mr if x["case_id"] == cid), None)
            if r and r["scores"].get("json_valid") and r["scores"].get("decision_correct"):
                cells.append(f"✓ `{r['scores']['actual_decision']}`")
            elif r and r["scores"].get("json_valid"):
                cells.append(f"✗ `{r['scores']['actual_demand']}`" if False else f"✗ `{r['scores'].get('actual_decision', '?')}`")
            elif r:
                cells.append("✗ PARSE")
            else:
                cells.append("—")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # Error Analysis
    lines.append("## Error Analysis")
    lines.append("")
    for mid in ranked:
        mr = all_model_results[mid]
        errors = []
        for r in mr:
            s = r["scores"]
            if r.get("api_error"):
                errors.append(f"- **{r['case_id'][-8:]}**: API error — `{r['api_error']}`")
            if not s["json_valid"]:
                errors.append(f"- **{r['case_id'][-8:]}**: JSON parse failure")
            if s.get("decision_correct") is False and s["json_valid"]:
                expected = r.get("expected_decision", "?")
                actual = s.get("actual_decision", "?")
                errors.append(f"- **{r['case_id'][-8:]}**: Wrong decision — expected `{expected}`, got `{actual}`")
            if s.get("over_automation_error"):
                errors.append(f"- **{r['case_id'][-8:]}**: Over-automation (accepted promote-candidate)")
            if s.get("false_escalation"):
                errors.append(f"- **{r['case_id'][-8:]}**: False escalation (strategist for routine case)")
        if errors:
            lines.append(f"### `{mid}`")
            lines.extend(errors)
            lines.append("")
        else:
            lines.append(f"### `{mid}`")
            lines.append("No errors — all 12 cases correct.")
            lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    if ranked:
        best = ranked[0]
        cheapest_fast = None
        for mid in ranked:
            if "haiku" in mid or "gpt-oss" in mid or "flash" in mid:
                if all_model_stats[mid]["avg_latency_ms"] < 2000:
                    cheapest_fast = mid
                    break
        lines.append(f"- **Best overall:** `{best}` (score {all_model_stats[best]['total_score']})")
        if cheapest_fast and cheapest_fast != best:
            lines.append(f"- **Best cost/performance:** `{cheapest_fast}` ({all_model_stats[cheapest_fast]['avg_latency_ms']:.0f}ms avg)")
        lines.append("")

    report = "\n".join(lines)

    # Write combined summary
    combined = {
        "benchmark": "librarian-benchmark",
        "combined": True,
        "timestamp": datetime.datetime.now().isoformat(),
        "models": {mid: all_model_stats[mid] for mid in ranked},
        "ranked": ranked,
    }
    combined_dir = os.path.join(RESULTS_DIR, "combined")
    os.makedirs(combined_dir, exist_ok=True)
    with open(os.path.join(combined_dir, "summary.json"), "w") as f:
        json.dump(combined, f, indent=2)

    os.makedirs(os.path.dirname(OBSIDIAN_REPORT), exist_ok=True)
    with open(OBSIDIAN_REPORT, "w") as f:
        f.write(report)

    print(f"Combined report written to: {OBSIDIAN_REPORT}")
    print(f"Combined JSON: {os.path.join(combined_dir, 'summary.json')}")
    print(f"\nRanked: {[m.split('/')[-1] for m in ranked]}")

if __name__ == "__main__":
    main()
