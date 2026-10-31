# 语义版 Git：Intent 8 设计

中文 | [English](../EN/semantic-git.md)

状态：已发布。第 1 到 3 阶段随 Intent 8.0 发布，第 4 阶段随 8.1 发布。

## 目标

让 `itt` 在语义历史上的行为与 Git 一致。熟悉 Git 的开发者应当能预判 Intent 如何处理并行工作、多台机器、worktree 和分叉，因为它的处理方式就是 Git 的方式。

7.x 做不到这些，也是 Intent 8 要解决的问题：

- 对象 ID 是每份副本各自递增的计数（`snap-003`），两份副本并行记录会产生相同 ID。
- 每个项目只有一条线性历史。push 和 pull 只做快进；分叉后 `itt status` 报告 `diverged`，没有合并手段。
- 每次推送的修订都保存一份完整快照，而本地仓库完全不保留修订历史。状态变化没有时间戳。
- 在 Git worktree 中，Intent 找不到主工作区的 `.intent/`。

## 已确定的决策（2026-10-30）

- 新对象使用哈希 ID，旧的计数 ID 永久有效。
- 每次写入都生成一个修订，没有 `itt commit`。
- IntHub 首发展示 `main` 及其合并历史，不提供分支图。
- 意图流转用 Intent 之间的关系表达，而不是分支（见[意图流转](intent-flow.md)），在 7.2 先行发布。

## 唯一的有意差异：没有暂存区

Git 要求人先暂存再提交。Intent 的写入者大多是正在做其他事的 Agent，它的首要承诺是低打扰。因此每次写入（`intent create`、`snap create`、状态变化）都立即生成一个修订，相当于带自动生成说明的 `git commit -a`。其余一切都对标 Git。

## 概念对照

| Git | Intent 8 |
|---|---|
| blob | 对象版本：某个 Intent、Snap 或 Decision 在某一时刻的 JSON 内容 |
| tree | 项目状态：对象 ID → 对象版本 |
| commit | **修订**：tree、父修订、作者/来源、时间、自动生成的摘要和变更对象列表 |
| 对象哈希 | 新对象使用哈希 ID（`snap-3f9a2c1…`，像 Git 一样缩写显示、接受唯一前缀）。旧的计数 ID 继续有效 |
| `HEAD`、分支、refs | `.intent/HEAD`、`refs/heads/*`；`itt branch`、`itt switch` |
| `git log` / `show` / `diff` | `itt log`（修订；`--graph` 画出分支）、`itt show ID|REV`、`itt diff A..B`（语义差异：新增 Snap、状态变化、新增或废弃的 Decision） |
| `git status` | 当前分支、上游、领先/落后数量 |
| 远端、`fetch`、`pull`、`push`、`clone` | `itt remote`、`itt fetch` 到 `refs/remotes/origin/*`、`itt pull` = fetch + merge、`itt push`（落后时被拒绝，与 Git 相同）、`itt clone PROJECT` |
| 三方合并 | **语义三方合并**，以合并基准为准（见下文） |
| worktree | 通过 `git rev-parse --git-common-dir` 定位仓库，所有 worktree 共享一个语义仓库，各自有自己的 `HEAD`，并推送自己的分支。bare 仓库和 `--separate-git-dir` 找不到主 worktree，这时各 worktree 各用自己的 `.intent/` |
| tag | `itt tag` 标记里程碑（后续） |

## 存储（仓库格式 2）

```text
.intent/
  trees/ab/cdef….json          {id: version}，分两层桶存放，修订之间共享未变的部分
  objects/ab/cdef….json        不可变的对象版本，按哈希寻址
  revisions/ab/cdef….json      {parents, tree, author, origin, time, summary, changes}
  refs/heads/main
  refs/remotes/origin/main
  HEAD                         "ref: refs/heads/main"
  hub.json                     远端和项目 ID
  maintenance.json             本项目的维护开关
```

`intents/`、`snaps/`、`decisions/` 继续作为可读的工作副本，就像 Git 的工作区：每次写入先改工作副本，再把它记录成一个修订，所以中断时最多留下一次尚未记录的改动，下一次写入会补上。命令被拒绝或中途被杀时都会撤销（被杀时由下一条命令完成），所以修订不会只记录半条命令。

对象在创建时获得稳定身份。修改 Intent 状态会写入同一 ID 的新版本，就像在 Git 中修改文件。关系列表（`snap_ids`、`decision_ids`、`intent_ids`）以及 Intent `relations` 中的记录都变为只增集合。

## 语义合并

Snap 只追加，新 ID 不会冲突，所以大多数合并就是并集。对于合并基准之后两边都改过的对象：

- 只增的关系集合：取并集，我方在前、对方在后。位置没有含义：最新 Snap 按 `created_at` 选取，hub 也按集合比较这些列表；
- `status`：两边相同，或只有一边改动，可以直接合并；两边改成不同的新状态（例如 `done` 与 `cancelled`）才是冲突；
- `reason` 与一次性写入的描述字段：只有两边设置得不一样时才冲突；
- Intent 的 `relations`：记录取并集，撤回优先；合并后若某个 Intent 出现两个上级或形成环，则视为冲突。

冲突是结构化的，不是文本标记：`itt merge` 停下，`itt status` 列出冲突对象及两边的值，用 `itt resolve ID --status done`（或 `--ours`/`--theirs`）逐个解决，然后 `itt merge --continue` 或 `itt merge --abort`。Agent 以 JSON 获得同样的信息。合并之后，WHAT 规范化后相同的进行中 Intent 会被列为可能重复，合并它们始终要显式使用 `--into`。

## 分支不等于意图流转

说到分支视图，自然会想到意图的流转、分支与汇合，但 Git 式的分支画不出这些。分支记录的是变更*在哪里*被记录（一台机器、一个 worktree、一次 Agent 会话），而不是目标之间*如何关联*。在每次写入自动生成修订的前提下：

| 情形 | 修订分支显示为 | 实际的意图流转 |
|---|---|---|
| 一个 Agent 在一个 worktree 里做 A 时发现子目标 B | 一条直线 | B 从 A 分出 |
| 两个 worktree 分别做互不相关的目标 A 和 C，然后合并 | 一次分叉加一次合并 | 两个独立的目标 |
| 笔记本和台式机都给 A 记了 Snap，然后合并 | 一次分叉加一次合并 | 一个目标，在两处记录 |
| 为 A 先后试了方案 X 和 Y，最终选 Y | 若都在同一分支上记录，则什么也看不出 | A 分出 X 和 Y，X 汇入 Y |
| 两份副本各自创建了「接入 Apple Pay」，然后合并 | 一次合并 | 同一目标被记录两次，需要合并 |

Git 本身也有这个缺口。提交图展示的是并行工作，团队靠「一个功能一个分支」之类的约定来表达功能结构。Intent 不能依赖这类约定，因为 Agent 不会遵守。

因此，意图流转用 Intent 之间的关系记录（见[意图流转](intent-flow.md)）。Snap 本来就归属于一个 Intent，Decision 可以注明它出自哪个 Intent。历史层补上关系无法提供的信息：每次变更发生的时间与记录的位置。修订分支只作为来源信息出现，并可在 `itt log --graph` 中查看，就像 `git log --graph` 之于 Git 用户。

## 远端协议 3 与 IntHub

`itt push` 先上传远端缺少的内容，再移动一个 ref。和 Git 远端一样，ref 只从推送者看到的位置出发、只向前移动，并且只在它能到达的内容全部到齐后才移动。`itt fetch` 分页下载本地缺少的内容。IntHub 用内容寻址的 blob 保存修订图，每个项目有自己的分支 ref，历史页展示 `main` 及其合并。`main` 同时按推送保留快照，供网页和协议 2 读取。

项目的协议 2 推送在首次使用修订图时转换成修订，并在 `legacy` 中保留旧 ID，所以修订图出现之前的副本能用最后看到的那次推送找到合并基点。迁移窗口内，旧客户端仍可读取和推送 `main`，它们的推送会并入修订图。

## 从 7.x 迁移

`itt` 8 通过显式的 `itt migrate` 无损转换 7.x 仓库，迁移前拒绝写入。现有对象成为第一个修订，保留旧 ID，IntHub 远端重新关联到同一项目。迁移后不支持降级，因此命令会先做备份。

## 分阶段实施

阶段 1 到 3 已在 Intent 8.0 发布，阶段 4 在 8.1 发布。

1. 仓库格式 2：对象、修订、refs、自动修订、新对象哈希 ID，`itt log`、`show`、`diff` 与 `itt migrate`。
2. 分支与 worktree：`itt branch`、`itt switch` 与 Git worktree 识别。
3. 带结构化冲突与重复目标提示的语义合并。
4. 远端协议 3：`fetch`、`pull` = fetch + merge、`push`、`clone`；IntHub 保存修订 DAG，展示 `main` 及其合并历史。

每个阶段都附带迁移与兼容测试，以及新增功能对应的 Skill 与 hook 指引。第 1 到 3 阶段只涉及本地，可以先于服务端改动发布。Intent 之间的关系在 7.2 单独发布，迁移时原样保留。
