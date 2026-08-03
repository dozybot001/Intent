# IntHub 生产部署

[中文](inthub-production.md) | [English](../EN/inthub-production.md)

IntHub 生产环境只有一条账户路径：用户通过 GitHub 首次授权时创建 IntHub 账户，之后用数据库 Web 会话登录；CLI 使用该账户签发的 access token。项目、工作区视图和同步历史都按 IntHub 账户隔离，不使用全站共享访问令牌。

GitHub App 与 IntHub 账户是两个不同边界：

- GitHub App 是平台持有的一份 OAuth 基础设施，每个部署只配置一次。
- GitHub App 的 GitHub owner 是平台操作者或平台组织，不是 IntHub 的唯一用户，也不是登录白名单。
- 普通 GitHub 用户不需要创建或拥有 App；首次登录会自动创建自己的 IntHub 账户。

## 数据与认证模型

- 浏览器：GitHub OAuth + PKCE + 一次性 state；GitHub access token 只用于读取当次身份，不持久化。
- Web 会话：随机 HttpOnly、SameSite=Strict Cookie；数据库只保存会话哈希。
- CLI：账户自行签发 `ith_pat_...` token；数据库只保存 token 哈希、名称、有效期、最后使用时间和撤销状态。
- 写入：`itt hub link`、`itt push` 及其兼容别名 `itt hub sync` 只接受账户 token；浏览器会话保持只读，仅允许管理本账户 token。
- 数据：每个项目都有 `account_id`；列表、详情、搜索与同步写入都使用同一账户边界。同一 GitHub 或 Gitee 仓库可以分别存在于不同 IntHub 账户下；GitHub OAuth 身份 provider 与仓库 provider 相互独立。

生产使用 PostgreSQL；本地 `itt hub start` 继续使用仅绑定回环地址的 SQLite 无认证模式。PostgreSQL 提供并发写入、备份恢复和未来扩展团队协作所需的长期边界，但数据库本身不替代授权模型。

## 拓扑

```text
Internet
  → Caddy :443
  → 127.0.0.1:7250
  → inthub-app :8000
  → inthub-postgres :5432（仅 Docker 内网）
```

- 使用独立 Compose 项目 `inthub`、网络和数据卷。
- 只公开 Caddy 的 80/443；应用绑定回环，PostgreSQL 不发布主机端口。
- 配置文件为 `/opt/inthub/shared/inthub.env`，权限 `0600`。
- release 位于 `/opt/inthub/releases/<git-sha>`，`/opt/inthub/current` 指向当前版本。
- 不复用其他服务的容器、数据库、凭据、目录或 Caddy site 文件。

## 首次部署与 GitHub App 配置

在 GitHub 的 Developer settings 中人工注册一个 public GitHub App。这是平台部署动作，只做一次：

- Homepage URL：`https://inthub.example.com`
- User authorization callback URL：`https://inthub.example.com/api/v1/auth/github/callback`
- Webhook：关闭
- Repository permissions：无
- Organization / account permissions：无
- `Where can this GitHub App be installed?`：`Any account`（public）；这不代表 App 可以读取用户仓库

生成 Client Secret 后，把 Client ID 与 Client Secret 直接写入服务器的 `/opt/inthub/shared/inthub.env`，权限保持 `0600`。不要把 Secret 发到聊天、写入 Git 或输出到日志：

```text
INTHUB_GITHUB_CLIENT_ID=<GitHub App Client ID>
INTHUB_GITHUB_CLIENT_SECRET=<GitHub App Client Secret>
```

再从 [inthub.env.example](../../deploy/inthub/inthub.env.example) 补齐其他配置。PostgreSQL 密码使用 URL 安全的随机值。

启动 release：

```bash
sudo docker compose \
  --project-name inthub \
  --env-file /opt/inthub/shared/inthub.env \
  --file /opt/inthub/current/deploy/inthub/compose.yaml \
  up --detach --build --remove-orphans
```

启动成功后，首页只显示正常的 `Continue with GitHub`。任意 GitHub 用户首次授权都会创建一个普通 `member` 账户；GitHub App owner 不获得额外的数据权限。

## 账户 token 与同步

登录后点击账户区的 `CLI token`。IntHub 创建一个默认有效期 90 天的账户 token，并且只展示一次：

```bash
itt auth login --api-base-url https://inthub.example.com
cd your-project
itt hub status
itt hub link
itt push --dry-run
itt push
```

若未提供 `--token` 或 `INTHUB_TOKEN`，`itt auth login` 会无回显地提示输入。它只把服务地址写入用户配置，token 则交给 Git 已配置的 credential helper。应使用操作系统安全存储支持的 helper；Git 的 `store` helper 会明文保存。也可以继续用 `--token` 仅传给单次 CLI 命令。CLI 不会将 token 写入 `.intent/hub.json`。HTTP 中使用标准 `Authorization: Bearer <token>`，这里的 Bearer 是传输方式，权限主体仍是具体 IntHub 账户。`itt auth logout` 只删除本机凭据，不撤销服务端 token；若凭据泄露或要永久移除，应在 Web UI 中撤销。

## 验证

```bash
curl --fail --silent --show-error https://inthub.example.com/healthz
curl --fail --silent --show-error https://inthub.example.com/readyz

# 未认证读取必须为 401
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  https://inthub.example.com/api/v1/projects

# 账户 token 只返回本账户项目
curl --fail --silent --show-error \
  -H "Authorization: Bearer $INTHUB_TOKEN" \
  https://inthub.example.com/api/v1/projects
```

`/health` 与 `/healthz` 只报告存活；`/readyz` 还检查 PostgreSQL。它们都不返回数据库地址、版本、凭据或项目数据。完成 OAuth 后，`GET /api/v1/auth/me` 返回当前账户；退出后旧 Cookie 必须得到 `401`。

安装 Caddy site 时只写 `/etc/caddy/sites-enabled/inthub.caddy`，并从共享根配置验证后 reload：

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
```

## 备份、发布与回滚

每次发布前同时备份：

- PostgreSQL 自包含 `pg_dump --format=custom`；
- `/opt/inthub/shared/inthub.env`，保持 `0600`。

账户模型是唯一受支持的数据模型，不提供预览版全站 token 数据库的兼容迁移。升级这类旧部署时先备份旧库，再创建当前空 schema；用户完成 GitHub 注册后运行 `itt auth login`，并在各仓库重新执行 `itt hub link` 和 `itt push`。

应用回滚不回滚数据。把 `/opt/inthub/current` 指回保留的 release、更新 release 变量并重新执行 `compose up`。包含不兼容 schema 变化的版本必须配套恢复数据库备份，不能只切换代码。

诊断只使用有界日志：

```bash
sudo docker compose --project-name inthub \
  --env-file /opt/inthub/shared/inthub.env \
  --file /opt/inthub/current/deploy/inthub/compose.yaml ps
sudo docker logs --tail 200 inthub-app
sudo docker logs --tail 200 inthub-postgres
```

日志和诊断输出不得包含账户 token、GitHub Client Secret 或 PostgreSQL 密码。
