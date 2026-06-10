# Bulk Property Toggles in Obsidian

Obsidian natively does not have a "toggle" capability for entire property subsets (e.g., turning on/off a set of "Triage properties" in an Inbound folder).

When modifying properties across an entire directory (bulk operations):
1. **Linter Plugin:** Recommending the user set up the "Linter" plugin is often the easiest UI-driven way to bulk add/remove frontmatter properties upon save.
2. **Automated Scripts:** As an agent, the preferred method to bulk toggle or migrate properties is to write a Python script using `yaml` (like `ruamel.yaml` to preserve formatting) and execute a pass across all files in a specific directory (e.g., `__Inbound`).
3. **No UI toggles:** Do not hallucinate a core Obsidian feature that lets a user easily "switch" a property group on/off with one button from the native app interface.