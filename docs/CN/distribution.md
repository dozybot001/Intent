[English](../EN/distribution.md) | 简体中文

# 分发与集成设计

用途：定义 Intent CLI 与各类 agent 平台集成应该如何分发，让默认用户旅程表现为“一次安装流程”，而不是多步手动拼装。

## 这份文档回答什么

- 如何在内部保留 CLI 层与平台适配层的分离，同时不把这个分层暴露给最终用户
- 默认安装路径应该长什么样
- `skills.sh` 这类 registry 在分发里处在什么位置
- release 时应该产出哪些 CLI 与集成物料

## 这份文档不回答什么

- 安装器的具体实现细节
- 每个平台的 API 或 UI 细节
- CLI 的最终 command contract 或 JSON schema

## 与其他文档的边界

- Intent CLI、Skill、IntHub 的长期关系，以 [愿景与问题定义](vision.md) 为准
- 稳定 CLI 行为与 machine contract，以 [CLI 统一设计文档](cli.md) 为准
- 当前 CLI 阶段的 release-ready 检查项，以 [发布基线](release.md) 为准
- `v0.1.0` 之后的优先级和演进节奏，以 [路线图](roadmap.md) 为准

## 1. 产品 framing

这里其实有两类用户：

- Intent CLI 的开发者与维护者
- 希望让自己的 agent 环境理解并操作 `itt` 的 Intent 用户

在内部，Intent 仍然可以保持分层：

- 本地 CLI runtime
- 共用的 integration guidance
- 平台专属的 adapter / skill

但对外默认体验不应该要求用户先理解这些打包边界，才能开始第一次使用。

## 2. 默认用户旅程

GitHub 项目首页应该同时暴露两类命令，但它们面向不同人群：

- `git clone ...` 这类 contributor command，给开发者、维护者、贡献者使用
- 一条面向普通用户的 user command，给“我只想把 Intent 装起来并接到现有 agent 上”的人使用

例如，首页可以呈现：

```bash
git clone https://github.com/dozybot001/Intent.git
```

以及：

```bash
curl -fsSL https://raw.githubusercontent.com/dozybot001/Intent/main/setup/install.sh | bash
```

这里的关键不是“完全不能从 GitHub 仓库拉文件”，而是用户不应该被要求手动 clone 仓库、进入目录、再理解内部结构。必要文件可以在 bootstrap 过程中自动获取。

目标用户旅程应是：

1. 用户在 GitHub 首页看到 user command
2. 用户在本地终端直接运行它
3. 安装流程先在固定位置，例如 `~/.intent/repo`，创建或刷新一份本地 Intent 仓库 checkout
4. 安装流程把这份 checkout 里的 `itt` 暴露为本地命令，例如链接到 `~/.intent/bin/itt`，并在可能时把这个目录接进 PATH
5. 安装流程自动检测当前机器上已有的受支持 agent
6. 若检测到支持的平台，就把对应 skill / adapter 安装到该平台实际会读取的目录，或通过该平台支持的机制完成注册
7. 若没有检测到受支持 agent，也应先让这份 repo-backed `itt` 可用，再明确提示用户后续可以运行 `itt setup <agent>`
8. 完成后，对应 agent 应该直接拿到可用的 Intent skill，而不是只在 Intent 自己的目录里多出一份用户还需要手工处理的 bundle

`itt setup --agent auto` 仍然是 CLI 内部的重要入口，但它更适合作为安装后的显式命令面，而不是替代 GitHub 首页上的 user command。

这里的关键约束还包括：`itt` 不应再来自另一份额外安装的独立 CLI 副本，而应直接来自这份固定本地 checkout。

## 3. 内部分层

当前路径模型应该尽量具体且保持很小：

- 固定本地 checkout：`~/.intent/repo`
- 命令 launcher：`~/.intent/bin/itt`
- setup source of truth：`~/.intent/repo/setup/`
- 运行时 receipts 和 generated helpers：`~/.intent/receipts/` 与 `~/.intent/generated/`

除了这些路径之外的内容，都应该视为贡献者工具链，而不是普通用户安装旅程的一部分。

## 4. 硬边界

为了避免之后的实现再次偏移，这些边界应该保持明确：

- 不再复制第二份 `setup/` 到 `~/.intent`
- 普通用户不再额外安装第二份独立 CLI
- 运行时 setup 资产只认固定本地 checkout
- `pip install -e .` 这类 contributor flow 可以保留，但必须持续被表述为贡献者路径

GitHub 首页和文档都应该优先指向 bootstrap 流程。

## 5. 命令模型

面向用户的命令面应尽量小：

```bash
itt setup --agent auto
itt setup codex
itt setup claude
itt setup cursor
itt doctor
itt integrations list
```

这些命令应该把平台特定的目录结构、adapter 布局和注册细节都藏在后面。

## 6. 仓库结构

仓库里的 source of truth 可以收敛得很小：

```text
setup/
  install.sh
  manifest.json
  codex/
  claude/
  cursor/
```

这样可以把 bootstrap 入口、manifest 和各平台 setup 资产都收敛在一个稳定位置里，而运行时 `itt` 只需要读取 `~/.intent/repo/setup/` 这份固定 checkout。

同时也意味着，固定 checkout 本身还包含 `itt` 入口和 CLI 源码；用户面对的是同一份本地 repo，而不是“repo 一份、CLI 另一份”。

## 7. Release 产物

在当前阶段，release 物料只需要维持同一条用户旅程：

1. 包含 `itt`、`src/` 和 `setup/` 的稳定仓库快照或 release archive
2. 稳定的 bootstrap 脚本
3. machine-readable integration manifest
4. `setup/` 里的平台 setup 资产

在固定 checkout 模型稳定之前，不应该让别的分发通道变成主叙事。

## 8. 平台 setup 行为

`itt setup <agent>` 在不同平台上应尽量遵守同一套高层 contract：

- 检查固定本地 checkout 和 repo-backed `itt` 是否可用
- 把正确的 skill / adapter 安装、链接或注册到对应平台实际会读取的位置
- 写入必要的本地配置
- 跑一次轻量验证

如果某个平台暂时没有稳定的全局文件安装位置，`itt setup <agent>` 也应该诚实退化成“生成 helper 资产并告诉用户剩余的手动步骤”，而不是假装已经真正接好了。

底层实现可以不同，但用户面对的语义应该保持一致。

## 9. 设计原则

- 不要求用户为了启用集成而手动 clone Intent 仓库，但允许 bootstrap 在后台自动 clone 到固定位置
- GitHub 首页应清楚区分 contributor command 与普通用户直接运行的 user command
- 不把第三方 registry 变成唯一安装路径
- 不把 CLI 的 release 叙事绑定到某一家 agent 厂商
- 不要求用户在开始之前先搞懂 skill、adapter 和本地 binary 的区别

## 10. 当前结论

Intent 在内部应该继续保持分层，但默认对外体验应收敛成这样一条清晰旅程：

- GitHub 首页给开发者展示 clone 命令
- GitHub 首页给普通用户展示 user command
- user command 在固定位置自动 clone 本地 repo，并直接暴露这份 repo 里的 `itt`
- user command 尽可能把匹配的 agent skill 直接接好
- 若本机暂时没有可检测的 agent，也应先让这份 repo-backed `itt` 可用，再把后续 `itt setup <agent>` 路径讲清楚

当前实现可以通过 GitHub 仓库拉取或复制这份本地 repo，但对用户来说，这条路径仍然应该表现为“运行一条命令，拿到 repo-backed `itt`，并在可能时自动接好 agent”。
