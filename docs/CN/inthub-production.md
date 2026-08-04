# IntHub 官方生产部署规范

[中文](inthub-production.md) | [English](../EN/inthub-production.md)

## Metadata

- Status: reviewed
- Owner: project maintainers
- Last verified: 2026-08-04
- Runtime surface: deploy, ops, data, web, API
- Primary code anchors:
  - [deploy/inthub/compose.yaml](../../deploy/inthub/compose.yaml) - 定义独立 PostgreSQL、应用镜像、回环端口、健康检查和容器安全边界
  - [deploy/inthub/inthub.caddy](../../deploy/inthub/inthub.caddy) - 定义 `inthub.tenon.asia` 的独立公网入口
  - [deploy/inthub/inthub.env.example](../../deploy/inthub/inthub.env.example) - 定义生产配置键，不包含真实 Secret
  - [Dockerfile](../../Dockerfile) - 定义以 Git commit 构建的只读 IntHub 应用镜像
- Primary tests:
  - [tests/test_inthub_postgres.py](../../tests/test_inthub_postgres.py) - 守护 PostgreSQL schema、账户隔离和并发写入边界
  - [tests/test_inthub_auth.py](../../tests/test_inthub_auth.py) - 守护 GitHub OAuth、Web session 和账户 access token
  - [tests/test_inthub_api_server.py](../../tests/test_inthub_api_server.py) - 守护健康检查、认证和 HTTP API 契约
  - [tests/test_inthub_web_ui.py](../../tests/test_inthub_web_ui.py) - 守护登录入口和 Web 静态契约
- Related docs:
  - [CLI 使用说明](cli.md)
  - [IntHub UI/UX 改造计划](inthub-uiux-redesign.md)

## 简短结论

IntHub 官方生产环境只从 Gitee 部署仓库
[`https://gitee.com/dozybot/Intent.git`](https://gitee.com/dozybot/Intent) 的
`main` 拉取代码。Gitee `origin/main` 是发布来源和生产 provenance；GitHub
[`dozybot001/Intent`](https://github.com/dozybot001/Intent) 可以继续接收提交、运行
CI 或 Pages，但不得成为生产拉取源，也不得在 Gitee 不可用时自动降级为部署 fallback。

GitHub 在这里同时承担 OAuth identity provider，但 OAuth 身份来源与代码部署来源是两个
独立边界：保留 GitHub 登录不意味着服务器应从 GitHub 拉代码。

官方运行实例固定为：

| 项目 | 当前标准值 |
|---|---|
| 公网域名 | `https://inthub.tenon.asia` |
| 官方主机 | `ubuntu@122.51.14.35` |
| 本机 SSH alias | `agenthub-prod`（仅为操作者便利，不属于服务配置） |
| 生产根目录 | `/opt/inthub` |
| 回环监听 | `127.0.0.1:7250` |
| Compose project | `inthub` |
| App container | `inthub-app` |
| PostgreSQL container | `inthub-postgres` |
| PostgreSQL volume | `inthub-postgres-data` |
| Caddy site | `/etc/caddy/sites-enabled/inthub.caddy` |
| 部署仓库 | `https://gitee.com/dozybot/Intent.git` |

## 心智模型

```text
开发机
  ├─ origin/main  → Gitee dozybot/Intent       ← 唯一生产来源
  └─ github/main  → GitHub dozybot001/Intent   ← 可选协作、CI、Pages

生产发布
  Gitee main 的已解析 commit
    → /opt/inthub/releases/<git-sha>
    → Docker image inthub:<git-sha>
    → /opt/inthub/current 原子切换
    → Compose project inthub

公网请求
  Internet
    → Caddy :443
    → 127.0.0.1:7250
    → inthub-app :8000
    → inthub-postgres :5432（仅 Docker private network）
```

代码托管、生产运行和用户身份不得混为一个权限边界：

- Gitee 仓库证明“生产部署的是哪个 commit”。
- GitHub App 只为普通用户提供 OAuth 身份确认，不读取用户仓库。
- IntHub 账户、Web session、CLI access token 和项目数据由 IntHub 自己的 PostgreSQL
  保存并授权。
- AgentHub 只提供服务器与运维背景；IntHub 不复用 AgentHub 的目录、容器、数据库、
  Secret、Gateway 凭据或部署接口。

## 来源与 remote 规范

开发 clone 必须使用以下 remote 心智：

```text
origin  https://gitee.com/dozybot/Intent.git
github  https://github.com/dozybot001/Intent.git
```

不变量：

1. `origin/main` 是唯一 production source of truth。
2. 每次部署前，目标 commit 必须已经存在于 Gitee `main`，并由服务器直接通过 Gitee
   解析和拉取。
3. GitHub push 是允许但可选的分发动作；GitHub Actions 结果可以作为额外质量证据，
   不能替代本地检查或 Gitee commit provenance。
4. 发布脚本不得包含 GitHub archive、GitHub clone、GitHub raw URL 或“Gitee 失败后改拉
   GitHub”的逻辑。
5. Gitee 不可用时，正确行为是停止发布并保留当前健康 release，而不是从其他来源继续。
6. 禁止通过 SCP、未提交工作树、临时压缩包或服务器现场修改生成 production release。

标准推送顺序：

```bash
git status --short
git push origin main

# 可选：保持 GitHub 协作面更新，但它不参与生产部署判定。
git push github main
```

若需要发布 tag，应先推 Gitee，再选择是否推 GitHub：

```bash
git push origin --tags
git push github --tags
```

## 官方服务器目录和权限

```text
/opt/inthub/
  current -> /opt/inthub/releases/<git-sha>
  releases/
    <git-sha>/
  shared/
    inthub.env              # 0600
  backups/
    <UTC timestamp>/
      inthub.dump           # PostgreSQL custom-format dump
      inthub.env            # 0600
```

- 每个 release 都是不可变目录，以完整 Git SHA 命名。
- `/opt/inthub/current` 只通过同一文件系统上的临时 symlink + atomic rename 切换。
- 创建和更新 release 不得覆盖已有目录；同一 SHA 已存在时先验证内容和构建 marker。
- `/opt/inthub/shared/inthub.env` 属于部署操作者，权限必须保持 `0600`。
- PostgreSQL 不映射主机端口；应用只绑定 `127.0.0.1:7250`。
- Caddy 只加载 IntHub 自己的 site 文件，不覆盖共享根 Caddyfile 或其他服务片段。

## 配置与认证

生产使用 PostgreSQL；本地 `itt hub start` 继续使用只绑定回环地址的 SQLite 无认证模式。
PostgreSQL 提供并发写入、备份恢复和未来团队协作需要的数据边界，但不替代应用授权。

生产只有一条账户路径：

- 浏览器：GitHub OAuth + PKCE + 一次性 state。
- Web session：随机 HttpOnly、SameSite=Strict Cookie；数据库只保存 session hash。
- CLI：账户签发 `ith_pat_...` access token；数据库只保存 token hash、名称、有效期、
  last-used 和撤销状态。
- 数据：Project、Workspace、Intent、Snap、Decision 和同步历史均按 `account_id` 隔离。

GitHub App 每个部署只配置一次：

- Homepage URL：`https://inthub.tenon.asia`
- Callback URL：`https://inthub.tenon.asia/api/v1/auth/github/callback`
- Webhook：关闭
- Repository permissions：无
- Organization / account permissions：无
- Installation scope：`Any account`

真实配置只写入 `/opt/inthub/shared/inthub.env`，不得写入 Git、聊天或诊断输出。至少包括：

```text
INTHUB_DOMAIN=inthub.tenon.asia
INTHUB_BIND_PORT=7250
INTHUB_RELEASE=<full-gitee-git-sha>
INTHUB_PACKAGE_VERSION=<version-derived-from-the-clean-release>
INTHUB_GITHUB_CLIENT_ID=<configured-client-id>
INTHUB_GITHUB_CLIENT_SECRET=<configured-client-secret>
INTHUB_POSTGRES_PASSWORD=<url-safe-random-password>
```

完整键集合以 [inthub.env.example](../../deploy/inthub/inthub.env.example) 为准。

## 标准发布流程

### 1. 本地发布资格

发布操作者必须先确认：

```bash
git status --short
git branch --show-current
git rev-parse HEAD
pytest -q
git diff --check
```

要求：工作树干净、分支为 `main`、测试通过。随后先推送 Gitee：

```bash
git push origin main
git ls-remote origin refs/heads/main
```

`git rev-parse HEAD` 必须与 Gitee 返回的 `refs/heads/main` SHA 完全一致。GitHub push
可以在此之前或之后执行，但不改变部署资格。

### 2. 生产预检

只读确认当前 release、配置权限、容器健康和磁盘空间：

```bash
ssh agenthub-prod 'readlink -f /opt/inthub/current'
ssh agenthub-prod 'stat -c "%a %U:%G %n" /opt/inthub/shared/inthub.env'
ssh agenthub-prod 'sudo docker ps --filter name=inthub --format "{{.Names}} {{.Image}} {{.Status}}"'
ssh agenthub-prod 'df -h /opt/inthub'
```

不得输出完整 env、数据库 URL、OAuth Secret、Cookie 或 access token。

### 3. 从 Gitee 解析并拉取 release

服务器使用公开只读 HTTPS 地址，不保存写凭据：

```bash
SOURCE_REPOSITORY=https://gitee.com/dozybot/Intent.git
RELEASE_SHA=$(git ls-remote "$SOURCE_REPOSITORY" refs/heads/main | awk '{print $1}')
RELEASE_DIRECTORY=/opt/inthub/releases/$RELEASE_SHA
STAGING_DIRECTORY=$(mktemp -d /opt/inthub/releases/.staging.XXXXXX)

git clone --branch main --single-branch --no-tags "$SOURCE_REPOSITORY" "$STAGING_DIRECTORY"
test "$(git -C "$STAGING_DIRECTORY" rev-parse HEAD)" = "$RELEASE_SHA"
test ! -e "$RELEASE_DIRECTORY"
mv "$STAGING_DIRECTORY" "$RELEASE_DIRECTORY"
```

发布 provenance 以 `git ls-remote` 与 clone 后的 `HEAD` 双重一致为准。不得从 GitHub
下载 tarball 补足或替换失败的 Gitee 拉取。

### 4. 发布前备份

每次发布都必须同时备份 PostgreSQL 与当前 env：

```bash
BACKUP_TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIRECTORY=/opt/inthub/backups/$BACKUP_TIMESTAMP
mkdir -p "$BACKUP_DIRECTORY"

sudo docker exec inthub-postgres sh -c \
  'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --format=custom' \
  > "$BACKUP_DIRECTORY/inthub.dump"
cp /opt/inthub/shared/inthub.env "$BACKUP_DIRECTORY/inthub.env"
chmod 600 "$BACKUP_DIRECTORY/inthub.dump" "$BACKUP_DIRECTORY/inthub.env"
test -s "$BACKUP_DIRECTORY/inthub.dump"
```

备份完成前不得构建或切换 release。

### 5. 构建不可变镜像

镜像 tag 使用完整 Gitee commit：

```bash
sudo docker build \
  --build-arg INTHUB_VERSION="$INTHUB_PACKAGE_VERSION" \
  --tag "inthub:$RELEASE_SHA" \
  --file "$RELEASE_DIRECTORY/Dockerfile" \
  "$RELEASE_DIRECTORY"

sudo docker image inspect \
  --format '{{index .Config.Labels "org.opencontainers.image.version"}}' \
  "inthub:$RELEASE_SHA"
```

构建失败不得修改 `/opt/inthub/current` 或共享 env。

### 6. 原子激活与自动回滚

激活步骤必须作为一个有回滚分支的操作完成：

1. 保存旧 `current` target 和旧 env 副本。
2. 生成新的 env candidate，只更新 `INTHUB_RELEASE` 与 `INTHUB_PACKAGE_VERSION`。
3. 原子替换 env，并将 `current` 原子切到新 release。
4. 使用新 release 的 Compose 文件执行：

```bash
sudo docker compose \
  --project-name inthub \
  --env-file /opt/inthub/shared/inthub.env \
  --file /opt/inthub/current/deploy/inthub/compose.yaml \
  up --detach --no-build --remove-orphans
```

5. 在有界时间内同时等待 `inthub-app` container health 为 `healthy`，且
   `http://127.0.0.1:7250/readyz` 成功。
6. 任一步失败时，先恢复旧 env 与旧 `current`，再以旧 Compose 配置重新执行
   `up --detach --no-build --remove-orphans`。

应用回滚不会自动回滚数据。若 release 包含不兼容 schema 变化，必须恢复对应数据库
备份，不能只切换代码。

### 7. 发布后验证

服务器内和公网都必须验证：

```bash
curl --fail --silent --show-error http://127.0.0.1:7250/healthz
curl --fail --silent --show-error http://127.0.0.1:7250/readyz
curl --fail --silent --show-error https://inthub.tenon.asia/healthz
curl --fail --silent --show-error https://inthub.tenon.asia/readyz

# 匿名项目读取必须为 401。
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  https://inthub.tenon.asia/api/v1/projects

# GitHub 登录入口必须开始 OAuth redirect。
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  https://inthub.tenon.asia/api/v1/auth/github/start
```

还需验证：

- `/opt/inthub/current` 指向预期完整 Gitee SHA；
- `INTHUB_RELEASE` 与 image tag 一致；
- `INTHUB_PACKAGE_VERSION` 与 image label 一致；
- `inthub-app` 和 `inthub-postgres` 都为 healthy；
- 新静态资源 revision 可从公网读取；
- GitHub OAuth 返回 `302`，匿名受保护 API 返回 `401`。

## Caddy 和 DNS

DNS 固定为 `inthub.tenon.asia A 122.51.14.35`。Caddy 只安装 IntHub 独立 site：

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
```

只有 [inthub.caddy](../../deploy/inthub/inthub.caddy) 发生变化时才需要 reload。普通应用
release 不重载 Caddy。

## 运行态排查

只使用有界、不会暴露 Secret 的诊断：

```bash
sudo docker compose --project-name inthub \
  --env-file /opt/inthub/shared/inthub.env \
  --file /opt/inthub/current/deploy/inthub/compose.yaml ps
sudo docker logs --tail 200 inthub-app
sudo docker logs --tail 200 inthub-postgres
git ls-remote https://gitee.com/dozybot/Intent.git refs/heads/main
```

判断顺序：

1. Gitee `main` 是否仍解析到预期 SHA；
2. `current`、env release、container image 是否为同一 SHA；
3. 容器 health 与 loopback `/readyz` 是否通过；
4. Caddy 与公网入口是否正常；
5. 匿名鉴权边界是否仍为 `401`。

## 不变量

- 生产代码只来自 Gitee，不自动 fallback 到 GitHub。
- Gitee 不可用不会影响当前运行实例，只会阻止新发布。
- PostgreSQL 和应用不暴露公网端口。
- 浏览器 session 默认只读；CLI 写入只接受账户 access token。
- GitHub OAuth token 不持久化，GitHub App owner 不获得额外 IntHub 数据权限。
- 每个 release 先备份、后构建、再切换；新 release 未健康时必须恢复旧 release。
- 不复用其他服务的容器、数据库、Secret、目录、Caddy site 或运行凭据。
- 任何日志、命令输出和文档都不得包含账户 token、GitHub Client Secret、数据库密码
  或 Cookie。

## 未决问题

- 当前发布动作仍由项目 Session 按本规范执行，尚未收敛为仓库内单一 deployment
  command；未来脚本必须把 Gitee-only provenance、备份和自动回滚做成硬校验。
- GitHub 与 Gitee 的同步目前是显式双推，不是服务端镜像；如果以后自动化，只允许
  Gitee 作为部署 authority，不能让 GitHub workflow 直接触发生产拉取。
- 发布保留策略和旧 Docker image 清理策略尚未自动化；清理前必须保留至少一个已验证
  可回滚 release 及其数据库/env 备份。
