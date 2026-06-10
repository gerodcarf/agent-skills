#!/usr/bin/env python3
"""Run 10-scenario orchestrator benchmark for all 5 models sequentially."""
import subprocess, sys
from pathlib import Path

MODELS = [
    ("z-ai/glm-5.1", "glm51"),
    ("xiaomi/mimo-v2-pro", "mimo"),
    ("google/gemini-3-flash-preview", "gemini"),
    ("anthropic/claude-sonnet-4.6", "sonnet"),
    ("anthropic/claude-opus-4.7", "opus"),
]

scripts_dir = Path(__file__).parent
results_dir = scripts_dir.parent / "results"
results_dir.mkdir(exist_ok=True)

for model, label in MODELS:
    log_file = results_dir / f"run_{label}.log"
    print(f"\n{'='*60}")
    print(f"Running {model} ({label})")
    print(f"Log: {log_file}")
    print(f"{'='*60}")
    try:
        subprocess.run(
            [sys.executable, str(scripts_dir / "run_with_tools.py"), model],
            cwd=str(scripts_dir),
            stdout=open(log_file, "w"),
            stderr=subprocess.STDOUT,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"FAILED with exit code {e.returncode}")
    except Exception as e:
        print(f"ERROR: {e}")

print("\nAll done.")
