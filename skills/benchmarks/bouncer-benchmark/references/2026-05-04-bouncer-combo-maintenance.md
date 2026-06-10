# Bouncer Combo Maintenance Log — 2026-05-04

This document records the observed failure modes and fixes applied to the `omniroute:bouncer` combo during a production incident.

## Failure Modes Observed

| Symptom | Root Cause | Fix Applied |
|---------|------------|-------------|
| `413 payload too large` (275KB) | Upstream context bloat — the bouncer is being called with enormous payloads. Even with simple YES/NO prompts, the request size ballooned far beyond reasonable limits. | Ensure bouncer requests use `max_tokens=10`. Trim any context being passed; do not include full documents. If using OmniRoute, check combo for accidental `fill_first` context concatenation. |
| `cerebras/gpt-oss-120b 404` | Model ID decommissioned or access revoked. | Replace with available equivalent (`cerebras/llama-3.1-8b` or remove). |
| `sambanova/gpt-oss-120b 429` | Rate limit exceeded (daily token cap or request cap). | Remove or substitute with a model having separate quota; avoid stacking multiple rate-limited providers in the same fill-first chain. |
| `groq/llama-3.3-70b-versatile 413` | TPM limit exceeded (12000 TPM, requested ~22736). Payload size contributed to high token count. | Same as payload bloat fix; consider using smaller 8B models with higher TPM allowances. |
| `stepfun/step-3.5-flash fallback failed` | Nous Portal not configured (`hermes auth` not run). | Either configure Nous auth or remove fallback entry from combo to prevent silent failures. |
| `MCP granola/mesh 401 Unauthorized` | Expired bearer tokens in profile `config.yaml`. | Refresh tokens or disable MCP servers in bouncer profile if not needed (`mcp_servers: {}`). |

## Verified Healthy Combo Skeleton

```yaml
fill_first:
  - groq/llama-3.1-8b-instant   # speed leader
  - cerebras/llama-3.1-8b       # free tier backup
  - openrouter/google/gemma-4-26b-a4b-it  # cheap structured backup
max_retries: 0
queue_timeout_ms: 10000
```

## Smoke Test Criteria

- **Accuracy:** 5/6 test cases correct (≥80%).
- **Latency:** Average <400ms.
- **Output hygiene:** Zero multi-word responses; only `YES` or `NO`.

## Kanban Readiness

The bouncer profile is kanban-ready once the combo issues above are resolved. Assign tasks to `bouncer` as any other profile; the dispatcher injects `KANBAN_GUIDANCE` automatically. Suitable for backfill/audit and workflow-gate scenarios; avoid for high-throughput live streams.