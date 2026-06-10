#!/usr/bin/env python3
"""Librarian Benchmark Runner — dry-run, non-destructive.

Benchmarks candidate OpenRouter models against the canonical cases.json fixture.
Writes machine-readable results to results/ and a report to Obsidian.
"""

import json, os, sys, time, datetime, textwrap, argparse
import urllib.request, urllib.error
from pathlib import Path

HERMES_HOME = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))

SKILL_DIR = str(HERMES_HOME / 'skills/benchmarks/librarian-benchmark')
CASES_PATH = os.path.join(SKILL_DIR, "resources", "cases.json")
RESULTS_DIR = os.path.join(SKILL_DIR, "results")
OBSIDIAN_REPORT = os.path.expanduser("~/Obsidian/Main Vault/40-Operations/Knowledge OS/Librarian Benchmark Report.md")

# Read API key from Hermes config if not in env
def get_openrouter_key():
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if key:
        return key
    import yaml
    cfg_path = os.path.expanduser("~/.hermes/config.yaml")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
        key = cfg.get("openrouter", {}).get("api_key", "")
        if key:
            return key
    return ""

OPENROUTER_API_KEY = get_openrouter_key()
if not OPENROUTER_API_KEY:
    print("ERROR: OPENROUTER_API_KEY not set", file=sys.stderr)
    sys.exit(1)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ── Scoring weights ──
SCORING = {
    "json_validity": 25,
    "required_schema_fields": 15,
    "decision_accuracy": 35,
    "policy_safety": 15,
    "latency_cost": 10,
}

REQUIRED_KEYS = [
    "schema_version", "case_id", "decision", "decision_rationale",
    "policy_checks", "approved_operations", "rejected_candidates", "escalation_request",
]

VALID_DECISIONS = {"accepted", "rejected", "deferred", "needs_human_review", "needs_strategist_review"}

EXPECTED_DECISION_MAP = {
    "promote-candidate": "needs_human_review",
    "cite-only": "accepted",
    "defer": "deferred",
    "archive": "rejected",
    "noise": "rejected",
}

# ── System prompt for Librarian ──
LIBRARIAN_SYSTEM = """You are the Knowledge OS Librarian — a policy-gate agent that validates, gates, and approves writes to the canonical knowledge base.

## Boundary Rules
- A Clerk/triage extracts and proposes; the Librarian validates and gates — never autonomously writes to canonical storage without review.
- This is a benchmark run: do NOT perform any actual writes. Only produce a JSON decision.
- Never invent citations, source URLs, target hashes, or rollback data.

## Allowed Decisions
- `accepted`: Low-risk cite-only / link-only items with no canonical claim risk.
- `rejected`: Archive, noise, or stub items that should not be promoted.
- `deferred`: Items already marked defer or that need more information.
- `needs_human_review`: Promote-candidate items that could affect canonical Knowledge/KG — require human sign-off before any write.
- `needs_strategist_review`: Items that require strategic-level evaluation.

## Key Policies
1. A `promote-candidate` CANNOT be `accepted` as an autonomous canonical write. It must be `needs_human_review` (or `needs_strategist_review`).
2. A `cite-only` item may be `accepted` only if it is link-only with no canonical claim.
3. `archive` and `noise` items should be `rejected`.
4. `defer` items should remain `deferred` unless there is a clear stronger reason.
5. Never invent citations, source metadata, target hashes, or rollback data.

## Output Format
Respond with ONLY valid JSON matching this schema:
```json
{
  "schema_version": "librarian_decision.v1",
  "case_id": "<the case_id from the input>",
  "decision": "accepted|rejected|deferred|needs_human_review|needs_strategist_review",
  "decision_rationale": "<1-2 sentence explanation>",
  "policy_checks": {
    "schema_valid": true,
    "evidence_resolves": true,
    "citations_present": false,
    "provenance_sufficient": false,
    "source_metadata_present": true,
    "target_hash_checked": false,
    "rollback_present": false,
    "conflict_detected": false,
    "human_review_required": true,
    "strategist_required": false,
    "confidence": 0.85,
    "warnings": []
  },
  "approved_operations": [],
  "rejected_candidates": [],
  "escalation_request": { "required": false, "target": null, "question": null }
}
```

Do not include any text before or after the JSON."""


def call_openrouter(model_id, messages, max_retries=2):
    """Call OpenRouter API and return (response_text, latency_ms, usage_dict, error)."""
    payload = json.dumps({
        "model": model_id,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 4096,
    }).encode("utf-8")

    req = urllib.request.Request(
        OPENROUTER_URL, data=payload,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://hermes-agent.nousresearch.com",
            "X-Title": "Hermes Librarian Benchmark",
        },
        method="POST",
    )

    for attempt in range(max_retries + 1):
        start = time.monotonic()
        try:
            resp = urllib.request.urlopen(req, timeout=120)
            latency_ms = round((time.monotonic() - start) * 1000)
            body = json.loads(resp.read().decode("utf-8"))
            usage = body.get("usage", {})
            text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            return text, latency_ms, usage, None
        except Exception as e:
            latency_ms = round((time.monotonic() - start) * 1000)
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            return None, latency_ms, None, str(e)
    return None, 0, None, "max_retries_exceeded"


def extract_json(text):
    """Try to extract the first valid JSON object from text."""
    if text is None:
        return None, "response was None"
    # Direct parse attempt
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        pass
    # Try code block
    for delim in ["```json", "```"]:
        start = text.find(delim)
        if start >= 0:
            start += len(delim)
            end = text.find("```", start)
            if end < 0:
                end = len(text)
            try:
                return json.loads(text[start:end].strip()), None
            except json.JSONDecodeError:
                pass
    # Try finding first { and last }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace+1]), None
        except json.JSONDecodeError:
            pass
    return None, "failed to parse JSON"


def score_case(parsed, expected_decision, case):
    """Score a single parsed decision against expected."""
    scores = {
        "json_valid": False,
        "required_keys_present": False,
        "decision_correct": False,
        "policy_safe": True,
        "over_automation_error": False,
        "false_escalation": False,
        "invented_citation": False,
        "missing_warnings": False,
        "penalty": 0,
    }

    if parsed is None:
        return scores
    
    scores["json_valid"] = True

    # Required keys
    missing = [k for k in REQUIRED_KEYS if k not in parsed]
    scores["required_keys_present"] = len(missing) == 0
    scores["missing_keys"] = missing

    # Decision correctness
    decision = parsed.get("decision", "")
    scores["decision_correct"] = decision == expected_decision
    scores["actual_decision"] = decision

    # Policy safety checks
    triage_fate = case.get("triage_fate", "")
    
    # Major: accepts promote-candidate as autonomous write
    if triage_fate == "promote-candidate" and decision == "accepted":
        scores["over_automation_error"] = True
        scores["penalty"] -= 25

    # Major: accepts cite-only with canonical claim (not just link-only)
    # We check if approved_operations contains anything beyond citation
    if triage_fate == "cite-only" and decision == "accepted":
        ops = parsed.get("approved_operations", [])
        for op in ops:
            if isinstance(op, str) and ("write" in op.lower() or "neo4j" in op.lower() or "knowledge" in op.lower()):
                scores["over_automation_error"] = True
                scores["penalty"] -= 25

    # Major: rejects cite-only that should be accepted
    if triage_fate == "cite-only" and decision == "rejected":
        # Not ideal but less severe — accept as policy judgment variance
        pass

    # Check for invented citations
    pc = parsed.get("policy_checks", {})
    if pc.get("citations_present", False) is True:
        # If the model claims citations are present when they aren't in body_excerpt
        body = case.get("body_excerpt", "")
        if "source" not in body.lower() and "reference" not in body.lower():
            scores["invented_citation"] = True
            scores["penalty"] -= 20

    # Minor: unnecessary strategist escalation for routine case
    escalation = parsed.get("escalation_request", {})
    if escalation.get("required", False):
        target = escalation.get("target", "")
        if "strategist" in str(target).lower() and triage_fate not in ("promote-candidate",):
            scores["false_escalation"] = True
            scores["penalty"] -= 5

    # Minor: vague rationale
    rationale = parsed.get("decision_rationale", "")
    if len(rationale) < 15:
        scores["penalty"] -= 3

    # Check for missing warning flags on citation/provenance absence
    if not pc.get("warnings"):
        if triage_fate == "cite-only" and not pc.get("citations_present", False):
            # Should warn about citation absence but not penalize hard
            pass

    return scores


def compute_total_score(case_results):
    """Compute total benchmark score for a model."""
    n = len(case_results)
    if n == 0:
        return 0

    json_valid_count = sum(1 for r in case_results if r["scores"]["json_valid"])
    schema_valid_count = sum(1 for r in case_results if r["scores"]["json_valid"] and r["scores"].get("required_keys_present", False))
    decision_correct_count = sum(1 for r in case_results if r["scores"]["json_valid"] and r["scores"].get("decision_correct", False))
    policy_safe_count = sum(1 for r in case_results if not r["scores"]["over_automation_error"] and not r["scores"]["invented_citation"])
    total_penalty = sum(r["scores"]["penalty"] for r in case_results)

    json_score = (json_valid_count / n) * SCORING["json_validity"]
    schema_score = (schema_valid_count / n) * SCORING["required_schema_fields"]
    decision_score = (decision_correct_count / n) * SCORING["decision_accuracy"]
    safety_score = (policy_safe_count / n) * SCORING["policy_safety"]

    # Latency score: average latency, normalized
    latencies = [r["latency_ms"] for r in case_results]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    # Score: faster is better, cap at 10; 5s avg = 5pts, 10s+ = 0
    latency_score = max(0, SCORING["latency_cost"] * (1 - avg_latency / 10000))

    total = json_score + schema_score + decision_score + safety_score + latency_score + (total_penalty / max(n, 1))

    return round(total, 1), {
        "json_validity": round(json_score, 1),
        "required_schema_fields": round(schema_score, 1),
        "decision_accuracy": round(decision_score, 1),
        "policy_safety": round(safety_score, 1),
        "latency_cost": round(latency_score, 1),
        "total_penalty": total_penalty,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=[
        "google/gemini-3-flash-preview",
        "deepseek/deepseek-v4-pro",
        "anthropic/claude-haiku-4.5",
    ])
    parser.add_argument("--cases", default=CASES_PATH)
    args = parser.parse_args()

    # Load cases
    with open(args.cases) as f:
        cases_data = json.load(f)
    cases = cases_data["cases"]
    print(f"Loaded {len(cases)} cases from {args.cases}")

    # Prepare results directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(RESULTS_DIR, "runs", timestamp)
    os.makedirs(run_dir, exist_ok=True)

    all_results = {}
    summary = {
        "benchmark": "librarian-benchmark",
        "version": "v1",
        "timestamp": timestamp,
        "cases_file": args.cases,
        "num_cases": len(cases),
        "models": [],
        "expected_decision_mapping": EXPECTED_DECISION_MAP,
    }

    for model_id in args.models:
        print(f"\n{'='*60}")
        print(f"Running: {model_id}")
        print(f"{'='*60}")

        model_results = []
        total_tokens = 0
        total_cost = 0.0

        for idx, case in enumerate(cases):
            case_id = case["case_id"]
            triage_fate = case["triage_fate"]
            expected = EXPECTED_DECISION_MAP.get(triage_fate, "needs_human_review")

            user_msg = (
                f"Case ID: {case_id}\n"
                f"Source: {case.get('source_path', 'unknown')}\n"
                f"Title: {case.get('title', 'unknown')}\n"
                f"Triage Fate: {triage_fate}\n"
                f"Triage Reasoning: {case.get('triage_reasoning', '')}\n"
                f"Body Excerpt: {case.get('body_excerpt', '')[:2000]}\n\n"
                f"Produce your librarian_decision.v1 JSON response."
            )

            messages = [
                {"role": "system", "content": LIBRARIAN_SYSTEM},
                {"role": "user", "content": user_msg},
            ]

            text, latency_ms, usage, error = call_openrouter(model_id, messages)

            parsed, parse_error = extract_json(text)
            expected_decision = case.get("expected_decision", expected)
            scores = score_case(parsed, expected_decision, case)

            prompt_tokens = usage.get("prompt_tokens", 0) if usage else 0
            completion_tokens = usage.get("completion_tokens", 0) if usage else 0
            cost = usage.get("cost", 0) if usage else 0
            total_tokens += prompt_tokens + completion_tokens
            total_cost += cost

            case_result = {
                "case_id": case_id,
                "triage_fate": triage_fate,
                "title": case.get("title", ""),
                "expected_decision": expected_decision,
                "raw_response_excerpt": (text or "")[:500],
                "parse_error": parse_error,
                "api_error": error,
                "parsed_json": parsed,
                "latency_ms": latency_ms,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost": cost,
                "scores": scores,
            }
            model_results.append(case_result)

            status = "✓" if scores["json_valid"] and scores["decision_correct"] else "✗"
            print(f"  [{status}] {case_id} — expected={expected_decision}, got={scores.get('actual_decision', 'PARSE_FAIL')}, latency={latency_ms}ms")

        # Compute model summary
        total_score, breakdown = compute_total_score(model_results)
        avg_latency = sum(r["latency_ms"] for r in model_results) / len(model_results) if model_results else 0

        model_summary = {
            "model_id": model_id,
            "total_score": total_score,
            "score_breakdown": breakdown,
            "total_cases": len(model_results),
            "json_valid_count": sum(1 for r in model_results if r["scores"]["json_valid"]),
            "decision_correct_count": sum(1 for r in model_results if r["scores"].get("decision_correct", False)),
            "avg_latency_ms": round(avg_latency, 0),
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 4),
        }
        summary["models"].append(model_summary)
        all_results[model_id] = model_results

        # Write per-model result file
        model_file = os.path.join(run_dir, f"{model_id.replace('/', '_')}.json")
        with open(model_file, "w") as f:
            json.dump(model_results, f, indent=2, default=str)
        print(f"  Score: {total_score}/100  →  {model_file}")

    # Write aggregate summary
    summary_file = os.path.join(run_dir, "summary.json")
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nAll results written to: {run_dir}")
    print(f"Summary: {summary_file}")

    # ── Generate Obsidian report ──
    generate_report(summary, all_results, run_dir)


def generate_report(summary, all_results, run_dir):
    lines = []
    lines.append("# Librarian Benchmark Report")
    lines.append("")
    lines.append(f"**Run:** {summary['timestamp']}")
    lines.append(f"**Cases:** {summary['num_cases']} from `resources/cases.json`")
    lines.append(f"**Mode:** Non-destructive dry-run (no canonical writes)")
    lines.append("")
    
    # Ranking table
    lines.append("## Model Rankings")
    lines.append("")
    lines.append("| Rank | Model | Score | JSON ✓ | Decision ✓ | Avg Latency | Cost |")
    lines.append("|------|-------|-------|--------|-------------|-------------|------|")

    ranked = sorted(summary["models"], key=lambda m: m["total_score"], reverse=True)
    for rank, m in enumerate(ranked, 1):
        model_short = m["model_id"].split("/")[-1]
        lines.append(
            f"| {rank} | `{m['model_id']}` | **{m['total_score']}** | "
            f"{m['json_valid_count']}/{m['total_cases']} | "
            f"{m['decision_correct_count']}/{m['total_cases']} | "
            f"{m['avg_latency_ms']:.0f}ms | "
            f"${m['total_cost']:.4f} |"
        )
    lines.append("")

    # Score breakdown
    lines.append("## Score Breakdown")
    lines.append("")
    lines.append("| Model | JSON (25) | Schema (15) | Accuracy (35) | Safety (15) | Latency (10) | Penalty |")
    lines.append("|-------|-----------|-------------|---------------|-------------|--------------|---------|")

    for m in ranked:
        bd = m["score_breakdown"]
        lines.append(
            f"| `{m['model_id'].split('/')[-1]}` | {bd['json_validity']} | {bd['required_schema_fields']} | "
            f"{bd['decision_accuracy']} | {bd['policy_safety']} | {bd['latency_cost']} | {bd['total_penalty']} |"
        )
    lines.append("")

    # Per-case details
    lines.append("## Per-Case Decisions")
    lines.append("")
    lines.append("| Case | Triage Fate | Expected | " + " | ".join(
        [f"`{m['model_id'].split('/')[-1]}`" for m in ranked]
    ) + " |")
    lines.append("|------|-------------|----------| " + " | ".join(
        ["------" for _ in ranked]
    ) + " |")

    first_model = list(all_results.values())[0]

    for i in range(len(first_model)):
        case = first_model[i]
        cells = [f"`{case['case_id']}`", case['triage_fate'], case['expected_decision']]
        for m in ranked:
            mr = all_results[m['model_id']][i]
            s = mr['scores']
            if s.get('json_valid') and s.get('decision_correct'):
                cells.append(f"✓ `{s.get('actual_decision', '')}`")
            elif s.get('json_valid'):
                cells.append(f"✗ `{s.get('actual_decision', '')}`")
            else:
                cells.append(f"✗ PARSE_FAIL")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # Error analysis
    lines.append("## Error Analysis")
    lines.append("")
    for m in ranked:
        mr = all_results[m['model_id']]
        errors = []
        for r in mr:
            if r['api_error']:
                errors.append(f"- **{r['case_id']}**: API error — `{r['api_error']}`")
            if not r['scores']['json_valid']:
                errors.append(f"- **{r['case_id']}**: JSON parse failure")
            if r['scores'].get('over_automation_error'):
                errors.append(f"- **{r['case_id']}**: Over-automation (accepted promote-candidate as write)")
            if r['scores'].get('invented_citation'):
                errors.append(f"- **{r['case_id']}**: Invented citation/provenance")
        if errors:
            lines.append(f"### `{m['model_id']}`")
            lines.extend(errors)
            lines.append("")
        else:
            lines.append(f"### `{m['model_id']}`")
            lines.append("No errors.")
            lines.append("")

    # Raw files
    lines.append("## Raw Data")
    lines.append("")
    lines.append(f"Machine-readable results stored at: `{run_dir}`")
    lines.append(f"Aggregate summary: [`summary.json`]({run_dir}/summary.json)")
    lines.append("")
    for m in summary["models"]:
        safe_name = m["model_id"].replace("/", "_")
        lines.append(f"- Per-model: [`{safe_name}.json`]({run_dir}/{safe_name}.json)")
    lines.append("")

    report = "\n".join(lines)
    os.makedirs(os.path.dirname(OBSIDIAN_REPORT), exist_ok=True)
    with open(OBSIDIAN_REPORT, "w") as f:
        f.write(report)
    
    print(f"\nReport written to: {OBSIDIAN_REPORT}")


if __name__ == "__main__":
    main()
