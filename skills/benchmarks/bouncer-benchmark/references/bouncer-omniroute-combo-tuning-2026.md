# Bouncer OmniRoute Combo Tuning (2026)

When configuring the OmniRoute combo for the Tier 5 Bouncer role (binary triage pre-filtering), follow these mandatory structural insights based on high-volume latency testing:

## 1. Strategy Selection: `fill-first` Only
Never use `auto` for the Bouncer combo. `auto` introduces unnecessary dynamic routing overhead that ruins the 200ms latency requirement. 
Use `fill-first` to guarantee a deterministic cascade that predictably exhausts 100% free/abundant quotas before touching paid safety nets.

## 2. Ideal Cascade Order (Free -> Resilient Paid)
A healthy bouncer combo should be stacked exactly like this:
1. **Speed Leaders (Free/Cheap):** `groq/llama-3.1-8b-instant` (averages ~26ms, burns free API tier) -> `cerebras/llama3.1-8b` -> `cf/@cf/meta/llama-3.1-8b-instruct` (all routinely clear Bouncer triages in ~200ms).
2. **Accuracy Fallback (Free/Abundant):** `bazaarlink/llama-3.3-70b-instruct`, `groq/llama-3.3-70b-versatile`, or `sambanova/Meta-Llama-3.3-70B-Instruct` (heavier models, better accuracy, but lower TPM limits. Put them *after* the 8B models so they don't hit 413 Payload Too Large limits under extreme load). 
3. **Structured Fallback (Paid):** `mistral/mistral-small-2506` or `mistral/mistral-small-latest` (fast, structured JSON, 100% accuracy on binary logic).
4. **Resilient Safety Net (Paid):** `antigravity/gemini-3.1-flash-lite` -> `antigravity/gemini-2.5-flash-lite`.

## 3. Toxicity: Missing Account IDs, Bad Aliases, & 120b Models
Do **not** include:
* `cloudflare-ai/@cf/meta/llama-3.3-70b-instruct` (Cloudflare strictly missing Account ID or deprecated alias in OmniRoute -> throws instant 502/400 errors blocking the cascade).
* `openrouter/mistralai/mistral-small-2506` (Invalid model ID alias on OpenRouter).
* `sambanova/gpt-oss-120b`, `ollama-cloud/deepseek-v4-flash`, or `gemma-4-26b:free` (They consistently `Timeout/Network Error` under strict latency caps. Because `fill-first` silently rolls over them, they inject an invisible ~5 second latency spike before reaching a working model).

## 4. API Pitfall: Streaming & Early EOF
When evaluating Bouncer models via Python `requests` or external scripts directly against the OmniRoute `/v1/chat/completions` endpoint, **always set `"stream": False`**.
OmniRoute often returns `HTTP 502: STREAM_EARLY_EOF` when interacting with Groq/Cerebras APIs for very short Bouncer prompt completions (`max_tokens=10`) if streaming is allowed to default to true or if the chunk size misaligns. Disabling stream guarantees a 200 OK.