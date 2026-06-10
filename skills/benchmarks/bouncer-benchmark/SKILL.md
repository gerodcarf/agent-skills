---
name: bouncer-benchmark
description: "Protocol for high-speed binary (YES/NO) pre-filtering of data streams. Documents the Bouncer role: using 8B models on Groq/Cerebras to protect higher-intelligence tiers from noise, with benchmarking for 200ms-level latency."
triggers:
  - fast and dumb
  - binary triage
  - bouncer protocol
  - high volume filtering
  - noise reduction
pinned: true
---

# Fast and Dumb Triage (The Bouncer Protocol)

## Overview

The **Fast and Dumb (Tier 5)** protocol focuses on raw latency and binary logic to act as a "Bouncer" for high-volume data streams (DoD awards, RSS feeds, logs). It filters out 90%+ of noise before data enters more expensive "Structured" (Tier 4) or "Reasoning" (Tier 1) tiers.

## The Bouncer vs. The Clerk

| Feature | The Bouncer (Tier 5) | The Clerk (Tier 4) |
| :--- | :--- | :--- |
| **Primary Goal** | Noise Reduction (Yes/No) | Extraction (JSON/CSV) |
| **Model Class** | Llama 3.1/3.2 8B / 1B | Gemini 2.5 Flash Lite |
| **Latency Target** | <300ms | <1s |
| **Fail Mode** | False Positives | Schema Violation ("Yapping") |

## Implementation Workflow

### 1. Model Selection (2026-04-22 Stats)
- **Primary Accuracy Leader:** `groq/llama-3.3-70b-versatile` (100% accuracy, ~350ms latency). Optimized for edge cases that trip up 8B models.
- **Primary Speed Leader:** `groq/llama-3.1-8b-instant` (Latency: ~210ms, 80% extraction acc).
- **Free King:** `cerebras/llama-3.1-8b` (Latency: ~290ms, 1M free daily tokens).
- **Just-in-Case Fallback:** `openrouter/google/gemini-2.5-flash-lite` (Extreme stability if LPUs are down).

### 2. Prompting for speed
Triage prompts must be extremely restrictive to avoid "yapping" (conversational filler) which adds latency and can break basic logic checks.
```text
Is this a deep-tech award >$50M? Return ONLY 'YES' or 'NO'.
Award: {text}
```

### 3. Benchmarking Script
Use direct API calls (bypassing the gateway) to measure raw provider latency. Use `op read` for secure key handling.
```python
# key snippet for latency tracking
t0 = time.time()
r = requests.post(url, headers=headers, json=payload)
latency = time.time() - t0
```

## Pitfalls & Lessons Learned

- **The "Smart Model" Failure:** Highly intelligent models (like Gemini 2.0 Flash Lite) and newer 3.2 family models often fail Tier 5 triage because they provide conversational filler (e.g., "Yes, this is an award...").
- **Mitigation (Intensity Prompting):** To ensure 100% adherence, use extreme constraint prompting: "Return ONLY the word YES or NO. Any other text will result in a failure."
## Pitfalls & Lessons Learned

- **The "Smart Model" Failure:** Highly intelligent models (like Gemini 2.0 Flash Lite) and newer 3.2 family models often fail Tier 5 triage because they provide conversational filler (e.g., "Yes, this is an award...").

- **Mitigation (Intensity Prompting):** To ensure 100% adherence, use extreme constraint prompting: "Return ONLY the word YES or NO. Any other text will result in a failure."

- **Model Decommission Drift:** Groq/Cerebras IDs change frequently. Always check 400/404 errors as signals.

- **Reasoning Trace Separation:** Some local deployments or newer model families (e.g., Gemma 4) may output reasoning traces to a separate `reasoning_content` field while leaving the main `content` field empty. This causes extraction to fail even if the model internally produces the correct answer. When benchmarking local or custom endpoints, inspect the full response JSON for alternative content fields. If present, modify the extraction logic to capture `reasoning_content` or concatenate it with `content` for evaluation.

- **TPM/context limits:** `groq/llama-3.3-70b-versatile` returned 413 "Request too large" at ~275KB payloads. This indicates upstream context bloat. Even though bouncer prompts are tiny, the combo routing may be concatenating large handoffs or compression artifacts. Keep the payload under ~32KB by:
  - Using `max_tokens=10` in the bouncer request.
  - Avoiding sending full documents; send only the minimal text needed for the YES/NO decision.
  - If using via OmniRoute, check that the combo isn't including excessive `fill_first` context from previous uses.

## Distinguishing Inline/Fallback vs. Kanban Execution

> Seeing logs like `Combo "bouncer" (fill-first) with N models` does **not** indicate kanban work. It shows inline/fallback routing through OmniRoute. The bouncer may be invoked as a fallback from other profiles even when its own kanban queue is empty.

| Mode | Trigger | Kanban DB | Use Case |
|------|---------|-----------|----------|
| **Inline/Fallback** | `model="bouncer"` via gateway | No | Fast, stateless; normal triage |
| **Kanban** | Dispatcher creates task | Yes (`kanban.db`) | Auditable backfill, workflow gates |

**Check actual kanban activity:**
```bash
# Global kanban DB (most common)
sqlite3 ~/.hermes/kanban.db "SELECT COUNT(*) FROM tasks WHERE status NOT IN ('completed','cancelled','failed');"

# Profile-specific DB (if dispatcher routes there)
sqlite3 ~/.hermes/profiles/bouncer/kanban.db "SELECT COUNT(*) FROM tasks WHERE status NOT IN ('completed','cancelled','failed');"
```
Zero rows means no kanban work assigned; combo logs are just fallback traffic.

## Bouncer Test Crash Loops

When bouncer kanban tasks repeatedly crash and restart (status "running" but `task_runs` shows "crashed" with `pid <n> not alive`), the worker process is dying immediately after start. Common causes:

- **Skill explosion:** Bouncer profile's `skills/` directory may contain hundreds of cached skill files. Excessive skill loading can exhaust memory or exceed startup timeouts. The bouncer should load **zero intentional skills** (maybe one guard skill max). If `skills/` has >50 files, it's likely bloated.
- **Combo misconfiguration:** `omniroute:bouncer` combo may reference decommissioned models (404) or rate-limited providers (429). Check OmniRoute logs for "Trying model N/M" failures.
- **SOUL mismatch:** Bouncer's `SOUL.md` demands strict YES/NO; test body may request formatted output (e.g., "numbered list"). This can cause the agent to error out if it interprets the request as violating its core rules.
- **Timeout too low:** `agent.max_turns: 5` and `gateway_timeout: 120` may be insufficient if the combo chain retries or slows.

**Diagnosis order:**
1. Inspect `~/.hermes/profiles/bouncer/logs/errors.log` and `agent.log` for startup exceptions.
2. Verify bouncer combo health via OmniRoute logs; prune broken model entries.
3. If `skills/` directory is bloated, clear it to just the minimal guard skill or set skill restrictions in `config.yaml`.
4. Adjust `max_turns` upward temporarily and ensure `reasoning_effort: low` is respected.

## Skill Explosion in Bouncer Profile

> The bouncer's `skills/` directory often contains **hundreds of cached skill files** from global sync. These are not all loaded at runtime, but if Hermes attempts to load too many, the bouncer worker can crash due to memory pressure or startup latency.

**Proper bouncer skill footprint:**
- `skills/` should be **empty or contain at most 1-2 guard-related skills**.
- No auxiliary or research skills should be present.
- If you see >20 `.md` files in `~/.hermes/profiles/bouncer/skills/`, it's bloated.

**Fix:**
```bash
# List skill files (likely many)
find ~/.hermes/profiles/bouncer/skills -name "*.md" | wc -l

# If bloated, clear the directory (keep SOUL.md and config.yaml safe)
rm -rf ~/.hermes/profiles/bouncer/skills/*
# Optionally add back a minimal guard skill if needed
```

**Long-term:** Enforce skill filtering via `config.yaml` to prevent future skill accumulation:
```yaml
skills:
  guard_agent_created: false
  # explicit allowlist or deny list can be added
```

[[], ["SKILL]` loading lines\n- Avoid assumptions based on `find ... | wc -l`\n\n### Checking Kanban Task Status\nThe bouncer may have a kanban profile but that doesn't mean it's actively processing tasks. To verify:\n```bash\n# Check for any non-completed tasks\nsqlite3 ~/.hermes/profiles/bouncer/kanban.db", "SELECT COUNT(*) FROM tasks WHERE status NOT IN ('completed','cancelled','failed');", 'Returns 0 if no active work\n```\nAlternatively, inspect `task_runs` and `task_events` for recent activity. An empty database means no kanban work has been assigned.\n\n### Fallback Combo Logs vs. Kanban Work\nSeeing logs like `Combo "bouncer', ['fill-first] with 7 models` indicates the **bouncer combo is being invoked as a fallback** from other profiles\' error chains, not that the bouncer is running a kanban task. The bouncer\'s own `config.yaml` may appear in other agents\' `fallback_providers`; this is normal routing behavior and does not require kanban.\n\n### Kanban Dispatch Configuration\nThe bouncer\'s `config.yaml` typically contains:\n```yaml\nkanban:\n  dispatch_in_gateway: false  # default: dispatcher does NOT send tasks automatically\n```\nSetting this to `true` would enable the dispatcher to assign work. Until then, the bouncer only runs when explicitly called (inline or as a fallback). Ensure this flag aligns with your intended usage: `false` for on-demand triage, `true` for dedicated backfill worker.\n\n### Distinguishing Inline vs. Kanban Execution\n- **Inline/Fallback:** Request goes through the gateway\'s `model="bouncer', "resolution. No kanban DB involvement. Fast, stateless.\n- **Kanban:** Dispatcher creates a task in the profile's `kanban.db`. Worker claims and runs it with retries, heartbeats, and persistence. Slower, auditable.\n\nIf you see combo activity but no kanban rows, you're observing inline fallback routing."]]]

## Deployed Bouncer Profile (2026-05-04)

**Profile:** `~/.hermes/profiles/bouncer/` — config.yaml + SOUL.md
**Combo:** `omniroute:bouncer` (fill-first, fast models)
**Smoke test:** 5/6 accuracy, avg 269ms latency (Groq Llama 3.3 70B). All responses clean single-word, zero yapping.

### Combo Maintenance & Kanban Integration

The bouncer combo requires periodic upkeep to remain reliable. As of 2026-05-04, the following issues were discovered and fixed:

- **Model decommission drift:** `cerebras/gpt-oss-120b` returned 404 (model removed or no longer accessible). Always verify model IDs; replace with currently available equivalents like `cerebras/llama-3.1-8b` if needed.
- **Rate-limit saturation:** `sambanova/gpt-oss-120b` hit 429 (rate limit). For fill-first chains, ensure secondary models have distinct quota buckets; consider removing or replacing heavily throttled providers.
- **TPM/context limits:** `groq/llama-3.3-70b-versatile` returned 413 "Request too large" at ~275KB payloads. This indicates upstream context bloat. Even though bouncer prompts are tiny, the combo routing may be concatenating large handoffs or compression artifacts. Keep the payload under ~32KB by:
  - Using `max_tokens=10` in the bouncer request.
  - Avoiding sending full documents; send only the minimal text needed for the YES/NO decision.
  - If using via OmniRoute, check that the combo isn’t including excessive `fill_first” context from previous uses.
- **Fallback chain broken:** The combo’s fallback to Nous Portal (`stepfun/step-3.5-flash`) failed with “provider not configured.” Either configure Nous auth (`hermes auth`) or remove the fallback entry to avoid silent failures.
- **MCP 401 noise:** Granola/Mesh MCP servers expired. If MCP isn’t used by the bouncer, disable MCP in the profile’s `config.yaml` to reduce startup warnings.

When these issues are resolved, the bouncer profile is kanban-ready. Assign kanban tasks to the `bouncer` profile just like any other worker. The dispatcher injects `KANBAN_GUIDANCE` automatically, and the bouncer’s binary nature makes it suitable for:
- Backfill/audit scenarios where you need to process large historical batches with persistence.
- Workflow gates (bouncer → clerk) where you want an auditable YES/NO trail on the board.
- Cases where you want to temporarily pause/review rejected items via the board UI.

Avoid using bouncer through kanban for high-throughput live streams; inline execution is far more efficient.

### Working Combo Snippet

Update `omniroute:bouncer` to currently healthy fast models. Example (adjust to your quota):

```yaml
fill_first:
  - groq/llama-3.1-8b-instant   # speed leader, ~210ms
  - cerebras/llama-3.1-8b       # free tier, ~290ms
  - openrouter/google/gemma-4-26b-a4b-it  # cheap backup
max_retries: 0
queue_timeout_ms: 10000
```

### SOUL.md Template

Bouncer SOUL.md files should follow this pattern (no personality, mechanical constraints):

```markdown
# Bouncer

You are a binary triage filter. Your job is to answer YES or NO as fast as possible.

## Rules
1. Return ONLY YES or NO. No preamble. No explanation.
2. When uncertain, say YES. False positives are cheap; false negatives lose data.
3. Never elaborate.
4. Speed over cleverness.

## Output Format
Every response must be exactly one of: YES, NO — no punctuation, no extra whitespace.
```

### Smoke Test Methodology

Test through OmniRoute (not direct provider) to validate the full routing path:

```python
# 6-test suite: 2 clear yes, 2 clear no, 1 borderline, 1 noise
tests = [
    ("Is this relevant to [topic]? {text}", "YES", "clear yes"),
    ("Is this relevant to [topic]? {text}", "NO", "clear no"),
    ("Is this relevant to [topic]? {unrelated_text}", "NO", "irrelevant"),
    ("Is this relevant to [topic]? {related_text}", "YES", "relevant"),
    ("Is this relevant to [topic]? {adjacent_text}", "YES", "partial match"),
    ("Is this relevant to [topic]? {noise_text}", "NO", "noise"),
]
# Payload: model="bouncer", max_tokens=10, stream=false
# Acceptance: ≥80% accuracy, avg <400ms, zero multi-word responses
```

Key: include a borderline/partial-match test to calibrate false-negative rate. The one miss in initial smoke test was defensible (model said NO to adjacent-but-not-literal match).

## Hierarchy Placement (Confirmed 2026-04-22)
1. **Tier 1: Deep Reasoning** (Opus/Sonnet) - Strategic Synthesis
2. **Tier 2: Complex Coding** (GLM 5.1/ZAI) - Technical Implementation
3. **Tier 3: Orchestrator** (Gemini Flash/Nous) - Coordination
4. **Tier 4: Cheap Structured** (Gemini Flash Lite) - Clerk (JSON/CSV)
5. **Tier 5: Fast and Dumb** (Llama 3.3 70B/Groq) - Bouncer (Binary)


## Common Benchmark Baseline

Load and follow the `model-benchmark` skill before modifying or running this benchmark. Results should be written to `results/benchmark.db` using the common SQLite schema and mirrored to the Obsidian Benchmarks folder.
