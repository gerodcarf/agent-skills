#!/usr/bin/env python3
"""
answer-panel: Fan-out reasoning panel with judge synthesis.

Send a prompt to N models in parallel through OmniRoute, then use a judge model
to synthesize their responses into a single grounded answer.

Usage:
    python3 panel.py "Your question here"
    python3 panel.py --preset budget "Your question"
    python3 panel.py --panel "model1,model2,model3" --judge frontier "Your question"
    python3 panel.py --json "Your question"
    echo "Long prompt..." | python3 panel.py --stdin
"""

import argparse
import concurrent.futures
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# ─── Config ───────────────────────────────────────────────────────────────────

BASE_URL = os.environ.get("OMNIROUTE_BASE_URL", "http://localhost:20128/v1")
API_KEY = os.environ.get("OMNIROUTE_API_KEY", "")
DEFAULT_PANEL = os.environ.get(
    "PANEL_DEFAULT_PANEL",
    "gemini-cli/gemini-3.1-pro-preview,openrouter/x-ai/grok-4.3,openrouter/deepseek/deepseek-v4-pro",
)
DEFAULT_JUDGE = os.environ.get("PANEL_DEFAULT_JUDGE", "orchestrator")
PRESETS_PATH = Path(__file__).parent / "presets.json"

# ─── Judge Synthesis Prompt ──────────────────────────────────────────────────

JUDGE_PROMPT = """You are the judge of a panel of AI models. Each panelist was asked the same question. Your job is to synthesize their responses into a single, best possible answer.

## Panelist Responses

{panelist_responses}

## Your Task

1. **Agreement**: Identify key points where most or all panelists agree. These are high-confidence.
2. **Disagreement**: Identify where panelists contradict each other or give materially different answers. Flag these explicitly.
3. **Coverage**: Note important points that only one panelist raised (unique insights) and gaps that all panelists missed.
4. **Synthesize**: Produce a final answer that is grounded in the panel's collective intelligence. Do not blindly majority-vote — weigh arguments on their merits.

## Output Format

Give your answer in this structure:

### Final Answer
[Your synthesized answer. Be direct and comprehensive.]

### Points of Agreement
- [Point 1]
- [Point 2]

### Points of Disagreement
- [Disagreement 1 — which panelists said what]
- [Or: "No material disagreements among panelists."]

### Unique Insights
- [Insights only one panelist raised]
"""

# ─── API Call ─────────────────────────────────────────────────────────────────


def call_model(model: str, messages: list, max_tokens: int = 4096, timeout: int = 120) -> dict:
    """Call an OpenAI-compatible chat completion endpoint. Returns dict with content, model, error."""
    url = f"{BASE_URL}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
        "temperature": 0.7,
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            choice = data["choices"][0]["message"]
            return {
                "content": choice.get("content", "").strip(),
                "model": data.get("model", model),
                "requested_model": model,
                "usage": data.get("usage", {}),
                "error": None,
            }
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:500]
        except Exception:
            pass
        return {"content": "", "model": model, "requested_model": model, "usage": {}, "error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"content": "", "model": model, "requested_model": model, "usage": {}, "error": str(e)}


# ─── Panel Fan-Out ────────────────────────────────────────────────────────────


def fan_out(panel_models: list, query: str, system_prompt: Optional[str] = None, max_tokens: int = 4096) -> list:
    """Send query to all panel models in parallel. Returns list of result dicts."""
    def make_messages():
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": query})
        return messages

    messages = make_messages()

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(panel_models)) as executor:
        futures = {
            executor.submit(call_model, model, messages, max_tokens): model
            for model in panel_models
        }
        results = []
        for future in concurrent.futures.as_completed(futures):
            model = futures[future]
            try:
                result = future.result()
            except Exception as e:
                result = {"content": "", "model": model, "requested_model": model, "usage": {}, "error": str(e)}
            results.append(result)

    # Sort by original panel order for deterministic output
    order = {m: i for i, m in enumerate(panel_models)}
    results.sort(key=lambda r: order.get(r["requested_model"], 999))
    return results


# ─── Judge Synthesis ──────────────────────────────────────────────────────────


def synthesize(panel_results: list, query: str, judge_model: str, system_prompt: Optional[str] = None) -> dict:
    """Send all panel responses to a judge model for synthesis."""
    # Build anonymized panelist responses
    letters = "ABCDEFGHIJ"
    panelist_text = []
    for i, r in enumerate(panel_results):
        if r["error"]:
            panelist_text.append(f"### Panelist {letters[i]} ({r['requested_model']})\n[ERROR: {r['error']}]")
        else:
            panelist_text.append(f"### Panelist {letters[i]} ({r['model']})\n{r['content']}")

    judge_body = JUDGE_PROMPT.format(panelist_responses="\n\n".join(panelist_text))

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "system", "content": judge_body})
    messages.append({"role": "user", "content": f"Original question: {query}\n\nSynthesize the panel responses above into a final answer."})

    return call_model(judge_model, messages, max_tokens=4096, timeout=180)


# ─── Presets ──────────────────────────────────────────────────────────────────


def load_preset(name: str) -> dict:
    """Load a named panel preset from presets.json."""
    if not PRESETS_PATH.exists():
        sys.exit(f"Error: presets.json not found at {PRESETS_PATH}")
    with open(PRESETS_PATH) as f:
        presets = json.load(f)
    if name not in presets:
        available = ", ".join(sorted(presets.keys()))
        sys.exit(f"Error: preset '{name}' not found. Available: {available}")
    return presets[name]


# ─── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Fan-out reasoning panel with judge synthesis.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  panel.py 'What are the risks of ASML right now?'\n"
               "  panel.py --preset budget 'Quick question'\n"
               "  panel.py --panel 'model1,model2' --judge frontier 'Question'\n"
               "  panel.py --json 'Question' | python3 -m json.tool\n",
    )
    parser.add_argument("query", nargs="?", help="The question/prompt for the panel")
    parser.add_argument("--stdin", action="store_true", help="Read query from stdin")
    parser.add_argument("--panel", default=None, help="Comma-separated panel model slugs")
    parser.add_argument("--judge", default=None, help="Judge model slug (default: frontier)")
    parser.add_argument("--preset", default=None, help="Named preset from presets.json")
    parser.add_argument("--system", default=None, help="System prompt for panelists and judge")
    parser.add_argument("--json", action="store_true", help="Output full result as JSON")
    parser.add_argument("--max-tokens", type=int, default=4096, help="Max tokens per panelist response")
    parser.add_argument("--judge-prompt-file", default=None, help="Custom judge prompt template file")
    parser.add_argument("--list-presets", action="store_true", help="List available presets and exit")
    args = parser.parse_args()

    # List presets
    if args.list_presets:
        with open(PRESETS_PATH) as f:
            presets = json.load(f)
        for name, p in sorted(presets.items()):
            panel_str = ", ".join(p["panel"][:3]) + ("..." if len(p["panel"]) > 3 else "")
            print(f"  {name:15s}  {p.get('description', '')}")
            print(f"  {'':15s}  Panel: {panel_str}  Judge: {p['judge']}")
        return

    # Load custom judge prompt if provided
    global JUDGE_PROMPT
    if args.judge_prompt_file:
        with open(args.judge_prompt_file) as f:
            JUDGE_PROMPT = f.read()

    # Determine panel models
    if args.preset:
        preset = load_preset(args.preset)
        panel_models = preset["panel"]
        judge_model = args.judge or preset["judge"]
    else:
        panel_str = args.panel or DEFAULT_PANEL
        panel_models = [m.strip() for m in panel_str.split(",") if m.strip()]
        judge_model = args.judge or DEFAULT_JUDGE

    if not panel_models:
        sys.exit("Error: no panel models specified. Use --panel, --preset, or set PANEL_DEFAULT_PANEL.")

    # Get query
    if args.stdin:
        query = sys.stdin.read().strip()
    elif args.query:
        query = args.query
    else:
        sys.exit("Error: provide a query as an argument or use --stdin.")

    # ─── Run Panel ────────────────────────────────────────────────────────────
    t0 = time.time()
    print_err(f"Panel: {', '.join(panel_models)}")
    print_err(f"Judge: {judge_model}")
    print_err(f"Query: {query[:120]}{'...' if len(query) > 120 else ''}")
    print_err("")

    # Fan out
    print_err("→ Fanning out to panel...")
    t1 = time.time()
    panel_results = fan_out(panel_models, query, system_prompt=args.system, max_tokens=args.max_tokens)
    t2 = time.time()
    succeeded = sum(1 for r in panel_results if not r["error"])
    print_err(f"  {succeeded}/{len(panel_results)} panelists responded in {t2-t1:.1f}s")
    for i, r in enumerate(panel_results):
        status = "✓" if not r["error"] else f"✗ {r['error'][:60]}"
        print_err(f"  Panelist {'ABCDEFGHIJ'[i]} ({r['requested_model']}): {status}")

    if succeeded == 0:
        sys.exit("Error: all panelists failed. Check OmniRoute proxy at " + BASE_URL)

    # Synthesize
    print_err("")
    print_err("→ Synthesizing with judge...")
    t3 = time.time()
    judge_result = synthesize(panel_results, query, judge_model, system_prompt=args.system)
    t4 = time.time()
    if judge_result["error"]:
        print_err(f"  ✗ Judge failed: {judge_result['error']}")
        # Fallback: just concatenate panel responses
        print_err("  Falling back to raw panel output (no synthesis)")
    else:
        print_err(f"  ✓ Judge responded in {t4-t3:.1f}s")
    total_time = time.time() - t0

    # ─── Output ───────────────────────────────────────────────────────────────
    if args.json:
        output = {
            "query": query,
            "panel": panel_models,
            "judge": judge_model,
            "panelist_responses": [
                {
                    "panelist": f"ABCDEFGHIJ"[i],
                    "model": r["requested_model"],
                    "actual_model": r["model"],
                    "content": r["content"],
                    "error": r["error"],
                }
                for i, r in enumerate(panel_results)
            ],
            "synthesis": judge_result.get("content", ""),
            "synthesis_error": judge_result.get("error"),
            "total_time_s": round(total_time, 1),
            "panel_time_s": round(t2 - t1, 1),
            "judge_time_s": round(t4 - t3, 1),
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        # Human-readable output
        if judge_result.get("content") and not judge_result.get("error"):
            print(judge_result["content"])
        else:
            # Fallback: show panel responses directly
            print("━━━ Panel Responses (judge failed) ━━━\n")
            for i, r in enumerate(panel_results):
                if r["content"]:
                    print(f"── Panelist {'ABCDEFGHIJ'[i]} ({r['model']}) ──")
                    print(r["content"])
                    print()

        print_err(f"\n⏱ Total: {total_time:.1f}s (panel: {t2-t1:.1f}s, judge: {t4-t3:.1f}s)")


def print_err(msg):
    """Print to stderr so stdout stays clean for JSON piping."""
    print(msg, file=sys.stderr)


if __name__ == "__main__":
    main()
