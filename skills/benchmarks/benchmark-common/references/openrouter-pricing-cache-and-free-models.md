# OpenRouter pricing cache and free-model benchmark notes

Session-derived benchmark lesson (2026-06-06):

- When a benchmark runner compares multiple OpenRouter models, fetch `/api/v1/models` pricing once per run and reuse an in-memory pricing cache. Re-fetching per case/model is slow and creates avoidable API churn.
- Normalize direct API cost fields defensively: some response paths expose `usage.cost`, while benchmark DB/reporting code may carry the same value as `cost_usd`. Treat both as aliases before falling back to pricing-table computation.
- OpenRouter `:free` models may correctly report `$0.000000` even when token counts are non-zero; do not classify that as missing cost if the model id is a free tier and the pricing cache confirms zero prices.
- Free frontier-sized models can be useful for batch/off-hours benchmark roles even when latency is poor. In one Researcher benchmark, `nvidia/nemotron-3-ultra-550b-a55b:free` tied DeepSeek quality (`0.9467`, 3/3) at zero cost, but averaged ~160s/case.
- Always report real run IDs, score/pass/latency/tokens/cost, and any scoring notes so routing decisions can separate quality, cost, and throughput.
