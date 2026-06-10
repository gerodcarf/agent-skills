# Model Availability Audit — hindsight-retain-free Combo (2026-05-13)

## Context

Hindsight's retain pipeline sends ~67K tokens for fact extraction. Groq's gpt-oss-20b
free tier was failing with HTTP 413 (8K TPM limit). We audited the 12 models in the
`hindsight-retain-free` OmniRoute combo to find which can handle large context.

## Test Methodology

Two-phase test via OmniRoute (`http://localhost:20128/v1/chat/completions`):
1. **Ping:** 10-token prompt, 30s timeout.
2. **Context:** ~10K token synthetic conversation, 90s timeout.

Thresholds: PASS (<30s latency), SLOW (>30s), FAIL (any error).

## Results

### ✅ PASS (Keep in combo)

| Model | Provider | Ping (s) | Ctx Latency (s) | Ctx Tokens | Notes |
|-------|----------|----------|-----------------|------------|-------|
| nvidia/nemotron-3-nano-30b-a3b | Nvidia | 0.4 | 0.7 | 14,669 | **Fastest.** 30B but handles context easily. |
| nvidia/openai/gpt-oss-120b | Nvidia | 0.4 | 0.7 | 12,978 | 120B via Nvidia proxy, fast and reliable. |
| kiro/claude-haiku-4.5 | Kiro | 1.8 | 3.0 | 19,727 | Good latency, high token count. |
| ollama-cloud/gemma4:31b | Ollama Cloud | 1.7 | 3.0 | 14,830 | Gemma 4 gen, stable on Ollama Cloud. |
| gemini/gemma-4-26b-a4b-it | Gemini (free API) | 17.4 | 26.3 | 14,819 | Works but slow first-connection. Usable as fallback. |

### ❌ FAIL (Remove from combo)

| Model | Error | Details |
|-------|-------|---------|
| openrouter/google/gemma-4-26b-a4b-it:free | 429 Rate Limit | Google AI Studio throttles OpenRouter free tier. Passes ping, fails 10K context. |
| cerebras/gpt-oss-120b | 404 Not Found | Model not deployed on Cerebras. |
| ollama-cloud/nemotron-3-super | 502 Error | Ollama Cloud endpoint broken or model unloaded. |
| ollama-cloud/minimax-m2.7 | 403 Forbidden | Ollama Cloud access denied for this model. |
| ollama-cloud/gpt-oss:120b | 404 Not Found | Model not found on Ollama Cloud. |
| sambanova/gpt-oss-120b | Timeout | 30s timeout on ping. SambaNova endpoint unresponsive. |
| qoder/qwen3-32b | 401 Auth | Credentials not configured for Qoder provider. |

## Key Findings

1. **Nvidia proxy is the best free performer** — both `nemotron-3-nano-30b` and
   `gpt-oss-120b` respond in <1s for 10K token contexts.
2. **Ollama Cloud is unreliable** — 3/4 Ollama Cloud models failed with 403/404/502.
   This may be a transient issue (models rotating on their platform) but shouldn't
   be the primary path for production retain.
3. **OpenRouter free tier is rate-limited** — Google AI Studio (upstream of
   `:free` Gemma models) throttles bulk traffic. This is a known upstream limitation.
4. **Kiro haiku is a good fallback** — 19K tokens processed in 3s, and Kiro's
   quotas are generous.
5. **67K token validation needed** — The audit used 10K tokens. The 5 PASS candidates
   should be verified at full 67K context to confirm they don't hit size limits at scale.

## Recommended Combo Configuration

```yaml
hindsight-retain-free:
  strategy: fill-first
  models:
    1. nvidia/nemotron-3-nano-30b-a3b   # Primary — fastest
    2. nvidia/openai/gpt-oss-120b        # Secondary — large model, fast
    3. kiro/claude-haiku-4.5             # Tertiary — good balance
    4. ollama-cloud/gemma4:31b           # Quaternary — Ollama Cloud backup
    5. gemini/gemma-4-26b-a4b-it         # Last resort — slow but free
```