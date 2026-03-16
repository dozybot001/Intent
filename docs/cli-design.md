# Intent CLI 设计说明 v0.4

## 这篇文档回答什么

- Intent CLI 的产品定位、边界和主路径是什么
- 核心对象应该如何暴露给用户和 agent
- 命令语义、默认行为和交互原则应该如何组织

## 这篇文档不回答什么

- 为什么需要 Intent 的完整问题论证
- 字段级 schema、JSON 返回结构和 exit code
- 首版实现顺序与测试矩阵

## 与其他文档的边界

- 问题定义和长期方向以 [愿景与问题定义](vision.md) 为准
- 术语统一以 [术语表](glossary.md) 为准
- schema、状态机、JSON contract 以 [实现约束](cli-contract.md) 为准

## 1. v0.4 设计结论

v0.4 的重点不是扩对象，而是降低理解成本、压缩主路径、稳定 agent 接口。

当前设计结论如下：

- 首页只暴露 6 个命令：`init`、`start`、`status`、`snap`、`adopt`、`log`
- `start` 取代 `new` 成为首页推荐入口
- `adopt` 是系统中心动作
- `status` 面向人，`inspect` 面向机器
- `run` 和 `decision` 保留，但不进入首页主路径
- 先证明本地 semantic layer，再谈平台

## 2. 产品定位

一句话定义：

**Intent CLI 是一个构建在 Git 之上的 semantic history 工具，用来记录当前想解决什么问题、形成过哪些候选结果、最终正式采纳了什么。**

Intent CLI 的边界是：

- 工作在本地 Git 仓库中
- 维护 `.intent/` 元数据层
- 管理 semantic history，而不是 code history
- 为 agent、Skill、IDE 和 automation 提供稳定入口

Intent CLI 不负责：

- 替代 Git 的文件版本控制
- 替代 issue、PR 或 docs 系统
- 保存全部原始对话
- 在 v0.4 阶段承担远端协作平台职责

## 3. 首页主路径

### 3.1 README 首页命令集合

```bash
itt init
itt start
itt status
itt snap
itt adopt
itt log
```

### 3.2 最小示例

```bash
itt init
itt start "Reduce onboarding confusion"

# explore and change code with agent...

itt snap "Landing page candidate B"
git add .
git commit -m "refine onboarding landing layout"
itt adopt -m "Adopt progressive disclosure layout"
itt log
```

### 3.3 这条路径必须让用户立刻理解的事情

- Git 还在正常工作
- Intent 记录的是更高层的采纳历史
- `start -> snap -> adopt` 比对象名更值得被记住

## 4. 对象与曝光顺序

v0.4 继续保留五对象模型，但不要求新用户一开始就理解全部对象。

| 对象 | 回答的问题 | 首页是否出现 | 表层命令 | 说明 |
| --- | --- | --- | --- | --- |
| `intent` | 当前想解决什么问题 | 是 | `itt start` | 当前默认语义上下文 |
| `checkpoint` | 目前有哪些候选结果 | 是，但通过 `snap` 暴露 | `itt snap` | adoption 的直接前置对象 |
| `adoption` | 最终正式采纳了哪个候选 | 是 | `itt adopt` | semantic history 的 headline object |
| `decision` | 为什么是这个，而不是那个 | 否 | `itt decide` | 只在取舍值得沉淀时显式出现 |
| `run` | 这一轮 agent 执行做了什么 | 否 | `itt run start/end` | 更偏 agent、automation、telemetry |

设计原则很简单：

- 对象模型可以完整
- onboarding 只暴露最少必要动作
- 高级对象延后显现

## 5. 命令体系

### 5.1 Surface CLI

给人高频使用的短命令：

```bash
itt init
itt start
itt status
itt snap
itt adopt
itt log
itt revert
```

按需出现：

```bash
itt decide
itt inspect
itt run start
itt run end
itt checkpoint select
```

兼容别名：

```bash
itt new
```

### 5.2 Canonical CLI

给 agent、Skill、IDE、automation 使用的稳定对象命令：

```bash
itt intent create
itt intent list
itt intent show
itt intent switch

itt checkpoint create
itt checkpoint list
itt checkpoint show
itt checkpoint select

itt adoption create
itt adoption list
itt adoption show
itt adoption revert

itt decision create
itt decision list
itt decision show

itt run start
itt run end
itt run list
itt run show

itt inspect
```

### 5.3 分层原则

- Surface CLI 用来形成肌肉记忆
- Canonical CLI 用来提供稳定语义 contract
- 表层命令可以是 sugar，但底层对象语义必须稳定

## 6. 核心命令语义

### 6.1 `itt init`

作用：初始化当前 Git 仓库的 `.intent/` 元数据层。

要求：

- 创建 `.intent/`
- 初始化 `config.json` 和 `state.json`
- 准备对象存储目录

### 6.2 `itt start`

作用：开始处理一个问题，并创建新的 active intent。

示例：

```bash
itt start "Reduce onboarding confusion"
```

canonical form：

```bash
itt intent create --title "Reduce onboarding confusion"
```

设计要点：

- 首页推荐 `start`，而不是 `new`
- 用户不是在“创建对象”，而是在“开始处理一个问题”
- 执行后自动切换到 active intent

### 6.3 `itt snap`

作用：保存一个 checkpoint 的表层快路径命令。

示例：

```bash
itt snap "Landing page candidate B"
```

canonical form：

```bash
itt checkpoint create --title "Landing page candidate B"
```

设计要点：

- 底层对象仍叫 checkpoint
- 高频表层命令继续使用 `snap`
- 新 checkpoint 自动成为 current checkpoint

### 6.4 `itt adopt`

作用：正式采纳某个 checkpoint。

推荐快路径：

```bash
itt adopt -m "Adopt progressive disclosure layout"
```

显式路径：

```bash
itt adopt cp-012 -m "Adopt progressive disclosure layout"
```

canonical form：

```bash
itt adoption create \
  --checkpoint cp-012 \
  --title "Adopt progressive disclosure layout"
```

设计要点：

- `adopt` 是系统中心动作
- 默认作用于 current checkpoint
- 若当前对象不明确，必须报错，不能猜测
- 支持轻量 rationale，例如 `--because`
- 成功输出应强调“采纳了一个候选结果”，而不是“创建了 adoption 对象”

必备能力：

- `--json`
- `--id-only`
- `--if-not-adopted`
- `--checkpoint <id>`
- `--link-git <hash|HEAD>`
- `--no-interactive`
- `--yes`

### 6.5 `itt status`

作用：给人看当前 semantic workspace 状态，并推荐下一步动作。

它必须优先回答四件事：

- 当前在处理哪个 intent
- 当前默认对象是什么
- 当前整体状态是什么
- 下一步最合理的动作是什么

`status` 不是半结构化的 `inspect`。它首先是 human entrypoint。

### 6.6 `itt inspect`

作用：给机器输出稳定、完整、可消费的语义上下文。

设计定位：

- `inspect` 是 agent、Skill、IDE、automation 的标准入口
- 目标不是“好看”，而是“稳定”
- 缺失对象时应返回 `null`，而不是随意省略字段

### 6.7 第二层命令

`itt decide`

- 用来沉淀长期有效的原则或取舍
- 不是每次 adopt 的必需步骤

`itt revert`

- 用来撤销一次 adoption
- 撤销本身也必须形成新的 semantic history

`itt run start/end`

- 用来记录一次 agent 执行或协作 span
- 更偏 agent、automation 和 provenance 场景

`itt checkpoint select`

- 用来显式设置 current checkpoint
- 适合多个候选并存时的人类和 agent 场景

## 7. Current Object 机制

v0.4 明确保留 current object philosophy，但只把它当作 human UX 的核心，不把它当成 automation 的主契约。

### 7.1 active intent

系统维护一个 active intent，作为默认语义上下文。

### 7.2 current checkpoint

系统维护一个 current checkpoint，作为默认候选对象。

创建新 checkpoint 时：

- 自动成为 current checkpoint

显式切换时：

```bash
itt checkpoint select cp-012
```

### 7.3 默认行为规则

人类模式：

- `itt start` 创建并切换到 active intent
- `itt snap` 创建并切换到 current checkpoint
- `itt adopt` 默认采纳 current checkpoint
- `itt status` 优先围绕 current object 组织信息

agent 模式：

- 优先显式传 intent id / checkpoint id
- 可以读取 current object，但不应把它当成强契约
- 推荐先 `itt inspect --json` 再执行写操作

### 7.4 冲突处理

如果存在多个未采纳候选且默认对象不清晰：

- `itt adopt` 不应猜测
- 返回 state conflict
- 输出明确 next action，例如 `itt checkpoint select`

## 8. Agent-Friendly 设计要求

- 所有读命令支持 `--json`
- 所有写命令返回稳定结果结构
- 所有核心写命令支持 non-interactive 模式
- 所有核心写命令支持基础幂等保护
- `inspect --json` 是标准上下文入口

推荐 agent 调用顺序：

1. `itt inspect --json`
2. 判断 context 和 pending actions
3. 显式执行对象命令
4. 再次 `itt inspect --json` 验证状态变化

## 9. Git 绑定策略

Intent 不是漂浮在 Git 之上的纯注释层。semantic history 应尽量绑定到可理解的 Git 状态。

规则如下：

- checkpoint 可以绑定当前 `HEAD`，也可以只记录 working tree context
- adoption 应尽量绑定稳定 Git 引用
- dirty working tree 可以给 warning，但不必默认阻断
- strict mode 可以要求 clean tree + stable commit

这样做的目的不是把流程做重，而是让 semantic history 不脱离实际代码状态。

## 10. 输出文案原则

CLI 文案必须优先讲动作结果，而不是对象创建细节。

不推荐：

```text
Created adoption object adopt-007
```

推荐：

```text
Adopted checkpoint cp-012
Intent: Reduce onboarding confusion
Git: a91c3d2
Next: itt log
```

用户应该优先看到：

- 做成了什么动作
- 对哪个对象生效
- 当前处于什么状态
- 下一步该做什么

## 11. v0.4 暂不引入的内容

- 原始对话全量存储
- `push` / `pull` 这类远端同步命令
- 更多新对象扩展
- 平台化叙事主导首页表达

当前阶段最重要的不是扩大想象空间，而是让 CLI 足够清楚、稳定、可用。

## 12. 总结

v0.4 的方向可以概括成一句话：

**不扩对象，继续做减法；不只让模型成立，更要让首次使用、日常使用和 agent 使用都成立。**
