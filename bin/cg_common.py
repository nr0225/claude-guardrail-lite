"""Shared helpers for claude-guardrail-pack (stdlib only, Python 3.8+)."""
import contextlib, fnmatch, glob, hashlib, itertools, json, os, re, time

try:
    import fcntl
except ImportError:  # native Windows is not supported; keep importable for tests
    fcntl = None

HOME = os.environ.get("CLAUDE_GUARDRAIL_HOME", os.path.expanduser("~/.claude-guardrail"))
APPROVALS = os.path.join(HOME, "approvals.json")
RECEIPTS = os.path.join(HOME, "receipts.jsonl")
LOCK = os.path.join(HOME, ".lock")
RULES = os.environ.get("CLAUDE_GUARDRAIL_RULES", os.path.join(HOME, "rules.json"))
USER_HOME = os.path.expanduser("~")


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
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


@contextlib.contextmanager
def locked():
    """Serialize read-modify-write of approvals.json between hook runs and cg-approve."""
    ensure_home()
    fd = os.open(LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if fcntl:
            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)  # closing releases the flock


def fingerprint(tool_name, subject):
    """6-char code shown to the human. Only a label: approvals are bound to digest()."""
    return digest(tool_name, subject)[:6].upper()


def digest(tool_name, subject):
    """Full SHA-256 of one exact tool call. An approval only matches this exact value."""
    return hashlib.sha256(("%s\x00%s" % (tool_name, subject.strip())).encode("utf-8")).hexdigest()


def load_state():
    """approvals.json v2: {"pending": {code: {...}}, "approved": {code: {...}}}.
    Anything else (including the 0.1.0/0.1.1 flat format) counts as empty."""
    s = load_json(APPROVALS, {})
    if not isinstance(s, dict):
        s = {}
    st = {"pending": s.get("pending"), "approved": s.get("approved")}
    now = time.time()
    for k in st:
        v = st[k] if isinstance(st[k], dict) else {}
        st[k] = {c: e for c, e in v.items() if isinstance(e, dict) and e.get("expires", 0) > now}
    return st


def receipt(entry):
    ensure_home()
    entry = dict(entry, ts=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    with open(RECEIPTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Built-in self-protection. Not configurable through rules.json on purpose.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.realpath(__file__))


def protected_roots():
    roots = {os.path.realpath(HOME), _HERE, os.path.realpath(RULES)}
    return sorted(roots)


SELF_WORDS = re.compile(r"\.claude-guardrail|cg-approve|cg_common|cg-guard|CLAUDE_GUARDRAIL_", re.I)


def _inside(p, roots):
    return any(p == r or p.startswith(r.rstrip(os.sep) + os.sep) for r in roots)


def _protected_inodes(roots):
    out = set()
    for r in roots:
        if os.path.isfile(r):
            st = os.stat(r); out.add((st.st_dev, st.st_ino))
        for dp, _, fs in os.walk(r):
            for f in fs:
                try:
                    st = os.stat(os.path.join(dp, f)); out.add((st.st_dev, st.st_ino))
                except OSError:
                    pass
    return out


def resolve(path, cwd):
    here = cwd or os.getcwd()
    path = re.sub(r"\$\{HOME[^}]*\}|\$HOME\b", lambda _m: USER_HOME, path)
    path = re.sub(r"\$\{(?:PWD|OLDPWD)[^}]*\}|\$(?:PWD|OLDPWD)\b|^~[+-](?=/|$)", lambda _m: here, path)
    path = os.path.expanduser(os.path.expandvars(path))
    if not os.path.isabs(path):
        path = os.path.join(cwd or os.getcwd(), path)
    return os.path.normpath(path)


def touches_guardrail(path, cwd, _cache={}):
    """True if `path` is, or (via symlink, hardlink, ../, case-insensitive FS) reaches,
    a file or directory of the guardrail."""
    roots = protected_roots()
    if SELF_WORDS.search(path):
        return True
    p = resolve(path, cwd)
    if _inside(os.path.realpath(p), roots):
        return True
    # walk up existing ancestors: catches case-insensitive names and bind mounts
    q = p
    while True:
        if os.path.exists(q):
            for r in roots:
                try:
                    if os.path.exists(r) and os.path.samefile(q, r):
                        return True
                except OSError:
                    pass
        parent = os.path.dirname(q)
        if parent == q:
            break
        q = parent
    if os.path.isfile(p):  # hardlink to a guardrail file
        if "inodes" not in _cache:
            _cache["inodes"] = _protected_inodes(roots)
        st = os.stat(p)
        if (st.st_dev, st.st_ino) in _cache["inodes"]:
            return True
    return False


# ---------------------------------------------------------------------------
# Shell text normalization. Regexes are matched against the raw command AND
# these variants, so quoting tricks only ever add matches, never remove them.
# ---------------------------------------------------------------------------
_ANSI_C = re.compile(r"\$'((?:[^'\\]|\\.)*)'")
_ASSIGN = re.compile(r"(?:^|[\s;&|(])(?:export\s+|local\s+|declare\s+(?:-\w+\s+)*)?([A-Za-z_]\w*)=([^\s;&|()]*)")


def _ansi_c(m):
    try:
        return m.group(1).encode("latin-1", "backslashreplace").decode("unicode_escape")
    except Exception:
        return m.group(1)


def _braces(word, limit=64):
    m = re.search(r"\{([^{},]{0,200}(?:,[^{},]{0,200}){1,32})\}", word)
    if not m:
        return [word]
    out = []
    for alt in m.group(1).split(","):
        out.extend(_braces(word[:m.start()] + alt + word[m.end():], limit))
        if len(out) >= limit:
            break
    return out[:limit]


def normalize_shell(cmd):
    s = cmd.replace("\\\n", "")
    s = _ANSI_C.sub(_ansi_c, s)
    s = re.sub(r"\$\{?IFS\}?", " ", s)
    s = re.sub(r"(['\"])\s*\+\s*(['\"])", "", s)      # 'a' + 'b'  (python/js concatenation)
    s = s.replace("'", "").replace('"', "")
    s = re.sub(r"\\(.)", r"\1", s)                     # r\m -> rm
    # expand simple NAME=value assignments made in the same command
    for _ in range(3):
        env = dict(_ASSIGN.findall(s)[:64])
        if not env:
            break
        t = s
        for k, v in env.items():
            t = re.sub(r"\$\{%s\}|\$%s\b" % (k, k), lambda _m, v=v: v, t)
        if t == s:
            break
        s = t
    return s


def shell_variants(cmd, cwd):
    """Raw command, normalized text, and a version with ~, $HOME, braces and globs expanded."""
    norm = normalize_shell(cmd)
    words = [w for w in re.split(r"[\s;&|()<>`=]+", norm) if w]
    extra = []
    globbed = 0
    here = cwd or os.getcwd()
    bases = [here]
    for w in words[:400]:
        for b in _braces(w):
            if b.startswith("~") or "$" in b:
                b = resolve(b, cwd)
                extra.append(b)
            if any(c in b for c in "*?[") and globbed < 40:
                globbed += 1
                for base in ([None] if os.path.isabs(b) else bases):
                    try:
                        extra.extend(itertools.islice(glob.iglob(b if base is None else os.path.join(base, b)), 200))
                    except Exception:
                        pass
            elif b != w:
                extra.append(b)
    return [cmd, norm, norm + " " + " ".join(extra)], words, extra


SELF_NAMES = (".claude-guardrail", "cg-approve")


def glob_could_reach_guardrail(word):
    """Static check, independent of what exists on disk right now: could any path
    component of this glob expand to one of the guardrail's names?"""
    for comp in word.split("/"):
        if not any(c in comp for c in "*?["):
            continue
        if len(re.sub(r"\[[^\]]*\]|[*?]", "", comp)) < 3:
            continue  # too broad to judge from text (.*, *, c*); the disk check covers it
        for name in SELF_NAMES:
            if name.startswith(".") and not comp.startswith((".", "[")):
                continue  # shells do not match a leading dot with * or ? (unless dotglob)
            if fnmatch.fnmatch(name.lower(), comp.lower()):
                return True
    return False


def joined_literals(cmd):
    """Aggressive text variant: glue adjacent string literals ('a' 'b', 'a'+'b', "a"."b",
    ['a', 'b']) so names split across literals become visible. Only used for self-protection."""
    s = cmd.replace("\\\n", "")
    s = re.sub(r"(['\"])\s*(?:[,.+]\s*)?(['\"])", "", s)
    return s.replace("'", "").replace('"', "")


def bash_touches_guardrail(cmd, cwd):
    variants, words, extra = shell_variants(cmd, cwd)
    if any(SELF_WORDS.search(v) for v in variants + [joined_literals(cmd)]):
        return True
    for w in words:
        for b in _braces(w):
            if glob_could_reach_guardrail(b):
                return True
    for w in words + extra:
        if "/" in w or w.startswith(".") or w.startswith("~"):
            if touches_guardrail(w, cwd):
                return True
    if cwd and touches_guardrail(cwd, cwd):
        return True
    return False


def strings_in(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings_in(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings_in(v)
