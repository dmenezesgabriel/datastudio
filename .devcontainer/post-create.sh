#!/usr/bin/env bash
set -euo pipefail

echo "Syncing dependencies..."
uv sync

echo "Installing pre-commit hooks..."
uv run pre-commit install

echo "Installing Claude Code skills..."
npx -y skills add microsoft/playwright-cli --skill '*' -a claude-code -y
npx -y skills add anthropics/skills --skill frontend-design -a claude-code -y

echo "Post-create setup complete!"
