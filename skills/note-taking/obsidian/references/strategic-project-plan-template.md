# Strategic Project Plan Template — Obsidian Backlog Projects

When the user asks you to create a strategic project/action plan in Obsidian (as opposed to a tactical Kanban task), use this structure. These live under `10-Backlog/Projects/` in the vault.

## File Naming

- Human-readable, descriptive names: `Cerberus Migration Cleanup Action Plan.md`
- No UUIDs, no dates-in-filename unless the plan is date-scoped (like a sprint)
- Use title case

## Required Sections

Strategic project plans should include most or all of these sections, adapted to the project:

### 1. Executive Summary
- Current status (use 🟢🟡🔴 for at-a-glance readiness)
- What is already clean/done
- What blocks the goal

### 2. Source Inventory
Table with columns: `# | Source Artifact | Type | Date | Superseded?`
- List every audit/review/reference artifact consulted
- **Explicitly mark superseded sources** — later revisions override earlier findings
- Note the difference between original and revised findings

### 3. Consolidated Findings Table
Table with columns: `ID | Area | Severity | Source | Finding | Current Status | Recommended Action | Owner | Blocks [goal]?`
- ID format: prefix by severity (`C1`, `H1`, `M1`, `L1` for Critical/High/Medium/Low)
- Source column should reference the Source Inventory row (S1, S2, etc.)
- "Blocks [goal]?" is a yes/no column that ties findings to the actual milestone

### 4. Action Plan by Workstream
Group related findings into workstreams (A, B, C...). Each workstream gets:
- A `> **Goal:**` blockquote explaining the workstream objective
- Checkbox items (`- [ ]`) with finding ID references
- Specific commands or verification steps where applicable

### 5. Prioritized Next Steps
Break into tiers:
- **P0** — Blocking before milestone
- **P1** — Should fix before milestone
- **P2** — Can migrate as known debt
- **P3** — Archive/disposition later

Each tier is a table with `# | Item | Workstream | Effort`.

### 6. Suggested Kanban Follow-Up Tasks
**Do not create them** unless explicitly asked. Just propose:
- Title
- Assignee suggestion (e.g., `coder`, `reviewer`, `clerk`)
- Body / acceptance criteria
- Dependencies

### 7. Verification Checklist
Concrete commands grouped by workstream. Use fenced code blocks. Include comments showing expected output:
```bash
# A1: Check passes
python3 -m py_compile scripts/foo.py
# Expected: no output (success)
```

### 8. Open Questions for Human Decision
Table with: `# | Question | Context | Impact`
- Only include decisions that need human judgment (security posture, retirement vs revival, acceptable debt level)

## Pitfalls

- **Do not treat earlier audits as authoritative if a revised version superseded them.** Always check for revision markers, red-team review verdicts, or explicit "superseded" language.
- **Live-verify audit findings before writing them into the plan.** Check the actual files/workspace state, not just the audit report text. Findings may have been fixed between the audit and the plan creation.
- **Distinguish the workspace you're verifying from the canonical repo.** Kanban task workspaces (`~/.hermes/kanban/workspaces/t_xxx/`) contain clones/forks, not the live source. Check `workspace_path` in the kanban DB if unsure.
- **Use the kanban SQLite DB directly** when `kanban_*` tools don't expose enough data (task comments, metadata, completion timestamps). Access via `sqlite3 ~/.hermes/kanban.db` in terminal.
- **Do not fabricate results.** If a source cannot be found, mark it as "unverified / needs lookup."
- **Preserve sensitive details.** Do not quote secret values, API keys, or tokens — even redacted ones from audit files.
