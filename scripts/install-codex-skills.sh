#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${CODEX_HOME:-$HOME/.codex}/skills"

python3 "$ROOT/scripts/sync-codex-skills.py"
mkdir -p "$DEST"

for skill_dir in "$ROOT"/codex-skills/*; do
  [ -d "$skill_dir" ] || continue
  name="$(basename "$skill_dir")"
  rm -rf "$DEST/$name"
  cp -R "$skill_dir" "$DEST/$name"
done

chmod +x "$ROOT"/tools/*.py "$ROOT"/tools/*.sh 2>/dev/null || true

echo "Installed Codex skills to $DEST"
echo 'Restart Codex App, open Skills, then choose AI Berkshire 投研路由 or invoke $research.'
echo "Legacy custom prompts are optional and supported only as a deprecated CLI/IDE compatibility layer."
