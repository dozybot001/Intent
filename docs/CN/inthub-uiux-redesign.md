# IntHub UI/UX 改造计划

状态：实施中  
设计方向：Soft Spatial Cards
产品定位：面向开发者与 Agent 的项目连续性工作台

### Tenon 产品规范对齐（2026-10-04）

遵循 Tenon 子系产品统一规范，统一品牌归属、关于信息与账户服务，不统一产品内部外观。保留 IntHub 字标与墨绿、铜橙配色，产品图形使用双折页；在字标右上侧添加官方完整 Tenon 标识，本地携带 `tenon-mark.svg`，favicon 使用同一官方资产。标识最低14px、比例0.58em、间距最低4px、上移0.04em，与产品组合整体交互，小标不单独设提示或按钮。

按2026-10-04新增规范进一步落实：

- 简体中文与英文覆盖静态页面、动态对象视图、关于、错误、等待和辅助技术文案；系统语言作初始选择，界面可切换并仅保存语言偏好。用户记录的目标、事实、约束、项目名称、ID、命令和原始 JSON 不翻译。切换时保留搜索输入、当前项目、详情与令牌内容，不重新发起业务操作。
- 唯一网页登录准备路径改为同源固定 `/auth/redirect`，本地完整等待界面先绘制，再请求 `POST /api/v1/auth/tenon/prepare`。中央目的地址由后端生成且前后端均核对，15秒超时后停止等待，提供重试及返回；每次重试是新授权事务，不开空白窗口或复制登录表单。原直跳 start 接口移除，既有回调地址、PKCE、state、nonce 和短期会话不变。
- 登录、搜索、有效约束、首次同步步骤和令牌用途的辅助说明归入标题紧邻右侧的 i。入口与圆圈按标题字号适配，保持易于点击的命中区；提示采用260px基准宽、8px偏移、12px圆角及规范阴影。支持触控、悬停、聚焦、外部点击与 Escape，使用原生 top-layer 浮层防止裁切并按视窗翻转。产品正文、错误、进度和一次性令牌保存警示保持直接可读。
- 所有异步按钮即时呈现等待并阻止重复操作，成功/失败后恢复。退出失败不假装已退出；网络请求有超时。项目选择器保留自主面板并补上方向键/Home/End操作，输入及展开控件采用产品样式，不展示浏览器默认外观。
- 账户操作收纳到头像触发的自主菜单，桌面与手机都能创建 CLI 令牌或退出 IntHub；公开展示不开放私有账户操作。
- 关于和令牌对话框共用集中维护的宽高参数（最大540×540px），外框固定、正文内部滚动、标题/关闭与底部操作固定；短屏及软键盘按 visualViewport 调整。当前没有布尔选项，不人为新增开关；后续布尔控件必须采用 switch 语义的胶囊开关。

自动化验证使用 HTTP 契约与无浏览器的 JavaScript 逻辑测试，不代替所有者的视觉/触控/实际登录验收。该产品为网页，不涉及 iOS 原生语言设置。

工作台（包括公开展示）顶栏与登录页均提供「About IntHub」。使用可关闭、支持 Escape 和原生焦点管理的完整对话框，依次展示产品组合标志、实际版本、两段已实现能力说明、出品方「榫卯 Tenon AI」及官网 `https://tenon.asia/`。版本来自发布镜像构建参数 `INTHUB_VERSION`，开发环境回退到已安装包元数据，不写死产品版本；未能加载配置时明确显示不可用，不展示占位版本。

账号入口保持唯一 Tenon OIDC，不复制中央表单或第三方登录。此轮仅对齐 UIUX，不清除已完成的 Tenon 身份映射、业务数据或 CLI PAT。自动化验证版本与静态资产/API 契约，浏览器视觉及操作验收由产品所有者完成。

### 完整精修（2026-10-04）

- [排版与颜色](../../apps/inthub_web/static/styles.css)：本地 Inter v4.1 可变字体搭配系统中文字体，UI 标题与正文统一现代无衬线，品牌字标仍使用原 Avenir 字体参数。降低阴影、减少大写小标签与卡片上浮，以字号、间距和不同密度区分主内容与元信息。手机顶栏两行布局，项目名称不与所有操作按钮挤在同一行。
- [主题控制](../../apps/inthub_web/static/theme.js)：系统 / 浅色 / 深色三种偏好，仅保存 `inthub.theme`；首屏绘制前应用，登录准备页也复用。切换不重载页面或发起业务请求。状态、菜单、弹窗、说明浮层及骨架使用主题颜色，官方 Tenon 标志不变。
- [浏览交互](../../apps/inthub_web/static/app.js)：时间线按意图筛选复用已有 Snap，不新增 API。搜索、项目切换、详情与抽屉以请求身份阻止过期响应写回；错误正文提供重试。移动端自动预览不强制进入详情，抽屉开启时管理焦点、关闭时不可聚焦并恢复触发点。
- 接续可用性与同步状态分离：只有显式 Verified、Boundary、Next、Blocker 齐全且无阻塞，才表示可以继续；缺失信息保持可见，不从代码或用户文本推断。
- [纯逻辑测试](../../tests/inthub_web_logic.cjs)、[主题测试](../../tests/inthub_theme_logic.cjs)与 HTTP 静态资源测试验证行为；字体携带完整 [OFL 许可](../../apps/inthub_web/static/Inter-LICENSE.txt)。未做浏览器视觉、触控或实际任务验收，也不宣称已完成全站 WCAG 审计。当前没有多行输入与布尔选项，这两项为 N/A。

## 1. 改造目标

IntHub 的主任务不是展示 Intent、Snap 和 Decision 三类对象，而是帮助用户在最短时间内恢复正确的工作语境：

- 当前目标是什么，为什么重要；
- 已验证到什么状态；
- 当前真正的工作边界；
- 下一步与 blocker；
- 后续工作必须遵守哪些 Decision。

本轮改造把默认入口从“对象浏览器”收敛为“Continuation Brief”，同时建立可扩展到多项目、多账户和团队协作的 SaaS 页面骨架。

## 2. 设计原则

1. **接续优先**：回到项目后，Goal、Boundary、Next、Blocker 和 Decisions 必须先于历史对象出现。
2. **项目优先**：账户、Workspace、Project 和对象层级必须清晰，Intent/Snap/Decision 不再承担全局导航职责。
3. **语义优先**：展示对象之间的原因、约束、取代和接续关系，而不是把原始 JSON 当成主要界面。
4. **渐进披露**：默认视图足够完成接续，需要查证时才进入完整时间线、关系和原始数据。
5. **可靠状态**：加载、空数据、错误、未同步、dirty workspace 和缺失检查点都必须显式呈现。
6. **键盘与 URL 优先**：常用路径支持键盘；项目、标签、搜索和详情状态可深链接并正确响应前进/后退。
7. **克制的品牌感**：保留档案账本的历史气质，但不使用色条、网格和密集描边模拟控制台；语义状态依靠小型状态点与标签表达。

## 3. 信息架构

### 全局层

- Projects
- Global Search / Command Palette
- Activity（后续）
- Account & Settings

### Project 层

- Overview：Continuation Brief
- Intents：当前目标与完整目标历史
- Timeline：Snap 时间线
- Decisions：当前约束与废弃历史
- Sync & Workspaces（后续）

### Detail 层

- 对象详情
- 关联对象
- 语义时间线
- Raw JSON（高级披露）

## 4. 视觉方向：Soft Spatial Cards

- 主工作区使用浅色分层导航、冷中性画布和高对比度正文；深石墨色只保留给登录叙事区、命令与 Raw JSON 等明确的技术上下文。
- 卡片依靠圆角、留白、轻边框和多层柔和阴影建立空间关系，不使用左侧色条、内嵌高亮条或四象限硬分隔表达选中与层级。
- 暖铜色仅用于小面积品牌锚点、下一步提示和焦点状态；健康、警告与阻塞使用低饱和语义状态点或标签。
- UI 正文使用现代无衬线字体；ID、分支与命令使用等宽字体；衬线字体只用于品牌标题和少量叙事标题。
- 顶层 Continuation Brief 使用完整浮层卡片，内部检查点使用弱化的嵌套卡片；列表与详情使用更轻的表面，避免所有内容具有相同视觉权重。
- 动效集中在页面进入、面板切换和状态反馈，持续时间保持在 120–180ms，并支持 reduced motion。
- Desktop 使用多层工作台；Tablet 使用可折叠导航；Mobile 使用底部主导航和 list-to-detail 钻取。

## 5. 分阶段实施

### P0：计划与内容契约

- [x] 完成线上 Desktop/Mobile 和源码交互审查。
- [x] 确定产品北极星、信息架构与视觉方向。
- [x] 建立本计划、范围和验收标准。
- [ ] 将 `verified / boundary / next / blocker / constraints` 定义为稳定展示契约。
- [ ] 盘点空、加载、错误、无 Active Intent、多 Active Intent、存在 blocker 等数据状态。

### P1：SaaS Shell 与 Continuation Brief

- [x] 建立全局 Header、Project 导航和清晰的项目选择器。
- [x] 增加 Overview 作为默认入口。
- [x] 以 Active/Suspended Intent、最新 Snap、Decision 和 Workspace 状态生成 Continuation Brief。
- [x] 修复 Active Intent 排序，完成项不得覆盖当前目标优先级。
- [x] 移除原始 API 地址等开发者噪声，降低 Refresh 的视觉权重。
- [x] 将现有 Search 变为可达导航，并提供 `Cmd/Ctrl+K` 入口。
- [x] 建立 Desktop、Tablet 和 Mobile 响应式基础。
- [x] 将 P1 的色条、深色控制台导航和硬分隔卡片收敛为 Soft Spatial Cards 视觉系统。

P1 的视觉和交互观感由产品所有者验收；自动化侧只负责语法、数据契约、静态构建和回归测试。

### P2：对象浏览与语义时间线

- [x] 以“连续语义轨迹”替换旧柱状图 Logo，并为账户提供不依赖外部图片的确定性字母头像。
- [x] Intent 使用 Active、Suspended、Completed/Cancelled 分组和折叠。
- [x] Snap 使用按日期分组的纵向时间流，显示短标题、Next/Boundary、阻塞状态和 Intent 归属。
- [x] Snap 详情按 Verified、Boundary、Next、Blocker、Constraints 拆分，并限制详情标题的视觉尺度。
- [x] Decision 突出当前约束、影响范围和 deprecated 历史；在没有显式取代关系时不虚构 superseded 链路。
- [ ] 支持 split view、关系跳转、详情返回栈和上下文菜单。
- [ ] 补齐搜索范围、结果高亮、最近搜索与键盘结果导航。

#### Snap 展示标题契约

Snap 的存储 schema 没有独立 `title`：`what` 是已验证里程碑或紧凑接续检查点，`why` 承载原因、权衡和局部约束。IntHub 不再把完整 `what` 同时当页面标题。

- Timeline、搜索结果、关系列表和详情页标题，从 `Verified` 的首个有效语义分句生成短展示标题。
- 展示标题只在客户端计算，不写回 `.intent/`，不改变 append-only 历史，也不要求旧数据迁移。
- 完整内容继续在结构化 checkpoint、对象详情和 Raw JSON 中展示。
- 当 `what` 或 `why` 已包含显式 Verified、Boundary、Next、Blocker、Constraints 标记时，解析器可从两者合并字段；无法识别时仍保守回退到原始 `what`，不猜测缺失语义。

### P3：SaaS 账户与首次使用

- [x] 登录页采用与工作台一致的 Soft Spatial Cards，说明产品价值、展示 Continuation Brief 预览，并移除 “private archive” 单用户语义。
- [ ] 首次登录引导完成安装 CLI、Link Project 和 First Sync。
- [ ] 建立 Settings / Developer Settings / Access Tokens。
- [ ] Token 创建支持名称、有效期、一次性 Secret、复制、列表、last-used 和 revoke。
- [ ] 增加 Workspace / Sync Health 页面与错误恢复路径。

### P4：体验精修与规模化

- [x] Skeleton、Toast、搜索/详情/项目加载的正文错误与重试；只读数据不伪造乐观成功状态。
- [x] 系统/浅色/深色模式与 reduced motion；抽屉焦点管理及菜单键盘操作。
- [ ] 全站 WCAG AA 审计与所有者真实操作验收。
- [ ] 大列表分页或虚拟化。
- [ ] UX 指标与真实任务验证。
- [ ] 评估组件化前端架构；不因视觉改造机械引入框架。

## 6. 第一阶段边界

第一批实现只覆盖 P1，并复用当前 API：

- `/api/v1/projects`
- `/api/v1/projects/{id}/overview`
- `/api/v1/projects/{id}/handoff`
- `/api/v1/intents/{id}`
- `/api/v1/snaps/{id}`
- `/api/v1/decisions/{id}`
- `/api/v1/search`

当前 Snap 的接续语义仍可能位于自由文本中。P1 允许进行保守解析；无法明确识别时必须显示“未显式记录”，不得推断或生成不存在的 Next/Blocker。显式数据契约在 P2 前确定。

## 7. 验收标准

### 核心任务

- 回访用户在 30 秒内能从 Overview 正确说出 Goal、Boundary、Next、Blocker。
- 当前 Active Intent 从项目默认页一步可达，且始终先于完成项。
- 当前 Decision 在修改代码前可见；没有 Decision 时明确显示 N/A。
- 缺失 Next 或 Blocker 时明确暴露记录缺口，而不是隐藏在长文本中。

### SaaS 体验

- 新用户在不查外部文档的情况下完成首次同步流程。
- Header 不显示原始 API URL，不把 Refresh 作为主操作。
- Search 从导航和 `Cmd/Ctrl+K` 均可进入。
- Token 创建与撤销形成完整闭环，Secret 不会再次展示。

### 质量

- 1280px Desktop、768px Tablet 和 390px Mobile 无横向溢出。
- Mobile 无固定页脚遮挡，主导航和详情返回行为稳定。
- 键盘可完成导航、搜索、详情打开和返回。
- 颜色对比度达到 WCAG AA，reduced-motion 生效。
- 现有 API、认证和对象关系测试保持通过。

## 8. 不在当前范围

- 团队权限、Billing、邀请和组织管理。
- 实时协同、评论和通知中心。
- 图谱可视化和自动生成项目洞察。
- 为视觉改造新增庞大的聚合 API。
- 在缺少显式语义时由模型猜测 Next、Blocker 或 Decision。

## 9. 参考原则

- [Linear：通过层级、密度和布局降低视觉噪声](https://linear.app/now/how-we-redesigned-the-linear-ui)
- [Vercel：统一团队级与项目级导航](https://vercel.com/changelog/dashboard-navigation-redesign-rollout)
- [GitHub：上下文感知的 Command Palette](https://docs.github.com/en/get-started/accessibility/github-command-palette)
