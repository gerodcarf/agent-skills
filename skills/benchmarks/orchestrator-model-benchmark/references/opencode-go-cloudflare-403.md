# OmniRoute `opencode-go` Cloudflare 403 Preflight Failure

**Context:** Orchestrator benchmark preflight for `omniroute:opencode-go/deepseek-v4-pro`.

## Symptom

The managed benchmark runner stops at the ping gate before creating a run:

```text
Pinging omniroute:opencode-go/deepseek-v4-pro...
Ping failed (direct): HTTP Error 403: Forbidden
Ping failed (script):
✗ omniroute:opencode-go/deepseek-v4-pro failed: 403 Forbidden
  [opencode-go/deepseek-v4-pro] [403]: <!doctype html> (reset after 2s)
  Check OMNIROUTE_API_KEY environment variable
```

Do **not** assume this specific message means the Hermes/OmniRoute API key is bad. In the observed case, all active OmniRoute API keys produced the same 403.

## Diagnosis pattern

1. Confirm the benchmark stopped at ping/preflight, so no benchmark rows were recorded.
2. If the script suggests `Check OMNIROUTE_API_KEY`, test another active OmniRoute API key or inspect OmniRoute call logs before changing credentials.
3. Query OmniRoute call logs for the requested model. The durable signal is an upstream Cloudflare denial, not a local key problem:

```text
provider: opencode-go
account: Sub
status: 403
error: Cloudflare Access denied | opencode.ai used Cloudflare to restrict access
```

4. Inspect the provider connection; it may be marked unavailable with the same 403 HTML error:

```text
provider: opencode-go
test_status: unavailable
error_code: 403.0
last_error: [403]: <!doctype html>
```

## Interpretation

For `opencode-go/deepseek-v4-pro`, a 403 HTML body from `opencode.ai` is an upstream Cloudflare restriction on the `opencode-go` provider path. It is distinct from:

- a missing OmniRoute API key,
- a revoked/inactive OmniRoute API key,
- a missing direct DeepSeek provider credential.

The correct benchmark behavior is to stop at preflight and report the provider route as unroutable. Do not manually insert partial benchmark results.

## Alternative-route sanity checks

If the user asks for a nearby fallback, probe alternatives explicitly rather than substituting silently. In the observed session:

- `cheap-reasoning` via OmniRoute pinged successfully, but it is a combo route and does not preserve exact route fidelity.
- `openrouter/deepseek/deepseek-v4-pro` returned a 502 empty-content error.
- `deepseek/deepseek-v4-pro` had no direct DeepSeek credentials configured.

Because the user prefers exact route fidelity for benchmarks, do not replace `opencode-go/deepseek-v4-pro` with a fallback unless they explicitly approve it.