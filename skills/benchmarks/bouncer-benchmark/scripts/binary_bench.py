import os, json, time, requests, subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

def get_key(op_path):
    try:
        res = subprocess.run(["op", "read", op_path], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except:
        return None

# --- Keys (Loaded from 1Password) ---
KEYS = {
    "groq": get_key("op://Ambler-Tokens/Groq/api_key"),
    "cerebras": get_key("op://Ambler-Tokens/Cerebras/api_key"),
    "openrouter": get_key("op://Ambler-Tokens/OpenRouter/api_key_enrich")
}

BENCHMARK_CASKS = [
    {
        "id": "signal_tesla",
        "input": "Tesla Inc., Austin, Texas, is awarded a $98,000,000 firm-fixed-price contract for providing lithium-ion battery modules for the Department of Defense.",
        "expected": "YES"
    },
    {
        "id": "signal_lockheed",
        "input": "Lockheed Martin Corp., Orlando, Florida, is awarded $150,000,000 for the production of advanced quantum sensing systems for high-altitude reconnaissance.",
        "expected": "YES"
    },
    {
        "id": "noise_maintenance",
        "input": "Standard Electric Co., Denver, Colorado, is awarded a $5,000,000 contract for routine electrical maintenance at Buckley SFB.",
        "expected": "NO"
    },
    {
        "id": "noise_food",
        "input": "Aramark Services, Philadelphia, Pennsylvania, is awarded a $120,000,000 contract for food service operations at Fort Bragg.",
        "expected": "NO"
    },
    {
        "id": "noise_construction",
        "input": "Turner Construction Co., New York, NY, is awarded a $500,000,000 contract for building a new administrative facility for the VA.",
        "expected": "NO"
    }
]

PROMPT = "Is this a deep-tech/lithium/energy supply chain award with a value > $50,000,000? Return ONLY 'YES' or 'NO'.\n\nAward: {input}"

MODELS = [
    {"p": "groq", "m": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B (Groq)"},
    {"p": "cerebras", "m": "llama3.1-8b", "label": "Llama 3.1 8B (Cerebras)"},
    {"p": "groq", "m": "llama-3.1-8b-instant", "label": "Llama 3.1 8B (Groq)"},
    {"p": "openrouter", "m": "google/gemini-2.0-flash-lite-preview-02-05", "label": "Gemini 2.0 Flash Lite (OR)"}
]

def call_provider(provider, model, prompt):
    key = KEYS.get(provider)
    if not key:
        return None, 0, "Missing Key"

    if provider == "cerebras":
        url = "https://api.cerebras.ai/v1/chat/completions"
    elif provider == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
    else:  # openrouter
        url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 10
    }
    
    t0 = time.time()
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        elapsed = time.time() - t0
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip(), elapsed, None
        return None, elapsed, f"HTTP {r.status_code}"
    except Exception as e:
        return None, 0, str(e)

def run():
    print(f"Tier 5 Binary Triage Benchmark")
    print(f"{'Model':<30} | {'Acc':<5} | {'Latency':<8}")
    print("-" * 60)
    
    for m in MODELS:
        correct = 0
        total_time = 0
        for task in BENCHMARK_CASKS:
            text, lat, err = call_provider(m["p"], m["m"], PROMPT.format(input=task["input"]))
            total_time += lat
            if text and task["expected"] in text.upper():
                correct += 1
            
        acc = correct / len(BENCHMARK_CASKS)
        avg_lat = total_time / len(BENCHMARK_CASKS)
        print(f"{m['label']:<30} | {acc:.0%}   | {avg_lat:.3f}s")

if __name__ == "__main__":
    run()
