#!/usr/bin/env python3
"""OCR-vision benchmark spoke — canonical-25 corpus.

This is a benchmark-common spoke module. It contains only OCR-specific
cases, scoring logic, and image-passing mechanics.
Execution is driven by benchmark-common/scripts/run_benchmark.py OR
called standalone via __main__ below.

Usage (standalone):
    python3 ocr_cases.py --provider omniroute --model gemini-cli/gemini-2.5-flash
    python3 ocr_cases.py --provider openrouter --model google/gemini-2.5-flash-preview
    python3 ocr_cases.py --smoke --provider omniroute --model gemini-cli/gemini-2.5-flash
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

# ── Hub import ─────────────────────────────────────────────────────────────────
_COMMON = Path.home() / ".hermes" / "skills" / "benchmarks" / "benchmark-common" / "scripts"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

_HUB_AVAILABLE = False
_hub_PROVIDER_DEFAULTS: dict = {}


def _utc_now() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _make_run_id(benchmark_name: str, model: str) -> str:
    import datetime, hashlib
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    slug = hashlib.sha1(f"{benchmark_name}:{model}:{stamp}".encode()).hexdigest()[:8]
    return f"{benchmark_name}_{stamp}_{slug}"


try:
    from benchmark_common import (  # type: ignore  # noqa: E402
        CaseResult,
        Target,
        PROVIDER_DEFAULTS as _hub_PROVIDER_DEFAULTS,
        make_run_id as _make_run_id,  # type: ignore[assignment]
        utc_now as _utc_now,  # type: ignore[assignment]
        save_run,
        load_dotenv,
    )
    _HUB_AVAILABLE = True
except ImportError:
    pass  # standalone mode — stubs above are used

# ── Constants ──────────────────────────────────────────────────────────────────

BENCHMARK_NAME = "ocr-benchmark"
SUITE_VERSION = "canonical-25-v0.2"
PASS_THRESHOLD = 0.60  # ≥60/100 weighted points

SKILL_ROOT = Path(__file__).parent.parent
PAGES_DIR = SKILL_ROOT / "resources" / "pages"
MANIFEST = PAGES_DIR / "manifest.json"

VISION_PROMPT = """\
Extract ALL content from this document page as clean markdown.

Rules:
- Preserve ALL tables using markdown table format (| and --- separators)
- Preserve chart titles, axis labels, legends exactly
- Extract ALL numeric data values with units
- Do NOT summarize or paraphrase — extract verbatim
- Output ONLY markdown, no fences, no commentary"""

# ── Scoring patterns ───────────────────────────────────────────────────────────

_TABLE_ROW = re.compile(r"\|.+\|", re.MULTILINE)
_TABLE_SEP = re.compile(r"\|?\s*[-]{3,}\s*\|", re.MULTILINE)
_CHART_TITLE = re.compile(r"^(chart|figure|graph)\s*\d*[:.?]?", re.IGNORECASE | re.MULTILINE)
_AXIS_LABEL = re.compile(r"(x[-\s]?axis|y[-\s]?axis|source:|note:)", re.IGNORECASE)
_NUMERIC_UNIT = re.compile(r"\b\d[\d,.]*\s*([a-zA-Z%$€£¥°]+)\b")

# Known polite-refusal / no-image-detected responses — score 0 regardless of length
BAD_FALLBACKS = [
    "I don't see any document attached",
    "I don't see an image",
    "no image",
    "no document",
    "I cannot see",
    "I'm unable to view",
    "please attach",
    "please provide",
    "no attachment",
    "I don't have access to the image",
    "As an AI, I don't have the ability",
]


def score_page(md: str, category: str = "mixed") -> Tuple[float, Dict[str, Any]]:
    """Return (0.0-1.0, detail_dict) for a page extraction response."""
    t = md.strip()

    # Hard zero: polite refusal
    low = t.lower()
    for bad in BAD_FALLBACKS:
        if bad.lower() in low:
            return 0.0, {"invalid": True, "reason": bad[:60]}

    has_tbl = bool(_TABLE_ROW.search(t)) and bool(_TABLE_SEP.search(t))
    has_chart = bool(_CHART_TITLE.search(t)) or bool(_AXIS_LABEL.search(t))
    has_num = bool(_NUMERIC_UNIT.findall(t))
    has_content = len(t) > 100

    # Points by dimension
    pts = 0
    pts += 25 if has_tbl else 0
    pts += 20 if has_chart else 0
    pts += 20 if has_num else 0
    pts += 15 if has_content else 0
    # Category bonus: scanned text passes on content alone
    if category == "scanned_text" and has_content:
        pts += 20
    elif category in ("chart", "table") and (has_chart or has_tbl):
        pts += 20

    score = min(pts / 100, 1.0)
    return score, {
        "has_tables": has_tbl,
        "has_charts": has_chart,
        "has_numbers": has_num,
        "has_content": has_content,
        "length": len(t),
        "pts": pts,
    }


# ── Manifest loading ───────────────────────────────────────────────────────────

def load_manifest() -> List[Dict[str, Any]]:
    if not MANIFEST.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST}")
    data = json.loads(MANIFEST.read_text())
    return data["pages"]


# ── API call ───────────────────────────────────────────────────────────────────

def _encode_image(png_path: Path) -> str:
    return base64.b64encode(png_path.read_bytes()).decode()


def call_vision(
    client: Any,
    model: str,
    png_path: Path,
) -> Tuple[str, int, int, int, float]:
    """Call the vision endpoint. Returns (response_text, prompt_tok, completion_tok, total_tok, latency_ms)."""
    b64 = _encode_image(png_path)
    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ],
        max_tokens=4096,
        temperature=0,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    text = resp.choices[0].message.content or ""
    usage = resp.usage
    pt = getattr(usage, "prompt_tokens", 0) or 0
    ct = getattr(usage, "completion_tokens", 0) or 0
    total = getattr(usage, "total_tokens", pt + ct)
    return text, pt, ct, total, latency_ms


# ── Per-page case runner ───────────────────────────────────────────────────────

def run_cases(
    pages: List[Dict[str, Any]],
    client: Any,
    model: str,
    sleep_s: float = 0.5,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    results = []
    for i, page in enumerate(pages):
        png = PAGES_DIR / page["filename"]
        if not png.exists():
            if verbose:
                print(f"  [{i+1}/{len(pages)}] SKIP — PNG not found: {png.name}")
            results.append({
                "page_id": page["id"],
                "category": page.get("category", "unknown"),
                "passed": False,
                "score": 0.0,
                "error": "PNG not found",
                "latency_ms": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "content_length": 0,
            })
            continue

        try:
            text, pt, ct, total, latency_ms = call_vision(client, model, png)
            score, detail = score_page(text, page.get("category", "mixed"))
            passed = score >= PASS_THRESHOLD
            if verbose:
                status = "✓" if passed else "✗"
                refusal = " [REFUSAL]" if detail.get("invalid") else ""
                print(
                    f"  [{i+1}/{len(pages)}] {status} {page['id']} "
                    f"score={score:.2f} pts={detail.get('pts', '?')} "
                    f"len={detail['length']} lat={latency_ms}ms{refusal}"
                )
            results.append({
                "page_id": page["id"],
                "category": page.get("category", "unknown"),
                "passed": passed,
                "score": score,
                "detail": detail,
                "response_preview": text[:300],
                "latency_ms": latency_ms,
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "total_tokens": total,
                "content_length": len(text.strip()),
                "error": "",
            })
        except Exception as e:
            if verbose:
                print(f"  [{i+1}/{len(pages)}] ERROR {page['id']}: {e}")
            results.append({
                "page_id": page["id"],
                "category": page.get("category", "unknown"),
                "passed": False,
                "score": 0.0,
                "error": str(e)[:200],
                "latency_ms": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "content_length": 0,
            })

        if sleep_s > 0 and i < len(pages) - 1:
            time.sleep(sleep_s)

    return results


# ── Summary helpers ────────────────────────────────────────────────────────────

def summarize(results: List[Dict[str, Any]], model: str, provider: str) -> Dict[str, Any]:
    n = len(results)
    passed = sum(1 for r in results if r["passed"])
    avg_lat = sum(r["latency_ms"] for r in results) / max(n, 1)
    total_tok = sum(r["total_tokens"] for r in results)
    by_cat: Dict[str, Dict] = {}
    for r in results:
        cat = r["category"]
        entry = by_cat.setdefault(cat, {"total": 0, "passed": 0})
        entry["total"] += 1
        if r["passed"]:
            entry["passed"] += 1
    return {
        "model": model,
        "provider": provider,
        "suite": SUITE_VERSION,
        "total_pages": n,
        "passed": passed,
        "pass_rate": passed / max(n, 1),
        "avg_latency_ms": avg_lat,
        "total_tokens": total_tok,
        "by_category": by_cat,
        "timestamp": _utc_now(),
    }


# ── CLI ─────────────────────────────────────────────────────────────────────────

def _build_client(provider: str, model: str, base_url: str | None, api_key: str | None):
    try:
        from openai import OpenAI
    except ImportError:
        raise SystemExit("Install openai: pip install openai")

    if _HUB_AVAILABLE:
        load_dotenv()

    defaults = _hub_PROVIDER_DEFAULTS if _HUB_AVAILABLE else {
        "omniroute": ("${OMNIROUTE_URL}/v1", "OMNIROUTE_API_KEY"),
        "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
        "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
        "nous": ("https://inference-api.nousresearch.com/v1", "NOUS_API_KEY"),
    }

    if base_url is None:
        url_tmpl, key_var = defaults.get(provider, (None, None))
        if url_tmpl is None:
            raise SystemExit(f"Unknown provider '{provider}'. Use --base-url to set manually.")
        base_url = url_tmpl.replace("${OMNIROUTE_URL}", os.environ.get("OMNIROUTE_URL", "http://localhost:20128"))

    if api_key is None:
        _, key_var = defaults.get(provider, (None, "OPENAI_API_KEY"))
        api_key = os.environ.get(key_var or "", "")

    return OpenAI(base_url=base_url, api_key=api_key or "sk-placeholder")


def main() -> None:
    ap = argparse.ArgumentParser(description="OCR-vision benchmark (canonical-25)")
    ap.add_argument("--provider", default="omniroute", choices=["omniroute", "openrouter", "openai", "nous", "custom"])
    ap.add_argument("--model", required=False, default=None, help="Model ID on the provider")
    ap.add_argument("--model-list", help="Path to file with one provider:model per line (batch mode)")
    ap.add_argument("--base-url", default=None, help="Override API base URL")
    ap.add_argument("--api-key", default=None, help="Override API key")
    ap.add_argument("--sleep", type=float, default=0.5, help="Sleep between pages (use 3 for free Gemini)")
    ap.add_argument("--smoke", action="store_true", help="Run 1 page only (fast gate)")
    ap.add_argument("--output", default=None, help="Write JSON report to file")
    ap.add_argument("--output-dir", default=None, help="Directory for batch run reports")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    pages = load_manifest()
    if args.smoke:
        pages = pages[:1]

    if args.model_list:
        # Batch mode
        out_dir = Path(args.output_dir) if args.output_dir else Path("/tmp/ocr_bench")
        out_dir.mkdir(parents=True, exist_ok=True)
        for line in Path(args.model_list).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                prov, mdl = line.split(":", 1)
            else:
                prov, mdl = args.provider, line
            print(f"\n── {prov}:{mdl} ──")
            client = _build_client(prov, mdl, args.base_url, args.api_key)
            results = run_cases(pages, client, mdl, args.sleep, not args.quiet)
            summary = summarize(results, mdl, prov)
            fname = out_dir / f"ocr_bench_{prov}_{mdl.replace('/', '_')}.json"
            fname.write_text(json.dumps({"summary": summary, "results": results}, indent=2))
            print(f"  → {fname}  pass={summary['passed']}/{summary['total_pages']}")
        return

    if not args.model:
        ap.error("--model is required (or use --model-list for batch)")

    client = _build_client(args.provider, args.model, args.base_url, args.api_key)

    print(f"OCR Benchmark  suite={SUITE_VERSION}  model={args.model}  provider={args.provider}")
    print(f"Pages: {len(pages)}  sleep={args.sleep}s")
    print("─" * 60)

    results = run_cases(pages, client, args.model, args.sleep, not args.quiet)
    summary = summarize(results, args.model, args.provider)

    print("─" * 60)
    print(
        f"Result: {summary['passed']}/{summary['total_pages']} passed "
        f"({summary['pass_rate']:.0%})  "
        f"avg_lat={summary['avg_latency_ms']:.0f}ms  "
        f"total_tokens={summary['total_tokens']}"
    )
    for cat, s in summary["by_category"].items():
        print(f"  {cat}: {s['passed']}/{s['total']}")

    if args.output:
        out = Path(args.output)
        out.write_text(json.dumps({"summary": summary, "results": results}, indent=2))
        print(f"\nReport → {out}")
    else:
        print("\n(use --output to save JSON report)")

    if _HUB_AVAILABLE:
        run_id = _make_run_id(BENCHMARK_NAME, args.model)
        try:
            save_run(
                benchmark=BENCHMARK_NAME,
                run_id=run_id,
                summary=summary,
                results=results,
            )
            print(f"SQLite: run_id={run_id}")
        except Exception as e:
            print(f"[warn] SQLite save failed: {e}")

    # Exit non-zero on smoke test failure
    if args.smoke and summary["pass_rate"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
