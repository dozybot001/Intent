# IntHub 官方生产部署规范

[中文](inthub-production.md) | [English](../EN/inthub-production.md)

## Metadata

- Status: implemented
- Owner: project maintainers
- Last verified: 2026-08-04
- Runtime surface: build, package, deploy, ops, data, web, API
- 正式入口：[deploy/inthub/release.sh](../../deploy/inthub/release.sh)
- 内部实现：
  - [build-release.sh](../../deploy/inthub/build-release.sh) - 从 clean Commit 构建并验证 release bundle
  - [release_manifest.py](../../deploy/inthub/release_manifest.py) - 生成并严格校验 manifest 与 checksum
  - [remote-release.sh](../../deploy/inthub/remote-release.sh) - 服务器校验、备份、加载、验收和回滚
  - [runtime-images.lock.json](../../deploy/inthub/runtime-images.lock.json) - 锁定数据库 runtime identity
  - [smoke.sh](../../deploy/inthub/smoke.sh) - 内部与公网验收
  - [compose.yaml](../../deploy/inthub/compose.yaml) - 只允许启动已经加载的镜像
  - [inthub.caddy](../../deploy/inthub/inthub.caddy) - IntHub 独立公网入口

## 结论

IntHub 生产发布使用下面的固定闭环：

```text
本地 clean main Commit
  → 从 Git object 导出 commit-exact source context
  → 本机共享 linux/amd64 Builder 构建镜像
  → 对同一镜像做本地 smoke
  → source archive + image archive + manifest + SHA-256
  → SSH 上传 /opt/inthub/incoming
  → 取得 /opt/inthub/.release-lock
  → 服务器校验并 docker load，禁止 clone、build、pull
  → PostgreSQL/env 备份
  → --no-build --pull never 启动非活动 App slot
  → 候选 slot 内部 ready，旧 slot 继续服务
  → Caddy 切流 + 公网 smoke
  → 原子切换 /opt/inthub/current，停止旧 slot
  → 失败时把流量切回仍在运行的旧 slot，不自动降级数据库
```

唯一支持的生产命令是：

```bash
bash deploy/inthub/release.sh
```

`build-release.sh` 可以单独生成无生产影响的 bundle；`remote-release.sh` 是内部步骤，
必须持有由正式入口创建的项目发布锁，不能作为常规生产入口直接调用。

## Git 和远端边界

本项目默认只维护一个远端：

```text
origin  https://github.com/dozybot001/Intent.git
```

GitHub 是异步备份、协作、CI 和 Pages 平面，不是构建或部署依赖：

- 发布版本由本机完整 Git SHA 标识，不由分支名或远端状态标识；
- 发布要求本地 `main`、clean worktree 和通过的检查，不要求先 push；
- GitHub 不可用时可以继续发布本地 clean Commit；
- manifest 默认记录 `github_sync: pending`；明确确认已同步时可设置
  `INTHUB_GITHUB_SYNC_STATUS=confirmed`；
- 未同步 Commit 的 bundle 始终带有 commit-exact source archive；
- 生产服务器不得执行 `git clone`、`git pull`、`git fetch` 或访问 GitHub；
- 发布脚本不得临时改写 remote，也不得增加 Gitee 或自动 fallback 镜像。

GitHub 同步是独立动作，例如：

```bash
git push origin main
```

它不是 `release.sh` 的隐藏步骤，也不授权生产发布。

## 官方运行边界

| 项目 | 标准值 |
|---|---|
| 公网域名 | `https://inthub.tenon.asia` |
| 本机 SSH alias | `agenthub-prod` |
| 生产根目录 | `/opt/inthub` |
| 回环 slot | `127.0.0.1:7250`（blue）、`127.0.0.1:7251`（green） |
| 目标平台 | `linux/amd64` |
| 共享 Builder | `shared-linux-amd64` |
| Compose project | `inthub` |
| App container | `inthub-app-blue` / `inthub-app-green`；首次迁移兼容旧 `inthub-app` |
| PostgreSQL container | `inthub-postgres` |
| PostgreSQL volume | `inthub-postgres-data` |
| Caddy site | `/etc/caddy/sites-enabled/inthub.caddy` |

PostgreSQL 不发布主机端口，应用只绑定回环地址。IntHub 不复用其他项目的容器、
数据库、Secret、目录、发布锁、Caddy site 或部署凭据。

## 共享 Builder

IntHub 使用机器级、按目标平台划分的 Builder，不创建项目专属 Builder。默认名称为
`shared-linux-amd64`，可通过 `INTHUB_BUILDER` 显式覆盖为另一套可信的
Linux/amd64 Builder。

首次使用时，可在发布之外完成机器级 bootstrap：

```bash
docker buildx create \
  --name shared-linux-amd64 \
  --driver docker-container \
  --platform linux/amd64
docker buildx inspect shared-linux-amd64 --bootstrap
```

Builder 只接收从指定 Commit 导出的 tracked source context，不接收生产 env、
PostgreSQL 数据、OAuth Secret、CLI token 或 SSH 私钥。依赖缓存建立和刷新发生在
取得生产发布锁之前；服务器不会在 Builder 缺失时进行现场 build。

## Release bundle

`build-release.sh` 在 `dist/inthub/<full-sha>/` 生成不可覆盖的 bundle。`dist/` 已由
Git 忽略。bundle 的精确文件集是：

```text
source.tar.gz          commit-exact tracked source archive
images.tar.gz          linux/amd64 IntHub 与 PostgreSQL image archive
manifest.json          provenance、平台、镜像 ID、配方和检查结果
SHA256SUMS             bundle 精确文件集的 SHA-256
compose.yaml           生产 Compose 配置；没有 build，pull_policy=never
inthub.caddy           项目独立公网入口
release_manifest.py    服务器侧标准库校验器
remote-release.sh      受发布锁保护的内部激活步骤
runtime-images.lock.json  PostgreSQL reference、pull digest、image ID 与平台锁
smoke.sh               匿名内部与公网验收
```

Manifest 至少证明：

- schema version、project ID、完整 Git SHA、`dirty: false`；
- `github_sync: pending|confirmed`，仅供审计；
- target `linux/amd64`；
- source/image archive 的文件名、字节数和 SHA-256；
- App 与 PostgreSQL 镜像 reference、image ID、平台和可用 RepoDigest；
- PostgreSQL manifest 必须与 `runtime-images.lock.json` 完全一致；普通 App release
  不允许隐式升级数据库 runtime；
- App OCI revision/version/source label；
- Dockerfile 与 `pyproject.toml` 的 SHA-256；
- Builder 名称、driver、Buildx 版本和构建时间；
- `pytest`、`git diff --check` 和同一生产镜像本地 smoke 均已通过。

校验器拒绝未知字段、额外文件、缺失文件、symlink、非普通文件、错误类型、截断 JSON、
路径逃逸、大小不符、checksum 不符、平台不符和 revision/version 不符。服务器在这些
校验完成前不会加载镜像或修改运行服务。

## 本地发布资格

正式入口在任何 SSH 上传前完成：

1. 确认 worktree（包括 untracked files）为空；
2. 确认当前分支为 `main`；
3. 运行完整 `pytest -q`；
4. 运行 `git diff --check`；
5. 从 Commit 导出 source archive 和独立构建上下文；
6. 对 commit-exact context 执行高置信度凭证扫描；
7. 用共享 Builder 构建 `inthub:<full-sha>` 的 Linux/amd64 镜像；
8. 确认 PostgreSQL runtime image 的 ID、不可变 pull digest 和 Linux/amd64 平台
   与项目 lock 完全一致；
9. 以 read-only、capability-free、`no-new-privileges` 边界启动同一 App image，
   验证 `/healthz` 与 `/readyz`；
10. 打包两个镜像并生成、复验 manifest 与 SHA256SUMS。

已有同 SHA bundle 时不会覆盖；只有完整复验通过才允许复用。

## 服务器目录与 Secret

```text
/opt/inthub/
├── incoming/<sha>-<operation>/
├── releases/<full-sha>/
├── current -> releases/<full-sha>
├── shared/inthub.env              # 0600
├── backups/<timestamp>-<sha>/
│   ├── inthub.dump                # 0600，存在数据库时生成
│   ├── inthub.env                 # 0600
│   ├── release-manifest.json      # 0600
│   └── inthub.caddy               # 仅入口变化时保存
└── .release-lock/
    ├── owner
    └── metadata
```

真实配置只存在 `/opt/inthub/shared/inthub.env`，权限必须为 `0600`。至少包括域名、
PostgreSQL 密码、GitHub App client ID/secret、session TTL 和限制参数。release SHA、
package version、App container 与 blue/green 端口不再由操作者维护；激活脚本从已验证
manifest 和受限 slot 集合注入，避免共享 Secret 文件与 release/traffic 状态漂移。

Secret、数据库 dump、用户数据、access token 和 Cookie 不得进入 Git、Builder、
构建上下文、镜像层、bundle、manifest、日志或 Memory。

## 远端发布顺序

`release.sh` 只通过 SSH/rsync 传输 bundle，并执行以下受限流程：

1. 创建项目专属 incoming、releases、backups 和 shared 目录；
2. 上传到唯一 operation 目录；
3. 校验上传后的 `remote-release.sh` 与本地 SHA-256 一致；
4. 通过原子 `mkdir` 获取 fail-closed `/opt/inthub/.release-lock`；
5. 再次验证 bundle 精确文件集、manifest 和所有 checksum；
6. 将新 bundle 原子提升为不可写的 `releases/<full-sha>`；同 SHA 只允许内容完全一致；
7. 备份 mode-0600 env；已有 PostgreSQL volume 时，要求运行中的数据库生成
   custom-format dump，并用 `pg_restore --list` 复验；
8. 已有数据库时先确认运行中的 PostgreSQL image ID 与 runtime lock 一致；不一致
   必须走独立数据库维护流程；
9. 从 `images.tar.gz` 执行 `docker load`，校验 image ID、平台和 OCI label；
10. 保持当前 App slot 与 Caddy 不变，在非活动 7250/7251 slot 运行
    `docker compose ... up --no-deps --no-build --pull never`；
11. 等待候选 App、PostgreSQL health 和候选 loopback `/readyz`；
12. 渲染候选端口的 Caddy site，备份旧 site，验证根配置后 reload 切流；
13. 对候选 loopback 与正式域名执行 smoke；此时旧 slot 仍保持运行；
14. 全部通过后用同文件系统 symlink rename 原子切换 `current`；
15. 验证 `current` 与正在服务的 slot image 是同一 SHA，再停止旧 slot 并释放锁。

SSH 使用 keepalive。远端执行开始后，如果连接中断，本地不会擅自移除锁，因为生产
完成状态未知；操作者必须先只读检查 `current`、容器和 `.release-lock/metadata`。

## 验收内容

内部和公网都必须满足：

- `/healthz` 与 `/readyz` 返回成功；
- 匿名 `/api/v1/projects` 返回 `401`；
- GitHub OAuth start 返回 `302` 或 `303`；
- `TRACE` 返回 `405`；
- 首页包含要求的 CSP；
- 当前 `inthub-app-blue` 或 `inthub-app-green` 与 `inthub-postgres` 都为 healthy；
- PostgreSQL 没有主机端口；
- App image revision/version 与 manifest 一致；
- `current` 最终指向预期完整 SHA。

自动化不能替用户宣称 GitHub 登录后的真实业务流程或 UI 视觉已经验收。UI 改动发布后
仍需把公网 URL 交给用户检查。

## 回滚和数据库边界

- 候选 health、Caddy 或公网 smoke 任一步失败时，恢复旧 Caddy 并删除候选 slot；
  旧 slot 在整个验收期没有停止，因此回滚不依赖重新拉起旧应用；
- 第一次发布失败时停止未通过的 App，不删除 PostgreSQL volume；
- 应用回滚绝不自动执行数据库 downgrade；
- schema 变化必须使用 expand/contract，保证上一应用在回滚窗口内仍兼容；
- rollback 不删除 release、镜像、Secret、backup 或 volume；
- 同机 mode-0600 dump 只提供发布回滚证据，不等于灾难恢复；关键数据仍需异地加密
  副本、保留策略和恢复演练；
- release、镜像和 backup 清理是独立、明确授权的操作。

## Caddy 与首次接入

DNS 指向生产主机后，正式入口可以安装或更新 IntHub 自己的 Caddy site；它不会覆盖
共享根 Caddyfile 或其他项目 site。变更前保存旧文件，`caddy validate` 失败或公网
smoke 失败会恢复旧 site。

新主机首次接入前需要由操作者在发布之外完成：

1. 本机安装 Docker CLI、Buildx 与可用 Engine；服务器安装 Docker
   Engine/Compose、Caddy、Gzip、Python 3、rsync 和 SHA-256 工具；
2. 配置 SSH 与项目目录 sudo 权限；
3. 创建 mode-`0600` 的 `/opt/inthub/shared/inthub.env`；
4. 建立机器级 `shared-linux-amd64` Builder；
5. 确认 DNS 与 GitHub App callback；
6. 取得当次生产发布授权后运行唯一正式入口。

安装工具和配置 Secret 不应隐含在普通应用 release 中。
