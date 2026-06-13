# Obsidian KOS Integration

The research pipeline produces artifacts that integrate with the Obsidian Knowledge OS (KOS). This reference defines the integration points, promotion gates, and cross-linking conventions.

## KOS Folder Structure

When `OUTPUT_ROOT` is set to the Obsidian vault's intake area:

```
$OBSIDIAN_VAULT/
├── 30-Intake/
│   └── Spiders/
│       └── <ParentTopic>/
│           └── <Topic>/
│               ├── _brief.md
│               ├── Entities/
│               └── Sources/
├── 20-Knowledge/          ← canonical, promoted only through gates
│   ├── Companies/
│   ├── Domains/
│   └── Themes/
│       └── Gray Rhinos/
│           └── scenarios/
├── ~/Bookshelf/           ← research corpus (PDFs, reports)
│   └── __Inbound/         ← staging for PageIndex pipeline
└── ~/Research/            ← alt path (symlinked from ~/Bookshelf)
```

## Spider → Knowledge Promotion Gate

Pipeline-produced entities in `30-Intake/Spiders/` are NOT canonical. They promote to `20-Knowledge/` only when ALL THREE are true:

1. **Source-backed:** Named in at least one PageIndex-enriched source (structured entity extraction OR raw OCR text — not just a landing page)
2. **Graph-backed:** Has a Neo4j node with appropriate provenance (`spider-validated`, `pipeline-extracted`, or `curated`)
3. **Substantive:** Carries one of: numeric metric, stated relationship, or risk flag with reasoning

Below the bar → stays in Spiders. Do not promote prematurely.

### Provenance Hierarchy

| Provenance | Meaning | Trust |
|-----------|---------|-------|
| `curated` | Manually curated via scout→clerk→analyst pipeline | Highest |
| `spider-validated` | Spider-discovered, dossier_minimum + frontier checkpoint | High |
| `pipeline-extracted` | Extracted via research-pipeline clerk stage | Medium |
| `unverified` | Discovery-only (junkyard-scout output) | Lowest — never write to KG |

## Frontmatter Conventions for KOS

### Spider entity notes (intake)

```yaml
---
spider_status: intake-not-canonical
source_layer: 30-Intake
recon_id: <parent>-<topic>-<date>
type: company|technology|person|concept
name: <Entity Name>
status: stub|partial|well-covered|dossier_minimum
chokepoint: yes|no|unknown
geography: <country/region>
role_in_value_chain: <description>
tags: [recon, <domain-tags>]
sources:
  - "Source title"
---
```

### Promoted knowledge notes (20-Knowledge)

```yaml
---
type: company|technology|concept
status: active
last_updated: YYYY-MM-DD
provenance: curated|spider-validated|pipeline-extracted
neo4j_node: true|false
tags: [<domain>, <industry>]
---
```

## Wikilink Conventions

- Use **basename links** (`[[Entity Name]]` or `[[Entity Name|Display Alias]]`) — not folder-relative paths.
- Folder-relative links like `[[Entities/Foo]]` break when notes are promoted or moved.
- After any batch move (spider → knowledge promotion), run link resolution to verify.

## Obsidian-Specific Extensions

When running on a Hermes installation with Obsidian integration:

1. **PageIndex pipeline:** PDFs staged in `~/Research/__Inbound/` → `process_inbound.py` → PageIndex enrichment → registry update
2. **Nightly intake-curator:** Automated triage of spider output → creates promotion candidates
3. **KOS promotion scripts:** `receipt_promote.py`, `clipping_to_receipt.py` for structured intake flow
4. **Dashboard integration:** Research topics surface in Obsidian dashboards via frontmatter tags

These are local extensions — the portable skill does not depend on them, but links to them when available.

## Feeding Gray Rhino Scenarios

When research feeds into Gray Rhino trading scenarios:

1. Entity notes should include a `chokepoint` field and `role_in_value_chain` description
2. Source notes should be tagged with relevant `scenario_id` from the Gray Rhinos wiki
3. The synthesis `_report.md` should include a "Trading Implications" section with tradable instruments
4. Cross-link the report to the relevant scenario page: `[[ai_quantum_balkanization]]`
5. After human review, update `tripwires.json` if execution thresholds need adjustment

See the `gray-rhino` local skill for the full tripwire/scenario integration contract.
