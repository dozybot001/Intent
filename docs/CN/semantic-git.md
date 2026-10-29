# 语义版 Git：Intent 8 设计提案

中文 | [English](../EN/semantic-git.md)

状态：提案（2026-10-30）。目标版本：Intent 8.0。

## 目标

让 `itt` 在语义历史上的行为与 Git 一致。熟悉 Git 的开发者应当能预判 Intent 如何处理并行工作、多台机器、worktree 和分叉，因为它的处理方式就是 Git 的方式。

目前（7.x）还做不到：

- 对象 ID 是每份副本各自递增的计数（`snap-003`），两份副本并行记录会产生相同 ID。
- 每个项目只有一条线性历史。push 和 pull 只做快进；分叉后 `itt status` 报告 `diverged`，没有合并手段。
- 每次推送的修订都保存一份完整快照，而本地仓库完全不保留修订历史。
- 在 Git worktree 中，Intent 找不到主工作区的 `.intent/`。

## 唯一的有意差异：没有暂存区

Git 要求人先暂存再提交。Intent 的写入者大多是正在做其他事的 Agent，它的首要承诺是低打扰。因此每次写入（`intent create`、`snap create`、状态变化）都立即生成一个修订，相当于带自动生成说明的 `git commit -a`。其余一切都对标 Git。

## 概念对照

| Git | Intent 8 |
|---|---|
| blob | 对象版本：某个 Intent、Snap 或 Decision 在某一时刻的 JSON 内容 |
| tree | 项目状态：对象 ID → 对象版本 |
| commit | **修订**：tree、父修订、作者/来源、时间、自动生成的摘要和变更对象列表 |
| 对象哈希 | 新对象使用内容寻址 ID（`snap-3f9a2c1…`，像 Git 一样缩写显示、接受唯一前缀）。旧的计数 ID 永久有效 |
| `HEAD`、分支、refs | `.intent/HEAD`、`refs/heads/*`；`itt branch`、`itt switch` |
| `git log` / `show` / `diff` | `itt log`（修订）、`itt show ID|REV`、`itt diff A..B`（语义差异：新增 Snap、状态变化、新增或废弃的 Decision） |
| `git status` | 当前分支、上游、领先/落后数量 |
| 远端、`fetch`、`pull`、`push`、`clone` | `itt remote`、`itt fetch` 到 `refs/remotes/origin/*`、`itt pull` = fetch + merge、`itt push`（落后时被拒绝，与 Git 相同）、`itt clone URL --project NAME` |
| 三方合并 | **语义三方合并**，以合并基准为准（见下文） |
| worktree | 通过 `git rev-parse --git-common-dir` 定位仓库，所有 worktree 共享一个语义仓库，各自有自己的 `HEAD` |
| tag | `itt tag` 标记里程碑（后续） |

## 存储（仓库格式 2）

```text
.intent/
  objects/ab/cdef….json        不可变的对象版本，按哈希寻址
  revisions/ab/cdef….json      {parents, tree, author, origin, time, summary, changes}
  refs/heads/main
  refs/remotes/origin/main
  HEAD                         "ref: refs/heads/main"
  config.json                  远端、上游、维护开关
```

对象在创建时获得稳定身份。修改 Intent 状态会写入同一 ID 的新版本，就像在 Git 中修改文件。关系列表（`snap_ids`、`decision_ids`、`intent_ids`）变为只增集合。

## 语义合并

Snap 只追加，新 ID 不会冲突，所以大多数合并就是并集。对于合并基准之后两边都改过的对象：

- 只增的关系集合：取并集，按 `created_at` 排序；
- `status`：两边相同，或只有一边改动，可以直接合并；两边改成不同的新状态（例如 `done` 与 `cancelled`）才是冲突；
- `reason` 与一次性写入的描述字段：只有两边改得不一样时才冲突。

冲突是结构化的，不是文本标记：`itt merge` 停下，`itt status` 列出冲突对象及两边的值，用 `itt resolve ID --status done`（或 `--ours`/`--theirs`）逐个解决，然后 `itt merge --continue` 或 `itt merge --abort`。Agent 以 JSON 获得同样的信息。

## 远端协议 3 与 IntHub

push 与 fetch 像 Git 协商 pack 一样协商缺失的修订和对象版本。IntHub 保存修订 DAG 与去重后的对象，同时消除了目前每次推送都存一份完整快照的问题。分支 ref 按项目保存；网页先展示 `main`，并增加分支与历史视图。迁移期间 IntHub 继续接受 7.x 协议。

## 从 7.x 迁移

`itt` 8 通过显式的 `itt migrate` 无损转换 7.x 仓库（迁移前拒绝写入）：现有对象成为第一个修订，保留旧 ID，IntHub 远端重新关联到同一项目。迁移后不支持降级，因此命令会先做备份。

## 分阶段实施

1. 仓库格式 2：对象、修订、refs、自动修订，`itt log`、`show`、`diff`，迁移，新对象使用哈希 ID。
2. 分支与 worktree：`itt branch`、`itt switch`、Git worktree 识别。
3. 带结构化冲突的语义合并。
4. 远端协议 3：`fetch`、`pull` = fetch + merge、`push`、`clone`；IntHub 修订 DAG 与分支视图。
5. Agent 工作流：Skill 与 hook 对分支和冲突的指引。

每个阶段都附带迁移与兼容测试；第 1 到 3 阶段只涉及本地，可以先于服务端改动发布。

## 需要所有者决定的问题

1. 新对象使用哈希 ID（推荐），还是保留计数并加副本前缀？
2. 每次写入自动生成修订（推荐），还是显式 `itt commit`？
3. 首发时 IntHub 是否展示分支，还是只展示 `main` 及合并历史？
