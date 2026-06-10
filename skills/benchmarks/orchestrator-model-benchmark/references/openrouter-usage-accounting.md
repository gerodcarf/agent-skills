# OpenRouter Usage Accounting for Orchestrator Benchmarks

Use this when a benchmark request asks for token usage, cache usage, or cost for the full orchestrator suite.

## Lessons

- The default `managed_run.py` records scores but does not preserve full OpenRouter usage/cost details per scenario.
- OpenRouter returns useful accounting when the chat completion body includes:

```json
"usage": {"include": true}
```

- Read these fields from each response:
  - `usage.prompt_tokens`
  - `usage.completion_tokens`
  - `usage.prompt_tokens_details.cached_tokens`
  - `usage.prompt_tokens_details.cache_write_tokens`
  - `usage.completion_tokens_details.reasoning_tokens`
  - `usage.cost`
  - `usage.cost_details.upstream_inference_prompt_cost`
  - `usage.cost_details.upstream_inference_completions_cost`
- Cached tokens are included inside `prompt_tokens`; calculate uncached input as `prompt_tokens - cached_tokens`.
- For transparent reporting, include both actual billed cost and a no-cache equivalent if cache discounts materially affect totals.
- Do not rely on remembered sale/discount status. Fetch current OpenRouter model pricing immediately before reporting. Promotions change quickly.

## Cost formula

For a model with pricing values per token:

```text
actual_cost = (uncached_input_tokens * prompt_price)
            + (cached_input_tokens * input_cache_read_price)
            + (completion_tokens * completion_price)
```

If OpenRouter returns `usage.cost`, prefer that as the billed value and use the formula as a cross-check.

## Reporting shape

Minimum user-facing table for full-suite runs:

| Model | Run group | Score | Input tokens | Output tokens | Cached input | Reasoning tokens | Billed cost | No-cache equivalent |
|---|---:|---:|---:|---:|---:|---:|---:|---:|

Then include a per-scenario table with score, input, output, cached input, and cost.
