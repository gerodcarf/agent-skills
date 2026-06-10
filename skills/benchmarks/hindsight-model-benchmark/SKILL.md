---
name: hindsight-model-benchmark
description: "Benchmark models for Hindsight retain compatibility — tests input context size tolerance (~67K tokens), structured JSON extraction quality, and rate-limit/TPM headroom. For evaluating candidate models to replace Groq/gpt-oss-20b in Hindsight's retain_extract_facts pipeline."
category: benchmarks
version: 0.1.0
pinned: false
---

# Hindsight Model Benchmark

## Purpose

Evaluate whether OpenAI-compatible models can serve as the LLM backend for
Hindsight's `retain_extract_facts` pipeline. Tests three axes:

- **Context size tolerance** — Can the model accept ~67K input tokens without 413/400 errors?
- **JSON extraction quality** — Does it return valid, schema-compliant fact extraction?
- **Rate-limit headroom** — How many requests/minute before 429s?

This benchmark was created after Groq's `openai/gpt-oss-20b` (Hindsight's
configured retain model) started returning HTTP 413 "Request too large" —
Groq free tier caps at 8K TPM, while each retain sends ~67K tokens.

## Triggers

"hindsight benchmark", "hindsight model test", "test models for hindsight",
"rate limit risk hindsight"

## Quick Start

```bash
cd ~/.hermes/skills/benchmarks/hindsight-model-benchmark

# Run against a single model through OmniRoute
python3 scripts/run_hindsight_benchmark.py run \
  --provider omniroute \
  --model google/gemma-4-26b-a4b-it:free

# Run through OmniRoute combo
python3 scripts/run_hindsight_benchmark.py run \
  --provider omniroute \
  --model hindsight-retain

# Run multiple models (one at a time for clean rate-limit measurement)
python3 scripts/run_hindsight_benchmark.py run \
  --provider omniroute \
  --models google/gemma-4-26b-a4b-it:free openai/gpt-oss-120b:free

# Run through OpenRouter directly
python3 scripts/run_hindsight_benchmark.py run \
  --provider openrouter \
  --model google/gemma-4-26b-a4b-it:free

# Rate-limit stress test (burst N requests)
python3 scripts/run_hindsight_benchmark.py ratelimit \
  --provider omniroute \
  --model hindsight-retain \
  --burst 10 \
  --stagger 2

# Show leaderboard from all prior runs
python3 scripts/run_hindsight_benchmark.py leaderboard

# Regenerate Obsidian markdown
python3 scripts/run_hindsight_benchmark.py update-summary
```

## Test Battery

### H1: Context Size Acceptance
**Goal:** Verify the model accepts ~67K tokens of input without size/quota errors.
- Sends a realistic Hindsight retain payload (synthetic conversation text at
  ~67K tokens) to `chat/completions`
- Measures success/failure and any HTTP error codes
- **Metrics:** Acceptance (boolean), error code on failure

### H2: Structured JSON Extraction
**Goal:** Verify the model can extract facts from large context into valid JSON.
- Same large context, instructs model to extract structured facts
  (key decisions, preferences, tool quirks, environment facts)
- Measures JSON parse rate, schema compliance, and extraction quality
- **Metrics:** JSON valid, field count extracted, schema compliance %

### H3: Rate Limit Stress
**Goal:** Measure how many requests/minute the model handles before 429.
- Sends sequential requests at configurable stagger intervals
- Records success/failure per request and identifies the breaking point
- **Metrics:** Max RPM before 429, total successful in burst, time-to-limit

## Test Payloads

The benchmark generates realistic payloads via synthetic conversation text
that mimics how Hindsight constructs its `retain_context`. The synthetic text
is a concatenation of realistic agent-user exchanges, tool calls, and system
messages until it reaches the target token count.

**Default target:** ~67,000 input tokens (Hindsight's observed average).
**Adjustable via:** `--target-tokens N`

## Scoring

| Dimension | Weight | What It Tests |
|-----------|--------|--------------|
| Context Acceptance | 30% | Does it accept 67K input? (pass/fail) |
| JSON Validity | 25% | Parseable JSON output with correct schema |
| Extraction Quality | 25% | Meaningful facts extracted (not garbage) |
| Rate Limit Headroom | 20% | How many RPM before 429? |

## Database and Artifacts

Results in `results/hindsight-benchmark.db`.

```sql
runs(
  id, run_id, provider, requested_model, actual_model,
  scenario, timestamp, status, accuracy, json_valid,
  latency_seconds, input_tokens, output_tokens, cost_usd,
  response_sample, error_message, rate_limit_max_rpm
)
```

Obsidian output:
- `~/Obsidian/Main Vault/40-Operations/Hermes/Benchmarks/hindsight-model-benchmark/hindsight-model-overview.md`
- `~/Obsidian/Main Vault/40-Operations/Hermes/Benchmarks/hindsight-model-benchmark/hindsight-model-results.md`

## Models to Evaluate

Candidate replacements for `groq/openai/gpt-oss-20b`:

| Model | Input $/M | Output $/M | Notes |
|-------|-----------|------------|-------|
| `google/gemma-4-26b-a4b-it:free` | $0 | $0 | Free, 262K ctx — proven stable, but check TPM |
| `google/gemma-4-26b-a4b-it` | $0.07 | $0.35 | Paid, 262K ctx, stable |
| `openai/gpt-oss-120b:free` | $0 | $0 | Frontier 120B, free tier, may have TPM limits |
| `nvidia/nemotron-3-super-120b-a12b:free` | $0 | $0 | Frontier 120B, free tier |
| `meta-llama/llama-3.3-70b-instruct:free` | $0 | $0 | Frontier 70B, free tier — may not support 67K |
| `qwen/qwen3-32b:free` | $0 | $0 | Free tier; Qwen handles long context well |
| `qwen/qwen3.6-plus` | $0.20 | $0.60 | Nous-hosted, known stable |

**Note:** Frontier model free tiers on OpenRouter may have hidden TPM/RPM
limits that only appear under burst load. Always run the `ratelimit` subcommand.

## Pitfalls

- **Groq 8K TPM trap.** `openai/gpt-oss-20b` on Groq free tier caps at 8K tokens/minute.
  A 67K request fails immediately (HTTP 413). This is the current failure mode.
- **Free Gemma 401s on OpenRouter.** `google/gemma-4-26b-a4b-it:free` returns 401 —
  Google rejects credential passthrough for free tiers. Test before relying on it.
- **urllib timeouts on macOS.** Use `curl`-based calls like `benchmark_common.py` does.
- **Stream mode breaks parsing.** Always set `stream: false` in payloads.
- **67K input token estimation.** Token counts are estimated by character count / 4.
  Actual tokenizer counts vary. The benchmark uses a generous synthetic payload.
- **OpenRouter provider/model format.** When using `--provider openrouter`, the model
  argument should NOT include the `openrouter:` prefix.
- **OmniRoute combos.** When benchmarking through an OmniRoute combo, the actual
  model used may differ from `requested_model`. Record `actual_model` from the response.
- **Rate limit bursts can cascade.** Running multiple models' rate-limit tests back-to-back
  may cause OpenRouter-wide throttling on the IP. Stagger runs by 30s between models.

## Combo Member Audit

When auditing individual models within an OmniRoute combo (e.g., `hindsight-retain-free`),
use `scripts/audit_retain_combo.py` instead of `run_hindsight_benchmark.py`. It:
- Reads the OmniRoute Hermes API key automatically from the local SQLite DB.
- Tests each combo member individually via `POST /v1/chat/completions` at `http://localhost:20128`.
- Two-phase test: (1) small ping (10 tokens), (2) context-size test (~10K tokens).
- Classifies results: PASS (<30s), SLOW (>30s), CTX-FAIL, RATE-LIM, NOT-FOUND, AUTH, TIMEOUT.
- Outputs a summary table with explicit keep/remove recommendations.

```bash
python3 scripts/audit_retain_combo.py
```

The audit uses smaller payloads (10K tokens) for speed. After identifying candidates that
pass the 10K test, run the full `run_hindsight_benchmark.py` at 67K tokens to validate
actual Hindsight-scale context handling.

## Execution Path
`~/.hermes/skills/benchmarks/hindsight-model-benchmark/`
