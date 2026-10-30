# Changelog

## 0.1.2 (2026-10-30)
Security release, same hook code as the full pack 0.1.2.
- Fix (self-approval): self-protection is built into the hook. Paths are resolved
  (`~`, `$HOME`, `../`, globs, braces, variables, quote splitting, symlinks, hardlinks,
  case-insensitive names) before checking them against the guardrail's own files. In 0.1.1
  quoting (`.claude-guard""rail`), globs (`~/.claude-g*`), symlinks made by glob, NotebookEdit,
  MCP file tools or a fake pty around `cg-approve` could still forge an approval.
- Fix: approvals are bound to the SHA-256 of the exact call, not just the 6-char code.
- Fix: `cg-approve` only approves a call the hook actually blocked and shows it first.
- Fix: approvals are consumed under a file lock; an empty rules.json fails closed.
- Fix: in 0.1.1 a 60,000-character command of `>` characters kept the hook busy past its
  10 s timeout (a timed-out hook lets the call run). Patterns now use bounded repetition and
  a keyword prefilter, and Bash commands over 100,000 characters are denied.
- New rules `opaque-shell` (eval, decode-and-run, piping into a shell, `$'\x..'`) and
  `guardrail-reference` (files whose content names the guardrail), both approvable.
- Wider `git-push-protected` (`-uf`, `--mirror`, `HEAD:refs/heads/main`, global options)
  and `rm-recursive-force` (`find … -delete`, quoting tricks).
- Matcher is now `Bash|Edit|Write|MultiEdit|NotebookEdit|mcp__.*`; `install.sh --apply`
  widens an existing entry and replaces an unmodified older rules.json (backup kept).

## 0.1.1 (2026-10-30)
- Write/Edit could change `~/.claude-guardrail/approvals.json`; `rm -r -f` and
  `git -C dir push` were missed; bad input could crash the hook. All fixed.

## 0.1 (2026-10-19)
- First beta: `git-push-protected`, `rm-recursive-force`, `claude-settings`, `self-protect`.
