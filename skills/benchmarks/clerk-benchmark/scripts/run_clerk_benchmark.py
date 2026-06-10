#!/usr/bin/env python3
"""Clerk benchmark runner - Neo4j ingestion readiness.

The Clerk's real job is not toy exact-match extraction. It is taking messy text and
returning schema-bound graph JSON that can be validated and ingested into Neo4j
without exploding the pipeline.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any

COMMON = Path(__file__).resolve().parents[1].parent / 'model-benchmark' / 'scripts'
sys.path.insert(0, str(COMMON))
from benchmark_common import (  # type: ignore
    CaseResult,
    add_common_args,
    canonical_model_id,
    chat_completion,
    chat_completion_raw,
    connect_db,
    extract_text_and_usage,
    fetch_openrouter_pricing,
    finish_run,
    load_dotenv_key,
    make_run_id,
    parse_json_loose,
    record_case,
    resolve_pricing,
    resolve_target,
    start_run,
    strip_json_fences,
    token_cost_from_pricing,
)

BENCHMARK_NAME = 'clerk-benchmark'
BENCHMARK_VERSION = '0.4.0-cost-estimates'

# Fallback prices are dollars per token. OpenRouter's /models endpoint uses this same unit.
# Keep this tiny: it only covers models we benchmark often, and live OpenRouter pricing wins.
FALLBACK_PRICING_PER_TOKEN: dict[str, tuple[Decimal, Decimal]] = {
    'qwen/qwen3-235b-a22b-2507': (Decimal('0.000000071'), Decimal('0.0000001')),
    'google/gemma-4-26b-a4b-it': (Decimal('0.00000006'), Decimal('0.00000033')),
    'stepfun/step-3.5-flash': (Decimal('0.0000001'), Decimal('0.0000003')),
    'openai/gpt-4o': (Decimal('0.0000025'), Decimal('0.00001')),
    # Gemini public API pricing, dollars per token. Keep aliases because OmniRoute
    # model IDs vary by provider connection / combo mapping.
    'gemini/gemini-2.5-flash-lite': (Decimal('0.0000001'), Decimal('0.0000004')),
    'google/gemini-2.5-flash-lite': (Decimal('0.0000001'), Decimal('0.0000004')),
    'gemini/gemini-3.1-flash-lite-preview': (Decimal('0.0000001'), Decimal('0.0000004')),
    'google/gemini-3.1-flash-lite-preview': (Decimal('0.0000001'), Decimal('0.0000004')),
    'gemini-3.1-flash-lite-preview': (Decimal('0.0000001'), Decimal('0.0000004')),
    'gemini/gemini-2.5-flash': (Decimal('0.0000003'), Decimal('0.0000025')),
    'google/gemini-2.5-flash': (Decimal('0.0000003'), Decimal('0.0000025')),
    # Free/provider-subsidized lanes intentionally remain zero unless invoice-backed.
    'cerebras/qwen-3-235b-a22b-instruct-2507': (Decimal('0'), Decimal('0')),
}

ALLOWED_LABELS = {
    'Organization', 'Person', 'Product', 'Technology', 'Contract', 'Opportunity',
    'Program', 'Facility', 'Location', 'Agency', 'Metric', 'Event', 'Material',
    'Capability', 'Document', 'Constraint', 'Project'
}
ALLOWED_REL_TYPES = {
    'SUPPLIES', 'CUSTOMER_OF', 'PARTNERS_WITH', 'COMPETES_WITH', 'OWNS',
    'SUBSIDIARY_OF', 'AWARDED_TO', 'FUNDED_BY', 'LOCATED_IN', 'MANUFACTURES',
    'USES_TECHNOLOGY', 'HAS_CAPABILITY', 'MENTIONS', 'HAS_METRIC', 'HAS_EVENT',
    'DEPENDS_ON', 'PRODUCES', 'OPERATES', 'REGULATES', 'APPLIES_TO'
}
REQUIRED_TOP_KEYS = {'nodes', 'relationships', 'warnings'}
OPTIONAL_TOP_KEYS = {'source'}

SYSTEM_PROMPT = """You are the Clerk, a strict Neo4j ingestion extraction engine.
Return only valid JSON. No markdown fences. No commentary.
Your output must match this top-level shape exactly:
{
  "nodes": [
    {
      "temp_id": "stable_snake_case_id",
      "labels": ["AllowedLabel"],
      "properties": {"name": "..."},
      "confidence": 0.0,
      "source_span": "exact quote from source"
    }
  ],
  "relationships": [
    {
      "start_temp_id": "node_temp_id",
      "end_temp_id": "node_temp_id",
      "type": "ALLOWED_REL_TYPE",
      "properties": {},
      "confidence": 0.0,
      "source_span": "exact quote from source"
    }
  ],
  "warnings": []
}

Rules:
- Allowed labels: Agency, Capability, Constraint, Contract, Document, Event, Facility, Location, Material, Metric, Opportunity, Organization, Person, Product, Program, Project, Technology.
- Allowed relationship types: APPLIES_TO, AWARDED_TO, COMPETES_WITH, CUSTOMER_OF, DEPENDS_ON, FUNDED_BY, HAS_CAPABILITY, HAS_EVENT, HAS_METRIC, LOCATED_IN, MANUFACTURES, MENTIONS, OPERATES, OWNS, PARTNERS_WITH, PRODUCES, REGULATES, SUBSIDIARY_OF, SUPPLIES, USES_TECHNOLOGY.
- Use arrays for labels and relationships even when there is one item.
- `confidence` must be a number between 0 and 1.
- Every node needs a non-empty temp_id, labels, properties object, confidence, and source_span.
- Every relationship must reference existing node temp_ids.
- Neo4j property values must be strings, numbers, booleans, null, or arrays of those scalars. No nested objects inside properties.
- Normalize dates to YYYY-MM-DD when full date is present; otherwise keep the source wording as a string.
- Normalize money as numeric value plus currency/unit fields when explicit.
- If something is ambiguous, do not invent. Add a warning object with code, message, and source_span.
"""

CASES: list[dict[str, Any]] = [
    {
        'id': 'supplier_relationship_basic',
        'category': 'supplier_graph',
        'input': "Apple supplies OLED displays to Samsung for its Galaxy phones.",
        'min_nodes': 3,
        'min_relationships': 2,
        'must_nodes': [
            {'label': 'Organization', 'name': 'Apple'},
            {'label': 'Organization', 'name': 'Samsung'},
            {'label': 'Product', 'name_contains': 'OLED'},
        ],
        'must_relationships': [
            {'type': 'SUPPLIES', 'start_name': 'Apple', 'end_name': 'Samsung'},
        ],
        'pass_required_relationships': 0.0,
    },
    {
        'id': 'govcon_award_extraction',
        'category': 'govcon_graph',
        'input': "On March 14, 2025, the U.S. Air Force awarded Anduril Industries a $99.7 million contract for counter-UAS systems under FA8650-25-C-1234.",
        'min_nodes': 4,
        'min_relationships': 3,
        'must_nodes': [
            {'label': 'Agency', 'name_contains': 'Air Force'},
            {'label': 'Organization', 'name_contains': 'Anduril'},
            {'label': 'Contract', 'property_equals': {'contract_number': 'FA8650-25-C-1234'}},
            {'label': 'Product', 'name_contains': 'counter-UAS'},
        ],
        'must_relationships': [
            {'type': 'AWARDED_TO'},
            {'type': 'FUNDED_BY'},
        ],
        'must_properties': [
            {'label': 'Contract', 'key': 'award_amount', 'type': 'number'},
            {'label': 'Contract', 'key': 'currency', 'equals': 'USD'},
            {'label': 'Contract', 'key': 'award_date', 'equals': '2025-03-14'},
        ],
    },
    {
        'id': 'subsidiary_and_location',
        'category': 'entity_resolution_graph',
        'input': "Amazon Web Services, a subsidiary of Amazon.com, operates data centers in Northern Virginia and uses NVIDIA H100 GPUs for AI workloads.",
        'min_nodes': 5,
        'min_relationships': 4,
        'must_nodes': [
            {'label': 'Organization', 'name_contains': 'Amazon Web Services'},
            {'label': 'Organization', 'name_contains': 'Amazon.com'},
            {'label': 'Facility', 'name_contains': 'data center'},
            {'label': 'Location', 'name_contains': 'Northern Virginia'},
            {'label': 'Product', 'name_contains': 'H100'},
        ],
        'must_relationships': [
            {'type': 'SUBSIDIARY_OF'},
            {'type': 'OPERATES'},
            {'type': 'LOCATED_IN'},
            {'type': 'USES_TECHNOLOGY'},
        ],
    },
    {
        'id': 'negative_ambiguity_warning',
        'category': 'ambiguity_handling',
        'input': "Project Falcon may involve either Northrop Grumman or Lockheed Martin, but the source does not confirm the prime contractor. It mentions a possible hypersonics sensor payload.",
        'min_nodes': 2,
        'min_relationships': 1,
        'min_warnings': 1,
        'must_nodes': [
            {'label': 'Project', 'name_contains': 'Falcon'},
            {'label': 'Capability', 'name_contains': 'hypersonic'},
        ],
        'forbidden_relationships': [
            {'type': 'AWARDED_TO'},
            {'type': 'PARTNERS_WITH'},
        ],
        'pass_required_nodes': 0.5,
    },
    {
        'id': 'metric_normalization',
        'category': 'property_type_graph',
        'input': "TSMC reported Q4 2024 revenue of NT$868.46 billion and said 3nm process technology contributed 26% of wafer revenue.",
        'min_nodes': 3,
        'min_relationships': 2,
        'must_nodes': [
            {'label': 'Organization', 'name_contains': 'TSMC'},
            {'label': 'Metric', 'name_contains': 'revenue'},
            {'label': 'Technology', 'name_contains': '3nm'},
        ],
        'must_properties': [
            {'label': 'Metric', 'key': 'value', 'type': 'number'},
            {'label': 'Metric', 'key': 'currency', 'equals': 'NTD'},
            {'label': 'Metric', 'key': 'percentage', 'type': 'number'},
        ],
    },
    {
        'id': 'duplicate_entity_canonicalization',
        'category': 'dedupe_graph',
        'input': "International Business Machines Corp. (IBM) announced watsonx updates. IBM said watsonx.governance will help banks manage AI risk.",
        'min_nodes': 3,
        'max_organization_nodes': 1,
        'min_relationships': 2,
        'must_nodes': [
            {'label': 'Organization', 'name_contains': 'International Business Machines'},
            {'label': 'Product', 'name_contains': 'watsonx'},
            {'label': 'Product', 'name_contains': 'watsonx.governance'},
        ],
        'must_relationships': [
            {'type': 'OWNS'},
        ],
        'pass_dedupe': 0.0,
    },
    {
        'id': 'material_supply_chain',
        'category': 'supply_chain_graph',
        'input': "MP Materials produces rare earth oxides at Mountain Pass, California. General Motors depends on rare earth magnets for EV motors and signed a supply agreement with MP Materials.",
        'min_nodes': 5,
        'min_relationships': 5,
        'must_nodes': [
            {'label': 'Organization', 'name_contains': 'MP Materials'},
            {'label': 'Organization', 'name_contains': 'General Motors'},
            {'label': 'Material', 'name_contains': 'rare earth'},
            {'label': 'Location', 'name_contains': 'Mountain Pass'},
            {'label': 'Product', 'name_contains': 'EV motors'},
        ],
        'must_relationships': [
            {'type': 'PRODUCES'},
            {'type': 'DEPENDS_ON'},
            {'type': 'SUPPLIES'},
            {'type': 'LOCATED_IN'},
        ],
    },
    {
        'id': 'document_citation_spans',
        'category': 'source_traceability_graph',
        'input': "Source: DC-Grid-2026 memo. Dominion Energy warned that Loudoun County interconnection queues could delay new data center energization until 2028.",
        'min_nodes': 4,
        'min_relationships': 3,
        'must_nodes': [
            {'label': 'Document', 'name_contains': 'DC-Grid-2026'},
            {'label': 'Organization', 'name_contains': 'Dominion Energy'},
            {'label': 'Location', 'name_contains': 'Loudoun County'},
            {'label': 'Constraint', 'name_contains': 'interconnection'},
        ],
        'must_relationships': [
            {'type': 'MENTIONS'},
        ],
        'require_source_spans': True,
        'pass_score': 0.65,
        'pass_required_nodes': 0.5,
        'pass_required_relationships': 0.0,
    },
]


def normalize(s: Any) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', str(s).lower()).strip()


# Backward-compatible wrappers around benchmark_common shared utilities
def strip_fences(text: str) -> str:
    return strip_json_fences(text)


def parse_json_output(text: str) -> tuple[Any | None, list[str], bool]:
    """Parse JSON output, returning (parsed, errors, repaired)."""
    errors: list[str] = []
    try:
        return json.loads(text.strip()), errors, False
    except Exception as e:
        errors.append(f'json_parse_failed: {e}')
    cleaned = strip_fences(text)
    if cleaned != text.strip():
        try:
            return json.loads(cleaned), ['markdown_fence_used'], True
        except Exception as e:
            errors.append(f'fence_repair_failed: {e}')
    m = re.search(r'(\{.*\})', text, re.S)
    if m:
        try:
            return json.loads(m.group(1)), errors + ['json_extracted_from_surrounding_text'], True
        except Exception as e:
            errors.append(f'extraction_repair_failed: {e}')
    return None, errors, False


def estimate_case_cost_usd(usage: dict[str, int], model: str, provider: str, pricing_cache: dict[str, tuple[Decimal, Decimal]]) -> tuple[float, bool, str]:
    cost, source = token_cost_from_pricing(model, usage, FALLBACK_PRICING_PER_TOKEN, pricing_cache)
    return cost, True, source


def scalar_or_scalar_list(value: Any) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(v is None or isinstance(v, (str, int, float, bool)) for v in value)
    return False


def node_name(node: dict[str, Any]) -> str:
    props = node.get('properties') if isinstance(node.get('properties'), dict) else {}
    return str(props.get('name') or props.get('title') or node.get('temp_id') or '')


def node_has_label(node: dict[str, Any], label: str) -> bool:
    return isinstance(node.get('labels'), list) and label in node['labels']


def find_nodes(nodes: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for n in nodes:
        if 'label' in spec and not node_has_label(n, spec['label']):
            continue
        props = n.get('properties') if isinstance(n.get('properties'), dict) else {}
        name = normalize(node_name(n))
        if 'name' in spec and normalize(spec['name']) != name:
            continue
        if 'name_contains' in spec and normalize(spec['name_contains']) not in name:
            continue
        if 'property_equals' in spec:
            ok = True
            for k, v in spec['property_equals'].items():
                if props.get(k) != v:
                    ok = False
            if not ok:
                continue
        out.append(n)
    return out


def relationship_matches(rel: dict[str, Any], spec: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    if 'type' in spec and rel.get('type') != spec['type']:
        return False
    start = by_id.get(str(rel.get('start_temp_id')), {})
    end = by_id.get(str(rel.get('end_temp_id')), {})
    start_name = normalize(node_name(start))
    end_name = normalize(node_name(end))
    if 'start_name' in spec and normalize(spec['start_name']) not in start_name:
        return False
    if 'end_name' in spec and normalize(spec['end_name']) not in end_name:
        return False
    if 'product_name_contains' in spec:
        target = normalize(spec['product_name_contains'])
        if target not in start_name and target not in end_name and target not in normalize(rel.get('properties', {})):
            return False
    return True


def property_check(nodes: list[dict[str, Any]], check: dict[str, Any]) -> bool:
    candidates = [n for n in nodes if node_has_label(n, check['label'])]
    key = check['key']
    for n in candidates:
        props = n.get('properties') if isinstance(n.get('properties'), dict) else {}
        if key not in props:
            continue
        val = props[key]
        if check.get('type') == 'number' and isinstance(val, (int, float)) and not isinstance(val, bool):
            return True
        if 'equals' in check and val == check['equals']:
            return True
        if 'contains' in check and normalize(check['contains']) in normalize(val):
            return True
    return False


def validate_and_score(text: str, case: dict[str, Any]) -> tuple[bool, float, str, dict[str, Any]]:
    data, parse_errors, repaired = parse_json_output(text)
    dimensions = {
        'json_valid': 0.0,
        'strict_no_repair': 0.0,
        'schema_valid': 0.0,
        'neo4j_property_safe': 0.0,
        'reference_integrity': 0.0,
        'required_nodes': 0.0,
        'required_relationships': 0.0,
        'required_properties': 0.0,
        'ambiguity_handling': 1.0,
        'source_traceability': 0.0,
        'dedupe': 1.0,
    }
    failures: list[str] = []
    if data is None:
        return False, 0.0, '; '.join(parse_errors), {'dimensions': dimensions, 'failures': parse_errors}

    dimensions['json_valid'] = 1.0
    dimensions['strict_no_repair'] = 0.0 if repaired else 1.0
    if repaired:
        failures.extend(parse_errors or ['output_required_repair'])

    if not isinstance(data, dict):
        failures.append('top_level_not_object')
        return False, 0.1, '; '.join(failures), {'dimensions': dimensions, 'failures': failures}

    top_keys = set(data.keys())
    if not REQUIRED_TOP_KEYS.issubset(top_keys):
        failures.append(f'missing_top_keys:{sorted(REQUIRED_TOP_KEYS - top_keys)}')
    extra_top = top_keys - REQUIRED_TOP_KEYS - OPTIONAL_TOP_KEYS
    if extra_top:
        failures.append(f'extra_top_keys:{sorted(extra_top)}')

    nodes = data.get('nodes')
    rels = data.get('relationships')
    warnings = data.get('warnings')
    if not isinstance(nodes, list) or not isinstance(rels, list) or not isinstance(warnings, list):
        failures.append('nodes_relationships_warnings_must_be_arrays')
        nodes = nodes if isinstance(nodes, list) else []
        rels = rels if isinstance(rels, list) else []
        warnings = warnings if isinstance(warnings, list) else []

    node_errors = 0
    ids: set[str] = set()
    by_id: dict[str, dict[str, Any]] = {}
    property_safe = True
    source_spans = 0
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            node_errors += 1
            continue
        tid = n.get('temp_id')
        labels = n.get('labels')
        props = n.get('properties')
        conf = n.get('confidence')
        span = n.get('source_span')
        if not isinstance(tid, str) or not tid.strip():
            failures.append(f'node_{i}_bad_temp_id'); node_errors += 1
        elif tid in ids:
            failures.append(f'duplicate_temp_id:{tid}'); node_errors += 1
        else:
            ids.add(tid); by_id[tid] = n
        if not isinstance(labels, list) or not labels or not all(isinstance(x, str) and x in ALLOWED_LABELS for x in labels):
            failures.append(f'node_{i}_bad_labels:{labels}'); node_errors += 1
        if not isinstance(props, dict):
            failures.append(f'node_{i}_properties_not_object'); node_errors += 1
            props = {}
        else:
            for k, v in props.items():
                if not isinstance(k, str) or not scalar_or_scalar_list(v):
                    property_safe = False
                    failures.append(f'node_{i}_unsafe_property:{k}')
        if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not 0 <= conf <= 1:
            failures.append(f'node_{i}_bad_confidence'); node_errors += 1
        if isinstance(span, str) and span.strip():
            source_spans += 1
        else:
            failures.append(f'node_{i}_missing_source_span'); node_errors += 1

    rel_errors = 0
    for i, r in enumerate(rels):
        if not isinstance(r, dict):
            rel_errors += 1
            continue
        if r.get('type') not in ALLOWED_REL_TYPES:
            failures.append(f'rel_{i}_bad_type:{r.get("type")}'); rel_errors += 1
        if r.get('start_temp_id') not in ids or r.get('end_temp_id') not in ids:
            failures.append(f'rel_{i}_dangling_reference'); rel_errors += 1
        props = r.get('properties')
        if not isinstance(props, dict):
            failures.append(f'rel_{i}_properties_not_object'); rel_errors += 1
        else:
            for k, v in props.items():
                if not isinstance(k, str) or not scalar_or_scalar_list(v):
                    property_safe = False
                    failures.append(f'rel_{i}_unsafe_property:{k}')
        conf = r.get('confidence')
        if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not 0 <= conf <= 1:
            failures.append(f'rel_{i}_bad_confidence'); rel_errors += 1
        span = r.get('source_span')
        if isinstance(span, str) and span.strip():
            source_spans += 1
        else:
            failures.append(f'rel_{i}_missing_source_span'); rel_errors += 1

    enough_counts = len(nodes) >= case.get('min_nodes', 0) and len(rels) >= case.get('min_relationships', 0)
    if len(warnings) < case.get('min_warnings', 0):
        failures.append('missing_required_warning')
        dimensions['ambiguity_handling'] = 0.0

    if node_errors == 0 and rel_errors == 0 and not extra_top and REQUIRED_TOP_KEYS.issubset(top_keys) and enough_counts:
        dimensions['schema_valid'] = 1.0
    if property_safe:
        dimensions['neo4j_property_safe'] = 1.0
    if rel_errors == 0:
        dimensions['reference_integrity'] = 1.0

    must_nodes = case.get('must_nodes', [])
    found_nodes = sum(1 for spec in must_nodes if find_nodes(nodes, spec))
    dimensions['required_nodes'] = found_nodes / len(must_nodes) if must_nodes else 1.0
    for spec in must_nodes:
        if not find_nodes(nodes, spec):
            failures.append(f'missing_node:{spec}')

    must_rels = case.get('must_relationships', [])
    found_rels = sum(1 for spec in must_rels if any(relationship_matches(r, spec, by_id) for r in rels if isinstance(r, dict)))
    dimensions['required_relationships'] = found_rels / len(must_rels) if must_rels else 1.0
    for spec in must_rels:
        if not any(relationship_matches(r, spec, by_id) for r in rels if isinstance(r, dict)):
            failures.append(f'missing_relationship:{spec}')

    for spec in case.get('forbidden_relationships', []):
        if any(relationship_matches(r, spec, by_id) for r in rels if isinstance(r, dict)):
            failures.append(f'forbidden_relationship_present:{spec}')
            dimensions['ambiguity_handling'] = 0.0

    prop_checks = case.get('must_properties', [])
    found_props = sum(1 for chk in prop_checks if property_check(nodes, chk))
    dimensions['required_properties'] = found_props / len(prop_checks) if prop_checks else 1.0
    for chk in prop_checks:
        if not property_check(nodes, chk):
            failures.append(f'missing_or_bad_property:{chk}')

    if case.get('require_source_spans'):
        dimensions['source_traceability'] = 1.0 if source_spans == len(nodes) + len(rels) and source_spans > 0 else 0.0
    else:
        dimensions['source_traceability'] = source_spans / max(1, len(nodes) + len(rels))

    if 'max_organization_nodes' in case:
        org_count = sum(1 for n in nodes if isinstance(n, dict) and node_has_label(n, 'Organization'))
        if org_count > case['max_organization_nodes']:
            failures.append(f'too_many_organization_nodes:{org_count}')
            dimensions['dedupe'] = 0.0

    safety_keys = ['json_valid', 'strict_no_repair', 'schema_valid', 'neo4j_property_safe', 'reference_integrity']
    graph_keys = ['required_nodes', 'required_relationships', 'source_traceability', 'dedupe']
    domain_keys = ['required_properties', 'ambiguity_handling']

    safety_score = sum(dimensions[k] for k in safety_keys) / len(safety_keys)
    graph_quality_score = (
        dimensions['required_nodes'] * 0.40
        + dimensions['required_relationships'] * 0.35
        + dimensions['source_traceability'] * 0.15
        + dimensions['dedupe'] * 0.10
    )
    domain_fidelity_score = (
        dimensions['required_properties'] * 0.65
        + dimensions['ambiguity_handling'] * 0.35
    )
    overall_score = (
        safety_score * 0.50
        + graph_quality_score * 0.35
        + domain_fidelity_score * 0.15
    )

    ingestion_ready = (
        dimensions['json_valid'] == 1.0
        and dimensions['strict_no_repair'] == 1.0
        and dimensions['schema_valid'] == 1.0
        and dimensions['neo4j_property_safe'] == 1.0
        and dimensions['reference_integrity'] == 1.0
    )
    # Case pass now means hard Neo4j ingestion safety only. Graph/domain quality is scored separately.
    passed = ingestion_ready
    notes_obj = {
        'scores': {
            'safety': round(safety_score, 4),
            'graph_quality': round(graph_quality_score, 4),
            'domain_fidelity': round(domain_fidelity_score, 4),
            'overall': round(overall_score, 4),
            'ingestion_ready': ingestion_ready,
        },
        'score_dimensions': dimensions,
        'failures': failures[:20],
    }
    notes = json.dumps(notes_obj, sort_keys=True)
    return passed, round(overall_score, 4), notes, notes_obj


def render_obsidian(db_path: str, obsidian_dir: str) -> None:
    out = Path(obsidian_dir).expanduser() / f'{BENCHMARK_NAME}-results.md'
    script = COMMON / 'update_obsidian_results.py'
    subprocess.run([sys.executable, str(script), '--db', db_path, '--benchmark-name', BENCHMARK_NAME, '--out', str(out)], check=False)


def chat_completion_with_retries(target, messages, *, temperature: float, max_tokens: int, timeout: int, extra: dict[str, Any], max_retries: int):
    attempt = 0
    while True:
        try:
            resp, latency_ms = chat_completion_raw(
                target,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                extra=extra,
            )
            text, usage = extract_text_and_usage(resp)
            return text, usage, latency_ms, resp
        except Exception as e:
            msg = str(e)
            retryable = 'HTTP 429' in msg or 'Requests per minute limit exceeded' in msg or 'reset after' in msg
            if attempt >= max_retries or not retryable:
                raise
            m = re.search(r'reset after (\d+)s', msg)
            wait_s = int(m.group(1)) + 1 if m else min(30, 2 ** attempt)
            time.sleep(wait_s)
            attempt += 1


def main() -> None:
    ap = argparse.ArgumentParser(description='Run Clerk Neo4j ingestion-readiness benchmark')
    add_common_args(ap)
    ap.add_argument('--json-mode', action='store_true', help='Request OpenAI/OpenRouter JSON object response_format where supported')
    ap.set_defaults(benchmark_version=BENCHMARK_VERSION, max_tokens=2048, suite_version='neo4j-v1')
    args = ap.parse_args()

    target = resolve_target(args.provider, args.model, args.base_url, args.api_key)
    pricing_cache = fetch_openrouter_pricing()
    con = connect_db(args.db)
    run_id = make_run_id(BENCHMARK_NAME, target.model.replace('/', '_').replace(':', '_'))
    start_run(con, run_id, BENCHMARK_NAME, args, target)
    status, error = 'completed', ''

    try:
        for c in CASES:
            prompt = f"{SYSTEM_PROMPT}\n\nUnstructured source text:\n{c['input']}\n\nExtract graph JSON now."
            try:
                extra = {'stream': False}
                if args.json_mode:
                    extra['response_format'] = {'type': 'json_object'}
                text, usage, latency_ms, resp = chat_completion_with_retries(
                    target,
                    [{'role': 'user', 'content': prompt}],
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    timeout=args.timeout,
                    extra=extra,
                    max_retries=args.max_retries,
                )
                passed, score, notes, _ = validate_and_score(text, c)
                cost_usd, cost_estimated, pricing_source = estimate_case_cost_usd(usage, target.model, target.provider, pricing_cache)
                try:
                    notes_data = json.loads(notes)
                    notes_data['cost'] = {
                        'usd': cost_usd,
                        'per_100_runs_usd': cost_usd * 100,
                        'pricing_source': pricing_source,
                        'pricing_required': pricing_source == 'unknown',
                    }
                    notes = json.dumps(notes_data, sort_keys=True)
                except Exception:
                    notes = notes + f'; cost_usd={cost_usd:.8f}; cost_per_100_runs_usd={cost_usd * 100:.6f}; pricing_source={pricing_source}'
                record_case(con, run_id, CaseResult(
                    case_id=c['id'],
                    category=c['category'],
                    prompt=prompt,
                    expected=json.dumps({k: c[k] for k in c.keys() if k not in {'input'}}, sort_keys=True),
                    response=text.strip(),
                    passed=passed,
                    score=score,
                    latency_ms=latency_ms,
                    prompt_tokens=usage['prompt_tokens'],
                    completion_tokens=usage['completion_tokens'],
                    total_tokens=usage['total_tokens'],
                    cost_usd=cost_usd,
                    cost_estimated=cost_estimated,
                    notes=notes,
                    raw_json=json.dumps(resp)[:8000],
                ))
                if args.provider == 'omniroute':
                    time.sleep(10)
            except Exception as e:
                if args.provider == 'omniroute':
                    time.sleep(10)
                record_case(con, run_id, CaseResult(
                    case_id=c['id'],
                    category=c['category'],
                    prompt=prompt,
                    expected=json.dumps({k: c[k] for k in c.keys() if k not in {'input'}}, sort_keys=True),
                    response='',
                    passed=False,
                    score=0.0,
                    latency_ms=0,
                    error=str(e),
                ))
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
