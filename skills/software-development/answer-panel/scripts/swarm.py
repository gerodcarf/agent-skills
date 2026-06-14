#!/Users/ambler/.hermes/hermes-agent/venv/bin/python
"""
Create a Kanban Swarm v1 graph:
    parallel workers (customizable via --workers)
    └─ verifier (customizable via --verifier)
         └─ synthesizer (customizable via --synthesizer)

Subscribes the orchestrating chat platform (Discord, etc.) to the final 
synthesizer task so that outcomes are auto-delivered back to the session thread.
"""

import sys
import os
import argparse
import json
import subprocess
from pathlib import Path

# Incorporate hermes_cli search path
HERMES_AGENT_PATH = "/Users/ambler/.hermes/hermes-agent"
if HERMES_AGENT_PATH not in sys.path:
    sys.path.insert(0, HERMES_AGENT_PATH)

from hermes_cli import kanban_db as kb
from hermes_cli import kanban_swarm as ks
from hermes_cli.kanban_swarm import SwarmWorkerSpec

def get_specialized_worker(profile: str, goal: str, priority: int) -> SwarmWorkerSpec:
    """Returns a specialized SwarmWorkerSpec if the profile matches standard roles, 
    otherwise falls back to a generic spec."""
    if profile == "scout":
        return SwarmWorkerSpec(
            profile="scout",
            title=f"Scout perspective: {goal[:60]}...",
            body=(
                "Establish the macroeconomic, structural, organizational, and strategic/geopolitical vectors "
                "surrounding the goal.\n\n"
                f"Swarm Goal:\n{goal}\n\n"
                "Focus on non-obvious choke points, talent movement, and the strategic landscape. Document key findings."
            ),
            skills=["fact-finder"],
            priority=priority
        )
    elif profile == "researcher":
        return SwarmWorkerSpec(
            profile="researcher",
            title=f"Researcher data gather: {goal[:60]}...",
            body=(
                "Perform deep online searching (via Tavily, Perplexity, or search APIs) to gather and verify recent "
                "market reports, technical articles, and exact figures relevant to the goal.\n\n"
                f"Swarm Goal:\n{goal}\n\n"
                "Find exact numbers, timelines, and verified facts. Call out discrepancies."
            ),
            skills=["research-recon"],
            priority=priority
        )
    elif profile == "clerk":
        return SwarmWorkerSpec(
            profile="clerk",
            title=f"Clerk repository context: {goal[:60]}...",
            body=(
                "Inspect local repository structures, files, codebases, local knowledge graphs, or ledger assets "
                "to contextually map this goal against our local workspace state.\n\n"
                f"Swarm Goal:\n{goal}\n\n"
                "Report on current files, code constraints, and local documentation."
            ),
            skills=["codebase-inspection"],
            priority=priority
        )
    else:
        # Generic spec for custom cheap1/2/3 or frontier1/2/3 workers
        return SwarmWorkerSpec(
            profile=profile,
            title=f"Worker ({profile}) analysis: {goal[:60]}...",
            body=(
                f"Provide your analysis and perspectives on the research goal from your model's lens.\n\n"
                f"Swarm Goal:\n{goal}\n\n"
                "Conduct research, outline your findings, and log your structured insights."
            ),
            skills=[],  # Custom workers leverage their own profile default skills
            priority=priority
        )

def main():
    parser = argparse.ArgumentParser(description="Spawn a Kanban Swarm to resolve a reasoning/research goal.")
    parser.add_argument("goal", help="The research goal or question to analyze.")
    parser.add_argument("--workers", default="scout,researcher,clerk", 
                        help="Comma-separated list of worker profiles (default: scout,researcher,clerk).")
    parser.add_argument("--verifier", default="reviewer", 
                        help="Profile to assign as verifier/gatekeeper (default: reviewer).")
    parser.add_argument("--synthesizer", default="analyst", 
                        help="Profile to assign as final synthesizer (default: analyst).")
    parser.add_argument("--tenant", default=os.environ.get("HERMES_TENANT"), help="Tenant namespace.")
    parser.add_argument("--priority", type=int, default=10, help="Priority tiebreaker (default 10).")
    parser.add_argument("--created-by", default="swarm-orchestrator", help="Creator name (default swarm-orchestrator).")
    parser.add_argument("--json", action="store_true", help="Emit output in JSON format.")
    args = parser.parse_args()

    goal = args.goal.strip()
    if not goal:
        print("Error: goal must not be empty.", file=sys.stderr)
        sys.exit(1)

    # Parse and build worker profiles
    profiles_list = [p.strip() for p in args.workers.split(",") if p.strip()]
    if not profiles_list:
        print("Error: must provide at least one worker profile.", file=sys.stderr)
        sys.exit(1)

    workers = [get_specialized_worker(p, goal, args.priority) for p in profiles_list]

    try:
        conn = kb.connect()
    except Exception as e:
        print(f"Error: Could not connect to Kanban SQLite database: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        swarm = ks.create_swarm(
            conn=conn,
            goal=goal,
            workers=workers,
            verifier_assignee=args.verifier,
            synthesizer_assignee=args.synthesizer,
            root_title=f"Swarm: {goal[:60]}...",
            tenant=args.tenant,
            created_by=args.created_by,
            priority=args.priority,
        )
    except Exception as e:
        print(f"Error spawning Kanban Swarm graph: {e}", file=sys.stderr)
        sys.exit(1)

    # Subscribe original session platform / chat to the synthesizer task so gateway auto-sends final report
    platform = os.environ.get("HERMES_SESSION_PLATFORM")
    chat_id = os.environ.get("HERMES_SESSION_CHAT_ID")
    thread_id = os.environ.get("HERMES_SESSION_THREAD_ID")

    subscribed = False
    if platform and chat_id:
        try:
            cmd = [
                "/Users/ambler/.hermes/hermes-agent/venv/bin/hermes",
                "kanban",
                "notify-subscribe",
                swarm.synthesizer_id,
                "--platform", platform,
                "--chat-id", chat_id,
            ]
            if thread_id:
                cmd.extend(["--thread-id", thread_id])
            
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            subscribed = True
        except Exception as e:
            print(f"Warning: Failed to subscribe chat context to task {swarm.synthesizer_id}: {e}", file=sys.stderr)

    if args.json:
        result = swarm.as_dict()
        result["subscribed"] = subscribed
        print(json.dumps(result, indent=2))
    else:
        print("Kanban Swarm v1 Graph Spawned successfully!")
        print(f"  Swarm Root Card:   {swarm.root_id}")
        print(f"  Workers:           {', '.join(swarm.worker_ids)} ({args.workers})")
        print(f"  Verifier:          {swarm.verifier_id} ({args.verifier})")
        print(f"  Synthesizer:       {swarm.synthesizer_id} ({args.synthesizer})")
        if subscribed:
            print(f"  Notifications:     Subscribed active channel {platform}:{chat_id}:{thread_id} to Synthesizer {swarm.synthesizer_id}.")
            print("  Handoff Target:    Once the analyst synthesizes the findings, the final Markdown report will be delivered here automatically.")

if __name__ == "__main__":
    main()
