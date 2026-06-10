# OmniRoute opencode-go preflight quirk

## Symptom

`managed_run.py` preflight for `omniroute:opencode-go/deepseek-v4-pro` may fail with:

```text
HTTP Error 403: Forbidden
[opencode-go/deepseek-v4-pro] [403]: <!doctype html> (reset after 2s)
```

while the same model succeeds through normal Hermes CLI / OmniRoute traffic.

## Cause

The Cloudflare edge in front of the `opencode-go` upstream can reject Python `urllib`'s default User-Agent. The benchmark script's direct preflight is not fully representative unless it mirrors normal client traffic.

## Durable fix pattern

For direct OpenAI-compatible preflight calls to OmniRoute, include both bounded generation parameters and an explicit client User-Agent:

```python
body = json.dumps({
    "model": model_id,
    "messages": [{"role": "user", "content": "ping"}],
    "max_tokens": 16,
    "temperature": 0,
    "stream": False,
}).encode()
req = urllib.request.Request(
    f"{base_url}/chat/completions",
    data=body,
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Hermes-Agent/1.0",
    },
)
```

Do not conclude the model is unavailable from this preflight failure alone. Cross-check with `hermes chat --provider omniroute -m <model>` and recent OmniRoute call logs if needed.