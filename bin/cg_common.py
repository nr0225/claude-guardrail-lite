"""Shared helpers for claude-guardrail-pack (stdlib only, Python 3.8+)."""
import hashlib, json, os, time

HOME = os.environ.get("CLAUDE_GUARDRAIL_HOME", os.path.expanduser("~/.claude-guardrail"))
APPROVALS = os.path.join(HOME, "approvals.json")
RECEIPTS = os.path.join(HOME, "receipts.jsonl")
RULES = os.environ.get("CLAUDE_GUARDRAIL_RULES", os.path.join(HOME, "rules.json"))


def ensure_home():
    os.makedirs(HOME, mode=0o700, exist_ok=True)


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    ensure_home()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def fingerprint(tool_name, subject):
    """Deterministic 6-char code for one exact tool call."""
    h = hashlib.sha256(("%s\x00%s" % (tool_name, subject.strip())).encode("utf-8")).hexdigest()
    return h[:6].upper()


def receipt(entry):
    ensure_home()
    entry = dict(entry, ts=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    with open(RECEIPTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
