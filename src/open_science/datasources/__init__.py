"""阶段 2 · 数据源层。

operon 的 87 个数据源以**扁平命名空间**存在：24 个 `mcp_*` 聚合 server +
~63 个客户端包，彼此互相 import（run_server.py 只是把 lib/ 放上 sys.path）。
本项目**原样 vendor** 这份 lib/（见 vendor/lib/），源逻辑一行不改——它们本就是
打公共 API 的 HTTP 客户端 / 标准 MCP server。OpenHands 侧只加一层 glue：

    launcher.py   —— 复刻 operon 的 run_server.py（stdio 启动某个聚合 server）
    registry.py   —— 域→server 映射（读 vendor 的 domains.json），生成 OpenHands MCPConfig
    inject.py     —— 按关键词/领域 trigger 只注入命中域（= operon 渐进暴露）
"""
