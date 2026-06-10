# Clerk fallback model benchmark notes — 2026-05-09

Context: evaluating strict JSON / Neo4j-ingestion fallback models for the `clerk` Hermes profile and OmniRoute `clerk` combo.

## Key results

| Model | Provider path | Score | Ingestion-ready | Avg latency | Tokens | Est. cost | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| `gemini/gemini-2.5-flash-lite` | OmniRoute | 0.896 | 7/8 | 2659 ms | 26,059 | $0.004274 | Best cheap strict-JSON fallback |
| `gemini/gemini-3.1-flash-lite-preview` | OmniRoute | 0.877 | 6/8 | 8112 ms | 24,956 | $0.003833 | Slower and weaker; do not prefer |
| `cerebras/qwen-3-235b-a22b-instruct-2507` | OmniRoute | partial only | 4/7 in partial paced run | unstable | — | $0/free lane | Useful only as low-weight opportunistic combo member; raw lane hits 429s |

## Recommendation

For profile-level emergency fallback, prefer:

```yaml
fallback_providers:
  - provider: gemini
    model: gemini-2.5-flash-lite
```

If direct Gemini credentials are not available in the runtime environment, route through OmniRoute:

```yaml
fallback_providers:
  - provider: omniroute
    model: gemini/gemini-2.5-flash-lite
```

Keep Cerebras/Qwen as a small-weight member inside the OmniRoute combo, not as the primary or profile-level fallback. It can produce good Clerk JSON, but sustained standalone calls trigger provider RPM limits and poison benchmark results with 429s.

## Failure modes observed

- Direct OpenRouter call for `cerebras/qwen-3-235b-a22b-instruct-2507` returned `HTTP 401: No cookie auth credentials found`; use OmniRoute for this lane in Gerod's setup.
- Cerebras sustained benchmark runs hit `HTTP 429: Requests per minute limit exceeded`. The benchmark runner needed actual retry/backoff; `--max-retries` existed but was not used before patching.
- `gemini/gemini-2.5-flash-lite` failed only one case due to enum drift (`SUPPLIED_TO` instead of allowed `SUPPLIES`), not JSON validity. This is prompt/post-normalization territory, not model disqualification.
- `gemini/gemini-3.1-flash-lite-preview` was valid/reachable but slower and less reliable than 2.5 Flash-Lite.

## Cost handling lesson

Benchmark runners must price OmniRoute/proxy runs, not just direct OpenRouter runs. Missing price coverage must not silently show `$0.000000` for paid models. Add model aliases to `FALLBACK_PRICING_PER_TOKEN` before trusting the Obsidian cost column.

Pricing used for Gemini Flash-Lite variants in this session: `$0.10/M input`, `$0.40/M output`.
