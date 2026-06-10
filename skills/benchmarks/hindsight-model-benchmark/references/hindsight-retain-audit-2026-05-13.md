# Hindsight Retain Benchmark Results (2026-05-13)

Standalone audit of 12 models in the `hindsight-retain-free` combo. Tested ping latency and ~10K token context acceptance through OmniRoute.

## Results Table

| Model | Ping | Ping Latency | Context OK | Ctx Latency | Tokens | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **nvidia/nvidia/nemotron-3-nano-30b-a3b** | ✅ | 0.4s | ✅ | 0.7s | 14,669 | ✅ PASS — Fastest |
| **nvidia/openai/gpt-oss-120b** | ✅ | 0.4s | ✅ | 0.7s | 12,978 | ✅ PASS — Fast |
| **kiro/claude-haiku-4.5** | ✅ | 1.8s | ✅ | 3.0s | 19,727 | ✅ PASS — Good |
| **ollama-cloud/gemma4:31b** | ✅ | 1.7s | ✅ | 3.0s | 14,830 | ✅ PASS — Good |
| **gemini/gemma-4-26b-a4b-it** | ✅ | 17.4s | ✅ | 26.3s | 14,819 | ⚠️ SLOW (but works) |
| **openrouter-google/gemma-4-26b-a4b-it:free** | ✅ | 1.9s | ❌ | 28.6s | 0 | ❌ RATE-LIMIT (429) |
| **cerebras/gpt-oss-120b** | ❌ | 0.1s | -- | -- | 0 | ❌ 404 NOT-FOUND |
| **ollama-cloud/nemotron-3-super** | ❌ | 11.4s | -- | -- | 0 | ❌ 502 ERROR |
| **ollama-cloud/minimax-m2.7** | ❌ | 18.8s | -- | -- | 0 | ❌ 403 FORBIDDEN |
| **ollama-cloud/gpt-oss:120b** | ❌ | 3.3s | -- | -- | 0 | ❌ 404 NOT-FOUND |
| **sambanova/gpt-oss-120b** | ❌ | 30.0s | -- | -- | 0 | ❌ TIMEOUT |
| **qoder/qwen3-32b** | ❌ | 5.2s | -- | -- | 0 | ❌ 401 AUTH |

## Key Findings

- **5 models work** — 7 are dead (404, 403, 401, timeout, or permanently rate-limited)
- **Free tiers are unreliable** — OpenRouter free Gemma and Cerebras free GPT-OSS both failed
- **Paid APIs are reliable** — Gemini (free API account), Kiro, and Nvidia paid endpoints all worked
- **Groq's gpt-oss-20b was the original cause of Hindsight failures** — its 8k TPM limit causes instant HTTP 413 on 67K requests
- **Gemma-4-26b-a4b-it (free)** — 429 rate-limited on OpenRouter; Google AI Studio free tier throttles heavily

## Action Taken

Removed all 7 dead models from the `hindsight-retain-free` combo via direct SQLite update in Docker container. Updated Hindsight's `.env` to route through OmniRoute's `hindsight-retain` combo instead of Groq.
