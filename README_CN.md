# Intent

中文 | [English](README.md)

Git 之上的开发语义历史层。它记录**目标**、**语义快照**和**决策**。

## 为什么

Git 记录代码怎么变的。但它不记录**你为什么走这条路**、途中做了什么决策、上次停在哪里。

Intent 补上这层缺失的 **语义历史** — 一组既能保留产品形成历史、又能穿越上下文丢失的正式对象。

> 开发正在从"写代码"转向"引导 agent、沉淀决策"。历史层应该反映这一点。

```mermaid
flowchart LR
  subgraph traditional["古法编程"]
    direction TB
    H1["人"]
    C1["代码"]
    H1 -->|"Git"| C1
  end
  subgraph agent["Agent 驱动开发"]
    direction TB
    H2["人"]
    AG["Agent"]
    C2["代码"]
    H2 -."❌ 无语义历史".-> AG
    AG -->|"Git"| C2
  end
  subgraph withintent["有 Intent 的 Agent"]
    direction TB
    H3["人"]
    AG2["Agent"]
    C3["代码"]
    H3 -->|"Intent"| AG2
    AG2 -->|"Git"| C3
  end
  traditional ~~~ agent ~~~ withintent
```

## 三个对象，一张图

| 对象 | 记录什么 |
|---|---|
| 🎯 **Intent** | 从交互中总结出的目标 |
| 📸 **Snap** | 语义快照 — 做了什么、为什么 |
| 🔶 **Decision** | 跨多个 intent 持续生效的长期约束 |

对象自动关联。关系始终双向且只增不减。

```mermaid
flowchart LR
  D1["🔶 Decision 1"]
  D2["🔶 Decision 2"]

  subgraph Intent1["🎯 Intent 1"]
    direction LR
    S1["📸 Snap 1"] --> S2["📸 Snap 2"] --> S3["📸 ..."]
  end

  subgraph Intent2["🎯 Intent 2"]
    direction LR
    S4["📸 Snap 1"] --> S5["📸 Snap 2"] --> S6["📸 ..."]
  end

  D1 -- auto-attach --> Intent1
  D1 -- auto-attach --> Intent2
  D2 -- auto-attach --> Intent2
```

## 记录与接续

早期版本采用 **Snap–Query** 模式——agent 在每次交互后自动捕获快照。在自用中，这会产生过多低价值记录，并打断自然的工作流。

Intent 现在采用 **Intent–Session** 模式：agent 自由工作，由你明确决定何时让 Intent 写入。记录聚焦已经验证的目标、里程碑和决策，而不是捕获每个中间动作。这是一项旨在保持低打扰的产品取舍；未记录的工作不会被自动恢复。

1. 和 agent 一起完成你的目标
2. 明确要求 agent 用 Intent 记录或更新这项工作
3. Agent 先检查现有状态，复用语义相同的 active 或 suspended Intent，只写入新增的高信号语义
4. 如果目标仍未结束，最后一个 Snap 必须是自包含检查点：已验证状态、当前边界、下一步，以及 blocker 或局部约束

没有新的关键信息时，零写入也是正确结果。每次记录没有对象数量配额：不同的独立目标边界应拆成不同 Intent，并且只创建保存关键语义变化所需的 Snap。和 `git commit` 一样，写入必须由用户明确发起；普通的总结、记笔记或状态汇报不授权修改 `.intent/`。

需要接续时，明确要求 agent “通过 Intent 恢复项目”。Agent 先运行 `itt inspect`；如果最新检查点不足且 `has_more` 为 true，再用 `itt inspect --intent ID --history 3` 受限读取最近历史。仅查看或解释恢复状态时保持只读。

## 如何判断它有用

Intent 围绕两个产品目标设计，它们不是已被证明的对比结论：

| 目标 | 仍需在真实使用中验证的标准 |
|---|---|
| 低打扰记录 | 记录占用较少时间和上下文，不打断正常开发，并避免退化为命令日志。 |
| 有用的接续 | 后续 session 或另一个 agent 能以更少的重复解释，恢复目标及其原因、最新的有意义里程碑和当前有效的长期决策。 |

历史自用只能说明早期流程曾端到端运行，不能证明当前接续契约已经成立。当前版本应通过自然发生的接续案例验证，并明确区分 Intent 直接提供的信息、后来从代码重新发现的信息，以及用户重新解释的信息。见[自用验证协议](docs/CN/dogfooding.md)。

## 快速开始

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/dozybot001/Intent/main/scripts/install.sh | bash

# Windows (PowerShell)
irm https://raw.githubusercontent.com/dozybot001/Intent/main/scripts/install.ps1 | iex

# 克隆仓库 & 添加 agent skill
git clone https://github.com/dozybot001/Intent.git
npx skills add dozybot001/Intent -g --all
```

需要 Python 3.9+ 和 Git。安装脚本会自动处理 pipx。
需要升级或修复已有的 `itt` 安装时，直接重新运行安装脚本即可。

在需要记录的 Git 仓库中初始化 Intent：

```bash
cd your-project
itt init
```

`itt init` 会创建 `.intent/`，并将它加入当前克隆的 Git 本地 `.git/info/exclude`；它**不会**修改团队共享的 `.gitignore`。本地忽略规则写入失败时，命令会返回 warning。有意共享前应先审查其中内容；如果整个团队都应继承该规则，再单独将 `.intent/` 加入 `.gitignore`。

先为官方 IntHub 服务全局登录一次，再分别绑定和推送每个仓库：

```bash
itt auth login
cd your-project
itt hub status
itt hub link
itt push
```

`itt auth login` 默认使用 `https://inthub.tenon.asia`。非敏感服务地址保存在用户级配置中，账户 token 则交给 Git 已配置的 credential helper，例如 macOS Keychain、Git Credential Manager 或 libsecret。同一账户凭据可跨仓库复用；每个仓库仍在自己的 `.intent/hub.json` 中保存非敏感的 `project_id`、`workspace_id` 和 `repo_binding`。`itt hub status` 可以在不调用 IntHub API 的情况下报告这些本地状态。GitHub 和 Gitee origin 都受支持，GitHub OAuth 只用于识别 IntHub 账户。CLI 不需要改写 `origin`；如果当前 origin 与保存的绑定不一致，`itt push` 会拒绝执行。`--token` 与 `INTHUB_TOKEN` 继续作为单次命令或环境覆盖，绝不会写入仓库配置。`itt hub sync` 保留为 `itt push` 的兼容别名。

想在浏览器中查看语义历史，启动 **IntHub Local**（任意目录可用）：

```bash
itt hub start
```

然后在你的项目仓库里：

```bash
itt hub link --api-base-url http://127.0.0.1:7210
itt push
```

IntHub Local 默认只绑定 `127.0.0.1`。当前本地 API 不强制校验 Bearer Token，并返回宽松的 CORS 响应头；因此只应在可信本机使用，不要将它绑定到对外网卡，也不要通过公网接口或反向代理暴露。

公网部署使用统一账户路径：GitHub 登录或注册、数据库 Web 会话、账户级 CLI access token、账户隔离的项目、PostgreSQL、回环应用端口和 Caddy TLS。参见 [IntHub 生产部署](docs/CN/inthub-production.md)。

> **Tips：** 请明确表达：“用 Intent 把这轮工作写入 `.intent/`”进入记录模式；“通过 Intent 恢复这个项目”进入接续模式。普通总结和状态汇报保持只读。

## Showcase

浏览维护者持续更新、只读的个人 IntHub：

**[IntHub Showcase](https://inthub.tenon.asia/showcase)** — 展示显式选中的项目及其当前 Intent、时间线和 Decision。公开范围是项目白名单；以后新增的项目在单独加入前仍保持私有。

早期静态快照仍保留在仓库的历史 Pages 数据中，也可运行 `itt hub start` 在本地浏览。

## 文档

- [愿景](docs/CN/vision.md) — 为什么需要语义历史
- [接续案例](docs/CN/continuation-case.md) — 一个可复现的中断到恢复流程
- [自用验证协议](docs/CN/dogfooding.md) — 对自然接续进行信息来源标注验证
- [CLI 设计文档](docs/CN/cli.md) — 对象模型、命令、JSON 契约
- [IntHub 生产部署](docs/CN/inthub-production.md) — PostgreSQL、认证、TLS、备份与回滚

## 社区

- [贡献指南](.github/CONTRIBUTING.md)
- [行为准则](.github/CODE_OF_CONDUCT.md)
- [安全策略](.github/SECURITY.md)

## 许可证

MIT
