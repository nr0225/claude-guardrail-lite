#!/usr/bin/env bash
# Install claude-guardrail-lite for the current user.
#   ./install.sh          copy files, then print the settings.json snippet to add yourself
#   ./install.sh --apply  also merge the hook into ~/.claude/settings.json (a backup is kept)
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${CLAUDE_GUARDRAIL_HOME:-$HOME/.claude-guardrail}"
BIN="${CLAUDE_GUARDRAIL_BIN:-$HOME/.local/bin}"
SETTINGS="${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"
command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }

mkdir -p "$DEST/bin" "$BIN"; chmod 700 "$DEST"
cp "$SRC"/bin/cg-* "$SRC"/bin/cg_common.py "$DEST/bin/"; chmod +x "$DEST"/bin/cg-guard "$DEST"/bin/cg-approve "$DEST"/bin/cg-receipts
[ -f "$DEST/rules.json" ] && echo "keeping your existing $DEST/rules.json" || cp "$SRC/rules.json" "$DEST/rules.json"
ln -sf "$DEST/bin/cg-approve" "$BIN/cg-approve"
ln -sf "$DEST/bin/cg-receipts" "$BIN/cg-receipts"

HOOK_CMD="python3 \"$DEST/bin/cg-guard\""
if [ "${1:-}" = "--apply" ]; then
  mkdir -p "$(dirname "$SETTINGS")"
  [ -f "$SETTINGS" ] && cp "$SETTINGS" "$SETTINGS.bak.$(date +%Y%m%d%H%M%S)"
  python3 - "$SETTINGS" "$HOOK_CMD" <<'PY'
import json, os, sys
path, cmd = sys.argv[1], sys.argv[2]
s = json.load(open(path)) if os.path.exists(path) and os.path.getsize(path) else {}
pre = s.setdefault("hooks", {}).setdefault("PreToolUse", [])
if not any(h.get("command") == cmd for m in pre for h in m.get("hooks", [])):
    pre.append({"matcher": "Bash|Edit|Write|MultiEdit", "hooks": [{"type": "command", "command": cmd, "timeout": 10}]})
json.dump(s, open(path, "w"), indent=2)
print("hook added to", path)
PY
else
  cat <<SNIP
Add this to $SETTINGS (or run ./install.sh --apply):
{
  "hooks": {
    "PreToolUse": [
      {"matcher": "Bash|Edit|Write|MultiEdit",
       "hooks": [{"type": "command", "command": "$(printf '%s' "$HOOK_CMD" | sed 's/"/\\"/g')", "timeout": 10}]}
    ]
  }
}
SNIP
fi
case ":$PATH:" in *":$BIN:"*) ;; *) echo "note: add $BIN to your PATH to use cg-approve";; esac
echo "done. rules: $DEST/rules.json  receipts: cg-receipts"
