# IntHub 同步契约（首版）

[English](../EN/inthub-sync-contract.md) | 中文

## 这篇文档回答什么

- IntHub 首版如何在本地 Intent CLI、IntHub 服务端和 GitHub 之间分工
- 首版同步数据到底长什么样
- 首版的身份、幂等、对象归属和最小 API 面应该如何定义
- 什么能力是首版必须做的，什么能力要明确延后

## 与其他文档的边界

- 产品定位与首期范围以 [IntHub MVP 设计文档](inthub-mvp.md) 为准
- 本地对象模型以 [CLI 统一设计文档](cli.md) 为准
- 本文只回答 “如何把本地 `.intent/` 安全同步到 IntHub，并在远端形成可读协作视图”

## 1. 首版不变约束

- 首版只支持 **GitHub-first** 的仓库来源
- GitHub 负责 repo identity、权限和 Git 上下文
- IntHub 负责 semantic data 的同步、存储、索引和展示
- `.intent/` 必须继续留在本地工作区，不提交到 Git，也不作为 GitHub 内容被消费
- IntHub Web 首版默认 **只读**
- 本地 CLI 继续是主要写入口
- PyPI 分发保持 CLI-only；IntHub Web 和 API 不属于 Python 包分发边界

## 2. 首版系统分工

### 本地 CLI

负责：

- 读取 `.intent/` 中的 `intent / snap / decision`
- 读取当前 Git 上下文
- 生成同步 payload
- 将 payload 推送到 IntHub

不负责：

- 远端对象编辑
- 远端搜索索引
- 远端对象冲突合并

### IntHub API

负责：

- 身份校验
- repo 绑定校验
- 接收 sync batch
- 以 append-only 方式保存原始 batch
- 派生当前读模型
- 为 Web 提供 overview / handoff / detail / search 数据

部署说明：

- 首版 API 可以继续和仓库放在一起开发，但不属于 PyPI 分发面

### GitHub

负责：

- 用户身份与 repo 授权
- repo / branch / commit / release 等代码上下文

不负责：

- semantic object 主存储
- semantic object 查询
- semantic object 关系计算

### IntHub Web

部署说明：

- 首版 Web shell 是静态前端，适合通过 GitHub Pages 或其他静态托管方式发布

## 3. 首版 provider 与权限模型

首版只支持 GitHub 作为 repo provider。

建议的权限模型：

- **生产环境优先使用 GitHub App**
- 本地开发或早期验证阶段可以临时使用个人 token

原因很直接：

- GitHub App 更适合按仓库安装和回收权限
- 个人 token 虽然快，但长期权限边界更差

首版可以接受以下折中：

- IntHub 账号体系先复用 GitHub 登录
- 一个 IntHub project 在首版实现上可以先只绑定一个 GitHub repo

注意，这只是首版实现收敛，不是长期模型限制。

## 4. 本地 hub 配置

首版建议在 `.intent/` 下新增一个本地专用文件：

```text
.intent/
  config.json
  hub.json
  intents/
  snaps/
  decisions/
```

`hub.json` 是 **本地运行时配置**，不是语义对象的一部分。

建议最小结构：

```json
{
  "api_base_url": "http://127.0.0.1:8000",
  "auth_token": "",
  "workspace_id": "wks_01J....",
  "project_id": "proj_01J....",
  "repo_binding": {
    "provider": "github",
    "repo_id": "dozybot001/Intent",
    "owner": "dozybot001",
    "name": "Intent"
  },
  "last_sync_batch_id": "sync_01J....",
  "last_synced_at": "2026-03-19T00:00:00Z"
}
```

设计意图：

- `api_base_url` 与 `auth_token` 属于本地运行时配置
- `workspace_id` 必须对同一份 checkout 稳定
- 但它不属于 Git 内容，也不应跨 clone 自动共享
- `project_id` 与 `repo_binding` 用于把当前工作区连到 IntHub

## 5. 身份与对象归属

首版至少需要区分以下几类标识：

| 标识 | 含义 |
| --- | --- |
| `project_id` | IntHub 项目 |
| `repo_id` | GitHub 仓库 |
| `workspace_id` | 一份本地 checkout |
| `sync_batch_id` | 一次同步 |
| `remote_object_id` | IntHub 内部对象主键 |
| `local_object_id` | 本地 `intent-001` / `snap-001` / `decision-001` |

首版的关键规则：

- 本地对象不能直接拿 `intent-001` 作为远端主键
- 远端对象的唯一归属键应是：
  - `workspace_id`
  - `object_type`
  - `local_object_id`

也就是说，两个不同 workspace 里都存在 `intent-001` 是合法的，远端不能自动把它们视为同一个对象。

## 6. CLI 首版命令面建议

首版建议只引入最小入口：

```bash
itt hub login
itt hub link
itt hub sync
```

职责划分：

- `itt hub login`
  - 获取 IntHub 访问令牌
- `itt hub link`
  - 选择或创建 IntHub project
  - 绑定当前 GitHub repo
  - 初始化本地 `.intent/hub.json`
- `itt hub sync`
  - 读取 `.intent/`
  - 补充 Git 上下文
  - 生成并推送一个 sync batch

首版不建议做：

- `itt hub pull`
- `itt hub edit`
- `itt hub comment`

因为这些都会把首版从 sync-first 拉向双向协同系统。

## 7. Sync batch payload

首版推荐上传 **完整对象快照**，而不是增量 patch。

建议的最小 payload：

```json
{
  "sync_batch_id": "sync_01J...",
  "generated_at": "2026-03-19T00:00:00Z",
  "client": {
    "name": "intent-cli-python",
    "version": "1.3.0"
  },
  "project_id": "proj_01J...",
  "repo": {
    "provider": "github",
    "repo_id": "123456789",
    "owner": "dozybot001",
    "name": "Intent"
  },
  "workspace": {
    "workspace_id": "wks_01J..."
  },
  "git": {
    "branch": "main",
    "head_commit": "abc123",
    "dirty": true,
    "remote_url": "git@github.com:dozybot001/Intent.git"
  },
  "snapshot": {
    "schema_version": "1.0",
    "intents": [],
    "snaps": [],
    "decisions": []
  }
}
```

其中：

- `snapshot.intents / snaps / decisions` 直接承载当前本地对象 JSON
- 不要求客户端先算派生视图
- 不要求客户端上传完整终端日志或原始聊天记录

## 8. 幂等与接收规则

首版必须把这些规则写死：

### 8.1 幂等

- `sync_batch_id` 由客户端生成
- 同一个 `sync_batch_id` 重复上传时，服务端必须返回相同结果，不重复入库

### 8.2 接收校验

服务端至少应校验：

- 用户是否有对应 IntHub project 权限
- 当前 repo 是否已绑定到该 project
- payload 中的 GitHub repo 信息是否与绑定一致
- `workspace_id` 是否存在于当前 project
- `schema_version` 是否可接受

### 8.3 dirty 工作区

首版 **允许** `dirty = true` 的同步。

这是必要的，因为：

- 语义协作常常发生在提交之前
- handoff 不应被迫等待 commit

但 Web 必须明确展示 dirty 状态，避免用户误以为该语义已和某个 clean commit 完全对齐。

## 9. 服务端存储与派生规则

首版建议采用两层存储：

### 原始层

- append-only 保存每个 `sync batch`
- 保留完整原始 payload

### 派生层

- 基于每个 workspace 的最新 batch 计算当前对象状态
- 基于 project 范围聚合 overview / handoff / search

首版的一个重要简化是：

- **不跨 workspace 自动合并语义对象**

这意味着：

- IntHub 可以在项目页聚合多个 workspace 的状态
- 但不会假装两个不同 workspace 的 `intent-001` 是同一个东西

## 10. 首版最小 API 面

首版建议至少具备这些接口：

### 写接口

- `POST /api/v1/hub/link`
- `POST /api/v1/sync-batches`

### 读接口

- `GET /api/v1/projects/:project_id/overview`
- `GET /api/v1/projects/:project_id/handoff`
- `GET /api/v1/projects`
- `GET /api/v1/intents/:remote_object_id`
- `GET /api/v1/decisions/:remote_object_id`
- `GET /api/v1/snaps/:remote_object_id`
- `GET /api/v1/search`

首版可以不急着提供：

- 通用对象更新接口
- 远端评论接口
- 远端状态修改接口

## 11. Web 首版读模型要求

Web 首版只需要 4 个高价值视图：

### Project Overview

展示：

- active intents
- active decisions
- recent snaps
- workspace sync 状态

### Handoff

聚合展示：

- 当前仍在推进的 intent
- 每个 intent 的最新 snap
- 当前 active decisions

### Intent Detail

展示：

- 当前对象状态
- snap 时间线
- 来源 workspace
- 最近一次同步时的 branch / commit / dirty

### Search

仅覆盖：

- title
- query
- summary
- rationale

## 12. 安全与隐私边界

首版必须明确不上传这些内容：

- 原始聊天全文
- 文件内容
- diff 内容
- shell 原始日志

首版同步的只是结构化 semantic objects 和必要的 Git 上下文。

这条边界非常重要，否则 IntHub 很容易滑向“远端工作日志平台”。

## 13. 建议的首版实现顺序

1. 定义 `hub.json` 与 `sync batch` schema
2. 做 `itt hub link` / `itt hub sync`
3. 做 `POST /sync-batches` 与 append-only 存储
4. 做 project overview / handoff 读接口
5. 做只读 Web 页面
6. 最后再补搜索

## 14. 判断是否可以开始做第一版

当下面这些问题已经没有歧义时，就可以开始实现：

- semantic data 是否进入 Git / GitHub
- GitHub 在系统中的职责是什么
- workspace 如何稳定标识
- sync batch 是否上传完整快照
- 首版是否允许 dirty sync
- 首版是否保持 Web 只读

如果这些问题还在摇摆，就不该开工。
