# Intent CLI Design Spec v0.4

## 导读

**本文回答什么**

- Intent CLI 的产品定位、边界和主路径是什么
- 核心对象、命令体系和交互原则应该如何组织
- human path 与 agent path 应如何拆分

**适合谁读**

- 想理解 README 主路径背后完整设计的人
- 想讨论命令命名、对象模型和 CLI 体验的人
- 想在进入实现前先看清产品约束的人

**与其他文档关系**

- 这篇文档负责产品设计、命令语义和交互路径
- 如果你想先理解项目为什么存在，建议先读 [Intent 愿景笔记 v3](intent_vision_notes_v_3_cn.md)
- 如果你需要冻结字段、返回结构和行为 contract，请继续读 [Intent CLI Implementation Contract v0.1](intent_cli_implementation_contract_v_0.md)

---

## 1. 文档目标

本文档定义 Intent 第一阶段产品 **Intent CLI**（命令名暂定为 `itt`）的 v0.4 设计方案。

v0.4 建立在 v0.3 之上，不推翻既有对象模型，而是在以下三个方面继续收敛：

1. **进一步降低首次理解与首次使用门槛**
2. **进一步明确 human path 与 agent path 的边界**
3. **进一步强化“为什么不是 Git + PR + Issue + Docs 就够了”的产品论证**

v0.4 的任务不是扩展系统能力，而是让 Intent CLI 更像一个能被真正持续使用、能被 agent 稳定调用、能被外界快速理解的产品。

一句话概括：

**v0.4 的重点不是再加命令，而是把 Intent CLI 打磨成一个“看得懂、跑得通、讲得清”的 semantic history 工具。**

---

## 2. 产品定位

### 2.1 一句话定义

**Intent CLI 是一个构建在 Git 之上的 semantic history 工具，用来记录当前想解决什么问题、形成过哪些候选结果、最终正式采纳了什么，以及为什么采纳。**

### 2.2 Intent 解决的不是“信息不存在”，而是“信息没有成为一等对象”

在今天的软件协作中，高层语义信息并不是不存在，而是分散存在于：

* commit message
* issue
* PR discussion
* docs
* chat
* agent conversation
* 临时笔记与口头共识

这些信息的问题不是“没有”，而是：

* 不稳定
* 不集中
* 不可持续追踪
* 不以统一对象模型存在
* 不适合 agent 稳定读取与操作

因此 Intent CLI 所补的，不是另一个记录系统，而是一层新的对象层：

**把原本碎片化存在的高层语义，提升为可创建、可比较、可采纳、可撤销、可查询的 semantic objects。**

### 2.3 产品边界

Intent CLI：

* 工作在本地 Git 仓库中；
* 维护 `.intent/` 元数据层；
* 管理 semantic history，而不是 code history；
* 与 Git 并行工作，而不是替代 Git；
* 面向 agent-driven development / vibe coding / 高层采纳式开发；
* 为后续 IntHub 与 Skill / agent workflow 提供本地标准接口。

Intent CLI 不负责：

* 替代 Git 的文件版本控制能力；
* 替代 issue tracker、PR system 或 docs system；
* 存储全部原始对话与全部执行日志；
* 在 v0.4 中承担完整远端协作平台职责；
* 变成一个“记录一切”的重型过程系统。

### 2.4 核心判断

Git 自然记录的是 **code history**；
Intent CLI 自然记录的是 **adoption-oriented semantic history**。

Git 擅长回答：

* 改了什么代码？
* 哪个 commit 引入了变化？
* 哪个分支合并了哪些修改？

Intent 擅长回答：

* 当前想解决什么问题？
* 出现过哪些候选结果？
* 最终正式采纳了哪一个？
* 为什么采纳这个，而不是那个？

因此可以用一句话总结两者关系：

**Git 记录代码变化，Intent 记录采纳历史。**

---

## 3. v0.4 的设计结论

相比 v0.3，v0.4 明确做出以下收敛。

### 3.1 不扩对象，继续压缩 onboarding

核心对象仍然保持不变：

* intent
* run
* checkpoint
* adoption
* decision

但首次接触产品的用户，不应该被要求理解所有对象。

v0.4 的原则是：

* **对象模型可以完整**
* **onboarding 只暴露最少必要动作**
* **高级对象延后显现**

### 3.2 首页主路径继续保持 6 个命令

README 首屏与 onboarding 只强调以下 6 个命令：

```bash
itt init
itt start
itt status
itt snap
itt adopt
itt log
````

说明：

* v0.4 用 `start` 取代 v0.3 的 `new` 作为 intent 创建的首页命令；
* `new` 仍保留为兼容别名；
* `snap` 继续作为 checkpoint 的表层快路径；
* `adopt` 继续作为第一核心动作；
* `log` 继续作为 semantic history 的默认查看入口。

### 3.3 `start` 比 `new` 更符合真实任务语义

v0.4 判断：用户不是在“创建一个对象”，而是在“开始处理一个问题”。

因此首页推荐命令从：

```bash
itt new "Reduce onboarding confusion"
```

收敛为：

```bash
itt start "Reduce onboarding confusion"
```

这使得首屏语义更自然：

* init 一个仓库
* start 一个问题
* snap 一个候选
* adopt 一个结果

### 3.4 `status` 与 `inspect` 彻底分层

* `status`：面向人类，输出当前状态与推荐下一步动作
* `inspect`：面向 agent，输出完整、稳定、机器可消费的上下文结构

v0.4 不再允许两者语义混杂。

### 3.5 `run` 继续下沉，不进入主路径

v0.4 保留 run 对象，但进一步明确其定位：

* 对人类用户，run 不是主流程显式对象；
* 对 agent、IDE、automation、telemetry，run 很重要；
* `run` 应更像 execution span / provenance node，而不是普通用户首要理解对象。

因此：

* `run` 保留；
* `itt run start/end` 继续存在；
* 但 README 首页不出现 run；
* 未来可支持自动生成 run，而无需每次人类显式管理。

### 3.6 `decision` 继续按需显式化

v0.4 继续坚持：

* adoption 记录“采纳了什么”
* decision 记录“值得单独沉淀的取舍”

不是每次 adoption 都必须产生 decision。

因此：

* `adopt --because` 仍然成立；
* 只有关键原则判断、长期有效取舍，才推荐显式 `decide`。

### 3.7 先证明 local semantic layer，再谈平台

v0.4 更明确地把本地 CLI 验证放在第一优先级：

* 先证明本地 semantic workflow 成立；
* 再证明 agent contract 成立；
* 再考虑 IntHub 作为远端组织与展示层。

这意味着在产品叙事上：

**CLI 不是 IntHub 的附庸，CLI 本身就是第一阶段产品。**

---

## 4. 核心对象模型

v0.4 保留五对象模型，但更明确它们的层级、价值与曝光顺序。

### 4.1 Intent

表示当前想解决的问题、目标或任务定义。

Intent 回答的问题是：

**我们现在到底想解决什么？**

示例：

* Reduce onboarding confusion
* Improve trust in research assistant responses
* Simplify Intent CLI onboarding

### 4.2 Run

表示一次 agent 执行、一轮探索尝试或一段协作过程。

Run 回答的问题是：

**这轮尝试做了什么？**

v0.4 定位：

* 对 provenance、automation、agent orchestration 很重要；
* 对普通人类使用者不是首页主对象；
* 可以显式创建，也可以未来自动生成。

### 4.3 Checkpoint

表示一个候选语义快照，是当前形成的可比较结果。

Checkpoint 回答的问题是：

**目前有哪些候选结果可供比较与采纳？**

说明：

* 对象名仍为 checkpoint；
* 高频表层命令仍为 `snap`；
* checkpoint 是 adoption 的直接前置对象。

### 4.4 Adoption

表示正式采纳某个 checkpoint。

Adoption 回答的问题是：

**最终正式接受了哪个候选结果？**

定位：

* adoption 是 semantic history 的 headline object；
* `adopt` 是 Intent CLI 的第一核心命令；
* adoption 是最接近 `git commit` 的语义动作，但对象语义高于 commit。

### 4.5 Decision

表示关键取舍、原则判断或长期有效 rationale。

Decision 回答的问题是：

**为什么是这个，而不是那个？**

定位：

* decision 不是日常必需对象；
* 只有当 reasoning 值得独立沉淀时才显式创建；
* 它补充 adoption，而不是取代 adoption。

---

## 5. 设计原则

### 5.1 CLI 是肌肉记忆，不是 schema

底层对象模型可以严谨；
表层 CLI 必须短、顺、容易形成肌肉记忆。

因此：

* 允许 object name 与 surface command 不完全一致；
* `snap` 可以映射到 checkpoint；
* `start` 可以映射到 intent create；
* sugar 不是妥协，而是高频交互优化。

### 5.2 adopt 是系统中心动作

Git 的中心动作是 `commit`；
Intent CLI 的中心动作是 `adopt`。

因为在 agent-driven development 中，更重要的不是“谁写了代码”，而是：

**哪个候选结果被正式采纳。**

### 5.3 对人类要顺滑，对 agent 要稳定

因此：

* 人类模式允许 default current object；
* agent 模式优先显式传参；
* 读命令必须结构化；
* 写命令必须稳定、可依赖、可幂等。

### 5.4 默认行为服务高频路径

高频动作不应要求用户总是输入对象 id。

因此 v0.4 继续明确：

* `snap` 自动成为 current checkpoint；
* `adopt` 默认作用于 current checkpoint；
* `status` 优先围绕当前工作对象组织信息。

### 5.5 只记录值得正式成立的语义节点

Intent CLI 不是日志备份系统。

v0.4 的原则是：

**不是为了记录一切，而是为了记录那些值得被比较、采纳、撤销、追溯的语义节点。**

### 5.6 先做窄而硬的产品，再做宽而大的平台

v0.4 不追求过早扩张平台能力；
优先保证：

* 主路径足够清晰；
* 本地对象层足够稳定；
* agent contract 足够可靠；
* demo workflow 足够可信。

---

## 6. 命令体系总览

v0.4 继续采用双层命令体系，但进一步明确 Surface CLI 与 Canonical CLI 的职责边界。

### 6.1 Layer A：Surface CLI（人类高频命令层）

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
itt run
itt inspect
```

兼容别名：

```bash
itt new
```

说明：

* `start` 是 v0.4 首页推荐命令；
* `new` 作为兼容 alias 保留，但不再作为首推；
* `inspect` 虽然很重要，但它不是普通用户首页必须理解的命令；
* `run` 与 `decide` 继续按需显式出现。

### 6.2 Layer B：Canonical CLI（agent / Skill / IDE / automation）

```bash
itt intent create
itt intent list
itt intent show
itt intent switch

itt run start
itt run end
itt run list
itt run show

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

itt inspect
```

说明：

* 对象子命令是 canonical contract；
* 表层命令只是 sugar；
* agent 默认应优先使用 canonical form 与 `inspect --json`。

---

## 7. 首页主路径设计

### 7.1 v0.4 首页最小路径

```bash
itt init
itt start "Reduce onboarding confusion"

# explore and change code with agent...

itt snap "Landing page candidate B"
git add .
git commit -m "refine onboarding landing layout"
itt adopt -m "Adopt progressive disclosure layout"
```

### 7.2 这条路径想让用户直觉记住的不是对象名，而是动作

* `start`：开始处理一个问题
* `snap`：保存一个候选
* `adopt`：正式采纳这个候选

### 7.3 完整路径（高级场景）

```bash
git checkout -b feature/onboarding-v2

itt init
itt start "Reduce onboarding confusion"

itt run start
# agent works...
itt run end -m "Generated landing page candidate with progressive disclosure"

itt snap "Landing page candidate B"

git add .
git commit -m "refine onboarding landing layout"

itt adopt -m "Adopt progressive disclosure layout" \
  --because "reduces cognitive load for first-time users"

itt log
```

### 7.4 这条完整路径适用于

* 展示 run 的价值；
* 展示 semantic history 与 Git history 的绑定；
* 展示 adoption + rationale 的最小闭环；
* 面向 Skill / IDE / automation integration。

---

## 8. 命令设计

## 8.1 `itt init`

### 作用

初始化当前 Git 仓库的 Intent 元数据层。

### 示例

```bash
itt init
```

### 行为

* 检查当前目录是否为 Git 仓库；
* 创建 `.intent/` 目录；
* 初始化 schema version；
* 初始化 state 与 config；
* 准备对象存储目录。

---

## 8.2 `itt start`

### 作用

创建一个新的 intent，并将其设为当前 active intent。

### 示例

```bash
itt start "Reduce onboarding confusion"
```

带说明：

```bash
itt start "Reduce onboarding confusion" \
  -d "First-time users feel overwhelmed on the landing page"
```

### canonical form

```bash
itt intent create --title "Reduce onboarding confusion"
```

### 设计说明

v0.4 首页推荐 `start` 而不是 `new`，因为它更符合真实用户意图：

用户不是在创建抽象对象，而是在开始处理一个问题。

### 兼容说明

以下写法仍然成立，但不再是首推文档写法：

```bash
itt new "Reduce onboarding confusion"
```

---

## 8.3 `itt snap`

### 作用

创建一个 checkpoint 的表层快路径命令。

### 示例

```bash
itt snap "Landing page candidate B"
```

带说明：

```bash
itt snap "Landing page candidate B" -m "progressive disclosure version"
```

### canonical form

```bash
itt checkpoint create --title "Landing page candidate B"
```

### 设计说明

v0.4 继续坚持：

* 底层对象名仍为 checkpoint；
* 表层高频命令继续是 `snap`；
* CLI 优先服务高频输入体验。

### 默认行为

执行 `itt snap` 后：

* 新 checkpoint 自动成为 current checkpoint；
* 自动关联 active intent；
* 若存在 active run，则自动关联；
* 默认尝试记录当前 Git `HEAD`；
* `status` 的 next action 通常会切换到 `adopt`。

---

## 8.4 `itt adopt`

### 作用

正式采纳某个 checkpoint。

### 推荐快路径

```bash
itt adopt -m "Adopt progressive disclosure layout"
```

### 显式路径

```bash
itt adopt cp-012 -m "Adopt progressive disclosure layout"
```

### canonical form

```bash
itt adoption create \
  --checkpoint cp-012 \
  --title "Adopt progressive disclosure layout" \
  --git HEAD
```

### v0.4 设计重点

#### 1. 默认作用于 current checkpoint

若未显式指定 checkpoint id，则：

* 默认采纳 current checkpoint；
* 若 current checkpoint 不存在，则报错并给出 next action；
* 若存在歧义状态，则不做猜测。

#### 2. 支持轻量 rationale

```bash
itt adopt -m "Adopt progressive disclosure layout" \
  --because "reduces cognitive load for first-time users"
```

说明：

* `--because` 默认写入 adoption 的 rationale；
* 简短理由不必强制拆成 decision；
* 只有长期有效、可复用取舍才推荐显式 `decide`。

#### 3. adopt 的输出必须强化“结果导向”

成功输出建议类似：

```text
Adopted checkpoint cp-012
Intent: Reduce onboarding confusion
Git: a91c3d2
Recorded rationale: reduces cognitive load for first-time users
Next: itt log
```

即使对象模型严谨，用户也应从输出上立即理解：

**不是“创建了 adoption 对象”，而是“正式采纳了一个候选结果”。**

#### 4. Git linkage policy

* 若当前 `HEAD` 已提交，则默认记录关联 git ref；
* 若工作区未提交，则 warning 但允许继续；
* strict mode 可要求必须绑定稳定 commit。

### 必备 agent 能力

`adopt` / `adoption create` 必须支持：

* `--json`
* `--id-only`
* `--if-not-adopted`
* `--checkpoint <id>`
* `--link-git <hash|HEAD>`
* `--no-interactive`
* `--yes`

---

## 8.5 `itt status`

### 作用

查看当前 semantic workspace 状态，并输出推荐下一步动作。

### 示例

```bash
itt status
```

### 设计定位

`status` 是人类入口，而不是“半结构化 inspect”。

它必须优先回答：

1. 当前在处理哪个 intent？
2. 当前工作对象是什么？
3. 当前整体状态是什么？
4. Git 状态是否健康？
5. 最合理的下一步是什么？

### 推荐输出风格

```text
Active intent: intent-003 Reduce onboarding confusion
Current checkpoint: cp-012 Landing page candidate B
State: candidate ready for adoption
Git: working tree clean, HEAD=a91c3d2
Next: itt adopt -m "Adopt progressive disclosure layout"
```

### next action 规则示例

* 当前无 active intent → 推荐 `itt start`
* 改了代码但未形成候选 → 推荐 `itt snap`
* 已有 checkpoint 未采纳 → 推荐 `itt adopt`
* adoption 后有重要取舍待沉淀 → 推荐 `itt decide`
* 多个候选存在且默认目标不明确 → 推荐 `itt checkpoint select`

---

## 8.6 `itt inspect`

### 作用

输出机器可读的 semantic context。

### 示例

```bash
itt inspect
itt inspect --json
```

### 设计定位

`inspect` 是 agent / Skill / IDE / automation 的标准上下文入口。

### 与 `status` 的区别

* `status` 是给人看的当前状态
* `inspect` 是给机器读的稳定上下文
* `inspect` 的目标不是好看，而是稳定可消费

### 建议输出字段

* active_intent
* active_run
* current_checkpoint
* latest_adoption
* git_branch
* git_head
* working_tree_status
* pending_items
* suggested_next_actions
* warnings
* mode

### JSON 示例

```json
{
  "ok": true,
  "active_intent": {
    "id": "intent-003",
    "title": "Reduce onboarding confusion"
  },
  "current_checkpoint": {
    "id": "cp-012",
    "title": "Landing page candidate B",
    "status": "ready_for_adoption"
  },
  "latest_adoption": {
    "id": "adopt-007",
    "checkpoint_id": "cp-010"
  },
  "git": {
    "branch": "feature/onboarding-v2",
    "head": "a91c3d2",
    "working_tree": "clean"
  },
  "suggested_next_actions": [
    {
      "command": "itt adopt -m \"Adopt progressive disclosure layout\"",
      "reason": "current checkpoint is ready for adoption"
    }
  ],
  "warnings": [],
  "mode": "agent"
}
```

---

## 8.7 `itt decide`

### 作用

记录关键取舍、设计原则或长期有效 reasoning。

### 示例

```bash
itt decide "Use progressive disclosure instead of dashboard-first layout"
```

带理由：

```bash
itt decide "Use progressive disclosure instead of dashboard-first layout" \
  --because "first-time users need lower cognitive load"
```

### v0.4 设计要求

* decision 不是每次 adopt 的必需步骤；
* 它只在 reasoning 值得独立沉淀时出现；
* 它不应退化成通用备注容器。

### 使用原则

推荐创建 decision 的场景：

* 这是一个长期有效的设计原则；
* 这个判断可能在未来多次复用；
* 团队需要明确“为什么不是另外一个方案”。

---

## 8.8 `itt log`

### 作用

查看 semantic history。

### 默认输出重点

默认优先展示：

* adoption
* checkpoint
* decision
* intent switch

### 设计原则

v0.4 继续坚持：

* adoption 是 headline object；
* checkpoint 是候选形成节点；
* decision 是关键 reasoning 节点；
* run 不应成为默认 headline。

### 示例

```bash
itt log
```

扩展形式：

```bash
itt log --include-runs
```

---

## 8.9 `itt revert`

### 作用

撤销某次 adoption。

### 示例

```bash
itt revert adopt-007 -m "Revert due to increased cognitive load in testing"
```

### canonical form

```bash
itt adoption revert adopt-007 --reason "Revert due to increased cognitive load in testing"
```

### 设计原则

* 顶层继续保留 `itt revert` 以保持 Git-like 体验；
* semantic revert 应形成新的历史节点；
* 旧 adoption 不被删除，而被后续历史覆盖与说明。

---

## 8.10 `itt run start` / `itt run end`

### 作用

记录一次 agent 执行或协作尝试的开始与结束。

### 示例

```bash
itt run start
itt run end -m "Generated landing page candidate with progressive disclosure"
```

### v0.4 定位

* run 继续存在；
* 但更偏向高级 / agent / telemetry 场景；
* 普通用户不需要在首页 workflow 中先理解 run；
* 将来可以支持自动 run 生成。

---

## 8.11 `itt checkpoint select`

### 作用

显式设置 current checkpoint。

### 示例

```bash
itt checkpoint select cp-012
```

### 设计价值

它是 current object philosophy 的关键补足命令。

适用场景：

* 存在多个候选结果；
* 用户想显式切换默认目标对象；
* agent 需要稳定设置后续 adopt 对象。

---

## 9. Current Object 机制

v0.4 继续明确 current object philosophy，但将其定位为 human UX 的核心，而不是 automation 的主要契约。

### 9.1 active intent

系统维护一个 active intent 作为默认语义上下文。

### 9.2 current checkpoint

系统维护一个 current checkpoint 作为默认候选对象。

创建新 checkpoint 时：

* 自动成为 current checkpoint。

显式切换时：

```bash
itt checkpoint select cp-012
```

### 9.3 默认行为规则

#### 人类模式

* `itt start`：创建并切换到 active intent
* `itt snap`：创建并切换到 current checkpoint
* `itt adopt`：默认采纳 current checkpoint
* `itt status`：优先展示 current intent 与 current checkpoint

#### agent 模式

* 推荐显式传 intent id / checkpoint id；
* default current object 可以存在，但不应作为强契约；
* `inspect --json` 返回 current object 信息供 agent 判断。

### 9.4 冲突处理

如果存在多个未采纳 checkpoint 且当前默认对象不清晰：

* `itt adopt` 不应猜测；
* 返回 state conflict；
* 输出明确 next action。

---

## 10. Agent-Friendly 规范

v0.4 将 agent compatibility 视为第一等设计要求，而不是附加增强项。

### 10.1 所有读命令支持 `--json`

至少包括：

```bash
itt status --json
itt log --json
itt checkpoint list --json
itt checkpoint show cp-012 --json
itt inspect --json
```

### 10.2 所有写命令返回稳定对象结构

例如：

```bash
itt adopt --checkpoint cp-012 -m "Adopt progressive disclosure layout" --json
```

返回：

```json
{
  "ok": true,
  "object": "adoption",
  "id": "adopt-007",
  "intent_id": "intent-003",
  "checkpoint_id": "cp-012",
  "git_ref": "a91c3d2",
  "git_linkage_quality": "stable_commit"
}
```

### 10.3 所有写命令支持 non-interactive 模式

例如：

* `--yes`
* `--no-interactive`

### 10.4 所有核心写命令支持幂等保护

例如：

* `--if-not-exists`
* `--if-not-adopted`
* `--dedupe-key <key>`

### 10.5 Exit code 必须可依赖

建议规范：

* `0`：success
* `1`：general failure
* `2`：invalid input
* `3`：state conflict
* `4`：object not found

### 10.6 `inspect` 是标准上下文入口

推荐 agent 调用顺序：

1. `itt inspect --json`
2. 判断当前 context 与 pending actions
3. 显式执行对象命令
4. 再次 `inspect --json` 验证状态变化

### 10.7 Agent contract 应单独成文

v0.4 建议后续将以下内容提炼为单独文档：

**《Intent CLI Agent Integration Contract v0.1》**

应包含：

* JSON contract
* write response schema
* exit code
* idempotency semantics
* non-interactive policy
* inspect-first workflow

---

## 11. Git 绑定策略

v0.4 继续明确 semantic history 与 Git history 的绑定原则。

### 11.1 checkpoint 与 Git

checkpoint 默认可绑定当前 `HEAD`：

* 若当前已有提交，则记录 HEAD hash；
* 若当前尚未提交，则记录 working tree context；
* checkpoint 不要求必须绑定稳定 commit。

### 11.2 adoption 与 Git

adoption 应尽量绑定稳定 Git 引用。

默认策略：

* 若当前存在已提交 HEAD，则自动绑定；
* 若 working tree 不 clean，则 warning 但允许继续；
* 返回结果中必须标识 linkage quality。

### 11.3 strict mode

strict mode / CI / automation policy 中，可要求：

* adoption 必须绑定 commit；
* working tree 必须 clean；
* 或要求显式传入 `--link-git <hash>`。

### 11.4 设计理由

这样做的原因是：

* 让 semantic history 不漂浮；
* 让人类工作流不过早变重；
* 给 automation / CI 保留更严格的策略空间。

---

## 12. 推荐命令集合

### 12.1 README 首页命令集合

v0.4 首页只展示以下 6 个命令：

```bash
itt init
itt start
itt status
itt snap
itt adopt
itt log
```

### 12.2 README 第二层命令

按需展示：

```bash
itt revert
itt decide
itt run start
itt run end
```

### 12.3 Canonical CLI 命令集合

```bash
itt intent create
itt intent list
itt intent show
itt intent switch

itt run start
itt run end
itt run list
itt run show

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

itt inspect
```

---

## 13. 输出文案原则

v0.4 新增一条重要要求：

**输出文案必须优先讲动作结果，而不是对象创建细节。**

### 13.1 不推荐的输出

```text
Created adoption object adopt-007
```

### 13.2 推荐的输出

```text
Adopted checkpoint cp-012
Intent: Reduce onboarding confusion
Git: a91c3d2
Next: itt log
```

### 13.3 原则说明

用户应优先理解：

* 做成了什么动作
* 对哪个对象生效
* 当前处于什么状态
* 下一步应该做什么

对象 id 与底层字段是附加信息，不应成为主叙事。

---

## 14. 本地存储结构建议

v0.4 继续采用 `.intent/` 作为本地元数据目录。

```text
.intent/
  config.json
  state.json
  intents/
    intent-001.json
  runs/
    run-001.json
  checkpoints/
    cp-001.json
  adoptions/
    adopt-001.json
  decisions/
    decision-001.json
```

### 14.1 `state.json` 建议字段

* active_intent_id
* active_run_id
* current_checkpoint_id
* mode
* schema_version

### 14.2 建议对象通用字段

* `id`
* `created_at`
* `updated_at`
* `intent_id`
* `run_id`
* `git_ref`
* `title`
* `summary`
* `status`

### 14.3 adoption 建议补充字段

* `checkpoint_id`
* `rationale`
* `git_linkage_quality`

---

## 15. 最小可验证闭环

v0.4 新增一个关键产品要求：

**Intent CLI 必须有一个别人可以在几分钟内跑通的最小闭环。**

### 15.1 最小 demo 路径

```bash
itt init
itt start "Improve onboarding"
itt snap "candidate B"
git add .
git commit -m "landing iteration"
itt adopt -m "Adopt candidate B"
itt log
```

### 15.2 为什么这很重要

因为新范式不是靠长文档建立信任，而是靠：

* 一条能跑通的路径
* 一个能被立刻理解的结果
* 一个能看见 semantic history 的实际输出

### 15.3 这条路径应满足的验证目标

用户跑完后应立刻理解三件事：

1. Git 仍然存在，而且正常工作；
2. Intent 记录了更高层的采纳历史；
3. semantic history 确实比 commit history 更接近“我们做了什么决定”。

---

## 16. v0.4 暂不引入的内容

以下内容仍不建议进入 v0.4：

### 16.1 原始对话全量存储

原因：

* 数据量大
* 信噪比低
* 容易使产品退化成聊天归档工具

### 16.2 `push` / `pull`

原因：

* 远端模型仍未稳定
* 本地对象模型与契约优先级更高

### 16.3 更复杂的新对象扩展

例如：

* proposal
* thread
* session
* discussion

原因：

* 当前问题不是对象不够多
* 而是现有对象是否足够顺手、稳定、可信

### 16.4 过早的平台化叙事主导产品表达

原因：

* 现阶段最该被验证的是 CLI
* 不是大而全协作平台想象
* 平台能力应建立在本地 semantic layer 成立之后

---

## 17. 与 Skill / IntHub 的关系

### 17.1 Skill 的角色

Skill 不只是推广方式，而应成为 Intent CLI 的天然执行层。

如果 agent 被系统性教会：

* 什么时候 `itt start`
* 什么时候 `itt snap`
* 什么时候 `itt adopt`
* 什么时候 `itt decide`
* 什么时候先 `itt inspect --json`

那么 semantic history 就会成为 agent 工作流的一部分，而不是用户额外维护的一层负担。

### 17.2 IntHub 的角色

当本地对象层、状态层与 CLI 契约稳定后，IntHub 可以自然成为远端协作层，用于组织和展示：

* intents
* checkpoints
* adoptions
* decisions
* semantic timelines

因此：

* **Intent CLI**：本地记录与语义操作层
* **IntHub**：远端组织与展示层
* **Skill / agent workflow**：让 agent 原生理解并使用 `itt`

### 17.3 v0.4 的优先级判断

在当前阶段：

**CLI 的成立性高于 IntHub 的叙事完整性。**

也就是说，先把本地 semantic workflow 做窄、做硬、做通，再让远端平台自然长出来。

---

## 18. 结论

Intent CLI v0.4 的核心方向可以概括为一句话：

**不扩对象，继续做减法；不只让模型成立，更要让首次使用、日常使用和 agent 使用都成立。**

具体体现为：

* 保留五对象模型；
* 将首页主路径继续收敛为 6 个命令；
* 用 `start` 替代 `new` 作为首页 intent 入口；
* 保留 `snap` 作为 checkpoint 的高频表层命令；
* 将 `adopt` 继续确立为第一核心动作；
* 将 `status` 彻底收敛为 human workflow 入口；
* 将 `inspect` 明确为 agent 标准上下文入口；
* 让 `run` 继续下沉到高级与 agent 场景；
* 让 `decision` 保持按需显式化；
* 强调输出文案必须结果导向；
* 引入“最小可验证闭环”作为产品成立条件；
* 继续将 local semantic layer 置于平台叙事之前。

最终可以用一句话总结：

**Git 记录代码变化，Intent 记录采纳历史，IntHub 组织语义历史。**
