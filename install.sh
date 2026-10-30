#!/usr/bin/env bash
# Install claude-guardrail-lite for the current user.
#   ./install.sh          copy files, then print the settings.json snippet to add yourself
#   ./install.sh --apply  also merge the hook into ~/.claude/settings.json (a backup is kept)
#   ./install.sh --update-rules  replace your rules.json with the shipped one (old file kept as rules.json.bak.*)
#   Options can be combined: ./install.sh --apply --update-rules
set -euo pipefail
APPLY=0; UPDATE_RULES=0
for a in "$@"; do
  case "$a" in
    --apply) APPLY=1;;
    --update-rules) UPDATE_RULES=1;;
    *) echo "unknown option: $a"; exit 1;;
  esac
done
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${CLAUDE_GUARDRAIL_HOME:-$HOME/.claude-guardrail}"
BIN="${CLAUDE_GUARDRAIL_BIN:-$HOME/.local/bin}"
SETTINGS="${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"
command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }

mkdir -p "$DEST/bin" "$BIN"; chmod 700 "$DEST"
cp "$SRC"/bin/cg-* "$SRC"/bin/cg_common.py "$DEST/bin/"; chmod +x "$DEST"/bin/cg-guard "$DEST"/bin/cg-approve "$DEST"/bin/cg-receipts
if [ -f "$DEST/rules.json" ] && [ "$UPDATE_RULES" = 1 ]; then
  cp "$DEST/rules.json" "$DEST/rules.json.bak.$(date +%Y%m%d%H%M%S)"; cp "$SRC/rules.json" "$DEST/rules.json"
  echo "rules.json replaced with the shipped version (backup kept next to it)"
elif [ -f "$DEST/rules.json" ] && python3 -c 'import hashlib,sys; sys.exit(0 if hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest() in sys.argv[2:] else 1)' "$DEST/rules.json" \
    ad9fb603956a4b666351305758bfa2392108fdefee0c6e0842e16bb891c80178 50a7418e2717d91f7a2d9e191607aa96de023f4873db8718e32ca2394fdb16d7; then
  # unmodified rules from an older release: upgrade automatically, keep a backup
  cp "$DEST/rules.json" "$DEST/rules.json.bak.$(date +%Y%m%d%H%M%S)"; cp "$SRC/rules.json" "$DEST/rules.json"
  echo "rules.json was the unmodified file from an older release; replaced with this version (backup kept next to it)"
elif [ -f "$DEST/rules.json" ]; then
  if cmp -s "$SRC/rules.json" "$DEST/rules.json"; then :; else
    echo "keeping your existing $DEST/rules.json (differs from the shipped one; run ./install.sh --update-rules to replace it)"; fi
else
  cp "$SRC/rules.json" "$DEST/rules.json"
fi
ln -sf "$DEST/bin/cg-approve" "$BIN/cg-approve"
ln -sf "$DEST/bin/cg-receipts" "$BIN/cg-receipts"

HOOK_CMD="python3 \"$DEST/bin/cg-guard\""
if [ "$APPLY" = 1 ]; then
  mkdir -p "$(dirname "$SETTINGS")"
  [ -f "$SETTINGS" ] && cp "$SETTINGS" "$SETTINGS.bak.$(date +%Y%m%d%H%M%S)"
  python3 - "$SETTINGS" "$HOOK_CMD" <<'PY'
import json, os, sys
path, cmd = sys.argv[1], sys.argv[2]
s = json.load(open(path)) if os.path.exists(path) and os.path.getsize(path) else {}
pre = s.setdefault("hooks", {}).setdefault("PreToolUse", [])
MATCHER = "Bash|Edit|Write|MultiEdit|NotebookEdit|mcp__.*"
mine = [m for m in pre if any(h.get("command") == cmd for h in m.get("hooks", []))]
if mine:
    for m in mine:  # upgrade from 0.1.0/0.1.1: widen the matcher in place
        m["matcher"] = MATCHER
else:
    pre.append({"matcher": MATCHER, "hooks": [{"type": "command", "command": cmd, "timeout": 10}]})
json.dump(s, open(path, "w"), indent=2)
print(("hook matcher updated in" if mine else "hook added to"), path)
PY
else
  cat <<SNIP
Add this to $SETTINGS (or run ./install.sh --apply):
{
  "hooks": {
    "PreToolUse": [
      {"matcher": "Bash|Edit|Write|MultiEdit|NotebookEdit|mcp__.*",
       "hooks": [{"type": "command", "command": "$(printf '%s' "$HOOK_CMD" | sed 's/"/\\"/g')", "timeout": 10}]}
    ]
  }
}
SNIP
fi
case ":$PATH:" in *":$BIN:"*) ;; *) echo "note: add $BIN to your PATH to use cg-approve";; esac
echo "done. rules: $DEST/rules.json  receipts: cg-receipts"
