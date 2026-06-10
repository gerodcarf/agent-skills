#!/usr/bin/env python3
"""Initialize the benchmark SQLite database."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'results' / 'benchmark.db'

def init():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        model TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        scenario TEXT NOT NULL,
        detection INTEGER,
        restraint INTEGER,
        permission INTEGER,
        communication INTEGER,
        scope INTEGER,
        accuracy INTEGER,
        total INTEGER,
        response_text TEXT,
        scorer_notes TEXT
    );

    CREATE TABLE IF NOT EXISTS model_aliases (
        alias TEXT PRIMARY KEY,
        full_model_id TEXT NOT NULL,
        last_seen TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model);
    CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp);
    CREATE INDEX IF NOT EXISTS idx_runs_scenario ON runs(scenario);
    """)

    conn.commit()
    conn.close()
    print(f"✅ Benchmark DB initialized at {DB_PATH}")

if __name__ == '__main__':
    init()
