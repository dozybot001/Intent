[English](glossary.EN.md) | 简体中文

配对文件：[glossary.EN.md](glossary.EN.md)

# Intent 术语表

这份文档只做术语对齐。它不解释项目愿景，也不定义实现 contract。

## 核心句

Git 记录代码变化，Intent 记录采纳历史。

## 术语

- `semantic history`：不是代码 diff 的历史，而是意图、候选、采纳与决策的历史
- `intent`：当前想解决的问题或目标
- `checkpoint`：已经形成、值得比较的候选结果
- `adoption`：对某个 checkpoint 的正式采纳
- `decision`：值得长期保留的取舍理由或原则判断
- `run`：一次 agent 执行或一轮探索过程；对 automation 很重要，但不是首页主对象
- `active intent`：当前默认的问题上下文
- `current checkpoint`：当前默认的候选对象
- `Surface CLI`：给人高频使用的短命令，例如 `itt start`、`itt snap`
- `Canonical CLI`：给 agent、Skill、IDE、automation 使用的稳定对象命令，例如 `itt checkpoint create`
- `status`：面向人，回答“现在处于什么状态，下一步做什么”
- `inspect`：面向机器，输出稳定、完整、可消费的上下文结构

## 一条最小闭环

Intent 当前最重要的路径是：

`问题 -> 候选 -> 采纳`

对应到命令层就是：

`start -> snap -> adopt`

## Intent 不是什么

- 不是 Git 的替代品
- 不是 issue、PR 或 docs 系统的替代品
- 不是“记录一切”的日志归档工具
