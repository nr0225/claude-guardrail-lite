# claude-guardrail-lite (free)

> **⚠️ Beta (v0.1).** Not yet verified in a live Claude Code session; the hook logic is unit-tested against simulated PreToolUse events only. Please report anything odd via Issues.
> **This is a regex guardrail, not a sandbox.** It catches common accidents (force pushes, `rm -rf`); it does not contain a determined or obfuscating agent.
>
> **⚠️ Beta（v0.1）**：尚未在實際 Claude Code session 中驗證，只以模擬的 PreToolUse 事件做過單元測試。**這是 regex 護欄，不是沙箱。**

> 免費 lite 版只含 `git-push-protected`、`rm-recursive-force` 兩條規則（加上保護自身的 `self-protect`、`claude-settings`）。完整版另含 ORM、Terraform/K8s、SQL、.env 等規則與測試套件。
> Free lite edition: two rules (`git-push-protected`, `rm-recursive-force`) plus self-protection. The full pack adds ORM, infra, SQL and .env rules plus a test suite. [Get the full pack (US$19)](https://buy.polar.sh/polar_cl_Y93JwF9WRZO9j6w2v0tJJ5xAqwKJGnuufCWC72QKCm0).


Claude Code 的「先擋再核准」護欄。高風險指令一律先 **deny**，人類在自己的終端機輸入一次性核准碼後才放行，每次決策都留一筆 JSONL 收據。

A deny-first guardrail for Claude Code. Risky tool calls are always **denied** until a human approves that exact call from their own terminal with a one-time code. Every decision is written to a JSONL receipt log.

## 為什麼不用 `"ask"` / Why not `"ask"`

在 `auto`（以及 `bypassPermissions` 等非互動模式）下，PreToolUse hook 回傳 `"ask"` 會被直接放行，見 [anthropics/claude-code#89561](https://github.com/anthropics/claude-code/issues/89561) 和 [#51255](https://github.com/anthropics/claude-code/issues/51255)。本套件只回 `deny` 或不表態，所以任何模式都擋得住。

In `auto` and other non-interactive modes a PreToolUse `"ask"` silently becomes allow (see the issues above). This pack only ever returns `deny` or stays silent, so it holds in every permission mode.

## 安裝 / Install

需要 / Requires: `python3` (3.8+, stdlib only), macOS or Linux.

```bash
./install.sh          # 複製檔案並印出 settings.json 片段 / copy files, print the snippet
./install.sh --apply  # 同時寫入 ~/.claude/settings.json（會先備份）/ also merge the hook (backup kept)
```

## 使用流程 / Flow

1. Claude 想執行 `git push origin main` → 被擋，訊息附核准碼，例如 `8888B4`。
   Claude tries `git push origin main` and is denied with a code such as `8888B4`.
2. 你在**自己的**終端機執行 `cg-approve 8888B4`，再輸入一次核准碼確認。
   In **your own** terminal run `cg-approve 8888B4` and retype the code to confirm.
3. 叫 Claude 重試**完全相同**的指令 → 放行一次，核准碼隨即失效（預設 10 分鐘內有效）。
   Tell Claude to retry the identical command. It passes once, then the code is spent (valid 10 minutes by default).
4. `cg-receipts` 看最近 20 筆決策。 / `cg-receipts` shows the last 20 decisions.

## 限制 / Limitations (please read)

- 這是防「手滑」的護欄，不是沙箱。刻意混淆的指令（例如用變數拼字、base64）可能繞過 regex。
  This stops accidents, not a determined adversary. Obfuscated commands can slip past regexes.
- `cg-approve` 需要真正的終端機（`/dev/tty`），而且 agent 的指令只要提到它就會被擋，但這不是密碼學等級的隔離。
  `cg-approve` requires a real terminal and any agent command that mentions it is denied, but this is not cryptographic isolation.
- 規則解析或輸入錯誤時一律 fail closed（擋下）。 / Bad input or missing rules fail closed.

## License

MIT, see [LICENSE](LICENSE).
