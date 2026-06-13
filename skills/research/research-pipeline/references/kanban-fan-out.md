# Kanban Fan-Out: Card Templates and Dispatch Patterns

## When to Fan Out

Fan out when a single topic area decomposes into multiple independent discovery/capture units. Don't fan out for a single well-defined topic with <10 sources — run it directly.

## Card Templates

### Discovery Card (junkyard-scout — Perplexity/Free-search combo)

```yaml
---
title: "Discovery: <sphere> — <topic>"
assignee: junkyard-scout
skills: [research-pipeline]
workspace_path: "<absolute path to output root>"
priority: 10
---
## Task

Perform first-pass discovery for **<sphere>: <topic>**.

**Strategic lens:** <one-sentence thesis or research question>

**Deliverables:**
1. List of 10-15 candidate public source URLs (reports, news, regulatory filings, analyst pieces)
2. List of 5-10 key entity names (companies, technologies, people, policies)
3. 3-5 search query vectors that would find deeper material

**Output format:** Bullet list. Keep/DROP labels on each candidate. No tool calls needed.

**Constraints:**
- PUBLIC sources only. No private strategy, vault content, or credentials.
- Your output is unverified candidates. The researcher profile will verify and capture.
- Do not attempt to write files or make changes.

Write your output as a comment on this card when done.
```

### Discovery Card (junkyard-scout — Junkyard combo, query generation only)

```yaml
---
title: "Query Gen: <sphere> — <topic>"
assignee: junkyard-scout
skills: [research-pipeline]
workspace_path: "<absolute path to output root>"
priority: 10
---
## Task

Generate search queries and entity seeds for **<sphere>: <topic>**.

**Strategic lens:** <one-sentence thesis or research question>

**Deliverables:**
1. 15 diverse search queries (mix of obvious, lateral, and adversarial angles)
2. 10 entity names likely relevant to this topic
3. 5 lateral concept areas to explore (domains that connect but aren't obvious)

**ANTI-HALLUCINATION RULES (mandatory):**
1. Only use information you are confident is real. If unsure whether a source, URL, entity, or fact exists, label it UNCERTAIN.
2. Do NOT fabricate URLs. If you cannot recall a specific URL, describe the source (e.g., "CSIS report on export controls, circa 2025") and let the researcher find the actual link.
3. Do NOT invent metrics, dates, or policy names. If unsure of a specific number or date, say "approximate" or "uncertain date".
4. When generating search queries, clearly separate queries you know will return results from exploratory/speculative queries.
5. Your output is UNVERIFIED CANDIDATES. Everything will be fact-checked by a trusted profile. It is better to say "I don't know" than to fabricate.

**Constraints:**
- You have NO web access. Generate queries and structure only — do not assert facts.
- Do NOT produce source summaries or claim specific findings.
- PUBLIC topic only. No private strategy or credentials.

Write your output as a comment on this card when done.
```

### Capture Card (researcher)

```yaml
---
title: "Capture & Entity Build: <sphere> — <topic>"
assignee: researcher
skills: [research-pipeline]
parents: ["<discovery-card-id>"]
workspace_path: "<absolute path to output root>"
priority: 8
---
## Task

Capture sources and build entity notes for **<sphere>: <topic>**.

**Parent discovery output:** (from discovery card — will be injected when this card becomes ready)

**Deliverables:**
1. Source notes in `Sources/` — one markdown file per captured source, following the Source Note schema
2. Entity notes in `Entities/` — one markdown file per key entity, following the Entity Note schema
3. `_brief.md` hub note with: findings summary, entity list, gaps, next legs
4. `_campaign_state.json` with: source count, entity count, stage = "captured"

**Constraints:**
- Deduplicate against existing entities in the output folder (if this is a re-run)
- Max 10 sources, max 8 entities — prioritize depth over breadth
- Each entity note should be at least `partial` status (not a bare stub)
- For PDF sources: extract text, write as source note, stage PDF if high-value

**OCR handling:**
- If a source is a scanned PDF or image, extract text using `pdftotext` or the OCR pipeline (see `references/ocr-pipeline.md`)
- Flag OCR-extracted content in source note frontmatter: `extraction_method: ocr`

Mark this card done when `_brief.md` exists and entity count > 0.
```

### Extraction Card (clerk)

```yaml
---
title: "Structured Extraction: <sphere> — <topic>"
assignee: clerk
skills: [research-pipeline]
parents: ["<capture-card-id>"]
workspace_path: "<absolute path to output root>"
priority: 6
---
## Task

Extract structured data from captured sources for **<sphere>: <topic>**.

**Input:** Read all `Sources/*.md` and `Entities/*.md` in the topic folder.

**Deliverables:**
1. `_extraction.json` — strict JSON following the Extraction JSON schema (see SKILL.md)
2. For each entity: type classification, confidence score, metrics (if any), relationship triples

**Output schema (write to `_extraction.json`):**
```json
{
  "topic": "<topic>",
  "entities": [
    {
      "name": "...",
      "type": "company|technology|person|concept",
      "classification_confidence": 0.0-1.0,
      "metrics": {},
      "relationships": [
        {"target": "...", "type": "supplies-to|competes-with|depends-on|controls-supply-of", "confidence": 0.0-1.0}
      ],
      "source_refs": ["path.md"]
    }
  ],
  "low_confidence_flags": []
}
```

**Constraints:**
- Strict JSON only. No prose in the output file.
- Flag anything below 0.7 confidence in `low_confidence_flags`.
- Do not infer relationships not supported by source text.
```

### Synthesis Card (analyst)

```yaml
---
title: "Synthesis & Report: <thesis>"
assignee: analyst
skills: [research-pipeline]
parents: ["<extraction-card-1>", "<extraction-card-2>", "<extraction-card-3>"]
workspace_path: "<absolute path to output root>"
priority: 4
---
## Task

Synthesize research across all spheres into a unified report for **<thesis>**.

**Input:** Read all `_extraction.json`, `_brief.md`, entity notes, and source notes across all sphere folders.

**Deliverables:**
1. `_report.md` — full synthesis report (see schema below)
2. `_deepening_queue.md` — prioritized list of entities/sources needing deeper work
3. Update each sphere's `_brief.md` gaps section with cross-sphere findings

**Report structure:**
- **Executive Summary (BLUF):** Bottom line up front.
- **Key Findings:** Tagged KNOWN vs INFERRED. Cite source notes.
- **Cross-Sphere Analysis:** How the spheres interact, fracture lines, dependencies.
- **Needle-Movers:** Ranked table of factors that could shift the landscape.
- **Constraints & Risks:** Geographic concentration, IP moats, capital intensity.
- **Strategic Implications:** Timing, allocation, trade architecture.
- **Open Questions:** Mapped from gaps across all spheres.
- **Confidence Assessment:** Overall confidence level with justification.

**Constraints:**
- Every claim must trace to a source note or be explicitly tagged as INFERRED.
- Resolve conflicts between sources explicitly — don't average them.
- The deepening queue should prioritize by impact × ease of resolution.
```

### Neo4j Writeback Card (optional, post-synthesis)

```yaml
---
title: "Neo4j KG Writeback: <topic>"
assignee: clerk
skills: [research-pipeline]
parents: ["<extraction-card-id>"]
workspace_path: "<absolute path to output root>"
priority: 5
---
## Task

Write structured extraction data to Neo4j knowledge graph.

**Input:** `_extraction.json` from the extraction stage.

**Deliverables:**
1. Execute Cypher CREATE/MERGE statements for all entities and relationships.
2. Set provenance labels per the KG contract.
3. Verify node creation with a count query.

**Neo4j connection:**
- URI: `$NEO4J_URI` (bolt) or `$NEO4J_URL` (HTTPS)
- Auth: `$NEO4J_USER` / `$NEO4J_PASSWORD`

**Cypher patterns:**
```cypher
// Entity creation
MERGE (o:Organization {name: $name})
SET o.type = $type, o.provenance = $provenance,
    o.source_topic = $topic, o.last_updated = $date

// Relationship creation
MATCH (a {name: $source}), (b {name: $target})
MERGE (a)-[r:supplies_to]->(b)
SET r.confidence = $confidence, r.source_topic = $topic
```

**Provenance values:**
- `spider-validated` — discovered via spider + dossier + frontier checkpoint
- `pipeline-extracted` — extracted via research-pipeline clerk stage
- `curated` — manually curated (do not use for pipeline-discovered entities)

**Constraints:**
- Use MERGE, not CREATE — avoid duplicate nodes.
- Never overwrite existing provenance with a lower-trust value.
- Flag any merge conflicts in the card comment.
```

## Dispatch Example: Balkanization Thesis (3 Spheres)

```python
# Create the campaign
output_root = f"{OBSIDIAN_VAULT}/30-Intake/Spiders/Balkanization"

# Phase 1: Discovery (parallel, no dependencies)
discovery_us = kanban_create(
    title="Discovery: US Sphere — Export Controls & AI Policy",
    assignee="junkyard-scout",
    body=discovery_template.format(sphere="US", topic="export-controls-ai-policy", ...),
    skills=["research-pipeline"],
    workspace_path=output_root,
    priority=10,
)

discovery_eu = kanban_create(...)  # EU sphere
discovery_cn = kanban_create(...)  # China sphere

# Phase 2: Capture (depends on discovery)
capture_us = kanban_create(
    title="Capture: US Sphere — Export Controls & AI Policy",
    assignee="researcher",
    parents=[discovery_us],
    ...
)

# Phase 3: Extraction (depends on capture)
extraction_us = kanban_create(
    title="Extraction: US Sphere",
    assignee="clerk",
    parents=[capture_us],
    ...
)

# Phase 4: Synthesis (depends on ALL extractions)
synthesis = kanban_create(
    title="Synthesis: AI & Quantum Balkanization",
    assignee="analyst",
    parents=[extraction_us, extraction_eu, extraction_cn],
    ...
)

# Phase 5: Neo4j writeback (optional, depends on extraction)
for ext_id in [extraction_us, extraction_eu, extraction_cn]:
    kanban_create(
        title=f"Neo4j Writeback: {sphere}",
        assignee="clerk",
        parents=[ext_id],
        ...
    )
```
