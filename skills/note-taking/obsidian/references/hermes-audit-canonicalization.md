# Hermes audit canonicalization

Session-derived checklist for storing Hermes security/review audit records in Obsidian.

## Canonical location

Use Obsidian for durable, human-reviewable audit records:

```text
~/Obsidian/main-vault/40-Operations/Hermes/Audits/
```

Use `~/.hermes/audits/` only as scratch/legacy staging. Avoid long-term duplicate audit files.

## File naming

Use human-readable Markdown filenames:

```text
V2 Cerberus Security Audit - 2026-06-08.md
```

Avoid UUIDs and opaque names for Obsidian audit records.

## Migration / de-duplication checklist

1. Copy or write the final corrected audit into the Obsidian audits folder.
2. Verify the source and Obsidian files are byte-identical before deleting any source duplicate:
   - compare file size; and
   - compare SHA-256 hash or equivalent content digest.
3. Delete the duplicate under `~/.hermes/audits/` only after the Obsidian copy is confirmed complete.
4. If automation still expects the legacy path, prefer a pointer/stub or update the automation rather than maintaining two full copies.

## Reviewer / red-team profile convention

Reviewer/red-team profiles may write final audit Markdown directly to the Obsidian audits folder only when the task explicitly asks for a canonical audit artifact.

Before finalizing:

- Ensure the audit is secret-safe: no raw API keys, OAuth tokens, bearer strings, credentials, or unredacted private values.
- Use redaction markers for evidence.
- Run a heuristic secret scan and report counts only, never matched secret-like strings.
- Keep session-specific execution detail concise; the audit should be reviewable by a human in Obsidian.

## Common pitfall

Do not blindly preserve both `.hermes/audits/` and Obsidian copies. The user's preference is a single canonical audit record in Obsidian, with `.hermes/audits/` treated as scratch/legacy.