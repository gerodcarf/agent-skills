# Researcher Benchmark Rubric

The Researcher benchmark is designed for the Hermes researcher role, not the scout, clerk, or final synthesizer roles.

## Contract under test

A Researcher model receives an evidence packet or bounded source manifest and must return a handoff that downstream agents can verify and ingest.

The core question is:

> Can this model transform sources into cited, temporally safe, structured research facts without wandering, inventing support, or collapsing into vague prose?

## Dimensions

### 1. JSON/schema discipline — 20 points

- Valid JSON object.
- Required top-level keys exist:
  - `task_assessment`
  - `source_plan`
  - `fact_table`
  - `synthesis`
  - `handoff`

### 2. Source discipline — 20 points

- Uses all required source IDs when relevant.
- Does not invent source IDs.
- Maps facts to source IDs rather than generic citation language.
- Preserves source types and source purposes.

### 3. Fact extraction completeness — 20 points

- Produces enough facts for the case.
- Includes key domain anchors from the expected case metadata.
- Each fact carries:
  - `market_knowledge_date`
  - `source_id`
  - `metric`
  - `value`
  - `constraint_implication`

### 4. Temporal/lookahead discipline — 15 points

- Uses ISO `market_knowledge_date` values.
- Does not import facts unavailable at that date.
- Explicitly states lookahead guardrails.

This is critical for historical semiconductor boom/bust work because current AI/HBM outcomes can contaminate interpretation of 2018-2019 memory cycles.

### 5. Bounded research judgment — 15 points

- Chooses the correct `recommended_next_action`:
  - `handoff_to_clerk` when enough evidence exists.
  - `targeted_followup` when more specific sources are needed.
  - `block_for_missing_source` when the task cannot proceed responsibly.
- Avoids generic “keep searching until complete” behavior.
- Names missing source classes narrowly.

### 6. Handoff utility — 10 points

- Includes Clerk/Neo4j candidate entities and relationships.
- Includes follow-up tasks as scoped slices, not monolithic research projects.
- Produces a useful bridge from evidence to ingestion or synthesis.

## Pass threshold

Default pass threshold is **0.80**.

A model that writes fluent prose but fails citation/source/temporal controls should fail. A model that is terse but valid, cited, and handoff-ready should pass.

## Failure modes this benchmark is meant to catch

- Repeated broad search recommendations after sufficient evidence exists.
- Invented sources or unsupported citations.
- Retrospective lookahead contamination.
- Mixing 2023-2024 HBM/AI logic into 2018-2019 memory-cycle facts.
- Treating planning/decomposition tasks as ingestion-ready fact extraction.
- Producing a memo instead of a structured handoff.
