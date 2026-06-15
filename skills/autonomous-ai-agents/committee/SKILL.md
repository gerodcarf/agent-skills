---
name: committee
description: "Launch a multi-model reasoning committee on a question. Fan out to 6 workers (GLM-5.2, MiniMax-M3, DeepSeek-V4-Pro, Gemini-3.5-flash, GPT-5.5, Grok-4.3) at medium reasoning, gate through a reviewer, and auto-deliver the synthesis back to this thread."
version: 1.0.0
category: autonomous-ai-agents
---

# /committee — Multi-Model Reasoning Committee

Launch a Kanban Committee that fans a question out to 6 specialized worker profiles in parallel, gates the outputs through a verifier, synthesizes a final report, and auto-delivers it back to the originating thread.

## Usage

```
/committee <your question>
```

The text after `/committee` is the research goal. Be specific — this becomes the prompt for all 5 workers.

## What Happens

1. **6 workers run in parallel** (all at medium reasoning):
   - `worker-cheap1` — GLM-5.2 (consistently top-scored analytical model)
   - `worker-cheap3` — MiniMax-M3 (framework innovator, surfaces novel angles)
   - `worker-cheap4` — DeepSeek-V4-Pro (quantitative depth)
   - `worker-frontier1-librarian` — Gemini-3.5-flash-medium (librarian context compiler + research lane)
   - `worker-frontier2` — GPT-5.5-medium (sourcing, detail mapping & citation rigor)
   - `worker-frontier4` — Grok-4.3 (frontier4; adversarial/frontier reasoning)
2. **Every worker must produce source-traceable output**: a `Source Ledger`, a `Claim Register`, and material claims linked to stable source IDs (e.g. `worker-frontier1-S01`). Workers should distinguish original sources from KOS context, note access date/path/URL, and quote or line-reference the evidence behind each key claim.
3. **Reviewer** (`reviewer` profile) cross-checks all outputs for contradictions and hallucinations **and performs a source credibility audit**. The reviewer should mark source IDs as primary/secondary, timely/stale, direct/indirect, credible/questionable, and explicitly identify unsupported claims that must not carry forward.
4. **Analyst** (`analyst` profile) synthesizes a single decision-ready report **with a traceability appendix**. The final synthesis must preserve source details and trace back key claims to stable source IDs rather than citing only "worker analysis."
5. **Auto-delivery** — the final report is posted back to this thread automatically

Expected wall time: ~8-12 minutes. Expected cost: ~$0.50-1.00.

## Execution

When invoked, immediately run this command. Do NOT plan or ask for confirmation — launch the committee directly:

```bash
/Users/ambler/.hermes/hermes-agent/venv/bin/python \
  ~/agent-skills/skills/software-development/answer-panel/scripts/committee.py \
  --preset committee_default \
  --json \
  "<GOAL>"
```

Replace `<GOAL>` with the user's question (the text after `/committee`). Escape any quotes in the goal text.

After the committee launches, report the task IDs and worker assignments back to the user. Do NOT wait for completion — the synthesis will auto-deliver when done.

## How It Works

The committee_default preset creates a Kanban DAG:
- Root card (shared blackboard)
- 6 parallel worker tasks (each under its own Hermes profile with isolated workspace)
- Reviewer task (gated — waits for all workers)
- Analyst/synthesizer task (gated — waits for reviewer)

The orchestrating session is subscribed to the synthesizer task via `hermes kanban notify-subscribe`, so the gateway auto-sends the final report to this thread when the analyst completes.

## Preset Configuration

Defined in `~/agent-skills/skills/software-development/answer-panel/scripts/presets.json` under `committee_default`.

To change the worker roster, edit the preset. To use a different preset, run committee.py manually with `--preset <name>`.

## Source Traceability protocol

For research/investment committees, source tracing is mandatory because final synthesis otherwise becomes a meta-analysis of worker prose and loses provenance.

### Worker Traceability Deliverables
Each worker must write a markdown report containing:
- `## Source Ledger`: Table of Source ID, Type, Title/Name, URL or local path, Date/Access date, Why used, and Credibility notes.
- `## Claim Register`: Table of Claim ID, Claim, Source IDs, Confidence, and Notes/Caveats.
- Prefix IDs with worker name (e.g., `worker-frontier1-S01`, `worker-frontier1-C03`).
- Factual claims, market-size figures, ticker mappings, and catalysts must cite a Source ID.
- Differentiate fact from inference: cite facts directly, label inference, and cite the facts it depends on.
- Include skepticism for low-credibility sources (such as promotional IR, stale articles, or unsourced web summaries).

### Reviewer Credibility Audit Deliverables
The reviewer must produce:
- `## Source Credibility Audit`: Table of Source ID, Worker, Primary/secondary, Timeliness, Directness, Credibility verdict, Carry forward? (Y/N), and Notes.
- `## Unsupported or Weakly Supported Claims`: Table of Claim ID, Claim, Problem, and Required fix.
- Verify that keys are tied to stable source IDs and that original paths or URLs are recoverable.
- The reviewer must block the swarm if key claims lack source IDs, rely on unvetted model memory without sources, or source links are missing or non-recoverable.

### Synthesizer Carry-Through Deliverables
The final synthesis must contain:
- `## References / Source Traceability` table at the end of the report representing: Final claim, Worker claim IDs, Source IDs, Original references.
- Inline citations using Source IDs (e.g. `[worker-frontier1-S01]`) for key factual points, numbers, and catalysts.
- Do not introduce new material factual claims without source IDs and references.
- Do not include claims marked by the verifier as failed or unsupported unless framing them as disputed.

## Architecture Details

See [[Swarm Performance and Architecture - 2026-06-14]] and [[Swarm Efficiency - Medium vs High and Budget Synthesis - 2026-06-14]] for full architecture, model grading, and cost-quality analysis.

Also see the `kanban-swarm` skill for the full design pattern documentation.
