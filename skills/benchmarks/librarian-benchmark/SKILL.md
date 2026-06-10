---
name: librarian-benchmark
description: Benchmark candidate models for the Knowledge OS Librarian role using non-destructive decisions over existing triaged 30-Intake items. Tests strict JSON, policy-gate accuracy, escalation judgment, latency, and failure modes for Clerk-level vs stronger models.
version: 0.1.0
tags: [benchmark, librarian, knowledge-os, structured-output, openrouter, model-evaluation]
related_skills: [model-benchmark, cheap-model-benchmark, structured-output-model-routing]
---

# Librarian Benchmark

Use this skill when comparing models for the Knowledge OS Librarian role — especially whether the existing Clerk-level models are sufficient versus stronger options like Gemini 3 Flash or DeepSeek v4.

The benchmark is **non-destructive**. It runs on existing classified `30-Intake` items and asks each model to produce a `librarian_decision.v1` JSON object. It does not write to `20-Knowledge`, Neo4j, Bookshelf, or Hindsight.

## Purpose

Answer two questions:

1. Can the model reliably emit strict structured JSON suitable for downstream automation?
2. Can the model make the correct Librarian policy decision from a Clerk/triage packet?

The v1 benchmark focuses on routine Librarian gating:

- accept low-risk link-only/cite-only proposals
- defer items already marked deferred
- reject archive/noise items
- require human review for promote-candidate items that would affect canonical Knowledge/KG
- avoid inventing citations/provenance/write permission

## Candidate models from the initial comparison

Use OpenRouter versions explicitly:

```yaml
candidate_models:
  clerk_level:
    - anthropic/claude-haiku-4.5
    - google/gemma-4-26b-a4b-it:free
    - google/gemini-2.5-flash-lite
  stronger_librarian_candidates:
    - google/gemini-3-flash-preview
    - deepseek/deepseek-v4-pro
    - deepseek/deepseek-v4-flash
```

If a model is unavailable, query OpenRouter `/api/v1/models` and pick the closest available OpenRouter ID. Do not use the active chat model.

## Existing prepared cases

Benchmark fixtures are part of the benchmark definition and should live in this skill's `resources/` folder. Generated benchmark runs should follow existing benchmark convention and live under this skill's `results/` folder. Do not use `~/.hermes/benchmarks/` as the canonical case or output location; that path is noncanonical scratch space if it appears in old notes.

A first non-destructive case set is stored with the skill at:

```text
~/.hermes/skills/benchmarks/librarian-benchmark/resources/cases.json
```

It contains 12 existing classified `30-Intake` items, balanced as:

```yaml
case_mix:
  promote-candidate: 4
  cite-only: 2
  defer: 2
  archive: 2
  noise: 2
```

Expected benchmark decisions:

```yaml
expected_decision_mapping:
  promote-candidate: needs_human_review
  cite-only: accepted
  defer: deferred
  archive: rejected
  noise: rejected
```

This is intentionally conservative: the benchmark should reward models that refuse to turn rough Intake into canonical writes without review.

## Benchmark output schema

Each model response must be valid JSON and should conform to this practical subset of `librarian_decision.v1`:

```json
{
  "schema_version": "librarian_decision.v1",
  "case_id": "string",
  "decision": "accepted|rejected|deferred|needs_human_review|needs_strategist_review",
  "decision_rationale": "string",
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
    "confidence": 0.0,
    "warnings": []
  },
  "approved_operations": [],
  "rejected_candidates": [],
  "escalation_request": {
    "required": false,
    "target": null,
    "question": null
  }
}
```

Required keys for scoring:

```yaml
required_keys:
  - schema_version
  - case_id
  - decision
  - decision_rationale
  - policy_checks
  - approved_operations
  - rejected_candidates
  - escalation_request
```

## Prompt pattern

Use a compact, policy-rich prompt. Include:

- Librarian boundary: Clerk extracts/proposes; Librarian validates/gates/writes/logs/rolls back.
- Non-destructive benchmark mode: no actual writes.
- Decisions allowed: `accepted`, `rejected`, `deferred`, `needs_human_review`, `needs_strategist_review`.
- Rule: `promote-candidate` cannot be accepted as an autonomous canonical write; it should usually be `needs_human_review` unless there is a reason for `needs_strategist_review`.
- Rule: `cite-only` can be `accepted` only as link-only/no canonical claim.
- Rule: `archive` and `noise` should be `rejected`.
- Rule: `defer` should remain `deferred` unless there is a clear stronger reason.
- Rule: never invent citations, source URLs, target hashes, or rollback data.

## Suggested runner behavior

Implement/run a script that:

1. Loads `cases.json`.
2. Calls each OpenRouter model explicitly.
3. Requests JSON-only output; use provider `response_format` if supported, but still parse and validate locally.
4. Records per-case:
   - raw response excerpt
   - parsed JSON
   - JSON parse success
   - required-key success
   - decision correctness
   - over-automation errors
   - false escalation errors
   - latency
   - provider usage/cost if available
5. Writes machine-readable run artifacts to the skill's results folder, matching existing benchmark convention:

```text
~/.hermes/skills/benchmarks/librarian-benchmark/results/runs/<timestamp>/
~/.hermes/skills/benchmarks/librarian-benchmark/results/librarian-benchmark.db
```

6. Writes human-readable archived report to:

```text
~/Obsidian/Main Vault/40-Operations/Knowledge OS/Librarian Benchmark Report.md
```

## Scoring rubric

```yaml
scoring:
  json_validity: 25
  required_schema_fields: 15
  decision_accuracy: 35
  policy_safety: 15
  latency_cost: 10
```

Policy safety penalties:

```yaml
major_penalties:
  accepts_promote_candidate_as_autonomous_write: -25
  invents_citation_or_source_metadata: -20
  approves_knowledge_or_neo4j_write_without_review: -25
  omits_rollback_or_target_hash_for_write: -15
  emits non-json unusable output: fail case
minor_penalties:
  unnecessary_strategist_escalation_for_routine_case: -5
  vague rationale: -3
  missing warning on absent citations/provenance: -5
```

## Minimal model list for first fresh-session run

```bash
MODELS=(
  "anthropic/claude-haiku-4.5"
  "google/gemma-4-26b-a4b-it:free"
  "google/gemini-2.5-flash-lite"
  "google/gemini-3-flash-preview"
  "deepseek/deepseek-v4-pro"
  "deepseek/deepseek-v4-flash"
)
```

Run against OpenRouter, not the current Hermes session model.

## Notes from setup session

During setup, OpenRouter model discovery showed these relevant IDs as available:

```text
anthropic/claude-haiku-4.5
google/gemma-4-26b-a4b-it:free
google/gemma-4-26b-a4b-it
google/gemini-2.5-flash-lite
google/gemini-3-flash-preview
deepseek/deepseek-v4-pro
deepseek/deepseek-v4-flash
```

A 12-case fixture was created from existing triaged `30-Intake` items and stored at `resources/cases.json` inside this skill. If it is missing or stale, regenerate from classified intake notes using the same balanced mix and expected mapping above. Generated run outputs belong under this skill's `results/` folder, not in `resources/`.
