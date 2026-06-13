#!/usr/bin/env bash
set -e

HERMES_SKILLS_DIR="${HERMES_HOME:-$HOME/.hermes}/skills"
mkdir -p "$HERMES_SKILLS_DIR"

echo "Installing Agent Skills into $HERMES_SKILLS_DIR..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_ROOT="$SCRIPT_DIR/skills"

# Walk all categories and subcategories, symlinking leaf skill directories
# (directories containing a SKILL.md file)
find "$SKILLS_ROOT" -name "SKILL.md" -type f | while read -r skill_file; do
    skill_dir="$(dirname "$skill_file")"
    skill_name="$(basename "$skill_dir")"

    # Determine the relative category path from skills root to skill dir's parent
    rel_path="$(realpath --relative-to="$SKILLS_ROOT" "$(dirname "$skill_dir")" 2>/dev/null || python3 -c "import os,sys; print(os.path.relpath(os.path.dirname('$skill_dir'), '$SKILLS_ROOT'))")"

    # Target path mirrors the category structure
    target_parent="$HERMES_SKILLS_DIR/$rel_path"
    target="$target_parent/$skill_name"
    mkdir -p "$target_parent"

    if [ ! -e "$target" ]; then
        ln -sf "$skill_dir" "$target"
        echo "Symlinked ${rel_path}/${skill_name}"
    else
        echo "Skipped ${rel_path}/${skill_name} (already exists)"
    fi
done

echo "Done."
