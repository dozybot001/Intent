# Reporting security issues / 安全问题报告

Please do not open a public issue for a security problem in Intent CLI or IntHub.

- Email <support@tenonai.cn> with "Intent security" in the subject.
- Or use GitHub's private [Report a vulnerability](https://github.com/dozybot001/Intent/security/advisories/new).
- Tenon AI's [security policy](https://tenonai.cn/security/#report) describes how reports are handled.

Include the affected version (`itt version`) or commit, steps to reproduce and the impact you expect. Never include a real access token, private `.intent/` content or anyone else's data.

Scope: the CLI (`itt`), the agent Skill and the install scripts in this repository, IntHub Local (`itt hub start`), and the hosted IntHub at inthub.tenonai.cn. Fixes ship in the latest 8.x release.

发现 Intent CLI 或 IntHub 的安全问题，请不要开公开的 issue。

- 邮件：<support@tenonai.cn>，标题注明「Intent 安全」。
- 或者用 GitHub 的「[Report a vulnerability](https://github.com/dozybot001/Intent/security/advisories/new)」（私下报告）。
- 报告和答复的做法见榫卯 Tenon AI 的[安全政策](https://tenonai.cn/zh/security/#report)。

请写明：受影响的版本（`itt version`）或提交、复现步骤、你认为的影响。请不要在报告里放真实的访问令牌、`.intent/` 里的私有内容或别人的数据。

范围：这个仓库里的命令行工具（`itt`）、Agent Skill 和安装脚本，IntHub Local（`itt hub start`），以及 inthub.tenonai.cn 上托管的 IntHub。修复随最新的 8.x 版本发布。

## Security boundaries

- **`.intent/`** is plain JSON and may hold goals, reasoning and decisions. `itt init` keeps it out of Git in that clone only, through `.git/info/exclude`. Review it before you share or commit it.
- **Access tokens.** `itt auth login` stores the token with Git's credential helper, for one IntHub address, so it is as safe as that helper: the macOS Keychain, for example, or plain text with `credential.helper=store`. Where no helper can store it, the token goes to `credentials.json` in the user-level Intent config folder, readable only by you. Tokens never enter `.intent/`. `--token` and `INTHUB_TOKEN` are never saved, and are sent only to an address given on the command line, the user-level address or loopback, never to one named only by a shared `.intent/hub.json`. Remote addresses must use HTTPS.
- **IntHub Local** is for one person on a trusted machine and has no accounts: anything that can reach it can read and write its history. It listens on 127.0.0.1, answers only same-origin requests on loopback host names, refuses to start without sign-in on any other interface, and keeps history unencrypted in `~/.inthub/inthub.db`. Do not expose it to a network or put it behind a reverse proxy.
- **The hosted IntHub** uses Tenon sign-in (OIDC with PKCE), host-only `Secure`, `HttpOnly`, `SameSite=Strict` session cookies, per-account isolation, revocable access tokens stored as hashes, same-origin checks on browser writes and a strict Content Security Policy. A browser session can only read history; pushing needs an access token. If a token may have leaked, revoke it in Settings.

## 安全边界

- **`.intent/`** 是普通 JSON，可能包含目标、推理和决策。`itt init` 只在当前克隆里通过 `.git/info/exclude` 把它排除出 Git。共享或提交之前请先检查。
- **访问令牌。** `itt auth login` 用 Git 的凭据助手保存令牌，只对应一个 IntHub 地址，安全性取决于这个助手：例如 macOS 钥匙串；设了 `credential.helper=store` 就是明文。没有助手能保存时，令牌放在用户级 Intent 配置目录的 `credentials.json`，只有你能读。令牌不会进 `.intent/`。`--token` 和 `INTHUB_TOKEN` 不保存，只发往命令行给出的地址、用户级地址或本机回环地址，不会发往只在共享的 `.intent/hub.json` 里出现的地址。远程地址必须用 HTTPS。
- **IntHub Local** 供一个人在可信的电脑上用，没有账号：能连上它的程序都能读写它的历史。它监听 127.0.0.1，只回应回环主机名上的同源请求，不登录时拒绝在其他网卡上启动，历史不加密地存在 `~/.inthub/inthub.db`。不要把它暴露到网络上，也不要放在反向代理后面。
- **托管的 IntHub** 用 Tenon 账号登录（OIDC 加 PKCE），会话 Cookie 限定主机并带 `Secure`、`HttpOnly`、`SameSite=Strict`，数据按账号隔离，访问令牌以哈希保存、可以作废，浏览器的写操作要过同源检查，并启用严格的内容安全策略。浏览器会话只能读历史，推送要用访问令牌。令牌可能泄露时，请在设置里作废。
