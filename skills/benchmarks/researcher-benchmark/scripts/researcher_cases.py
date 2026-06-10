#!/usr/bin/env python3
"""Researcher benchmark cases and scorer.

This is a benchmark-common spoke module. It intentionally contains only
Researcher-specific cases and rubric logic; execution stays in
benchmark-common/scripts/run_benchmark.py.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

_COMMON = Path.home() / ".hermes" / "skills" / "benchmarks" / "benchmark-common" / "scripts"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

from run_benchmark import CaseDef  # type: ignore  # noqa: E402

BENCHMARK_NAME = "researcher-benchmark"
SUITE_VERSION = "semiconductor-v0.1"
PASS_THRESHOLD = 0.80

SYSTEM_PROMPT = """You are the Hermes Researcher profile under benchmark.
Return only strict JSON. Do not use markdown fences.
Your job is not to write a polished memo. Your job is to convert the supplied
evidence packet into cited, point-in-time facts and a bounded handoff.
Do not invent sources. Do not use facts unavailable at the stated market
knowledge dates. If evidence is insufficient, say so and specify targeted
follow-up sources instead of broad searching.
"""

OUTPUT_CONTRACT = """
Return strict JSON with keys:
- task_assessment: {sufficient_evidence:boolean, recommended_next_action:string, missing_sources:list}
- source_plan: list of {source_id, source_type, use}
- fact_table: list of facts with fact_id, company, cycle, market_knowledge_date, source_id, fact_type, metric, value, constraint_implication, confidence
- synthesis: {cycle_read, downstream_constraint_relevance, lookahead_guardrails}
- handoff: {ready_for_clerk:boolean, neo4j_candidate_entities:list, neo4j_candidate_relationships:list, followup_tasks:list}
""".strip()


def _prompt(title: str, task: str, evidence: str, constraints: str) -> str:
    return f"""{SYSTEM_PROMPT}

# Benchmark case: {title}

## Research task
{task}

## Evidence packet
{evidence}

## Constraints
{constraints}

## Output contract
{OUTPUT_CONTRACT}
"""


CASES: List[CaseDef] = [
    CaseDef(
        id="skhynix_2018_2019_memory_downturn",
        category="historical_cycle_extraction",
        prompt=_prompt(
            "SK Hynix 2018-2019 memory downturn",
            "Extract handoff-ready facts about the 2018-2019 DRAM/NAND downturn relevant to future AI/data-center semiconductor chokepoint mapping.",
            """S1 | company_annual_report | SK Hynix Annual Report 2018 | publication_date=2019-03-29 | market_knowledge_date=2019-03-29
- Management described a sharp deterioration in the memory market from late 2018.
- DRAM demand growth slowed as data-center customers adjusted inventories.
- NAND pricing also weakened because suppliers increased 3D NAND output while demand growth softened.
- SK Hynix stated it would respond with flexible capex and technology migration rather than indiscriminate capacity expansion.

S2 | earnings_call | SK Hynix Q4 2018 earnings call | publication_date=2019-01-24 | market_knowledge_date=2019-01-24
- Q4 2018 DRAM bit shipments declined by a single-digit percentage quarter over quarter.
- DRAM average selling price declined by a high single-digit percentage quarter over quarter.
- NAND bit shipments increased by a low-teen percentage quarter over quarter, while NAND ASP declined by around 20% quarter over quarter.
- Management said server customers were carrying inventory and delaying purchases.

S3 | industry_data | WSTS/SIA memory market summary | publication_date=2019-06-04 | market_knowledge_date=2019-06-04
- Global semiconductor sales in early 2019 were materially lower year over year, with memory the largest drag.
- The downturn followed a 2017-2018 memory pricing boom and capacity response.
""",
            """Use only S1-S3. Do not mention HBM3, ChatGPT, generative AI GPU clusters, or 2023-2024 outcomes as facts known in 2019. Recommended next action should be handoff_to_clerk if you find enough facts; otherwise targeted_followup.""",
        ),
        expected=json.dumps(
            {
                "required_sources": ["S1", "S2", "S3"],
                "required_terms": ["inventory", "data-center", "DRAM", "NAND", "ASP", "capex", "market_knowledge_date"],
                "forbidden_terms": ["HBM3", "ChatGPT", "generative AI", "2024 HBM"],
                "required_next_action": "handoff_to_clerk",
                "min_facts": 5,
                "required_companies": ["SK Hynix"],
                "required_cycles": ["2018", "2019"],
            }
        ),
    ),
    CaseDef(
        id="micron_2023_2024_hbm_ramp",
        category="ai_constraint_extraction",
        prompt=_prompt(
            "Micron 2023-2024 HBM ramp",
            "Extract facts about Micron's AI/HBM capacity ramp and explain how they map to AI/data-center downstream constraints.",
            """S1 | annual_report | Micron FY2023 Form 10-K | publication_date=2023-10-06 | market_knowledge_date=2023-10-06
- Micron reported a severe memory industry downturn in fiscal 2023, including weak pricing, high customer inventories, and reduced wafer starts.
- The company continued technology transitions and emphasized long-term demand from data center, AI, and automotive markets.
- Micron described capex discipline after the downturn.

S2 | earnings_call | Micron FQ2 2024 earnings call | publication_date=2024-03-20 | market_knowledge_date=2024-03-20
- Management said AI server demand was driving strong growth for high-bandwidth memory and high-capacity DRAM.
- Micron stated its HBM3E product had entered volume production and would contribute revenue in fiscal 2024.
- Management said calendar 2024 HBM supply was sold out and a majority of calendar 2025 supply had already been allocated.
- Management noted HBM die size and manufacturing complexity can displace conventional DRAM bit supply.

S3 | investor_presentation | Micron AI memory presentation | publication_date=2024-05-21 | market_knowledge_date=2024-05-21
- HBM demand is linked to AI accelerator platforms and advanced packaging constraints.
- HBM requires tight coordination across memory, logic GPU/accelerator vendors, packaging, substrate, and customer qualification schedules.
""",
            """Use only S1-S3. Keep 2023 downturn facts separate from 2024 AI/HBM ramp facts. The output should be ready for a Clerk to convert into supply-chain graph entities and relationships.""",
        ),
        expected=json.dumps(
            {
                "required_sources": ["S1", "S2", "S3"],
                "required_terms": ["HBM3E", "sold out", "2025", "AI server", "advanced packaging", "DRAM", "market_knowledge_date"],
                "forbidden_terms": ["2026", "Blackwell Ultra", "HBM4 volume production"],
                "required_next_action": "handoff_to_clerk",
                "min_facts": 6,
                "required_companies": ["Micron"],
                "required_cycles": ["2023", "2024"],
            }
        ),
    ),
    CaseDef(
        id="cross_cycle_semiconductor_backfill_plan",
        category="bounded_research_planning",
        prompt=_prompt(
            "Cross-cycle semiconductor backfill plan",
            "Design a bounded researcher handoff plan for filling semiconductor supply-chain history relevant to AI/data-center downstream constraints. Focus on prior booms/busts and avoid monolithic scope creep.",
            """S1 | project_note | Memory Sector Chokepoint Backfill draft | publication_date=2026-06-06 | market_knowledge_date=2026-06-06
- Existing project focuses on memory-sector chokepoints and HBM/DRAM/NAND suppliers.
- It overlaps with broader semiconductor supply-chain backfill projects covering packaging, foundry, substrates, WFE, and materials.
- The immediate operating problem is that broad research tasks time out or spin on search loops.

S2 | task_log_summary | Researcher task failure diagnosis | publication_date=2026-06-06 | market_knowledge_date=2026-06-06
- Recent SK Hynix and Micron backfill tasks used less than 100k input tokens and did not require a 1M context model.
- Failures were caused by repeated web-search/extract loops, task timeout configuration, or runtime/library issues.
- Recommended remediation is decomposition by company × cycle × source type with explicit stop conditions.

S3 | domain_requirement | Master semiconductor supply-chain backfill requirement | publication_date=2026-06-06 | market_knowledge_date=2026-06-06
- Need a master project task to fill in semiconductor supply chain as it relates to AI/data-center downstream constraints.
- Backfill must cover previous semiconductor booms and busts, not only the current AI/HBM cycle.
- Relevant historical cycles include memory pricing booms/busts, foundry capacity shortages, packaging/substrate bottlenecks, and WFE/materials constraints.
""",
            """Do not propose one giant autonomous task. Produce a bounded plan with specific follow-up task slices and stop conditions. Recommended next action should be targeted_followup, not handoff_to_clerk, because this is a planning/decomposition case rather than evidence extraction.""",
        ),
        expected=json.dumps(
            {
                "required_sources": ["S1", "S2", "S3"],
                "required_terms": ["company", "cycle", "source type", "stop", "memory", "foundry", "packaging", "substrate", "WFE", "materials"],
                "forbidden_terms": ["one giant task", "1M context required", "search the web until complete"],
                "required_next_action": "targeted_followup",
                "min_facts": 3,
                "required_companies": [],
                "required_cycles": ["boom", "bust"],
            }
        ),
    ),
]


def _load_expected(case: CaseDef) -> Dict[str, Any]:
    try:
        return json.loads(case.expected)
    except Exception:
        return {}


def _parse_json(response: str) -> Tuple[Dict[str, Any] | None, str]:
    text = response.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
        if not isinstance(obj, dict):
            return None, "top-level JSON is not an object"
        return obj, ""
    except Exception as exc:
        return None, f"invalid JSON: {exc}"


def _text_contains(text: str, term: str) -> bool:
    return term.lower() in text.lower()


def _collect_source_ids(obj: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for item in obj.get("source_plan", []) or []:
        if isinstance(item, dict) and item.get("source_id"):
            ids.append(str(item["source_id"]))
    for item in obj.get("fact_table", []) or []:
        if isinstance(item, dict) and item.get("source_id"):
            ids.append(str(item["source_id"]))
    return ids


def _fact_table(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    facts = obj.get("fact_table", [])
    return [f for f in facts if isinstance(f, dict)] if isinstance(facts, list) else []


def _recommended_next_action(obj: Dict[str, Any]) -> str:
    assessment = obj.get("task_assessment") or {}
    if isinstance(assessment, dict):
        return str(assessment.get("recommended_next_action", ""))
    return ""


def _handoff(obj: Dict[str, Any]) -> Dict[str, Any]:
    handoff = obj.get("handoff") or {}
    return handoff if isinstance(handoff, dict) else {}


def _has_market_dates(facts: Iterable[Dict[str, Any]]) -> bool:
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    return all(pattern.match(str(f.get("market_knowledge_date", ""))) for f in facts)


def _list_len(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def score(response: str, case: CaseDef) -> Tuple[bool, float, str]:
    expected = _load_expected(case)
    obj, err = _parse_json(response)
    notes: List[str] = []
    total = 0.0

    if obj is None:
        return False, 0.0, err

    raw = json.dumps(obj, ensure_ascii=False)

    # 20 pts: JSON validity and required top-level schema.
    required_top = ["task_assessment", "source_plan", "fact_table", "synthesis", "handoff"]
    present = [k for k in required_top if k in obj]
    schema_score = 20.0 * len(present) / len(required_top)
    total += schema_score
    if schema_score < 20:
        notes.append(f"schema missing {sorted(set(required_top) - set(present))}")

    # 20 pts: source discipline.
    required_sources = set(expected.get("required_sources", []))
    used_sources = set(_collect_source_ids(obj))
    source_score = 0.0
    if required_sources:
        source_score += 12.0 * len(required_sources & used_sources) / len(required_sources)
    invented = sorted(s for s in used_sources if s and s not in required_sources)
    source_score += 8.0 if not invented else max(0.0, 8.0 - 2.0 * len(invented))
    total += min(20.0, source_score)
    if invented:
        notes.append(f"invented source ids {invented}")

    # 20 pts: fact extraction completeness.
    facts = _fact_table(obj)
    min_facts = int(expected.get("min_facts", 0))
    fact_score = 0.0
    if min_facts:
        fact_score += 8.0 * min(1.0, len(facts) / min_facts)
    required_terms = expected.get("required_terms", [])
    matched_terms = [t for t in required_terms if _text_contains(raw, str(t))]
    if required_terms:
        fact_score += 8.0 * len(matched_terms) / len(required_terms)
    with_source_and_implication = [
        f for f in facts
        if f.get("source_id") and f.get("constraint_implication") and f.get("metric") and f.get("value")
    ]
    fact_score += 4.0 * (len(with_source_and_implication) / len(facts) if facts else 0.0)
    total += min(20.0, fact_score)
    missing_terms = sorted(set(required_terms) - set(matched_terms))
    if missing_terms:
        notes.append(f"missing terms {missing_terms[:8]}")

    # 15 pts: temporal discipline and lookahead guardrails.
    temporal_score = 0.0
    if facts and _has_market_dates(facts):
        temporal_score += 7.0
    synthesis = obj.get("synthesis") or {}
    guardrail_text = ""
    if isinstance(synthesis, dict):
        guardrails = synthesis.get("lookahead_guardrails") or []
        if isinstance(guardrails, list):
            guardrail_text = json.dumps(guardrails, ensure_ascii=False)

    # A model should be allowed to name forbidden lookahead concepts inside
    # explicit guardrails (e.g. "avoided ChatGPT/HBM3 claims"). Penalize only
    # appearances outside that guardrail field.
    raw_without_guardrails = raw.replace(guardrail_text, "") if guardrail_text else raw
    forbidden = [t for t in expected.get("forbidden_terms", []) if _text_contains(raw_without_guardrails, str(t))]
    temporal_score += 6.0 if not forbidden else max(0.0, 6.0 - 2.0 * len(forbidden))
    if isinstance(synthesis, dict) and _list_len(synthesis.get("lookahead_guardrails")) >= 1:
        temporal_score += 2.0
    total += min(15.0, temporal_score)
    if forbidden:
        notes.append(f"forbidden/lookahead terms present outside guardrails {forbidden}")

    # 15 pts: bounded research judgment.
    next_action = _recommended_next_action(obj)
    required_next = expected.get("required_next_action")
    judgment_score = 8.0 if next_action == required_next else 0.0
    assessment = obj.get("task_assessment") or {}
    if isinstance(assessment, dict) and "sufficient_evidence" in assessment and isinstance(assessment.get("missing_sources", []), list):
        judgment_score += 4.0
    if not any(_text_contains(raw, phrase) for phrase in ["search the web until", "keep searching", "comprehensive internet search"]):
        judgment_score += 3.0
    total += min(15.0, judgment_score)
    if next_action != required_next:
        notes.append(f"next_action {next_action!r} != {required_next!r}")

    # 10 pts: handoff utility.
    handoff = _handoff(obj)
    handoff_score = 0.0
    if "ready_for_clerk" in handoff:
        handoff_score += 2.0
    handoff_score += 3.0 if _list_len(handoff.get("neo4j_candidate_entities")) >= 1 else 0.0
    handoff_score += 3.0 if _list_len(handoff.get("neo4j_candidate_relationships")) >= 1 else 0.0
    if isinstance(handoff.get("followup_tasks", []), list):
        handoff_score += 2.0
    total += min(10.0, handoff_score)

    normalized = round(total / 100.0, 4)
    passed = normalized >= PASS_THRESHOLD
    if not notes:
        notes.append("ok")
    return passed, normalized, "; ".join(notes)
