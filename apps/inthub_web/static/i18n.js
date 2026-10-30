/* UI copy only. User-authored goals, checkpoints, identifiers and JSON stay intact. */
window.IntHubI18n = (() => {
  const zh = {
    "Settings": "设置", "Appearance": "外观", "Language": "语言", "System": "跟随系统", "Light": "浅色", "Dark": "深色",
    "Theme: System": "主题：跟随系统", "Theme: Light": "主题：浅色", "Theme: Dark": "主题：深色", "Switch theme": "切换主题",
    "All Intents": "全部意图", "Filter timeline by Intent": "按意图筛选时间线", "{count} checkpoints": "{count} 个检查点",
    "{count} incomplete checkpoints": "{count} 个检查点待补充", "{count} blocked objectives": "{count} 个目标被阻塞", "Ready to continue": "可以继续工作",
    "Overview": "概览", "Intents": "意图", "Timeline": "时间线", "Decisions": "决策", "Search": "搜索",
    "Project": "项目", "Project memory": "项目记忆",
    "Intent resources": "Intent 资源", "Intent Skill": "Intent Skill", "Official repository": "官方仓库",
    "Run once per project; Git is optional.": "每个项目初始化一次；无需 Git。", "Choose a shared project name, then push its semantic history.": "选择共享项目名，然后推送语义历史。",
    "No projects yet": "暂无项目", "Checking sync": "正在检查同步", "Waiting for project": "等待项目", "Continuity status": "接续状态",
    "Current work": "当前工作", "Continuation queue": "接续队列", "Related context": "关联上下文", "Back to list": "返回列表",
    "Account": "账号", "Private session": "私有会话", "Access token": "访问令牌", "Sign out": "退出 IntHub",
    "Account center": "账号中心", "Delete account": "删除账号", "Opening account management…": "正在打开账号管理…",
    "Tenon returned an invalid deletion destination.": "Tenon 返回了无效的删除入口。",
    "About IntHub": "关于 IntHub", "Close About IntHub": "关闭关于 IntHub", "Version": "版本", "Publisher": "出品方",
    "IntHub, by Tenon, home": "IntHub，Tenon 出品，首页", "IntHub, by Tenon": "IntHub，Tenon 出品",
    "Skip to project content": "跳至项目内容", "Project navigation": "项目导航", "Project index": "项目索引",
    "Search project": "搜索项目", "Refresh project data": "刷新项目数据", "Refreshing project data": "正在刷新项目数据",
    "Loading project data": "正在加载项目数据", "Loading continuation brief": "正在加载接续简报", "Related object detail": "关联对象详情",
    "Close related detail": "关闭关联详情", "Loading…": "正在加载…", "Loading project data…": "正在加载项目数据…",
    "Sign in to IntHub": "登录 IntHub", "Continue with your project context intact.": "保留项目上下文，继续工作。",
    "Continuation brief": "接续简报",
    "Verified": "已验证", "Boundary": "工作边界", "Next": "下一步", "Blocker": "阻塞项", "Context": "背景",
    "Decision": "决策",
    "Sign in with Tenon": "使用 Tenon 账号登录", "Connecting to Tenon…": "正在前往 Tenon 登录…",
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
