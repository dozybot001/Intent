# Intent 愿景笔记 v3

## 导读

**本文回答什么**

- 为什么 agent 时代需要一层新的 semantic history
- Intent 试图解决的核心痛点是什么
- 它与 Git、Intent CLI、Skill 与 IntHub 分别是什么关系

**适合谁读**

- 第一次接触 Intent 的读者
- 想理解项目长期方向和问题定义的人
- 想先理解“为什么做”再进入设计与实现的人

**与其他文档关系**

- 这篇文档负责说明问题、背景和长期方向
- 如果你想看 CLI 应该如何设计，请继续读 [Intent CLI Design Spec v0.4](intent_cli_design_spec_v_0_4_cn.md)
- 如果你想直接进入 schema、状态机和实现 contract，请读 [Intent CLI Implementation Contract v0.1](intent_cli_implementation_contract_v_0.md)

---

## 1. 核心判断

在 vibe coding 时代，软件的底层仍然是代码，Git 仍然是记录代码变化的基础设施。

变化的不是代码消失了，而是：

* 人越来越少直接与代码交互；
* 人越来越多通过 agent 间接塑造代码；
* 开发过程开始稳定地产生一层新的高层对象：意图、候选方案、采纳、撤销、决策、checkpoint。

因此，新的问题不是“如何替代 Git”，而是：

**如何在 Git 之上，为人和 agent 的协作建立一层新的语义记录系统。**

Intent 的定位正是这一层。

它不试图否定 Git，而是试图补上 Git 天然没有被设计去承担的部分：**semantic history**。

---

## 2. 真正的痛点：不是信息不存在，而是信息没有成为一等对象

今天的软件协作里，高层语义信息其实并不稀缺。

相反，它到处都是，散落在：

* commit message
* issue
* PR review
* design doc
* 团队聊天
* agent conversation
* 临时说明、口头共识与本地笔记

问题不是“没有这些信息”，而是这些信息大多：

* 不集中；
* 不稳定；
* 不可持续追踪；
* 不以统一对象模型存在；
* 不适合被 agent 稳定读取和操作；
* 很难形成可比较、可采纳、可撤销、可查询的历史。

所以今天真正缺失的，不是代码历史，而是：

**语义历史。**

我们能看到代码怎么变了，却很难可靠地恢复：

* 这次演化本来想解决什么问题；
* agent 是围绕哪个目标在工作；
* 多个候选方案里最后采纳了哪一个；
* 为什么采纳这一版，而不是另一版；
* 哪次改动对应哪个更高层的产品意图；
* 某个 checkpoint 在语义上到底意味着什么。

因此，Intent 要解决的不是“记录更多信息”，而是：

**把原本碎片化存在的高层语义，提升为第一类历史对象。**

---

## 3. 为什么现有工具组合不够

很多人第一反应会是：

为什么不能继续用 Git + PR + issue + docs + 聊天记录？

答案是：这些工具能共同承载一部分语义，但它们并没有把语义本身定义成一个统一、稳定、可操作的对象系统。

现有组合的问题不在于“完全不能用”，而在于它们的语义表达具有以下结构性缺陷：

### 3.1 语义被分散表达，而不是被正式建模

今天“为什么做”“在比较什么”“最终采纳什么”，可能分别存在于：

* issue 标题
* PR 描述
* 某条评论
* 某个 doc 段落
* 某次 agent 对话
* 某句 commit message

这些内容可以阅读，却很难作为一个完整对象被引用、查询、比较、回滚和复用。

### 3.2 语义节点缺乏稳定边界

Git 很擅长描述 patch、commit、branch、merge 这些代码世界的一等对象。

但它并不天然擅长描述：

* 当前 active intent 是什么；
* 某次探索产生了哪些候选；
* 哪个候选被正式采纳；
* 采纳背后的取舍是否值得沉淀为长期决策。

也就是说，代码对象的边界很清楚，语义对象的边界却往往是模糊的、临时的、依附性的。

### 3.3 对 agent 不够友好

在 agent-driven development 中，系统需要的不只是“能读给人看”的说明，而是：

* 稳定的对象 id；
* 明确的状态机；
* 可预测的上下文入口；
* 可消费的结构化历史；
* 可执行的语义操作。

Issue、PR、聊天、文档可以辅助理解，但它们不是为此设计的。

### 3.4 “采纳”没有成为系统中心动作

在传统开发里，核心动作更接近“编写代码”。

但在 agent 时代，越来越关键的动作其实是：

* 提出目标；
* 生成候选；
* 比较候选；
* 正式采纳；
* 必要时撤销；
* 沉淀决策理由。

也就是说，高层协作的中心正在从“写”逐渐转向“选”。

现有工具组合并没有把“采纳”定义成一个一等、可追踪、可回退的历史动作。

---

## 4. Intent 的解决方案

Intent 不替代 Git。

Intent 的目标，是构建一个 **Git-compatible 的高层语义层**：

* Git 记录代码变化；
* Intent 记录语义变化；
* Git 管理 code history；
* Intent 管理 semantic history。

可以把它理解为：

**Intent 是构建在 Git 之上的 intention and adoption layer。**

它面向的对象不是底层 code，而是更高层的开发对象，例如：

* intent
* checkpoint
* adoption
* decision
* semantic history

在这个模型里，Intent 不去和 Git 争夺“谁管理代码版本”这件事，而是回答另一组问题：

* 当前想解决什么问题？
* 已经形成了哪些候选结果？
* 最终正式采纳了哪个候选？
* 为什么是这个，而不是那个？

一句话说：

**Git 记录代码变化，Intent 记录采纳历史。**

---

## 5. Intent 不是日志工具

这里必须把边界说清楚：

**Intent 不是为了记录一切，而是为了记录那些值得被正式采纳、撤销、比较和追溯的语义节点。**

这意味着：

* Intent 不追求保存全部原始对话；
* 不追求备份每一步中间过程；
* 不追求成为另一个“开发日志归档系统”；
* 不追求把所有上下文都塞进一个重型数据库。

Intent 关注的是那些真正“成立”的高层动作：

* 一个 intent 被正式开启；
* 一个 checkpoint 被形成；
* 一个候选被正式采纳；
* 一次 adoption 被撤销；
* 一个值得长期复用的 decision 被沉淀。

因此，Intent 的价值不在于“记录更多”，而在于：

**记录更少，但记录得更正式、更稳定、更可操作。**

---

## 6. 为什么这是 agent 时代的新需求

在传统开发中，程序员直接操作代码，很多高层语义虽然没有被正式建模，但至少还天然存在于人的脑中，或者散落在 issue、PR、docs、review 和团队聊天里。

这虽然不完美，但还能运作。

而在 vibe coding / agent-driven development 时代，情况发生了变化：

* 人和代码之间插入了 agent；
* 大量实现过程由 agent 承担；
* 候选方案数量显著增加；
* 人对底层实现细节的直接控制减少；
* “最终为什么选择这一版”变得更加不透明；
* 用户与 agent 的 query、修正、采纳、撤销，本身开始成为开发过程的一部分。

于是，新的系统需求出现了：

**不仅要记录代码怎么变，还要记录意图是如何被表达、尝试、比较、采纳和沉淀的。**

换句话说，当人越来越像 reviewer / selector / director，而 agent 越来越像 executor 时，软件历史记录的中心就不能只停留在 code diff 上。

---

## 7. 产品路线：先做本地 semantic layer，再谈平台

Intent 的第一阶段不应该是大而全的平台，而应该是一个本地、开源、可验证的 CLI。

原因很简单：

* Git 的成功，首先来自清晰的本地模型和命令系统；
* Intent 也必须先建立自己的本地对象层与操作逻辑；
* 在对象模型和状态契约尚未稳定前，直接做平台会过早复杂化；
* 一个新范式要先证明“工作流成立”，再证明“平台叙事成立”。

因此，第一阶段产品是：

## Intent CLI

Intent CLI 的角色，类似于 Git CLI，只不过它管理的不是 code objects，而是 semantic objects。

例如可以建立这样的理解映射：

* `git commit` 对应一次 adoption
* commit message 对应 adoption message
* log 对应 semantic history 查看
* revert 对应 adoption 的撤销或回退

这并不意味着 Intent 在 CLI 层就已经和 Git 本质不同。

恰恰相反：

**在 CLI 层，Intent 和 Git 的逻辑是相似的。**

它们都在记录“变化的历史”。

区别只在于：

* Git 面向的是代码对象；
* Intent 面向的是语义对象。

---

## 8. 为什么 CLI 必须先成立

Intent 这个项目最危险的地方，不是想法太小，而是太容易过早变大。

如果一开始就把重点放到远端平台、协作可视化和大规模语义网络上，项目很容易变成一个“听起来很对，但用不起来”的系统。

所以第一阶段真正要验证的不是：

* 能不能讲出一个宏大的故事；
* 能不能做出一个像 GitHub 的平台；
* 能不能把所有信息都接入统一图谱。

而是：

* 本地 semantic workflow 是否成立；
* 核心对象是否足够清楚；
* 命令是否足够顺手；
* agent 是否可以稳定调用；
* semantic history 是否真的比 commit history 更接近“我们做了什么决定”。

Intent CLI 的成立性，才是后续一切叙事的前提。

---

## 9. 最小可验证闭环

一个新范式不会因为文档写得漂亮而成立，只会因为有一个足够小、足够硬、足够可跑通的闭环而成立。

Intent 的最小闭环应该是：

1. 开始一个 intent
2. 形成一个 candidate / checkpoint
3. 正式采纳它
4. 在 log 中看到 semantic history

例如：

* `itt init`
* `itt start "Improve onboarding"`
* `itt snap "candidate B"`
* `git commit -m "landing iteration"`
* `itt adopt -m "Adopt candidate B"`
* `itt log`

当别人能在几分钟内跑通这条路径，并立刻看到：

* Git 仍然正常工作；
* Intent 没有替代 Git；
* Intent 额外记录了“采纳了什么、为什么采纳”这一层历史；

这个项目才开始从“概念成立”走向“产品成立”。

---

## 10. 与 agent 的真正差异化

Intent 不只是给人类多一套命令。

它更重要的价值在于：它天然适合作为 agent 的语义操作层。

对于 agent 来说，最需要的不是更多 prose，而是：

* 稳定的对象模型；
* 明确的当前状态；
* 结构化的上下文入口；
* 可预测的写入行为；
* 可幂等的历史操作。

这也是为什么 Intent 和普通“笔记工具”“开发日志工具”不同。

笔记工具记录的是描述；
Intent 记录的是对象化的语义动作。

日志工具记录的是过程痕迹；
Intent 记录的是正式成立的 semantic nodes。

因此，Intent 的长期价值不只是帮助人类回忆过去，更是让 agent 能稳定参与未来。

---

## 11. IntHub 的位置

IntHub 仍然重要，但它不应该在第一层叙事里抢走 Intent CLI 的位置。

更准确地说：

* **Intent CLI** 是本地记录与语义操作层；
* **Skill / agent workflow** 是让 agent 原生理解并使用 `itt` 的执行层；
* **IntHub** 是远端组织与展示层。

也就是说，IntHub 不是第一阶段要证明的东西，而是当本地 semantic layer 已经成立之后，自然会长出来的第二阶段产品。

到那时，IntHub 可以承载和展示：

* 一个项目当前在追求哪些 intents；
* 哪些 checkpoints 被形成；
* 哪些 adoption 被正式接受或撤销；
* 某个功能的语义演化路径是什么；
* 多个 agent 方案是如何被比较、筛选和确认的；
* 哪些 decision 构成了长期有效的产品/架构判断。

所以，Intent 的愿景不是“先做一个新的 GitHub”。

更准确的说法是：

**先把 semantic history 在本地做成立，再让远端协作层自然长出来。**

---

## 12. Intent 的一句话定义

### 中文

Intent 是一个构建在 Git 之上的高层语义版本系统，用来记录 agent 时代软件开发中的意图、候选、采纳与决策历史。

### English

Intent is a Git-compatible semantic history layer for agent-driven software development.

---

## 13. 最终愿景

Git 会继续作为代码世界的基础设施存在。

Intent 想做的，不是替代它，而是在其之上建立一个新的协作范式：

* 让人和 agent 的协作过程有正式的语义记录；
* 让意图、候选、采纳与决策成为一等对象；
* 让软件开发不仅有 code history，也有 semantic history；
* 让未来的构建平台不只理解代码如何变化，也理解系统为什么这样演化。

可以把这件事概括成三句话：

**Git 管代码。**
**Intent 管采纳历史。**
**IntHub 组织语义历史。**

这不是对 Git 的替代，而是对 agent 时代软件历史记录方式的一次补全。
