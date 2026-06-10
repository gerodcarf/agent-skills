# Obsidian Template Conventions

## Location
- Templates live in `05-Templates/<category-subfolder>/` (never flat in 05-Templates/)
- A Protocols pointer in `20-Knowledge/Protocols/` routes to each template set and explains when to use each

## Subfolder Examples
- `05-Templates/investment-memo-templates/` — Macro/Sector Thesis, Company Memo, Position Memo
- `05-Templates/investment-memo-templates/` — **Trading Thesis Header** (canonical YAML frontmatter block for upgrading existing theses to the unified `trading-thesis` contract)
- Future: `05-Templates/meeting-templates/`, `05-Templates/spider-templates/`, etc.

## Template Design Principles

1. **Frontmatter first.** Every template starts with YAML frontmatter containing:
   - Template usage instructions as YAML comments (lines starting with `#`)
   - All computable/parseable fields in frontmatter (not buried in prose)
   - Templater syntax where applicable (`<% tp.date.now("YYYY-MM-DD") %>`)
   - Status enums documented inline (e.g., `# draft | active | closed`)

2. **Cross-document linkage via frontmatter.** Templates that reference each other use frontmatter fields, not just inline wikilinks:
   - Position Memo → `source_memos.company` and `source_memos.thesis`
   - Company Memo → `thesis_ids`
   - This makes linkage queryable by scripts

3. **Section placement matters.** Each section belongs at the right document level:
   - Denominator Effect → Company Memo only (not Macro/Sector)
   - Trade expression baskets → Macro/Sector Thesis Memo only (not Position)
   - Computable triggers → All three, but scoped differently
   - Options structure → Position Memo only
   - Post-mortem → Position Memo only

4. **Placeholder text.** Use `<placeholder>` angle brackets for required fields. Instructions say "leave n/a if not applicable rather than deleting."

5. **Protocols pointer.** Each template set gets a companion file in `20-Knowledge/Protocols/` that:
   - Lists all templates and when to use each
   - Documents linkage rules between templates
   - States design principles
   - Example: `20-Knowledge/Protocols/Investment Memo Templates.md`

## Naming
- Human-readable filenames with spaces: `Company Memo.md`, `Position Memo.md`
- No UUIDs (those are for the Hermes Kanban delegation board only)

## Obsidian Rendering Notes
- Standard `##` headers render correctly in Reading View
- Some themes render H2s with normal weight in Live Preview — this is a theme issue, not a syntax issue
- Use `---` horizontal rules sparingly between major sections to avoid visual noise
