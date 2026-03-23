# 安全策略

中文 | [English](SECURITY.md)

## 支持的版本

| 版本 | 支持状态 |
| ---- | -------- |
| 2.x  | :white_check_mark: |
| < 2.0 | :x: |

## 报告安全漏洞

如果你在 Intent CLI 或 IntHub 中发现安全漏洞，请通过 [GitHub issue](https://github.com/dozybot001/Intent/issues) 报告。如果漏洞较敏感，请先私下联系维护者，再决定是否公开披露。

我们会在 7 天内确认收到报告，并同步修复时间安排。

## 范围

- **Intent CLI**（`itt`）：本地运行，负责读写 `.intent/` JSON 文件，并通过 HTTP 与 IntHub 通信。
- **IntHub Local**：默认绑定 `127.0.0.1`，不面向公网部署。
- **`.intent/` 数据**：默认保存在本地，并通过 `.gitignore` 排除出 Git；其中可能包含项目上下文，应按本地工作区元数据同等对待。
