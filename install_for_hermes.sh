#!/usr/bin/env bash
set -e

HERMES_SKILLS_DIR="${HERMES_HOME:-$HOME/.hermes}/skills"
mkdir -p "$HERMES_SKILLS_DIR"

echo "Installing Agent Skills into $HERMES_SKILLS_DIR..."

cd "$(dirname "$0")/skills"

for category in */; do
    for skill in "$category"*; do
        if [ -d "$skill" ]; then
            target="$HERMES_SKILLS_DIR/$skill"
            mkdir -p "$(dirname "$target")"
            if [ ! -e "$target" ]; then
                ln -sf "$PWD/$skill" "$target"
                echo "Symlinked $skill"
            else
                echo "Skipped $skill (already exists)"
            fi
        fi
    done
done

echo "Done."
