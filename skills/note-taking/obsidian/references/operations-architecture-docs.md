# Operations Architecture Docs in Obsidian

Use this pattern when the user asks for durable documentation of a local operational system (dashboard, terminal, pipeline cockpit, service bundle, or automation surface) in the Obsidian vault.

## Target location

- Operational/system runbooks and living architecture notes belong under `~/Obsidian/main-vault/40-Operations/<System Name>/` unless the user gives a more specific path.
- Prefer a stable human-readable file name such as `Terminal Architecture.md`, `Runbook.md`, or `Service Map.md`.

## What to inspect before writing

Gather facts from the actual local system rather than relying on memory or generic assumptions:

1. Code root and entrypoint (`app.py`, scripts, templates, generated artifacts).
2. Runtime wrapper scripts and environment variables.
3. macOS LaunchAgent/systemd/service labels, plist paths, log paths, and restart commands.
4. Local and tailnet URLs; verify local health with `curl -I` when feasible.
5. Tailscale Serve or reverse-proxy configuration.
6. Data sources, output artifacts, side effects, and any staging/sync boundaries.
7. Known pitfalls such as port mismatches, generated-artifact vs generator edits, external-volume permissions, and adjacent services that must not be confused.

## Recommended document shape

Use frontmatter plus a concise but complete architecture/runbook:

- Purpose and scope
- Runtime topology diagram (Mermaid is acceptable in Obsidian)
- Serving/process model
- Code layout
- Navigation/routes or user-facing surfaces
- Data source and side-effect table
- Subsystem sections for major workflows
- Health checks and restart/log commands
- Known pitfalls/design constraints
- Extension/update pattern
- Documentation TODOs

## Quality bar

The note should be useful as the first place to look six months later. Include exact paths and commands, but avoid turning it into a one-off session transcript. If runtime artifacts are generated, explicitly name the generator scripts so future changes happen at the durable source, not only in generated output.
