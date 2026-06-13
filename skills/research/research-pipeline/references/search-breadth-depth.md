# Search Breadth + Depth: Combo Layering & Spider Configuration

## The Two-Vector Model

Research campaigns need two orthogonal search strategies. Most failures come from using one vector for both jobs.

### Breadth (cast wide, find unknowns)

| Tool | What It Finds | Precision | Hallucination Risk |
|------|---------------|-----------|-------------------|
| `perplexity` (pplx-sonar) | Real URLs with live web search + citations | High | Low — sources are real |
| `free-search` (DDG) | Volume results, wider net | Medium | Low — sources are real |
| `junkyard` (free reasoner) | Search queries, aliases, lateral connections | N/A (generates queries, not answers) | **High on facts, low on queries** |
| `x_search` | Expert commentary, leaks, sentiment signals | Variable | Low — returns real posts |

### Depth (drill deep, verify, extract)

| Tool | What It Does | Precision | Trust Level |
|------|-------------|-----------|-------------|
| `web_search` / `web_extract` (Hermes native) | Targeted capture, high-signal extraction | High | Trusted |
| `x_search` (in researcher hands) | Expert timeline reconstruction, primary-source discovery | High | Trusted |
| Researcher profile (KOS-aware) | Can see existing notes, avoid duplication, understand provenance | High | Trusted |
| Analyst profile | Cross-source synthesis, conflict resolution | High | Trusted |

## Combo → Role Mapping

### OmniRoute Combos

| Combo | Model | Role in Pipeline | Web Access | Anti-Hallucination |
|-------|-------|-----------------|------------|-------------------|
| `perplexity` | `perplexity-web/pplx-sonar` | Stage 1: Live discovery (real URLs + citations) | ✅ Perplexity search | Built-in (cited sources) |
| `free-search` | `duckduckgo-web/*` | Stage 1: Volume discovery (breadth casting) | ✅ DuckDuckGo | Medium (DDG-sourced) |
| `junkyard` | Free reasoner (deepseek/etc.) | Stage 1: Query generation + Stage 2: Bulk filtering | ❌ None | **Requires guardrails** |

### Trusted Profiles (non-OmniRoute)

| Profile | Role | Combo | KOS Context |
|---------|------|-------|-------------|
| `clerk` | Stage 2: Triage/filter, Stage 4: Extraction | Structured combo | ✅ |
| `researcher` | Stage 3: Depth capture | Trusted combo | ✅ |
| `analyst` | Stage 5: Synthesis | High-context combo | ✅ |
| `frontier` | Stage 6: Checkpoint | Top-tier | ✅ |

## Spider Configuration Matrix

Different campaign types need different combos of breadth + depth.

| Campaign Type | Breadth Vector | Depth Vector | When to Use |
|--------------|---------------|-------------|-------------|
| **Broad discovery** | Perplexity + Free-search + Junkyard queries | Researcher (light) | New domain, unknown landscape |
| **Focused deepening** | Junkyard queries only (for gaps) | Researcher (heavy) + x_search | Deepening existing entities to dossier_minimum |
| **Thesis validation** | Perplexity (targeted) | Researcher + Analyst | Testing a specific hypothesis against sources |
| **Backfill** | Free-search (volume) + Junkyard (aliases) | Researcher (batch) | Filling known gaps in entity coverage |
| **Red-team / adversarial** | Junkyard (red-team mode) | Analyst (cross-examination) | Stress-testing a thesis for weaknesses |

## Junkyard Anti-Hallucination Protocol

The junkyard combo has NO web access. It generates text from training data. This makes it excellent at:
- ✅ Generating diverse search queries
- ✅ Expanding aliases and synonyms
- ✅ Identifying lateral connections between concepts
- ✅ Producing red-team objections and skeptical counterarguments
- ✅ KEEP/DROP labeling on candidate lists

And dangerous for:
- ❌ Fabricating URLs, paper titles, or author names
- ❌ Inventing metrics, dates, or policy numbers
- ❌ Hallucinating entity relationships

### Mandatory Guardrails for Every Junkyard Prompt

```
ANTI-HALLUCINATION RULES (mandatory):
1. Only use information you are confident is real. If unsure whether a source, URL, entity, or fact exists, label it UNCERTAIN.
2. Do NOT fabricate URLs. If you cannot recall a specific URL, describe the source (e.g., "CSIS report on export controls, circa 2025") and let the researcher find the actual link.
3. Do NOT invent metrics, dates, or policy names. If unsure of a specific number or date, say "approximate" or "uncertain date".
4. When generating search queries, clearly separate queries you know will return results from exploratory/speculative queries.
5. Your output is UNVERIFIED CANDIDATES. Everything will be fact-checked by a trusted profile. It is better to say "I don't know" than to fabricate.
```

### Safe vs Unsafe Junkyard Tasks

| Safe (low hallucination risk) | Unsafe (high hallucination risk) |
|-------------------------------|----------------------------------|
| "Generate 10 search queries about X" | "List the top 10 sources about X" |
| "What are alternative names for X?" | "What is X's revenue?" |
| "Generate red-team objections to thesis Y" | "Summarize the key findings of report Z" |
| "Label these candidates KEEP or DROP" | "Extract entities from this text" |
| "What domains relate to X?" | "What does source Y say about X?" |

**Rule:** Junkyard generates queries and structure. Perplexity/free-search find real sources. Researcher extracts real data. Never let junkyard assert facts.

## Breadth Discovery Dispatch Patterns

### Pattern 1: Full Breadth (three-combo sweep)

Dispatch three parallel discovery cards:

1. **Perplexity card:** "Find real, citable sources about [topic]. Return URLs with brief descriptions."
2. **Free-search card:** "Find volume sources about [topic]. Cast wide — news, blogs, forums, filings."
3. **Junkyard card:** "Generate 15 diverse search queries about [topic]. Include aliases, lateral concepts, and adversarial angles. Do NOT fabricate URLs or facts — only generate queries."

### Pattern 2: Targeted Breadth (perplexity only)

For focused campaigns where precision matters more than volume:

1. **Perplexity card:** "Find primary sources about [specific entity/policy]. Prioritize: government filings, regulatory documents, analyst reports, court documents."

### Pattern 3: Junkyard-Assisted Breadth (query-first)

For unfamiliar domains where you don't know the search space:

1. **Junkyard card:** "Generate 15 search queries + 10 entity names + 5 lateral concept areas for [topic]. Queries only, no fabricated facts."
2. **Perplexity card:** "Search for: [queries from junkyard]. Return real URLs."
3. **Free-search card:** "Search for: [queries from junkyard]. Volume sweep."

## x_search Integration

X/Twitter search is valuable for:
- **Expert signals:** Domain experts posting primary-source links or analysis
- **Leak detection:** Pre-publication rumors, teardown reveals, insider commentary
- **Sentiment tracking:** Market perception of events
- **Timeline reconstruction:** Real-time event chains

### When to include x_search

| Campaign Type | x_search Role |
|--------------|---------------|
| Broad discovery | Skip (too noisy for initial scan) |
| Focused deepening | ✅ Expert commentary on specific entity |
| Thesis validation | ✅ Contrarian views, counter-evidence |
| Red-team | ✅ Skeptical takes, debunking threads |

### x_search dispatch pattern

```python
# In researcher capture card, include:
"Use x_search to find expert commentary on [entity/topic]. Focus on:
- Domain experts (not general commentators)
- Posts with primary-source links
- Contrarian or skeptical views
- Timeline signals (when did people first notice X?)"
```

## Campaign-Level Configuration

When dispatching a full campaign, configure at the Kanban level:

```yaml
campaign_config:
  topic: "AI & Quantum Balkanization"
  breadth_mode: full  # full | targeted | junkyard_assisted
  depth_mode: heavy   # light | standard | heavy
  include_x_search: true
  spheres:
    - name: "US"
      focus: "Export controls, CHIPS Act, PQC"
    - name: "EU"
      focus: "ASML, AI Act, sovereignty"
    - name: "China"
      focus: "SMIC, rare earths, quantum"
  junkyard_guardrails: true  # always true
```
