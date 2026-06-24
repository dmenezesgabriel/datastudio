#!/usr/bin/env bash
# Restore Claude Code user-level config from the tracked devcontainer files.
# Runs as part of postCreateCommand so settings survive container rebuilds.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p ~/.claude
cp "$SCRIPT_DIR/statusline-command.sh" ~/.claude/statusline-command.sh
chmod +x ~/.claude/statusline-command.sh
cp "$SCRIPT_DIR/claude-settings.json" ~/.claude/settings.json
