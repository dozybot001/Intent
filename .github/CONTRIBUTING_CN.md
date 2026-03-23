# 贡献指南

中文 | [English](CONTRIBUTING.md)

感谢你对 Intent 的关注和贡献意愿。

## 开始之前

```bash
git clone https://github.com/dozybot001/Intent.git
cd Intent
pip install -e .
npx skills add dozybot001/Intent -g --all
```

在提交 PR 之前请先运行测试：

```bash
python -m pytest -q
```

## 开发流程

本项目使用 Intent 管理自身开发流程。如果你已经安装了 `itt`：

```bash
itt init          # 如果你的 fork 里还没有 .intent/
itt inspect       # 查看当前状态
```

开始一段有明确目标的工作前先创建 intent，到达有语义价值的阶段性节点时再创建 snap。

## 报告问题

请通过 [GitHub issue](https://github.com/dozybot001/Intent/issues/new?template=bug_report_CN.md) 提交问题，并尽量包含：

- 你的预期行为
- 实际发生了什么
- 相关 `itt` 命令及其 JSON 输出
- 你的 Python 版本与操作系统

## 提交改动

1. Fork 仓库并创建分支
2. 完成改动；如果行为发生变化，请补上测试
3. 运行 `python -m pytest -q` 并确认全部通过
4. 提交一份说明清晰的 pull request

## 项目结构

```text
src/intent_cli/       CLI 源码（通过 pip install . 发布）
apps/                 IntHub Local（API + Web UI）
SKILL.md              Agent skill 规范
showcase/             官方语义历史示例
docs/                 文档与参考资料
tests/                测试套件
```

## 代码风格

- 保持简单，不要过度设计。
- CLI 不引入外部依赖。
- 新命令和行为变更要配套测试。
