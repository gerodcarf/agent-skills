# Bookshelf Intake Format

**Location:** `~/Bookshelf/__Inbound/`
**Inbound scan doc:** `~/Obsidian/main-vault/40-Operations/Knowledge OS/Bookshelf Inbound Scan.md`

## Source Sidecar YAML (`.source.yaml`)

Sidecars are **flat YAML documents** — NOT Obsidian-style markdown with `---` frontmatter delimiters.
Using `---` will cause `yaml.safe_load()` to throw "expected a single document in the stream."

### Canonical field set

```yaml
schema_version: bookshelf_source.v1
title: "Report Title"
author: "Author / Org"
date: YYYY-MM-DD
type: report
source_url: "https://..."
pdf_url: "https://..."
source_provenance_status: known
source_system: manual_ingest
captured_at: "YYYY-MM-DD"
captured_by: Hermes
intended_collection: Investing
intended_domain: macro/wealth-management
origin_note: "Why we grabbed it"
why_keep: "Long-form justification for Bookshelf retention"
status: staged
domains:
  - investing
  - macro
tags:
  - tag1
  - tag2
notes: >
  Summary of key findings / methodology caveats.
```

### Key fields

| Field | Purpose |
|-------|---------|
| `schema_version` | Always `bookshelf_source.v1` |
| `source_provenance_status` | `known` for verified sources, `unverified` otherwise |
| `source_system` | Origin — `manual_ingest`, scraper name, etc. |
| `intended_collection` | Top-level Bookshelf folder: `Companies`, `Domains`, `Investing`, `Themes`, `Other` |
| `intended_domain` | Domain path under the collection |
| `status` | `staged` (inbound), `processed`, etc. |
| `content_hash` | Optional `sha256:` hash of the PDF |

### Pitfalls

- **No `---` delimiters.** Sidecars are pure YAML, not Obsidian markdown. `write_file`'s YAML linter will correctly flag `---` in the body as a multi-document error.
- **Validate with Python** after writing: `python3 -c "import yaml; yaml.safe_load(open('file.source.yaml'))"`
- **Check existing examples** in `__Inbound/` before inventing fields — the format is already established.
