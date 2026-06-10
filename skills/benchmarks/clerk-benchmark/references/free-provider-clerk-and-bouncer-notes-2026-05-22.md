# Free provider Clerk/Bouncer notes — 2026-05-22

Session-specific calibration for OmniRoute free/abundant lanes. Use this as routing context, not as a permanent ban on providers — credentials and adapter behavior may change.

## GitHub Models (`ghm/`)

Catalog included `ghm/openai/gpt-4.1`, `ghm/openai/gpt-4o`, `ghm/openai/gpt-4o-mini`, `ghm/openai/o3`, `ghm/openai/o4-mini`, `ghm/mistral-ai/Mistral-Medium-3`, `ghm/cohere/Cohere-command-a`, `ghm/meta/Llama-4-Maverick-17B-128E-Instruct`, `ghm/deepseek/DeepSeek-R1`, and `ghm/xai/grok-3`.

Short Clerk smoke results before stopping to avoid GitHub Models ban/rate-risk:

| Model | Clerk score | Pass | Notes |
|---|---:|---:|---|
| `ghm/openai/gpt-4o` | 0.893 | 6/8 | strongest quick signal |
| `ghm/openai/gpt-4.1` | 0.877 | 5/8 | good but slower |
| `ghm/openai/gpt-4o-mini` | 0.850 | 5/8 | usable but not worth ban-risk |
| `ghm/cohere/Cohere-command-a` | 0.768 | 5/8 | weaker |
| `ghm/mistral-ai/Mistral-Medium-3` | 0.000 | 0/8 | failed |

Operational conclusion: do not put GitHub Models into recurring Clerk benchmark lanes unless rate-policy is explicitly accepted.

## `clerk-free` combo state

At time of test, `clerk-free` contained:

1. `if/kimi-k2-thinking`
2. `if/qwen3-coder-plus`
3. `if/deepseek-v3.2`
4. `nvidia/llama-3.3-70b-instruct`
5. `groq/llama-3.3-70b-versatile`

Findings:

- `if/*` routed through `qoder`; the Qoder connection had invalid/expired credentials (`401 invalid_api_key` / `No credentials for provider: qoder`). Re-test after credential refresh; don't encode this as a permanent model failure.
- `nvidia/llama-3.3-70b-instruct` returned 404 for every Clerk case. Likely model slug/catalog mismatch.
- `groq/llama-3.3-70b-versatile` is reachable but not Clerk-grade: Clerk score `0.561`, pass `3/8`, avg `~922ms`. It produced valid simple extractions but failed harder graph-ingestion cases.

## Bouncer relevance

`groq/llama-3.3-70b-versatile` is a good Bouncer candidate despite weak Clerk results:

| Model | Bouncer pass | Avg latency | Notes |
|---|---:|---:|---|
| `groq/llama-3.3-70b-versatile` | 5/6 | ~26–34ms | missed quantum-sensing due to prompt coverage |
| `antigravity/gemini-2.5-flash-lite` | 5/6 | ~32ms | abundant quota; same miss |
| `antigravity/gemini-3.1-flash-lite` | 5/6 | ~30ms | abundant quota; same miss |
| `antigravity/gpt-oss-120b-medium` | 0/6 | ~35ms | broken adapter behavior; echoed prompt meta-text |

Conclusion: separate Clerk and Bouncer routing. Free/fast models that are useful for Bouncer are not necessarily safe for Neo4j Clerk ingestion.
