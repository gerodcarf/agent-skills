# Obsidian Local REST API — Python Wrapper & Reference

**Plugin:** obsidian-local-rest-api (v3.6.2)
**Python Wrapper:** `~/Agents-Shared/tools/obsidian-rest/obsidian_rest.py` (~270 lines, stdlib only)
**Dependencies:** Python stdlib (urllib, json, re, ssl, os) — no external packages.

## Philosophy

The plugin runs inside Obsidian and exposes its live `metadataCache` via REST. The wrapper is just HTTP glue — no custom parsing, no filesystem scanning, no path validation needed. Search and wikilink operations use Obsidian's own index (~50-200ms) instead of `rg`/file walking (1-5s).

## Quick Usage

```python
from obsidian_rest import ObsidianVault

vault = ObsidianVault()  # auto-discovers API key from vault data.json

# Read/write
content = vault.read("00-Home.md")
files = vault.list("10-Backlog")

# Search (indexed, scored)
results = vault.search("supply chain", limit=10)
# → [{"filename": "...", "score": N, "matches": [{"context": "...", ...}]}]

# Wikilinks
backlinks = vault.backlinks("AGENTS")       # notes linking TO AGENTS
outlinks = vault.outlinks("00-Home.md")     # wikilinks IN the note

# Tags
tags = vault.tags()                         # list of {tag, count}

# Frontmatter
fm = vault.get_frontmatter("10-Backlog/Tasks/Foo.md")
vault.patch_frontmatter("10-Backlog/Tasks/Foo.md", "status", "active")

# Obsidian must be running for this to work.
```

## Architecture

```
obsidian_rest.py (stdlib Python)
    │
    ├── urllib.request  → HTTPS POST/GET
    └── json            → parse responses
         │
         ▼
Obsidian Local REST API (port 27124, self-signed TLS)
    │
    └── metadataCache → Obsidian's live index (backlinks, search, tags)
```

## API Key Discovery

1. `OBSIDIAN_REST_API_KEY` env var (highest priority)
2. Scans `~/Obsidian/` (follows iCloud symlinks) for `.obsidian/plugins/obsidian-local-rest-api/data.json`
3. Falls back to `~/Documents/Obsidian/`

Raises `RuntimeError` if no key found.

## Confirmed Endpoints

Base: `https://localhost:27124` (self-signed TLS). Auth: `Authorization: Bearer <key>`.

### Core Vault Operations

| Operation | Method | Endpoint | Notes |
|-----------|--------|----------|-------|
| List files | GET | `/vault/`, `/vault/subfolder/` | Response: `{"files": ["00-Home.md", "10-Backlog/", ...]}`. Files include `.md`, directories end with `/` |
| Read note | GET | `/vault/path/to/note.md` | Response: raw markdown content (string) |
| Write/replace | PUT | `/vault/path/to/note.md` | Content-Type: `text/markdown` or `text/plain`. Overwrites entire file |
| Append | PATCH | `/vault/path/to/note.md` | Content-Type: `text/plain`. Body: text to append |
| Delete | DELETE | `/vault/path/to/note.md` | Moves to Obsidian trash |
| Move/rename | PATCH | `/vault/old-path.md` | Content-Type: `application/json`. Body: `{"path": "new-path.md"}`. Auto-updates wikilinks |
| Open in UI | POST | `/open/path/to/note.md` | Opens note in Obsidian window |

### Search

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/search/simple/?query=...` | **POST** | Fuzzy full-text search. Query in URL, NOT body. POST required (GET returns 405). Empty body OK. Response: scored matches with context snippets. Score = negative float (closer to 0 = better) |
| `/search/` | POST | Dataview DQL (Content-Type: `application/vnd.olrapi.dataview.dql+txt`). E.g. `LIST FROM "20-Knowledge" WHERE contains(file.tags, "#supply-chain")` |
| `/search/` | POST | JsonLogic (Content-Type: `application/vnd.olrapi.jsonlogic+json`) |

### Tags & Metadata

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tags/` | GET | All tags with usage counts. Response: `[{"tag": "#supply-chain", "count": 42}]` |
| `/periodic/daily/`, `/weekly/`, `/daily/2026/05/12/` | GET | Today's daily/weekly note or specific date |
| `/active/` | GET | Currently open file in Obsidian |

## Pitfalls

### Routes are FLAT — no `/api/v1/` prefix
The most common mistake. The plugin serves at `/vault/`, `/search/simple/`, `/tags/` — **not** `/api/v1/vault/`. `curl https://localhost:27124/api/v1/...` returns 404.

### Search: POST with query in URL
`/search/simple/?query=supply+chain` requires **POST** method despite the query being in the URL. GET returns 405. Do NOT send a JSON body — returns 400: `"A single '?query=' parameter is required"`.

### Wrong API key = silent disconnect (curl error 52)
On wrong auth, the plugin closes the socket with empty reply rather than returning 401. curl shows `Empty reply from server` (error 52). Check Obsidian is running before assuming the key is wrong.

### HTTPS (27124) vs insecure HTTP (27123)
The plugin runs both ports. Always use HTTPS (27124). The insecure port (27123) responds but some endpoints return 404 even when auth is correct.

### SSL: self-signed cert
Use `-k` with curl or `verify=False` / `CERT_NONE` in Python. The cert file is at `.obsidian/plugins/obsidian-local-rest-api/obsidian-local-rest-api-certificate.crt` if you want to trust it.

### Symlink resolution for API key discovery
`Main Vault → ~/Library/Mobile Documents/com~apple~CloudDocs/Main Vault` is an iCloud symlink. `os.walk()` doesn't follow symlinks by default. The wrapper uses `os.path.realpath()` and `followlinks=True`.

### Filenames
`list()` returns files with `.md` extension, directories with trailing `/`. `backlinks("AGENTS")` searches for `[[AGENTS]]` — use basename without `.md`.

### Obsidian must be running
The plugin lives inside Obsidian's Electron process. If closed, port 27124 has nothing listening.

## Deprecation Notes

The `obsidian-toolset` skill (full Python filesystem library) was deprecated 2026-05-12. The third-party `mcp-obsidian-vault` was removed from `config.yaml` on the same date. Skills referencing `mcp_obsidian_*` tools have been patched to use `obsidian-cli` or `kanban_list` instead.
