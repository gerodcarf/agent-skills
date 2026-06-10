# OmniRoute clerk-free Combo Evaluation — 2026-05-22

Evaluated models in the OmniRoute `clerk-free` combo for Clerk (Neo4j ingestion) viability.

## Findings

- `if/kimi-k2-thinking`, `if/qwen3-coder-plus`, `if/deepseek-v3.2`: Failed (`HTTP 400 No credentials for provider: qoder` and 401s). OmniRoute `qoder` key is expired/invalid.
- `nvidia/llama-3.3-70b-instruct`: Failed (`HTTP 404 page not found`).
- `groq/llama-3.3-70b-versatile`: Completed, but weak for Clerk. Score: 0.561, 3/8 passed. Failed graph-ingestion cases (`subsidiary_and_location`, `material_supply_chain`) and formatting on complex metrics. **Verdict: Not ingestion-ready.**

## GHM (GitHub Models) Note

Also briefly evaluated `ghm/openai/gpt-4o-mini`, `ghm/cohere/Cohere-command-a`, and `ghm/openai/gpt-4o` for Clerk. While `gpt-4o` showed promise (6/8 pass), we abandoned using `ghm` for automated benchmarking to avoid API ban/rate-limit risks on the GitHub Models platform.

## Recommendation

Do not use `clerk-free` for production ingestion until the models are replaced or the keys are fixed. The primary `clerk` combo (e.g., `gemini/gemini-2.5-flash-lite` or `antigravity/gemini-2.5-flash-lite`) remains the gold standard.