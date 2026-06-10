# Neo4j Ingestion Rebuild Notes — 2026-05-08

## Trigger

The toy Clerk benchmark was misaligned with the Clerk role. It exact-matched simple Apple JSON/CSV answers, but the production requirement is: messy text -> strict graph JSON that can safely feed Neo4j.

## User correction

The Clerk's main job is reliable Neo4j ingestion. Do not optimize this benchmark around exact toy values or generic structured-output neatness. Optimize around graph-readiness.

## Implementation summary

Rebuilt `scripts/run_clerk_benchmark.py` to version `0.2.0-neo4j-ingestion`, suite `neo4j-v1`.

Core output contract:

```json
{
  "nodes": [
    {
      "temp_id": "stable_snake_case_id",
      "labels": ["Organization"],
      "properties": {"name": "Example Corp"},
      "confidence": 0.95,
      "source_span": "exact quote from source"
    }
  ],
  "relationships": [
    {
      "start_temp_id": "example_corp",
      "end_temp_id": "product_x",
      "type": "MANUFACTURES",
      "properties": {},
      "confidence": 0.85,
      "source_span": "exact quote from source"
    }
  ],
  "warnings": []
}
```

Scoring dimensions:
- JSON validity
- strict no-repair output, i.e. no markdown fence stripping
- schema validity
- Neo4j-safe property values
- relationship reference integrity
- required core nodes
- required core relationships
- required normalized properties
- ambiguity handling
- source traceability
- dedupe/canonicalization

Scenario coverage:
1. supplier relationship
2. GovCon award extraction
3. subsidiary/location/facility/technology graph
4. ambiguity warning instead of hallucinated prime contractor
5. metric normalization
6. duplicate entity canonicalization
7. material supply chain
8. document/source citation and constraint extraction

## Important benchmark design lesson

A model that produces valid JSON but uses illegal relationship labels like `HAS_CONTRACT` or `CONTRIBUTES_TO` is not Clerk-ready. A model that emits plausible prose-like facts but misses temp-id reference integrity, source spans, or Neo4j-safe property types is also not Clerk-ready.

## OpenRouter / GPT-4o smoke result

Command used:

```bash
python3 ~/.hermes/skills/benchmarks/clerk-benchmark/scripts/run_clerk_benchmark.py \
  --provider openrouter \
  --model openai/gpt-4o \
  --db "$HOME/.hermes/data/benchmarks/clerk/benchmark.db" \
  --obsidian-dir "$HOME/Obsidian/Main Vault/40-Operations/Hermes/Benchmarks/clerk-benchmark" \
  --temperature 0 \
  --max-tokens 2048 \
  --timeout 60 \
  --json-mode
```

Run: `clerk-benchmark-20260508T212453Z-1dcd8995`

Result:
- score: `0.821`
- pass: `3/8`
- avg latency: `3364 ms`
- tokens: `7515`

Interpretation:
GPT-4o with OpenRouter JSON mode was generally JSON-valid and property-safe, but still failed several graph-semantic checks: GovCon normalization, IBM dedupe, document/constraint modeling, and illegal/incorrect relationship semantics.

## Pitfall

OpenRouter `response_format: {"type":"json_object"}` enforces JSON syntax only. It does not enforce the full graph schema. Keep local validation as the source of truth.
