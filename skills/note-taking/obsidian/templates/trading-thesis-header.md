---
title: "Trading Thesis Header Template"
type: template
status: active
---

---
title: "..."
type: trading-thesis
status: draft
created: YYYY-MM-DD
last_reviewed: YYYY-MM-DD
themes:
  - "20-Knowledge/Themes/<theme-slug>"
horizon: structural|sliding|catalyst
lifecycle: harvested_reloading|initiation|...
max_allocation_pct: N
time_horizon: "..."
confidence: low|medium|medium-high|high
supporting_evidence:
  themes:
    - "20-Knowledge/Themes/<theme-slug>"
  companies:
    - "20-Knowledge/Domains/Semiconductors/SMIC.md"
    - "20-Knowledge/Domains/Semiconductors/ASML.md"
  clippings:
    - "KOS/..."
spider_artifacts:
  - "..."
---

# <Thesis Body Starts Here>

> Insert full thesis body after the YAML frontmatter block.
> Preserve all existing content exactly; this header is the only change when upgrading from legacy format.

## Notes for agents (remove before publishing)
- Infer title from existing H1.
- Set created from existing date metadata or file mtime.
- Set last_reviewed = today on each update pass.
- Map themes by topic (agentic AI → agentic-consumability; semiconductor/HBM/China → china-ai-supply-chain; defense/space/geopolitics → defense-space-geopolitics; drone supply chain → drone-supply-chain; cybersecurity M&A → cybersecurity-consolidation).
- If theme unclear, use themes: [] and add evidence_gaps: ["theme_unassigned"].
- Populate supporting_evidence with relevant KOS paths; use wikilinks in body, plain paths inside YAML for programmatic resolution.
- Default confidence to low if missing.
- Default max_allocation_pct to 5 if unknown.
