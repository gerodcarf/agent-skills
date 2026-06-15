#!/Users/ambler/.hermes/hermes-agent/venv/bin/python
"""
Create a Kanban Swarm v1 graph:
    Librarian Context Compilation
    └─ parallel workers (customizable via --workers)
         └─ verifier (customizable via --verifier)
              └─ synthesizer (customizable via --synthesizer)

Subscribes the orchestrating chat platform (Discord, etc.) to the final 
synthesizer task so that outcomes are auto-delivered back to the session thread.
"""

import sys
import os
import argparse
import json
import sqlite3
import shlex
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

# Incorporate hermes_cli search path
HERMES_AGENT_PATH = "/Users/ambler/.hermes/hermes-agent"
if HERMES_AGENT_PATH not in sys.path:
    sys.path.insert(0, HERMES_AGENT_PATH)

from hermes_cli import kanban_db as kb
from hermes_cli import kanban_swarm as ks
from hermes_cli.kanban_swarm import SwarmWorkerSpec

@dataclass(frozen=True)
class CommitteeCreated:
    """IDs produced by :func:`create_committee_swarm`."""
    root_id: str
    librarian_id: str
    worker_ids: list[str]
    verifier_id: str
    synthesizer_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "root_id": self.root_id,
            "librarian_id": self.librarian_id,
            "worker_ids": list(self.worker_ids),
            "verifier_id": self.verifier_id,
            "synthesizer_id": self.synthesizer_id,
        }

def get_specialized_worker(profile: str, goal: str, priority: int) -> SwarmWorkerSpec:
    """Returns a specialized SwarmWorkerSpec if the profile matches standard roles, 
    otherwise falls back to a generic spec."""
    context_instruction = (
        "\n\nIMPORTANT: A pre-compiled context file `kos_context.md` will be generated in your workspace "
        "before you run by the librarian task. You MUST read this file first (using read_file / open-file inside "
        "your workspace directory) to ground your analysis in our existing Knowledge OS files, local databases, "
        "and hindsight memories.\n\n"
        "SOURCE TRACEABILITY REQUIREMENT: Your report must preserve provenance, not just conclusions. Include:\n"
        "1. `## Source Ledger` table with Source ID, type, title/name, URL or local path, date/access date, why used, credibility notes.\n"
        "2. `## Claim Register` table with Claim ID, claim, Source IDs, confidence, and caveats.\n"
        "3. Stable IDs prefixed by your worker/profile, e.g. `worker-frontier1-S01` and `worker-frontier1-C03`.\n"
        "4. Every material factual claim, number, ticker mapping, market-size estimate, replacement claim, and catalyst must cite one or more Source IDs.\n"
        "5. Separate fact from inference. Cite facts directly; label inference and cite the facts it depends on.\n"
        "6. If using `kos_context.md`, cite the original KOS path/section where visible; if provenance is incomplete, mark it `KOS excerpt — provenance incomplete`."
    )

    if profile == "scout":
        return SwarmWorkerSpec(
            profile="scout",
            title=f"Scout perspective: {goal[:60]}...",
            body=(
                "Establish the macroeconomic, structural, organizational, and strategic/geopolitical vectors "
                "surrounding the goal.\n\n"
                f"Swarm Goal:\n{goal}\n\n"
                "Focus on non-obvious choke points, talent movement, and the strategic landscape. Document key findings."
                + context_instruction
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
                + context_instruction
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
                + context_instruction
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
                "Conduct research, outline your findings, and log your structured insights.\n\n"
                "IMPORTANT: Save your full analysis as a markdown report to your workspace "
                "using write_file to `report.md` (relative path). Post a summary to the blackboard via kanban_comment "
                "on the root task with key findings. Do NOT only post to the blackboard — the written artifact is required."
                + context_instruction
            ),
            skills=[],  # Custom workers leverage their own profile default skills
            priority=priority
        )

def load_preset(name: str) -> dict:
    """Load a named panel preset from presets.json."""
    presets_path = Path(__file__).parent / "presets.json"
    if not presets_path.exists():
        print(f"Error: presets.json not found at {presets_path}", file=sys.stderr)
        sys.exit(1)
    with open(presets_path) as f:
        presets = json.load(f)
    if name not in presets:
        available = ", ".join(sorted(presets.keys()))
        print(f"Error: preset '{name}' not found. Available: {available}", file=sys.stderr)
        sys.exit(1)
    return presets[name]

def create_committee_swarm(
    conn: sqlite3.Connection,
    *,
    goal: str,
    workers: Iterable[SwarmWorkerSpec],
    verifier_assignee: str,
    synthesizer_assignee: str,
    root_title: Optional[str] = None,
    verifier_title: str = "Verify committee outputs",
    synthesizer_title: str = "Synthesize committee outputs",
    tenant: Optional[str] = None,
    created_by: str = "committee-orchestrator",
    workspace_root: str = "/Users/ambler/.hermes/kanban/workspaces",
    priority: int = 0,
    idempotency_key: Optional[str] = None,
) -> CommitteeCreated:
    goal = ks._require_text(goal, "goal")
    verifier_assignee = ks._require_text(verifier_assignee, "verifier_assignee")
    synthesizer_assignee = ks._require_text(synthesizer_assignee, "synthesizer_assignee")
    worker_specs = list(workers)
    if not worker_specs:
        raise ValueError("at least one worker is required")
    for i, spec in enumerate(worker_specs, start=1):
        ks._require_text(spec.profile, f"workers[{i}].profile")
        ks._require_text(spec.title, f"workers[{i}].title")

    # 1. Create root task
    root_title = root_title or f"Committee: {goal.splitlines()[0][:80]}"
    root = kb.create_task(
        conn,
        title=root_title,
        body=(
            "Kanban Committee planning/root card. This card is completed "
            "immediately so the pipeline can start while it remains the "
            "shared blackboard and audit anchor.\n\n"
            f"Goal:\n{goal}"
        ),
        assignee=created_by,
        created_by=created_by,
        tenant=tenant,
        priority=priority,
        idempotency_key=idempotency_key,
        workspace_kind="dir",
        workspace_path=None,
        skills=["kanban-orchestrator"],
    )

    # 2. Setup path
    swarm_workspace_dir = os.path.join(workspace_root, root)
    os.makedirs(swarm_workspace_dir, exist_ok=True)

    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET workspace_path = ? WHERE id = ?", (swarm_workspace_dir, root))
    conn.commit()

    # Recover existing topology if any
    existing = ks.latest_blackboard(conn, root).get("topology")
    if isinstance(existing, dict):
        worker_ids = [str(x) for x in existing.get("worker_ids", []) if x]
        verifier_id = existing.get("verifier_id")
        synthesizer_id = existing.get("synthesizer_id")
        librarian_id = existing.get("librarian_id")
        if worker_ids and verifier_id and synthesizer_id and librarian_id:
            return CommitteeCreated(
                root_id=root,
                librarian_id=str(librarian_id),
                worker_ids=worker_ids,
                verifier_id=str(verifier_id),
                synthesizer_id=str(synthesizer_id),
            )

    kb.complete_task(
        conn,
        root,
        summary="Committee topology planned; root remains the shared blackboard.",
        metadata={
            "kind": "kanban_committee_v1",
            "goal": goal,
            "worker_count": len(worker_specs),
        },
    )

    context_suffix = ks._swarm_context(root, goal)

    # 3. Create context compiler task (assigned to librarian)
    librarian_body = (
        "Run the context compiled database feeding script to pull and bundle data "
        "from local Obsidian, Neo4j, Hindsight, and Bookshelf index into `kos_context.md`. "
        "Run this terminal command exactly:\n\n"
        "```bash\n"
        f"/Users/ambler/.hermes/hermes-agent/venv/bin/python "
        f"~/agent-skills/skills/software-development/answer-panel/scripts/librarian_feeder.py "
        f"--goal {shlex.quote(goal)} --workspace-dir {shlex.quote(swarm_workspace_dir)}\n"
        "```\n\n"
        "Verify that `kos_context.md` was successfully created under your workspace, then mark this task done."
        + context_suffix
    )

    librarian_id = kb.create_task(
        conn,
        title=f"Librarian context compile: {goal[:60]}...",
        body=librarian_body,
        assignee="librarian",
        created_by=created_by,
        parents=[root],
        tenant=tenant,
        priority=priority + 5, # High priority to execute first
        workspace_kind="dir",
        workspace_path=swarm_workspace_dir,
        skills=["codebase-inspection"]
    )

    # 4. Create workers (depend on librarian)
    worker_ids = []
    for spec in worker_specs:
        worker_id = kb.create_task(
            conn,
            title=spec.title,
            body=(spec.body or "") + context_suffix,
            assignee=spec.profile,
            created_by=created_by,
            parents=[librarian_id],  # Dependencies gate until librarian finishes
            tenant=tenant,
            priority=spec.priority or priority,
            workspace_kind="dir",
            workspace_path=swarm_workspace_dir,
            skills=spec.skills or None,
            max_runtime_seconds=spec.max_runtime_seconds,
        )
        worker_ids.append(worker_id)

    # 5. Create verifier (depends on workers)
    verifier_body = (
        "Review every worker handoff and blackboard update. Gate the swarm: "
        "complete only with metadata {\"gate\": \"pass\"} when evidence is "
        "sufficient; otherwise block with exact missing work.\n\n"
        "SOURCE AUDIT REQUIREMENT: You must evaluate worker credibility and source tracing. Include:\n"
        "1. `## Source Credibility Audit` table with Source ID, Worker, Primary/secondary, Timeliness, Directness, Credibility verdict, Carry forward? (Y/N), Notes.\n"
        "2. `## Unsupported or Weakly Supported Claims` table with Claim ID, Claim, Problem, Required fix.\n"
        "3. Verify that key claims are tied to stable source IDs and that source paths or URLs are recoverable.\n"
        "4. BLOCK the swarm if key claims lack source IDs, rely on unvetted model memory without sources, or source links are missing or non-recoverable."
        + context_suffix
    )
    verifier = kb.create_task(
        conn,
        title=verifier_title,
        body=verifier_body,
        assignee=verifier_assignee,
        created_by=created_by,
        parents=worker_ids,
        tenant=tenant,
        priority=priority,
        workspace_kind="dir",
        workspace_path=swarm_workspace_dir,
        skills=["requesting-code-review"],
    )

    # 6. Create synthesizer (depends on verifier)
    synthesizer_body = (
        "Synthesize the verified worker outputs into the final deliverable. "
        "Do not start until the verifier has passed the gate.\n\n"
        "SOURCE TRANSPARENCY REQUIREMENT: You must carry references and source IDs through key claims in the final synthesis.\n"
        "1. Do not introduce new material factual claims without source IDs and references.\n"
        "2. Do not include claims marked by the verifier as failed/unsupported unless explicitly highlighting them as disputed.\n"
        "3. Include a `## References / Source Traceability` table at the end of the report representing: Final claim, Worker claim IDs, Source IDs, Original references (URLs/paths/citations).\n"
        "4. Include inline citations to Source IDs (e.g. `[worker-frontier1-S01]`) for key factual points, numbers, and catalysts."
        + context_suffix
    )
    synthesizer = kb.create_task(
        conn,
        title=synthesizer_title,
        body=synthesizer_body,
        assignee=synthesizer_assignee,
        created_by=created_by,
        parents=[verifier],
        tenant=tenant,
        priority=priority,
        workspace_kind="dir",
        workspace_path=swarm_workspace_dir,
        skills=["humanizer"],
    )

    created = CommitteeCreated(root, librarian_id, worker_ids, verifier, synthesizer)
    ks.post_blackboard_update(
        conn,
        root,
        author=created_by,
        key="topology",
        value=created.as_dict() | {"goal": goal},
    )
    return created

def main():
    parser = argparse.ArgumentParser(description="Spawn a Kanban Committee Swarm to resolve a reasoning/research goal.")
    parser.add_argument("goal", help="The research goal or question to analyze.")
    parser.add_argument("--workers", default="scout,researcher,clerk", 
                        help="Comma-separated list of worker profiles (default: scout,researcher,clerk).")
    parser.add_argument("--preset", default=None,
                        help="Load worker list from a named preset in presets.json.")
    parser.add_argument("--verifier", default="reviewer", 
                        help="Profile to assign as verifier/gatekeeper (default: reviewer).")
    parser.add_argument("--synthesizer", default="analyst", 
                        help="Profile to assign as final synthesizer (default: analyst).")
    parser.add_argument("--tenant", default=os.environ.get("HERMES_TENANT"), help="Tenant namespace.")
    parser.add_argument("--priority", type=int, default=10, help="Priority tiebreaker (default 10).")
    parser.add_argument("--created-by", default="committee-orchestrator", help="Creator name (default committee-orchestrator).")
    parser.add_argument("--json", action="store_true", help="Emit output in JSON format.")
    parser.add_argument("--model-overrides", default="",
                        help="Comma-separated profile:model overrides (e.g. worker-frontier1:cx/gpt-5.5-high).")
    args = parser.parse_args()

    goal = args.goal.strip()
    if not goal:
        print("Error: goal must not be empty.", file=sys.stderr)
        sys.exit(1)

    # Parse and build worker profiles
    if args.preset:
        preset_data = load_preset(args.preset)
        profiles_list = preset_data["panel"]
        if "judge" in preset_data:
            args.synthesizer = preset_data["judge"]
    else:
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

    # Persistent workspaces root mapping
    workspace_root = os.path.expanduser("~/.hermes/kanban/workspaces")
    os.makedirs(workspace_root, exist_ok=True)

    try:
        swarm = create_committee_swarm(
            conn=conn,
            goal=goal,
            workers=workers,
            verifier_assignee=args.verifier,
            synthesizer_assignee=args.synthesizer,
            root_title=f"Committee: {goal[:60]}...",
            tenant=args.tenant,
            created_by=args.created_by,
            priority=args.priority,
            workspace_root=workspace_root,
        )
    except Exception as e:
        print(f"Error spawning Kanban Committee Swarm graph: {e}", file=sys.stderr)
        sys.exit(1)

    all_task_ids = [swarm.root_id, swarm.verifier_id, swarm.synthesizer_id, swarm.librarian_id] + swarm.worker_ids

    # Apply database runtime model overrides if specified
    model_override_applied = []
    if args.model_overrides:
        overrides = {}
        for item in args.model_overrides.split(","):
            if ":" in item:
                prof, mod = item.split(":", 1)
                overrides[prof.strip()] = mod.strip()
        
        cursor = conn.cursor()
        for task_id in all_task_ids:
            cursor.execute("SELECT assignee FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row and row[0] in overrides:
                target_model = overrides[row[0]]
                cursor.execute("UPDATE tasks SET model_override = ? WHERE id = ?", (target_model, task_id))
                model_override_applied.append(f"{row[0]} -> {target_model}")
        conn.commit()

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
        result["model_overrides"] = model_override_applied
        print(json.dumps(result, indent=2))
    else:
        print("Kanban Committee Swarm Graph Spawned successfully!")
        print(f"  Committee Root Card:   {swarm.root_id}")
        print(f"  Librarian context:     {swarm.librarian_id} (librarian)")
        print(f"  Workers:               {', '.join(swarm.worker_ids)} ({', '.join(profiles_list)})")
        print(f"  Verifier:              {swarm.verifier_id} ({args.verifier})")
        print(f"  Synthesizer:           {swarm.synthesizer_id} ({args.synthesizer})")
        if model_override_applied:
            print(f"  Model Overrides:       {', '.join(model_override_applied)}")
        if subscribed:
            print(f"  Notifications:         Subscribed active channel {platform}:{chat_id}:{thread_id} to Synthesizer {swarm.synthesizer_id}.")
            print("  Handoff Target:        Once the analyst synthesizes the findings, the final Markdown report will be delivered here automatically.")

if __name__ == "__main__":
    main()
