# IntHub MVP 设计文档

中文 | [English](../EN/inthub-mvp.md)

## 1. 产品定位

IntHub 不是新的语义层，也不是重型项目管理平台。

它的定位是：

**构建在 Intent 之上的远端协作层。**

一句话说：

**本地 `itt` 负责写语义，IntHub 负责共享语义。**

因此，IntHub 首期最重要的能力不是“在线编辑对象”，而是：

- 让人和 agent 看到同一份当前语义状态
- 让交接、续做、review 和回溯不再依赖临时解释
- 让 `intent / snap / decision` 第一次具备远端可见性、可检索性和可共享性

## 2. 首期设计原则

- **local-write first**：首期仍以本地 CLI 作为主要写入口
- **remote-read first**：IntHub 先解决共享 inspect、展示、检索和 handoff
- **reuse the local model**：不重新发明对象模型，不增加第四类核心对象
- **sync current semantics, not everything**：同步的是结构化语义对象，不是全部原始对话和全部中间日志
- **low-friction by default**：不让远端协作层反过来把本地 workflow 变成官僚流程
- **semantic data stays out of Git**：`.intent/` 属于本地语义工作区元数据，不应提交到 Git，也不应以 GitHub 作为语义对象主存储

对于首期实际交付形态，还应增加一条：

- **local-instance first for adoption**：在真正的远端托管形态成熟前，首个面向普通用户的 IntHub 体验应优先收敛为一个可分发的本地实例（IntHub Local），让用户能先在本机浏览器查看自己项目的语义历史

## 3. 当前非目标

IntHub 首期不优先做：

- 远端直接编辑 `intent / snap / decision`
- 完整原始对话归档
- 通用任务系统、issue 系统或 PM 平台
- 实时评论流、审批流和复杂通知系统
- 为多人并发写入提前设计过重的冲突合并机制
- 脱离 Git 与本地 workspace 上下文的“纯网页对象系统”

## 4. MVP 范围

### 4.0 首个可分发形态：IntHub Local

为了让普通用户尽快体验 IntHub，首期不应把“先部署一个远端服务”当成唯一前提。

更合理的第一步是提供一个 **可分发的本地 IntHub 实例（IntHub Local）**：

- 通过 **GitHub Release assets** 分发
- 安装后在用户本机启动一个 IntHub 后端实例
- 默认只绑定 `127.0.0.1:7210`
- 默认将 Web 与 API 一起服务
- 用户在自己的项目仓库里执行 `itt hub login / link / sync`
- 再在本地浏览器中打开 IntHub，查看自己项目同步上来的 `intent / snap / decision`

这样做的价值是：

- 不要求普通用户先理解云部署、域名或托管
- 不破坏“PyPI 只分发 CLI”的边界
- 保持 IntHub 的产品体验与未来远端实例一致，只是部署位置不同

这里要明确一个边界：`IntHub Local` 是 **单独分发物**，不是 CLI PyPI 包的隐式组成部分。

### 4.1 必须有的用户可见能力

#### 项目总览

提供当前项目的一屏视图，至少包含：

- active intents
- active decisions
- recent snaps
- 当前关联的 repos / workspaces
- 每个 workspace 最近一次同步状态

#### Handoff 视图

这是远端版的 `itt inspect`，用于回答：

- 现在有哪些目标还在推进
- 最近做到了哪
- 哪些长期决策仍在生效
- 新 agent 接手时先看什么

#### Intent 详情页

至少展示：

- title / status / rationale
- source query
- 关联 decisions
- snap 时间线
- 最新一条 snap 摘要
- 关联的 repo / branch / commit 上下文

#### Decision 详情页

至少展示：

- title / rationale / status
- 当前仍受约束的 intents
- 已关联过的历史 intents
- decision 何时 deprecated

#### 搜索

首期搜索只要求高信号字段：

- object title
- source query / snap query
- summary
- rationale

不要求首期支持复杂语法，也不要求全量聊天检索。

### 4.2 核心使用场景

IntHub 首期至少要让以下场景成立：

1. 一个新 agent 打开项目后，不需要用户重新讲上下文，就能知道该从哪里继续。
2. 一个 reviewer 能快速理解“现在为什么沿着这条路径推进”，而不只看到代码 diff。
3. 同一个仓库在多次 session 间切换时，用户能看到最近的真实推进状态，而不是零散聊天记录。

### 4.3 官方 showcase project

IntHub 首期应至少有一个官方 showcase project，用来展示这套协作层在真实工作中的样子。

首选样本应当是 **Intent 项目自身的语义历史**，原因是：

- 它是真实持续发生的数据，不是为了演示硬造的 fixture
- 它天然覆盖 IntHub 想证明的核心价值：跨 agent handoff、feedback 消费、decision 约束、错误纠偏
- 项目维护者对上下文最熟，最容易持续维护展示质量

这个 showcase 不应只是一次性的静态故事页，而应是一个持续更新的 live showcase。展示上应同时提供两层入口：

- **showcase / case-study 入口**：帮助第一次接触 IntHub 的人快速理解“这套东西是怎么被真实使用的”
- **raw object 入口**：允许用户继续下钻到真实的 intent / snap / decision 视图，而不是只看整理后的叙事

也就是说，案例叙事可以存在，但不能替代原始对象视图；两者应并存。

## 5. 最小信息架构

首期建议只引入协作层所必需的四层容器：

| 层 | 作用 |
| --- | --- |
| `project` | 协作范围与顶层入口 |
| `repo` | 对应一个 Git 仓库 |
| `workspace` | 一份本地 checkout / agent 工作副本 |
| `sync batch` | 一次从本地向 IntHub 的同步记录 |

在这四层之下，远端继续承载三类现有语义对象：

- intent
- snap
- decision

不要在首期再引入新的通用核心对象来稀释边界。

## 6. 同步模型

首期建议采用：

**batch append-only + object snapshot view**

也就是：

- 每次同步创建一条新的 `sync batch`
- batch 里带上当前 workspace 的 Git 与 schema 上下文
- batch 上传当前对象快照，而不是远端重新推断语义
- 远端把“最新对象状态”作为派生视图来展示

这样做的原因是：

- 比完整 event-sourcing 更容易落地
- 比只做最终状态 upsert 更容易保留同步边界
- 与当前本地 append-only、对象不可变的设计更一致

每个 sync batch 至少应包含：

- `project`
- `repo`
- `workspace`
- `schema_version`
- `branch`
- `head_commit`
- `dirty`
- `synced_at`
- 当前可见的 intents / snaps / decisions 对象快照

## 7. ID 与来源设计

本地对象 ID 例如 `intent-001` 只在单个 workspace 内有意义，不能直接拿来当远端全局主键。

因此首期应明确区分两套标识：

- **local display ID**：例如 `intent-001`，继续保留给人类阅读和本地 CLI 使用
- **remote global ID**：由 IntHub 分配，用于远端存储、索引和 API 引用

远端对象还应保留来源信息：

- origin workspace
- local object id
- object type
- created_at

这样才能同时满足：

- UI 中延续本地可读性
- 远端避免多仓库 / 多 workspace 撞号

## 8. Git 上下文要求

IntHub 不是要替代 Git，但首期必须把语义对象和 Git 上下文并排展示。

每次同步至少应关联：

- repo
- branch
- HEAD commit
- dirty state

如果没有这些信息，IntHub 会退化成“远端笔记墙”，而不是协作层。

同时应明确边界：

- Git / GitHub 提供 repo identity、权限和代码上下文
- IntHub 提供语义对象的同步、存储、索引和展示
- `.intent/` 不应被提交到仓库，也不应作为 GitHub 内容的一部分被消费

这样可以避免把 semantic history 反向耦合到 branch、merge、rebase 和 PR 噪音之中。

## 9. 首期 API / 同步入口建议

首期不需要很宽的 API 面，但至少需要这些能力：

- 提交一个 sync batch
- 拉取项目总览
- 拉取 intent 详情
- 拉取 decision 详情
- 搜索对象

CLI 侧不一定要一开始就做很多新命令，但至少应预留一个明确入口，例如：

```bash
itt hub sync
```

它的职责应该尽量单纯：

- 读取本地 `.intent/`
- 补充 Git 上下文
- 推送到 IntHub

不要把远端对象编辑、评论、审批一开始就塞进 CLI。

## 10. 建议的实施顺序

### 阶段 A：同步 contract

- 明确 sync batch payload
- 定义 project / repo / workspace / object 的最小远端 schema
- 先保证幂等同步成立

### 阶段 B：只读 Web 总览

- 项目首页
- handoff / inspect 视图
- intent / decision 详情页

### 阶段 C：搜索与回溯

- 基于 title / query / summary / rationale 的搜索
- recent activity / timeline 视图

### 阶段 D：再决定是否扩写能力

只有在前面这些能力已经被真实使用证明有价值之后，再考虑：

- 更细的 review 视图
- 远端写入口
- 更复杂的协作流

## 11. 判断 IntHub MVP 是否成立

不是看页面有多少，而是看这几个问题是否被明显改善：

- 一个新 agent 是否真的更容易接手当前工作
- 用户是否更容易看懂“现在为什么这样推进”
- review / handoff 是否减少了对聊天回忆的依赖
- 新增复杂度是否带来了真实协作收益

如果这些问题没有被改善，说明 IntHub 只是把本地对象搬到了网页上，还没有真正成为协作层。
