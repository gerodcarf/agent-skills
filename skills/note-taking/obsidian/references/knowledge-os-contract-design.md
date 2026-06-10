# Knowledge OS Contract Design Pattern

Use this reference when drafting durable Knowledge OS architecture notes or backlog plans about agent/operation contracts. It summarizes the contract model established from the GBrain comparison and the two clipped arXiv articles on Agent Contracts / Agent Behavioral Contracts.

## Source-aligned layers

1. **Operation contracts** — GBrain-style operation definitions: stable verb, params/input schema, output schema, handler, mutating flag, scope, local-only/remote-safe behavior, caller context.
2. **Execution contracts** — from resource-bounded Agent Contracts: `C=(I,O,S,R,T,Φ,Ψ)` where inputs/outputs/skills are bounded by resources, time, success criteria, and termination conditions.
3. **Behavioral contracts** — from Agent Behavioral Contracts: preconditions, hard/soft invariants, hard/soft governance, recovery, satisfaction/telemetry. Implement rich behavioral monitoring later, but reserve schema fields early.
4. **Pipeline / handoff contracts** — composition across Scout → Clerk → Librarian → Knowledge Writer / Neo4j Writer. Upstream outputs must satisfy downstream preconditions.

## Local v1 schema decision

Gerod chose to include explicit accountability metadata in v1:

```yaml
principal: knowledge-os
subject: profile:librarian
```

This is a local extension, not directly copied from GBrain or the papers. Treat it as clarifying metadata, not the formal mathematical core.

## Inherit platform guardrails; add local anti-slippage rules

Do not rebuild generic Hermes/model/platform safety guardrails. Instead, contracts should declare inherited guardrails and define Knowledge OS-specific deltas:

```yaml
inherits:
  - hermes.platform_guardrails
  - hermes.profile_permissions
  - vault.AGENTS.md
```

Behavioral contracts should focus on doctrine slippage that generic platforms do not know:

- no canonical Knowledge write without citation
- no Neo4j edge/upsert without provenance
- no Hindsight memory as evidence
- no `30-Intake` item as sole canonical citation
- no collapse of Obsidian Master Plan and Hermes Delegation Board
- trading/ledger mutations require backup/review discipline

## Phasing recommendation

Build up front:

- operation contracts
- execution contracts: resource/time/tool budgets, lifecycle, terminal states
- schema fields for behavior/recovery/telemetry
- a small number of easy hard invariants

Defer:

- fuzzy soft-invariant scoring
- behavioral drift metrics
- calibration/reference distributions
- LLM-as-judge monitoring loops
- complex recovery handlers

## Minimal contract skeleton

```yaml
contractspec: kos/v1
kind: agent
name: librarian-promotion-contract
principal: knowledge-os
subject: profile:librarian

inherits:
  - hermes.platform_guardrails
  - vault.AGENTS.md

operation_scope:
  allowed_operations:
    - source.search
    - pageindex.query
    - kg.query
    - librarian.propose
    - knowledge.validate

execution:
  resources:
    max_tokens: 100000
    max_runtime_seconds: 900
    max_tool_calls: 60
  termination:
    - budget_exhausted
    - missing_required_provenance
    - human_review_required

behavior:
  hard_invariants:
    - no_30_intake_as_canonical_evidence
    - no_hindsight_memory_as_evidence
    - no_canonical_write_without_citation
    - no_neo4j_edge_without_provenance
  soft_invariants:
    - prefer_primary_sources
    - flag_uncertain_entity_type
    - distinguish_fact_from_inference

recovery:
  missing_citation:
    action: downgrade_to_candidate_packet
  provenance_gap:
    action: block_for_librarian_review
```

## Pitfalls

- Do not call an invented field “source-backed” unless it is actually present in GBrain or the papers. If using a local extension such as `principal`/`subject`, label it as a local schema decision.
- Do not overbuild behavioral contracts in phase 1; reserve hooks and enforce obvious hard invariants first.
- Do not duplicate generic platform guardrails. Inherit them and add Knowledge OS-specific invariants.
