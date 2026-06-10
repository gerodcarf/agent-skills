# Hub and Spoke Benchmark Consolidation Pattern

When maintaining multiple variant benchmarks that evaluate different profile use cases (e.g., `clerk`, `bouncer`, `scout`, etc.), **avoid the temptation to merge them all into one monolithic `benchmark` skill**. This bloats the context and causes models testing one tier to process scoring logic for an unrelated tier.

Instead, use the **Hub and Spoke (Base class / Subclass)** architecture:

### 1. The \"Hub\" (Base Class): `benchmark-common`
Consolidate all **shared execution logic** here.
- **Scripts:** `benchmark-common/scripts/run_benchmark.py` handles `.env` loading, CLI parsing, OmniRoute proxy routing, model APIs, and generic scoring loops.
- **Templates:** Markdown templates or shared report scaffolders live in `benchmark-common/templates/`.
- **Docs:** `benchmark-common/SKILL.md` explains the dataset format required and the unified API.

### 2. The \"Spokes\" (Subclasses): `profile-benchmark`
Maintain distinct profile-bound skills (e.g., `bouncer-benchmark`, `clerk-benchmark`) with drastically reduced file footprints.
- **No duplicated execution code:** Subclasses must NOT contain their own `run_benchmark.py` or `.env` loaders.
- **Datasets & Rubrics Only:** They exclusively contain the specific profile's dataset (`dataset.jsonL`, etc.), passing criteria, and custom scoring logic if fundamentally different.
- **Documentation:** Their `SKILL.md` holds the specialized instructions and simply directs the Agent to call the canonical script in the Hub: `python3 ~/.hermes/skills/benchmarks/benchmark-common/scripts/run_benchmark.py --dataset ...`

### Why?
- **DRY (Don't Repeat Yourself):** API breakage or proxy updates only require patching `benchmark-common`.
- **Context Economy:** A `clerk` evaluator reads only the clerk criteria, not the logic for bounding boxes in `ocr` sweeps.