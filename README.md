# claude-guardrail-lite (free, MIT)

A deny-first PreToolUse hook for Claude Code. Risky tool calls are **denied** until a human approves that exact call from their own terminal with a one-time code. Every decision is written to a local JSONL receipt log.

Claude Code 的「先擋再核准」PreToolUse hook。高風險指令一律先 **deny**，人類在自己的終端機輸入一次性核准碼後才放行，每次決策都留一筆本機 JSONL 收據。

![demo: a simulated PreToolUse event for git push origin main is denied with code 8888B4, cg-approve in a real terminal approves it, the identical retry passes once](docs/demo.gif)

<sub>The demo pipes simulated PreToolUse JSON into the hook by hand; every line of output is real (`docs/demo-transcript.txt`). It is not a recording of a live Claude Code session. 示範是手動把模擬的 PreToolUse 事件送進 hook，輸出都是實際執行結果，不是 Claude Code 實機錄影。</sub>

> **Beta (v0.1.2).** Tested by replaying simulated PreToolUse events, including an adversarial run of 64 tamper attempts against the approval store in a throwaway HOME. Not yet recorded end to end in a live Claude Code session by the author. Please run the self-check below and report anything odd in Issues. **This is a regex guardrail, not a sandbox.**
> **Beta（v0.1.2）**：以模擬的 PreToolUse 事件測試，包含在拋棄式 HOME 裡對核准檔做的 64 種竄改測試。作者尚未在真實 Claude Code session 中錄下完整流程。裝好後請跑下面的自我檢查，有問題請開 Issue。**這是 regex 護欄，不是沙箱。**

## What the lite edition covers / 免費版涵蓋範圍

| id | Blocks / 擋什麼 |
|---|---|
| `git-push-protected` | `git push` with `--force`/`-f`/`--force-with-lease`/`--mirror`/`+branch`, or to main/master/production/prod (also `HEAD:refs/heads/main`, `git -C dir push`, `git --no-pager push`) |
| `rm-recursive-force` | `rm -rf`, `rm -fr`, `rm -r -f`, `rm --recursive --force`, `find … -delete` |
| `claude-settings` | edits to `.claude/settings*.json` (Edit/Write, or shell `>`, `tee`, `sed -i`, `cp`, `mv`, `rm`), so the agent can't switch the hook off |
| `opaque-shell` | commands the hook cannot read because they are built at run time: `eval`, `base64 -d \| sh`, piping anything into `sh`/`bash` (including `curl … \| sh`), `$'\x..'`, `$(printf …)` |
| `guardrail-reference` | Edit/Write/NotebookEdit content that names the guardrail's files or `cg-approve` (for example a script that would edit them) |
| `self-protect` (built in) | any call that names or resolves to the guardrail's files or `cg-approve`. Paths are expanded first (`~`, `$HOME`, `../`, globs, braces, variables, split quotes) and symlinks, hardlinks and case-insensitive names are resolved. Covers Bash, Edit, Write, MultiEdit, NotebookEdit and MCP tools. **Cannot be approved.** |

**Full pack (US$19, one-time):** adds `git reset --hard`/`clean -f`/`branch -D`, ORM force/reset commands (Prisma, Drizzle, Rails, Django, Sequelize), `terraform apply/destroy`, `pulumi up/destroy`, `kubectl delete`, `helm uninstall`, `DROP`/`TRUNCATE`/`DELETE` without `WHERE`, `.env` writes, a unit-test suite, and a commercial license. [Get the full pack](https://buy.polar.sh/polar_cl_Y93JwF9WRZO9j6w2v0tJJ5xAqwKJGnuufCWC72QKCm0?utm_source=github&utm_medium=readme&utm_campaign=lite).
完整版（US$19 一次買斷）另含上述規則、單元測試與商業授權。

## Why not `"ask"` / 為什麼不用 `"ask"`

Several users report in the still-open [anthropics/claude-code#89561](https://github.com/anthropics/claude-code/issues/89561) that a PreToolUse `"ask"` let the tool call run with no prompt (mostly in auto mode; one report in default mode). In the same thread, `"deny"` from the same hook was enforced, and Claude Code's hooks reference documents `"deny"` as preventing the tool call. This hook only returns `deny` or stays silent, so it does not depend on `"ask"`.

多位使用者在仍未關閉的 #89561 回報：hook 回 `"ask"` 時，工具呼叫沒有跳確認就執行了（多數在 auto 模式，也有一則在 default 模式）。同一串裡，同一個 hook 回 `"deny"` 有被執行；官方文件也寫 `"deny"` 會阻止該次呼叫。本 hook 只回 `deny` 或不表態，不依賴 `"ask"`。

## Install / 安裝

Requires `python3` 3.8+ (stdlib only), macOS or Linux. / 需要 `python3` 3.8 以上，macOS 或 Linux。

```bash
git clone https://github.com/nr0225/claude-guardrail-lite && cd claude-guardrail-lite
./install.sh          # copy files, print the settings.json snippet / 複製檔案並印出設定片段
./install.sh --apply  # also merge the hook into ~/.claude/settings.json (backup kept) / 同時寫入設定（會先備份）
```

Upgrading from 0.1 or 0.1.1: `git pull && ./install.sh --apply`. An unmodified old rules.json is replaced (backup kept) and the hook matcher is widened; old approvals stop working. / 從舊版升級：`git pull && ./install.sh --apply`。

Restart Claude Code and run `/hooks` to confirm `cg-guard` is listed. Optional on Claude Code v2.1.295+: add `"onFailure": "block"` to the hook entry so a hook that cannot start or times out blocks instead of allowing.
重開 Claude Code，輸入 `/hooks` 確認看得到 `cg-guard`。Claude Code v2.1.295 以上可在這個 hook 加 `"onFailure": "block"`，hook 跑不起來或逾時時也會擋下。

### Self-check / 自我檢查 (in your own terminal / 在你自己的終端機)

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"git push origin main"},"permission_mode":"auto"}' \
  | python3 ~/.claude-guardrail/bin/cg-guard
# expect permissionDecision "deny" and code 8888B4 / 應看到 deny 和核准碼 8888B4
```

Then ask Claude Code to run `git push --dry-run origin main`; it should be denied with a code.
再請 Claude Code 執行 `git push --dry-run origin main`，應該被擋並顯示核准碼。

## Flow / 使用流程

1. Claude tries `git push origin main` and is denied with a code such as `8888B4`. / Claude 想 push 到 main，被擋並拿到核准碼。
2. In **your own** terminal: `cg-approve 8888B4`. It prints the exact blocked call; retype the code to confirm. / 你在**自己的**終端機執行 `cg-approve 8888B4`，畫面會列出被擋的完整指令，確認後再輸入一次核准碼。
3. Tell Claude to retry the identical command. It passes once; the approval is spent (valid 10 minutes) and is bound to the SHA-256 of that exact call. / 叫 Claude 重試完全相同的指令，放行一次後失效（10 分鐘內有效），核准綁定該指令的 SHA-256。
4. `cg-receipts` shows the last 20 decisions. / `cg-receipts` 看最近 20 筆。

## Limitations / 限制

- Stops accidents, not a determined adversary. The agent runs as your user; a script that computes the path at run time (for example from `chr()` numbers) and is then executed still gets through. Use a container, a separate OS user or a VM against a hostile agent. / 防手滑，不防刻意的對手：agent 跟你是同一個帳號，執行時才算出路徑的腳本仍然擋不到。
- `cg-approve` needs a terminal (`/dev/tty`), but `script` or Python's `pty` can fake one; what stops the agent is that any call naming or resolving to it is denied. Not cryptographic isolation. / `cg-approve` 需要終端機，但可以被假造；真正擋住 agent 的是「提到或指向它就拒絕」，不是密碼學等級的隔離。
- Bash commands over 100,000 characters are denied with no approval (too long to check within the hook timeout). / 超過 10 萬字元的 Bash 指令一律拒絕。
- Some harmless commands are denied with no approval because a glob could reach the guardrail folder, for example `ls ~/.*`. Run those yourself. / 有些無害指令（例如 `ls ~/.*`）會被擋且不能核准，請自己在終端機執行。
- Bare `git push` while on main is not caught (the branch is not in the command text); pair with GitHub branch protection. / 沒寫分支的 `git push` 擋不到，請搭配 branch protection。
- Bash, Edit, Write, MultiEdit, NotebookEdit and `mcp__*` tools are checked; MCP tools only for self-protection. / 檢查 Bash、Edit、Write、MultiEdit、NotebookEdit 與 MCP 工具（MCP 只做自我保護）。
- Missing rules, malformed input or an internal error answer `deny`. If `python3` cannot start or the hook times out, Claude Code continues by default (see `onFailure` above). / 規則不見、輸入錯誤、內部錯誤都回 deny；python3 跑不起來或逾時則預設放行。
- Native Windows is not supported; WSL is untested. / 不支援原生 Windows，WSL 未測。

## Uninstall / 解除安裝

Run in your own terminal (the agent is blocked from `~/.claude-guardrail` on purpose): remove the `cg-guard` entry from `hooks.PreToolUse` in `~/.claude/settings.json`, then `rm ~/.local/bin/cg-approve ~/.local/bin/cg-receipts` and `rm -r ~/.claude-guardrail`.

## License

MIT, see [LICENSE](LICENSE). Not affiliated with Anthropic; "Claude" and "Claude Code" are trademarks of Anthropic.
