/* UI copy only. User-authored goals, checkpoints, identifiers and JSON stay intact. */
window.IntHubI18n = (() => {
  const zh = {
    "Settings": "设置", "Close": "关闭", "Preferences": "偏好设置", "Appearance": "外观", "Language": "语言", "System": "跟随系统", "Light": "浅色", "Dark": "深色",
    "Theme: System": "主题：跟随系统", "Theme: Light": "主题：浅色", "Theme: Dark": "主题：深色", "Switch theme": "切换主题",
    "All Intents": "全部意图", "Filter timeline by Intent": "按意图筛选时间线", "{count} checkpoints": "{count} 个检查点",
    "{count} incomplete checkpoints": "{count} 个检查点待补充", "{count} blocked objectives": "{count} 个目标被阻塞", "Ready to continue": "可以继续工作",
    "Overview": "概览", "Intents": "意图", "Timeline": "时间线", "Decisions": "决策", "Search": "搜索",
    "Project": "项目", "Project memory": "项目记忆",
    "Intent resources": "Intent 资源", "Intent Skill": "Intent Skill", "Official repository": "官方仓库",
    "Detects the agent you use, or asks; --host codex / claude-code overrides that. Git is optional.": "自动识别正在使用的 Agent，无法识别时会询问；可用 --host codex / claude-code 指定。Git 可选。",
    "Add the agent skill": "安装 Agent Skill", "Needs Node.js. Installs for Claude Code and Codex; add -a cursor and so on for other agents.": "需要 Node.js。默认为 Claude Code 和 Codex 安装；其他 Agent 可追加 -a cursor 等参数。",
    "Push": "推送", "Creates the project under this directory's name and pushes its semantic history.": "以当前目录名创建项目并推送语义历史。",
    "Optional: to use a different project name, link it first.": "可选：如需使用其他项目名，请先关联。",
    "Once the project hooks are trusted, tell the agent “Resume this project through Intent.” to continue later.": "信任项目 hooks 后，下次继续时告诉 Agent：「通过 Intent 恢复这个项目。」",
    "Choose a shared project name, then push its semantic history.": "选择共享项目名，然后推送语义历史。",
    "No projects yet": "暂无项目", "Checking sync": "正在检查同步", "Waiting for project": "等待项目", "Continuity status": "接续状态",
    "Current work": "当前工作", "Continuation queue": "接续队列", "Related context": "关联上下文", "Back to list": "返回列表",
    "Account": "账号", "Access token": "访问令牌", "Sign out": "退出 IntHub",
    "Delete account": "删除账号", "Opening account management…": "正在打开账号管理…",
    "Tenon returned an invalid deletion destination.": "Tenon 返回了无效的删除入口。",
    "About IntHub": "关于 IntHub", "Close About IntHub": "关闭关于 IntHub", "Version": "版本", "Publisher": "出品方",
    "IntHub, by Tenon, home": "IntHub，Tenon 出品，首页", "IntHub, by Tenon": "IntHub，Tenon 出品",
    "Project navigation": "项目导航", "Project index": "项目索引",
    "Search project": "搜索项目", "Refresh project data": "刷新项目数据", "Refreshing project data": "正在刷新项目数据",
    "Loading project data": "正在加载项目数据", "Loading continuation brief": "正在加载接续简报", "Related object detail": "关联对象详情",
    "Close related detail": "关闭关联详情", "Loading…": "正在加载…", "Loading project data…": "正在加载项目数据…",
    "Sign in to IntHub": "登录 IntHub", "Continue with your project context intact.": "保留项目上下文，继续工作。",
    "Continuation brief": "接续简报",
    "Verified": "已验证", "Boundary": "工作边界", "Next": "下一步", "Blocker": "阻塞项", "Context": "背景",
    "Decision": "决策",
    "Continue with GitHub": "使用 GitHub 继续", "Continue with Apple": "使用 Apple 继续", "Continue with email": "使用邮箱继续", "Last used": "上次使用",
    "Opening sign-in…": "正在打开登录…", "Connecting to Apple…": "正在前往 Apple…", "Connecting to GitHub…": "正在前往 GitHub…",
    "Signing in for the first time creates a Tenon Account. IntHub is made by Tenon AI, and the same account works with our other products. We only receive your basic profile and email address.": "首次登录会创建 Tenon 账号。IntHub 由榫卯 Tenon AI 出品，同一账号也可以登录我们的其他产品。我们只获取你的基本资料和邮箱。",
    "IntHub is a project continuity workspace for developers and Agents. It brings together Intent goals, Snap checkpoints and durable Decisions so work can resume with its context intact.": "IntHub 是面向开发者与 Agent 的项目接续工作台。它汇集 Intent 目标、Snap 检查点与长期 Decision，让工作在保留上下文的情况下继续。",
    "Sync semantic history from the Intent CLI, review the current continuation brief, explore the timeline and search project history.": "你可以通过 Intent CLI 同步语义历史，查看当前接续简报、浏览时间线与搜索项目历史。",
    "IntHub / developer access": "IntHub / 开发者访问", "New access token": "新建访问令牌", "New CLI token": "新的 CLI 令牌",
    "This secret is shown once. Paste it into": "令牌只显示一次。将它粘贴到", "; IntHub will not display it again.": "；IntHub 不会再次显示。",
    "Copy token": "复制令牌", "Copied": "已复制", "Done": "完成", "Creating token…": "正在创建令牌…", "Copying…": "正在复制…", "Signing out…": "正在退出…",
    "Token copied.": "令牌已复制。", "Copy failed. Select and copy the token manually.": "复制失败，请选中令牌并手动复制。",
    "Semantic goals": "语义目标", "Project constraints": "项目约束", "Semantic history": "语义历史", "Find context": "查找上下文",
    "No continuation checkpoint recorded.": "尚未记录接续检查点。", "checkpoint missing": "缺少检查点", "Checkpoint missing": "缺少检查点",
    "No active Intent. The project has no explicit current objective.": "没有活跃意图，项目当前没有明确目标。",
    "No suspended work waiting to resume.": "没有暂停待接续的工作。", "Active": "活跃", "Suspended": "已暂停", "Completed": "已完成", "Cancelled": "已取消",
    "Resolved history": "已结束的历史", "Completed and cancelled objectives": "已完成或取消的目标", "Other": "其他",
    "Active objectives": "活跃目标", "No active objective. Resume a suspended Intent or record a new one.": "没有活跃目标。请恢复暂停的意图或记录新的意图。",
    "In progress": "进行中", "On hold": "已暂停", "Unknown": "未知", "No Intent scope recorded": "尚未记录意图范围",
    "Open the Decision to inspect its recorded rationale.": "打开决策以查看已记录的理由。", "Deprecated": "已废弃", "Current constraint": "当前约束",
    "Deprecated history": "已废弃的历史", "Retired constraints kept for traceability": "保留已废弃约束以便追溯", "Active constraints": "有效约束",
    "Rules that remain binding across linked objectives.": "在关联目标中持续生效的约束。", "No active cross-Intent constraints.": "没有有效的跨意图约束。",
    "No intents.": "没有意图。", "No decisions.": "没有决策。", "No decisions linked.": "未关联决策。", "No snaps recorded.": "未记录 Snap。",
    "No linked intents.": "未关联意图。", "No linked intent.": "未关联意图。", "No snaps synced yet.": "尚未同步 Snap。",
    "Undated": "日期未知", "Today": "今天", "Yesterday": "昨天", "Blocked": "被阻塞", "Next missing": "缺少下一步", "Unblocked": "无阻塞", "Checkpoint": "检查点",
    "Search project memory": "搜索项目记忆", "Goal, boundary, decision…": "目标、边界、决策…", "Go": "搜索", "Searching…": "正在搜索…",
    "Type a query and press Go.": "输入关键词后点击搜索。", "Search the reason behind the work.": "查找工作背后的原因。",
    "Find Intent goals, Snap checkpoints and Decisions inside the current project. Use": "在当前项目中查找 Intent 目标、Snap 检查点与 Decision。使用",
    "from anywhere to return here.": "可从任意位置回到此处。", "No matches found.": "没有匹配结果。", "Select an object to inspect.": "选择对象以查看详情。",
    "Not explicitly recorded in the latest Snap.": "最新 Snap 中没有明确记录。", "Open Intent ↗": "打开意图 ↗",
    "N/A — no active Decision constrains future work.": "不适用：没有约束后续工作的有效决策。", "No workspace has completed a first sync.": "尚无工作区完成首次同步。",
    "Detached workspace": "游离工作区", "Working tree changes synced": "已同步工作区变更", "Continuity is in sync": "接续信息已同步",
    "Waiting for first sync": "等待首次同步", "Workspace health": "工作区状态", "Active decisions": "有效决策", "Raw JSON": "原始 JSON",
    "No active Intent defines the next move.": "尚无活跃意图明确下一步。",
    "History is available, but IntHub cannot name the current goal until an active Intent and a self-contained checkpoint are synced.": "历史记录可用；同步活跃意图与自包含检查点后，IntHub 才能明确当前目标。",
    "Why": "原因", "Reason": "结束原因", "Snap Timeline (": "Snap 时间线（", "Linked Decisions (": "关联决策（", "Affected Intents (": "受影响的意图（",
    "more decision(s)": "条更多决策", "more intent(s)": "个更多意图", "older snap(s)": "条更早的 Snap", "Current cross-Intent constraint": "当前跨意图约束",
    "Deprecated constraint history": "已废弃约束历史", "No Intent scope is recorded.": "未记录意图范围。", "No why provided.": "未提供原因。",
    "an unlinked Intent": "未关联的意图", "Unlinked Intent": "未关联的意图", "Semantic checkpoint for": "语义检查点所属目标：", "Continuation checkpoint": "接续检查点",
    "Constraints:": "约束：", "Parent Intent": "所属意图",

    "1. Initialize": "1. 初始化", "Run once per repo.": "每个仓库只需执行一次。", "2. Link & Sync": "2. 绑定并同步", "1. Link & Sync": "1. 绑定并同步",
    "Point CLI here, create binding, push snapshot.": "将 CLI 指向此服务，创建绑定并推送快照。", "Ensure CLI points here, then push the next snapshot.": "确认 CLI 指向此服务，再推送新快照。",
    "2. Sync Again Later": "2. 后续同步", "Push new semantic history after more work.": "完成后续工作后推送新的语义历史。",
    "Get started with IntHub": "开始使用 IntHub", "Complete the first sync": "完成首次同步", "Run these commands where your .intent/ data lives.": "在 .intent/ 数据所在的仓库中执行这些命令。",
    "Never synced": "从未同步", "Not synced": "未同步", "Synced": "已同步", "Updated": "已更新", "No active objective": "没有活跃目标", "No project linked": "未绑定项目",
    "Waiting for first project": "等待首个项目", "No projects linked yet.": "尚未绑定项目。", "Link a project to get started.": "绑定项目以开始。",
    "Link a project to build a continuation brief.": "绑定项目以生成接续简报。", "Complete the first sync to populate data.": "完成首次同步以载入数据。", "No object is available in this view.": "此视图没有可用对象。",
    "Failed to initialize.": "初始化失败。", "Unavailable": "不可用", "Unavailable (unpackaged source)": "不可用（未安装的源码）",
    "IntHub returned an invalid response.": "IntHub 返回了无效响应。", "Request failed": "请求失败", "Tenon sign-in was cancelled.": "已取消 Tenon 登录。",
    "That sign-in attempt expired. Please try again.": "登录请求已失效，请重试。", "Tenon sign-in could not be completed. Please try again.": "未能完成 Tenon 登录，请重试。", "Sign-in could not be completed.": "未能完成登录。",
    "Sign in again to continue.": "请重新登录后继续。", "Could not load data. Try again.": "无法加载数据，请重试。", "Permission denied.": "没有操作权限。", "Object no longer exists.": "对象已不存在。",
    "Login request timed out. Try again.": "登录请求超时，请重试。", "Could not prepare Tenon sign-in. Try again.": "无法准备 Tenon 登录，请重试。", "Retry": "重试", "Return to IntHub": "返回 IntHub",
    "Switch language": "切换语言", "Explanation": "说明", "No repository access is requested. Tenon manages identity; IntHub keeps its own 30-day session.": "无需仓库权限。Tenon 管理身份，IntHub 保持独立的30天会话。",
    "Search matches goals, checkpoints and decisions within the selected project. Cmd/Ctrl+K opens search.": "搜索当前项目中的目标、检查点和决策。Cmd/Ctrl+K 可打开搜索。",
    "A token grants CLI access to your own projects. It is shown once; keep it secret and revoke it when no longer needed.": "令牌供 CLI 访问你自己的项目，只显示一次。请妥善保管，不再使用时撤销。",
    "{count} decisions": "{count} 条决策", "{count} linked Intents": "{count} 个关联意图", "Applies to {count} linked Intents.": "适用于 {count} 个关联意图。",
    "Load more ({count})": "加载更多（{count}）", "{count} workspaces": "{count} 个工作区", "{count} constraints": "{count} 条约束", "{count} sources": "{count} 个来源",
    "Shared history": "共享语义历史", "History status": "历史状态", "Legacy history": "旧版历史",
    "{count} active · {missing} missing next": "{count} 个活跃目标 · {missing} 个缺少下一步", "{name} is up to date": "{name} 已更新",
    "{id} checkpoint": "{id} 检查点", "Checkpoint {id}": "检查点 {id}", "dirty": "有变更", "clean": "无变更",
    "Copy failed. Select and copy the text manually.": "复制失败，请手动选中并复制。",
    "Copy command": "复制命令",
    "Show {count} more": "再显示 {count} 条",
    "Updated {time}": "{time}更新",
    "Open Intent": "打开意图",
    "Latest checkpoint": "最新检查点",
    "View checkpoint": "查看检查点",
    "Synced {time}": "{time}同步",
    "Copy brief": "复制简报",
    "Active work": "进行中的工作",
    "Recent activity": "最近动态",
    "View timeline": "查看时间线",
    "{count} snaps": "{count} 个 Snap",
    "{count} intents": "{count} 个意图",
    "{count} active": "{count} 个进行中",
    "{count} deprecated": "{count} 条已废弃",
    "An Intent is one goal with its own outcome. Agents record them while they work.": "意图是一个有独立结果的目标，由 Agent 在工作中记录。",
    "Snaps are verified checkpoints. They appear here after the next push.": "Snap 是经过验证的检查点，下一次推送后会显示在这里。",
    "Decisions are durable rules that bind future Intents, such as an architecture choice or a product constraint.": "决策是约束后续意图的长期规则，例如架构选择或产品约束。",
    "Intent": "意图",
    "Snap": "Snap",
    "Details": "详情",
    "Created {time}": "创建于 {time}",
    "Snaps": "Snap 记录",
    "Linked decisions": "关联决策",
    "Affected Intents": "受影响的意图",
    "Install the Intent CLI": "安装 Intent CLI",
    "Requires Python 3.9+. Re-run any time to upgrade.": "需要 Python 3.9+，重复执行即可升级。",
    "Initialize your project": "初始化项目",
    "Sign in from the CLI": "在 CLI 中登录",
    "Create an access token, then paste it when the CLI asks. It is shown once.": "创建访问令牌，并在 CLI 提示时粘贴。令牌只显示一次。",
    "Link and push": "绑定并推送",
    "Welcome": "欢迎",
    "Sync semantic history from the Intent CLI, then continue from the brief here.": "通过 Intent CLI 同步语义历史，然后在这里从接续简报继续工作。",
    "Create access token": "创建访问令牌",
    "Could not load this project.": "无法加载此项目。",
    "Go to": "前往",
    "Link a project to search its history.": "绑定项目后即可搜索其历史。",
    "Checkpoints": "检查点",
    "Project data refreshed.": "项目数据已刷新。",
    "Command copied.": "命令已复制。",
    "Brief copied.": "简报已复制。",
    "Search…": "搜索…",
    "Goals, checkpoints and decisions for agent-driven development.": "为 Agent 驱动的开发保留目标、检查点与决策。",
    "Navigate": "选择",
    "Open": "打开",
    "Projects": "项目列表",
    "Back": "返回",
    "Close details": "关闭详情",
    "Search results": "搜索结果",
    "In effect": "有效",
    "{count} in effect": "{count} 条有效",
    "just now": "刚刚",
    "View all": "查看全部",
    "{count} result": "{count} 个结果",
    "{count} results": "{count} 个结果",
    "Cancel": "取消",
    "{count} incomplete checkpoint": "{count} 个检查点待补充",
    "{count} blocked objective": "{count} 个目标被阻塞",
    "{count} snap": "{count} 个 Snap",
    "{count} decision": "{count} 条决策",
    "{count} intent": "{count} 个意图",
    "{count} checkpoint": "{count} 个检查点",
    "{count} linked Intent": "{count} 个关联意图",
    "Applies to {count} linked Intent.": "适用于 {count} 个关联意图。",

    "Flow": "流转", "Flow between Intents": "意图之间的流转", "Legend": "图例", "Relations": "关系",
    "Part of": "属于", "Parts": "组成部分", "Derived from": "衍生自", "Spawned": "衍生出",
    "Succeeds": "继承自", "Succeeded by": "被继承", "Depends on": "依赖", "Needed by": "被依赖", "Conflicts with": "对立",
    "Dropped": "已放弃", "Parent ended": "上级已结束", "Handover pending": "待交接", "Handed over": "已交接",
    "Satisfied": "已满足", "Broken dependency": "依赖已失效", "Broken": "已失效", "Blocking": "阻塞中", "Unresolved conflict": "对立未解决", "Resolved": "已解决",
    "Needs attention": "需要处理", "{count} needs attention": "{count} 条需要处理", "{count} need attention": "{count} 条需要处理",
    "{count} relation": "{count} 条关系", "{count} relations": "{count} 条关系",
    "Hide ended": "隐藏已结束", "Focus on…": "聚焦于…", "Focused on {id}": "聚焦于 {id}",
    "Focus on one Intent and its direct relations": "聚焦一个意图及其直接关联",
    "No relations between Intents yet.": "意图之间还没有关系。",
    "Relations record where a goal comes from and what constrains it. Add them from the CLI; the flow appears here after the next push.": "关系记录一个目标从哪里来、受什么制约。在 CLI 中添加后，下一次推送时流转图会出现在这里。",
    "No related Intent is open. Show ended Intents to see the rest of the flow.": "没有进行中的关联意图。显示已结束的意图即可查看完整流转。",
    "Not related to other Intents": "与其他意图无关联", "No relations to other Intents.": "与其他意图没有关系。",
    "Show in Flow": "在流转图中查看", "Decisions from this Intent": "源自此意图的决策",
    "Rejoin": "汇回", "+{count} more": "还有 {count} 条",
    "Source": "来源", "Project-level": "项目级", "Not traced to one Intent; it applies across the project.": "未追溯到具体意图，适用于整个项目。",
    "Showing {shown} of {total} — refine the search": "显示前 {shown} 条，共 {total} 条，请细化搜索",
    "Part of branches off its parent and rejoins it once done or dropped. Derived from branches off without rejoining. Succeeds is a thick arrow: the lane flows on into its successor. Depends on is a thin arrow from the prerequisite: amber while blocked, green once satisfied, red if it was cancelled. Conflicts with is a dashed line marked vs until one side ends. Diamonds are Decisions; hollow ones are deprecated.": "属于：从上级分出，完成或放弃后汇回上级。衍生自：分出后不汇回。继承自：粗箭头，泳道流入接手的意图。依赖：从前置意图指来的细箭头，阻塞时为琥珀色，满足后为绿色，前置被取消则为红色。对立：标有 vs 的虚线，直到一方结束。菱形是决策，空心表示已废弃。",

    "Profile": "个人资料", "Edit in Tenon": "在 Tenon 中修改",
    "Access tokens": "访问令牌", "The Intent CLI signs in with an access token to push this account's projects. Revoke a token when a machine no longer needs it.": "Intent CLI 使用访问令牌登录，推送本账号的项目。某台机器不再需要时，请作废它的令牌。",
    "Name": "名称", "Expires in": "有效期", "{count} day": "{count} 天", "{count} days": "{count} 天", "Generate token": "生成令牌", "Generating…": "正在生成…",
    "Enter a token name.": "请输入令牌名称。", "Token created. Copy it now; it won't be shown again.": "令牌已创建。请立即复制，此后不会再显示。",
    "Created {date}": "创建于 {date}", "Last used {time}": "最近使用：{time}", "Never used": "从未使用", "Expires {date}": "{date} 到期",
    "Revoke": "作废", "Copy": "复制", "Copy it now; it won't be shown again.": "请立即复制，此后不会再显示。",
    "No active tokens. Generate one for each machine or Agent that runs the Intent CLI.": "没有有效的令牌。请为每台运行 Intent CLI 的机器或 Agent 各生成一个。",
    "Revoke {name}?": "作废 {name}？", "Every CLI that uses this token stops being able to push at once. This cannot be undone.": "使用此令牌的 CLI 会立即无法推送。此操作无法撤销。",
    "Revoke token": "作废令牌", "Revoking…": "正在作废…", "Token revoked.": "令牌已作废。",
    "Removes the account with its personal projects and access tokens. Teams you administer pass to the next member; a team with nobody else is deleted with its projects. You confirm it in Tenon's account center.": "删除账号及其个人项目和访问令牌。你管理的团队交给下一位成员；没有其他成员的团队连同项目一起删除。需在 Tenon 账号中心确认。",
    "General": "常规", "Project name": "项目名称", "Rename": "重命名", "Renaming…": "正在重命名…", "Renamed to {name}.": "已重命名为 {name}。",
    "Enter a project name.": "请输入项目名称。", "Use {count} characters or fewer.": "最多 {count} 个字符。",
    "Project names cannot contain slashes or control characters.": "项目名称不能包含斜杠或控制字符。", "Choose a name other than . or ..": "名称不能是 . 或 ..",
    "A project named {name} already exists.": "已有名为 {name} 的项目。",
    "Clones on itt 7.3 or later follow the new name on their next push or pull. Older versions report {code} until they upgrade.": "itt 7.3 及以上版本的副本会在下次推送或拉取时跟随新名称；旧版本会报告 {code}，升级后恢复正常。",
    "Export": "导出", "Download project data": "下载项目数据", "The current semantic snapshot and the revision list as JSON: everything itt pull can restore.": "以 JSON 格式下载当前语义快照和修订列表，包含 itt pull 能恢复的全部内容。",
    "Download export": "下载导出文件", "Preparing export…": "正在准备导出…", "Export downloaded.": "导出文件已下载。",
    "Danger zone": "危险操作", "Delete this project": "删除此项目", "Removes the project and its semantic history from this hub. Local .intent data is not touched.": "从此 IntHub 删除项目及其语义历史，不影响本地的 .intent 数据。",
    "Delete project": "删除项目", "Deleting…": "正在删除…", "Delete {name}?": "删除 {name}？", "Deleted {name}.": "已删除 {name}。",
    "This removes the project and its semantic history from this hub. Local .intent data is not touched. This cannot be undone.": "这会从此 IntHub 删除项目及其语义历史，不影响本地的 .intent 数据。此操作无法撤销。",
    "Type {name} to confirm.": "输入 {name} 以确认。", "Type the name exactly as shown.": "请按显示的名称准确输入。",

    "History": "历史", "{count} push": "{count} 次推送", "{count} pushes": "{count} 次推送", "First push": "首次推送", "Revision": "修订",
    "No semantic changes": "没有语义变化", "No pushes yet.": "还没有推送。",
    "Each push is one revision: what changed, who pushed it and when.": "每次推送是一条修订：改了什么、谁推送的、什么时候推送的。",
    "Each push to IntHub is one revision, like a Git commit: what it added or changed, who pushed it and when. Open one to see the objects.": "每次推送到 IntHub 是一条修订，相当于 Git 的一次 commit：新增或变更了什么、谁推送的、什么时候推送的。打开一条可以查看具体对象。",
    "Added {added}; changed {changed}": "新增 {added}，变更 {changed}", "Added {items}": "新增 {items}", "Changed {items}": "变更 {items}",
    "{count} Intent": "{count} 个意图", "{count} Intents": "{count} 个意图", "{count} Snap": "{count} 个 Snap", "{count} Snaps": "{count} 个 Snap",
    "{count} Decision": "{count} 个决策", "{count} Decisions": "{count} 个决策", ", ": "、", "{items} and {last}": "{items}、{last}",
    "Added Intents": "新增的意图", "Added Snaps": "新增的 Snap", "Added Decisions": "新增的决策", "Changed": "变更",
    "Added: {relation} {intent}": "新增关系：{relation} {intent}", "Removed: {relation} {intent}": "移除关系：{relation} {intent}",
    "Pushed by {name}": "由 {name} 推送", "{count} more not shown": "另有 {count} 个未显示", "This push added and changed nothing.": "这次推送没有新增或变更任何内容。",
    "Pushed by the account that owns this email.": "由拥有此邮箱的账号推送。",
    "Commit {sha}": "提交 {sha}", "with uncommitted changes": "含未提交的修改",
    "All authors": "全部作者", "Filter timeline by author": "按作者筛选时间线", "No checkpoints match these filters.": "没有符合筛选条件的检查点。",
    "Link your Snaps": "关联 Snap", "Sign in again to link Snaps to this account.": "请重新登录，把 Snap 关联到此账号。",
    "Snaps link to this account when their author email is {email}. Set Git to the same address:": "作者邮箱为 {email} 的 Snap 会关联到此账号。请把 Git 设成同一邮箱：",
    "Skip to main content": "跳至主要内容", "Tenon account center": "Tenon 账号中心", "Sign in": "登录", "Back to the project": "返回项目", "All projects": "全部项目",
    "Nothing has been published yet.": "这个项目还没有发布任何内容。", "Public": "公开", "Private": "私有", "Visibility": "可见性", "{count} blocked": "{count} 个被阻塞",
    "Admin": "管理员", "Member": "成员", "Viewer": "只读成员", "Role": "角色", "Role of {name}": "{name} 的角色", "You": "你", "Team": "团队", "Teams": "团队", "Members": "成员",
    "Save": "保存", "Saving…": "正在保存…", "{count} member": "{count} 位成员", "{count} members": "{count} 位成员", "{count} project": "{count} 个项目",
    "{count} projects": "{count} 个项目", "New team": "新建团队", "Create team": "创建团队", "Creating team…": "正在创建团队…", "Create a team": "创建团队", "Team name": "团队名称",
    "Team URL": "团队 URL", "Enter a team name.": "请输入团队名称。", "Enter a team URL.": "请输入团队 URL。",
    "Use lowercase letters, digits and hyphens, up to 39 characters, with no hyphen at either end.": "只能使用小写字母、数字和连字符，最多 39 个字符，首尾不能是连字符。",
    "Lowercase letters, digits and hyphens. Team projects use it in the CLI as team/project.": "使用小写字母、数字和连字符。在 CLI 中，团队项目写作 team/project。",
    "The team URL {slug} is taken.": "团队 URL {slug} 已被占用。", "You have reached the limit on teams.": "你创建的团队数量已达上限。", "Created {name}.": "已创建 {name}。",
    "Team saved.": "团队已保存。", "You are not in a team yet.": "你还没有加入任何团队。", "This team does not exist, or you are not in it.": "这个团队不存在，或者你不在其中。",
    "This team has no projects yet.": "这个团队还没有项目。", "Clones follow a new team URL on their next push or pull.": "副本会在下次推送或拉取时跟随新的团队 URL。",
    "Joined {date}": "{date} 加入", "Remove": "移除", "Remove member": "移除成员", "Removing…": "正在移除…", "Remove {name}?": "移除 {name}？",
    "Removed {name}.": "已移除 {name}。", "{name} loses access to the team's projects.": "{name} 将无法再访问团队项目。", "{name} is now {role}.": "{name} 现在是{role}。",
    "Leave team": "退出团队", "Leaving…": "正在退出…", "Leave {name}?": "退出 {name}？", "You left {name}.": "你已退出 {name}。",
    "You lose access to the team's projects until someone invites you again.": "退出后你将无法访问团队项目，除非有人再次邀请你。", "Delete team": "删除团队", "Delete this team": "删除这个团队",
    "Removes the team. It has no projects.": "删除团队。它没有任何项目。", "Removes the team and its {count} project.": "删除团队及其 {count} 个项目。",
    "Removes the team and its {count} projects.": "删除团队及其 {count} 个项目。",
    "This removes the team from this hub. This cannot be undone.": "这会从此 IntHub 删除团队。此操作无法撤销。",
    "This removes the team and its {count} project from this hub, with their history. Local .intent data is not touched. This cannot be undone.": "这会从此 IntHub 删除团队及其 {count} 个项目和历史，不影响本地的 .intent 数据。此操作无法撤销。",
    "This removes the team and its {count} projects from this hub, with their history. Local .intent data is not touched. This cannot be undone.": "这会从此 IntHub 删除团队及其 {count} 个项目和历史，不影响本地的 .intent 数据。此操作无法撤销。",
    "Invite people": "邀请成员", "Create invite link": "创建邀请链接", "Creating link…": "正在创建链接…", "Pending invites": "待接受的邀请", "{role} invite": "{role}邀请",
    "Created by {name}": "由 {name} 创建", "Invite revoked.": "邀请已作废。", "Link copied.": "链接已复制。",
    "A link works once and expires after 7 days. Anyone who opens it and signs in joins with the role you choose.": "每个链接只能使用一次，7 天后失效。打开链接并登录的人会以你选择的角色加入。",
    "Invite link created. Copy it now; it won't be shown again.": "邀请链接已创建。请立即复制，此后不会再显示。", "Team invite": "团队邀请",
    "This invite link is no longer valid.": "这个邀请链接已失效。", "Go to IntHub": "前往 IntHub", "You are already in this team.": "你已经在这个团队中。", "Open team": "打开团队",
    "Not now": "暂不加入", "Accept": "接受", "Joining…": "正在加入…", "{name} invited you to join {team} as {role}.": "{name} 邀请你以{role}身份加入 {team}。",
    "You are invited to join {team} as {role}.": "你受邀以{role}身份加入 {team}。", "You joined {name}.": "你已加入 {name}。", "Project settings": "项目设置",
    "Everyone in {team} works on this project. Manage them on the team page.": "{team} 的所有成员都在这个项目上协作。请在团队页面管理成员。", "Make public": "设为公开",
    "Make private": "设为私有", "Make {name} public?": "将 {name} 设为公开？", "Make {name} private?": "将 {name} 设为私有？",
    "Anyone on the internet can read this project. Only members can push.": "互联网上的任何人都能读取这个项目，只有成员可以推送。",
    "Only people with access to this project can read it.": "只有能访问这个项目的人可以读取它。",
    "Anyone on the internet will be able to read all its Intents, Snaps, Decisions and history. Author emails stay hidden from visitors. People who already read it may keep it.": "互联网上的任何人都将能读取它的全部 Intent、Snap、Decision 和历史。作者邮箱不会向访客显示。已经读取过的人可能会保留这些内容。",
    "Only people with access to this project will be able to read it. Visitors lose access at once.": "只有能访问这个项目的人才能读取它。访客会立即失去访问权限。",
    "This project is now public.": "这个项目现已公开。", "This project is now private.": "这个项目现已设为私有。", "My account": "我的账号", "New owner": "新所有者", "Transfer": "转移",
    "Transfer this project": "转移这个项目", "Transfer project": "转移项目", "Transferring…": "正在转移…",
    "Moves it to a team you administer, or back to your account. Clones follow on their next push or pull.": "把项目转移到你管理的团队，或转回你的账号。副本会在下次推送或拉取时跟随。",
    "Transfer {name} to {target}?": "将 {name} 转移到 {target}？", "Transferred to {target}.": "已转移到 {target}。",
    "Who can read, push and manage it changes with the owner. Its ID stays, so clones follow on their next push or pull.": "谁能读取、推送和管理它将随所有者改变。项目 ID 不变，副本会在下次推送或拉取时跟随。",
    "A project with this name already exists there.": "那里已有同名项目。", "Choose a team you administer.": "请选择你管理的团队。",
    "Make another member an admin first.": "请先把另一位成员设为管理员。", "Revoke a pending invite first.": "请先作废一个待接受的邀请。",
    "Only team admins can do this.": "只有团队管理员可以执行此操作。", "That person is not in this team.": "此人不在这个团队中。", "Team not found.": "找不到这个团队。", "This project does not exist, or you cannot see it.": "这个项目不存在，或者你无权查看。",
  };
  let language;
  try { language = localStorage.getItem("inthub.language"); } catch {}
  if (!["zh-CN", "en"].includes(language)) language = navigator.language?.startsWith("zh") ? "zh-CN" : "en";
  const incomingLanguage = new URLSearchParams(window.location?.search || "").getAll("lang");
  if (incomingLanguage.length === 1 && ["en", "zh"].includes(incomingLanguage[0])) {
    language = incomingLanguage[0] === "zh" ? "zh-CN" : "en";
    try { localStorage.setItem("inthub.language", language); } catch {}
  }
  const t = (key, values = {}) => {
    const copy = language === "zh-CN" ? zh[key] ?? key : key;
    return copy.replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? `{${name}}`));
  };
  const bindings = [];
  function bindStatic(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (node.parentElement.closest("script, style, pre, code, .brand-wordmark, .account-avatar")) continue;
      const key = node.nodeValue.trim();
      if (Object.hasOwn(zh, key)) bindings.push({ node, original: node.nodeValue, key });
    }
    for (const node of root.querySelectorAll("[aria-label], [placeholder], [title]")) {
      for (const attr of ["aria-label", "placeholder", "title"]) {
        const key = node.getAttribute(attr);
        if (Object.hasOwn(zh, key)) bindings.push({ node, attr, key });
      }
    }
    applyStatic();
  }
  function applyStatic() {
    document.documentElement.lang = language;
    for (const b of bindings) {
      if (b.attr) b.node.setAttribute(b.attr, t(b.key));
      else b.node.nodeValue = b.original.replace(b.key, t(b.key));
    }
    for (const button of document.querySelectorAll("[data-language-switch]")) {
      button.textContent = language === "zh-CN" ? "EN" : "中文";
      button.setAttribute("aria-label", language === "zh-CN" ? "Switch to English" : "切换为中文");
    }
    for (const button of document.querySelectorAll("[data-language-select]")) {
      const selected = button.dataset.languageSelect === language;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    }
  }
  function setLanguage(value) {
    if (!["zh-CN", "en"].includes(value)) return;
    language = value;
    try { localStorage.setItem("inthub.language", value); } catch {}
    applyStatic();
    window.dispatchEvent(new Event("inthub:language"));
  }
  const keyFor = copy => Object.keys(zh).find(key => zh[key] === copy) || copy;
  return { t, zh, keyFor, bindStatic, applyStatic, setLanguage, get language() { return language; } };
})();
