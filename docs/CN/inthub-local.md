# IntHub Local 使用说明

中文 | [English](../EN/inthub-local.md)

## 它是什么

IntHub Local 是 IntHub 的首个可分发形态。

它会在你的机器上运行一个本地 IntHub 实例，同时服务 API 和 Web UI，让你可以在浏览器里查看自己仓库中的语义历史。

预构建的 `bin/inthub-local.pyz` 直接随仓库提供。

## 依赖前提

- Python 3.9+
- 一个已经在使用 Intent 的本地仓库
- 该仓库配置了 GitHub `origin` remote，供 IntHub V1 绑定使用

## 启动 IntHub Local

```bash
python3 bin/inthub-local.pyz
```

默认行为：

- 监听 `http://127.0.0.1:7210`
- 数据库位于 `~/.inthub/inthub.db`
- 自动打开浏览器

## 连接你的仓库

在你自己的项目仓库里执行：

```bash
itt hub link --api-base-url http://127.0.0.1:7210
itt hub sync
```

然后在浏览器中打开 `http://127.0.0.1:7210`。

如果之后你又新增了 Intent 数据，只需要重新执行一次 `itt hub sync`，本地 IntHub 视图就会刷新。

## 常用参数

```bash
python3 bin/inthub-local.pyz --no-open
python3 bin/inthub-local.pyz --port 7211
python3 bin/inthub-local.pyz --db-path /path/to/inthub.db
```

如果你改了端口，记得在 `itt hub link --api-base-url ...` 里使用同一个地址。
