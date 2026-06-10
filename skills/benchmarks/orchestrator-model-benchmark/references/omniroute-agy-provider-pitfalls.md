# OmniRoute `agy/` Provider — Routing & Availability Pitfalls

**Date:** 2026-06-06
**Context:** Attempted full-suite benchmark on `agy/gemini-pro-agent`, `agy/gemini-3.1-pro-high`, `agy/gemini-3-flash-agent`

## Key Findings

### 1. Catalog listing ≠ routable

Models appear in `GET /v1/models` but return 404/400 on actual chat completions:

```
agy/gemini-3-flash-agent  → 404 "Antigravity upstream error"
agy/gemini-3-flash        → 404 "Antigravity upstream error"
```

The error body says `"No credentials for provider: agy"` on the script ping fallback, confirming the upstream Antigravity credentials are missing or expired for some models even though the catalog advertises them.

**Implication:** Always probe with a real `POST /v1/chat/completions` call before committing to a benchmark run. The `managed_run.py` ping gate catches this, but catalog-only checks (e.g. listing models) are insufficient.

### 2. Credential cooldown (429)

```
agy/gemini-pro-agent → 429 "All credentials for model gemini-pro-agent are cooling down"
Retry after: 51426s (~14.3 hours)
```

OmniRoute rotates credentials and enforces cooldown windows. If all credentials for a model are exhausted, the model becomes unavailable until cooldown expires. The `managed_run.py` ping gate catches this and skips the run cleanly.

**Implication:** When batch-running multiple models, credential exhaustion on one model does not block others (they use different credential pools). Run models individually if you suspect cooldown issues.

### 3. `agy/` prefix routes through Antigravity

All `agy/` models resolve through the Antigravity upstream. Error messages reference "Antigravity upstream error" and "No credentials for provider: agy". The Antigravity upstream can be flaky — models may work one day and 404 the next if credentials expire or models are rotated out.

### 4. Batch execution pattern

`managed_run.py` runs one model at a time. To batch multiple models sequentially:

```bash
for model_spec in "omniroute agy/model-a label-a" "omniroute agy/model-b label-b"; do
  python3 managed_run.py $model_spec
done
```

Each invocation is independent — one failure does not block the next.

### 5. `antigravity/` prefix also affected

Direct `antigravity/` prefix models hit the same upstream:
- `antigravity/gemini-pro-agent` → 502 empty content / reset
- `antigravity/gemini-3.1-pro-high` → 404
- `antigravity/gemini-3-flash-agent` → 404

Use `agy/` as the canonical prefix when both are available; behavior is equivalent.

## Verified Working `agy/` Models (as of 2026-06-06)

- `agy/gemini-3.1-pro-high` — completed full 6-scenario benchmark (52/108 = 48%)

## Models That Failed

- `agy/gemini-pro-agent` — 429 credential cooldown
- `agy/gemini-3-flash-agent` — 404 not routable (catalog lists but no credentials)
