/* UI copy only. User-authored goals, checkpoints, identifiers and JSON stay intact. */
window.IntHubI18n = (() => {
  const zh = {
    "Settings": "设置", "Appearance": "外观", "Language": "语言", "System": "跟随系统", "Light": "浅色", "Dark": "深色",
    "Theme: System": "主题：跟随系统", "Theme: Light": "主题：浅色", "Theme: Dark": "主题：深色", "Switch theme": "切换主题",
    "All Intents": "全部意图", "Filter timeline by Intent": "按意图筛选时间线", "{count} checkpoints": "{count} 个检查点",
    "{count} incomplete checkpoints": "{count} 个检查点待补充", "{count} blocked objectives": "{count} 个目标被阻塞", "Ready to continue": "可以继续工作",
    "Overview": "概览", "Intents": "意图", "Timeline": "时间线", "Decisions": "决策", "Search": "搜索",
    "Project": "项目", "Project memory": "项目记忆",
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
    "Why": "原因", "Reason": "废弃原因", "Snap Timeline (": "Snap 时间线（", "Linked Decisions (": "关联决策（", "Affected Intents (": "受影响的意图（",
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
  };
  let language;
  try { language = localStorage.getItem("inthub.language"); } catch {}
  if (!["zh-CN", "en"].includes(language)) language = navigator.language?.startsWith("zh") ? "zh-CN" : "en";
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
