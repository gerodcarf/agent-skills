# GitHub Models (ghm) and clerk-free Evaluation — 2026-05-22

Session notes evaluating OmniRoute's `github-models` (ghm) provider and the `clerk-free` combo for Clerk Neo4j-ingestion readiness.

## GitHub Models (`ghm/`)
GitHub Models (`ghm/openai/gpt-4o`, `ghm/cohere/Cohere-command-a`, `ghm/openai/gpt-4.1`, etc.) are highly competent for Clerk extraction:
- `ghm/openai/gpt-4o`: Score ~0.893 (6/8 passes)
- `ghm/openai/gpt-4.1`: Score ~0.877 (5/8 passes)
- `ghm/openai/gpt-4o-mini`: Score ~0.850 (5/8 passes)

**Verdict:** Despite good performance, do **not** use `ghm` models for automated Clerk benchmark lanes or production ingestion combos due to ban and rate-limit risks associated with the free GitHub Models tier.

## `clerk-free` OmniRoute Combo
The `clerk-free` combo is currently **not viable** for real Neo4j ingestion.
- `if/kimi-k2-thinking`, `if/qwen3-coder-plus`, `if/deepseek-v3.2`: Fail with HTTP 400 (No credentials for provider `qoder`).
- `nvidia/llama-3.3-70b-instruct`: Fails with HTTP 404.
- `groq/llama-3.3-70b-versatile`: Reachable, fast, and free, but scores only ~0.561. It fails harder graph-ingestion cases (e.g., metric normalization, document citation spans). 

**Verdict:** Do not route real KOS ingestion work to `clerk-free`. Use the stronger fallback lanes (`gemini/gemini-2.5-flash-lite`, `antigravity/gemini-2.5-flash-lite`) instead. `groq/llama-3.3-70b-versatile` is acceptable only for cheap, first-pass extraction where failures are tolerated.