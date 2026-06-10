#!/usr/bin/env python3
"""Generic benchmark runner for Hermes benchmark suites.

This is the unified execution harness that all benchmark subclass skills should
invoke. It handles:
  - CLI argument parsing (provider, model, timeout, retries, etc.)
  - Provider resolution (OmniRoute, OpenRouter, Groq, etc.)
  - API calling with retry logic
  - Run lifecycle (start_run -> record_case -> finish_run)
  - Cost tracking
  - Obsidian report rendering
  - Leaderboard generation

Subclass skills provide:
  - Test cases (fixtures/prompts/expected results)
  - A scoring function (response + case -> (passed, score, notes))
  - A system prompt (optional)
  - Benchmark name/version/suite metadata

Usage as a library:
  from run_benchmark import BenchmarkRunner, CaseDef
  runner = BenchmarkRunner(
      benchmark_name="my-benchmark",
      benchmark_version="1.0.0",
      suite_version="v1",
      cases=[CaseDef(id="c1", category="cat", prompt="...", expected="...")],
      scorer=my_score_fn,
      system_prompt="You are a helpful assistant.",
  )
  runner.run()

Usage as a CLI (loads cases/scorer from a Python module):
  python run_benchmark.py run \\
    --benchmark-name my-benchmark \\
    --benchmark-version 1.0.0 \\
    --suite-version v1 \\
    --cases-module benchmarks.my_benchmark.cases \\
    --provider omniroute \\
    --model google/gemma-4-26b-a4b-it
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time as _time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Import shared utilities from the sibling benchmark_common module
sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_common import (  # type: ignore
    CaseResult,
    Target,
    add_common_args,
    canonical_model_id,
    chat_completion,
    connect_db,
    extract_text_and_usage,
    fetch_openrouter_pricing,
    finish_run,
    load_dotenv,
    make_run_id,
    record_case,
    resolve_target,
    start_run,
    token_cost_from_pricing,
)

# ─── Data Classes ──────────────────────────────────────────────────────


@dataclass
class CaseDef:
    """A single benchmark test case definition.

    Subclass skills create a list of these to define their test battery.
    """

    id: str
    category: str
    prompt: str
    expected: str
    # Optional per-case overrides
    max_tokens: int = 0  # 0 = use runner default
    temperature: float = -1  # -1 = use runner default
    timeout: int = 0  # 0 = use runner default
    extra_api_params: Dict[str, Any] = field(default_factory=dict)


# Scoring function signature: (response_text, case) -> (passed, score, notes)
ScorerFn = Callable[[str, CaseDef], Tuple[bool, float, str]]


# ─── Benchmark Runner ──────────────────────────────────────────────────


class BenchmarkRunner:
    """Generic benchmark execution harness.

    Orchestrates the full lifecycle: resolve provider -> start run -> iterate
    cases -> call API -> score -> record -> finish run -> render reports.
    """

    def __init__(
        self,
        *,
        benchmark_name: str,
        benchmark_version: str = "1.0.0",
        suite_version: str = "v1",
        cases: List[CaseDef],
        scorer: ScorerFn,
        system_prompt: str = "",
        db_path: Optional[str] = None,
        obsidian_dir: Optional[str] = None,
        default_models: Optional[List[str]] = None,
        extra_pricing: Optional[Dict[str, Tuple]] = None,
    ):
        self.benchmark_name = benchmark_name
        self.benchmark_version = benchmark_version
        self.suite_version = suite_version
        self.cases = cases
        self.scorer = scorer
        self.system_prompt = system_prompt
        self.default_models = default_models or []
        self.extra_pricing = extra_pricing or {}
        self._pricing_cache: Optional[Dict[str, Tuple]] = None

        # Default paths: ~/.hermes/skills/benchmarks/<name>/results/
        skill_dir = Path.home() / ".hermes" / "skills" / "benchmarks" / benchmark_name
        self.db_path = Path(db_path) if db_path else skill_dir / "results" / "benchmark.db"
        self.obsidian_dir = Path(obsidian_dir) if obsidian_dir else None

    def run(
        self,
        provider: str = "omniroute",
        model: Optional[str] = None,
        models: Optional[List[str]] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        timeout: int = 60,
        max_retries: int = 2,
        preflight: bool = False,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        """Execute the benchmark. Returns a summary dict."""
        load_dotenv()
        target = resolve_target(provider, model or "unknown", base_url, api_key)
        if self._pricing_cache is None:
            self._pricing_cache = fetch_openrouter_pricing()
            print(f"pricing_cache=openrouter entries={len(self._pricing_cache)}", flush=True)
        con = connect_db(self.db_path)
        results_per_model: List[Dict[str, Any]] = []

        model_list = models or ([model] if model else self.default_models)
        if not model_list:
            raise ValueError("No model specified. Use --model or --models, or set default_models.")

        for m in model_list:
            target = resolve_target(provider, m, base_url, api_key)
            run_id = make_run_id(self.benchmark_name, canonical_model_id(m))

            # Build a minimal args namespace for start_run
            args = argparse.Namespace(
                provider=provider,
                model=m,
                base_url=target.base_url,
                api_key=target.api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                max_retries=max_retries,
                db=str(self.db_path),
                benchmark_version=self.benchmark_version,
                suite_version=self.suite_version,
                notes="",
            )
            start_run(con, run_id, self.benchmark_name, args, target)

            status, error = "completed", ""
            try:
                for case in self.cases:
                    result = self._run_case(
                        con, run_id, target, case,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout=timeout,
                        max_retries=max_retries,
                        json_mode=json_mode,
                    )
                finish_run(con, run_id, status)
            except Exception as exc:
                status, error = "failed", str(exc)
                finish_run(con, run_id, status, error)
                raise

            row = con.execute(
                "SELECT score, passed_cases, total_cases, avg_latency_ms, total_tokens, cost_usd "
                "FROM benchmark_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            summary = {
                "run_id": run_id,
                "model": m,
                "score": row["score"] if row else 0,
                "passed": row["passed_cases"] if row else 0,
                "total": row["total_cases"] if row else 0,
                "avg_latency_ms": row["avg_latency_ms"] if row else 0,
                "tokens": row["total_tokens"] if row else 0,
                "cost_usd": row["cost_usd"] if row else 0,
            }
            print(
                f"{run_id} score={summary['score']:.3f} "
                f"pass={summary['passed']}/{summary['total']} "
                f"avg_ms={summary['avg_latency_ms']:.0f} "
                f"tokens={summary['tokens']} cost=${summary['cost_usd']:.6f}"
            )
            results_per_model.append(summary)

        return {
            "benchmark": self.benchmark_name,
            "models_run": len(results_per_model),
            "results": results_per_model,
        }

    def _run_case(
        self,
        con,
        run_id: str,
        target: Target,
        case: CaseDef,
        *,
        temperature: float,
        max_tokens: int,
        timeout: int,
        max_retries: int,
        json_mode: bool,
    ) -> CaseResult:
        """Run a single benchmark case with retry logic."""
        case_temp = case.temperature if case.temperature >= 0 else temperature
        case_tokens = case.max_tokens or max_tokens
        case_timeout = case.timeout or timeout

        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": case.prompt})

        extra = dict(case.extra_api_params)
        if json_mode:
            extra["response_format"] = {"type": "json_object"}

        last_error = ""
        for attempt in range(1 + max_retries):
            try:
                text, usage, latency_ms = chat_completion(
                    target,
                    messages,
                    temperature=case_temp,
                    max_tokens=case_tokens,
                    timeout=case_timeout,
                    extra=extra or None,
                )
                passed, score, notes = self.scorer(text.strip(), case)

                # Cost estimation — use token_cost_from_pricing with fallback table
                cost_usd = 0.0
                cost_estimated = True
                try:
                    from benchmark_common import token_cost_from_pricing  # type: ignore
                    cost_usd, _ = token_cost_from_pricing(
                        target.model,
                        usage,
                        self.extra_pricing,
                        self._pricing_cache,
                    )
                except Exception:
                    pass

                result = CaseResult(
                    case_id=case.id,
                    category=case.category,
                    prompt=case.prompt,
                    expected=case.expected,
                    response=text.strip(),
                    passed=passed,
                    score=score,
                    latency_ms=latency_ms,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    cost_usd=cost_usd,
                    cost_estimated=cost_estimated,
                    notes=notes,
                )
                record_case(con, run_id, result)
                return result

            except Exception as exc:
                last_error = str(exc)
                if attempt < max_retries:
                    wait = 2 ** attempt
                    print(f"    retry {attempt+1}/{max_retries} after {wait}s: {exc}", flush=True)
                    _time.sleep(wait)

        # All retries exhausted
        result = CaseResult(
            case_id=case.id,
            category=case.category,
            prompt=case.prompt,
            expected=case.expected,
            response="",
            passed=False,
            score=0.0,
            latency_ms=0,
            error=last_error,
        )
        record_case(con, run_id, result)
        return result


# ─── Obsidian Report Rendering ─────────────────────────────────────────


def render_obsidian_report(db_path: str, obsidian_dir: str, benchmark_name: str) -> str:
    """Render a markdown summary from the benchmark DB to an Obsidian vault.

    Returns the rendered markdown string.
    """
    from benchmark_common import connect_db  # type: ignore

    con = connect_db(db_path)
    rows = con.execute(
        "SELECT run_id, provider, model, status, score, passed_cases, total_cases, "
        "avg_latency_ms, total_tokens, cost_usd, started_at "
        "FROM benchmark_runs "
        "ORDER BY started_at DESC LIMIT 50"
    ).fetchall()

    lines = [
        f"# {benchmark_name} Results",
        "",
        f"> Auto-generated from `{db_path}`",
        "",
        "| Run | Model | Score | Pass | Avg ms | Tokens | Cost |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['run_id'][:20]} | {r['model']} | {r['score']:.3f} "
            f"| {r['passed_cases']}/{r['total_cases']} "
            f"| {r['avg_latency_ms']:.0f} | {r['total_tokens']} "
            f"| ${r['cost_usd']:.6f} |"
        )

    lines.append("")
    md = "\n".join(lines)

    if obsidian_dir:
        out = Path(obsidian_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{benchmark_name}-results.md").write_text(md)

    return md


# ─── Leaderboard ────────────────────────────────────────────────────────


def render_leaderboard(db_path: str, benchmark_name: str, top_n: int = 20) -> str:
    """Render a leaderboard of best scores per model."""
    from benchmark_common import connect_db  # type: ignore

    con = connect_db(db_path)
    rows = con.execute(
        "SELECT model, MAX(score) as best_score, "
        "ROUND(AVG(avg_latency_ms), 0) as avg_ms, "
        "ROUND(SUM(cost_usd), 6) as total_cost, "
        "COUNT(*) as runs "
        "FROM benchmark_runs WHERE status='completed' "
        "GROUP BY model ORDER BY best_score DESC LIMIT ?",
        (top_n,),
    ).fetchall()

    lines = [
        f"# {benchmark_name} Leaderboard",
        "",
        "| # | Model | Best Score | Avg ms | Total Cost | Runs |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for i, r in enumerate(rows, 1):
        lines.append(
            f"| {i} | {r['model']} | {r['best_score']:.3f} "
            f"| {r['avg_ms']:.0f} | ${r['total_cost']:.6f} | {r['runs']} |"
        )
    lines.append("")
    return "\n".join(lines)


# ─── Dynamic Module Loading ────────────────────────────────────────────


def load_cases_from_module(module_path: str) -> List[CaseDef]:
    """Load a list of CaseDef objects from a Python module.

    The module must expose a ``CASES`` variable (list of CaseDef).
    """
    mod = importlib.import_module(module_path)
    cases = getattr(mod, "CASES", None)
    if cases is None:
        raise ValueError(f"Module {module_path} has no CASES attribute")
    return list(cases)


def load_scorer_from_module(module_path: str) -> ScorerFn:
    """Load a scoring function from a Python module.

    The module must expose a ``score`` function with signature:
        score(response: str, case: CaseDef) -> tuple[bool, float, str]
    """
    mod = importlib.import_module(module_path)
    scorer = getattr(mod, "score", None)
    if scorer is None:
        raise ValueError(f"Module {module_path} has no score function")
    return scorer


# ─── CLI Entry Point ────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generic Hermes benchmark runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = p.add_subparsers(dest="command")

    # ── run subcommand ──
    run_p = sub.add_parser("run", help="Run a benchmark suite")
    run_p.add_argument("--benchmark-name", required=True, help="Benchmark suite name (e.g. clerk-benchmark)")
    run_p.add_argument("--cases-module", help="Python module path to load cases from")
    run_p.add_argument("--scorer-module", help="Python module path to load scorer from (same as cases-module if omitted)")
    run_p.add_argument("--system-prompt", default="", help="System prompt to prepend to all cases")

    # Common args from benchmark_common (provider, model, db, temperature, etc.)
    add_common_args(run_p)
    # Override some defaults for the generic runner
    run_p.set_defaults(max_retries=2, model=None)
    run_p.add_argument("--models", nargs="+", help="Run multiple models sequentially")
    run_p.add_argument("--preflight", action="store_true", help="Ping model before benchmark")
    run_p.add_argument("--json-mode", action="store_true", help="Request JSON response_format")
    run_p.set_defaults(func=_cmd_run)

    # ── report subcommand ──
    rpt_p = sub.add_parser("report", help="Render Obsidian report from DB")
    rpt_p.add_argument("--benchmark-name", required=True)
    rpt_p.add_argument("--db", required=True, help="Path to benchmark SQLite DB")
    rpt_p.add_argument("--obsidian-dir", help="Obsidian vault dir for report output")
    rpt_p.set_defaults(func=_cmd_report)

    # ── leaderboard subcommand ──
    lb_p = sub.add_parser("leaderboard", help="Render leaderboard from DB")
    lb_p.add_argument("--benchmark-name", required=True)
    lb_p.add_argument("--db", required=True, help="Path to benchmark SQLite DB")
    lb_p.set_defaults(func=_cmd_leaderboard)

    return p


def _cmd_run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    cases_module = args.cases_module
    scorer_module = args.scorer_module or cases_module

    if not cases_module:
        parser.error("--cases-module is required for CLI mode. Use the Python API for inline cases.")

    cases = load_cases_from_module(cases_module)
    scorer = load_scorer_from_module(scorer_module)

    runner = BenchmarkRunner(
        benchmark_name=args.benchmark_name,
        benchmark_version=args.benchmark_version,
        suite_version=args.suite_version,
        cases=cases,
        scorer=scorer,
        system_prompt=args.system_prompt,
        db_path=args.db,
        obsidian_dir=args.obsidian_dir,
    )
    result = runner.run(
        provider=args.provider,
        model=args.model,
        models=args.models,
        base_url=args.base_url,
        api_key=args.api_key,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
        max_retries=args.max_retries,
        preflight=args.preflight,
        json_mode=args.json_mode,
    )
    print(json.dumps(result, indent=2))


def _cmd_report(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    md = render_obsidian_report(args.db, args.obsidian_dir, args.benchmark_name)
    print(md)


def _cmd_leaderboard(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    md = render_leaderboard(args.db, args.benchmark_name)
    print(md)


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    raw = list(argv if argv is not None else sys.argv[1:])
    if not raw or raw[0].startswith("-"):
        raw = ["run"] + raw
    args = parser.parse_args(raw)
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)
    # Subcommand functions get (args, parser) for error reporting
    args.func(args, parser)


if __name__ == "__main__":
    main()
