#!/usr/bin/env python3
"""Quick model audit for hindsight-retain-free combo."""
from __future__ import annotations
import json, sqlite3, os, time, urllib.request, urllib.error, sys

OMNI_URL = "${OMNIROUTE_URL}/v1/chat/completions"
HERMES_KEY = ""

# Load key
db = os.path.expanduser("~/OmniRoute/data/storage.sqlite")
con = sqlite3.connect(db)
row = con.execute("SELECT key FROM api_keys WHERE name='Hermes'").fetchone()
con.close()
if row:
    HERMES_KEY = row[0]
else:
    print("ERROR: No Hermes key found"); sys.exit(1)

# Combo models (from DB inspection)
MODELS = [
    "openrouter/google/gemma-4-26b-a4b-it:free",
    "nvidia/nvidia/nemotron-3-nano-30b-a3b",
    "gemini/gemma-4-26b-a4b-it",
    "cerebras/gpt-oss-120b",
    "kiro/claude-haiku-4.5",
    "ollama-cloud/gemma4:31b",
    "ollama-cloud/nemotron-3-super",
    "ollama-cloud/minimax-m2.7",
    "ollama-cloud/gpt-oss:120b",
    "nvidia/openai/gpt-oss-120b",
    "sambanova/gpt-oss-120b",
    "qoder/qwen3-32b",
]

def call_model(model, prompt, max_tokens=64, timeout=60):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": max_tokens,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {HERMES_KEY}"}
    req = urllib.request.Request(OMNI_URL, data=json.dumps(payload).encode(), headers=headers, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            latency = time.time() - t0
            text = ""
            choices = data.get("choices", [])
            if choices:
                text = choices[0].get("message", {}).get("content", "") or choices[0].get("message", {}).get("reasoning", "") or ""
            usage = data.get("usage", {})
            return {"ok": True, "latency": round(latency, 1), "text": text[:80], "prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0), "actual_model": data.get("model", "")}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "http": e.code, "body": body[:200], "latency": round(time.time() - t0, 1)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "latency": round(time.time() - t0, 1)}

# Generate ~10K token payload for context test
CONVERSATION_CHUNK = """[user] Can you analyze the Q4 supply chain data? The Neo4j database shows 847 companies, 312 with website enrichment done. Hindsight is getting 413 errors from Groq. OmniRoute handles routing through multiple providers. We need to switch the model.
[assistant] The issue is Groq's 8K TPM limit. Hindsight sends ~67K tokens per retain. Let's test alternative models.
[tool_call: terminal] docker logs hindsight --tail 50
[tool_output] APIStatusError: groq/openai/gpt-oss-20b HTTP 413 Request too large. TPM: Limit 8000.
[tool_call: web_search] "large context LLM alternatives to Groq 2026"
[tool_output] Nvidia Nemotron models accept 256K context. Google Gemini supports 1M. Qwen 3 supports 131K.
[tool_call: terminal] curl -s ${OMNIROUTE_URL}/v1/models
[tool_output] List of 80+ models available through OmniRoute.
[assistant] Recommended combo: Nemotron 3-Super (free) → GPT-OSS 120B (Cerebras free) → Gemma 4 26B (paid).
"""

def gen_large_prompt(target_chars=40000):
    """~10K tokens = ~40K chars"""
    payload = ""
    i = 0
    while len(payload) < target_chars:
        payload += f"\n=== Conversation block {i} ===\n" + CONVERSATION_CHUNK
        i += 1
    return payload[:target_chars]

LARGE_PROMPT = gen_large_prompt()

print(f"Testing {len(MODELS)} models from hindsight-retain-free combo\n")
print(f"{'Model':<55} {'Ping':>5} {'PingLat':>7} {'Ctx':>5} {'CtxLat':>7} {'Tokens':>8} {'Status'}")
print("-" * 100)

results = []

for model in MODELS:
    short = model.split("/")[-1] if "/" in model else model

    # Test 1: Small ping
    r1 = call_model(model, "Reply with just: OK", max_tokens=10, timeout=30)
    ping_latency = r1.get("latency", 0)
    ping_ok = r1.get("ok", False)
    ping_text = r1.get("text", "")

    # Initialize context test vars before the branch
    ctx_ok = False
    ctx_latency = 0
    ctx_tokens = 0
    r2 = r1

    if ping_ok:
        # Test 2: Context size (10K tokens)
        r2 = call_model(model, LARGE_PROMPT + "\n\nReply: ACK", max_tokens=10, timeout=90)
        ctx_latency = r2.get("latency", 0)
        ctx_ok = r2.get("ok", False)
        ctx_tokens = r2.get("prompt_tokens", 0)

    # Classify status
    if not ping_ok:
        http = r1.get("http", 0)
        if http == 429:
            status = "❌ RATE-LIM"
        elif http == 404:
            status = "❌ NOT-FOUND"
        elif http == 401:
            status = "❌ AUTH"
        elif http == 0:
            status = "❌ TIMEOUT"
        else:
            status = "❌ ERROR"
    elif ctx_ok and ctx_latency < 30:
        status = "✅ PASS"
    elif ctx_ok and ctx_latency >= 30:
        status = "⚠️ SLOW"
    else:
        status = "❌ CTX-FAIL"

    # Display
    ctx_ok_str = "✅" if ctx_ok else "❌" if ping_ok else "--"
    print(f"{short:<55} {'✅' if ping_ok else '❌'} {ping_latency:>5.1f}s {ctx_ok_str:>5} {ctx_latency:>5.1f}s {ctx_tokens:>8} {status}")

    results.append({
        "model": model,
        "ping_ok": ping_ok,
        "ping_latency_s": round(ping_latency, 1),
        "ctx_ok": ctx_ok,
        "ctx_latency_s": round(ctx_latency, 1),
        "ctx_tokens": ctx_tokens,
        "status": status,
        "error": r1 if not ping_ok else (r2 if not ctx_ok else None),
    })

# Summary
print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)

passed = [r for r in results if "PASS" in r["status"]]
slow = [r for r in results if "SLOW" in r["status"]]
failed = [r for r in results if r["status"].startswith("❌")]

if passed:
    print("\n✅ PASS (can handle context, fast response):")
    for r in passed:
        print(f"  - {r['model']} (ping {r['ping_latency_s']}s, ctx tokens {r['ctx_tokens']})")

if slow:
    print("\n⚠️ SLOW (works but latency >30s):")
    for r in slow:
        print(f"  - {r['model']} (ctx latency {r['ctx_latency_s']}s)")

if failed:
    print("\n❌ FAIL (remove from combo):")
    for r in failed:
        err = r.get("error", {})
        if isinstance(err, dict):
            msg = err.get("http", err.get("error", err.get("body", "unknown")[:100]))
        else:
            msg = str(err)[:100]
        print(f"  - {r['model']} [{r['status']}] {msg}")

print(f"\nVerdict: {len(passed)} OK, {len(slow)} slow, {len(failed)} remove from combo")
