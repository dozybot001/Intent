# Intent Docs

这里收录 Intent 的愿景、CLI 设计和实现约束文档。

如果你是第一次进入 `docs/`，建议先从这页开始，再进入具体文档。

## 从哪里开始

- 想快速理解项目为什么存在：先看 [Intent 愿景笔记 v3](intent_vision_notes_v_3_cn.md)
- 想理解 CLI 应该长成什么样：看 [Intent CLI Design Spec v0.4](intent_cli_design_spec_v_0_4_cn.md)
- 想开始实现或校对 contract：看 [Intent CLI Implementation Contract v0.1](intent_cli_implementation_contract_v_0.md)
- 想快速建立整体认识：按 `愿景 -> 设计 -> 实现约束` 的顺序阅读

## 文档地图

### [Intent 愿景笔记 v3](intent_vision_notes_v_3_cn.md)

回答的问题：

- 为什么 agent 时代需要 semantic history
- Intent 解决的核心痛点是什么
- 它与 Git、Intent CLI、Skill、IntHub 的关系是什么

适合阅读的人：

- 第一次了解项目的人
- 想参与产品方向讨论的人
- 想先理解“为什么做”再看实现的人

### [Intent CLI Design Spec v0.4](intent_cli_design_spec_v_0_4_cn.md)

回答的问题：

- Intent CLI 的产品定位和边界是什么
- 核心对象、命令体系和主路径如何组织
- human path 与 agent path 如何区分

适合阅读的人：

- 想讨论命令设计和交互体验的人
- 想理解 README 中主路径背后完整设计的人
- 想校对对象模型与命令体系的人

### [Intent CLI Implementation Contract v0.1](intent_cli_implementation_contract_v_0.md)

回答的问题：

- 首版实现必须冻结哪些 schema 与 contract
- `.intent/`、`state.json` 和对象字段应该如何落地
- JSON 输出、错误模型、幂等语义和 non-interactive 行为如何定义

适合阅读的人：

- 开始实现 CLI 的人
- 需要对接 agent、Skill 或 IDE integration 的人
- 想检查首版边界和实现优先级的人

## 当前参考优先级（Source of Truth）

当前文档的使用原则建议如下：

- 愿景与问题定义：以 [Intent 愿景笔记 v3](intent_vision_notes_v_3_cn.md) 为准
- 产品定位、命令设计与交互主路径：以 [Intent CLI Design Spec v0.4](intent_cli_design_spec_v_0_4_cn.md) 为准
- schema、状态机、JSON contract、错误模型与实现边界：以 [Intent CLI Implementation Contract v0.1](intent_cli_implementation_contract_v_0.md) 为准

如果不同文档之间出现细节不一致，建议按下面的规则理解：

- 产品层的意图、命令语义和用户路径，优先参考 design spec
- 具体实现字段、返回结构和行为约束，优先参考 implementation contract

## 当前阅读建议

如果你只想抓住当前阶段最重要的部分，优先关注这些内容：

- `init -> start -> snap -> adopt -> log` 这条最小闭环
- `intent / checkpoint / adoption / state` 这几个首版核心对象
- `status --json` / `inspect --json` 等机器可读 contract
- Git linkage policy、错误模型和幂等语义

## 说明

- `backup/` 中的历史材料不作为当前主参考
- 根目录 [README.md](../README.md) 面向仓库首页，只保留总览与导航
