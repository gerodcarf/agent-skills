---
name: research-pipeline
description: "Portable multi-agent research pipeline: junkyard-scout discovery → researcher capture → clerk extraction → analyst synthesis. Uses Kanban fan-out and specialist Hermes profiles. Machine-agnostic — all paths via env vars."
version: 1.0.0
author: gerod
license: MIT
metadata:
  hermes:
    tags: [research, pipeline, kanban, multi-agent, discovery, portable]
    related_skills: [research-recon, gray-rhino, kanban-orchestrator, kanban-worker]
trigger:
  - running a structured research campaign across multiple agents
  - backfilling knowledge across a thesis or domain
  - needing junkyard-scout for cheap discovery before committing expensive models
  - fan-out research across Kanban specialist profiles
---

# Research Pipeline

A portable, multi-agent research pipeline that orchestrates specialist Hermes profiles through a structured discovery → capture → extraction → synthesis workflow. Designed to be machine-agnostic — no hardcoded paths, all configuration via environment variables.

## Core Principle

Research is a pipeline, not a monologue. Different model tiers excel at different stages. This skill defines the contracts, output schemas, and Kanban fan-out patterns to coordinate them efficiently.

## Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        RESEARCH PIPELINE v2                              │
│                   Breadth + Depth Vector Architecture                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  STAGE 1: BREADTH DISCOVERY (junkyard-scout, parallel)                  │
│  ├─ Perplexity combo: live web + citations (real URLs)                  │
│  ├─ Free-search combo: DuckDuckGo volume (real URLs)                    │
│  ├─ Junkyard combo: query expansion, aliases, red-team (no web)         │
│  ├─ x_search: expert sentiment, leaks, timeline signals                 │
│  └─ Output: candidate source URLs + entity seeds + search vectors       │
│     ↓                                                                   │
│  STAGE 2: FILTER & PRIORITIZE (clerk)                                   │
│  ├─ Deduplicate against existing corpus                                 │
│  ├─ Score by signal (primary > secondary > tertiary)                    │
│  ├─ Flag high-value entities for deepening                              │
│  └─ Output: prioritized capture queue                                   │
│     ↓                                                                   │
│  STAGE 3: DEPTH CAPTURE (researcher)                                    │
│  ├─ web_search / web_extract on prioritized targets                     │
│  ├─ x_search for expert commentary                                      │
│  ├─ OCR for scanned/image sources (pdftotext → Tesseract → vision)     │
│  ├─ Create source notes + entity dossiers                               │
│  └─ Output: _brief.md, Sources/, Entities/                              │
│     ↓                                                                   │
│  STAGE 4: EXTRACTION (clerk)                                            │
│  ├─ Structured JSON: entity classification, relationships, metrics     │
│  └─ Output: _extraction.json                                            │
│     ↓                                                                   │
│  STAGE 5: SYNTHESIS (analyst)                                           │
│  ├─ Cross-source synthesis, gap analysis, report                        │
│  └─ Output: _report.md, _deepening_queue.md                             │
│     ↓                                                                   │
│  STAGE 6: CHECKPOINT (frontier, optional)                               │
│  ├─ Adversarial review, branch validation                               │
│  └─ Output: recommendation, confidence, rationale                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### The Two-Vector Model

Research needs two orthogonal search strategies:

**Breadth** (cast wide, find unknowns):
- Perplexity (`pplx-sonar`): live web search with citations — real URLs, high precision
- Free-search (`duckduckgo-web/*`): DuckDuckGo volume — wider net, lower precision
- Junkyard (free reasoner): query generation, alias expansion, red-team — NO web access, prone to hallucination on facts but excellent at generating search queries
- x_search: real-time expert commentary, leaks, sentiment

**Depth** (drill deep, verify, extract):
- web_search / web_extract: targeted, high-signal capture
- x_search: expert timeline reconstruction
- Trusted reasoners with KOS context (researcher, analyst): can see existing notes, avoid duplication, understand provenance

**Key rule:** `junkyard` has NO web access. Use it for query/idea generation (where hallucination risk is low — you're generating candidates, not asserting facts). Use `perplexity`/`free-search` for finding real sources. See `references/search-breadth-depth.md` for full architecture.

See `references/search-breadth-depth.md` for OmniRoute combo layering, spider configuration matrix, and campaign dispatch patterns.

## Profile Pipeline

| Stage | Profile | OmniRoute Combo | Trust | Web? | Cost |
|-------|---------|----------------|-------|------|------|
| Breadth: Live discovery | `junkyard-scout` | `perplexity` (pplx-sonar) | Untrusted | ✅ Perplexity | $$ |
| Breadth: Volume discovery | `junkyard-scout` | `free-search` (DDG) | Untrusted | ✅ DuckDuckGo | $0 |
| Breadth: Query generation | `junkyard-scout` | `junkyard` (reasoner) | Untrusted | ❌ | $0 |
| Filter & prioritize | `clerk` | (structured combo) | Trusted | — | $ |
| Depth: Capture | `researcher` | (trusted combo) | Trusted | ✅ web_search | $$ |
| Extraction | `clerk` | (structured combo) | Trusted | — | $ |
| Synthesis | `analyst` | (high-context combo) | Trusted | — | $$$ |
| Checkpoint | `frontier` | (top-tier) | Trusted | — | $$$$ |

### Stage Contracts

#### 1. Discovery (junkyard-scout)

**Input:** Topic, optional seed URL/text, strategic lens.
**Output:** Candidate source list (public URLs only), entity seed names, search query vectors.
**Constraints:**
- Public URLs/snippets only — never vault content, strategy, PII, secrets.
- Output is unverified candidates — always escalated downstream.
- No tool calling or strict JSON — bullets, prose, KEEP/DROP labels.
- No side-effecting work: no writes, no code edits, no trading.

**When to use:** First-pass scan of a new domain, seed expansion, brainstorming search vectors. Cheap enough to run wide.

**When to skip:** Small, well-defined topics with <10 known sources. For follow-up deepening passes on existing entities.

#### 2. Capture (researcher)

**Input:** Candidate sources from discovery, or direct topic assignment.
**Output:** Source notes (markdown), entity notes (with YAML frontmatter), `_brief.md` hub note.
**Responsibilities:**
- Deduplicate against existing corpus.
- Capture source content as structured markdown notes.
- Create/update entity notes with provenance.
- Write the hub `_brief.md` with findings, gaps, and next legs.

#### 3. Extraction (clerk)

**Input:** Captured source notes, entity notes.
**Output:** Strict JSON: entity classification, relationship triples, metric extraction.
**Responsibilities:**
- Extract structured data from messy markdown sources.
- Classify entities (company, technology, person, concept).
- Generate Neo4j-ready relationship triples.
- Flag low-confidence extractions.

#### 4. Synthesis (analyst)

**Input:** All captured material, extraction JSON, brief.
**Output:** `_report.md` with BLUF, key findings (KNOWN vs INFERRED), needle-movers, constraints, strategic implications, open questions.
**Responsibilities:**
- Cross-source synthesis and conflict resolution.
- Gap analysis against thesis/strategic lens.
- Confidence tagging on all claims.
- Deepening queue generation.

#### 5. Checkpoint (frontier)

**Input:** Compact decision packet (one question, evidence table, candidate options, cost-of-wrong).
**Output:** Recommendation, confidence level, rationale, stop/continue verdict.
**Triggered by:** High-stakes branch decisions, thesis conflicts, investment implications, or when the runner is not a frontier model.

## Kanban Fan-Out Pattern

For large campaigns (multiple topics, domain backfills), decompose into Kanban cards rather than running the entire pipeline in one session.

### Fan-out structure

```
Orchestrator creates:
│
├── Card 1: Discovery — Sphere A (junkyard-scout)
├── Card 2: Discovery — Sphere B (junkyard-scout)
├── Card 3: Discovery — Sphere C (junkyard-scout)
│      (parallel, each runs independently)
│
├── Card 4: Capture & Entity Build — Sphere A (researcher)
│      parents: [Card 1]
├── Card 5: Capture & Entity Build — Sphere B (researcher)
│      parents: [Card 2]
├── Card 6: Capture & Entity Build — Sphere C (researcher)
│      parents: [Card 3]
│
├── Card 7: Structured Extraction — All Spheres (clerk)
│      parents: [Card 4, Card 5, Card 6]
│
└── Card 8: Synthesis & Report (analyst)
       parents: [Card 7]
```

### Card-writing rules

1. **One card = one verification gate.** If acceptance criteria require both crawling and polished synthesis, split.
2. **Name the profile in the assignee.** Each card targets one specialist profile.
3. **Set parents for dependencies.** Capture cards depend on their discovery card. Synthesis depends on all capture cards.
4. **Budget the iteration.** Discovery cards: small `--max-sources` (6-10). Capture cards: bounded entity count (top N). Synthesis: read-only from existing artifacts.
5. **Include the output path.** Every card must state where artifacts go (see Output Location).
6. **Attach skills.** Pass `skills: ["research-pipeline"]` on cards that need the pipeline protocol.

See `references/kanban-fan-out.md` for detailed card templates and dispatch examples.

## Output Location

All artifacts are env-var configured — no hardcoded paths.

| Variable | Default | Purpose |
|----------|---------|---------|
| `OUTPUT_ROOT` | `.` (current dir) | Root for all research output |
| `OBSIDIAN_VAULT` | `$HOME/Obsidian/main-vault` | Obsidian vault root (if using Obsidian) |
| `RESEARCH_ROOT` | `$HOME/Research` | Research corpus root for PDFs |

### Standard output structure

```
$OUTPUT_ROOT/<parent>/<topic>/
├── _brief.md                    ← Hub note (researcher)
├── _report.md                   ← Synthesis report (analyst)
├── _deepening_queue.md          ← Next legs (analyst)
├── _campaign_state.json         ← Machine-readable state (optional)
├── Entities/
│   ├── Company Name.md
│   ├── Technology Name.md
│   └── Person Name.md
└── Sources/
    ├── Author — Title.md
    └── Source — Title.md
```

For Obsidian-integrated use, set `OUTPUT_ROOT=$OBSIDIAN_VAULT/30-Intake/Spiders`.

## Output Schemas

### Hub Note (`_brief.md`)

```yaml
---
recon_id: <parent>-<topic>-<date>
topic: <Topic Display Name>
parent: <Parent Topic>
seed: <optional seed URL>
status: active
last_run: YYYY-MM-DD
tags: [recon, <domain-tags>]
entities: [Entity1, Entity2, ...]
gaps:
  - "Gap description 1"
  - "Gap description 2"
---
```

### Entity Note

```yaml
---
recon_id: <parent>-<topic>-<date>
type: company|technology|person|concept
name: <Entity Name>
tags: [recon, <domain-tags>]
status: stub|partial|well-covered|dossier_minimum
sources:
  - "Source title or URL"
chokepoint: yes|no|unknown
geography: <country/region>
role_in_value_chain: <description>
---
```

### Source Note

```yaml
---
recon_id: <parent>-<topic>-<date>
type: article|paper|thread|report|filing
source_url: https://...
date: YYYY-MM-DD
tags: [recon, <domain-tags>]
ingestion_status: captured|pdf_staged|enriched
pdf_path: <optional local path>
---
```

### Extraction JSON (clerk output)

```json
{
  "topic": "<topic>",
  "entities": [
    {
      "name": "Entity Name",
      "type": "company",
      "classification_confidence": 0.95,
      "metrics": {"metric_name": "value"},
      "relationships": [
        {"target": "Other Entity", "type": "supplies-to", "confidence": 0.8}
      ],
      "source_refs": ["source_note_path.md"]
    }
  ],
  "low_confidence_flags": []
}
```

See `references/output-schema.md` for full schema details and validation rules.

## Running the Pipeline

### Mode 1: Full Pipeline via Kanban (recommended for large campaigns)

```python
# Orchestrator creates discovery cards per topic/sphere
kanban_create(
    title="Discovery: <sphere> — <topic>",
    assignee="junkyard-scout",
    body="...",
    skills=["research-pipeline"],
    workspace_path="/path/to/output/root"
)
```

The dispatcher picks up cards, spawns workers, and the pipeline flows through dependency gates.

See `references/kanban-fan-out.md` for card templates.

### Mode 2: Direct Pipeline via delegate_task (for single topics)

```python
# Discovery (cheap, wide)
delegate_task(
    goal="Discover sources for <topic>. Return candidate URLs and entity seeds.",
    toolsets=["web"],
    context="Strategic lens: <thesis>. Output: bullet list of URLs + entity names."
)

# Capture (structured)
delegate_task(
    goal="Capture sources and create entity notes for <topic>.",
    toolsets=["web", "file"],
    context="Sources: <list from discovery>. Output to: <path>. Follow research-pipeline output schemas."
)

# Synthesis (high-context)
delegate_task(
    goal="Synthesize research findings into a report.",
    toolsets=["file"],
    context="Read all source/entity notes at <path>. Output: _report.md with BLUF, findings, gaps."
)
```

### Mode 3: Script-Led (for automated/repeated runs)

```bash
# Discovery + capture in one pass
python3 scripts/recon.py \
  --topic "Topic" \
  --parent "Parent" \
  --output-root "$OUTPUT_ROOT" \
  --max-sources 10

# Report generation
python3 scripts/report.py \
  --topic "topic-slug" \
  --parent "parent" \
  --output-root "$OUTPUT_ROOT"
```

Scripts use `web_search`/`web_extract` with DuckDuckGo fallback. All paths configurable via env vars.

## Integration with Local Skills

This portable skill defines the pipeline contract. Local installations may extend it:

| Extension | What it adds | When to load |
|-----------|-------------|-------------|
| `research-recon` (local) | Campaign mode, frontier checkpoints, depth-first supply-chain spidering, PDF handling, Firecrawl integration, Obsidian-specific paths | When running on the Hermes installation with full tool access |
| `gray-rhino` (local) | Gray Rhino scenario integration, tripwire hooks, trading proxy mapping | When research feeds into Gray Rhino scenarios |

**Load order:** Load `research-pipeline` (portable contract) first, then `research-recon` (local extensions) if available. The portable skill defines structure; the local skill adds machine-specific tooling and battle-tested patterns.

## Obsidian KOS Integration

When `OUTPUT_ROOT` points inside an Obsidian vault, the pipeline produces KOS-compatible artifacts:

- **Intake layer** (`30-Intake/Spiders/`): Pipeline output is intake-not-canonical by default
- **Promotion gate**: Entities promote to `20-Knowledge/` only when source-backed + graph-backed + substantive
- **Frontmatter**: Spider notes carry `spider_status: intake-not-canonical`, `source_layer: 30-Intake`
- **Wikilinks**: Use basename links (`[[Entity Name]]`), not folder-relative paths
- **PageIndex**: PDFs stage in `~/Research/__Inbound/` → `process_inbound.py` → enrichment → registry
- **Nightly curator**: Automated triage of spider output creates promotion candidates

See `references/obsidian-kos-integration.md` for promotion gates, provenance hierarchy, frontmatter schemas, and Gray Rhino scenario integration.

## Neo4j Knowledge Graph Writeback

The clerk extraction stage produces `_extraction.json` which feeds directly into Neo4j:

- **Connection:** `$NEO4J_URI` (bolt) or `$NEO4J_URL` (HTTPS), auth via `$NEO4J_USER` / `$NEO4J_PASSWORD`
- **Provenance:** Pipeline entities get `provenance: "pipeline-extracted"`. Never overwrite higher-trust provenance (curated, spider-validated).
- **Patterns:** MERGE for nodes/relationships (never CREATE — avoid duplicates). Attach metrics as node properties or separate `:Metric` nodes.
- **Validation:** Post-writeback count queries verify node creation and check for orphan relationships.
- **Conflict handling:** Don't overwrite — flag disputes with `in_dispute: true` and dual values.
- **PageIndex synergy:** KG is enriched by PageIndex pipeline for PDF-backed sources with `provenance: "curated"`.

See `references/neo4j-writeback.md` for full Cypher patterns, provenance rules, validation queries, and conflict handling.

## OCR Pipeline

When sources are scanned PDFs, images, or chart-heavy documents:

| Source Type | Method | When |
|-------------|--------|------|
| Text-rich PDF (<50pp) | `pdftotext` | Default — fastest |
| Scanned/image PDF | Tesseract OCR | When `pdftotext` returns <50 chars |
| Chart-heavy PDF | Vision model OCR | When charts contain critical data |
| Batch of 10+ PDFs | PageIndex pipeline | Batch processing at scale |

Source notes flag extraction method in frontmatter: `extraction_method: pdftotext|ocr|vision|web_extract`, `ocr_confidence: high|medium|low`.

See `references/ocr-pipeline.md` for commands, integration with PageIndex, and pitfalls.

## Depth-First Principle

For supply-chain and investment research, optimize for **depth over breadth**. A few well-documented chokepoint entities are worth more than dozens of shallow stubs.

```
discover candidates → score/prioritize → deepen top candidates → map relationships → branch only from validated chokepoints
```

Before branching to a new subtopic, P0/P1 entities in the current layer should be either:
- upgraded to `dossier_minimum` (bottom-line, products, customers, geography, dependencies, chokepoint assessment, citations), or
- explicitly rejected/deprioritized with evidence.

## Stop Conditions

A campaign stops because:
1. **Budget exhausted** — iteration limit, token budget, or time box reached. Write state and hand off.
2. **Evidence frontier reached** — no new sources found after N queries. The topic is saturated.
3. **Human gate** — high-stakes decision requires human judgment (investment implication, thesis conflict).
4. **Stop signal from user.**

Never stop just because stage 1 (discovery) completed. The campaign runs through capture → extraction → synthesis → checkpoint unless a stop condition triggers.

## Pitfalls

- **web_search rate limiting:** After ~30-45 calls in one session, `web_search` may return empty results silently. Front-load discovery calls early, then pivot to extraction/deepening.
- **web_extract batch size:** Max 2 URLs per `web_extract` call. Larger batches timeout.
- **junkyard-scout trust boundary:** Never send private content to junkyard-scout. Its outputs are always unverified candidates.
- **Subagent timeouts for web research:** Direct orchestrator `web_search` + `web_extract` is 3-5x faster than delegating entity enrichment to subagents. Use subagents for synthesis, not for web crawling.
- **Entity extraction noise:** Only extract entities from clean seed text, not from raw web page content.
- **Campaign state drift:** Update `_campaign_state.json`, worklog, and queue files after every batch. Scripts that write files but don't update state create silent divergence.

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OUTPUT_ROOT` | No | `.` | Root directory for all research output |
| `OBSIDIAN_VAULT` | No | `$HOME/Obsidian/main-vault` | Obsidian vault root |
| `RESEARCH_ROOT` | No | `$HOME/Research` | Research corpus for PDFs |
| `OPENROUTER_API_KEY` | No | — | LLM key for report synthesis |
| `ARXIV_SEARCH_SCRIPT` | No | auto-discover | Path to arxiv search script |

## Dependencies

- Python 3.9+ (scripts use `typing.Optional` not pipe unions)
- `web_search` / `web_extract` (Hermes built-ins, optional — DuckDuckGo fallback)
- Hermes Kanban system (for fan-out mode)
- Specialist profiles: junkyard-scout, researcher, clerk, analyst (for multi-agent mode)

All dependencies are optional — the skill works standalone with DuckDuckGo fallback, and works fully integrated with the Hermes profile/Kanban system when available.
