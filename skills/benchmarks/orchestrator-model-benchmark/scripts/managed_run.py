#!/usr/bin/env python3
"""
Managed Orchestrator Benchmark Runner.
Handles ping, execution via O‍mniRoute/OpenRouter, scoring, and Obsidian logging.
"""
import json, os, sys, time, subprocess, urllib.request
from pathlib import Path
from datetime import datetime, timezone

# Skill paths
SKILL_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_DIR / 'scripts'))

from run_benchmark import prepare_run, record_score, summarize_run
from scenarios import SCENARIOS

# Constants
OBSIDIAN_DIR = Path.home() / "Obsidian/Main Vault/Hermes/Benchmarks/Orchestrator"
OMNIROUTE_DB = Path.home() / 'OmniRoute/data/storage.sqlite'
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

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

def get_omniroute_key():
    try:
        cmd = ["sqlite3", str(OMNIROUTE_DB), "SELECT key FROM api_keys WHERE name='Hermes'"]
        return subprocess.check_output(cmd).decode().strip()
    except Exception as e:
        print(f"Error getting O‍mniRoute key: {e}")
        return None

def execute_tool(name, args):
    if name == "read_file":
        path = args.get("path", "")
        offset = args.get("offset", 1)
        limit = args.get("limit", 500)
        try:
            p = Path(path).expanduser()
            if not p.is_absolute():
                # For benchmark context, relative paths might be used
                pass
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

def call_model_with_tools(messages, model, api_key, base_url, max_turns=10):
    total_input = 0
    total_output = 0
    for turn in range(max_turns):
        body = json.dumps({
            "model": model,
            "messages": messages,
            "tools": TOOLS,
            "max_tokens": 4096,
            "temperature": 0,
            "stream": False
        }).encode()
        req = urllib.request.Request(
            f'{base_url}/chat/completions',
            data=body,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        )
        try:
            # Increase timeout to 300s for OmniRoute processing/tunnels
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read())
        except Exception as e:
            return {'error': str(e), 'turns': turn}

        usage = result.get('usage', {})
        total_input += usage.get('prompt_tokens', 0)
        total_output += usage.get('completion_tokens', 0)
        
        if 'choices' not in result or not result['choices']:
            return {'error': f"No choices in response: {result}", 'turns': turn}
            
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

def update_obsidian_log(run_group, model_label, results):
    # Append to a summary table in Obsidian
    log_file = OBSIDIAN_DIR / "Orchestrator Results Table.md"
    if not log_file.exists():
        header = "| Timestamp | Run ID | Model | Total Score | Scenarios (S1-S6) |\n"
        header += "|-----------|--------|-------|-------------|-------------------|\n"
        with open(log_file, "w") as f:
            f.write(header)
            
    # Calculate scores from the run group in DB
    import sqlite3
    from init_db import DB_PATH
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT scenario, total FROM runs WHERE run_id LIKE ? ORDER BY scenario", (f"{run_group}_%",))
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        return
        
    scenario_scores = {r[0]: r[1] for r in rows}
    total_score = sum(scenario_scores.values())
    s_list = []
    for sid in ["S1", "S2", "S3", "S4", "S5", "S6"]:
        s_list.append(str(scenario_scores.get(sid, "-")))
    
    row = f"| {datetime.now().strftime('%Y-%m-%d %H:%M')} | {run_group} | {model_label} | {total_score}/108 | {', '.join(s_list)} |\n"
    
    with open(log_file, "a") as f:
        f.write(row)
    print(f"Updated Obsidian log: {log_file}")

def run_managed_benchmark(provider, model_id, model_label):
    print(f"Pinging {provider}:{model_id}...")
    # Use a direct curl-based ping first to bypass the ping.py logic which might be too strict
    try:
        ping_key = get_omniroute_key() if provider == "omniroute" else os.environ.get('OPENROUTER_API_KEY')
        ping_url = os.environ.get('OMNIROUTE_URL', 'https://omniroute.cow-hippocampus.ts.net') + "/v1" if provider == "omniroute" else DEFAULT_BASE_URL
        
        body = json.dumps({"model": model_id, "messages": [{"role": "user", "content": "ping"}], "stream": False}).encode()
        req = urllib.request.Request(f"{ping_url}/chat/completions", data=body, headers={"Authorization": f"Bearer {ping_key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            if resp.status == 200:
                print("Ping success (direct).")
            else:
                print(f"Ping warning: status {resp.status}")
    except Exception as e:
        print(f"Ping failed (direct): {e}")
        # Fallback to script ping
        ping_script = Path.home() / ".hermes/skills/devops/model-ping/ping.py"
        res = subprocess.run([sys.executable, str(ping_script), provider, model_id], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Ping failed (script):\n{res.stdout}\n{res.stderr}")
            return
        print("Ping success (script).")

    # 2. Setup credentials
    base_url = DEFAULT_BASE_URL
    api_key = os.environ.get('OPENROUTER_API_KEY')
    
    if provider == "omniroute":
        base_url = os.environ.get('OMNIROUTE_URL', 'https://omniroute.cow-hippocampus.ts.net') + "/v1"
        api_key = get_omniroute_key()
    elif provider == "nous":
        # Nous might use different endpoint
        pass

    if not api_key:
        print(f"Error: No API key for {provider}")
        return

    # 3. Prepare run
    manifest = prepare_run(model_label, ["S1", "S2", "S3", "S4", "S5", "S6"])
    run_group = manifest['run_group']
    run_dir = SKILL_DIR / 'results' / 'runs' / run_group

    # 4. Execute scenarios
    for sid in ["S1", "S2", "S3", "S4", "S5", "S6"]:
        print(f"Running {sid}...", end=" ", flush=True)
        prompt_path = run_dir / sid / 'prompt.txt'
        fixtures_path = run_dir / sid / 'fixtures.json'
        
        prompt = prompt_path.read_text()
        with open(fixtures_path) as f:
            fixtures = json.load(f)
            
        messages = [
            {"role": "system", "content": "You are being benchmarked. Use tools to complete the task. Be concise and efficient."},
            {"role": "user", "content": prompt}
        ]
        
        t0 = time.time()
        res = call_model_with_tools(messages, model_id, api_key, base_url)
        elapsed = time.time() - t0
        
        if 'error' in res:
            print(f"FAILED: {res['error']}")
            continue
            
        print(f"done ({elapsed:.1f}s, {res['turns']} turns)")
        
        # Record and score
        record_score(f"{run_group}_{sid}", sid, model_label, res['response'], fixtures)

    # 5. Summarize
    summarize_run(run_group)
    
    # 6. Log to Obsidian
    update_obsidian_log(run_group, model_label, None)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: managed_run.py <provider> <model_id> [label]")
        sys.exit(1)
        
    provider = sys.argv[1]
    model_id = sys.argv[2]
    label = sys.argv[3] if len(sys.argv) > 3 else model_id.split('/')[-1]
    
    run_managed_benchmark(provider, model_id, label)
