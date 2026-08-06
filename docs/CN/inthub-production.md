# IntHub 官方生产部署规范

[中文](inthub-production.md) | [English](../EN/inthub-production.md)

## Metadata

- Status: implemented locally; production execution requires separate authorization
- Owner: project maintainers
- Last verified: 2026-08-07
- Runtime surface: local Git, Builder, Bundle, SSH, server, data, ingress
- 唯一正式入口：[release.sh](../../deploy/inthub/release.sh)
- 本地实现：[local-release.sh](../../deploy/inthub/local-release.sh)
- 构建入口：[build-release.sh](../../deploy/inthub/build-release.sh)
- 服务器激活：[remote-release.sh](../../deploy/inthub/remote-release.sh)
- Manifest：[release_manifest.py](../../deploy/inthub/release_manifest.py)

## 结论

IntHub 的默认发布闭环完全由本机和目标服务器控制：

```text
本地 clean main Commit
  → Commit 精确源码归档
  → 缓存的本地测试环境 + 固定 PostgreSQL 集成测试
  → Docker Desktop 共享 linux/amd64 Builder 构建一次
  → 最终 App 镜像在生产安全边界下本地 smoke
  → source + images + manifest + SHA256SUMS
  → 从磁盘重新完整验证并原子固化 Bundle
  → SSH/rsync 上传 incoming
  → 服务器先验证 Bundle，再取得 fail-closed lock
  → 固化只读 Release、备份、显式兼容迁移
  → 非活动 slot → readiness → 可逆切流 → 公网 smoke
  → 更新 current → 观察窗口 → 再次公网 smoke → 停止旧 slot
```

日常只有一个命令：

```bash
bash deploy/inthub/release.sh
```

该命令不会访问 GitHub API、等待云端 CI、push Commit、上传生产数据到 Registry，或在
服务器上执行 clone、依赖安装和 build。运行命令表示发起一次发布操作，但生产授权仍遵守
当前项目规则；仅构建 Bundle 时可单独运行 `build-release.sh`，不会接触服务器。

## GitHub 边界

项目只保留认可的 GitHub `origin` 作为异步镜像。`.github/workflows/tests.yml` 可以为已同步
Commit 提供附加反馈，但不属于发布门禁，也不会生成或部署生产制品。

- Commit 不要求先 push；`origin/main` 不参与 Release 身份或成功判定。
- 正式脚本不读取 remote URL、GitHub token、Actions 状态或 GHCR。
- GitHub 同步失败不影响本地构建、发布、验收或回滚。
- Bundle Manifest 不记录 `github_sync`、PR、workflow run 或云端状态。
- GitHub 同步是发布之外的普通 Git 操作，不得由 `release.sh` 隐式执行。
- GitHub 不是唯一备份；本地 Git、Bundle 与数据恢复材料需要自己控制的第二存储。

## 本地低成本适配

本机已有 Docker Desktop Builder `desktop-linux`，driver 为 `docker`，支持
`linux/amd64`。IntHub 将它作为默认机器级共享 Builder，不再创建项目专属 Builder：

```text
INTHUB_BUILDER=desktop-linux
INTHUB_BUILDER_DRIVER=docker
target=linux/amd64
```

`build-release.sh` 每次都读取并记录 Builder 名称、driver、Buildx/BuildKit 可见信息，要求
driver 与平台符合预期，否则失败关闭。迁移到另一台可信 Builder 时必须显式设置
`INTHUB_BUILDER` 和 `INTHUB_BUILDER_DRIVER`；脚本不会自动 fallback 到未知 Builder。

[prepare-release-env.sh](../../deploy/inthub/prepare-release-env.sh) 将固定发布测试依赖缓存在：

```text
dist/inthub-tools/<python-id>-<dependency-id>/
```

`dependency-id` 由本机 Python identity 与 `pyproject.toml` SHA-256 推导。第一次发布需要创建
venv 并安装依赖；依赖不变时直接复用。`dist/` 已被 Git 忽略，不污染 worktree，也不进入
源码归档、镜像、Bundle 或服务器。

## 本地质量门禁

`build-release.sh` 在产生 Bundle 前依次执行：

1. 要求当前仓库为 clean `main`，包括无 untracked files；
2. 固定完整 Git Commit 与版本，拒绝工作区在构建期间变化；
3. 检查 Docker Engine、Buildx、指定 Builder driver 和 `linux/amd64` 能力；
4. 校验或拉取 `runtime-images.lock.json` 中固定的 PostgreSQL `linux/amd64` platform manifest digest；
5. 准备或复用固定 pytest/psycopg 测试环境；
6. 启动临时 Linux/amd64 PostgreSQL，运行完整 pytest，包括 PostgreSQL 集成测试；
7. 执行 `git diff --check` 与 Commit object 检查；
8. 使用 `git archive` 导出 Commit 精确 source archive 和隔离 build context；
9. 扫描 tracked source 中的高置信度凭据与不支持的文件类型；
10. 推导并记录 database schema version 与 expand/contract 策略；
11. 在指定 Builder 上只构建一次 `inthub:<full-sha>`；
12. 从 `docker save` 归档核对 App/PostgreSQL 可移植 config digest、平台和 OCI revision/version/schema labels；
13. 用 read-only、cap-drop、no-new-privileges 边界启动最终 App 镜像并执行 health smoke；
14. 导出 App 和 PostgreSQL 镜像，创建 Manifest 与全文件 SHA-256；
15. 从磁盘重新验证精确文件集、Manifest、source recipe 与 checksum；
16. 原子 rename 为 `dist/inthub/<full-sha>`。

任一步失败都不会生成可发布 Bundle。已有同 SHA Bundle 时只允许完整验证后复用，不会覆盖
或拼接旧产物。

## Bundle 与 Manifest v3

Bundle 精确包含：

```text
source.tar.gz             Commit 精确 tracked source
images.tar.gz             linux/amd64 App + 固定 PostgreSQL 镜像
manifest.json             Release 身份、构建、测试、数据库与镜像证据
SHA256SUMS                精确文件集强校验和
compose.yaml              无 build，pull_policy=never
inthub.caddy              项目独立入口模板
release_manifest.py       标准库验证器
remote-release.sh         lock-protected 激活脚本
runtime-images.lock.json  PostgreSQL platform manifest/config digest/platform lock
smoke.sh                  loopback 与公网验收
```

Manifest schema v3 至少记录：

- `project_id=inthub`、完整 `git_sha`、`bundle_id=<git_sha>`、`dirty=false`；
- target `linux/amd64`；
- App 与 PostgreSQL reference、可移植 config digest、平台、RepoDigest 和 labels；
- Builder 名称、driver、Buildx 版本；
- Python、pytest、构建时间与实际通过的门禁；
- Dockerfile、`pyproject.toml`、runtime lock 的路径与 SHA-256；
- database schema version、expand/contract 与 backward-compatible 声明；
- source/image artifact 与所有 Release 文件的大小和 SHA-256。

验证器拒绝未知字段、截断 JSON、错误类型、额外或缺失文件、symlink、路径逃逸、source tar
特殊项、大小/checksum 漂移、错误平台、错误 config digest、错误 OCI label 与 runtime lock 漂移。
GitHub 同步状态属于未知字段，不能进入 Release 语义。

这里不使用 `docker image inspect .Id` 作为跨机器身份：启用 containerd image store 的 Docker
Desktop 会返回 OCI manifest/index digest，传统 Docker Engine 则返回 config digest。构建端和
服务器都从 `docker save` 的 `Config` 成员读取相同的 config digest，因此 Bundle 在两种
image store 之间迁移时不会误报或放过身份漂移。

## 上传与服务器固化

`local-release.sh` 只上传已经在本地完整复验的 Bundle：

1. 创建 `/opt/inthub/incoming/<sha>-<operation>`；
2. 使用 rsync 上传完整 Bundle；
3. 服务器在未取得生产 lock 前先校验 remote script SHA 与完整 Bundle；
4. 校验成功后用原子 `mkdir` 获取 `/opt/inthub/.release-lock`；
5. 写入 Commit、Bundle ID、client host 和开始时间；
6. 使用 SSH keepalive 调用 Bundle 内已校验的 `remote-release.sh`；
7. 远端执行开始后若 SSH 中断，本机不擅自删除 lock，因为生产结果未知。

服务器不访问 GitHub、Registry 或依赖源，不运行 `git`、`pip`、`apt`、`docker build` 或
`docker pull`。它只从 Bundle 执行 `docker load`，并再次核对 config digest、平台与 labels。

推荐目录：

```text
/opt/inthub/
├── incoming/                 未信任上传目录
├── releases/<bundle-id>/     已验证、只读 Bundle
├── current -> releases/...   最后通过公网验收的 Release
├── shared/inthub.env         mode 0600，永不进入 Bundle
├── backups/<time>-<sha>/     env、manifest、Caddy、数据库 dump
└── .release-lock/            owner、metadata、phase state
```

## 数据库、候选槽和切流

生产 App 固定 `INTHUB_AUTO_MIGRATE=0`。迁移只能在发布流程中显式运行：

1. 已有 PostgreSQL volume 时要求数据库正在运行且 config digest 匹配 runtime lock；
2. 生成 custom-format `pg_dump`，要求非空，并用 `pg_restore --list` 验证；
3. 加载并复验镜像；
4. 启动或确认固定 PostgreSQL；
5. 用候选 App 镜像执行 `apps.inthub_api.migrate --require-backward-compatible`；
6. 仅允许 expand/contract 兼容迁移，旧 App 在候选和回滚窗口持续可用；
7. 不自动 downgrade 数据库。

App 使用 7250/7251 蓝绿槽。旧槽在候选 readiness、Caddy 切流、公网 smoke 和观察窗口结束
前保持运行。第一次公网 smoke 成功后才原子更新 `current`；默认观察 30 秒并再次执行公网
smoke，之后才停止旧槽。

## 失败与恢复

- 本地测试、Builder、构建、smoke 或 Bundle 校验失败：不上传、不接触生产。
- 上传中断：只影响唯一 incoming 目录，不产生 Release。
- 服务器预验证失败：不取得 lock，不加载镜像、不备份、不迁移。
- 候选未 ready：删除候选，旧槽继续服务。
- 切流、公网 smoke 或观察窗口失败：恢复旧 Caddy/current，删除候选并验证旧槽仍运行。
- 回滚不完整：保留 lock 和 phase state，后续发布 fail closed。
- SSH/进程中断：先只读检查 lock、state、Caddy、current 与容器，不能盲目重试迁移或切流。
- 自动清理不删除 Release、镜像、Secret、volume 或 backup；这些都需要独立授权。

同机 dump 是发布回滚材料，不是灾难恢复。Git 历史、完整 Bundle、Secret 恢复材料和数据库
备份仍需复制到自己控制的加密第二存储，并定期做 restore drill。

## 一次性前置条件

- 本机 Docker Desktop 已启动，`desktop-linux` 支持 Linux/amd64；
- 本机可以创建 Python venv，首次可访问固定依赖源或已有缓存；
- SSH alias 默认为 `agenthub-prod`，可显式设置 `INTHUB_DEPLOY_HOST`；
- 服务器已有 Docker Engine/Compose、Caddy、Python 3、gzip、curl、sha256sum；
- `/opt/inthub/shared/inthub.env` 已创建、非 symlink、mode `0600`；
- DNS、TLS 与 GitHub OAuth callback 已准备；
- 生产执行获得当前项目要求的明确授权。

工具安装、Secret 创建、备份清理、数据库维护和真实生产发布都不是构建基础设施时的隐式
动作。本规范只定义并验证入口，不替用户授权执行生产变更。
