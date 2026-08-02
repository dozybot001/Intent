# IntHub 生产部署

[中文](inthub-production.md) | [English](../EN/inthub-production.md)

IntHub 生产部署面向私有语义历史展示。当前身份边界是单个部署、单个共享访问令牌；浏览器会把令牌换成 12 小时的 HttpOnly、SameSite=Strict 会话 Cookie，且该 Cookie 只能读取 API。`itt hub link` 和 `itt hub sync` 等写入操作始终要求 Bearer Token。

## 数据库选择

生产环境使用 PostgreSQL，本地 `itt hub start` 继续使用 SQLite。原因不是当前单用户流量需要 PostgreSQL，而是同步写入、备份恢复、并发连接和未来迁移到多账号时，PostgreSQL 提供了更合适的长期边界。两种后端共用同一查询层和显式 `sequence_id`，CI 会同时验证 SQLite 与 PostgreSQL。

PostgreSQL 本身并不等于多租户。正式多账号仍需增加账号所有权、按账号限定的唯一键和查询、独立登录会话、授权策略、配额与数据迁移；当前共享令牌不能被描述为多用户权限模型。

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

从 [inthub.env.example](../../deploy/inthub/inthub.env.example) 创建生产配置。访问令牌本体只交给 CLI/浏览器；服务端保存它的 SHA-256：

```bash
token="$(openssl rand -hex 32)"
token_sha256="$(printf %s "$token" | shasum -a 256 | awk '{print $1}')"
postgres_password="$(openssl rand -hex 32)"
```

不要把变量值写入 shell history、Git、聊天或日志。`INTHUB_POSTGRES_PASSWORD` 应使用 URL 安全字符；上面的十六进制生成方式满足这一要求。

关键配置：

| 变量 | 用途 |
| --- | --- |
| `INTHUB_RELEASE` | 完整 Git commit SHA，同时作为镜像 tag |
| `INTHUB_PACKAGE_VERSION` | 可追溯的 Python 包版本 |
| `INTHUB_DOMAIN` | 公网域名 |
| `INTHUB_BIND_PORT` | 回环端口，默认 `7250` |
| `INTHUB_API_TOKEN_SHA256` | 访问令牌的 SHA-256，不是令牌本体 |
| `INTHUB_POSTGRES_PASSWORD` | 独立 PostgreSQL 密码 |

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
