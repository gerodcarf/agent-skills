# Debugging Background Timeout and Exit Code -15

When running `managed_run.py` as a background process (e.g. `terminal(background=True, notify_on_complete=True)`), if it exits with `Exit Code -15` (SIGTERM) and produces no `response.txt` or `output`, the benchmark script hit the execution time limit.

## Common Root Causes

1. **Infinite Tool Calling Loops**
   Models like `qwen-max` or `claude-3.5-sonnet` can sometimes enter a loop where they repeatedly call `read_file` or `search_files` without rendering a final text answer. Because `managed_run.py` configures `max_turns=10` and executes these synchronously over HTTP (`stream: False`), an infinite loop of 10 tool generations + reasoning tokens can take upwards of 3-5 minutes for a single scenario.
   
2. **Context Window Expansion**
   Reasoning-heavy models (generating long `<reasoning_content>` blocks) bloat the `messages` array appended across consecutive turns. By turn 5, sending the raw history back to the OmniRoute proxy can strain backend ingestion APIs, leading to intermittent 503 timeouts that the benchmark script retries automatically (900s possible retry span).
   
3. **Hard System Limits**
   - The Hermes Gateway / `terminal_ide` `background=True` has a default `timeout` of 180s.
   - The OS/lockdown watchdogs may enforce a 60s hard limit on unregistered `python3` instances.
   
## Diagnostics

If the run stalls, do not rely on `managed_run.py`'s basic stdout, as buffering hides the exact tool being looped. Instead, use a custom monkey-patched `call_model_with_tools` wrapper to expose the exact responses:

```python
import sys; sys.path.insert(0, "./scripts")
import urllib.request, json, time
import managed_run
orig_call = managed_run.call_model_with_tools

def debug_call(messages, model, api_key, base_url, max_turns=10):
    for turn in range(max_turns):
        print(f"\\n[DEBUG] Turn {turn+1}...")
        body = json.dumps({"model": model, "messages": messages, "tools": managed_run.TOOLS, "max_tokens": 4096, "stream": False}).encode()
        req = urllib.request.Request(f'{base_url}/chat/completions', data=body, headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            choice = json.loads(resp.read())['choices'][0]['message']
            
        print(f"[DEBUG] Model returned: content={choice.get('content') is not None}, tool_calls={bool(choice.get('tool_calls'))}")
        if not choice.get('tool_calls'):
            return {'response': choice.get('content', ''), 'turns': turn + 1}
            
        messages.append(choice)
        for tc in choice['tool_calls']:
            print(f"[DEBUG] Executing tool {tc['function']['name']}")
            tool_res = managed_run.execute_tool(tc['function']['name'], json.loads(tc['function']['arguments']))
            messages.append({"role": "tool", "tool_call_id": tc['id'], "name": tc['function']['name'], "content": str(tool_res)[:2000]})
    return {'error': 'max turns', 'turns': max_turns}

managed_run.call_model_with_tools = debug_call
managed_run.run_managed_benchmark("omniroute", "nous/qwen/qwen3.7-max", "debug-run")
```