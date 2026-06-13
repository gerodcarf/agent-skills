---
name: hindsight-model-benchmark
description: Benchmark models for Hindsight retain compatibility — context-size tolerance, structured JSON extraction quality, OmniRoute routing, and provider quota headroom.
category: benchmarks
version: 0.2.0
pinned: false
---

# Hindsight Model Benchmark

## Purpose

Use this skill when evaluating or troubleshooting models/routes for Hindsight's `retain_extract_facts` pipeline, especially the `hindsight-retain` OmniRoute combo.

Hindsight retain is not a generic short-prompt extraction workload. Realistic retains can send very large prompts — observed/synthetic test payloads around **67K input tokens** — so provider context acceptance and TPM quota are first-class pass/fail gates.

## Triggers

- "benchmark hindsight-retain"
- "hindsight retain model"
- "Hindsight request too large"
- "retain_extract_facts"
- "test models for Hindsight"
- "OmniRoute hindsight-retain routing"
- "structured extraction model for memory retain"

## What to evaluate

Benchmark each candidate across three axes:

1. **Context-size acceptance** — Can the model/provider accept a ~67K-token retain prompt without 400/413/request-too-large failures?
2. **Structured JSON extraction quality** — Does it return valid schema-compliant fact extraction, not just plausible prose?
3. **Rate-limit / TPM headroom** — Does the provider tolerate expected active-use traffic? Hindsight can retain roughly once per conversation turn, plus async/burst behavior.

## Known failure mode

Groq `openai/gpt-oss-20b` was previously unsuitable as the configured retain backend on a low/free tier because the provider quota was about **8K TPM**, far below the ~67K-token retain payload. The model may appear available while still failing a single retain request due to provider quota.

## OmniRoute `hindsight-retain` checklist

When the backend is an OmniRoute combo, do not stop at checking that the combo list looks correct.

1. Verify the configured combo priority order.
2. Trigger one real Hindsight retain with a unique marker.
3. Inspect OmniRoute runtime logs for the `hindsight-retain` request.
4. Confirm candidates survived compatibility/capability filtering.
5. Confirm the actual first provider/model attempted.
6. Confirm the retain completed successfully.

Important pitfall: the combo priority order can be correct while OmniRoute compatibility filtering removes targets before execution. If so, fix the provider capability/source-override layer, restart OmniRoute, then verify with a live retain marker and logs.

## Verification marker pattern

Use a unique marker so logs and Hindsight recall can be tied to the exact test:

```text
Routing verification marker at <timestamp> after source-level OmniRoute capability override and restart. Success criterion: hindsight-retain keeps all intended targets and tries the preferred first target.
```

Then run/trigger Hindsight retain and inspect OmniRoute logs for:

- request path/model showing `hindsight-retain`,
- candidates retained after compatibility filtering,
- actual provider/model attempted first,
- final success/failure.

## Candidate notes

A prior benchmark identified `groq/openai/gpt-oss-120b` as a strong candidate in that run: high structured extraction quality and no marginal cost in the tested route. Treat this as a lead, not a permanent fact; provider quotas and routing behavior can change, so re-test before relying on it.

## References

- `references/omniroute-hindsight-retain-routing.md` — session-derived notes on the 67K-token constraint, Groq `gpt-oss-20b` TPM failure mode, and OmniRoute compatibility-filter verification.