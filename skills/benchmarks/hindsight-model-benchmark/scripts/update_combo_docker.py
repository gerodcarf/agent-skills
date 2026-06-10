#!/usr/bin/env python3
"""Update the hindsight-retain-free combo in the Docker container."""
import sqlite3, json

con = sqlite3.connect('/app/data/storage.sqlite')
con.row_factory = sqlite3.Row

row = con.execute("SELECT id, data FROM combos WHERE name = 'hindsight-retain-free'").fetchone()
if not row:
    print('Combo not found')
    con.close()
    exit(1)

combo_data = json.loads(row[1])
original_count = len(combo_data.get('models', []))

# Models to KEEP (verified working from benchmark)
KEEP_IDS = {
    "hindsight-retain-free-model-2-nvidia-nvidia-nemotron-3-nano-30b-a3b-nv-manual-1777213832",
    "hindsight-retain-free-model-3-gemini-gemma-4-26b-a4b-it-9d5da8cf-475b-48e1-a992-bdaf32afef8c",
    "hindsight-retain-free-model-5-kiro-claude-haiku-4-5-852b96bf-d7cb-49dc-b03a-db87a1d95e20",
    "hindsight-retain-free-model-6-ollama-cloud-gemma4-31b-63525e08-4b51-464a-a2c3-4f88541b66ea",
    "hindsight-retain-free-model-10-nvidia-openai-gpt-oss-120b-nv-manual-1777213832",
}

combo_data['models'] = [m for m in combo_data['models'] if m.get('id') in KEEP_IDS]
combo_data['version'] = combo_data.get('version', 0) + 1
combo_data['config']['maxRetries'] = 0
combo_data['config']['retryDelayMs'] = 500
combo_data['updatedAt'] = '2026-05-13T19:05:00.000Z'

new_json = json.dumps(combo_data)

con.execute("UPDATE combos SET data = ?, version = ?, updatedAt = ? WHERE id = ?",
    (new_json, combo_data['version'], combo_data['updatedAt'], row[0]))
con.commit()

print(f"Updated hindsight-retain-free: {original_count} -> {len(combo_data['models'])} models")
for m in combo_data['models']:
    print(f"  - {m['model']} [{m.get('providerId')}]")

con.close()
