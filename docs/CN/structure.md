[English](../EN/structure.md) | 简体中文

# 项目结构说明

用途：说明当前仓库的目录布局、各顶层路径的职责，以及哪些目录是 source of truth，哪些只是本地或生成状态。

## 这份文档回答什么

- 当前项目在安装路径清理之后的真实结构是什么样
- 哪些目录分别承载 CLI 源码、安装资源、文档、测试和本地 Intent 状态
- 哪些路径是给贡献者用的，哪些路径是给普通用户安装旅程服务的

## 这份文档不回答什么

- CLI 的完整 command contract 或 JSON schema
- 面向各 agent 的详细安装流程
- release 策略或 roadmap 优先级

## Canonical Source Tree

下面这棵树只展示当前维护中的 source-of-truth 路径，省略 `build/`、`dist/`、`.venv/`、`src/intent_cli.egg-info/` 这类生成物。

```text
Intent/
|-- AGENTS.md
|-- CHANGELOG.CN.md
|-- CHANGELOG.md
|-- LICENSE
|-- README.CN.md
|-- README.md
|-- docs/
|   |-- README.md
|   |-- CN/
|   |   |-- README.md
|   |   |-- cli.md
|   |   |-- demo.md
|   |   |-- distribution.md
|   |   |-- glossary.md
|   |   |-- i18n.md
|   |   |-- release.md
|   |   |-- roadmap.md
|   |   |-- structure.md
|   |   `-- vision.md
|   `-- EN/
|       |-- README.md
|       |-- cli.md
|       |-- demo.md
|       |-- distribution.md
|       |-- glossary.md
|       |-- i18n.md
|       |-- release.md
|       |-- roadmap.md
|       |-- structure.md
|       `-- vision.md
|-- itt
|-- pyproject.toml
|-- scripts/
|   |-- check.sh
|   |-- demo_agent.sh
|   |-- demo_log.sh
|   `-- smoke.sh
|-- setup/
|   |-- README.md
|   |-- install.sh
|   |-- manifest.json
|   |-- claude/
|   |   `-- SKILL.md
|   |-- codex/
|   |   `-- SKILL.md
|   `-- cursor/
|       |-- README.md
|       `-- intent.mdc
|-- src/
|   `-- intent_cli/
|       |-- __init__.py
|       |-- __main__.py
|       |-- cli.py
|       |-- constants.py
|       |-- core.py
|       |-- distribution.py
|       |-- errors.py
|       |-- git.py
|       |-- helpers.py
|       |-- render.py
|       `-- store.py
|-- tests/
|   `-- test_cli.py
`-- .intent/
    |-- config.json
    |-- state.json
    |-- adoptions/
    |-- checkpoints/
    |-- decisions/
    |-- intents/
    `-- runs/
```

## 顶层路径职责

- `README.md` 与 `README.CN.md`：GitHub 首页入口，同时面向贡献者和普通用户。
- `CHANGELOG.md` 与 `CHANGELOG.CN.md`：对外发布时的变更摘要。
- `AGENTS.md`：给在本仓库里工作的 coding agent 的仓库级指引。
- `pyproject.toml`：Python 打包元数据，以及 contributor 安装时的 `itt` console entrypoint 声明。
- `itt`：仓库内本地开发入口，同时也是固定 checkout 模型里会被暴露出去的命令入口。
- `src/intent_cli/`：CLI 的实际实现代码。
- `setup/`：普通用户安装资源和各 agent 的 setup 资产。
- `docs/`：中英文长文档集合。
- `scripts/`：开发期校验和演示脚本。
- `tests/`：CLI 和安装路径的自动化测试。
- `.intent/`：Intent 在本仓库内 dogfooding 时使用的本地语义历史。

## CLI 源码结构

- `cli.py`：命令解析和分发入口。
- `core.py`：工作区状态机和对象生命周期逻辑。
- `distribution.py`：固定 checkout 模型下的安装路径和 agent setup 行为。
- `store.py`：`.intent/` 本地对象存储。
- `git.py`：Git 状态检查和 linkage helper。
- `render.py`：面向人的文本输出。
- `helpers.py`、`constants.py`、`errors.py`：共享工具、退出码和错误模型支持。
- `__main__.py` 与 `__init__.py`：模块入口和包元信息胶水层。

## Setup 结构

`setup/` 是普通用户安装资源的唯一 source of truth。

- `install.sh`：GitHub 首页展示给普通用户的安装脚本。
- `manifest.json`：被 `itt integrations list`、`itt setup`、`itt doctor` 读取的 machine-readable 集成元数据。
- `codex/` 与 `claude/`：可以自动安装的 skill 资产。
- `cursor/`：当前仍需要 manual follow-up 的 Cursor helper 资产。
- `README.md`：解释固定 checkout 模型如何使用这个目录。

## 文档结构

- `docs/EN/` 与 `docs/CN/`：英文和简体中文的镜像文档树。
- `docs/*/README.md`：各语言文档索引。
- `cli.md`：命令语义和 CLI contract。
- `distribution.md`：安装路径与 agent 集成旅程。
- `structure.md`：当前这份仓库布局说明。
- `vision.md`、`roadmap.md`、`release.md`、`demo.md`、`glossary.md`、`i18n.md`：问题定义、规划、发布、演示和术语支持。

## 本地与生成状态

有些路径会出现在本地仓库里，但不属于长期维护的 source tree：

- `.intent/`：这个仓库自己的本地语义记录。
- `build/`、`dist/`：打包生成物。
- `src/intent_cli.egg-info/`：本地构建或 editable install 生成的打包元数据。
- `.venv/`：贡献者本地虚拟环境。
- `.DS_Store`：macOS 文件系统元数据，不属于项目结构。

当前普通用户安装旅程不应该依赖这些生成路径。真正维护中的运行时 source of truth 仍然是固定 checkout 加 `setup/`。
