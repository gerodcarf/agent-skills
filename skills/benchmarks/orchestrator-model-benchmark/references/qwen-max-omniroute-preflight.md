# Qwen-Max / OmniRoute orchestrator benchmark pre-flight

Use this reference when benchmarking large-context orchestrator candidates routed through OmniRoute, especially Qwen-Max deployments.

## Failure mode: plausible output from fallback model

A quick `hermes chat` smoke test can appear successful even when the target model failed and Hermes answered via a fallback provider. In the observed case, `orchestrator-jumbo` pointed at Qwen-Max, but the first call failed with:

```text
HTTP 400: [400]: <400> InternalError.Algo.InvalidParameter: Range of input length should be [1, 30720]
```

Hermes then fell back to `stepfun/step-3.7-flash:free`, producing a plausible response. A full benchmark would have been contaminated if logs were not checked.

## Why it happened

Full Hermes orchestrator payloads can exceed 30k tokens before the user prompt because the system context includes tool schemas, skills catalog, memories, and instructions. The observed orchestrator payload was about `35,342` input tokens, over the Alibaba/Qwen endpoint cap of `30,720`. A Nous-hosted Qwen-Max deployment accepted the same payload.

## Required pre-flight before scoring

1. Run an isolated one-turn prompt against the exact provider/model being benchmarked:

```bash
hermes chat -q "test" -m "<model-or-combo>" --provider <provider> --max-turns 1 -Q
```

For OmniRoute combos, use the explicit OmniRoute provider flag, for example:

```bash
hermes chat -q "test" -m "orchestrator-jumbo" --provider omniroute --max-turns 1 -Q
```

2. Inspect Hermes logs, not just CLI output:

```bash
grep -i "fallback\|<model-or-combo>\|Range of input length" ~/.hermes/logs/agent.log | tail -n 40
```

3. Confirm there is no fallback activation and the log line shows the intended `provider`, `base_url`, and `model`.

4. If a run label is used instead of the full model ID, map it back in the report response. Example: `qwen-max-run` was the benchmark label for `omniroute:nous/qwen/qwen3.7-max`.

## Result inspection pattern

The orchestrator benchmark DB stores one row per scenario in `runs`, not a single aggregate table. Aggregate manually:

```sql
SELECT timestamp, model, scenario, total
FROM runs
WHERE model = '<run-label>'
ORDER BY timestamp DESC;

SELECT SUM(total) AS total_score, COUNT(*) * 18 AS max_score
FROM runs
WHERE model = '<run-label>';
```

The bundled report helper also works:

```bash
python3 ~/.hermes/skills/benchmarks/orchestrator-model-benchmark/scripts/score_history.py --model <run-label> --report
python3 ~/.hermes/skills/benchmarks/orchestrator-model-benchmark/scripts/score_history.py --compare
```
