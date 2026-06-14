---
name: answer-panel
description: Fan-out reasoning panel — send a prompt to N models in parallel, then judge/synthesize into a single answer. Own your own "Fusion."
version: 1.0.0
category: software-development
---

# Answer Panel

Send a prompt to multiple models in parallel, collect their responses, and use a judge model to synthesize them into a single best answer. Inspired by OpenRouter Fusion, but runs locally through OmniRoute with your own model selection and synthesis logic.

## When to Use

- **Hard reasoning questions** where a single model might miss or hallucinate
- **Adversarial fact-checking** — panel diversity catches individual model errors
- **High-stakes one-shot answers** where you want consensus + disagreement surfaced
- **Cost-effective frontier performance** — budget panels can rival frontier models

## When NOT to Use

- Simple factual lookups (one model is enough)
- Tasks that need state/corpus (use the research-pipeline skill instead)
- Tool-calling workflows (panel members are called as pure completion endpoints)
- Streaming/chat-style interactions

## Architecture

```
                    ┌──────────────┐
                    │   User Query │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ┌────────┐  ┌────────┐  ┌────────┐
         │ Model A│  │ Model B│  │ Model C│   ← parallel fan-out
         └───┬────┘  └───┬────┘  └───┬────┘
             │           │           │
             └───────────┼───────────┘
                         ▼
                  ┌─────────────┐
                  │ Judge Model │              ← reads all responses
                  │ (synthesis) │                  maps agreement/disagreement
                  └──────┬──────┘
                         ▼
                  ┌─────────────┐
                  │ Final Answer│              ← single grounded answer
                  └─────────────┘
```

## Quick Start

```bash
# Basic: default panel + judge
python3 scripts/panel.py "What are the top 3 non-obvious risks of investing in ASML right now?"

# Specify panel models
python3 scripts/panel.py --panel "gemini-cli/gemini-3.1-pro-preview,xai/grok-4.3,openrouter/deepseek/deepseek-v4-pro" "Your question"

# Use a named preset
python3 scripts/panel.py --preset budget "Your question"

# Asynchronous Agentic Swarm (using Kanban and active Profiles)
# Spawns parallel worker cards, gates them with a reviewer task, and synthesizes via analyst.
# Subscribes the active Discord thread so findings are auto-delivered back here!
python3 scripts/swarm.py "Assess the Defensibility of ASML's EUV technology through 2030"
```

## Kanban Swarm Mode

For complex queries that require tool use (web search, reading codebase files, context mapping) or when utilizing slow reasoning-only models, we can orchestrate the panel using a native **Kanban Swarm**.

### When to Use Swarm
- **Tool usage is required**: Workers need to run web searches, read local project directories, or execute code rather than just act as text-only completion endpoints.
- **Asynchronous durability**: Overcomes API connection timeouts for extremely slow models (e.g. DeepSeek R1 reasoning) by running tasks in background worker shells.
- **Profile-specific models & contexts**: Each worker runs inside its respective profile namespace and uses its configured model and environmental variables.

### Swarm Topology
1. **Root Card** (`t_xxxx`): Shared blackboard (`[swarm:blackboard]`). Completed immediately.
2. **Specialists** (running in parallel once root completes):
   - `scout` (Macro shifts, talent movement, strategic positioning)
   - `researcher` (Web search & Perplexity fact gathering)
   - `clerk` (Local codebase & structural inspection)
3. **Verifier** (`reviewer`): Gated dependency. Reviews and compares findings, resolves contradictions.
4. **Synthesizer** (`analyst`): Synthesizes findings into the final Markdown report.

### Notification Integration
The script automatically parses the active chat environment variables (`HERMES_SESSION_PLATFORM`, `HERMES_SESSION_CHAT_ID`, `HERMES_SESSION_THREAD_ID`) and subscribes them to the final Synthesizer task. Once the `analyst` finishes the report, it is posted back to the Discord thread automatically.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OMNIROUTE_BASE_URL` | `http://localhost:20128/v1` | OmniRoute proxy endpoint |
| `OMNIROUTE_API_KEY` | *(empty — local proxy needs none)* | API key if using remote endpoint |
| `PANEL_DEFAULT_PANEL` | `gemini-cli/gemini-3.1-pro-preview,openrouter/x-ai/grok-4.3,openrouter/deepseek/deepseek-v4-pro` | Default panel models |
| `PANEL_DEFAULT_JUDGE` | `orchestrator` | Default judge (OmniRoute combo or model slug) |

## Presets

Named panel configurations in `scripts/presets.json`. Override or extend freely.

| Preset | Panel | Judge | Cost | Use Case |
|--------|-------|-------|------|----------|
| `default` | Gemini Pro + Grok 4.3 + DeepSeek V4 | orchestrator | Medium | General-purpose reasoning |
| `budget` | DeepSeek Flash + Qwen 3.6 + Grok 4.20 | clerk | Low | Cost-sensitive bulk reasoning |
| `frontier` | Claude Opus 4.7 + GPT-5.5 High + Grok 4.3 | jumbo | High | Max quality, money no object |
| `diverse` | Claude Sonnet + Gemini + Grok + DeepSeek + Qwen | jumbo | Medium-High | Max diversity for hard problems |
| `adversarial` | Gemini Pro (pro) + DeepSeek (skeptic) + Grok (realist) | researcher | Medium | Fact-checking, devil's advocate |

## How It Works

1. **Fan-out**: The query is sent to each panel model in parallel via `concurrent.futures.ThreadPoolExecutor`. Each model gets the same system prompt (if provided) and user query. Non-streaming (`stream=false`) for simplicity.

2. **Collection**: Panel responses are collected with their model name, content, and any errors. Failed models are flagged but don't block the panel — a 3-model panel where 1 fails still synthesizes from 2.

3. **Judge synthesis**: The judge model receives all panel responses (anonymized to "Panelist A/B/C" to avoid brand bias) plus a synthesis prompt that asks it to:
   - Identify where panelists agree (high confidence)
   - Identify where they disagree (flag for the user)
   - Note what each covered vs. missed
   - Produce a final grounded answer

4. **Output**: The final answer is printed. With `--json`, the full structure (individual panelist responses + judge synthesis) is returned.

## Programmatic Usage (Python)

```python
import subprocess, json

def ask_panel(question, panel_models=None, judge=None, system=None):
    """Call the panel and return structured result."""
    cmd = ["python3", "scripts/panel.py", "--json"]
    if panel_models:
        cmd += ["--panel", ",".join(panel_models)]
    if judge:
        cmd += ["--judge", judge]
    if system:
        cmd += ["--system", system]
    cmd.append(question)
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=SKILL_DIR)
    return json.loads(result.stdout)

# Example
result = ask_panel(
    "Is Centrus Energy's HALEU monopoly defensible through 2030?",
    panel_models=["xai/grok-4.3", "gemini-cli/gemini-3.1-pro-preview"],
    judge="frontier",
    system="You are a nuclear fuel cycle analyst."
)
print(result["synthesis"])  # Final answer
print(result["disagreements"])  # Where models diverged
```

## Integration with Other Skills

- **research-pipeline**: Use answer-panel for Stage 5 (synthesis) — fan out the synthesis prompt to a panel instead of a single analyst model
- **gray-rhino**: Tripwire evaluation — get panel consensus on whether a catalyst is real
- **bouncer-benchmark**: The panel itself is a bouncer (binary pre-filter), but with consensus

## Customization

### Custom Synthesis Logic

The judge prompt template is in `scripts/panel.py` as `JUDGE_PROMPT`. Override it by creating a `judge_prompt.txt` file in the working directory or passing `--judge-prompt-file`.

### Custom Presets

Add your own to `scripts/presets.json`:

```json
{
  "my-custom-panel": {
    "panel": ["model1", "model2", "model3"],
    "judge": "frontier",
    "description": "My custom reasoning panel"
  }
}
```

## Pitfalls

- **Streaming is off**: Panel calls use `stream=false` for simplicity. This means higher latency (each model must complete fully before returning). For long generations, this can take 30-60s per model. Parallelism mitigates this.
- **OmniRoute combo names vs raw models**: Both work. `clerk` (combo) routes through OmniRoute's provider chain. `gemini-cli/gemini-3.1-pro-preview` (raw model) hits one provider. Combos are more resilient (auto-fallback); raw models are more predictable.
- **Cost**: Fan-out means N× the cost of a single call. Budget presets exist for a reason. For expensive panels, use `--max-tokens` to cap each response.
- **Judge is the bottleneck**: The judge call is sequential (waits for all panelists). Use a fast judge combo if latency matters.
- **Context limits**: Each panelist response goes into the judge's context. Very long panelist responses (10k+ tokens each) with large panels (5+ models) can exceed the judge's context window. Use `--max-tokens` to keep panelist responses bounded.

## Verification

```bash
# Smoke test — panel should return a synthesized answer
python3 scripts/panel.py "What is 2+2?" --preset budget

# Verify JSON output
python3 scripts/panel.py --json "What is 2+2?" --preset budget | python3 -m json.tool
```
