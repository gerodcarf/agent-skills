#!/usr/bin/env python3
"""
Run orchestrator benchmark (all 10 scenarios) against a model via OpenRouter with tool support.
"""
import json, os, sys, time, subprocess, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run_benchmark import prepare_run, record_score
from score_results import score_scenario
from scenarios import SCENARIOS

# Load env
env_path = Path.home() / '.hermes' / '.env'
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            if line.startswith('export '):
                line = line[7:]
            k, v = line.split('=', 1)
            if k not in os.environ:
                os.environ[k] = v.strip('"\'')

# Try environment first, then fall back to 1Password
API_KEY = os.environ.get('OPENROUTER_API_KEY') or os.environ.get('OPENROUTER_ENRICH_KEY')
if not API_KEY or API_KEY.startswith('$(op'):
    try:
        result = subprocess.run(
            ['op', 'read', 'op://Ambler-Tokens/OpenRouter/api_key_enrich'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            API_KEY = result.stdout.strip()
    except Exception:
        pass

if not API_KEY:
    raise RuntimeError("No OPENROUTER_API_KEY found in environment or 1Password")

BASE_URL = 'https://openrouter.ai/api/v1'

# Pricing from pricing DB (approximate, updated per model)
PRICING = {
    'z-ai/glm-5.1': (0.698, 4.4),
    'xiaomi/mimo-v2-pro': (1.0, 3.0),
    'google/gemini-3-flash-preview': (0.5, 3.0),
    'google/gemini-3.1-pro-preview': (2.0, 12.0),
    'anthropic/claude-sonnet-4.6': (3.0, 15.0),
    'anthropic/claude-opus-4.7': (15.0, 75.0),
    'x-ai/grok-4.1-fast': (0.2, 0.5),
    'arcee-ai/trinity-large-thinking': (0.22, 0.85),
}

# Tools
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file with line numbers. Returns file content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"},
                    "offset": {"type": "integer", "description": "Start line (1-indexed)", "default": 1},
                    "limit": {"type": "integer", "description": "Max lines to read", "default": 500}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search file contents or find files by name pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex or glob pattern"},
                    "target": {"type": "string", "enum": ["content", "files"], "default": "content"},
                    "path": {"type": "string", "description": "Directory to search", "default": "."}
                },
                "required": ["pattern"]
            }
        }
    }
]

def execute_tool(name, args):
    if name == "read_file":
        path = args.get("path", "")
        offset = args.get("offset", 1)
        limit = args.get("limit", 500)
        try:
            p = Path(path).expanduser()
            lines = p.read_text().splitlines()
            result_lines = lines[offset-1:offset-1+limit]
            return "\n".join(f"{i+offset}|{line}" for i, line in enumerate(result_lines))
        except Exception as e:
            return f"ERROR: {e}"
    elif name == "search_files":
        pattern = args.get("pattern", "")
        target = args.get("target", "content")
        path = args.get("path", ".")
        try:
            cmd = ["grep", "-rn", pattern, path]
            if target == "files":
                cmd = ["find", path, "-name", pattern]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return result.stdout[:5000] if result.stdout else "No matches found."
        except Exception as e:
            return f"ERROR: {e}"
    return f"Unknown tool: {name}"

def call_model_with_tools(messages, model, max_turns=10):
    total_input = 0
    total_output = 0
    for turn in range(max_turns):
        body = json.dumps({
            "model": model,
            "messages": messages,
            "tools": TOOLS,
            "max_tokens": 4096,
            "temperature": 0
        }).encode()
        req = urllib.request.Request(
            f'{BASE_URL}/chat/completions',
            data=body,
            headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
        usage = result.get('usage', {})
        total_input += usage.get('prompt_tokens', 0)
        total_output += usage.get('completion_tokens', 0)
        choice = result['choices'][0]
        msg = choice['message']
        if not msg.get('tool_calls'):
            return {
                'response': msg.get('content', ''),
                'input_tokens': total_input,
                'output_tokens': total_output,
                'turns': turn + 1,
            }
        messages.append(msg)
        for tc in msg['tool_calls']:
            tool_name = tc['function']['name']
            tool_args = json.loads(tc['function']['arguments'])
            tool_result = execute_tool(tool_name, tool_args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc['id'],
                "content": tool_result[:5000]
            })
    return {
        'response': 'Max turns exceeded',
        'input_tokens': total_input,
        'output_tokens': total_output,
        'turns': max_turns,
    }

def run_benchmark(model_name, run_group=None):
    BASE = Path.home() / '.hermes/skills/benchmarks/orchestrator-model-benchmark/results/runs'
    
    # Prepare fresh fixtures for all 10 scenarios
    manifest = prepare_run(model_name, list(SCENARIOS.keys()))
    run_group = manifest['run_group']
    
    results = {}
    total_input = 0
    total_output = 0
    pricing = PRICING.get(model_name, (1.0, 3.0))
    
    for sid in list(SCENARIOS.keys()):
        prompt_path = BASE / run_group / sid / 'prompt.txt'
        fixtures_path = BASE / run_group / sid / 'fixtures.json'
        
        if not prompt_path.exists():
            print(f"  {sid}: prompt not found, skipping")
            continue
        
        prompt = prompt_path.read_text()
        with open(fixtures_path) as f:
            fixtures = json.load(f)
        
        # Add efficiency constraint for expensive models
        sys_content = "You are being benchmarked. Use available tools to complete the task. Answer directly and completely. Do not spend more than 3 turns reading files."
        if 'sonnet' in model_name.lower() or 'opus' in model_name.lower():
            sys_content += " Be concise and efficient with tool calls."
        
        messages = [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": prompt}
        ]
        
        print(f"  {sid}...", end=" ", flush=True)
        t0 = time.time()
        try:
            r = call_model_with_tools(messages, model_name)
            elapsed = time.time() - t0
            cost_in = r['input_tokens'] / 1_000_000 * pricing[0]
            cost_out = r['output_tokens'] / 1_000_000 * pricing[1]
            r['cost'] = cost_in + cost_out
            r['elapsed'] = elapsed
            results[sid] = r
            total_input += r['input_tokens']
            total_output += r['output_tokens']
            print(f"done ({elapsed:.1f}s, {r['turns']} turns, {r['input_tokens']}+{r['output_tokens']} tok, ${r['cost']:.4f})")
        except Exception as e:
            print(f"ERROR: {e}")
            results[sid] = {'response': f'ERROR: {e}', 'input_tokens': 0, 'output_tokens': 0, 'cost': 0, 'elapsed': 0, 'turns': 0}
        
        # Save response immediately
        dest = BASE / run_group / sid
        with open(dest / 'response.txt', 'w') as f:
            f.write(results[sid]['response'])
        with open(dest / 'usage.json', 'w') as f:
            json.dump({
                'model': model_name, 'provider': 'openrouter',
                'input_tokens': results[sid]['input_tokens'], 'output_tokens': results[sid]['output_tokens'],
                'cost_usd': results[sid]['cost'], 'elapsed_seconds': results[sid]['elapsed'],
                'turns': results[sid]['turns'],
                'pricing': {'input_per_1m': pricing[0], 'output_per_1m': pricing[1]}
            }, f, indent=2)
        
        # Score immediately
        run_id = f"{run_group}_{sid}"
        try:
            record_score(run_id, sid, model_name, results[sid]['response'], fixtures)
            print(f"    scored OK")
        except Exception as e:
            print(f"    scoring ERROR: {e}")
    
    total_cost = (total_input * pricing[0] + total_output * pricing[1]) / 1_000_000
    print(f"\nTotal: {total_input:,}+{total_output:,} tokens = ${total_cost:.4f}")
    
    # Generate summary
    from run_benchmark import summarize_run
    summarize_run(run_group)
    print(f"\nReport saved to results/report-{run_group}.md")

if __name__ == '__main__':
    model = sys.argv[1] if len(sys.argv) > 1 else "xiaomi/mimo-v2-pro"
    group = sys.argv[2] if len(sys.argv) > 2 else None
    print(f"Running benchmark: {model} (with tool access)")
    run_benchmark(model, group)
