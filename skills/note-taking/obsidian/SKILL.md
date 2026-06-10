---
name: obsidian
description: Manage Obsidian notes via obsidian-cli and raw filesystem fallback. Create, search, read, move, update, and bulk-edit notes in the Main Vault.
tags: [obsidian, notes, kanban, vault]
pinned: true
---

# Obsidian

**Vault:** `Main Vault`
**Vault root:** `~/Obsidian/main-vault/` (canonical symlink; lowercase/no space to avoid script breakage)
**Legacy compatibility symlink:** `~/Obsidian/Main Vault` → `~/Obsidian/main-vault`
**Hermes workspace:** `~/Obsidian/main-vault/Hermes/`
**CLI binary:** `/opt/homebrew/bin/obsidian-cli`

Always pass `-v "Main Vault"` to target the correct vault.

## Executable Automation Boundary

Do not make the Obsidian vault the canonical home for executable automation. Python/shell scripts that implement reusable workflows belong in a Hermes skill `scripts/` directory (or a project repo), while the vault should hold durable Markdown/YAML knowledge: runbooks, policies, manifests, audit records, sample outputs, and links to the executable. If reviewing or refactoring vault-resident scripts, move/rewrite the canonical executable into the appropriate skill `scripts/` folder and leave only documentation/manifests in Obsidian.

## Hermes Audit Records

Canonical, human-reviewable Hermes security/review audit reports belong in:

`~/Obsidian/main-vault/40-Operations/Hermes/Audits/`

Use human-readable filenames, e.g. `V2 Cerberus Security Audit - 2026-06-08.md`. Do not keep duplicate durable audit copies under `~/.hermes/audits/`; treat that location as scratch/legacy only. Before deleting a duplicate, verify the Obsidian copy exists and is byte-identical (size/hash) to the scratch/source copy.

Reviewer/red-team profiles may write final Markdown audit artifacts directly to this folder only when the task explicitly asks for a canonical, secret-safe audit/review artifact. Audit records must never contain raw secrets, tokens, credentials, long bearer strings, or unredacted private values; use redaction markers and run a secret-safety heuristic before considering the record final.

See `references/hermes-audit-canonicalization.md` for the session-derived checklist.

## Clipping / Note Recall Discipline

When a user asks to read a specific clipping or note by path/title, first verify the file exists with exact and broadened vault searches before summarizing. If the exact note is not found, say that directly and distinguish any adjacent web/index findings from the requested clipping; do not present an inferred paper/source as if it were the missing vault note. For clippings, search likely intake locations (`Clippings/`, `30-Intake/`, and the vault root) using exact title fragments and distinctive subtitle terms.

## Bookshelf

The reference collection at `~/Bookshelf/` (formerly `~/Research/`) holds 3rd-party material — reports, filings, PDFs. Inbound items go in `~/Bookshelf/__Inbound/` with a PDF + `.source.yaml` sidecar.

**Sidecar YAML format is flat YAML (`schema_version: bookshelf_source.v1`), NOT Obsidian-style `---` frontmatter.** See [`references/bookshelf-intake-format.md`](references/bookshelf-intake-format.md) for the full field set and pitfalls.

## Operations Architecture Runbooks

When creating or updating living architecture/runbook notes for local operational systems under `40-Operations/`, see [`references/operations-architecture-docs.md`](references/operations-architecture-docs.md) for details on target locations, pre-write inspection, document structure, and the quality bar.

## ⚠️ Path Gotchas

The vault path has a **space**. This breaks `read_file` and can cause `write_file` to report success without actually persisting.

**Always verify writes:**
```bash
cat "~/Obsidian/main-vault/Hermes/Tasks/Some File.md"
```

Prefer full expanded paths (no `~`) when using the `write_file` tool. Use `terminal` with `cat >` for critical writes.

## Planning Tables and Linked Markdown Artifacts

For large operating-model tables, routing matrices, stage maps, or other planning artifacts, prefer creating/updating a linked Markdown note in Obsidian over dumping a wide ASCII table into chat. Chat can summarize the change and provide the vault path/link; the table itself should live in a durable note that can be edited, linked, and reused. This is especially important for backlog/LLM-contract work under `10-Backlog/Tasks/`.

## Template Authoring
Templates go in `05-Templates/<category-subfolder>/` with a Protocols pointer in `20-Knowledge/Protocols/`. See `references/template-conventions.md` for location rules, cross-document linkage patterns, section placement, and naming conventions.

## Bulk Property Management
Obsidian does not support native UI toggles for property subsets. See `references/bulk-property-toggles.md` for the correct methods to bulk-update or toggle frontmatter properties.

## Master Plan Backlog Task Notes

When converting a tactical Kanban item into an Obsidian Master Plan backlog item, write the note under `10-Backlog/Tasks/` with a human-readable filename. Use compact frontmatter (`title`, `type: task`, `status: deferred`, `owner`, `priority`, `domain`, `created`, `source_kanban_task`, etc.).

## Bulk Editing & YAML Properties
Obsidian natively lacks a quick "toggle switch" to dynamically turn on/off groups of YAML properties (like `Triage` blocks vs. `Enrichment` blocks) in the UI. 
If the user asks to manipulate or toggle a set of properties across multiple files (or cleanly inside one), use the `terminal` tool to run Python/sed batch scripts acting directly on the frontmatter, or recommend bulk community plugins (like 'Linter' or 'Multi Properties'). Do not assume there is a UI button for toggling property groups. `kanban_url`, `tags`) and a body with: status, original Kanban context, current state at deferral, related Kanban tasks, and resume criteria. Verify the write by reading the resulting file because vault paths contain spaces and may be iCloud-backed.

When designing canonical registries, metadata indexes, or other human-reviewed source-of-truth Markdown/YAML artifacts, prefer storing them in Obsidian/KOS if backlinks and a single human review surface matter. Keep generated runtime artifacts, compiled outputs, caches, and machine-only exports outside the vault (for example under `~/data/...`).

## Cross-System Knowledge OS Artifacts

When an artifact documents the master Knowledge OS / knowledge-management architecture — spanning Obsidian, Bookshelf/PageIndex, Neo4j KG, Hindsight/memory, Hermes, and future agent/system consumers — store it under:

```text
40-Operations/Knowledge OS/
```

Use this instead of `40-Operations/Hermes/` because Hermes may be the primary operator, but the KM/KG outputs are cross-system assets intended for other agents and systems. Use `10-Backlog/Tasks/` only for concrete implementation tasks generated from these operating artifacts, not for the operating architecture itself.

### Knowledge OS Contract Artifacts

When drafting Knowledge OS agent/operation contract architecture, keep the design source-aligned with GBrain and the Agent Contracts / Agent Behavioral Contracts papers:

- Operation contracts: stable verbs, schemas, scope, mutating/local-only metadata, shared CLI/MCP/tool surfaces.
- Execution contracts: bounded resources/time, success criteria, termination conditions, lifecycle state, multi-agent budget conservation.
- Behavioral contracts: hard/soft invariants, governance, recovery, telemetry; implement rich behavioral monitoring later, but reserve hooks early.
- Pipeline/handoff contracts: upstream outputs must satisfy downstream preconditions (e.g., Clerk packet → Librarian decision → Knowledge/Neo4j writeback).

Local v1 schema decision: include `principal` and `subject` as accountability metadata (Gerod prefers the clarity), while labeling them as local extensions rather than claims from GBrain/the papers. Inherit Hermes/platform guardrails instead of rebuilding generic safety; add only Knowledge OS-specific anti-slippage invariants such as citation/provenance/source-of-truth rules. See `references/knowledge-os-contract-design.md` for the compact pattern and skeleton.

**Phase 0 kickoff workflow:** When starting from a strategic project note like `10-Backlog/Projects/Knowledge OS Agent Contract Strategy and Implementation Plan.md`, begin with durable, read-only design artifacts before runtime enforcement:

1. Read the project note and any existing sibling Knowledge OS contracts (e.g., `Librarian Contract.md`, `PDF Source Metadata Contract.md`) for vocabulary reuse.
2. Create/verify `40-Operations/Knowledge OS/Contracts/` with `README.md`, `schema/`, `registry/`, `operations/`, `agents/`, and `pipelines/` as needed.
3. Draft schema and registry skeletons first; mark source-backed concepts vs local extensions explicitly.
4. Validate YAML parseability with a read-only script/command before claiming progress.
5. Update the strategic project note status/progress log, but do **not** add runtime enforcement, writeback hooks, or tactical delegation tasks unless explicitly requested.

**Agent contract drafting workflow:** For first-pass Knowledge OS agent contracts (e.g., Clerk, Librarian, Knowledge Writer), keep them as durable design/contract artifacts, not runtime implementations:

1. Reuse the established operation-contract shape: `contractspec`, `kind`, `name`, `principal`, `subject`, `source_alignment`, `summary`, `inherits`, `operation_scope`, `io`, `execution`, `behavior`, `recovery`, `telemetry`, `runtime_binding`.
2. Make `source_alignment` explicit in each agent file. Use `source_backed_concepts` for GBrain / Agent Contracts / Agent Behavioral Contracts fields, and `local_extension_fields` for Knowledge OS/Hermes fields like `principal`, `subject`, `runtime_binding`, and `runtime_binding.isolation_level`.
3. Preserve role boundaries: Clerk extracts/proposes only; Librarian validates/gates and emits decisions but does not execute writeback in proposal-only mode; Knowledge Writer is the controlled write contract requiring Librarian decision, citations, provenance, target hash, rollback, dry-run, and receipt.
4. Register each new agent contract in `registry/kos-contract-registry.yaml` with runtime binding, review flags, and concise review notes.
5. Validate all contract YAML, not just the new files: parse every `*.yaml` under `Contracts/`, check required top-level fields for operation/agent contracts, confirm source-alignment/local-extension blocks, and confirm registry entries for all operation/agent files.
6. Append a progress-log entry to the strategic project note summarizing artifacts, validation, and the explicit non-goal: no runtime enforcement or writeback hooks added.

**Pipeline contract drafting workflow:** For Knowledge OS pipeline/handoff contracts (e.g., `pipelines/intake-to-knowledge-promotion.yaml`), keep them as durable design/contract artifacts and explicitly avoid implementing validators, runtime enforcement, writeback hooks, or live tool wrappers:

1. Use `kind: pipeline` with the same top-level vocabulary as agents/operations: `contractspec`, `name`, `principal`, `subject`, `source_alignment`, `summary`, `inherits`, `operation_scope`, `io`, `pipeline`, `execution`, `behavior`, `recovery`, `telemetry`, and `runtime_binding`.
2. In `source_alignment`, label pipeline composition, handoff preconditions/guarantees, execution bounds, invariants, recovery, and telemetry as source-backed concepts; label Knowledge OS receipt names, vault paths, role names, and runtime bindings as local extensions.
3. Model each handoff as a stage with `upstream_actor`, `downstream_actor`, `input_artifact`, `output_artifact`, `upstream_guarantees`, `downstream_preconditions`, `missing_guarantee_policy`, and `boundary_rules`.
4. Encode missing guarantees as `block`, `downgrade`, `reject`, `skip optional handoff`, or `require_review` outcomes. Never let downstream agents guess missing citations, provenance, content hashes, target hashes, rollback plans, or receipts.
5. Preserve role boundaries across the stage chain: Clerk extracts/proposes only; Librarian validates/gates/proposes only; Knowledge Writer requires Librarian decision, citations, provenance, target hash, rollback plan, dry-run, and receipt before mutation; optional KG upsert requires Knowledge write receipt plus provenance.
6. Register the pipeline in `registry/kos-contract-registry.yaml` and validate every YAML file under `Contracts/` for parseability plus registry coverage; for pipelines, also check that each stage has handoff guarantees, downstream preconditions, missing-guarantee policy, and boundary rules.
7. Append a progress-log entry to the strategic project note summarizing the pipeline, registry update, validation result, and explicit non-goal: no runtime enforcement/writeback hooks added.

## HTML Artifacts in the Vault

Obsidian is the canonical storage/index layer, but it usually does not provide the best reading experience for full HTML reports. For rich human-readable outputs (daily/weekly briefings, strategy dashboards, impact maps), store the `.html` file in the vault for durability/discoverability and open it in a browser.

Avoid duplicate human-readable outputs. If an HTML briefing exists, do **not** also create a full Markdown version. If Markdown is useful, create only a tiny pointer/decision-ledger stub:

```markdown
# Daily Brief — YYYY-MM-DD

Open report: [HTML briefing](file://~/Obsidian/Main%20Vault/40-Operations/Hermes/Briefings/daily/YYYY-MM-DD-daily-brief.html)
Source packet: `YYYY-MM-DD-daily-brief.json`

## Accepted decisions only
- ...
```

Canonical synthesized knowledge should still be promoted into `20-Knowledge/` as normal, with citations. The HTML report is a presentation layer, not the long-term source of truth.

## Retrieval Strategy

The vault now has three retrieval layers — use them in this order:

| Priority | Method | Best for | Requires |
|---|---|---|---|
| **1** | **qmd hybrid search** | Semantic/keyword search across vault + Wiki + Research + Bookshelf | qmd installed, `qmd embed` current |
| **2** | **Obsidian REST API** | Backlinks, outlinks, tag counts, Dataview DQL | Obsidian running |
| **3** | **obsidian-cli / filesystem** | CRUD, grep, bulk ops, when above unavailable | CLI or shell |

**QMD replaces ad-hoc grep/sessions_search for vault content recall.** For "what does the vault say about X" questions, start with `qmd query` before falling back to filesystem tools or Hindsight.

### QMD Hybrid Search

The vault is indexed into qmd across 11 collections under a single index at `~/.cache/qmd/index.sqlite`.

**Collections configured:**

| Collection | QMD URI | Path | File Count |
|---|---|---|---|
| knowledge | `qmd://knowledge/` | `20-Knowledge/` | 1,268 |
| intake | `qmd://intake/` | `30-Intake/` | 992 |
| spiders | `qmd://spiders/` | `30-Spiders/` | 26 |
| backlog | `qmd://backlog/` | `10-Backlog/` | 97 |
| archive | `qmd://archive/` | `90-Archive/` | 169 |
| operations | `qmd://operations/` | `40-Operations/` | 96 |
| research | `qmd://research/` | `~/Research` | 89 |
| hermes | `qmd://hermes/` | `Hermes/` | 1 |
| side-projects | `qmd://side-projects/` | `50-Side projects/` | 14 |
| templates | `qmd://templates/` | `05-Templates/` | 6 |
| wiki | `qmd://wiki/` | `Wiki/` | 0 (scaffold for future domain knowledge) |

**Run queries via terminal:**

```bash
# BM25 keyword only (fast, no model, ~0.2s)
qmd search "SMIC lithography" --json

# Semantic vector search (~3s, 1 model)
qmd vsearch "Chinese semiconductor supply chain dependencies" --json

# Hybrid + reranking — BEST QUALITY (~2-3s warm, all 3 models)
qmd query "What are the supply chain risks for SMIC and YMTC?" --json

# Scope to specific collections
qmd query "thesis on data center power" -c knowledge -c operations

# Retrieve full document
qmd get qmd://knowledge/path/to/note.md
qmd get "20-Knowledge/AI Data Centers.md"
```

**Structured multi-mode queries** (BM25 + vector combined):

```bash
qmd query $'lex: "SMIC"\nvec: lithography equipment dependencies China'
```

**Output format:** add `--json` for structured results. Without it, qmd prints formatted text.

**Re-indexing:**

```bash
# After new files land in any collection
qmd embed

# Update a single collection index
qmd update -c knowledge
```

**MCP integration (recommended for agents):**

Configure per `optional-skills/research/qmd` doc — add to `config.yaml`:

```yaml
mcp_servers:
  qmd:
    url: "http://localhost:8181/mcp"   # HTTP daemon mode
    # or stdio mode:
    # command: "qmd"
    # args: ["mcp"]
```

Daemon mode keeps models warm (~2GB RAM). Stdio mode loads on first search and stays warm for the session.

**Context descriptions are the biggest accuracy lever.** Every collection above has context metadata set via `qmd context add qmd://<name> "description"`. When adding new collections, ALWAYS set context — it dramatically improves retrieval quality by telling the query expansion model what each corpus contains.

**Vault alignment rule:** Collections map to numbered vault folders plus the four non-numbered roots (Wiki, Hermes, Bookshelf/Research). If a folder is not numbered and not in the explicit allowlist above, it is a stray — do not collect it.

### Primary: obsidian-cli

### Quick Reference

```bash
# List files in a folder
obsidian-cli list "Hermes/Tasks" -v "Main Vault"

# Print a note (full path from vault root)
obsidian-cli print "Hermes/Tasks/Investment Ledger Migration" -v "Main Vault"

# Search note names (fuzzy)
obsidian-cli search "ledger" -v "Main Vault"

# Search note content
obsidian-cli search-content "SQLite" -v "Main Vault"

# Create a note
obsidian-cli create "Hermes/Tasks/New Task" -v "Main Vault" --content "# Title\n\nBody here"

# Open in Obsidian app
obsidian-cli open "Hermes/Plan" -v "Main Vault"

# Move/rename (updates wikilinks automatically)
obsidian-cli move "Old Path" "New Path" -v "Main Vault"

# Delete
obsidian-cli delete "Hermes/Tasks/Old Note" -v "Main Vault"

# View/edit frontmatter
obsidian-cli frontmatter "Hermes/Tasks/Some Task" -v "Main Vault"
```

### Conventions

- **Paths are vault-relative:** `Hermes/Tasks/Foo` not `~/Obsidian/Hermes/Tasks/Foo.md`
- **No `.md` extension** in CLI commands
- **Kanban boards** use `obsidian-plugin: board` YAML frontmatter + checkbox lists in columns
- **Wikilinks** use `[[Note Name]]` or `[[Folder/Note Name]]` syntax
- **Kanban update workflow:**
  1. `obsidian-cli print "Master Plan" -v "Main Vault"` to read current board
  2. Use `patch` tool to edit the markdown
  3. Verify with `obsidian-cli print` again

### When to Use CLI vs File Tools

- **Use `obsidian-cli`** for: creating notes, searching, printing content, Kanban updates, moving/renaming
- **Use `read_file`/`write_file`** for: bulk operations, precise line-number edits, or when CLI isn't available
- **Use `patch`** for: surgical edits to existing notes (faster than re-writing entire file)

### Task Management Pattern (Master Plan)

The Obsidian project board is `Hermes/Master Plan.md` (renamed from "Hermes Kanban"). It tracks human-facing milestones and quarterly goals. Agent-routable tasks go through Hermes Kanban (`hermes kanban`).

For Master Plan updates:
1. Create task note: `obsidian-cli create "Hermes/Tasks/Task Name" -v "Main Vault"`
2. Add to Master Plan column: `patch` tool on `Master Plan.md`
3. Move between columns: `patch` tool (remove from one column, add to another)

## Fallback: Raw Shell / Filesystem

When `obsidian-cli` is unavailable or you need bulk operations.

### Read a note
```bash
cat "~/Obsidian/main-vault/Hermes/Tasks/Some File.md"
```

### List notes
```bash
ls "~/Obsidian/main-vault/Hermes/Tasks/"
```

### Search
```bash
grep -rli "keyword" "~/Obsidian/main-vault/" --include="*.md"
```

### Create a note
```bash
cat > "~/Obsidian/main-vault/Hermes/Tasks/New Note.md" << 'ENDNOTE'
# Title

Content here.
ENDNOTE
```

**Verify immediately after:**
```bash
head -3 "~/Obsidian/main-vault/Hermes/Tasks/New Note.md"
```

### Append to a note
```bash
echo "
New content here." >> "~/Obsidian/main-vault/Hermes/Tasks/Existing Note.md"
```

## Vault Organization

### Collections (QMD retrieval layer)

Vault folders are indexed into QMD as collections for semantic/keyword search. 

**Collection allowlist** — only numbered vault folders plus these four non-numbered roots:

| Folder | QMD URI | Classification |
|---|---|---|
| `05-Templates/` | `qmd://templates/` | Numbered |
| `10-Backlog/` | `qmd://backlog/` | Numbered |
| `20-Knowledge/` | `qmd://knowledge/` | Numbered |
| `30-Intake/` | `qmd://intake/` | Numbered |
| `30-Spiders/` | `qmd://spiders/` | Numbered |
| `40-Operations/` | `qmd://operations/` | Numbered |
| `50-Side projects/` | `qmd://side-projects/` | Numbered |
| `90-Archive/` | `qmd://archive/` | Numbered |
| `Wiki/` | `qmd://wiki/` | **Allowed non-numbered** (domain knowledge) |
| `Hermes/` | `qmd://hermes/` | **Allowed non-numbered** (agent ops) |
| `~/Bookshelf` | `qmd://research/` | **Allowed non-numbered** (PDF evidence) |
| `~/Research` | same as Bookshelf | **Allowed non-numbered** (mirrors Wiki) |

**Stray detection rule:** Any folder not in the numbered list AND not in the explicit allowlist above (Wiki, Hermes, Bookshelf, Research) is a stray. Do not add it to qmd, do not create it without user confirmation. The vault is structured; new domain folders go into Wiki/ subfolders, not top-level.

### Hermes/ vs Wiki/

**`Hermes/`** — Operational & tooling docs. Things about the agent itself.
- `Tasks/` — Active work items, kanban tasks, migration plans
- `Benchmarks/` — Model evaluation results (which model to route to)
- `Projects/` — Hermes-executed project plans
- `Logs/` — Runtime logs
- `Master Plan.md` — Project board (renamed from "Hermes Kanban"; human-facing milestones, not agent tasks). Agent-routable tasks live in Hermes Kanban (SQLite).

**`Wiki/`** — Domain knowledge. The *subject matter*, not the tooling. Organized into tiers:

```
Wiki/
├── Domains/                         # Vertical knowledge domains
│   ├── AI & Data Centers/           # value-chain/ + thesis/ + companies/
│   ├── Drones & Robotics/
│   ├── Energy Transition & Storage/ # (solar, wind, batteries, grid storage)
│   ├── ClimateTech/                 # (sustainable fuels, waste mgmt, circular economy)
│   ├── EVs & Mobility/
│   └── GovCon/
├── Themes/                          # Horizontal — cross-cut every domain
│   ├── Gray Rhinos/                 # High-probability, high-impact scenarios
│   ├── Supply Chain/                # Supply chain topology, concentration risk
│   └── Workforce/                   # Labor markets, skill gaps (placeholder)
├── Companies/                       # Individual company research (BYD, CATL, etc.)
├── Investing/                       # Structured investing knowledge
├── Trading/                         # Operational — strategies, P&L, watchlists, memos
├── Sente/                           # Org meta (Capital/Ventures)
└── Sweepstakes/                     # Utility
```

**Rule of thumb:** If you'd still want the doc if Hermes didn't exist → Wiki. If it's about *how* Hermes works → Hermes/.

### Wiki ↔ Research Alignment

`~/Research/` mirrors the wiki structure. When creating research folders, follow this mapping:

| Wiki | Research |
|---|---|
| `Wiki/Domains/AI & Data Centers/` | `Research/Domains/AI/` + `Research/Domains/DataCenter/` |
| `Wiki/Domains/Drones & Robotics/` | `Research/Domains/robotics/` |
| `Wiki/Domains/Energy Transition & Storage/` | `Research/Domains/Energy/` + `Solar/` + `Batteries/` |
| `Wiki/Domains/ClimateTech/` | `Research/Domains/ClimateTech/` (incl. WasteManagement) |
| `Wiki/Domains/EVs & Mobility/` | `Research/Domains/EV/` |
| `Wiki/Themes/Gray Rhinos/` | `Research/Themes/Gray Rhinos/` |
| `Wiki/Themes/Supply Chain/` | `Research/Themes/Supply Chain/` |
| `Wiki/Companies/` | `Research/Companies/` |
| `Wiki/Investing/` | `Research/Investing/` |

**Important:** Themes (Supply Chain, Gray Rhinos, Workforce) are NOT under Domains/ in either Wiki or Research. They are peers to Domains/. Companies is also a peer to Domains/, not nested under it.

### Wiki Domain Scaffolding

Every new wiki domain gets:

1. **`INDEX.md`** — Overview, subfolder map, entry point for humans
2. **`AGENTS.md`** — Schema, conventions, cross-references. Frontmatter: `wiki_domain: DomainName`
3. **`value-chain/`** — Supply chain topology, node details (stages 01-NN)
4. **`thesis/`** — Bull/bear signals, demand indicators, trade ideas (long/short, ST/LT)
5. **`companies/`** — Individual company research pages (if applicable)

Cross-domain overlaps (e.g., batteries in both Energy Storage and EVs) are handled via Obsidian backlinks. Duplicated value chain nodes with different thesis annotations are intentional — same fact, different trade.

### Theme Scaffolding

Themes do NOT have value-chain/ folders. They contain:
- `scenarios/` — Specific risk/event scenarios
- `signals/` — Leading indicators and monitoring signals
- `playbooks/` — Response strategies and trade playbooks
- `AGENTS.md` — Schema and conventions

### Two-Tier Board System

**Master Plan** (Obsidian `Hermes/Master Plan.md`) = human-facing project board. Milestones, quarterly goals, multi-week initiatives. Visual drag-and-drop Kanban for Gerod's strategic view.

**Hermes Kanban** (`~/.hermes/kanban.db`) = agent work queue. Machine-facing, programmatic, handles fan-out/retry/blocking. Agent-routable tasks (enrichment, extraction, benchmarks).

The bridge: Master Plan cards decompose into Hermes Kanban tasks. Completion summaries roll back up to Obsidian notes linked from Master Plan cards.

**Never merge these.** They serve different audiences with different primitives.

### Moving Content Between Hermes/ and Wiki/

Before bulk moves, always check for naming conflicts:

```bash
comm -12 <(find "Wiki/Target/" -maxdepth 1 -type f -name "*.md" -exec basename {} \; | sort) \
         <(find "Hermes/Source/" -maxdepth 1 -type f -name "*.md" -exec basename {} \; | sort)
```

When moving, flatten legacy nesting (e.g., `openclaw-migrated/`) — don't carry forward organizational debt.

### Internal Toolset — Python Wrapper

For programmatic vault operations when Obsidian is running, use the `ObsidianVault` Python wrapper (see `references/obsidian-rest-api.md`). It hits Obsidian's live `metadataCache` for indexed search, backlinks, outlinks, and tags — no filesystem scanning, no regex. Location: `~/Agents-Shared/tools/obsidian-rest/obsidian_rest.py` (~270 lines, stdlib only).

Delegate to `obsidian-cli` via terminal for all CRUD (read/write/move/delete/list/frontmatter). No MCP wrapper needed — agents call `obsidian-cli` directly via `terminal`. No full Python filesystem library needed.

## Backlog Task Consolidation

When multiple task files exist for what is actually one multi-phase project (e.g., `Data Center Power Delivery Ingestion`, `Data Center Power Delivery Ingestion - Handoff`, `Data Center Power Delivery Phase 2`), consolidate them:

1. **Read ALL related files** — use `read_file` with filesystem paths (MCP `list_tasks` often fails on the Backlog paths)
2. **Verify deliverables on disk** — check that `done` tasks actually have their files/artifacts before trusting the status
3. **Create a single master plan** with `type: project`, `status: in_progress`, phase-by-phase tracking, and explicit checklists for remaining work
4. **Flip old tasks** — use the `patch` tool (NOT the Obsidian REST API PUT with frontmatter targeting, which rejects absolute paths with spaces):
   - Set `status: done`
   - Add `parent: [[ consolidated-plan-name ]]`
   - Add `replaced_by: [[ consolidated-plan-name ]]`
   - Replace body text with a short "## Archived" section pointing to the new plan
5. **Never trust frontmatter blindly** — many legacy backlog tasks have `status: active`, `status: idea` when they're actually done, or missing frontmatter entirely. Always read the content.

## Local REST API Plugin

**Plugin:** obsidian-local-rest-api (v3.6.2)
**Port:** 27124 (HTTPS TLS, self-signed cert) / 27123 (HTTP insecure)
**API Key:** `4d2572928da533216a5a5652d8d61c4d1d29c5a4e7005692ac1d59c1bea6ac07` (auto-discovered from `.obsidian/plugins/obsidian-local-rest-api/data.json`)

### Reference File

Full endpoint details, request/response shapes, and the Python wrapper reference are in `references/obsidian-rest-api.md` within this skill.

### Confirmed Working Endpoints (quick reference)

```bash
# Base: https://localhost:27124 (always, not /api/v1/)
# Auth: Authorization: Bearer <api-key>

# List files at vault root or any path
GET /vault/                         → {"files": ["00-Home.md", "10-Backlog/", ...]}
GET /vault/10-Backlog/Tasks/        → {"files": ["Foo.md", "Projects/", ...]}
# Read a note
GET /vault/path/to/note.md          → markdown content (string)
# Write/replace a note
PUT /vault/path/to/note.md          (body = content)
# Append to a note
PATCH /vault/path/to/note.md        (body = content, Content-Type: text/plain)
# Delete a note
DELETE /vault/path/to/note.md       → moves to Obsidian trash
# Rename/move a note (auto-updates wikilinks)
PATCH /vault/old-path.md            (body = {"path": "new-path"})
# Open in Obsidian UI
POST /open/path/to/note.md

# Full-text search (indexed, scored, with context)
POST /search/simple/?query=supply+chain  → [{"filename": "...", "score": N, "matches": [...]}]
# Note: search requires POST, not GET, despite query in URL

# Structured search with Dataview DQL
POST /search/                       (Content-Type: application/vnd.olrapi.dataview.dql+txt)

# Structured search with JsonLogic
POST /search/                       (Content-Type: application/vnd.olrapi.jsonlogic+json)

# Tags with counts
GET /tags/                          → [{"tag": "#supply-chain", "count": 42}, ...]

# Periodic notes
GET /periodic/daily/

# Active file (currently open in Obsidian)
GET /active/
```

### Pitfalls

- **No `/api/v1/` prefix.** Routes are flat: `/vault/`, `/search/simple/`, etc. The third-party npm MCP may use different paths.
- **Search is POST, not GET.** GET returns 405 even for `/search/simple/?query=...`.
- **TLS cert is self-signed.** Use `-k` with curl or `verify=False` in Python.
- **The insecure port (27123) sometimes returns 404** even when HTTPS works. Always try HTTPS (27124).
- **Obsidian must be running** for the plugin to respond.
- **API key lives in vault config** at `.obsidian/plugins/obsidian-local-rest-api/data.json`. Auto-discovered by `obsidian_rest.py`.

### Python Wrapper

See `references/obsidian-rest-api.md` for the full `ObsidianVault` class reference, API key discovery, and all endpoint details.

Quick usage:

```python
from obsidian_rest import ObsidianVault
vault = ObsidianVault()
results = vault.search("supply chain")   # indexed search
links = vault.backlinks("AGENTS")        # notes linking to AGENTS
outlinks = vault.outlinks("00-Home.md")  # wikilinks in a note
tags = vault.tags()                      # all tags with counts
```

## Bases Formulas

Obsidian Bases (the built-in database/table view) supports formulas via a custom expression language. The available functions are documented at <https://obsidian.md/help/bases/functions>.

### Pitfalls

**No `indexOf` on lists.** The `List` type supports: `contains`, `containsAll`, `containsAny`, `filter`, `flat`, `isEmpty`, `join`, `map`, `reduce`, `reverse`, `slice`, `sort`, `unique`. There is **no `indexOf`** or `findIndex`. To map values to numbers (e.g., status → stage number), use nested `if()`:

```
if(current.status == "idea", 1, if(current.status == "planned", 2, if(current.status == "committed", 3, if(current.status == "active", 4, if(current.status == "completed", 5, if(current.status == "on_hold", 6, if(current.status == "cancelled", 7, if(current.status == "archived", 8, 0))))))))
```

The `if()` signature is `if(condition, trueResult, falseResult)` — note it uses commas, not `? :` ternary.

**Status values in Bases formulas** must match the canonical Master Plan status set (all lowercase):
```
planned, committed, active, blocked, on_hold, completed, cancelled, archived
```

## Templater Templates

Template folder: `05-Templates/task-templates/`
- `Task.md` — constrained status dropdown for individual tasks
- `Project.md` — constrained status dropdown for projects

Both use `tp.system.suggester` to enforce the canonical status set. Point Templater settings to `05-Templates` as the template folder.

## Wikilinks

Obsidian links notes with `[[Note Name]]` syntax. When creating notes, use these to link related notes.

## Strategic Project Plans

When creating strategic backlog projects in `10-Backlog/Projects/`, follow the structured template with required sections (executive summary, source inventory, consolidated findings, workstreams, priorities, verification checklists, open questions). See [`references/strategic-project-plan-template.md`](references/strategic-project-plan-template.md) for the full format spec and pitfalls.

## Obsidian Web Clipper

The Web Clipper browser extension clips articles into `30-Intake/Clippings/`. Its template system uses variables, filters, and optionally the Interpreter (LLM-powered prompt variables).

### Key Resources

- **Template examples:** <https://github.com/kepano/clipper-templates>
- **Interpreter docs:** <https://obsidian.md/help/web-clipper/interpreter>
- **Filters reference:** <https://obsidian.md/help/web-clipper/filters>
- **Property types (types.json):** `templates/clipper-properties-types.json` in this skill — import via Web Clipper Settings → Properties → Import

### Template Filter Chain: Path-Prefixed Wikilinks

By default, `{{author|split:", "|wikilink|join}}` produces vault-root wikilinks (`[[Kyle Chan]]`). To target a subfolder, use `replace` with regex `^` before `wikilink`:

```handlebars
{{author|split:", "|replace:"/^/":"20-Knowledge/Experts/"|wikilink|join}}
```

This produces `[[20-Knowledge/Experts/Kyle Chan]]` — the stub note lands in the correct folder. The regex `^` anchors at the start of each string element in the array (works element-wise on arrays from `split`).

### Interpreter: Inline LLM at Clip Time

The Interpreter sends the page HTML + all prompt variables in one LLM request. Configure via Web Clipper Settings → Interpreter:

| Setting | Value (for this vault) |
|---------|----------------------|
| Provider type | **Custom** (OmniRoute-compatible endpoint) |
| Base URL | `http://ambler.cow-hippocampus.ts.net:8088/v1/chat/completions` |
| Model ID | `clerk` (OmniRoute combo — fill-first chain) |
| API Key | Leave empty or use Hermes API key as needed |

**Context optimization:** Default context is full page HTML (10-50K tokens). Restrict with `selectorHtml:article` in template Advanced settings. A cheap model like `clerk` (Haiku → Gemma → Flash) processes 3-4 prompt variables in ~3-5 seconds on the article body alone.

**Inline vs batch split (design guidance):**
- **Do at clip time** (Interpreter, fast/cheap model): domain classification, relevance score (1-5), one-line signal summary, topic tags. These are structural metadata that save the intake curator from re-reading the article just to triage it.
- **Defer to batch** (better model, cross-article context): full narrative summaries, entity extraction for Neo4j, contradiction detection against existing theses, supply chain topology mapping.

**Typical frontmatter properties (add to template Properties):**

```yaml
domain: {{"classify this article's primary domain. Choose exactly one from: AI & Data Centers, Semiconductors, Energy, Drones & Robotics, EVs & Mobility, Gray Rhinos, Supply Chain, GovCon, Quantum, ClimateTech, Other. Return only the domain name."}}
relevance: {{"rate this article's relevance to an active investment thesis from 1-5. 1=irrelevant clickbait, 3=useful context, 5=directly supports or contradicts an active thesis. Return only the number."}}
signal: {{"summarize this article in one sentence, focusing on the actionable signal for an investment or supply chain thesis."|blockquote}}
auto_tags: {{"extract 2-4 topic tags from this article. Use lowercase, hyphenated. Examples: ai-inference, gpu, bottlenecks, supply-chain, capex, grid, nuclear, quantum, photonic, robotics, china, semiconductors. Return as comma-separated list."}}
```

### Property Types (types.json)

Import `.obsidian/types.json` into Web Clipper via Settings → Properties → Import to register all property types (text, date, number, multitext) at once. The canonical copy lives at `templates/clipper-properties-types.json` in this skill — merge it into your vault's `.obsidian/types.json` when adding new properties.

### Clipping from Personal Mac (not ambler)

The OmniRoute custom provider only works from ambler (same Tailnet). When clipping from a personal Mac outside the tailnet, configure a direct provider (OpenRouter, Anthropic, etc.) with a cheap model (`gpt-4.1-mini`, `claude-3-haiku`) instead. Both providers can coexist in Interpreter settings — switch per clip session.