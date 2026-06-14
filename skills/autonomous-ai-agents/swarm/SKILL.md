---
name: swarm
description: "Launch a multi-model reasoning swarm on a question. Fan out to 5 workers (GLM-5.2, MiniMax-M3, DeepSeek-V4-Pro, Gemini-3.5-flash, GPT-5.5) at medium reasoning, gate through a reviewer, and auto-deliver the synthesis back to this thread."
version: 1.0.0
category: autonomous-ai-agents
---

# /swarm — Multi-Model Reasoning Swarm

Launch a Kanban Swarm that fans a question out to 5 specialized worker profiles in parallel, gates the outputs through a verifier, synthesizes a final report, and auto-delivers it back to the originating thread.

## Usage

```
/swarm <your question>
```

The text after `/swarm` is the research goal. Be specific — this becomes the prompt for all 5 workers.

## What Happens

1. **5 workers run in parallel** (all at medium reasoning):
   - `worker-cheap1` — GLM-5.2 (consistently top-scored analytical model)
   - `worker-cheap3` — MiniMax-M3 (framework innovator, surfaces novel angles)
   - `worker-cheap4` — DeepSeek-V4-Pro (quantitative depth)
   - `worker-frontier2` — Gemini-3.5-flash-medium (geopolitical/strategic framing)
   - `worker-frontier1` — GPT-5.5-medium (sourcing and citation rigor)
2. **Reviewer** (`reviewer` profile) cross-checks all outputs for contradictions and hallucinations
3. **Analyst** (`analyst` profile) synthesizes a single decision-ready report
4. **Auto-delivery** — the final report is posted back to this thread automatically

Expected wall time: ~8-12 minutes. Expected cost: ~$0.50-1.00.

## Execution

When invoked, immediately run this command. Do NOT plan or ask for confirmation — launch the swarm directly:

```bash
/Users/ambler/.hermes/hermes-agent/venv/bin/python \
  ~/agent-skills/skills/software-development/answer-panel/scripts/swarm.py \
  --preset swarm_default \
  --json \
  "<GOAL>"
```

Replace `<GOAL>` with the user's question (the text after `/swarm`). Escape any quotes in the goal text.

After the swarm launches, report the task IDs and worker assignments back to the user. Do NOT wait for completion — the synthesis will auto-deliver when done.

## How It Works

The `swarm_default` preset creates a Kanban DAG:
- Root card (shared blackboard)
- 5 parallel worker tasks (each under its own Hermes profile with isolated workspace)
- Reviewer task (gated — waits for all workers)
- Analyst/synthesizer task (gated — waits for reviewer)

The orchestrating session is subscribed to the synthesizer task via `hermes kanban notify-subscribe`, so the gateway auto-sends the final report to this thread when the analyst completes.

## Preset Configuration

Defined in `~/agent-skills/skills/software-development/answer-panel/scripts/presets.json` under `swarm_default`.

To change the worker roster, edit the preset. To use a different preset, run swarm.py manually with `--preset <name>`.

## Architecture Details

See [[Swarm Performance and Architecture - 2026-06-14]] and [[Swarm Efficiency - Medium vs High and Budget Synthesis - 2026-06-14]] for full architecture, model grading, and cost-quality analysis.

Also see the `kanban-swarm` skill for the full design pattern documentation.
