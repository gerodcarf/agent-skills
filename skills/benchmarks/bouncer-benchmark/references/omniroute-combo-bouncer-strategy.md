# OmniRoute Combo Strategy: The Bouncer (Tier 5)

When configuring OmniRoute combos for high-volume binary triage (Bouncer) lanes, **always use the `fill-first` strategy**.

## Why `fill-first`?
`fill-first` guarantees a strict, deterministic cascade. It directs all volume to the #1 model in the list until rate limits (429s) or concurrency caps are hit, then spills predictably to #2. This is the only way to **predictably exhaust 100% free/abundant quotas** before falling back to reliable paid APIs.

## Why `auto` is Banned for Bouncer Combos
Do **not** use `auto` for Bouncer combos. 
- Bouncers require ultra-low, deterministic latency (~30ms) to clear high-volume queues.
- `auto` introduces routing logic overhead (calculating dynamic scores) and non-deterministic behavior, occasionally picking slower or "overkill" models that score well on secondary metrics, stalling the filtering pipeline.

## Bouncer Payload Constraints & Best Practices
- **Strict token limits:** Always force `max_tokens=10`.
- **Payload Bloat:** Models like `llama-3.3-70b-versatile` on free providers (e.g., Groq) have strict TPM limits (e.g., 12,000 TPM). Sending full documents quickly triggers `413 payload too large` or TPM exhaustion.
- **Context Trimming:** Aggressively trim context passed to the bouncer (first X chars only).
- **Target Selection:** Prefer ultra-fast 8B models (e.g., `groq/llama-3.1-8b-instant`, `cerebras/llama-3.1-8b`) for high-volume frontlines. They clear requests fast enough to handle queues without detonating TPM.
