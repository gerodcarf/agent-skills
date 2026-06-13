# Report templates for Kanban fan-out cards.
# Copy and fill in <placeholders>.

discovery_card = """\
## Task

Perform first-pass discovery for **<sphere>: <topic>**.

**Strategic lens:** <one-sentence thesis or research question>

**Deliverables:**
1. List of 10-15 candidate public source URLs (reports, news, regulatory filings, analyst pieces)
2. List of 5-10 key entity names (companies, technologies, people, policies)
3. 3-5 search query vectors that would find deeper material

**Output format:** Bullet list. KEEP/DROP labels on each candidate. No tool calls needed.

**Constraints:**
- PUBLIC sources only. No private strategy, vault content, or credentials.
- Your output is unverified candidates. The researcher profile will verify and capture.
- Do not attempt to write files or make changes.

Write your output as a comment on this card when done.
"""

junkyard_query_card = """\
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
"""

capture_card = """\
## Task

Capture sources and build entity notes for **<sphere>: <topic>**.

**Parent discovery output:** See parent card comments.

**Deliverables:**
1. Source notes in `Sources/` (one markdown file per captured source)
2. Entity notes in `Entities/` (one markdown file per key entity)
3. `_brief.md` hub note with: findings, entity list, gaps, next legs
4. `_campaign_state.json` with source/entity counts, stage = "captured"

**Constraints:**
- Deduplicate against existing entities in the output folder
- Max 10 sources, max 8 entities — depth over breadth
- Each entity note: at least `partial` status
- For PDF sources: `pdftotext` for text-rich, OCR for scanned (see references/ocr-pipeline.md)
- Flag OCR-extracted content: `extraction_method: ocr`
- **Use x_search** to find expert commentary, contrarian views, and timeline signals for key entities

Mark done when `_brief.md` exists and entity count > 0.
"""

extraction_card = """\
## Task

Extract structured data from captured sources for **<sphere>: <topic>**.

**Input:** Read all `Sources/*.md` and `Entities/*.md`.

**Deliverable:** `_extraction.json` — strict JSON:

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
- Strict JSON only. No prose in output file.
- Flag anything below 0.7 confidence.
- Do not infer relationships not in source text.
"""

synthesis_card = """\
## Task

Synthesize research across all spheres into a unified report for **<thesis>**.

**Input:** Read all `_extraction.json`, `_brief.md`, entity notes, source notes.

**Deliverables:**
1. `_report.md` — synthesis report
2. `_deepening_queue.md` — prioritized deepening targets

**Report structure:**
- Executive Summary (BLUF)
- Key Findings (tagged KNOWN vs INFERRED, with source citations)
- Cross-Sphere Analysis (fracture lines, dependencies, interactions)
- Needle-Movers (ranked factors that could shift the landscape)
- Constraints & Risks (geographic concentration, IP moats, capital intensity)
- Strategic Implications (timing, allocation, trade architecture)
- Trading Implications (tradable instruments, winners/losers per fracture)
- Open Questions (mapped from gaps across all spheres)
- Confidence Assessment

**Constraints:**
- Every claim traces to a source note or is tagged INFERRED.
- Resolve conflicts between sources explicitly.
- Deepening queue prioritized by impact × ease of resolution.
"""

neo4j_card = """\
## Task

Write structured extraction data to Neo4j knowledge graph.

**Input:** `_extraction.json` from the extraction stage.

**Deliverables:**
1. Execute Cypher MERGE statements for all entities and relationships.
2. Set provenance = "pipeline-extracted".
3. Never overwrite existing higher-trust provenance (curated, spider-validated).
4. Verify with count query.

**Connection:** `$NEO4J_URI` (bolt) or `$NEO4J_URL` (HTTPS), auth via `$NEO4J_USER` / `$NEO4J_PASSWORD`.

See `references/neo4j-writeback.md` for Cypher patterns, provenance rules, and validation queries.
"""
