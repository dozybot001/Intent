# IntHub 生产部署

[中文](inthub-production.md) | [English](../EN/inthub-production.md)

IntHub 生产部署面向私有语义历史展示。浏览器通过 GitHub OAuth 登录，IntHub 在 PostgreSQL 中建立可撤销的账户会话，并用 HttpOnly、SameSite=Strict Cookie 读取 API；GitHub Access Token 只用于当次身份校验，不会持久化。`itt hub link` 和 `itt hub sync` 等写入操作仍使用独立的部署级 Bearer Token。

当前是账户系统的单所有者阶段，不是完整多租户：生产配置只应允许一个稳定的 GitHub numeric user ID，所有项目仍属于当前部署的共享数据域。数据库已经包含 `accounts`、OAuth 登录尝试和 Web 会话，但项目所有权、账户级 PAT 与按账户过滤查询留待多账号阶段实现。

## 数据库选择

生产环境使用 PostgreSQL，本地 `itt hub start` 继续使用 SQLite。原因不是当前单用户流量需要 PostgreSQL，而是同步写入、备份恢复、并发连接和未来迁移到多账号时，PostgreSQL 提供了更合适的长期边界。两种后端共用同一查询层和显式 `sequence_id`，CI 会同时验证 SQLite 与 PostgreSQL。

PostgreSQL 本身并不等于多租户。正式多账号仍需增加项目所有权、按账号限定的唯一键和查询、账户级访问令牌、授权策略、配额与数据迁移；当前 GitHub allowlist 只解决浏览器身份，不应被描述为项目级权限模型。

## 生产拓扑

```text
Internet
  → Caddy :443
  → 127.0.0.1:7250
  → inthub-app :8000
  → inthub-postgres :5432（仅 Docker 内网）
```

- IntHub 使用独立 Compose 项目 `inthub`、独立网络和独立数据卷。
- 主机只暴露 Caddy 的 80/443；应用端口仅绑定 `127.0.0.1`，数据库不发布主机端口。
- 生产配置位于 `/opt/inthub/shared/inthub.env`，权限必须为 `0600`。
- release 位于 `/opt/inthub/releases/<git-sha>`，`/opt/inthub/current` 指向当前版本。
- 不得复用其他服务的容器、数据库、凭证、目录或 Caddy site 文件。

## 配置

从 [inthub.env.example](../../deploy/inthub/inthub.env.example) 创建生产配置。部署级访问令牌只交给 CLI，服务端保存它的 SHA-256：

```bash
token="$(openssl rand -hex 32)"
token_sha256="$(printf %s "$token" | shasum -a 256 | awk '{print $1}')"
postgres_password="$(openssl rand -hex 32)"
```

不要把变量值写入 shell history、Git、聊天或日志。`INTHUB_POSTGRES_PASSWORD` 应使用 URL 安全字符；上面的十六进制生成方式满足这一要求。

在 GitHub 账户设置中注册一个私有 GitHub App：

- Homepage URL：`https://inthub.example.com`
- User authorization callback URL：`https://inthub.example.com/api/v1/auth/github/callback`
- IntHub 不请求 OAuth scope，只读取登录所需的公开账户身份。
- 不启用 Webhook，不申请仓库或账户权限；未来需要仓库授权时再按最小权限增加。
- 将 Client ID、Client Secret 和允许登录者的 numeric GitHub user ID 写入权限为 `0600` 的生产 env 文件。不要使用可改名的 login 作为长期权限边界。

授权过程使用一次性 state 和 PKCE；登录成功后只保存 IntHub 自己的随机会话哈希。默认会话有效期为 7 天，退出登录会立即删除数据库会话。

关键配置：

| 变量 | 用途 |
| --- | --- |
| `INTHUB_RELEASE` | 完整 Git commit SHA，同时作为镜像 tag |
| `INTHUB_PACKAGE_VERSION` | 可追溯的 Python 包版本 |
| `INTHUB_DOMAIN` | 公网域名 |
| `INTHUB_BIND_PORT` | 回环端口，默认 `7250` |
| `INTHUB_API_TOKEN_SHA256` | 访问令牌的 SHA-256，不是令牌本体 |
| `INTHUB_POSTGRES_PASSWORD` | 独立 PostgreSQL 密码 |
| `INTHUB_GITHUB_CLIENT_ID` | GitHub App Client ID |
| `INTHUB_GITHUB_CLIENT_SECRET` | GitHub App Client Secret |
| `INTHUB_GITHUB_ALLOWED_USER_IDS` | 允许登录的 numeric GitHub user ID；当前生产只配置一个 |
| `INTHUB_SESSION_TTL_SECONDS` | IntHub Web 会话时长，默认 `604800`（7 天） |

## 发布

将目标 commit 放入 `/opt/inthub/releases/<git-sha>`，原子更新 `current` 链接，然后运行：

```bash
sudo docker compose \
  --project-name inthub \
  --env-file /opt/inthub/shared/inthub.env \
  --file /opt/inthub/current/deploy/inthub/compose.yaml \
  up --detach --build --remove-orphans
```

安装站点配置时，只写 `/etc/caddy/sites-enabled/inthub.caddy`。每次修改都必须从共享根配置验证后再 reload：

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
```

不要覆盖 `/etc/caddy/Caddyfile` 或其他 site 文件。

## 验证

```bash
curl --fail --silent --show-error https://inthub.example.com/healthz
curl --fail --silent --show-error https://inthub.example.com/readyz

# 未认证读取必须是 401
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  https://inthub.example.com/api/v1/projects

# Bearer 认证读取
curl --fail --silent --show-error \
  -H "Authorization: Bearer $INTHUB_TOKEN" \
  https://inthub.example.com/api/v1/projects

# GitHub 登录入口必须跳转到 github.com
curl --silent --head https://inthub.example.com/api/v1/auth/github/start
```

`/health` 与 `/healthz` 只报告进程存活；`/readyz` 还检查数据库。三个端点都不返回数据库地址、版本、凭证或项目数据。

项目同步：

```bash
export INTHUB_TOKEN='<access token>'
itt hub link --api-base-url https://inthub.example.com
itt hub sync --dry-run
itt hub sync
```

CLI 不会把 token 写进 `.intent/hub.json`。

浏览器访问站点后应看到 `Continue with GitHub`，而不是粘贴 Token 的输入框。完成 OAuth 后，`GET /api/v1/auth/me` 应返回当前 IntHub 账户；退出后旧 Cookie 再次访问该端点必须得到 `401`。

## 备份、恢复与回滚

创建 PostgreSQL 自包含备份：

```bash
mkdir -p /opt/inthub/backups
sudo docker compose \
  --project-name inthub \
  --env-file /opt/inthub/shared/inthub.env \
  --file /opt/inthub/current/deploy/inthub/compose.yaml \
  exec --no-TTY database \
  pg_dump --format=custom --username inthub --dbname inthub \
  > "/opt/inthub/backups/inthub-$(date -u +%Y%m%dT%H%M%SZ).dump"
```

恢复前先停止 `app`、另存当前数据库并在维护窗口中执行 `pg_restore`。不要未经核对直接覆盖现有数据库。

应用回滚不回滚数据：把 `/opt/inthub/current` 指回已经保留的旧 release，更新 `INTHUB_RELEASE` 与 `INTHUB_PACKAGE_VERSION`，再执行相同的 `compose up`。如果某次发布包含不可向后兼容的数据迁移，必须使用该发布配套的数据库恢复方案，而不能只切换代码。

常用诊断：

```bash
sudo docker compose --project-name inthub \
  --env-file /opt/inthub/shared/inthub.env \
  --file /opt/inthub/current/deploy/inthub/compose.yaml ps
sudo docker logs --tail 200 inthub-app
sudo docker logs --tail 200 inthub-postgres
```

日志和诊断输出不得包含访问令牌或数据库密码。
