#!/usr/bin/env python3
"""Hindsight Model Benchmark — rate limit risk for retain_extract_facts.

Tests whether candidate models can handle Hindsight's ~67K-token retain context:
  H1: Context size acceptance (67K input tokens)
  H2: Structured JSON extraction quality
  H3: Rate-limit stress (burst N requests)

Uses benchmark_common.py shared utilities (DB, API, pricing).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

COMMON = Path(__file__).resolve().parents[1].parent / 'model-benchmark' / 'scripts'
sys.path.insert(0, str(COMMON))
from benchmark_common import (
    Target,
    add_common_args,
    canonical_model_id,
    chat_completion,
    classify_error,
    connect_db,
    estimate_cost_usd,
    extract_text_and_usage,
    finish_run,
    load_dotenv,
    make_run_id,
    record_case,
    resolve_target,
    start_run,
    strip_json_fences,
    token_cost_from_pricing,
    utc_now,
)

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "results" / "hindsight-benchmark.db"
RESULTS_DIR = ROOT / "results" / "runs"
OBSIDIAN_RESULTS_PATH = Path.home() / "Obsidian" / "Main Vault" / "40-Operations" / "Hermes" / "Benchmarks" / "hindsight-model-benchmark" / "hindsight-model-results.md"

SCENARIOS = ("H1_context_acceptance", "H2_json_extraction")
SCENARIO_WEIGHTS = {
    "H1_context_acceptance": 0.30,
    "H2_json_extraction": 0.50,
    "H3_rate_limit": 0.20,
}

# ─── Synthetic Hindsight Payload Generator ─────────────────────────────

_CONVERSATION_TEMPLATE = """[user] Hey, can you check if the Groq API for gpt-oss-20b has changed its rate limits? I'm getting 413 errors.
[assistant] Let me look into the Groq API documentation and your recent logs. I can see from the Docker container logs that your Hindsight retain requests are hitting HTTP 413 "Request too large" with the message about TPM being exceeded. The Groq free on-demand tier has an 8,000 tokens per minute limit.
[user] That explains it. Our context is around 67k tokens. Can we switch to a different provider?
[assistant] Yes, we can point Hindsight's LLM at an OmniRoute combo instead. The container uses HINDSIGHT_API_LLM_BASE_URL and HINDSIGHT_API_LLM_MODEL environment variables.
[tool_call: terminal] docker inspect hindsight --format='{{json .Config.Env}}'
[tool_output] ["HINDSIGHT_API_LLM_BASE_URL=https://api.groq.com/openai/v1", "HINDSIGHT_API_LLM_MODEL=openai/gpt-oss-20b", ...]
[user] What models support 67K context on free tiers?
[assistant] Several OpenRouter free models support large contexts:
- google/gemini-3-flash-preview:free (1M ctx)
- openai/gpt-oss-120b:free (8K ctx on Groq but might work via OpenRouter)
- meta-llama/llama-3.1-8b-instruct:free (128K ctx)
- qwen/qwen2.5-72b-instruct:free (32K ctx — may be too small)
[tool_call: web_search] "largest context window free llm models 2026"
[tool_output: web] Several options including Gemini 1.5 Flash (1M), Claude Haiku (200K), and Qwen 3.5 (131K).
[user] Let's also check the Neo4j supply chain backfill status.
[assistant] The Neo4j backfill has processed 847 companies out of 1,203 planned. The current bottleneck is the enrichment-pipeline-stall-detection where concurrent API calls are causing write-lock contention.
[tool_call: terminal] curl -s https://boreas.cow-hippocampus.ts.net:7473/db/neo4j/tx/commit -X POST -H 'Content-Type: application/json' -d '{"statements": [{"statement": "MATCH (c:Company) RETURN count(c) as total, count(c.website) as with_website"}]}'
[tool_output] {"total": 847, "with_website": 312}
[user] The covered-call scanner showed IV percentile above 80 for some defense stocks.
[assistant] Scanning the covered-call dashboard, here are the high-IV candidates:
- LMT (Lockheed Martin): IV 78th percentile, avg call premium $4.20/share
- RTX (RTX Corp): IV 82nd percentile, avg call premium $3.15/share
- GD (General Dynamics): IV 71st percentile, avg call premium $5.80/share
[tool_call: terminal] hermes cron list
[tool_output] ID                              Schedule       Status  Name
nightly-intake                  0 03 * * *     active  Nightly intake curator
supply-chain-backfill           */30 * * * *  active  Supply chain backfill
covered-call-scan               0 9 * * 1     active  Weekly covered call scan
model-benchmark                 0 2 * * 0     active  Weekly benchmark run
[user] The PageIndex enrichment backlog for the defense domain has 23 unprocessed PDFs.
[assistant] Checking the backlog folder... I see 23 PDFs in __Inbound/ under Domains/Defense/. The oldest is from March 12. The enrichment pipeline processes ~5 PDFs/hour with the current qwen3:72b setup. At that rate, backlog will clear in ~5 hours.
[tool_call: read_file] path=~/Books/PageIndex/Domains/Defense/__Inbound/
[tool_output] 23 files: 05-drone-propulsion-trends.pdf, 06-munitions-supply-chain-report.pdf, ...
[user] What's the status of the research-recon topic on semiconductor foundry expansion?
[assistant] The research corpus has 4 relevant documents. Key findings: TSMC Arizona Phase 2 is on track for Q3 2027 production. Samsung Austin expansion delayed to 2028. Intel Ohio fabs still seeking CHIPS Act disbursement. This aligns with the Neo4j supply chain graph where we have 47 "foundry" nodes.
[tool_call: terminal] python3 ~/Projects/supply-chain-kg/query.py --query "MATCH (f:Company {type:'foundry'}) RETURN f.name, f.capacity_wafers_per_month ORDER BY f.capacity_wafers_per_month DESC"
[tool_output] TSMC Fab 18: 75000
Samsung Austin: 45000
Intel Fab 11: 35000
UMC Fab 12A: 28000
[user] Can you draft a briefing using the macro peer impact analysis format?
[assistant] Drafting brief based on catalyst-second-order-identification methodology. The key second-order plays from TSMC capacity expansion:
1. Semiconductor equipment suppliers (ASML, Applied Materials, Lam Research)
2. Specialty gas and chemical distributors
3. Wafer substrate manufacturers
4. Advanced packaging test equipment
[tool_call: write_file] path=~/Obsidian/Main Vault/Domains/Defense/Briefings/2026-05-13-tsmc-impact-brief.md
[tool_output] File written: 2.3KB
[user] The kanban system shows 5 blocked tasks in the supply-chain domain.
[assistant] Checking the kanban board at http://ambler.cow-hippocampus.ts.net:9119/kanban...
Blocked tasks:
1. task-2026-05-10-xyz123-mapping-tier3-suppliers — needs peer output from researcher-A
2. task-2026-05-11-abc456-enrichment-batch-failed — API key expired
3. task-2026-05-12-def789-citation-validation — needs human review
4. task-2026-05-12-ghi012-power-grid-mapping — blocked on external dataset access
5. task-2026-05-12-jkl345-contract-scraper — rate-limited by SAM.gov
[tool_call: kanban_list] assignee=supply-chain-a
[tool_output: json] [{"id": "...", "status": "blocked", "title": "Mapping Tier 3 Suppliers"}, ...]
[user] Run the OCR benchmark against the canonical-25 corpus with glm-4.6v.
[assistant] Starting OCR benchmark with glm/glm-4.6v via OmniRoute. Processing 25 pages with table/chart/numeric data extraction. ETA: ~5 minutes.
[tool_call: terminal] python3 ~/.hermes/skills/benchmarks/ocr-benchmark/scripts/run_ocr_benchmark.py run --provider omniroute --model glm/glm-4.6v
[tool_output processing...]
[user] What are tonight's covered-call opportunities after the earnings calendar update?
[assistant] Earnings this week: QCOM (Mon), NVDA (Wed), CRM (Thu). Pre-earnings covered calls are high-risk but premiums are elevated. QCOM IV is at 65th percentile with $2.80 avg premium. NVDA IV is at 90th percentile — but post-earnings gamma risk is significant. The schwab-trading skill's covered-call scanner shows 12 candidates with IV > 75%.

"""

# Additional filler to bulk up to ~67K tokens
_TOOL_HEAVY_SECTION = """[system] You are Hermes, an autonomous AI agent running on macOS. You have access to terminal, file operations, web search, Neo4j graph queries, Obsidian vault management, and various MCP servers.
[tool_call: Neo4j HTTP] MATCH (c:Company)-[:SUPPLIES]->(p:Product) WHERE p.category = 'GPU' RETURN c.name, c.website, count(p) as products ORDER BY products DESC LIMIT 10
[tool_output] [{"c.name": "TSMC", "c.website": "tsmc.com", "products": 12}, {"c.name": "Samsung Electronics", "c.website": "samsung.com", "products": 8}]
[tool_call: terminal] git -C ~/Projects/supply-chain-kg status --short
[tool_output] M scripts/query.py
 M data/neuralink-suppliers.json
?? data/new-foundries.json
[tool_call: web_search] "semiconductor supply chain bottlenecks 2026 ASML"
[tool_output: web]
1. ASML EUV lithography monopoly — sole source for cutting-edge
2. Japanese photoresist supply — JSR, Shin-Etsu control 80%
3. Specialty gases — Taiyo Nippon Sanso monopoly on etching gases
4. Packaging substrate — Ibiden, Shinko hold 65% market
5. Wafer dicing equipment — Disco Corporation near-monopoly
[tool_call: obsidian-rest] POST /v1/documents/Domains/Semiconductors/supply-chain-analysis
[tool_output: 201] Document created, 15 backlinks
[tool_call: terminal] python3 ~/Projects/neo4j-backfill/batch_enrich.py --domain semiconductors --batch-size 50
[tool_output] Batch 1/23: processed 50 companies, 34 enriched, 16 timeout
Batch 2/23: processed 50 companies, 28 enriched, 22 rate-limited
...
Completed: 847/1203 companies enriched. Estimated remaining: 5h 23m.
[tool_call: terminal] hermes skills list | grep -i supply
[tool_output] supply-chain-kg-reader, supply-chain-knowledge-graph, supply-chain-tier2-expansion
[tool_call: terminal] sqlite3 ~/ledger_api_server/ledger.db "SELECT ticker, entry_date, quantity, price_usd FROM trades WHERE entry_date > '2026-04-01' ORDER BY entry_date DESC LIMIT 10"
[tool_output] AAPL|2026-05-10|100|223.45
NVDA|2026-05-08|50|1089.50
MSFT|2026-05-07|75|467.20
GOOG|2026-05-06|40|192.30
AMZN|2026-05-05|60|245.78
[tool_call: web_search] "Q1 2026 data center GPU shipments Dell'Oro"
[tool_output: web] Dell'Oro Group reports Q1 2026 data center GPU shipments reached 2.1M units, up 145% YoY. Nvidia H200/H100 at 78% share, AMD MI300X at 18%, custom ASICs at 4%. Total data center capex for AI infrastructure: $89B annualized run rate.
[tool_call: terminal] docker ps --filter 'name=hindsight' | grep -v STATUS
[tool_output] CONTAINER   IMAGE                        COMMAND                   CREATED    STATUS      PORTS                    NAMES
hindsight   ghcr.io/vectorize-io/hindsight  /app/start-all.sh        5 days ago Up 20 hours 8888->8888, 9999->9999  hindsight
postgres    pgvector/pgvector:pg16         docker-entrypoint.s...   5 days ago Up 20 hours 5432/tcp                  hindsight-postgres
[tool_call: terminal] curl -s ${HINDSIGHT_URL}/health
[tool_output] {"status":"healthy","database":"connected"}
[tool_call: Neo4j HTTP] MATCH path=(c:Company)-[:SUPPLIES*1..3]->(end:Company) WHERE end.name = 'NVIDIA' RETURN c.name, length(path) as depth LIMIT 20
[tool_output] [{"c.name": "TSMC", "depth": 1}, {"c.name": "Samsung", "depth": 1}, {"c.name": "SK Hynix", "depth": 1}, {"c.name": "Micron", "depth": 1}, {"c.name": "Taiwan Semiconductor Materials", "depth": 2}, {"c.name": "Shin-Etsu Chemical", "depth": 2}]
[tool_call: terminal] python3 ~/Projects/consumer-sentinel/fetch.py --sources reddit,twitter,forums --keywords 'battery','fire','recall' --last-24h
[tool_output] 847 mentions found. Top clusters:
1. EV battery thermal events (142 mentions) — rising trend
2. Smart home device fire alerts (89 mentions) — stable
3. Laptop battery recalls (67 mentions) — spike detected
[tool_call: obsidian-rest] POST /v1/search?query=supply+chain+semiconductor
[tool_output: 200] 23 matching documents: Domains/Semiconductors/..., Domains/AI-Infrastructure/...
[tool_call: terminal] hermes cron run hindsight-retain
[tool_output] Running job hindsight-retain...
ERROR: Tool hindsight_retain returned error (120.16s): {"error": "Failed to store memory: "}
Job failed after 120s.

"""


def _generate_hindsight_payload(target_tokens: int = 67000) -> str:
    """Generate synthetic conversation text approximating target_tokens.

    Rough estimation: ~4 chars per token for English text.
    We repeat and vary the templates until we reach the target.
    """
    chars_per_token = 4
    target_chars = target_tokens * chars_per_token

    payload = _CONVERSATION_TEMPLATE + "\n"

    # If already close, stop
    if len(payload) >= target_chars:
        return payload[:target_chars]

    # Pad with tool-heavy sections (denser, more token-realistic)
    i = 0
    while len(payload) < target_chars:
        section = _TOOL_HEAVY_SECTION.replace("[tool_output", f"[tool_output (iteration-{i})")
        section = section.replace("[user]", f"[user] (continuation-{i})")
        payload += "\n" + section
        i += 1

    return payload[:target_chars]


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: chars / 4 for English-mixed content."""
    return max(len(text) // 4, 1)


# ─── Test Cases ────────────────────────────────────────────────────────

def build_h1_messages(target: Target, target_tokens: int = 67000) -> tuple[list[dict], int]:
    """H1: Context size acceptance — just get the model to respond to a huge input."""
    payload = _generate_hindsight_payload(target_tokens)
    token_est = _estimate_tokens(payload)
    return [
        {"role": "system", "content": "You are a memory retention assistant. You receive conversation transcripts and extract key facts. Respond with just 'ACK' to confirm you received the context."},
        {"role": "user", "content": payload + "\n\n---END OF CONTEXT---\n\nReply with just: ACK"},
    ], token_est


def build_h2_messages(target: Target, target_tokens: int = 67000) -> tuple[list[dict], int]:
    """H2: Structured JSON extraction — ask for fact extraction from large context."""
    payload = _generate_hindsight_payload(target_tokens)
    token_est = _estimate_tokens(payload)
    return [
        {"role": "system", "content": """You are a memory retention assistant. Extract structured facts from the conversation transcript below. Output ONLY valid JSON matching this schema:
{
  "facts": [
    {"type": "preference"|"decision"|"environment"|"tool_quirk"|"correction", "content": "the fact", "confidence": 0.0-1.0}
  ],
  "total_facts": 0,
  "extraction_notes": "brief summary of what was extracted"
}
Extract at least 10 facts. Be specific and actionable."""},
        {"role": "user", "content": payload + "\n\n---END OF CONTEXT---\n\nExtract facts as JSON."},
    ], token_est


# ─── Scoring ───────────────────────────────────────────────────────────

def score_h1(response: str, error: str = "") -> tuple[float, dict]:
    """H1 scoring: did it accept the context and respond?"""
    info = {}
    if error:
        info["error"] = error
        info["error_category"] = classify_error(error)
        if "413" in error or "too large" in error.lower():
            return 0.0, info
        if classify_error(error) in ("rate_limited", "timeout"):
            return 0.5, info  # Partial — model works but rate limited
        return 0.0, info

    if response and len(response.strip()) > 0:
        return 1.0, {"response_length": len(response), "contains_ack": "ack" in response.lower()[:50]}
    return 0.0, {"response_empty": True}


def score_h2(response: str, error: str = "") -> tuple[float, dict]:
    """H2 scoring: JSON validity + extraction quality."""
    info = {}
    if error:
        info["error"] = error
        info["error_category"] = classify_error(error)
        if "413" in error or "too large" in error.lower():
            return 0.0, info
        if classify_error(error) in ("rate_limited", "timeout"):
            return 0.3, info
        return 0.0, info

    # Try to parse JSON
    clean = strip_json_fences(response.strip())
    parsed = None
    parse_ok = False
    try:
        parsed = json.loads(clean)
        parse_ok = True
        info["json_valid"] = True
    except json.JSONDecodeError:
        # Try loose extraction
        match = re.search(r"\{.*\}", clean, flags=re.S)
        if match:
            try:
                parsed = json.loads(match.group(0))
                parse_ok = True
                info["json_valid"] = True
                info["json_fallback"] = True
            except json.JSONDecodeError:
                pass
        if not parse_ok:
            info["json_valid"] = False
            info["json_error"] = True
            return 0.0, info

    # Score extraction quality
    facts = parsed.get("facts", []) if isinstance(parsed, dict) else []
    fact_count = len(facts) if isinstance(facts, list) else 0
    info["fact_count"] = fact_count
    info["has_facts_key"] = "facts" in parsed if isinstance(parsed, dict) else False
    info["has_total_key"] = "total_facts" in parsed if isinstance(parsed, dict) else False

    # Quality: 50% for valid JSON, 25% for having facts, 25% for fact_count >= 10
    score = 0.5  # We got valid JSON
    if fact_count > 0:
        score += 0.25
    if fact_count >= 5:
        score += 0.15
    if fact_count >= 10:
        score += 0.10

    # Penalize nonsense
    if not any(f.get("content") for f in facts[:3]) if fact_count > 0 else True:
        score *= 0.5

    return min(score, 1.0), info


# ─── Database ──────────────────────────────────────────────────────────

def init_hindsight_db(path: Path) -> sqlite3.Connection:
    """Create hindsight-specific schema on top of common benchmark tables."""
    con = connect_db(path)
    con.execute('''CREATE TABLE IF NOT EXISTS hindsight_ratelimit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        request_num INTEGER NOT NULL,
        status TEXT NOT NULL,
        latency_ms INTEGER DEFAULT 0,
        error TEXT DEFAULT '',
        error_category TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES benchmark_runs(run_id)
    )''')
    return con


# ─── Main Runner ───────────────────────────────────────────────────────

def run_single_model(
    target: Target,
    target_tokens: int = 67000,
    db_path: Path = DB_PATH,
    timeout: int = 300,
    max_retries: int = 2,
    max_output_tokens: int = 512,
) -> dict:
    """Run H1 and H2 against a single model/target."""
    load_dotenv()
    con = init_hindsight_db(db_path)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    run_id = make_run_id("hindsight", target.model)
    args = argparse.Namespace(
        benchmark_version="0.1.0",
        suite_version="v1",
        notes=f"Hindsight retain benchmark — target_tokens={target_tokens}",
    )

    provider_str = target.provider
    target_obj = target  # already resolved
    start_run(con, run_id, "hindsight-model-benchmark", args, target_obj)

    run_summary = {
        "run_id": run_id,
        "provider": provider_str,
        "model": target.model,
        "base_url": target.base_url,
        "target_tokens": target_tokens,
        "results": {},
        "statuses": {},
        "errors": {},
        "rate_limit": None,
    }

    # H1: Context Size Acceptance
    print(f"\n{'='*60}")
    print(f"  H1: Context Size Acceptance (target: ~{target_tokens} tokens)")
    print(f"  Model: {target.provider}/{target.model}")
    print(f"  URL: {target.base_url}")
    print(f"{'='*60}")

    messages_h1, est_tokens = build_h1_messages(target, target_tokens)
    case_id = "H1_context_acceptance"

    response_h1, usage_h1, latency_h1 = _call_with_retry(
        target, messages_h1, timeout=timeout, max_retries=max_retries,
        max_tokens=16,
    )

    error_h1 = usage_h1.get("error", "")
    score_val_h1, info_h1 = score_h1(response_h1, error_h1)
    actual_model = usage_h1.get("actual_model", target.model)

    cost_info = _compute_cost(target.model, usage_h1)
    cost_usd = cost_info["cost_usd"]

    con.execute("""UPDATE benchmark_cases SET score = ?, passed = ?
        WHERE run_id = ? AND case_id = ?""", (score_val_h1, int(score_val_h1 >= 0.9), run_id, case_id))

    run_summary["results"]["H1"] = {
        "score": score_val_h1,
        "response_length": len(response_h1) if response_h1 else 0,
        "latency_ms": latency_h1,
        "estimated_input_tokens": est_tokens,
        "actual_model": actual_model,
        "cost_usd": cost_usd,
    }
    if error_h1:
        run_summary["errors"]["H1"] = error_h1

    print(f"  H1 score: {score_val_h1:.2f}/1.00  |  Latency: {latency_h1}ms  |  Tokens: {usage_h1.get('prompt_tokens', est_tokens)} in / {usage_h1.get('completion_tokens', 0)} out  |  Cost: ${cost_usd:.6f}")
    if error_h1:
        print(f"  H1 ERROR: {error_h1[:200]}")

    # H2: JSON Extraction Quality
    print(f"\n{'='*60}")
    print(f"  H2: Structured JSON Extraction")
    print(f"{'='*60}")

    messages_h2, _ = build_h2_messages(target, target_tokens)
    case_id = "H2_json_extraction"

    response_h2, usage_h2, latency_h2 = _call_with_retry(
        target, messages_h2, timeout=timeout, max_retries=max_retries,
        max_tokens=1024,
    )

    error_h2 = usage_h2.get("error", "")
    score_val_h2, info_h2 = score_h2(response_h2, error_h2)
    actual_model = usage_h2.get("actual_model", target.model) or actual_model

    cost_info2 = _compute_cost(target.model, usage_h2)
    cost_usd2 = cost_info2["cost_usd"]

    run_summary["results"]["H2"] = {
        "score": score_val_h2,
        "response_length": len(response_h2) if response_h2 else 0,
        "latency_ms": latency_h2,
        "fact_count": info_h2.get("fact_count", 0),
        "json_valid": info_h2.get("json_valid", False),
        "actual_model": actual_model,
        "cost_usd": cost_usd2,
    }
    if error_h2:
        run_summary["errors"]["H2"] = error_h2

    print(f"  H2 score: {score_val_h2:.2f}/1.00  |  Latency: {latency_h2}ms  |  Facts: {info_h2.get('fact_count', 0)}  |  JSON valid: {info_h2.get('json_valid', False)}  |  Cost: ${cost_usd2:.6f}")
    if error_h2:
        print(f"  H2 ERROR: {error_h2[:200]}")

    # Overall weighted score
    h1_w = 0.30
    h2_w = 0.50
    overall = (score_val_h1 * h1_w) + (score_val_h2 * h2_w)
    total_cost = cost_usd + cost_usd2
    total_latency = latency_h1 + latency_h2

    run_summary["overall_score"] = overall
    run_summary["total_cost_usd"] = total_cost
    run_summary["total_latency_ms"] = total_latency

    # Update run summary in DB
    try:
        finish_run(con, run_id, "completed")
    except Exception as e:
        finish_run(con, run_id, "error", str(e))

    con.close()

    # Write raw artifact
    artifact_path = RESULTS_DIR / f"{run_id}.json"
    artifact_path.write_text(json.dumps(run_summary, indent=2, default=str))
    print(f"\n  ✅ Run artifact: {artifact_path}")

    return run_summary


def _compute_cost(model: str, usage: dict) -> dict:
    if usage.get("cost") and usage["cost"] > 0:
        return {"cost_usd": float(usage["cost"]), "source": "api_response"}
    upstream = (usage.get("cost_details") or {}).get("upstream_inference_cost")
    if upstream:
        return {"cost_usd": float(upstream), "source": "upstream"}
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    # Default free tier pricing
    cost = (prompt_tokens / 1_000_000 * 0.0) + (completion_tokens / 1_000_000 * 0.0)
    return {"cost_usd": cost, "source": "free_tier"}


def _call_with_retry(
    target: Target, messages: list[dict], *, timeout: int, max_retries: int, max_tokens: int = 512,
) -> tuple[str, dict, int]:
    response, usage, latency = "", {}, 0
    for attempt in range(1 + max_retries):
        try:
            response, usage, latency = chat_completion(
                target, messages, temperature=0, max_tokens=max_tokens, timeout=timeout,
            )
            return response, usage, latency
        except Exception as e:
            error_text = str(e)
            print(f"    Attempt {attempt + 1}/{max_retries + 1} failed: {error_text[:150]}")
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"    Retrying in {wait}s...")
                time.sleep(wait)
            else:
                return "", {"error": error_text}, latency
    return "", {"error": "all retries exhausted"}, latency


# ─── Rate Limit Stress Test ───────────────────────────────────────────

def run_rate_limit_test(
    target: Target,
    burst: int = 10,
    stagger: float = 1.0,
    db_path: Path = DB_PATH,
    timeout: int = 120,
) -> dict:
    """H3: Rate limit stress — send burst requests and measure breaking point."""
    load_dotenv()
    con = init_hindsight_db(db_path)

    run_id = make_run_id("hindsight-rl", target.model)
    args = argparse.Namespace(
        benchmark_version="0.1.0",
        suite_version="v1",
        notes=f"Rate limit burst test: {burst} requests at {stagger}s stagger",
    )
    start_run(con, run_id, "hindsight-model-benchmark", args, target)

    print(f"\n{'='*60}")
    print(f"  RATE LIMIT STRESS TEST")
    print(f"  Model: {target.provider}/{target.model}")
    print(f"  Burst: {burst} requests, stagger: {stagger}s")
    print(f"{'='*60}")

    messages, est_tokens = build_h1_messages(target, target_tokens=10000)  # Smaller payload for speed

    results = []
    successful = 0
    failed = 0
    first_failure = None
    start_time = time.time()

    for i in range(burst):
        t0 = time.time()
        try:
            response, usage, latency = chat_completion(
                target, messages, temperature=0, max_tokens=16, timeout=timeout,
            )
            elapsed = time.time() - t0
            successful += 1
            status = "success"
            error = ""
            error_cat = ""
            print(f"  Request {i+1:3d}: OK  ({latency}ms, {usage.get('prompt_tokens', '?')} in tokens, elapsed {elapsed:.1f}s)")
        except Exception as e:
            elapsed = time.time() - t0
            failed += 1
            error = str(e)
            error_cat = classify_error(error)
            status = "failed"
            if first_failure is None:
                first_failure = i + 1
            print(f"  Request {i+1:3d}: FAIL  {error_cat} — {error[:100]} (elapsed {elapsed:.1f}s)")

        con.execute(
            "INSERT INTO hindsight_ratelimit(run_id, request_num, status, latency_ms, error, error_category, created_at) VALUES (?,?,?,?,?,?,?)",
            (run_id, i + 1, status, int(elapsed * 1000), error[:500], error_cat, utc_now()),
        )
        con.commit()
        results.append({"n": i + 1, "status": status, "error": error})

        # Check if we hit sustained failures (3 in a row = rate limit)
        if failed >= 3 and all(r["status"] == "failed" for r in results[-3:]):
            print(f"  ⚠️  Sustained failures after {i+1} requests (3 consecutive). Stopping.")
            break

        time.sleep(stagger)

    total_time = time.time() - start_time
    rpm = successful / (total_time / 60.0) if total_time > 0 else 0
    max_rpm = rpm

    run_summary = {
        "run_id": run_id,
        "provider": target.provider,
        "model": target.model,
        "successful": successful,
        "failed": failed,
        "first_failure_at": first_failure,
        "effective_rpm": round(max_rpm, 1),
        "total_time_s": round(total_time, 1),
    }

    finish_run(con, run_id, "completed" if failed == 0 else "partial")
    con.close()
    return run_summary


# ─── Obsidian Report ──────────────────────────────────────────────────

def update_obsidian(db_path: Path = DB_PATH) -> str:
    """Read all runs from DB and render Markdown leaderboard."""
    OBSIDIAN_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    con = connect_db(db_path)
    rows = con.execute("""
        SELECT run_id, provider, model, base_url, started_at, completed_at,
               score, total_cases, passed_cases, avg_latency_ms,
               prompt_tokens, completion_tokens, cost_usd, error, notes
        FROM benchmark_runs
        WHERE benchmark_name = 'hindsight-model-benchmark'
        ORDER BY started_at DESC
    """).fetchall()
    con.close()

    if not rows:
        OBSIDIAN_RESULTS_PATH.write_text("# Hindsight Model Benchmark Results\n\nNo runs recorded yet.\n")
        return "No data recorded yet."

    lines = [
        "# Hindsight Model Benchmark Results",
        "",
        "Benchmark for Hindsight `retain_extract_facts` compatibility.",
        "Tests: context size acceptance (~67K input tokens), JSON extraction quality, rate-limit headroom.",
        "",
        "| Run | Provider | Model | Score | Cases | Passed | Avg Latency | Cost | Date | Notes |",
        "|-----|----------|-------|-------|-------|--------|-------------|------|------|-------|",
    ]

    for row in rows:
        run_id = row["run_id"]
        provider = row["provider"]
        model = row["model"]
        score = row["score"]
        total = row["total_cases"]
        passed = row["passed_cases"]
        latency = row["avg_latency_ms"]
        cost = row["cost_usd"]
        date = row["started_at"][:10]
        notes = row["notes"] or ""
        error = row["error"] or ""

        score_display = f"{score:.2f}"
        if score >= 0.8:
            score_display = f"**{score_display}** ✅"
        elif score < 0.5:
            score_display = f"**{score_display}** ❌"

        notes_text = notes
        row_error = error
        if row_error:
            notes_text = (notes_text + " [err: " + row_error[:100] + "]").strip()

        lines.append(
            f"| {run_id[-8:]} | {provider} | {model} | {score_display} | {total} | {passed} | {latency:.0f}ms | ${cost:.6f} | {date} | {notes_text} |"
        )

    lines.append("")
    lines.append("---")
    lines.append(f"*Generated: {utc_now()}*")

    content = "\n".join(lines)
    OBSIDIAN_RESULTS_PATH.write_text(content)
    return content


# ─── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Hindsight Model Benchmark")
    sub = parser.add_subparsers(dest="command")

    # Run subcommand
    run_p = sub.add_parser("run", help="Run benchmark against a model")
    run_p.add_argument("--provider", default="omniroute")
    run_p.add_argument("--model")
    run_p.add_argument("--models", nargs="+", help="Multiple models (run sequentially)")
    run_p.add_argument("--base-url")
    run_p.add_argument("--api-key")
    run_p.add_argument("--target-tokens", type=int, default=67000,
                       help="Target input token count (default: 67000 for Hindsight)")
    run_p.add_argument("--timeout", type=int, default=300)
    run_p.add_argument("--max-retries", type=int, default=2)
    run_p.add_argument("--max-output-tokens", type=int, default=512,
                       help="max_tokens for API calls")
    run_p.add_argument("--db", default=str(DB_PATH))
    run_p.add_argument("--preflight", action="store_true", help="Ping model before benchmark")

    # Rate limit subcommand
    rl_p = sub.add_parser("ratelimit", help="Rate limit stress test")
    rl_p.add_argument("--provider", default="omniroute")
    rl_p.add_argument("--model", required=True)
    rl_p.add_argument("--base-url")
    rl_p.add_argument("--api-key")
    rl_p.add_argument("--burst", type=int, default=10)
    rl_p.add_argument("--stagger", type=float, default=1.0)
    rl_p.add_argument("--timeout", type=int, default=120)

    # Leaderboard subcommand
    lb_p = sub.add_parser("leaderboard", help="Show results leaderboard")

    # Update summary
    us_p = sub.add_parser("update-summary", help="Regenerate Obsidian markdown")

    args = parser.parse_args()

    if args.command == "leaderboard":
        print(update_obsidian())
        return

    if args.command == "update-summary":
        content = update_obsidian()
        print(content)
        print(f"\n✅ Written to {OBSIDIAN_RESULTS_PATH}")
        return

    if args.command == "ratelimit":
        target = resolve_target(
            args.provider, args.model, getattr(args, "base_url", None),
            getattr(args, "api_key", None),
        )
        result = run_rate_limit_test(
            target, burst=args.burst, stagger=args.stagger,
            timeout=args.timeout,
        )
        print(f"\nRate limit results: {result}")
        return

    if args.command == "run":
        models = (args.models if args.models else [])
        if args.model and args.model not in models:
            models.insert(0, args.model)

        if not models:
            print("Error: specify --model or --models")
            sys.exit(1)

        db_path = Path(args.db) if hasattr(args, "db") else DB_PATH
        target_tokens = getattr(args, "target_tokens", 67000)
        timeout = getattr(args, "timeout", 300)
        max_retries = getattr(args, "max_retries", 2)
        max_output_tokens = getattr(args, "max_output_tokens", 512)

        for model in models:
            target = resolve_target(
                args.provider, model, getattr(args, "base_url", None),
                getattr(args, "api_key", None),
            )
            print(f"\n🔍 Testing: {target.provider}/{target.model}")
            result = run_single_model(
                target, target_tokens=target_tokens,
                db_path=db_path, timeout=timeout, max_retries=max_retries,
                max_output_tokens=max_output_tokens,
            )
            print(f"\n✅ {model}: Overall score {result['overall_score']:.2f}/1.0  |  Cost ${result['total_cost_usd']:.6f}")
            # Stagger between models to avoid cascading rate limits
            if len(models) > 1:
                print(f"\n⏳ Waiting 30s before next model (rate limit cooldown)...")
                time.sleep(30)

        # Update Obsidian after all runs
        update_obsidian(db_path)
        print(f"\n📊 Leaderboard updated: {OBSIDIAN_RESULTS_PATH}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
