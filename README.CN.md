[English](README.md) | 简体中文

# Intent

> Git 记录代码变化，Intent 记录采纳历史。
> Intent 同时面向人和 agent。

Intent 是一个构建在 Git 之上的新层，用来记录软件开发里更高层的信息：

- 现在想解决什么问题
- 试过哪些候选方案
- 最后正式采纳了什么
- 为什么采纳它

它不替代 Git。  
它补的是 Git 通常不会清楚保存的那部分历史。

如果用一句更技术的话说，Intent 是一个面向 agent 时代的 Git-compatible semantic history layer。当前第一步先以 `Intent CLI` 的形式落地。

## 30 秒理解

在 agent-driven development 里，代码可以生成得很快，但决策过程往往是散的：

- 目标在 issue 里
- 候选方案在对话或草稿里
- 最终选择和理由在某次讨论里

Git 很擅长回答“代码怎么变了”，但不擅长回答“我们最后决定了什么”。

Intent 想补上的，就是这层历史。

Intent 以 CLI 形式提供这层历史，并提供给人和 agent 都可读取的结构化入口。

这意味着 Intent 不是“多一份说明文档”，而是把这些高层语义变成：

- 人容易理解的工作流
- 开发者容易集成的接口
- agent 能稳定读取和操作的对象

## 为什么不直接用 issue / ADR / commit message

现有工具当然有价值，但它们没有把“采纳历史”本身做成稳定对象。

| 方式 | 擅长什么 | 不足在哪里 |
| --- | --- | --- |
| commit message | 解释一次代码提交 | 不稳定回答“当前 intent 是什么”“试过哪些候选”“最终采纳了什么” |
| issue / PR | 承载讨论和上下文 | 信息容易分散，对 agent 缺少稳定对象边界和固定读取入口 |
| ADR / docs | 沉淀长期决策 | 对高频 `start -> snap -> adopt` 过重，不适合作为每次候选采纳的默认路径 |
| Intent | 记录语义对象与采纳历史 | 重点在本地 CLI 闭环和结构化读取入口 |

## 核心闭环

Intent 先把最重要的 3 个动作做成正式对象：

- `start`：开始处理一个问题
- `snap`：保存一个候选结果
- `adopt`：正式采纳一个候选结果

也就是这条最小路径：

`问题 -> 候选 -> 采纳`

这条路径同时面向人和 agent。

## 为什么它对 agent 重要

对 agent 来说，Intent 提供的是结构化上下文，而不是只依赖 prose：

- 稳定的对象边界
- 明确的当前状态
- 可预测的下一步动作
- 结构化、可消费的输出

Intent 将意图、候选和采纳作为正式对象暴露出来。

## 最小示例

```bash
itt init
itt start "Reduce onboarding confusion"
itt snap "Landing page candidate B"
git add .
git commit -m "refine onboarding landing layout"
itt adopt -m "Adopt progressive disclosure layout"
itt log
```

这条路径表达三件事：

- Git 还在正常管理代码
- Intent 额外记录了这次工作的语义历史
- `itt log` 比 commit history 更接近“这次到底采纳了什么决策”

## 本地体验

```bash
git clone https://github.com/dozybot001/Intent.git
cd Intent
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
itt --help
```

如果你只是想直接跑仓库里的版本，也可以用 `./itt --help`。

这条 editable install 路径是给贡献者和仓库内开发使用的。如果你只是想作为普通用户使用 Intent，可以直接跳到下面的 bootstrap 命令。

## 安装路径

给贡献者的命令：

```bash
git clone https://github.com/dozybot001/Intent.git
```

给普通用户的一条安装命令：

```bash
curl -fsSL https://raw.githubusercontent.com/dozybot001/Intent/main/setup/install.sh | bash
```

这条 bootstrap 命令会在 `~/.intent/repo` 保留一份本地 checkout，把
repo-backed 的 `itt` 暴露到 `~/.intent/bin/itt`，并在可能时把这个目录接进
PATH，然后对检测到的 agent 运行 `itt setup`。普通用户不需要再额外做一次
`pip install` 去安装独立 CLI 副本。

安装完成后，后续命令面保持很小：

```bash
itt integrations list
itt setup --agent auto
itt setup codex
itt setup claude
itt doctor
```

## 验证方式

```bash
./scripts/check.sh
```

如果你想分步骤执行，也可以用：

```bash
python3 -m unittest discover -s tests -v
./scripts/smoke.sh
./scripts/demo_log.sh
./scripts/demo_agent.sh
```

## 首页先记住这 6 个命令

```bash
itt init
itt start
itt status
itt snap
itt adopt
itt log
```

如果你是开发者或 agent 集成方，可以先看这两个入口：

```bash
itt status --json
itt inspect --json
```

当写命令依赖“当前对象”时，优先使用内置 selector：

```bash
itt adopt --checkpoint @current -m "Adopt candidate"
itt decide "Record rationale" --adoption @latest
```

如果 `itt adopt` 提示 checkpoint 冲突，就先用提示里的候选执行一次 `itt checkpoint select <id>`，再重试。

## Agent 的默认工作方式

Intent 不只是让 agent 在事后读取语义状态，也希望 agent 在执行过程中主动维护这层语义历史。

但这是一条功能设计方向，不是更高层目标本身。支持这套协议，是为了验证：在工作过程中记录语义状态，是否真的能提升 agent 的效率、连续性，以及人类对 agent 行为的理解和信任。

在实践里，一个 agent 通常应该：

- 当用户提出一个明确且有分量的工作请求，而当前又没有合适 active intent 时，从 query 提炼出一句简洁的 intent
- 为当前这一轮有意义的执行过程开启一个 run
- 当出现值得命名或比较的候选状态时，创建 checkpoint
- 当明确选定某个候选结果时，记录 adoption
- 当某个理由需要超出当前修改长期保留时，记录 decision
- 在每次状态变化后重新读取 `itt inspect --json`，而不是靠猜

但这套协议要克制使用。很小的只读问题或一句话澄清，不需要强行形成完整语义记录。

当前真正要回答的产品问题，不是“能不能要求 agent 多记一点”，而是“这种语义记录方式是否真的让 agent 工作得更好”。

## Intent 不是什么

- 不是 Git 的替代品
- 不是 issue、PR 或 docs 系统的替代品
- 不是“什么都记录”的日志归档工具

Intent 只关心那些值得被正式追踪的语义节点，例如意图、候选、采纳、撤销与决策。

## Human-Friendly, Agent-Friendly

Intent 的接口分成两层：

- 对用户：`start -> snap -> adopt`
- 对开发者：本地对象层与 CLI contract
- 对 agent：固定对象、固定状态和固定 JSON 入口

## 当前阶段

`v0.1.0` 已经打 tag。当前重点已经不是“先把原型做出来”，而是“先用起来、打磨它，并判断下一版真正该优化什么”。

当前优先级是：

- 在真实仓库里 dogfooding 当前 CLI
- 基于真实使用打磨发布质量、验证路径和文档
- 继续做低风险的内部清理，提升可维护性
- 用真实使用反馈决定合适的 `v0.2.0` 方向

## 文档

README 只保留总览，更完整的说明在 `docs/`：

- [变更记录](CHANGELOG.CN.md)
- [文档索引](docs/CN/README.md)
- [术语表](docs/CN/glossary.md)
- [愿景与问题定义](docs/CN/vision.md)
- [CLI 统一设计文档](docs/CN/cli.md)
- [分发与集成设计](docs/CN/distribution.md)
- [Demo](docs/CN/demo.md)
- [发布基线](docs/CN/release.md)
- [路线图](docs/CN/roadmap.md)
- [文档国际化规范](docs/CN/i18n.md)

更多背景见：[愿景与问题定义](docs/CN/vision.md)。
