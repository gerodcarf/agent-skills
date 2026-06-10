# Benchmarking Gateway Models - Session Notes

## Date: 2026-05-04

## Context
Attempted to run the Tier 3 (Orchestrator) benchmark suite on `nous:arcee-ai/trinity-large-thinking`. Encountered multiple technical hurdles related to model access and benchmark execution.

## Key Findings

### 1. `delegate_task` Model Override Limitation
**Discovery:** The `delegate_task` tool completely ignores the `model` parameter. It always uses the configured `delegation.model` from `~/.hermes/config.yaml`.

**Evidence:** Even when explicitly setting `model: "nous/arcee-ai/trinity-large-thinking"` in the `delegate_task` call, the result showed `model: "glm-5.1"`. The override is silently ignored.

**Implication:** To benchmark a non-default model via delegation, you must:
- Change the default delegation model in config
- Restart the Hermes agent to reload configuration
- Run the benchmark
- Revert the config and restart again (if needed)

### 2. Gateway Accessibility Issues
**Problem:** Direct HTTP access to the Hermes gateway (port 8090) was refused, preventing programmatic access via the gateway API.

**Symptoms:** `Connection refused` errors when attempting to connect to `http://localhost:8090/api/v1/chat/completions`.

**Possible Causes:**
- Gateway service not running
- Gateway bound to different port/interface
- Firewall restrictions

**Resolution Steps:**
- Verify gateway status: `hermes gateway status`
- Check gateway port in config
- Test connectivity with `curl http://localhost:8090/health`
- Start gateway if stopped: `hermes gateway run`

### 3. OpenRouter API Key Access
**Problem:** The benchmark scripts require an OpenRouter API key, which was not accessible in the sandbox environment (1Password CLI failed).

**Workaround:** If the target model is available on OpenRouter (as `arcee-ai/trinity-large-thinking` is), an API key must be provided. Options:
- Use an existing API key from environment variable `OPENROUTER_API_KEY`
- Retrieve from 1Password with `op read op://Ambler-Tokens/OpenRouter/api_key_enrich`
- Provide a new API key

### 4. Configuration Reload Behavior
**Observation:** Changing the delegation model via `hermes config set` or editing `config.yaml` does not immediately affect `delegate_task` calls. The agent process must be restarted to pick up the change.

**Test:** After changing `delegation.model` to `nous/arcee-ai/trinity-large-thinking` and sending SIGHUP to the agent, the config was updated, but `delegate_task` still used `glm-5.1`. This suggests subagents may cache configuration or use a different config source.

## Recommendations for Future Benchmark Sessions

### For OpenRouter Models
1. Ensure `OPENROUTER_API_KEY` is available in the environment
2. Use `managed_run.py` or `run_with_tools.py` from the benchmark skill
3. These scripts handle tool access and scoring automatically

### For Gateway Models
1. Verify gateway is running and accessible
2. Change `delegation.model` to the target model in config
3. Restart the Hermes agent: `kill -HUP <pid>` or restart service
4. Run the benchmark via `delegate_task` or direct gateway API
5. Revert config changes after benchmark completion

### For Quick Spot Checks
- Use `delegate_task` with the understanding it will use the current default model
- Check current default: `hermes config get delegation.model`
- If you need a different model, change config and restart first

## Transcript Summary
- Attempted to run benchmark via `managed_run.py` but failed due to missing OpenRouter API key
- Tried direct gateway HTTP API but connection refused
- Changed delegation model and restarted agent
- Ran S1 scenario via `delegate_task` — still used `glm-5.1` due to override limitation
- Documented findings and created this reference

## Next Steps
- Provide OpenRouter API key to run full benchmark
- Troubleshoot gateway connectivity
- Consider creating a wrapper script that handles the full benchmark workflow for gateway models