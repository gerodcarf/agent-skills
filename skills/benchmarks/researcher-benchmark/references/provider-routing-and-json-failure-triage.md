# Provider routing and JSON-failure triage notes

Session-derived guidance for running the researcher benchmark against provider-routed models.

## Provider/model namespace matters

When a user asks for a direct provider run, preserve the provider and model exactly as requested:

- Direct OpenRouter: `--provider openrouter --model stepfun/step-3.7-flash`
- OmniRoute-routed OpenRouter: `--provider omniroute --model openrouter/stepfun/step-3.7-flash`
- OmniRoute-routed Nvidia: `--provider omniroute --model nvidia/stepfun-ai/step-3.7-flash`

Do not treat these as interchangeable. If the user corrects the route, rerun using the corrected provider/model pair rather than explaining route availability.

## Diagnosing 0.000 researcher-benchmark runs

A `0.000` score does not always mean the model lacks domain knowledge. First inspect `benchmark_cases.notes`, `response`, token counts, and truncation symptoms.

Common strict-JSON failure pattern observed with `openrouter` / `stepfun/step-3.7-flash`:

- All cases failed with `invalid JSON: Expecting value: line 1 column 1 (char 0)`.
- Responses began with prose such as `Got it, let's tackle this step by step...` before any JSON.
- Each case hit the `--max-tokens 4000` cap and responses were often truncated.
- Some raw responses contained required semiconductor terms and source IDs, but the scorer rejected them because the entire response was not parseable strict JSON.
- Historical-cycle cases can still fail temporal discipline even when semantically rich; check `forbidden_terms` hits for lookahead leakage such as later AI-cycle terms in 2018-2019 cases.

Interpretation pattern for future reports: distinguish **output-contract failure** (invalid JSON, prose wrapper, truncation), **semantic/content failure** (missing required terms/sources/action), and **temporal-discipline failure** (forbidden lookahead terms).