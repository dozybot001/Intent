# IntHub 官方生产部署规范

[中文](inthub-production.md) | [English](../EN/inthub-production.md)

## Metadata

- Status: implemented; production execution requires explicit authorization
- Owner: project maintainers
- Last verified: 2026-08-24
- Runtime surface: local Git, Gitee, isolated server Builder, Bundle, data, ingress
- 唯一正式入口：[release.sh](../../deploy/inthub/release.sh)
- 本地资格门禁：[qualify-release.sh](../../deploy/inthub/qualify-release.sh)
- 服务器构建入口：[release-from-gitee.sh](../../deploy/inthub/release-from-gitee.sh)
- Bundle 构建器：[build-release.sh](../../deploy/inthub/build-release.sh)
- 生产激活器：[remote-release.sh](../../deploy/inthub/remote-release.sh)
- Manifest：[release_manifest.py](../../deploy/inthub/release_manifest.py)

## 唯一标准路径

IntHub 生产发布只接受 Gitee `main` 上已经回读确认的完整 Commit。GitHub 可以异步接收
同一历史，但不参与发布身份、构建、门禁、回滚或灾备判定。

```text
本地 clean main Commit
  → 固定 PostgreSQL 集成测试、diff/check、Commit 精确源码扫描
  → fast-forward 推送 Gitee main 并回读完整 SHA
  → 服务器再次回读同一个 Gitee SHA
  → /opt/inthub/builder/source 专用 checkout
  → 服务器固定 linux/amd64 Builder 再跑门禁并只构建一次
  → 最终镜像本机 smoke
  → source + images + Manifest v4 + SHA256SUMS
  → 原子固化只读 Bundle
  → Bundle 预验证后取得 fail-closed production lock
  → PostgreSQL/env 备份、显式兼容迁移
  → 非活动 slot → readiness → 可逆切流 → 公网 smoke
  → 更新 current → 观察窗口 → 再次公网 smoke → 停止旧 slot
```

日常只有一个生产命令：

```bash
bash deploy/inthub/release.sh
```

不支持本地镜像 Bundle 上传、服务器运行目录 `git pull`、GitHub fallback、外部 Registry、
可变 tag 部署或服务器现场修改。Gitee 不可用、SHA 不一致、Builder/依赖不可用时，发布
失败关闭，当前健康版本继续服务。

## 固定生产边界

| 项目 | 标准值 |
|---|---|
| 公网域名 | `https://inthub.tenon.asia` |
| 生产主机 | `ubuntu@122.51.14.35` |
| 本机 SSH alias | `agenthub-prod` |
| 本机 Gitee 写入 alias | `inthub-gitee` |
| Gitee 生产源码 | `https://gitee.com/dozybot/Intent.git` |
| Gitee 发布 ref | `refs/heads/main` |
| GitHub 异步镜像 | `https://github.com/dozybot001/Intent.git` |
| 生产根目录 | `/opt/inthub` |
| App 蓝绿端口 | `127.0.0.1:7250` / `127.0.0.1:7251` |
| Compose projects | `inthub`、`inthub-blue`、`inthub-green` |
| PostgreSQL | `inthub-postgres`，仅 `inthub-private` 网络 |
| Caddy site | `/etc/caddy/sites-enabled/inthub.caddy` |
| 目标平台 | `linux/amd64` |
| 服务器 Builder | `default`，driver=`docker` |

建议开发 clone 使用：

```text
origin  https://gitee.com/dozybot/Intent.git
github  https://github.com/dozybot001/Intent.git
```

发布脚本使用固定 Gitee 读写地址，不依赖 remote 名称；其中公开 HTTPS 地址负责回读，
`git@inthub-gitee:dozybot/Intent.git` 只负责 fast-forward 写入。该 remote 布局用于保持人的正常心智。
GitHub push 必须在发布之外单独执行，失败不能改变已经完成的生产结果。

发布机需要一次性创建独立的 Gitee 账户 SSH 公钥，并将本机 alias 固定到该私钥：

```sshconfig
Host inthub-gitee
  HostName gitee.com
  User git
  IdentityFile /absolute/path/to/inthub_gitee_push_ed25519
  IdentitiesOnly yes
```

仓库部署公钥在 Gitee 上是只读的，不能完成发布入口所需的 fast-forward push；因此这里使用
可独立撤销的账户公钥。私钥只留在发布机，不进入仓库、服务器或 Bundle。

## 一次性控制面初始化

服务器需要先安装稳定的 Gitee launcher。初始化只传输很小的控制面脚本，不传输源码、
镜像、Secret 或数据库，也不会 build、迁移、重启或切流：

```bash
bash deploy/inthub/bootstrap-gitee-deployment.sh
```

初始化会创建并核对项目专属目录、`inthub.env` 的 `0600` 权限、Docker/Buildx 和 Gitee
只读访问，并确认主机 Python 能通过 `python3-venv` 创建隔离环境，再以 SHA-256 验证后安装：

```text
/opt/inthub/deploy/release-from-gitee.sh
```

Ubuntu Builder 的一次性系统依赖为：

```bash
sudo apt-get install python3-venv
```

bootstrap 只验证该依赖，不自行修改系统软件包。

正式发布每次都会比较本地与服务器 launcher SHA。二者不一致时只会要求重新执行显式
bootstrap，不会偷偷更新生产控制面。

## 本地发布门禁与 Gitee 发布

`release.sh` 首先运行 `qualify-release.sh`：

1. 要求完整、clean 的 `main` Commit，拒绝 submodule、LFS 和 shallow history；
2. 校验固定 PostgreSQL runtime config digest 与 `linux/amd64` 平台；
3. 使用固定 pytest/psycopg 环境运行完整测试和真实 PostgreSQL 集成测试；
4. 执行 `git diff --check`、Commit object 检查；
5. 用 `git archive` 导出精确 Commit，并扫描高置信度凭据和不安全文件项；
6. 再次确认门禁期间 HEAD 和 worktree 未变化。

门禁通过后，脚本要求现有 Gitee `main` 是目标 Commit 的祖先，只允许 fast-forward 推送：

```text
<full-sha>:refs/heads/main
```

推送后必须用 `git ls-remote` 回读为相同完整 SHA，才会联系生产 launcher。Gitee 的分支名
只用于运输；Release 身份始终是完整 Commit、Bundle ID、镜像 config digest 和 Manifest。

## 服务器隔离构建

服务器 launcher 使用 `/opt/inthub/.build-lock` 阻止并发构建，并再次回读 Gitee `main`。
只有它与请求 SHA 完全一致时才会在专用 checkout 中执行：

```text
/opt/inthub/builder/
├── source/          Gitee 专用完整 Git checkout
├── tools/           固定 Python 门禁环境缓存
└── qualification/   临时精确源码扫描目录
```

launcher 会 clean 专用 checkout、fetch `main` 和 tags、检出精确 Commit，再用服务器
`default` linux/amd64 Builder 运行 `build-release.sh`。构建脚本再次执行同一门禁，只构建一次
App 镜像，对最终镜像做 read-only/cap-drop/no-new-privileges smoke，并生成不可覆盖 Bundle。
运行目录、`current`、Secret、数据库和 Caddy 都不参与构建。

## Bundle 与 Manifest v4

Bundle 固定包含：

```text
source.tar.gz
images.tar.gz
manifest.json
SHA256SUMS
compose.yaml
inthub.caddy
release_manifest.py
remote-release.sh
runtime-images.lock.json
smoke.sh
```

Manifest v4 在既有 Commit、平台、Builder、依赖、数据库、镜像、测试与 checksum 证据之外，
强制记录：

```json
{
  "source": {
    "transport": "gitee-exact-commit",
    "repository": "https://gitee.com/dozybot/Intent.git",
    "ref": "refs/heads/main",
    "commit": "<full-sha>"
  }
}
```

App OCI source label 同样固定为 `https://gitee.com/dozybot/Intent`。未知字段、额外文件、
symlink、路径逃逸、大小/checksum/平台/config digest/recipe/source 漂移都会失败关闭。

## 生产固化、数据库与蓝绿切流

服务器构建完成后，Bundle 内的 `remote-release.sh` 先完整验证 Bundle，再原子取得
`/opt/inthub/.release-lock`。这意味着测试或构建失败不会取得生产锁，也不会备份、迁移、
启动候选或改变流量。

生产阶段保持原有契约：

1. 原子移动到只读 `/opt/inthub/releases/<full-sha>` 并再次验证；
2. 生成非空 PostgreSQL custom-format dump，使用 `pg_restore --list` 验证，并备份 env/Manifest；
3. `INTHUB_AUTO_MIGRATE=0`，只显式执行 backward-compatible expand/contract 迁移；
4. 从 Bundle `docker load`，核对 config digest、平台、revision/version/schema labels；
5. 旧槽持续服务，候选只在非活动 7250/7251 槽启动；
6. readiness 通过后校验并 reload Caddy；
7. 公网 smoke 通过后才更新 `current`；观察窗口和第二次公网 smoke 通过后才停止旧槽。

App 回滚不自动 downgrade 数据库。若候选、切流或公网 smoke 失败，恢复旧 Caddy/current，
验证旧槽后删除候选；回滚不完整时保留生产锁与 phase state，后续发布 fail closed。

## 目录与中断恢复

```text
/opt/inthub/
├── deploy/                    稳定 Gitee server launcher
├── builder/                   专用 checkout、工具和缓存
├── incoming/                  尚未受信任的服务器构建 Bundle
├── releases/<full-sha>/       已验证只读 Release
├── current -> releases/...    最后通过公网验收的 Release
├── shared/inthub.env          0600，永不进入 Git/Bundle/镜像
├── backups/<time>-<sha>/      env、Manifest、Caddy、数据库 dump
├── logs/                      发布审计
├── .build-lock/               服务器构建 owner/metadata
└── .release-lock/             生产 owner/metadata/phase state
```

- 本地门禁或 Gitee push 失败：不接触生产。
- Gitee 回读或服务器构建失败：不取得生产锁，旧服务不变。
- SSH 中断：先检查 build/release lock、phase、Caddy、容器和 `current`，不得盲目重跑。
- 生产回滚失败：保留 lock，人工从明确 phase 恢复；不得强删锁后重试。
- Release、镜像、Builder cache、备份和数据的清理都需要独立授权。

同机 dump 不是灾难恢复。源码、Gitee/GitHub 之外的 Git 备份、完整 Release、Secret 恢复
材料和数据库备份仍需复制到自己控制的加密第二存储，并定期演练恢复。
