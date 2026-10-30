# Intent

中文 | [English](README.md)

[![tests](https://github.com/dozybot001/Intent/actions/workflows/test.yml/badge.svg)](https://github.com/dozybot001/Intent/actions/workflows/test.yml)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![status: beta](https://img.shields.io/badge/status-beta-orange)
![license: MIT](https://img.shields.io/badge/license-MIT-green)

**编码 Agent 记不住你上次做到哪里。Intent 把当前目标、最近一次经过验证的检查点和长期决策保存在 `.intent/` 中，下一次会话或另一个 Agent 可以直接接着做，而不是重新摸索。**

Git 记录代码怎么变；Intent 记录*为什么*这样做、哪些已经验证、下一步是什么，作为代码旁边的一份小型语义历史。

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/inthub-overview-dark.png">
  <img alt="IntHub 接续简报：每个进行中的目标及其下一步、阻塞项、工作边界和已验证状态" src="docs/assets/inthub-overview-light.png">
</picture>

## 为什么不只用 AGENTS.md 或 Agent 记忆？

| 你可能已经在用 | 它保存的是 | Intent 补上的是 |
|---|---|---|
| `AGENTS.md`、`CLAUDE.md`、Cursor rules | 在这个仓库里应该怎么工作 | 工作进行到哪里：当前目标、已验证状态、下一步、阻塞项 |
| Agent 自带的记忆 | 各工具私有、不透明的笔记 | 项目里的普通 JSON，任何 Agent 和你自己都能读 |
| Issue、PR、ADR | 团队计划与评审 | 工作过程中留下的检查点，以及会自动关联到新目标的决策 |
| Git 历史 | 代码改了什么 | 背后的理由，以及真正完成到哪一步 |

## 工作方式

三类对象，全部只追加：

| 对象 | 记录什么 |
|---|---|
| **Intent** | 一个目标，以及它为什么重要 |
| **Snap** | 一个经过验证的检查点：`Verified`、`Boundary`、`Next`、`Blocker`、`Constraints` |
| **Decision** | 约束后续目标的长期规则（例如「支付只走 PaymentIntent」） |

Intent 之间还可以建立关系：组成、衍生、继承、依赖、对立。IntHub 的「流转」页会画出目标如何分出、接续与汇合，以及每个 Decision 出自哪个 Intent（[意图流转](docs/CN/intent-flow.md)）。

开启持续维护后，每一轮 Agent 对话开始时由项目 hook 注入当前状态；只有确实验证了有意义的进展，Agent 才记录一个 Snap；每轮以 `recorded`、`no-op` 或 `failed` 收尾。没有变化的轮次不写入任何内容。Stop hook 只检查这一轮是否完成收尾，不评判语义质量。

## 快速开始

```bash
# 1. 安装 CLI（macOS / Linux），重复执行即可升级
curl -fsSL https://raw.githubusercontent.com/dozybot001/Intent/main/scripts/install.sh | bash

# 2. 为你使用的 Agent 安装 skill（需要 Node.js；也可以用 -a cursor 等）
npx skills add dozybot001/Intent -g -a claude-code -a codex -y

# 3. 在项目中启用（Git 可选）
cd your-project
itt init    # 为你使用的 Agent 配置 hooks（也可以指定 --host codex / claude-code）
```

然后信任一次项目 hooks：Codex 中打开 `/hooks`；Claude Code 中信任该目录并在 `/hooks` 确认两个 hook。之后照常工作。下次继续时告诉 Agent：*「通过 Intent 恢复这个项目。」*

Windows（PowerShell）：`irm https://raw.githubusercontent.com/dozybot001/Intent/main/scripts/install.ps1 | iex`。
使用 pipx 或 uv：`pipx install "intent-history @ git+https://github.com/dozybot001/Intent.git@v7.5.1"`（或 `uv tool install …`）。需要 Python 3.9+ 和 Git。

## 手动体验

```bash
itt init
itt intent create "Add Apple Pay to the web checkout" --why "Apple Pay users convert 2x on mobile Safari"
itt snap create "Payment sheet confirms PaymentIntents in test mode" \
  --next "Handle shipping-method changes server-side" --blocker none
itt decision create "Payments go through the PaymentIntent API only" --why "One SCA path"
itt inspect
```

在终端中 `itt` 输出便于阅读的文本；Agent 和脚本得到 JSON（`--json` 可强制 JSON）。

```text
Active
  intent-001  Add Apple Pay to the web checkout
              Next         Handle shipping-method changes server-side
              Blocker      none
              Verified     Payment sheet confirms PaymentIntents in test mode
              snap-001 · 2026-10-30 00:25 · 1 snap

Decisions
  decision-001  Payments go through the PaymentIntent API only
```

`itt log` 像 `git log` 一样列出检查点；`itt show ID` 显示单个对象及其关联。

## 支持的 Agent

| 宿主 | 支持方式 |
|---|---|
| **Codex** | Skill 加项目 hooks（开局上下文与 Stop 收尾检查）：`itt init` |
| **Claude Code** | Skill（或插件：`/plugin marketplace add dozybot001/Intent`，然后 `/plugin install intent-cli@intent`）加项目 hooks：`itt init --host claude-code`。见[配置与限制](references/claude-code-hooks.md)。 |
| **Cursor 及其他 Agent** | 仅 Skill 指令，尽力而为 |

Hooks 只写入项目内的文件（`.codex/hooks.json`、`.claude/settings.local.json`），不会启用其他项目。`itt maintenance off` 可关闭单个项目的记录。

## 保存什么，代价是什么

- `.intent/` 保存普通 JSON（`intents/`、`snaps/`、`decisions/`）。由于可能包含内部推理，`itt init` 只在当前克隆中把它排除出 Git（`.git/info/exclude`）；如果团队希望放进 Git，请有意识地提交。
- 每个启用 hook 的轮次会注入一段紧凑的开局上下文（有硬上限），并调用一次 `itt maintenance close`。除非你执行 push 或 pull，否则不会访问网络。

## 用 IntHub 浏览与共享（可选）

- **本地：** `itt hub start`，然后 `itt remote add origin http://127.0.0.1:7210 --project NAME` 和 `itt push`。IntHub Local 只接受回环地址上的同源请求。
- **托管：** [inthub.tenon.asia](https://inthub.tenon.asia)，由榫卯 Tenon AI 运营。运行 `itt auth login`，用 Tenon 账号在浏览器里批准代码，再 `itt push`。每个账号和团队可以保存 100 个项目和 1 GB 历史。项目默认私有，可以共享给团队（`--project 团队/项目`），也可以在项目设置里公开。在同一菜单删除账号会清除其云端数据（本地 `.intent/` 不受影响）。
- **在另一处恢复：** `itt init`、`itt remote add origin URL --project NAME`、`itt pull`。

目前每个项目只有一份共享历史：push 和 pull 只做快进。如果两份副本同时记录，`itt status` 会报告 `diverged`，双方都不会被改动，直到你运行 `itt pull --rebase`：远端对象保持原样，只有本地才有的对象换用下一个空闲 ID，再用 `itt push` 共享。Git 式的分支与合并是下一个里程碑（[设计](docs/CN/semantic-git.md)）。

## 卸载

```bash
itt maintenance off --remove-hooks    # 在每个项目里运行：从 Agent 设置中移除 Intent 的钩子
rm -rf .intent                        # 在每个项目里运行，如果也想删除它的历史
rm -rf ~/.local/share/intent ~/.local/bin/itt
```

用 `npx skills` 安装的 Skill 用 `npx skills remove intent-cli -g` 移除。IntHub 令牌在过期前一直有效，可以在设置里作废。

## 状态

Intent 处于 **Beta**（7.x）。同一主版本内，`.intent/` 格式与 JSON 输出保持兼容；不兼容的变化只会随新的主版本和迁移一起发布。记录与接续流程在 Python 3.9 至 3.14 上有测试覆盖。Intent 能否在真实工作中明显减少重复解释，仍在用自然接续案例验证，见[自用验证协议](docs/CN/dogfooding.md)。

## 常见问题

**它会取代 Git、Issue 或文档吗？** 不会。它记录的是这些工具没有记录的理由和工作状态。

**Agent 记录了无用内容怎么办？** 零写入是正常结果；skill 只记录经过验证的里程碑，从不按命令或文件逐条记录。对象只追加：更正以新的 Snap 表达。

**`pip install intent-cli` 是这个项目吗？** 不是，PyPI 上的这个名字属于一个无关工具。Intent 的发行名是 `intent-history`，命令是 `itt`。

**支持 Windows 吗？** CLI 与安装脚本支持 Windows。Claude Code hooks 需要 Git Bash。

## 文档

- [愿景](docs/CN/vision.md)：为什么需要语义历史
- [接续案例](docs/CN/continuation-case.md)：从中断到恢复的完整演示
- [CLI 参考](docs/CN/cli.md)：命令、对象与 JSON 约定
- [意图流转](docs/CN/intent-flow.md)：Intent 之间的关系与「流转」页
- [语义版 Git](docs/CN/semantic-git.md)：Intent 8 的分支与合并设计
- [Codex hooks](references/codex-hooks.md) 与 [Claude Code hooks](references/claude-code-hooks.md)
- [自用验证协议](docs/CN/dogfooding.md)
- 维护者：[IntHub 生产部署](docs/CN/inthub-production.md)

[贡献指南](.github/CONTRIBUTING.md) · [行为准则](.github/CODE_OF_CONDUCT.md) · [安全策略](.github/SECURITY.md) · MIT 许可
