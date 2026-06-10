# Custom Agent Skills

Portable, cross-agent skills for Hermes, Claude Code, Codex, and other AI agents.
These skills are decoupled from specific machine configurations, local secrets, and runtime paths.

## Installation into Hermes

Clone this repository and symlink or copy individual skills into `~/.hermes/skills/`:

```bash
cd ~/.hermes/skills/
ln -s ~/agent-skills/skills/benchmarks/benchmark-common benchmark-common
```
