# Intent

中文 | [English](README.md)

为 agent 驱动的开发提供语义历史。保留**产品如何逐步成形**，以及**工作如何跨 session 与 agent 恢复**。

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
| **Intent** | 从用户 query 中识别出的目标 |
| **Snap** | 一个语义检查点，记录发生了什么变化、学到了什么，以及后续反馈 |
| **Decision** | 跨多个 intent 持续生效的长期约束 |

对象自动关联。Decision 自动挂载到每个 active intent；intent 自动挂载到每个 active decision。关系始终双向且只增不减。

```mermaid
flowchart LR
  D1["🔶 Decision 1"]
  D2["🔶 Decision 2"]

  subgraph Intent1["🎯 Intent 1"]
    direction LR
    S1["Snap 1"] --> S2["Snap 2"] --> S3["..."]
  end

  subgraph Intent2["🎯 Intent 2"]
    direction LR
    S4["Snap 1"] --> S5["Snap 2"] --> S6["..."]
  end

  D1 -- auto-attach --> Intent1
  D1 -- auto-attach --> Intent2
  D2 -- auto-attach --> Intent2
```

## 快速开始

```bash
git clone https://github.com/dozybot001/Intent.git
cd Intent
pip install intent-cli-python && npx skills add dozybot001/Intent -g
```

安装 CLI 并添加 agent skill。需要 Python 3.9+、Git 和 Node.js。

想在浏览器中查看语义历史，在 clone 的仓库目录下启动 **IntHub Local**：

```bash
itt hub start
```

然后在你自己的项目仓库里：

```bash
itt hub link --api-base-url http://127.0.0.1:7210
itt hub sync
```

> **Tips：** 由于 `itt` 是一个全新的命令，agent 没有被训练过，建议每个 session 开始时打个 `/`，选到技能，回车就进入工作流了。

## 文档

- [愿景](docs/CN/vision.md) — 为什么需要语义历史
- [CLI 设计文档](docs/CN/cli.md) — 对象模型、命令、JSON 契约
- [路线图](docs/CN/roadmap.md) — 阶段规划
- [Dogfooding 实录](docs/CN/dogfooding.md) — 跨 agent 协作案例
- [IntHub Local](docs/CN/inthub-local.md) — 运行本地 IntHub 实例

## 许可证

MIT
